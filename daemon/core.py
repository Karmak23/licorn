# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, time, gamin
from collections import deque

from Queue              import Queue
from threading          import Thread, Event
from licorn.foundations import fsapi, logging, exceptions, styles
from licorn.core        import groups

### status codes ###
LCN_MSG_STATUS_OK      = 1
LCN_MSG_STATUS_PARTIAL = 2
LCN_MSG_STATUS_ERROR   = 254
LCN_MSG_STATUS_UNAVAIL = 255

LCN_MSG_CMD_QUERY       = 1
LCN_MSG_CMD_STATUS      = 2
LCN_MSG_CMD_REFRESH     = 3
LCN_MSG_CMD_UPDATE      = 4
LCN_MSG_CMD_END_SESSION = 254

### default paths ###
cache_path  = '/var/cache/licorn/licornd.db'
socket_path = '/var/run/licornd.sock'
socket_port = 3355
http_port   = 3356
buffer_size = 16*1024
wmi_group   = 'licorn-wmi'
log_path    = '/var/log/licornd.log'
pid_path    = '/var/run/licornd.pid'
wpid_path   = '/var/run/licornd-webadmin.pid'
dname       = 'licornd'

### Main Licorn daemon threads ###
# FIXME: convert these to LicornThread.
class ACLChecker(Thread):
	""" A Thread which gets paths to check from a Queue, and checks them in time. """
	__singleton = None
	_queue      = Queue(0)
	_stop_event = Event()
	def __new__(cls, *args, **kwargs) :
		if cls.__singleton is None :
			cls.__singleton = super(ACLChecker, cls).__new__(cls, *args, **kwargs)
		return cls.__singleton
	def __init__(self, cache, pname = dname) :

		self.name  = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		self.cache      = cache

		# will be filled later
		self.inotifier  = None
		self.groups     = None
	def set_inotifier(self, i) :
		self.inotifier = i
	def set_groups(self, g) :
		self.groups = g
	def process(self, event):
		""" Process Queue and apply ACL on the fly, then update the cache. """

		path, gid = event

		if path is None: return

		acl = self.groups.BuildGroupACL(gid, path)

		try :
			if os.path.isdir(path) :
				fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl') , -1)
				self.inotifier.just_checked.append(path)
				fsapi.auto_check_posix1e_acl(path, False, acl['default_acl'], acl['default_acl'])
				self.inotifier.just_checked.append(path)
				self.inotifier.just_checked.append(path)
			else :
				fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl'))
				self.inotifier.just_checked.append(path)
				fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')
				self.inotifier.just_checked.append(path)

		except (OSError, IOError), e :
			if e.errno != 2 :
				logging.warning("%s: problem in GAMCreated on %s (was: %s, event=%s)." % (self.getName(), path, e, event))

		#self.cache.cache(path)
	def enqueue(self, path, gid) :
		if self._stop_event.isSet() :
			logging.progress("%s: thread is stopped, not enqueuing %s|%s." % (self.getName(), path, gid))
			return

		self._queue.put((path, gid))
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		Thread.run(self)

		while not self._stop_event.isSet() :
			self.process(self._queue.get())

		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		logging.progress("%s: stopping thread." % (self.getName()))
		self._stop_event.set()
		self._queue.put((None, None))
