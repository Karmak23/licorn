# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, sys, time, gamin, signal

from threading   import Thread, Event
from collections import deque

from licorn.foundations         import fsapi, logging, exceptions, styles, process
from licorn.foundations.objects import LicornThread, Singleton
from licorn.core                import groups, configuration

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
cache_path    = '/var/cache/licorn/licornd.db'
socket_path   = '/var/run/licornd.sock'
syncer_port   = 3344
searcher_port = 3355
wmi_port      = 3356
buffer_size   = 16*1024
wmi_group     = 'licorn-wmi'
log_path      = '/var/log/licornd.log'
pid_path      = '/var/run/licornd.pid'
wpid_path     = '/var/run/licornd-webadmin.pid'
dname         = 'licornd'

def terminate_cleanly(signum, frame, threads = []) :
	""" Close threads, wipe pid files, clean everything before closing. """

	if signum is None :
		logging.progress("%s/master: cleaning up and stopping threads..." % dname)
	else :
		logging.warning('%s/master: signal %s received, shutting down...' % (dname,
			signum))

	for th in threads :
		th.stop()

	configuration.CleanUp()

	try : 
		for pid_file in (pid_path, wpid_path) :
			if os.path.exists(pid_file) :
				os.unlink(pid_file)
	except (OSError, IOError), e :
		logging.warning("Can't remove %s (was: %s)." % (
			styles.stylize(styles.ST_PATH, pid_path), e))

	logging.progress("%s/master: joining threads." % dname)

	for th in threads :
		th.join()

	logging.progress("%s/master: exiting." % dname)

	# be sure there aren't any exceptions left anywhere…
	time.sleep(0.5)

	sys.exit(0)
def setup_signals_handler(threads) :
	""" redirect termination signals to a the function which will clean everything. """

	def terminate(signum, frame) :
		return terminate_cleanly(signum, frame, threads)

	signal.signal(signal.SIGINT, terminate)
	signal.signal(signal.SIGTERM, terminate)
	signal.signal(signal.SIGHUP, terminate)
def exit_if_already_running() :
	if process.already_running(pid_path) :
		logging.notice("%s: already running (pid %s), not restarting." % (
			dname, open(pid_path, 'r').read()[:-1]))
		sys.exit(0)
def exit_if_not_running_root() :
	if os.getuid() != 0 or os.geteuid() != 0 :
		logging.error("%s: must be run as %s." % (dname,
			styles.stylize(styles.ST_NAME, 'root')))	
def eventually_daemonize(opts) :
	if opts.daemon : 
		process.daemonize(log_path, pid_path)
	else : 
		open(pid_path, 'w').write("%s\n" % os.getpid())

### Main Licorn daemon threads ###
# FIXME: convert these to LicornThread.
class ACLChecker(LicornThread, Singleton):
	""" A Thread which gets paths to check from a Queue, and checks them in time. """
	def __init__(self, cache, pname = dname) :
		LicornThread.__init__(self, pname)

		self.cache      = cache

		# will be filled later
		self.inotifier  = None
		self.groups     = None
	def set_inotifier(self, ino) :
		""" Get the INotifier instance from elsewhere. """
		self.inotifier = ino
	def set_groups(self, grp) :
		""" Get system groups from elsewhere. """
		self.groups = grp
	def process_message(self, event):
		""" Process Queue and apply ACL on the fly, then update the cache. """

		#logging.debug('%s: got message %s.' % (self.name, event))
		path, gid = event

		if path is None : return

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

		# FIXME: to be re-added when cache is ok.
		#self.cache.cache(path)
	def enqueue(self, path, gid) :
		""" Put an event into our queue, to be processed later. """
		if self._stop_event.isSet() :
			logging.warning("%s: thread is stopped, not enqueuing %s|%s." % (self.name, path, gid))
			return

		#logging.progress('%s: enqueuing message %s.' % (self.name, (path, gid)))
		LicornThread.dispatch_message(self, (path, gid))
class INotifier(Thread, Singleton):
	""" A Thread which collect INotify events and does what is appropriate with them. """
	_stop_event = Event()
	_to_watch   = deque()
	_to_remove  = deque()
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

