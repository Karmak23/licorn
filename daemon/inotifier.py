# -*- coding: utf-8 -*-
"""
Licorn Daemon inotifier thread.

:copyright: 2007-2009 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

import os, time, gamin, pyinotify, select

from threading   import Thread, Event, RLock, Timer
from collections import deque

from licorn.foundations           import logging, exceptions
from licorn.foundations           import fsapi, pyutils
from licorn.foundations.base      import BasicCounter
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import filters, gamin_events
from licorn.core                  import LMC
from licorn.daemon                import priorities
from licorn.daemon.threads        import LicornBasicThread

class INotifier(LicornBasicThread, pyinotify.Notifier):
	"""
	This inotifier is basically a rewrite of the pyinotify.ThreadedNotify class,
	adapted to be licornish (most notably get licornd as argument, and format
	the thread name conforming to Licorn other thread names.
	"""
	def __init__(self, licornd, read_freq=0, threshold=0, timeout=None):

		LicornBasicThread.__init__(self, 'INotifier', licornd)

		# considering the number of direct watches we're going to have,
		# a little increase is welcome.
		pyinotify.max_user_watches.value = 65535

		print '>> sysctl', pyinotify.max_user_instances.value, \
							pyinotify.max_user_watches.value, \
							pyinotify.max_queued_events.value

		self.default_mask = pyinotify.IN_CLOSE_WRITE \
							| pyinotify.IN_CREATE \
							| pyinotify.IN_MOVED_TO \
							| pyinotify.IN_MOVED_FROM \
							| pyinotify.IN_DELETE

		self._wm = pyinotify.WatchManager()

		# core objects watched configuration files, and the associated data.
		self._watched_conf_files = {}

		# internal storage for watched configuration dirs: a helper for
		# core_objects watched configuration files (we cannot watch files
		# directly, we need to handle them via their dir, for the thing to
		# be reliable).
		self.__watched_conf_dirs = {}

		self.inotifier_add = self._wm.add_watch
		self.inotifier_del = self._wm.rm_watch

		pyinotify.Notifier.__init__(self, self._wm,
							# FIXME: we set a default func to print and discover
							# all events while developing, but this should go
							# away when phase 1 dev is finished.
							default_proc_fun=pyinotify.PrintAllEvents(),
							read_freq=0, threshold=0, timeout=None)

		# Create a new pipe used for thread termination
		self._pipe = os.pipe()
		self._pollobj.register(self._pipe[0], select.POLLIN)
	def stop(self):
		""" Stop notifier's loop. Stop notification. Join the thread. """

		for watch in self.__watched_conf_dirs:
			self._wm.rm_watch(watch)

		LicornBasicThread.stop(self)

		os.write(self._pipe[1], 'stop')

		LicornBasicThread.join(self)

		pyinotify.Notifier.stop(self)

		self._pollobj.unregister(self._pipe[0])
		os.close(self._pipe[0])
		os.close(self._pipe[1])
	def run(self):

		# then listen for events.
		while not self._stop_event.isSet():

			self.process_events()
			ref_time = time.time()

			if self.check_events():
				self._sleep(ref_time)
				self.read_events()
	def watch_conf(self, conf_file, core_obj, reload_method=None, reload_hint=None):
		""" Helper / Wrapper method for core objects. This will setup a watcher
			on dirname(conf_file), if not already setup. returns a reload hint
			to be stored and used by the calling core object, to use in
			conjunction with us, to avoid false positives.

			:param core_obj: the core objects who wants us to watch the
				configuration file. used to get its name and its lock during
				the event-handle phases.

			.. note:: the reload_hint is a tricky thing, because integers are
				immutable, and thus cannot be shared. It seems the reference is
				not passed, but only the value, which makes it desynchronized
				between us and the core object. See http://mail.python.org/pipermail/python-dev/2003-May/035505.html
				for more details, but we end up with something a bit more
				complex, because we had no choice.
		"""

		dirname = os.path.dirname(conf_file)

		# prepare the internal data needed to receive events on this particular
		# configuration file. We index on the full path to avoid the eventual
		# rare case where 2 config files with the same name could exist at more
		# than one place on the system. This permits this mechanism to have a
		# wider audience than just only config files.


		hint = (BasicCounter(1)
					if reload_hint is None
					else reload_hint)

		self._watched_conf_files[conf_file] = (core_obj.name,
												core_obj.lock,
												hint,
												core_obj.reload
													if reload_method is None
													else reload_method)

		#print '>> obj', core_obj.name, 'hint', id(hint), type(hint), self._watched_conf_files[conf_file]

		# then verify if the containing directory is already watched, or not. If
		# it is, there's nothing else to do.
		if dirname in self.__watched_conf_dirs:
			return hint

		self.__watched_conf_dirs[dirname] = self._wm.add_watch(
								dirname,
								pyinotify.ALL_EVENTS
									- pyinotify.IN_OPEN
									- pyinotify.IN_ACCESS

									# FIXME: shouldn't we watch this, and reput
									# good perms on the file on change ?
									- pyinotify.IN_ATTRIB

									# don't miss config files that do not exist
									# at the moment of watch setup.
									# - pyinotify.IN_CREATE

									# don't miss configuration files that are
									# moved out of the way, and don't exist
									# anymore -> implies empty conf again.
									# - pyinotify.IN_MOVED_FROM

									- pyinotify.IN_CLOSE_NOWRITE,
								self.__config_file_event)
		return hint
	def __config_file_event(self, event):
		""" Handle inotify events on watched configuration files. Buffer the
			events until a threshold on reload_hint is reached, then trigger
			a reload. This avoids trigerring for a modification made inside
			of Licorn® (core object	maintain the reload_hint on their own),
			and avoid trigerring a reload when no real change occur but we
			still get false-positive events (IN_CLOSE_WRITE without IN_MODIFY,
			not to name them). """

		# the internal reload_hint flag is protected against collision
		# writes by core_obj.lock, because the read and the write will occur
		# in different threads. The lock will be released by
		# core_obj.serialize() even before it can be acquired here.

		#print '>> event', event

		try:
			name, lock, hint, reload_method = self._watched_conf_files[event.pathname]
			#print '>> get back', name, lock, hint, reload_method

		except (AttributeError, KeyError):
			assert ltrace('inotifier', '| __config_file_event unhandled %s' % event)
			#print '>> nothing found for', event.pathname
			return

		with lock:

			assert ltrace('inotifier',
					'| %s handle_config_change %s' % (name, event))

			if event.mask in (pyinotify.IN_MODIFY, pyinotify.IN_CREATE):
				# IN_MODIFY and IN_CREATE just lower the threshold, and we
				# return immediately, because the check should wait until the
				# upcoming CLOSE_WRITE event.
				#
				# There can be many MODIFY events before a CLOSE_WRITE, and
				# a bunch of time can pass before the CLOSE_WRITE in both
				# CREATE and MODIFY cases.
				#
				# Only the CLOSE_WRITE will trigger the check, and if
				# no MODIFY nor CREATE lowered the hint, the reload will not
				# occur; we just avoided a useless reload() cycle.

				hint -= 1
				#print '>> modify', hint
				return

			elif event.mask & pyinotify.IN_MOVED_TO:
				# IN_MOVED_TO lowers the level and triggers a check. If we
				# modified the file internally, the hint would have been
				# raised by one, making it just reach the normal state now.
				# If the file was moved by an outside process, the -1 will
				# make the hint reach the level that will trigger a reload().
				#
				# In some cases, the MOVED_TO process will concern a file with
				# exactly the same contents as the original file, and the
				# reload() is useless. Unfortunately, we can't know that in
				# advance, so we'd better reload() a little more, than having
				# the file on-disk desynchronized with internal data.
				hint -= 1
				#print '>> moved_to', hint

			# else:
			# IN_CLOSE_WRITE just triggers a check, so no particular action.
			# If MODIFY has lowered the level, this will trigger a reload().
			# else it will do nothing.
			#print '>> close_write', hint

			if hint <= 0:
				logging.info(_(u'{0}: configuration file {1} changed, '
					'reloading.').format(stylize(ST_NAME, name),
						stylize(ST_PATH, event.name)))

				# reset the hint to normal state before reloading(), to avoid
				# missing another eventual future event.
				hint.set(1)
				reload_method(event.pathname)
	def collect(self):
		# setup controllers notifies.
		for controller in LMC:
			if hasattr(controller, '_inotifier_install_watches'):
				getattr(controller, '_inotifier_install_watches')(self)
