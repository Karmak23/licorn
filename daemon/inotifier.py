# -*- coding: utf-8 -*-
"""
Licorn Daemon inotifier thread.

:copyright: 2007-2009 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

import os, time, gamin

from threading   import Thread, Event, RLock, Timer
from collections import deque

from licorn.foundations           import logging, exceptions
from licorn.foundations           import fsapi, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import filters, gamin_events
from licorn.core                  import LMC
from licorn.daemon                import priorities, aclcheck

class INotifier(Thread):
	""" A Thread which collect INotify events and does what is appropriate with
	 them. """

	def __init__(self, daemon, disable_boot_check=False):

		Thread.__init__(self)

		self.name = "%s/%s" % (daemon.dname, 'inotifier')

		self.daemon      = daemon

		self.lock        = RLock()
		self._stop_event = Event()
		self._to_add     = deque()
		self._to_remove  = deque()

		self.call_counter = 0
		self.last_call_time = None

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

		LMC.groups.set_inotifier(self)

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

		for gid in LMC.groups.Select(filters.STD):
			self.add_group_watch(gid)

		assert ltrace('thread', '%s initialized' % self.name)
	def dump_status(self, long_output=False, precision=None):
		""" dump current thread status. """

		assert ltrace('inotifier', '| %s.dump_status(long_output=%s, precision=%s)'
			% (self.name, long_output, precision))

		def small_status():
			return '%s(%s%s) %s (%s call%s%s) %s' % (
				stylize(ST_NAME, self.name),
				self.ident, stylize(ST_OK, '&') if self.daemon else '',
				stylize(ST_OK, 'alive') \
					if self.is_alive() else 'has terminated',
				stylize(ST_COMMENT, self.call_counter),
				's' if self.call_counter > 1 else '',
				', last: %s' % pyutils.format_time_delta(
					self.last_call_time - time.time(),
					use_neg=True, long_output=False)
						if self.last_call_time else '',
				self.queues_status_str()
				)

		if precision:
			data = '%s\ndetails for %s:' % (small_status(), ','.join([ ','.join(prelist)
				for prelist in precision ]))

			kept_keys = []

			for key in self.mon.objects.keys():
				if key.startswith(LMC.configuration.defaults.home_base_path):
					try:
						type, name, rest = (key.lstrip(
							'%s/' % LMC.configuration.defaults.home_base_path)).split('/', 2)
					except ValueError:
						type, name = (key.lstrip(
							'%s/' % LMC.configuration.defaults.home_base_path)).split('/', 1)

					#print '%s %s %s' % (key, type, name)

					if name in getattr(precision, type):
						#data += '\n\t%s -> %s' % (key, ','.join(
						#	[ str(dir(x)) for x in self.mon.objects[key] ]))
						kept_keys.append(key)
				# else:
				#	continue
				# we got a WatchObject() for anything outside /home

			kept_keys.sort()
			for key in kept_keys:
				data += '\n\twatch on %s' % stylize(ST_PATH, key)
				#
			return data

		elif long_output:
			return '''%s
	self.mon           = %s
	self.expected      =
		%s
	self._stop_event   = %s (%s)''' % (
			small_status(),
			str([ (x,y) for x,y in self.mon.objects.iteritems()]).replace(
				'), ', '),\n\t\t').replace('[(', '[\n\t\t(').replace(
					')]',')\n\t]'),
			'\n\t\t'.join([ '%s (%s items): %s' % (
				gamin_events[num],
				stylize(ST_COMMENT, len(self.expected[num])),
				self.expected[num]
				) for num in self.expected.keys() ]),
			self._stop_event, self._stop_event.isSet()
			)
		else:
			return small_status()
	def watch_configuration_files(self):
		""" monitor important configuration files, to know when another program
			touch them, and apply appropriate actions on change. """

		assert ltrace('inotifier', '| %s.watch_configuration_files()' %
			self.name)

		def reload_controller_unix(path, controller, *args, **kwargs):
			""" Timer() callback for watch threads.
			*args and **kwargs are not used. """
			logging.notice('%s: configuration file %s changed, '
				'reloading %s controller.' %
					(self.name, stylize(ST_PATH, path),
					stylize(ST_NAME, controller.name)))
			controller.reload_backend('shadow')

		def event_on_config_file(path, event, controller, index):
			""" We only watch GAMCreated events, because when
				{user,group}{add,mod,del} change their files, they create it
				from another, everytime (for atomic reasons). We, in licorn
				overwrite them, and this will generate a GAMChanged event,
				which permits us to distringuish between the different uses.
			"""
			assert ltrace('inotifier',
				'gam event %s on %s -> controller %s (index %s)' % (
				gamin_events[event], path, controller.name, index))

			if event == gamin.GAMCreated:
				create_thread = False
				try:
					if self.conffiles_threads[index].is_alive():
						self.conffiles_threads[index].cancel()

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
			return event_on_config_file(path, event, LMC.users, 1)
		def event_on_group(path, event):
			return event_on_config_file(path, event, LMC.groups, 2)

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
			LMC.configuration.defaults.home_base_path,
			LMC.configuration.groups.names.plural,
			LMC.groups.gid_to_name(gid)))
	def add_group_watch(self, gid):
		""" add a group watch. """

		group_home = "%s/%s/%s" % (
			LMC.configuration.defaults.home_base_path,
			LMC.configuration.groups.names.plural,
			LMC.groups.gid_to_name(gid))

		def myfunc(path, event, gid=gid, dirname=group_home):
			return self.process_event(path, event, gid, dirname)

		self.add_watch(group_home, myfunc)
	def aclcheck(self, path, gid, is_dir):
		if path is None: return

		self.call_counter += 1
		self.last_call_time = time.time()

		acl = LMC.groups.BuildGroupACL(gid, path)

		try:
			if is_dir:
				fsapi.auto_check_posix_ugid_and_perms(path, -1,
					LMC.groups.name_to_gid('acl') , -1)
				#self.gam_changed_expected.append(path)
				fsapi.auto_check_posix1e_acl(path, False,
					acl['default_acl'], acl['default_acl'])
				#self.gam_changed_expected.append(path)
				#self.prevent_double_check(path)
			else:
				fsapi.auto_check_posix_ugid_and_perms(path, -1,
					LMC.groups.name_to_gid('acl'))
				#self.prevent_double_check(path)
				fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')
				#self.prevent_double_check(path)

		except (OSError, IOError), e:
			if e.errno != 2:
				logging.warning(
					"%s: error on %s (was: %s)." % (self.name, path, e))

		# FIXME: to be re-added when cache is ok.
		#self.daemon.threads.cache.cache(path)

	def process_event(self, basename, event, gid, dirname):
		""" Process Gamin events and apply ACLs on the fly. """

		self.call_counter += 1
		self.last_call_time = time.time()

		# with Gamin, sometimes it is an abspath, sometimes not.
		# this happens on GAMChanged (observed the two), and
		# GAMDeleted (observed only abspath).
		if basename[0] == '/':
			path = basename
		else:
			path = '%s/%s' % (dirname, basename)

		assert ltrace('inotifier', '''NEW Inotify event %s on %s.''' % (
			gamin_events[event], stylize(ST_PATH, path)))

		if path[-1] == '/' :
			if event in (gamin.GAMCreated, gamin.GAMDeleted, gamin.GAMChanged):
				if path in self.expected[event]:
					# we received an event for the root dir of a new watch.
					# this is a duplicate of the parent/new_dir. Just discard it.
					assert ltrace('inotifier', '''SKIPDUP Inotify event %s '''
						'''on %s.''' % (
						stylize(ST_COMMENT, gamin_events[event]),
						stylize(ST_PATH, basename)))
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
					stylize(ST_COMMENT, gamin_events[event]),
					stylize(ST_PATH, basename)))

		if os.path.islink(path):
			# or fsapi.is_backup_file(path):
			assert ltrace('inotifier', '''DISCARD Inotify event on symlink %s.'''\
				% (stylize(ST_PATH, path)))
			return

		if event == gamin.GAMExists:
			try:
				if os.path.isdir(path):
					if path in self.mon.objects.keys():
						# skip already watched directories, and /home/groups/*

						assert ltrace('inotifier', '''SKIP Inotify event %s '''
							'''on already watched directory %s.''' % (
							stylize(ST_MODE, 'GAMExists'),
							stylize(ST_PATH, path)))
						return
					else:
						with self.lock:
							self._to_add.append((path, gid))
				else:
					# path is a file, check it.
					assert ltrace('inotifier', '''CHECK file %s.''' % (
						stylize(ST_PATH, path)))
					#self.daemon.threads.aclchecker.enqueue(path, gid)
					aclcheck(priorities.NORMAL, self.aclcheck,
								path=path, gid=gid, is_dir=False)

			except (OSError, IOError), e:
				if e.errno != 2:
					logging.warning('''%s: problem in GAMExists on %s'''
					''' (was: %s, event=%s).''' % (self.name,
					path, e, event))

		elif event == gamin.GAMCreated:

			assert ltrace('inotifier', "%s Inotify on %s." % (
				stylize(ST_MODE, 'GAMCreated'), path))

			try:
				if os.path.isdir(path):
					with self.lock:
						self._to_add.append((path, gid))
						# this WILL be generated by inotify/gamin and we don't
						#self.expected[gamin.GAMCreated].append(path + '/')
						# need it. Prepare ourselves to skip it.
						self.expected[gamin.GAMChanged].append(path)
					aclcheck(priorities.NORMAL, self.aclcheck,
								path=path, gid=gid, is_dir=True)
				else:
					aclcheck(priorities.NORMAL, self.aclcheck,
								path=path, gid=gid, is_dir=False)

				#self.daemon.threads.aclchecker.enqueue(path, gid)

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
					stylize(ST_PATH, path)))
				return

			else:

				assert ltrace('inotifier', "%s Inotify on %s." %  (
					stylize(ST_URL, 'GAMChanged'),
					stylize(ST_PATH, path)))

				#self.daemon.threads.aclchecker.enqueue(path, gid)
				aclcheck(priorities.NORMAL, self.aclcheck,
							path=path, gid=gid, is_dir=os.path.isdir(path))

		elif event == gamin.GAMMoved:

			logging.progress('%s: Inotify %s, not handled yet %s.' % (
				self.name,
				stylize(ST_PKGNAME, 'GAMMoved'),
				stylize(ST_PATH, path)))

		elif event == gamin.GAMDeleted:
			# if a dir is deleted, we will get 2 GAMDeleted events:
			#  - one for the dir watched (itself deleted)
			#  - one for its parent, signaling its child was deleted.

			assert ltrace('inotifier', "%s Inotify on %s." %  (
				stylize(ST_BAD, 'GAMDeleted'),
				stylize(ST_PATH, path)))

			# we can't test if the “path” was a dir, it has just been deleted
			# just try to delete it, wait and see. If it was, this will work.
			with self.lock:
				self._to_remove.append(path)
				if os.path.isdir(path):
					self.expected[gamin.GAMDeleted].append(path + '/')

			# TODO: remove recursively if DIR.
			#self.daemon.threads.cache.removeEntry(path)

		elif event == gamin.GAMEndExist:
			assert ltrace('inotifier', '%s Inotify on %s.' % (
				stylize(ST_COMMENT, 'GAMEndExist'),
				stylize(ST_PATH, path)))
			if path in self.expected[gamin.GAMEndExist]:
				assert ltrace('inotifier', '''QUICKSKIP GAMEndExist on %s.''' % (
					stylize(ST_PATH, path)))
				self.expected[gamin.GAMEndExist].remove(path)
			else:
				logging.warning('UNEXPECTED Inotify event %s on %s.' % (
				stylize(ST_COMMENT, 'GAMEndExist'),
				stylize(ST_PATH, path)))

		elif event == gamin.GAMAcknowledge:
			if path in self.expected[gamin.GAMAcknowledge]:
				# skip the GAMAcknoledge event, it is generated
				# by the rmdir part.
				self.expected[gamin.GAMAcknowledge].remove(path)
				assert ltrace('inotifier', '''QUICKSKIP GAMAcknoledge on %s.''' % (
					stylize(ST_PATH, path)))
			else:
				logging.warning('UNEXPECTED Inotify event %s on %s.' % (
				stylize(ST_COMMENT, 'GAMAcknowledge'),
				stylize(ST_PATH, path)))
		else:
			logging.progress('UNHANDLED Inotify event %s on %s.' % (
				stylize(ST_COMMENT, event),
				stylize(ST_PATH, path)))
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
				stylize(ST_OK, 'added'),
				attribute,
				stylize(ST_PATH, path),
				len(self.mon.objects),
				len(self._to_add),
				len(self._to_remove)
				), to_listener=False)
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

				if self.mon.objects[path] == []:
					del self.mon.objects[path]

				logging.info('''%s: %s inotify watch for %s [total: %d] '''
					'''[to_add: %d] [to_rem: %d].''' % (
					self.name,
					stylize(ST_BAD, 'removed'),
					stylize(ST_PATH, path),
					len(self.mon.objects),
					len(self._to_add),
					len(self._to_remove)
					), to_listener=False)

				#assert ltrace('inotifier', str(self.mon.objects).replace(', ', '\n'))
			except KeyError, e:

				logging.warning(e)
		assert ltrace('inotifier', '< remove_one_watch(%s)' % path)
	def queues_status_str(self):
		""" Compute and show internal queues statuses. """

		with self.lock:
			lengths = (
				len(self.mon.objects),
				len(self.mon.cancelled),
				len(self._to_add),
				len(self._to_remove),
				len(self.expected[gamin.GAMAcknowledge]),
				len(self.expected[gamin.GAMExists]),
				len(self.expected[gamin.GAMEndExist]),
				len(self.expected[gamin.GAMCreated]),
				len(self.expected[gamin.GAMChanged])
			)

		return ('''queues stati: [total: %d] [cancel: %d] '''
			'''[add: %d] [rem: %d] [ack: %d] '''
			'''[exist: %d] [endex: %d] [creat: %d] [chg: %d].''' % (
				lengths[0], lengths[1], lengths[2], lengths[3],
				lengths[4], lengths[5], lengths[6], lengths[7], lengths[8]
			))

		#if(lengths[7] > 0):
		#	logging.info('chg: %s' % \
		#	str(self.gam_changed_expected).replace(', ', ',\n\t'))
	def run(self):
		assert ltrace('thread', '%s running' % self.name)
		# don't call Thread.run(self), just override it.

		try:
			already_waited = False
			while not self._stop_event.isSet():
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
					else:
						already_waited = True
						self.mon.handle_events()
						time.sleep(0.001)

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

		assert ltrace('thread', '%s ended' % self.name)
	def stop(self):
		if self.is_alive and not self._stop_event.isSet():
			assert ltrace('thread', '%s stopping' % self.name)
			self._stop_event.set()
