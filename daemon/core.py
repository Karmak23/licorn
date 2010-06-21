# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, sys, time, gamin, signal

from threading   import Thread, Event, Semaphore
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
wpid_path     = '/var/run/licornd-wmi.pid'
wlog_path     = '/var/log/licornd-wmi.log'
dname         = 'licornd'

def terminate_cleanly(signum, frame, threads = []):
	""" Close threads, wipe pid files, clean everything before closing. """

	if signum is None:
		logging.progress("%s/master: cleaning up and stopping threads..." % \
			dname)
	else:
		logging.warning('%s/master: signal %s received, shutting down...' % (
			dname, signum))

	for th in threads:
		th.stop()

	configuration.CleanUp()

	try:
		for pid_file in (pid_path, wpid_path):
			if os.path.exists(pid_file):
				os.unlink(pid_file)
	except (OSError, IOError), e:
		logging.warning("Can't remove %s (was: %s)." % (
			styles.stylize(styles.ST_PATH, pid_path), e))

	logging.progress("%s/master: joining threads." % dname)

	for th in threads:
		th.join()

	logging.progress("%s/master: exiting." % dname)

	# be sure there aren't any exceptions left anywhere…
	time.sleep(0.5)

	sys.exit(0)
def setup_signals_handler(threads):
	""" redirect termination signals to a the function which will clean everything. """

	def terminate(signum, frame):
		return terminate_cleanly(signum, frame, threads)

	signal.signal(signal.SIGINT, terminate)
	signal.signal(signal.SIGTERM, terminate)
	signal.signal(signal.SIGHUP, terminate)
def exit_if_already_running():
	if process.already_running(pid_path):
		logging.notice("%s: already running (pid %s), not restarting." % (
			dname, open(pid_path, 'r').read()[:-1]))
		sys.exit(0)
def exit_if_not_running_root():
	if os.getuid() != 0 or os.geteuid() != 0:
		logging.error("%s: must be run as %s." % (dname,
			styles.stylize(styles.ST_NAME, 'root')))
def eventually_daemonize(opts):
	if opts.daemon:
		process.daemonize(log_path, pid_path)
	else:
		process.write_pid_file(pid_path)

### Main Licorn daemon threads ###
# FIXME: convert these to LicornThread.
class ACLChecker(LicornThread, Singleton):
	""" A Thread which gets paths to check from a Queue, and checks them in time. """
	def __init__(self, cache, pname = dname):
		LicornThread.__init__(self, pname)

		self.cache      = cache

		# will be filled later
		self.inotifier  = None
		self.groups     = None
	def set_inotifier(self, ino):
		""" Get the INotifier instance from elsewhere. """
		self.inotifier = ino
	def set_groups(self, grp):
		""" Get system groups from elsewhere. """
		self.groups = grp
	def process_message(self, event):
		""" Process Queue and apply ACL on the fly, then update the cache. """

		#logging.debug('%s: got message %s.' % (self.name, event))
		path, gid = event

		if path is None: return

		acl = self.groups.BuildGroupACL(gid, path)

		try:
			if os.path.isdir(path):
				fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl') , -1)
				#self.inotifier.gam_changed_expected.append(path)
				fsapi.auto_check_posix1e_acl(path, False, acl['default_acl'], acl['default_acl'])
				#self.inotifier.gam_changed_expected.append(path)
				#self.inotifier.prevent_double_check(path)
			else:
				fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl'))
				#self.inotifier.prevent_double_check(path)
				fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')
				#self.inotifier.prevent_double_check(path)

		except (OSError, IOError), e:
			if e.errno != 2:
				logging.warning("%s: problem in GAMCreated on %s (was: %s, event=%s)." % (self.name, path, e, event))

		# FIXME: to be re-added when cache is ok.
		#self.cache.cache(path)
	def enqueue(self, path, gid):
		""" Put an event into our queue, to be processed later. """
		if self._stop_event.isSet():
			logging.warning("%s: thread is stopped, not enqueuing %s|%s." % (self.name, path, gid))
			return

		#logging.progress('%s: enqueuing message %s.' % (self.name, (path, gid)))
		LicornThread.dispatch_message(self, (path, gid))
