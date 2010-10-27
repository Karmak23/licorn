# -*- coding: utf-8 -*-
"""
Licorn Daemon inotifier thread.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, time, gamin

from threading   import Thread, Event, Semaphore, RLock, Timer
from collections import deque

from licorn.foundations           import logging, styles
from licorn.foundations.objects   import Singleton
from licorn.foundations.constants import filters, gamin_events
from licorn.foundations.ltrace    import ltrace

from licorn.daemon.core         import dname

class INotifier(Thread, Singleton):
	""" A Thread which collect INotify events and does what is appropriate with them. """

	def __init__(self, checker, cache, configuration, groups, pname=dname,
		disable_boot_check=False):

		Thread.__init__(self)

		self.name = "%s/%s" % (
			pname, str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self.lock        = RLock()
		self._stop_event = Event()
		self._to_add     = deque()
		self._to_remove  = deque()

		self.cache      = cache
		self.aclchecker = checker
		checker.set_inotifier(self)

		# the next data structures are used to predict GAM behavior, to avoid
		# doing things multiple times, and avoid missing events.
		self.expected = {
			gamin.GAMAcknowledge: deque(),
			gamin.GAMChanged: deque(),
			gamin.GAMCreated: deque(),
			gamin.GAMDeleted: deque(),
			gamin.GAMExists: deque(),
			gamin.GAMEndExist: deque()
			}

		self.mon = gamin.WatchMonitor()

		# keep track of watched directories, and func prototypes used
		# to chk the data inside. this will avoid massive CPU usage,
		# at the cost of a python dict.
		self.wds = []

		self.groups = groups
		self.configuration = configuration
		self.users = groups.users

		checker.set_groups(groups)

		# at launch, the gam_server will run Exists() calls on all files and
		# directories monitored. This will permit us to check all entries
		# in shared dirs, and apply good permissions / ACLs if needed. Disabling
		# this feature makes inotifier thread be ready to anwser standard
		# requests faster (otherwise they are put in the queue, after or between
		# Exists() requests), but doesn't ensure all shared data are in a
		# consistent state.
		if disable_boot_check:
			self.mon.no_exists()

		self.watch_configuration_files()

		for gid in groups.Select(filters.STD):
			self.add_group_watch(gid)
	def watch_configuration_files(self):
		""" monitor important configuration files, to know when another program
			touch them, and apply appropriate actions on change. """

		def reload_controller_unix(path, controller, *args, **kwargs):
			""" Timer() callback for watch threads.
			*args and **kwargs are not used. """
			logging.notice('%s: configuration file %s changed, reloading controller %s.' %
				(self.name, styles.stylize(styles.ST_PATH, path), controller))
			controller.reload_backend('unix')

		def event_on_config_file(path, event, controller, index):
			""" We only watch GAMCreated events, because when
				{user,group}{add,mod,del} change their files, they create it
				from another, everytime (for atomic reasons). We, in licorn
				overwrite them, and this will generate a GAMChanged event,
				which permits us to distringuish between the different uses.
			"""
			assert ltrace('inotifier',
				'gam event %s on %s -> controller %s (index %s)' % (
				gamin_events[event], path, controller, index))

			if event == gamin.GAMCreated:
				create_thread = False
				try:
					if not self.conffiles_threads[index].isAlive():
						self.conffiles_threads[index].join()
						del self.conffiles_threads[index]
						create_thread = True
				except (KeyError, AttributeError):
					create_thread = True

				if create_thread:
					self.conffiles_threads[index] = Timer(0.25,
						reload_controller_unix, [ path, controller ])
					self.conffiles_threads[index].start()

		self.conffiles_threads = {}

		def event_on_passwd(path, event):
			return event_on_config_file(path, event, self.users, 1)
		def event_on_group(path, event):
			return event_on_config_file(path, event, self.groups, 2)

		for watched_file, callback_func in (
				('/etc/passwd', event_on_passwd),
				('/etc/shadow', event_on_passwd),
				('/etc/group', event_on_group),
				('/etc/gshadow', event_on_group)
			):
			self.add_watch(watched_file, callback_func,	is_dir=False)
	def del_group_watch(self, gid):
		""" delete a group watch. """
		self.remove_watch("%s/%s/%s" % (
			self.groups.configuration.defaults.home_base_path,
			self.groups.configuration.groups.names.plural,
			self.groups.gid_to_name(gid)))
	def add_group_watch(self, gid):
		""" add a group watch. """

		group_home = "%s/%s/%s" % (
			self.groups.configuration.defaults.home_base_path,
			self.groups.configuration.groups.names.plural,
			self.groups.gid_to_name(gid))

		def myfunc(path, event, gid=gid, dirname=group_home):
			return self.process_event(path, event, gid, dirname)

		self.add_watch(group_home, myfunc)
	def process_event(self, basename, event, gid, dirname):
		""" Process Gamin events and apply ACLs on the fly. """

		# with Gamin, sometimes it is an abspath, sometimes not.
		# this happens on GAMChanged (observed the two), and
		# GAMDeleted (observed only abspath).
		if basename[0] == '/':
			path = basename
		else:
			path = '%s/%s' % (dirname, basename)

		assert ltrace('inotifier', '''NEW Inotify event %s on %s.''' % (
			gamin_events[event], styles.stylize(styles.ST_PATH, path)))

		if path[-1] == '/' :
			if event in (gamin.GAMCreated, gamin.GAMDeleted, gamin.GAMChanged):
				if path in self.expected[event]:
					# we received an event for the root dir of a new watch.
					# this is a duplicate of the parent/new_dir. Just discard it.
					assert ltrace('inotifier', '''SKIPDUP Inotify event %s '''
						'''on %s.''' % (
						styles.stylize(styles.ST_COMMENT, gamin_events[event]),
						styles.stylize(styles.ST_PATH, basename)))
					self.expected[event].remove(path)
					return
				elif event == gamin.GAMDeleted:
					# this is an original event coming from a directory
					# deletion, but this will fail unless we strip out this
					# ending '/'.
					path = path[:-1]
			else:
				logging.info('''Strange (but handled anyway) inotify event '''
					'''%s on %s.''' % (
					styles.stylize(styles.ST_COMMENT, gamin_events[event]),
					styles.stylize(styles.ST_PATH, basename)))

		if os.path.islink(path):
			# or fsapi.is_backup_file(path):
			assert ltrace('inotifier', '''DISCARD Inotify event on symlink %s.'''\
				% (styles.stylize(styles.ST_PATH, path)))
			return

		if event == gamin.GAMExists:
			try:
				if os.path.isdir(path):
					#if path in self.wds:
					if path in self.mon.objects.keys():
						# skip already watched directories, and /home/groups/*

						assert ltrace('inotifier', '''SKIP Inotify event %s '''
							'''on already watched directory %s.''' % (
							styles.stylize(styles.ST_MODE, 'GAMExists'),
							styles.stylize(styles.ST_PATH, path)))
						return
					else:
						with self.lock:
							self._to_add.append((path, gid))
				else:
					# path is a file, check it.
					assert ltrace('inotifier', '''CHECK file %s.''' % (
						styles.stylize(styles.ST_PATH, path)))
					self.aclchecker.enqueue(path, gid)

			except (OSError, IOError), e:
				if e.errno != 2:
					logging.warning('''%s: problem in GAMExists on %s'''
					''' (was: %s, event=%s).''' % (self.name,
					path, e, event))

		elif event == gamin.GAMCreated:

			assert ltrace('inotifier', "%s Inotify on %s." % (
				styles.stylize(styles.ST_MODE, 'GAMCreated'), path))

			try:
				if os.path.isdir(path):
					with self.lock:
						self._to_add.append((path, gid))
						# this WILL be generated by inotify/gamin and we don't
						#self.expected[gamin.GAMCreated].append(path + '/')
						# need it. Prepare ourselves to skip it.
						self.expected[gamin.GAMChanged].append(path)

				self.aclchecker.enqueue(path, gid)

			except (OSError, IOError), e:
				if e.errno != 2:
					logging.warning('''%s: problem in GAMCreated on %s'''
					''' (was: %s, event=%s).''' % (self.name,
					path, e, event))

		elif event == gamin.GAMChanged:

			if path in self.expected[gamin.GAMChanged]:
				# skip the first GAMChanged event, it was generated
				# by the CHK in the GAMCreated part.
				self.expected[gamin.GAMChanged].remove(path)

				assert ltrace('inotifier', '''QUICKSKIP GAMChanged on %s.''' % (
					styles.stylize(styles.ST_PATH, path)))
				return

			else:

				assert ltrace('inotifier', "%s Inotify on %s." %  (
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

			assert ltrace('inotifier', "%s Inotify on %s." %  (
				styles.stylize(styles.ST_BAD, 'GAMDeleted'),
				styles.stylize(styles.ST_PATH, path)))

			# we can't test if the “path” was a dir, it has just been deleted
			# just try to delete it, wait and see. If it was, this will work.
			with self.lock:
				self._to_remove.append(path)
				self.expected[gamin.GAMDeleted].append(path + '/')

			# TODO: remove recursively if DIR.
			#self.cache.removeEntry(path)

		elif event == gamin.GAMEndExist:
			assert ltrace('inotifier', '%s Inotify on %s.' % (
				styles.stylize(styles.ST_COMMENT, 'GAMEndExist'),
				styles.stylize(styles.ST_PATH, path)))
			if path in self.expected[gamin.GAMEndExist]:
				assert ltrace('inotifier', '''QUICKSKIP GAMEndExist on %s.''' % (
					styles.stylize(styles.ST_PATH, path)))
				self.expected[gamin.GAMEndExist].remove(path)
			else:
				logging.warning('UNEXPECTED Inotify event %s on %s.' % (
				styles.stylize(styles.ST_COMMENT, 'GAMEndExist'),
				styles.stylize(styles.ST_PATH, path)))

		elif event == gamin.GAMAcknowledge:
			if path in self.expected[gamin.GAMAcknowledge]:
				# skip the GAMAcknoledge event, it is generated
				# by the rmdir part.
				self.expected[gamin.GAMAcknowledge].remove(path)
				assert ltrace('inotifier', '''QUICKSKIP GAMAcknoledge on %s.''' % (
					styles.stylize(styles.ST_PATH, path)))
			else:
				logging.warning('UNEXPECTED Inotify event %s on %s.' % (
				styles.stylize(styles.ST_COMMENT, 'GAMAcknowledge'),
				styles.stylize(styles.ST_PATH, path)))
		else:
			logging.progress('UNHANDLED Inotify event %s on %s.' % (
				styles.stylize(styles.ST_COMMENT, event),
				styles.stylize(styles.ST_PATH, path)))
	def add_watch(self, path, func, is_dir=True):
		""" manually add a monitor on a given path.

			path: must be a valid directory or file.
			func: method called when a GAMIN event is received on path.
		"""

		assert ltrace('inotifier', '| add_watch(path=%s, func=%s, is_dir=%s)' % (
			path, func, is_dir))

		with self.lock:
			if is_dir:
				self.mon.watch_directory(path, func)
				self.expected[gamin.GAMEndExist].append(path)
				attribute = 'directory'
			else:
				self.mon.watch_file(path, func)
				attribute = 'file'

			logging.info('''%s: %s inotify watch for %s %s [total: %d] '''
				'''[to_add: %d] [to_rem: %d].''' % (
				self.name,
				styles.stylize(styles.ST_OK, 'added'),
				attribute,
				styles.stylize(styles.ST_PATH, path),
				len(self.mon.objects),
				len(self._to_add),
				len(self._to_remove)
				))
	def remove_watch(self, path):
		"""Remove a dir and all its subdirs from our GAM WatchMonitor. """

		assert ltrace('inotifier', '> remove_watch(%s)' % path)

		with self.lock:
			try:
				for watch in self.mon.objects.keys():
					# remove every watch under a given path, but avoid removing
					# similar paths (don't remove 'dir*/' if removing 'dir/').
					#logging.notice('trying to remove %s (from %s) -> %s' % (
					#	watch, path, watch.replace(path, '')))
					splitted = watch.split(path)

					if watch == path or (
						len(splitted) > 1 and splitted[1][0] == '/'):
						self.remove_one_watch(watch)

			except gamin.GaminException, e:
				logging.warning('''%s.remove_watch(): exception %s.''' % e)

		assert ltrace('inotifier', '< remove_watch(%s)' % path)
	def remove_one_watch(self, path):
		""" Remove a single watch from the GAM WatchMonitor."""

		assert ltrace('inotifier', '> remove_one_watch(%s)' % path)

		with self.lock:
			try:
				self.expected[gamin.GAMAcknowledge].append(path)
				self.mon.stop_watch(path)
				#self.wds.remove(path)

				if self.mon.objects[path] == []:
					del self.mon.objects[path]

				logging.info('''%s: %s inotify watch for %s [total: %d] '''
					'''[to_add: %d] [to_rem: %d].''' % (
					self.name,
					styles.stylize(styles.ST_BAD, 'removed'),
					styles.stylize(styles.ST_PATH, path),
					len(self.mon.objects),
					len(self._to_add),
					len(self._to_remove)
					))

				#assert ltrace('inotifier', str(self.mon.objects).replace(', ', '\n'))
			except KeyError, e:

				logging.warning(e)
		assert ltrace('inotifier', '< remove_one_watch(%s)' % path)
	def show_statuses(self):
		""" Compute and show internal queues statuses. """

		with self.lock:
			lengths = (
				#len(self.wds),
				len(self.mon.objects),
				len(self._to_add),
				len(self._to_remove),
				len(self.expected[gamin.GAMAcknowledge]),
				len(self.expected[gamin.GAMExists]),
				len(self.expected[gamin.GAMEndExist]),
				len(self.expected[gamin.GAMCreated]),
				len(self.expected[gamin.GAMChanged])
			)

		logging.progress('''%s: queues stati: [total: %d] '''
			'''[add: %d] [rem: %d] [ack: %d] '''
			'''[exist: %d] [endex: %d] [creat: %d] [chg: %d].''' % (
				self.name,
				lengths[0], lengths[1], lengths[2], lengths[3],
				lengths[4], lengths[5], lengths[6], lengths[7]
			)
		)

		#if(lengths[7] > 0):
		#	logging.info('chg: %s' % \
		#	str(self.gam_changed_expected).replace(', ', ',\n\t'))
	def run(self):
		logging.progress("%s: thread running." % (self.name))
		Thread.run(self)

		try:
			already_waited = False
			time_count     = 0
			while not self._stop_event.isSet():

				if time_count >= 100000:
					self.show_statuses()
					time_count = 0

				with self.lock:
					while len(self._to_remove) and not self._stop_event.isSet():
						# remove as many watches as possible in the same time,
						# to help relieve the daemon.
						self.remove_watch(self._to_remove.popleft())

						# don't forget to handle_events(), to flush the GAM queue
						self.mon.handle_events()

				with self.lock:
					add_count = 0
					while add_count < 10 and len(self._to_add) \
						and not self._stop_event.isSet():
						path, gid = self._to_add.popleft()

						def myfunc(path, event, gid = gid, dirname = path):
							return self.process_event(path, event, gid, dirname)

						self.add_watch(path, myfunc)

						# don't forget to handle_events(), to flush the GAM queue
						self.mon.handle_events()
						add_count += 1

				if self._stop_event.isSet():
					break

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

		except Exception, e:
			if self._stop_event.isSet():
				logging.warning('%s: ignored exception while stopping: %s' % e)
			else:
				raise e

		del self.mon

		for timer in self.conffiles_threads.itervalues():
			if timer.isAlive():
				timer.cancel()
			timer.join()

		logging.progress("%s: thread ended." % (self.name))
	def stop(self):
		if Thread.isAlive(self) and not self._stop_event.isSet():
			logging.progress("%s: stopping thread." % (self.name))
			self._stop_event.set()