class INotifier(Thread):
	""" A Thread which collect INotify events and does what is appropriate with them. """
	__singleton = None
	_stop_event = Event()
	_to_watch   = deque()
	_to_remove  = deque()
	def __new__(cls, *args, **kwargs) :
		if cls.__singleton is None :
			cls.__singleton = super(INotifier, cls).__new__(cls, *args, **kwargs)
		return cls.__singleton
	def __init__(self, checker, cache, pname = dname) :

		self.name  = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		self.cache      = cache
		self.aclchecker = checker
		checker.set_inotifier(self)
		self.just_checked = []

		self.mon = gamin.WatchMonitor()

		# keep track of watched directories, and func prototypes used 
		# to chk the data inside. this will avoid massive CPU usage, 
		# at the cost of a python dict.
		self.wds = []

		groups.Select(groups.FILTER_STANDARD)
		self.groups = groups

		checker.set_groups(groups)

		#self.mon.no_exists()

		for gid in groups.filtered_groups :
			group_home = "%s/%s/%s" % (groups.configuration.defaults.home_base_path,
							groups.configuration.groups.names['plural'], groups.groups[gid]['name'])

			def myfunc(path, event, gid = gid, dirname = group_home) :
				return self.process_event(path, event, gid, dirname)

			self.add_watch(group_home, myfunc)
	def process_event(self, basename, event, gid, dirname):
		""" Process Gamin events and apply ACLs on the fly. """

		if basename[-1] == '/' :
			# we received an event for the root dir of a new watch.
			# this is a duplicate of the parent/new_dir. Just discard
			# it.
			return

		# with Gamin, sometimes it is an abspath, sometimes not.
		# this happens on GAMChanged (observed the two), and 
		# GAMDeleted (observed only abspath).
		if basename[0] == '/' :
			path = basename
		else :
			path = '%s/%s' % (dirname, basename)

		if event == gamin.GAMExists and path in self.wds :
			# skip already watched directories, and /home/groups/*
			return

		if os.path.islink(path) or fsapi.is_backup_file(path) :
			logging.debug("%s: discarding Inotify event on %s, it's a symlink or a backup file." % (self.getName(), styles.stylize(styles.ST_PATH, path)))
			return

		if event in (gamin.GAMExists, gamin.GAMCreated) :

			logging.debug("%s: Inotify %s %s." %  (self.getName(), styles.stylize(styles.ST_MODE, 'GAMCreated/GAMExists'), path))

			try :
				if os.path.isdir(path) :
					self._to_watch.append((path, gid))

				self.aclchecker.enqueue(path, gid)

			except (OSError, IOError), e :
				if e.errno != 2 :
					logging.warning("%s: problem in GAMCreated on %s (was: %s, event=%s)." % (self.getName(), path, e, event))

		elif event == gamin.GAMChanged :

			if path in self.just_checked :
				# skip the first GAMChanged event, it was generated
				# by the CHK in the GAMCreated part.
				self.just_checked.remove(path)
				return

			logging.debug("%s: Inotify %s on %s." %  (self.getName(),
				styles.stylize(styles.ST_URL, 'GAMChanged'), path))

			self.aclchecker.enqueue(path, gid)

		elif event == gamin.GAMMoved :

			logging.progress('%s: Inotify %s, not handled yet %s.' % (self.getName(), 
				styles.stylize(styles.ST_PKGNAME, 'GAMMoved'), styles.stylize(styles.ST_PATH, path)))

		elif event == gamin.GAMDeleted :
			# if a dir is deleted, we will get 2 GAMDeleted events: 
			#  - one for the dir watched (itself deleted)
			#  - one for its parent, signaling its child was deleted.

			logging.debug("%s: Inotify %s for %s." %  (self.getName(), 
				styles.stylize(styles.ST_BAD, 'GAMDeleted'), styles.stylize(styles.ST_PATH, path)))

			# we can't test if the “path” was a dir, it has just been deleted
			# just try to delete it, wait and see. If it was, this will work.
			self._to_remove.append(path)

			# TODO: remove recursively if DIR.
			#self.cache.removeEntry(path)

		elif event in (gamin.GAMEndExist, gamin.GAMAcknowledge) :
			logging.debug('%s: Inotify %s for %s.' % (self.getName(), styles.stylize(styles.ST_REGEX, 'GAMEndExist/GAMAcknowledge'), path))

		else :
			logging.debug('%s: unhandled Inotify event “%s” %s.' % (self.getName(), event, path))
	def add_watch(self, path, func) :

		if path in self.wds :
			return 0

		self.wds.append(path)
		logging.info("%s: %s inotify watch for %s [total: %d]." % (self.getName(),
			styles.stylize(styles.ST_OK, 'adding'),
			styles.stylize(styles.ST_PATH, path),
			len(self.wds)))
		return self.mon.watch_directory(path, func)
	def remove_watch(self, path) :
		if path in self.wds :
			try :
				self.wds.remove(path)
				logging.info("%s: %s inotify watch for %s [left: %d]." % (self.getName(), 
					styles.stylize(styles.ST_BAD, 'removing'),
					styles.stylize(styles.ST_PATH, path),
					len(self.wds)))

				# TODO: recurse subdirs if existing, to remove subwatches
				ret = self.mon.stop_watch(path) 
				return ret
			except gamin.GaminException :
				pass
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		Thread.run(self)

		try :
			already_waited = False
			while not self._stop_event.isSet() :

				while (len(self._to_remove) > 0) :
					# remove as many watches as possible in the same time,
					# to help relieve the daemon.
					self.remove_watch(self._to_remove.pop())

					# don't forget to handle_events(), to flush the GAM queue
					self.mon.handle_events()


				if len(self._to_watch) :
					# add one path at a time, to not stress the daemon, and
					# make new inotified paths come smoother.

					path, gid = self._to_watch.pop()
					def myfunc(path, event, gid = gid, dirname = path) :
						return self.process_event(path, event, gid, dirname)
					self.add_watch(path, myfunc)

					# don't forget to handle_events(), to flush the GAM queue
					self.mon.handle_events()

				while self.mon.event_pending() :
					self.mon.handle_one_event()
					self.mon.handle_events()
					already_waited = False
				else :
					if already_waited :
						self.mon.handle_events()
						time.sleep(0.01)
					else :
						already_waited = True
						self.mon.handle_events()
						time.sleep(0.001)
		except :
			if not self._stop_event.isSet() :
				raise

		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		if Thread.isAlive(self) and not self._stop_event.isSet() :
			logging.progress("%s: stopping thread." % (self.getName()))

			self._stop_event.set()

			while len(self.wds) :
				rep = self.wds.pop()
				logging.info("%s: %s inotify watch for %s [left: %d]." % (self.getName(), 
					styles.stylize(styles.ST_BAD, 'removing'),
					styles.stylize(styles.ST_PATH, rep),
					len(self.wds)))
				self.mon.stop_watch(rep)
				self.mon.handle_events()

			del self.mon