class INotifier(Thread, Singleton):
	""" A Thread which collect INotify events and does what is appropriate with them. """
	_stop_event = Event()
	_to_add   = deque()
	_to_remove  = deque()

	_ino_files  = 0
	_ino_dirs   = 0

	def __init__(self, checker, cache, pname = dname):

		Thread.__init__(self)

		self.name = "%s/%s" % (
			pname, str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self.cache      = cache
		self.aclchecker = checker
		checker.set_inotifier(self)
		#
		# the next data structures are used to predict GAM behavior, to avoid
		# doing things multiple times, and avoid missing events.
		#
		self.gam_ack_expected      = deque()
		self.gam_created_expected  = deque()
		self.gam_exists_expected   = deque()
		self.gam_changed_expected  = deque()
		self.gam_endexist_expected = deque()

		self.mon = gamin.WatchMonitor()

		# keep track of watched directories, and func prototypes used
		# to chk the data inside. this will avoid massive CPU usage,
		# at the cost of a python dict.
		self.wds = deque()
		self.wds_sem = Semaphore()

		groups.Select(groups.FILTER_STANDARD)
		self.groups = groups

		checker.set_groups(groups)

		# disable the Exists() calls at gamin's launch ?
		#self.mon.no_exists()

		for gid in groups.filtered_groups:
			group_home = "%s/%s/%s" % (groups.configuration.defaults.home_base_path,
							groups.configuration.groups.names['plural'], groups.groups[gid]['name'])

			def myfunc(path, event, gid = gid, dirname = group_home):
				return self.process_event(path, event, gid, dirname)

			self.add_watch(group_home, myfunc)
	def process_event(self, basename, event, gid, dirname):
		""" Process Gamin events and apply ACLs on the fly. """

		logging.debug('''NEW inotify event %d on %s.''' % (event,
			styles.stylize(styles.ST_PATH,
			basename if basename[0] == '/' else '%s/%s' % (
				dirname, basename))))

		if basename[-1] == '/':
			# we received an event for the root dir of a new watch.
			# this is a duplicate of the parent/new_dir. Just discard it.
			logging.debug('''SKIPDUP Inotify event on %s.''' % (
				styles.stylize(styles.ST_PATH, basename)))
			return

		# with Gamin, sometimes it is an abspath, sometimes not.
		# this happens on GAMChanged (observed the two), and
		# GAMDeleted (observed only abspath).
		if basename[0] == '/':
			path = basename
		else:
			path = '%s/%s' % (dirname, basename)

		if os.path.islink(path):
			# or fsapi.is_backup_file(path):
			logging.debug('''DISCARD Inotify event on symlink %s.'''\
				% (styles.stylize(styles.ST_PATH, path)))
			return

		if event == gamin.GAMExists:
			try:
				if os.path.isdir(path):
					if path in self.wds:
						# skip already watched directories, and /home/groups/*

						logging.debug('''SKIP Inotify %s event on already watched %s.''' % (
							styles.stylize(styles.ST_MODE, 'GAMExists'),
							styles.stylize(styles.ST_PATH, path)))
						return
					else:
						self._to_add.append((path, gid))
				else:
					# path is a file, check it.
					self.aclchecker.enqueue(path, gid)

			except (OSError, IOError), e:
				if e.errno != 2:
					logging.warning('''%s: problem in GAMExists on %s'''
					''' (was: %s, event=%s).''' % (self.name,
					path, e, event))

		elif event == gamin.GAMCreated:

			logging.debug("%s Inotify on %s." % (
				styles.stylize(styles.ST_MODE, 'GAMCreated'), path))

			try:
				if os.path.isdir(path):
					self._to_add.append((path, gid))

				self.aclchecker.enqueue(path, gid)

			except (OSError, IOError), e:
				if e.errno != 2:
					logging.warning('''%s: problem in GAMCreated on %s'''
					''' (was: %s, event=%s).''' % (self.name,
					path, e, event))

		elif event == gamin.GAMChanged:

			if path in self.gam_changed_expected:
				# skip the first GAMChanged event, it was generated
				# by the CHK in the GAMCreated part.
				self.gam_changed_expected.remove(path)

				logging.debug('''QUICKSKIP GAMChanged on %s.''' % (
					styles.stylize(styles.ST_PATH, basename)))
				return

			else:

				logging.debug("%s Inotify on %s." %  (
					styles.stylize(styles.ST_URL, 'GAMChanged'),
					styles.stylize(styles.ST_PATH, path)))

				self.aclchecker.enqueue(path, gid)

		elif event == gamin.GAMMoved:

			logging.progress('%s: Inotify %s, not handled yet %s.' % (
				self.name,
				styles.stylize(styles.ST_PKGNAME, 'GAMMoved'),
				styles.stylize(styles.ST_PATH, path)))

		elif event == gamin.GAMDeleted:
			# if a dir is deleted, we will get 2 GAMDeleted events:
			#  - one for the dir watched (itself deleted)
			#  - one for its parent, signaling its child was deleted.

			logging.debug("%s Inotify on %s." %  (
				styles.stylize(styles.ST_BAD, 'GAMDeleted'),
				styles.stylize(styles.ST_PATH, path)))

			# we can't test if the “path” was a dir, it has just been deleted
			# just try to delete it, wait and see. If it was, this will work.
			self._to_remove.append(path)

			# TODO: remove recursively if DIR.
			#self.cache.removeEntry(path)

		elif event == gamin.GAMEndExist:
			logging.debug('%s Inotify on %s.' % (
				styles.stylize(styles.ST_REGEX, 'GAMEndExist'),
				styles.stylize(styles.ST_PATH, path)))
			if path in self.gam_endexist_expected:
				logging.debug('''QUICKSKIP GAMEndExist on %s.''' % (
					styles.stylize(styles.ST_PATH, basename)))
				self.gam_endexist_expected.remove(path)

		elif event == gamin.GAMAcknowledge:
			if path in self.gam_ack_expected:
				# skip the GAMAcknoledge event, it is generated
				# by the rmdir part.
				self.gam_ack_expected.remove(path)
				logging.debug('''QUICKSKIP GAMAcknoledge on %s.''' % (
					styles.stylize(styles.ST_PATH, basename)))

			else:
				logging.warning('UNHANDLED %s Inotify on %s.' % (
				styles.stylize(styles.ST_REGEX, 'GAMAcknowledge'),
				styles.stylize(styles.ST_PATH, path)))

		else:
			logging.progress('UNHANDLED Inotify “%s” on %s.' % (
				styles.stylize(styles.ST_REGEX, event),
				styles.stylize(styles.ST_PATH, path)))
	def add_watch(self, path, func):

		#if path in self.wds:
		#	return 0

		self.wds_sem.acquire()
		self.wds.append(path)
		self.wds_sem.release()

		logging.info('''%s: %s inotify watch for %s [total: %d] [to_add: %d] '''
			'''[to_rem: %d].''' % (
			self.name,
			styles.stylize(styles.ST_OK, 'adding'),
			styles.stylize(styles.ST_PATH, path),
			len(self.wds),
			len(self._to_add),
			len(self._to_remove)
			))

		return self.mon.watch_directory(path, func)
	def remove_watch(self, path):
		"""Remove a dir and all its subdirs from our GAM WatchMonitor. """
		try:
			import copy
			wds_temp = copy.copy(self.wds)
			for watched in wds_temp:

				#print '%s\n%s' % (path, watched)

				if path in watched:
					self.remove_one_watch(watched)

			logging.debug('''remaining watches: %s.''' % self.wds)

		except gamin.GaminException, e:
			logging.warning('''%s.remove_watch(): exception %s.''' % e)
	def remove_one_watch(self, path):
		""" Remove a single watch from the GAM WatchMonitor."""
		try:
			self.gam_ack_expected.append(path)
			self.mon.stop_watch(path)

			self.wds_sem.acquire()
			self.wds.remove(path)
			self.wds_sem.release()

			logging.info("%s: %s inotify watch for %s [total: %d]." % (
				self.name,
				styles.stylize(styles.ST_BAD, 'removed'),
				styles.stylize(styles.ST_PATH, path),
				len(self.wds)))

		except KeyError, e:
			logging.warning(e)

	def run(self):
		logging.progress("%s: thread running." % (self.name))
		Thread.run(self)

		try:
			already_waited = False
			#last_lens = (0, 0, 0, 0, 0, 0, 0, 0)
			time_count = 0
			while not self._stop_event.isSet():

				lens = (
					len(self.wds),
					len(self._to_add),
					len(self._to_remove),
					len(self.gam_ack_expected),
					len(self.gam_exists_expected),
					len(self.gam_endexist_expected),
					len(self.gam_created_expected),
					len(self.gam_changed_expected)
					)

				if time_count >= 100000:
					logging.notice('''%s: queues stati: [total: %d] '''
						'''[add: %d] [rem: %d] [ack: %d] '''
						'''[ext: %d] [end: %d] [cre: %d] [chg: %d].''' % (
						self.name,
						lens[0], lens[1], lens[2], lens[3],
						lens[4], lens[5], lens[6], lens[7]
							)
						)
					#last_lens = lens
					time_count = 0

					if(lens[7] > 0):
						logging.info('chg: %s' % \
						str(self.gam_changed_expected).replace(', ', ',\n\t'))

				while len(self._to_remove):
					# remove as many watches as possible in the same time,
					# to help relieve the daemon.
					self.remove_watch(self._to_remove.popleft())

					# don't forget to handle_events(), to flush the GAM queue
					self.mon.handle_events()

				add_count = 0
				while add_count < 10 and len(self._to_add):
					path, gid = self._to_add.popleft()

					def myfunc(path, event, gid = gid, dirname = path):
						return self.process_event(path, event, gid, dirname)

					self.add_watch(path, myfunc)

					# don't forget to handle_events(), to flush the GAM queue
					self.mon.handle_events()
					add_count += 1

				while self.mon.event_pending():
					self.mon.handle_one_event()
					self.mon.handle_events()
					already_waited = False
				else:
					if already_waited:
						self.mon.handle_events()
						time.sleep(0.01)
						time_count += 100
					else:
						already_waited = True
						self.mon.handle_events()
						time.sleep(0.001)
						time_count += 10

		except:
			if not self._stop_event.isSet():
				raise

		logging.progress("%s: thread ended." % (self.name))
	def stop(self):
		if Thread.isAlive(self) and not self._stop_event.isSet():
			logging.progress("%s: stopping thread." % (self.name))
			import copy
			wds_temp = copy.copy(self.wds)
			for watched in wds_temp:
				self.remove_one_watch(watched)

			self._stop_event.set()

			del self.mon

