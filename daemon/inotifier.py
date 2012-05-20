# -*- coding: utf-8 -*-
"""
Licorn Daemon inotifier thread.

:copyright: 2007-2009 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

import os, time, pyinotify, select, errno

from licorn.foundations           import logging, exceptions
from licorn.foundations           import fsapi, pyutils
from licorn.foundations.base      import BasicCounter
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.constants import filters, priorities
from licorn.core                  import LMC
from licorn.daemon.threads        import LicornBasicThread

class INotifier(LicornBasicThread, pyinotify.Notifier):
	"""
	This inotifier is basically a rewrite of the pyinotify.ThreadedNotify class,
	adapted to be licornish (most notably get licornd as argument, and format
	the thread name conforming to Licorn other thread names.
	"""
	def __init__(self, licornd, no_boot_check=False):

		LicornBasicThread.__init__(self, 'INotifier', licornd)
		pyinotify.Notifier.__init__(self, pyinotify.WatchManager())

		# Create a new pipe used for thread termination
		self._pipe = os.pipe()
		self._pollobj.register(self._pipe[0], select.POLLIN)

		#self.default_mask = pyinotify.IN_CLOSE_WRITE \
		#					| pyinotify.IN_CREATE \
		#					| pyinotify.IN_MOVED_TO \
		#					| pyinotify.IN_MOVED_FROM \
		#					| pyinotify.IN_DELETE

		self._wm = self._watch_manager

		# core objects watched configuration files, and the associated data.
		self._watched_conf_files = {}

		# internal storage for watched configuration dirs: a helper for
		# core_objects watched configuration files (we cannot watch files
		# directly, we need to handle them via their dir, for the thing to
		# be reliable).
		self.__watched_conf_dirs = {}

		# comfort aliases to internal methods, to mirror the methods exported
		# from the daemon object.
		self.inotifier_add            = self._wm.add_watch
		self.inotifier_del            = self._wm.rm_watch
		self.inotifier_watch_conf     = self.watch_conf
		self.inotifier_del_conf_watch = self.del_conf_watch
	def dump_status(self, long_output=False, precision=None, as_string=True):

		if as_string:
			#~ if long_output:
				#~ return u'%s%s (%d watched dirs)\n\t%s\n' % (
					#~ stylize(ST_RUNNING
						#~ if self.is_alive() else ST_STOPPED, self.name),
					#~ u'&' if self.daemon else '',
					#~ len(self._wm.watches.keys()),
					#~ u'\n\t'.join(sorted(w.path
						#~ for w in self._wm.watches.itervalues()))
				#~ )
			#~ else:
			return (_(u'{0}{1} ({2} watched dirs, {3} config files, '
					u'{4} queued events)').format(stylize(ST_RUNNING
						if self.is_alive() else ST_STOPPED, self.name),
					u'&' if self.daemon else u'',
					stylize(ST_RUNNING,   str(len(self._watch_manager.watches))),
					stylize(ST_RUNNING,   str(len(self._watched_conf_files))),
					stylize(ST_IMPORTANT, str(len(self._eventq)))
					))
		else:
			return dict(
					name=self.name,
					daemon=self.daemon,
					alive=self.is_alive(),
					ident=self.ident,
					watches=len(self._watch_manager.watches),
					conf_files=self._watched_conf_files.keys(),
					qsize=len(self._eventq)
				)

	def stop(self):
		""" Stop notifier's loop. Stop notification. Join the thread. """

		# remove some references to existing objects, to allow them to be GC'ed.
		self.__watched_conf_dirs.clear()
		self._watched_conf_files.clear()

		w = len(self._wm.watches)

		if w > 5000:
			logging.notice(_(u'{0}: closing {1} watches, please wait…').format(
				stylize(ST_NAME, self.name), stylize(ST_ATTR, w)))

		try:
			self._wm.rm_watch(self._wm.watches.keys(), quiet=False)

		except Exception, e:
			logging.warning(e)

		LicornBasicThread.stop(self)

		try:
			os.write(self._pipe[1], 'stop')

		except (OSError, IOError), e:
			logging.warning(e)
	def run(self):

		while not self._stop_event.isSet():

			self.process_events()
			ref_time = time.time()

			if self.check_events():
				self._sleep(ref_time)
				try:
					self.read_events()

				except pyinotify.NotifierError, e:
					logging.warning(_(u'{0}: error on read_events: {1}').format(
						stylize(ST_NAME, self.name), e))

		try:
			pyinotify.Notifier.stop(self)

		except (OSError, IOError), e:
			if e.errno != errno.EBADF:
				raise e

		try:
			self._pollobj.unregister(self._pipe[0])
			os.close(self._pipe[0])
			os.close(self._pipe[1])

		except (OSError, IOError), e:
			logging.warning(e)

		del self._wm
	def del_conf_watch(self, conf_file):
		try:
			del self._watched_conf_files[conf_file]

		except Exception, e:
			logging.warning2(_(u'inotifier: error deleting {0} '
				u'(was: {1} {2})').format(conf_file, type(e), e))
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
				between us and the core object. See
				http://mail.python.org/pipermail/python-dev/2003-May/035505.html
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

		try:
			name, lock, hint, reload_method = self._watched_conf_files[event.pathname]

			logging.monitor(TRACE_INOTIFIER, 'New config file event on {0}', event.pathname)

		except (AttributeError, KeyError):
			assert ltrace(TRACE_INOTIFIER, '| __config_file_event unhandled %s' % event)
			return

		assert ltrace(TRACE_LOCKS, '| inotifier conf_enter %s' % lock)

		with lock:
			assert ltrace(TRACE_INOTIFIER,
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

			# else:
			# IN_CLOSE_WRITE just triggers a check, so no particular action.
			# If MODIFY has lowered the level, this will trigger a reload().
			# else it will do nothing.

			if hint <= 0:
				logging.info(_(u'{0}: configuration file {1} changed, '
					u'trigerring upstream reload.').format(
						stylize(ST_NAME, name),
						stylize(ST_PATH, event.name)))

				# reset the hint to normal state before reloading(), to avoid
				# missing another eventual future event.
				hint.set(1)
				reload_method(event.pathname)

		assert ltrace(TRACE_LOCKS, '| inotifier conf_exit %s' % lock)
	def collect(self):
		""" Setup the kernel inotifier arguments, and collect inotifier-related
			methods and events on controllers and
			object which export them in our standardized way. """

		number_of_things = (
			len([user for user in LMC.users if user.is_standard])
			+ len([group for group in LMC.groups if group.is_standard])
			)

		# 1 million watches per user and per group should be a sufficient base
		# to start with.
		max_user_watches  = 1048576 * number_of_things
		max_queued_events = 16384 * number_of_things

		for name, value in (('max_user_watches', max_user_watches),
							('max_queued_events', max_queued_events)):

			curval = int(open('/proc/sys/fs/inotify/{0}'.format(name)).read().strip())
			if curval < value:
				try:
					open('/proc/sys/fs/inotify/{0}'.format(name), 'w').write(str(value))
					logging.info(_(u'{0}: increased inotify {1} to {2}.').format(
						stylize(ST_NAME, self.name), stylize(ST_ATTR, name),
						stylize(ST_ATTR, value)))

				except (IOError, OSError), e:
					if e.errno not in (errno.EPERM, errno.EACCES):
						raise

					# in LXC, we don't always have permissions to tweak `/proc`.
					# This should not stop us, anyway.
					logging.exception(_(u'{0}: unable to increase inotify {1} to {2}').format(
						stylize(ST_NAME, self.name), stylize(ST_ATTR, name),
						stylize(ST_ATTR, value)))

		# setup controllers notifies.
		for controller in LMC:
			if hasattr(controller, '_inotifier_install_watches'):
				try:
					controller._inotifier_install_watches(self)

				except Exception, e:
					logging.warning(_(u'{0:s}: exception install watches of '
							u'{1:s}.').format(self, controller))
					pyutils.print_exception_if_verbose()
