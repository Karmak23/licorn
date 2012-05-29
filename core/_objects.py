# -*- coding: utf-8 -*-
"""
Licorn core objects

Basic objects used in all core controllers.

:copyright:
	* 2010 Olivier Cortès <oc@meta-it.fr>
	* partial 2010 Robin Lucbernet <robinlucbernet@gmail.com>

:license: GNU GPL version 2

"""

import Pyro.core, re, glob, os, posix1e, weakref, time, pyinotify, itertools

from threading import current_thread
from licorn.foundations.threads import RLock, Event

from licorn.foundations           import settings, exceptions, logging, options
from licorn.foundations           import hlstr, pyutils, fsapi
from licorn.foundations.events    import LicornEvent
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.classes   import PicklableObject
from licorn.foundations.constants import filters, verbose, priorities, roles

from licorn.core                  import LMC


def exclude_filter_func(path):
	""" Return True if a path is within one that is excluded system-wide.

		We need to test more than "path in inotifier_exclusions" because
		The pyinotify WatchManager continues to traverse sub-directories
		even if the containing directory is excluded.

		This is a simple helper for CoreFSUnitObject.

		NOTE: This helper must not go into daemon/inotifier, else user
		configuration files will be discarded when users home directories
		are "unwatched". We want to still watch ~/.licorn/ even if ~/ is
		unwatched.

	"""

	for excl_path in settings.inotifier_exclusions:
		if path.startswith(excl_path):
			assert ltrace(TRACE_INOTIFIER,'%s excluded because in %s' % (path, excl_path))
			return True
	return False

class CoreUnitObject(PicklableObject):
	""" Common attributes for unit objects and
		:class:`modules <~licorn.core.classes.CoreModule>` in Licorn® core.

		This class defines the following attributes:

		.. attribute:: oid

			this attribute is the Licorn® object internal unique number (it's
			unique among all instances of a given class). If not given in
			:meth:`__init__`, it will be determined from next free
			oid stored in the :attr:`CoreUnitObject.counter` class attribute.

		.. attribute:: controller

			a reference to the object's container (manager or controller). Must
			be passed as :meth:`__init__` argument, else the object won't be
			able to easily find it's parent when it needs it.

		.. versionadded:: 1.3

	"""
	_lpickle_ = {
			'by_name': [ 'controller' ],
			'to_drop': [
						'_CoreUnitObject__licornd',
						'_CoreUnitObject__controller'
					],
			 }

	def __init__(self, *args, **kwargs):

		self.__controller = kwargs.pop('controller')

		super(CoreUnitObject, self).__init__(*args, **kwargs)

		assert ltrace_func(TRACE_OBJECTS)

		# FIXME: find a way to store the reference to the controller, not only
		# its name. This will annoy Pyro which cannot pickle weakproxy objects,
		# but will be cleaner than lookup the object by its name...
		self.__licornd    = LMC.licornd
	@property
	def controller(self):
		return self.__controller
	@property
	def licornd(self):
		return self.__licornd
class CoreStoredObject(CoreUnitObject):
	""" Common attributes for stored objects (users, groups...). Add individual
		locking capability (better fine grained than global controller lock when
		possible), and the backend name of the current object storage.

		.. versionadded:: 1.2
	"""

	_lpickle_ = {
			'by_name' : [ 'backend' ],
			'to_drop':  [
						'_CoreStoredObject__ro_lock',
						'_CoreStoredObject__rw_lock',
						'_CoreStoredObject__lock'
					],
		}

	def __init__(self, *args, **kwargs):

		self.__backend = kwargs.pop('backend')

		super(CoreStoredObject, self).__init__(*args, **kwargs)

		assert ltrace_func(TRACE_OBJECTS)

		self.__myref   = weakref.ref(self)

		# various locks, with different levels, for different operations.
		self.__ro_lock = RLock()
		self.__rw_lock = RLock()
		self.__lock    = self.__rw_lock

	@property
	def weakref(self):
		return self.__myref
	@property
	def backend(self):
		return self.__backend
	@backend.setter
	def backend(self, backend):
		if hasattr(self, 'move_to_backend'):
			self.__backend = backend
		else:
			raise exceptions.LicornRuntimeError(_(u'Cannot set a backend '
				u'without a "move_to_backend" method on the current instance.'))
	@property
	def lock(self):
		return self.__lock
	def _is_locked(self, lock=None):
		if lock is None:
			lock = self.__lock
		if lock.acquire(blocking=False):
			lock.release()
			return False
		return True
	def is_ro_locked(self):
		return self._is_locked(self.__ro_lock)
	def is_rw_locked(self):
		return self._is_locked(self.__rw_lock)
class CoreFSUnitObject(object):
	""" This class only add methods to some instances. """

	_lpickle_ = {
		'to_drop': [
				'_CoreFSUnitObject__expiry_lock',
			]
		}

	def __init__(self, *args, **kwargs):

		# The Event will avoid checking or fast_checking multiple times
		# over and over.
		self._checking = Event()

		self.__check_expected   = set()
		self.__recently_deleted = set()

		# We display messages to be sure there is no problem,
		# but no more often that every 5 seconds (see later).
		self.__last_msg_time = time.time()

		# expiry system for internal fast checks, to avoid doing them over and
		# over, when massive changes occur in the shared dirs.
		self.__last_fast_check = {}
		self.__expire_time     = 10.0
		self.__expiry_lock     = RLock()

		# __load_rules() parameters.
		self.__check_file      = kwargs.pop('check_file')
		self.__object_info     = kwargs.pop('object_info')
		self.__vars_to_replace = kwargs.pop('vars_to_replace', None)

		# don't set it, this will be handled by _fast*() or check().
		#self.__check_rules    = None

		# these will be filled by inotifier-related things.
		self.__watches           = {}
		self.__watches_installed = False

		# This one needs the 2 others to exists in case it's `True`.
		self.__is_inotified      = self.__resolve_inotified_state(kwargs.pop('inotified', None))

	@property
	def check_rules(self):
		try:
			return self.__check_rules

		except AttributeError:
			return self.__load_check_rules()
	@property
	def watches(self):
		return self.__watches

	@property
	def inotified(self):
		return self.__is_inotified
	@inotified.setter
	def inotified(self, inotified):
		""" Change the inotify state of the object, and start/stop inotifier
			watches accordingly. """

		object_type_str = self.controller.object_type_str

		if inotified == self.__is_inotified:
			logging.notice(_(u'Inotify state {0} for {1} {2}.').format(
								stylize(ST_COMMENT, _(u'unchanged')),
								object_type_str,
								stylize(ST_NAME, self.name)))
			return

		with self.lock:

			self.__is_inotified = inotified

			if inotified:
				qualif     = ''
				act_value  = _(u'activated')
				set_value  = _(u'setup')
				color      = ST_OK

				settings.del_inotifier_exclusion(self.homeDirectory)

				# setup the inotify watches
				self._inotifier_add_all_watches()

			else:
				qualif     = _(u'not ')
				act_value  = _(u'deactivated')
				set_value  = _(u'torn down')
				color      = ST_BAD

				# or tear them down
				self._inotifier_del_watch()

				settings.add_inotifier_exclusion(self.homeDirectory)

			# the watched state is displayed in CLI.
			self._cli_invalidate()

			# we need a kwargs named 'group' or 'user', thus the **{...}.
			LicornEvent('%s_inotify_state_changed' % object_type_str,
						**{ object_type_str: self }).emit(priorities.LOW)

			logging.notice(_(u'Switched {0} {1} inotify state to {2} '
							u'(watchers for shared content are '
							u'beiing {3} in the background, this can '
							u'take a while…)').format(
								object_type_str,
								stylize(ST_NAME, self.name),
								stylize(color, act_value),
								set_value))
	def __resolve_inotified_state(self, inotified=None):
		""" Check if a given user/group is 'inotified' (its homeDirectory is
			watched) or not. This method is used in 2 different context:

			- at creation via `controller.add_*()`
			- at load via `backend.load_*()`.

			At creation, `inotified` will be ``True`` or ``False``, to indicate
			what default value it should be, because the current value can't
			be determined from `settings` nor the FS (the home directory is not
			yet created and settings aren't set for this user/group).

			At load, the `inotified` param should be ``None`` (backends don't
			need to care about it) and the user/group will determine the correct
			value from `settings.inotifier_exclusions`.

			:param inotified: a boolean, which can be ``None`` (and it's the
				default value if not passed when calling this method).
		"""

		# we can't use self.__is_system because it's not an attribute of
		# the current class.
		if self.is_system:
			# system users/groups don't handle the inotified attribute.
			return None

		if inotified is None:
			return self.homeDirectory not in settings.inotifier_exclusions

		else:
			return inotified

	# This method must not fail on any exception, else the INotifier will
	# crash and become unusable. Thus just warn if any exception occurs.
	# This is better than nothing and will be more precise in the future.
	@pyutils.catch_exception
	def __inotify_event_dispatcher(self, event):
		""" The inotifier callback. Just a shortcut. """

		mask = event.mask

		if mask & pyinotify.IN_IGNORED:
			# don't display this one, it floods the output too much and breaks
			# the network connection.
			logging.monitor(TRACE_INOTIFIER, TRACELEVEL_4,
				'{0}: ignored {1}', (ST_NAME, self.name), event)
			return

		# treat deletes and outboud moves first.
		if event.dir and (mask & pyinotify.IN_DELETE_SELF
							or mask & pyinotify.IN_MOVED_FROM):
			# if it is a DELETE_SELF, only the dir watch will be removed;
			# if it is a MOVED, all sub-watches must be removed.

			logging.monitor(TRACE_INOTIFIER, TRACELEVEL_2,
							'{0}: unwatch deleted/moved directory {1}',
								(ST_NAME, self.name),
								(ST_PATH, event.pathname))
			self.__unwatch_directory(event.pathname,
							deleted=(mask & pyinotify.IN_DELETE_SELF))
			return

		# if we can find an expected event for a given path, we should just
		# discard the check, because the event is self-generated by an
		# already-ran previous check.
		if mask & pyinotify.IN_ATTRIB:
			with self.lock:
				try:
					self.__check_expected.remove(event.pathname)
					logging.monitor(TRACE_INOTIFIER, TRACELEVEL_3,
						'{0}: skipped expected event {1}',
							(ST_NAME, self.name), event)

				except KeyError:
					pass
			return

		# don't handle anything if the CoreFSUnitObject is currently beiing
		# checked. This is suboptimal as we will probably miss newly created
		# files and dirs, but trying to do more clever things will result
		# in pretty convoluted code.
		#if self._checking.is_set():
		#	if time.time() - self.__last_msg_time >= 1.0:
		#		logging.monitor(TRACE_INOTIFIER, '{0}: skipped event {1} '
		#								'(CHK in progress)', self.name, event)
		#		logging.progress(_(u'{0}: manual check already in '
		#						u'progress, skipping event {1}.').format(
		#							stylize(ST_NAME, self.name), event))
		#		self.__last_msg_time = time.time()
		#
		#	return


		if event.dir:
			if mask & pyinotify.IN_CREATE or mask & pyinotify.IN_MOVED_TO:
				# we need to walk the directory, to be sure we didn't miss any
				# inside path. When massive directory creation occur (e.g. when a
				# user tar -xzf a kernel or such kind of big archive), the
				# inotifier will miss entries created while a given sub-directory
				# is not yet watched. We need to "rewalk" the directory to be sure
				# we got everything. This is a kind of double-job, but it's
				# required...
				#workers.aclcheck_enqueue(priorities.HIGH,
				#					self.__rewalk_directory, event.pathname)

				# no need to lock for this, INotifier events / calls are
				# perfectly sequential.

				if event.pathname not in self.__watches:
					logging.monitor(TRACE_INOTIFIER, TRACELEVEL_2,
									'{0}: watch new dir {1}',
										(ST_NAME, self.name),
										(ST_PATH, event.pathname))
					self.__watch_directory(event.pathname)

				logging.monitor(TRACE_INOTIFIER, TRACELEVEL_1,
								'{0}: rewalk dir {1}',
									(ST_NAME, self.name),
									(ST_PATH, event.pathname))
				self.__rewalk_directory(event.pathname)

			elif mask & pyinotify.IN_ATTRIB:
				logging.monitor(TRACE_INOTIFIER, TRACELEVEL_1,
								'{0}: fast-chk dir {1} (expiry={2})',
									(ST_NAME, self.name),
									(ST_PATH, event.pathname),
									(ST_VALUE, expiry_check))

				self._fast_aclcheck(event.pathname)

			else:
				logging.monitor(TRACE_INOTIFIER, TRACELEVEL_4,
								'{0}: useless dir event {1}',
								(ST_NAME, self.name), event)

		else:
			if mask & pyinotify.IN_ATTRIB \
					or mask & pyinotify.IN_CREATE \
					or mask & pyinotify.IN_MOVED_TO:
				logging.monitor(TRACE_INOTIFIER, TRACELEVEL_1,
								'{0}: fast-chk file {1}',
									(ST_NAME, self.name),
									(ST_PATH, event.pathname))
				self._fast_aclcheck(event.pathname)

			else:
				logging.monitor(TRACE_INOTIFIER, TRACELEVEL_4,
								'{0}: useless file event {1}',
									(ST_NAME, self.name), event)
	def __rewalk_directory(self, directory, walk_delay=None):
		""" TODO. """

		if walk_delay:
			time.sleep(walk_delay)

		for path, dirs, files in os.walk(directory):
			# "path" is used at the end of the loop.

			for adir in dirs[:]:
				full_path_dir = '%s/%s' % (path, adir)

				# don't recurse.
				#dirs.remove(adir)

				if full_path_dir in self.__recently_deleted:
					# for some obscure (and perhaps kernel caching reasons),
					# some things are not catched/seen if I untar exactly the
					# same archive in the same shared dir. we need to wait a
					# little and rewalk the directory manually. This will occur
					# a small set of supplemental _fast_aclcheck(), but it's
					# really needed to catch everything.
					logging.monitor(TRACE_INOTIFIER,  TRACELEVEL_2,
						'{0}: rewalk deleted {1}',
							(ST_NAME, self.name),
							(ST_PATH, full_path_dir))
					self.__recently_deleted.discard(full_path_dir)

					# wait a little before rewalking, there is a delay when
					# we untar the same archive over-and-over.
					workers.aclcheck_enqueue(priorities.LOW,
						self.__rewalk_directory,
							full_path_dir, walk_delay=0.1)

				if full_path_dir in self.__watches:
					logging.monitor(TRACE_INOTIFIER,  TRACELEVEL_2,
						'{0}: already watched {1}',
							(ST_NAME, self.name),
							(ST_PATH, full_path_dir))
					continue

				logging.monitor(TRACE_INOTIFIER,  TRACELEVEL_1,
									u'{0}: watch/fast-chk missed '
									u'directory {1} [from {2}]',
										(ST_NAME, self.name),
										(ST_PATH, full_path_dir),
										(ST_PATH, directory))

				self.__watch_directory(full_path_dir)

				workers.aclcheck_enqueue(priorities.NORMAL,
						self._fast_aclcheck, full_path_dir, expiry_check=True)

			for afile in files:
				full_path_file = '%s/%s' % (path, afile)

				if full_path_file in self.__check_expected:
					logging.monitor(TRACE_INOTIFIER,  TRACELEVEL_3,
									'{0}: expected file {1}',
										(ST_NAME, self.name),
										(ST_PATH, full_path_file))
					continue

				logging.monitor(TRACE_INOTIFIER, TRACELEVEL_1,
							'{0}: fast-chk missed file {1} [from {2}]',
								(ST_NAME, self.name),
								(ST_PATH, full_path_file),
								(ST_PATH, directory))

				workers.aclcheck_enqueue(priorities.NORMAL,
						self._fast_aclcheck, full_path_file, expiry_check=True)

			# we had to wait a little before checking the main dir, thus we
			# do it at the end of the loop, this should imply a small but
			#  sufficient kind of delay. This should have given enough time
			# to the process which created the dir to handle its own work
			# before we try to set a new ACL on it.
			logging.monitor(TRACE_INOTIFIER,  TRACELEVEL_1,
							'{0}: fast-chk missed directory {1}',
							(ST_NAME, self.name), (ST_PATH, path))

			workers.aclcheck_enqueue(priorities.NORMAL,
								self._fast_aclcheck, path, expiry_check=True)

	# This method must not fail on any exception, else the INotifier will
	# crash and become unusable. Thus just warn if any exception occurs.
	# This is better than nothing and will be more precise in the future.
	@pyutils.catch_exception
	def __watch_directory(self, directory, initial=False):
		""" initial is set to False only when the group is instanciated, to
			walk across all shared group data in one call. """

		with self.lock:
			watches = L_inotifier_add(
									path=directory,
									rec=initial, auto_add=False,
									mask=#pyinotify.ALL_EVENTS,
											pyinotify.IN_CREATE
											| pyinotify.IN_ATTRIB
											| pyinotify.IN_MOVED_TO
											| pyinotify.IN_MOVED_FROM
											| pyinotify.IN_DELETE_SELF,
									proc_fun=self.__inotify_event_dispatcher,
									# just log any error, don't raise
									# exceptions while adding watches.
									quiet=True,
									# When recursively adding homes, use
									# system-wide exclusions to relax the
									# inotifier.
									exclude_filter=exclude_filter_func)
			if watches:
				for key, value in watches.iteritems():
					if value < 0:
						# reason -2 is "path excluded by exclude_filter()".
						# No need to bother us with a false-negative, this
						# is the desired behaviour.
						if value != -2:
							logging.warning(_(u'Watch add failed for {0}, reason {1}').format(key, value))
						continue

					if key in self.__watches:
						logging.warning2(_(u'{0}: overwriting watch {1}!').format(
							stylize(ST_NAME, self.name), stylize(ST_PATH, key)))

					logging.monitor(TRACE_INOTIFIER, TRACELEVEL_2,
									'{0}: add-watch {1} {2}',
										(ST_NAME, self.name),
										(ST_PATH, key),
										(ST_UGID, value))
					self.__watches[key] = value

	# This method must not fail on any exception, else the INotifier will
	# crash and become unusable. Thus just warn if any exception occurs.
	# This is better than nothing and will be more precise in the future.
	@pyutils.catch_exception
	def __unwatch_directory(self, directory, deleted=False):

		with self.lock:
			if directory == self.homeDirectory:

				# NOTE: using sorted( ... , reverse=True) doesn't help
				# suppressing the useless pyinotify warnings.
				for watch in self.__watches.values():
					try:
						# rm_watch / inotifier_del wants a list of WDs as argument.
						self.__recently_deleted.update(L_inotifier_del([watch], quiet=True).iterkeys())

					except:
						logging.exception(_(u'Cannot remove watch {0}, continuing'), watch)
						continue

				self.__watches.clear()

			else:
				if deleted:
					try:
						logging.monitor(TRACE_INOTIFIER, TRACELEVEL_2,
										'{0}: self-del unwatch {1}',
											(ST_NAME, self.name),
											(ST_PATH, directory))

						del self.__watches[directory]
						self.__recently_deleted.add(directory)

					except KeyError, e:
						logging.warning2(_(u'{0}.__unwatch_directory '
							u'in {1}: {2} not found in watched '
							u'dirs.').format(self.name,
								self.homeDirectory, e))

				else:
					try:
						logging.monitor(TRACE_INOTIFIER, TRACELEVEL_1,
										'{0}: remove recursive {1}',
											(ST_NAME, self.name),
											(ST_PATH, directory))

						self.__recently_deleted.update(L_inotifier_del(
								self.__watches[directory],
									rec=True).iterkeys())

					except KeyError, e:
						logging.warning2(_(u'{0}.__unwatch_directory '
							u'in {1}: {2} not found in watched '
							u'dirs.').format(self.name,
								self.homeDirectory, e))
					else:
						for watch in self.__watches.keys():
							if watch.startswith(directory):
								logging.monitor(TRACE_INOTIFIER,
												TRACELEVEL_1,
											'{0}: remove internal {1}',
												(ST_NAME, self.name),
												(ST_PATH, watch))
								del self.__watches[watch]
								self.__recently_deleted.add(watch)
	def __load_check_rules(self, event=None):
		""" Exist to catch anything coming from the
			inotifier and that we want to ignore anyway.

			The return at the end allows us to use the rules immediately,
			when we load them in the standard check() method. """

		assert ltrace(TRACE_CHECKS, '| %s.__load_check_rules(%s)' % (self.name, event))

		if event is None:
			try:
				return self.__check_rules

			except AttributeError:
				# don't crash: just don't return, the rules will be loaded
				# as if there were no problem at all.
				pass

		with self.lock:
			self.__check_rules = self.controller.load_rules(
									core_obj=self,
									rules_path=self.__check_file,
									object_info=self.__object_info,
									vars_to_replace=self.__vars_to_replace)

			return self.__check_rules
	def reload_check_rules(self, vars_to_replace):
		""" called from a group, when permissiveness is changed. """
		with self.lock:
			self.__vars_to_replace = vars_to_replace

			self.__check_rules = self.controller.load_rules(
									core_obj=self,
									rules_path=self.__check_file,
									object_info=self.__object_info,
									vars_to_replace=self.__vars_to_replace)
	def _inotifier_del_watch(self, inotifier=None, full=False):
		""" delete a user/group watch. Called by Controller before deleting.
			CoreStoredObject. """

		# be sure to del all these, else we still got cross references to self
		# in the inotifier which holds references to our methods, preventing
		# the clean CoreObject deletion.

		if os.path.exists(os.path.dirname(self.__check_file)):
			L_inotifier_del_conf_watch(self.__check_file)

		self.__unwatch_directory(self.homeDirectory)

		try:
			del self.__check_rules

		except AttributeError, e:
			# this happens when a CoreObject is deleted but has not been
			# checked since daemon start. Rare, but happens.
			logging.warning2('del %s: %s' % (self.name, e))

		# we have no watches left. Reclaim some memory ;-)
		self.__recently_deleted.clear()

		self.__watches_installed = False
	def _inotifier_add_watch(self, inotifier=None, force_reload=False):
		""" add a group watch. not used directly by inotifier, but prefixed
			with it because used in the context. """

		# The configuration file watch is installed inconditionally (watched
		# home or not).
		#
		# NOTE1: the inotifier hint is not needed for the configuration
		# file, because we don't modify it from inside licornd. Only the
		# user/admin modifies it; no hint implies that any inotify event will
		# trigger the reload, which is what we want.
		#self.check_file_hint =
		#
		# NOTE2: don't check if the configuration file exists or not, just
		# watch it. This allows automatic detection of manually created files
		# by the administrator, which is a quite cool feature.
		#if os.path.exists(os.path.dirname(self.__check_file)):
		L_inotifier_watch_conf(self.__check_file, self, self.__load_check_rules)

		if self.inotified:
			self._inotifier_add_all_watches(force_reload)
	def _inotifier_add_all_watches(self, force_reload=False):
		assert ltrace_func(TRACE_INOTIFIER)

		if self.__watches_installed and not force_reload:
			return

		if force_reload:
			# set the property to whatever, it will find the directory for itself.
			self.homeDirectory = 'wasted string'

		# This is just in case it hasn't already been done before.
		self.__load_check_rules()

		# put this in the queue, to avoid taking too much time at daemon start.
		workers.service_enqueue(priorities.HIGH,
					self.__watch_directory, self.homeDirectory, initial=True)

		self.__watches_installed = True
	def _standard_check(self, minimal=True, force=False,
						batch=False, auto_answer=None, full_display=True):
		""" Check a standard CoreFSUnitObject. This works for users and groups,
			and generally speaking, any object which has a home directory.

			Specific things are left to the CoreObject itself (helper groups,
			symlinks, etc).
		"""

		assert ltrace_func(TRACE_CHECKS)

		if self._checking.is_set():
			logging.warning(_(u'{0} {1}: somebody is already checking; '
				u'operation aborted.').format(
					self.controller.object_type_str,
					stylize(ST_NAME, self.name)))
			return

		with self.lock:
			try:
				self._checking.set()

				logging.info(_(u'Checking {0} {1}…').format(
						_(self.__class__.__name__.lower()),
						stylize(ST_NAME, self.name)))

				if hasattr(self, '_pre_standard_check_method'):
					self._pre_standard_check_method(minimal, force, batch,
														auto_answer, full_display)

				# NOTE: in theory we shouldn't check if the dir exists here, it
				# is done in fsapi.check_one_dir_and_acl(). but we *must* do it
				# because we set uid and gid to -1, and this implies the need to
				# access to the path lstat() in ACLRule.check_dir().
				if not os.path.exists(self.homeDirectory):
					if batch or logging.ask_for_repair(_(u'Directory %s does not '
									u'exist but it is mandatory. Create it?') %
										stylize(ST_PATH, self.homeDirectory),
									auto_answer=auto_answer):
						os.mkdir(self.homeDirectory)

						if full_display:
							logging.info(_(u'Created directory {0}.').format(
								stylize(ST_PATH, self.homeDirectory)))

						# if home directory was missing, inotify watches are
						# probably missing. Re-set them up. If the object is
						# not inotified, this will install only the
						# configuration file watch.
						self._inotifier_add_watch()
					else:
						raise exceptions.LicornCheckError(_(u'Directory %s does not '
							u'exist but is mandatory. Check aborted.') %
								stylize(ST_PATH, self.homeDirectory))

				if self.check_rules is not None:

					try:
						checked = set()

						if __debug__:
							length     = 0
							old_length = 0

						for checked_path in fsapi.check_dirs_and_contents_perms_and_acls_new(
							self.check_rules, batch=batch, auto_answer=auto_answer,
								full_display=full_display):

							checked.add(checked_path)

							if __debug__:
								length = len(checked)

								if length != old_length:
									old_length = length
									logging.progress(_('{0} {1}: meta-data '
										'changed on path {2}.').format(
											self.controller.object_type_str,
											stylize(ST_NAME, self.name),
											stylize(ST_PATH, checked_path)))

							# give CPU to other threads.
							time.sleep(0)

						if full_display:
							# FIXME: pluralize
							logging.progress(_('{0} {1}: meta-data changed '
								'on {2} path(s).').format(
									self.controller.object_type_str,
									stylize(ST_NAME, self.name),
									stylize(ST_PATH, len(checked))))

					except TypeError:
						# nothing to check (fsapi.*() returned None and yielded nothing).
						if full_display:
							logging.info(_('{0} {1}: no shared data to '
								'check.').format(
								self.controller.object_type_str,
								stylize(ST_NAME, self.name)))

					except exceptions.DoesntExistException, e:
						logging.warning('%s %s: %s' % (
							self.controller.object_type_str,
							stylize(ST_NAME, self.name), e))

				# if the home dir or helper groups get corrected,
				# we need to update the CLI view.

			finally:
				self._cli_invalidate()
				self._checking.clear()

		if not minimal and hasattr(self, '_extended_standard_check_method'):
			# TODO: if extended / not minimal: all group members' homes are OK
			# (recursive CheckUsers recursif)
			# WARNING: be carefull of recursive multicalls, when calling
			# CheckGroups, which calls CheckUsers, which could call
			# CheckGroups()… use minimal=True as argument here, don't forward
			# the current "minimal" value.
			self._extended_standard_check_method(
				batch=batch, auto_answer=auto_answer, full_display=full_display)

	# pseudo-private methods.
	def _resolve_home_directory(self, directory=None):
		""" construct the standard value for a user/group home directory, and
			try to find if it a symlink. If yes, resolve the symlink and
			remember the result as the real home dir for the current session.

			Whatever the home is, return it. The return result of this
			method is meant to be stored as self.homeDirectory.

			If the home directory doesn't exist, don't raise any error:

			- if we are in user/group creation phase, this is completely normal.
			- if in any other phase, the problem will be corrected by the
			  check mechanism, and will be pointed by the [internal]
			  permissive resolver method (for groups).
		"""

		if self.is_system:
			return self._build_system_home(directory)

		if directory in (None, ''):
			home = self._build_standard_home()
		else:
			home = directory

		# follow the symlink for the group home, only if link destination
		# is a directory. This allows administrator to put big group dirs
		# on different volumes.
		if os.path.islink(home):
			if os.path.exists(home) \
				and os.path.isdir(os.path.realpath(home)):
				home = os.path.realpath(home)

		return home
	def _fast_aclcheck(self, path, expiry_check=False):
		""" check a file in a shared group directory and apply its perm
			without any confirmation.

			:param path: path of the modified file/dir
		"""

		if expiry_check:
			with self.__expiry_lock:
				expiry = self.__last_fast_check.get(path, None)

				if expiry:
					# don't check a previously checked file, if previous check was less
					# than 5 seconds.
					if time.time() - expiry < self.__expire_time:
						assert ltrace(TRACE_CHECKS, '  %s._fast_aclcheck: not expired %s' % (self.name, path))
						return
					else:
						del self.__last_fast_check[path]

		home = self.homeDirectory

		try:
			entry_stat = os.lstat(path)

		except (IOError, OSError), e:
			if e.errno == 2:
				if path != home:
					# bail out if path has disappeared since we were called.
					return
				else:
					# this is bad, our home directory disappeared... Should we
					# rebuild it ? NO => the admin could be just moving it to
					# another volume. Just display a warning and give an hint
					# on what to do after the move.
					#
					# NOT workers.aclcheck_enqueue(self.check, batch=True)
					logging.warning(_(u'{0}: home directory {1} disappeared. '
						u'If this is intentional, do not forget to run "{2}" '
						u'afterwards, to restore the inotifier watch.').format(
							stylize(ST_NAME, self.name), stylize(ST_PATH, home),
							stylize(ST_IMPORTANT, 'mod %s %s -w' % (
								self.controller.object_type_str, self.name))))

					self._inotifier_del_watch()
			else:
				raise e

		rule_name = path[len(home)+1:].split('/')[0]

		try:
			# if the path has a special rule, load it
			dir_info = self.__check_rules[rule_name].copy()

		except (AttributeError, KeyError):
			# else take the default one
			dir_info = self.__check_rules._default.copy()

		if path[-1] == '/':
			path = path[:-1]

		# the dir_info.path has to be the path of the checked file
		dir_info.path = path

		# determine good UID owner for the path:
		try:
			# this will fail for a group, and succeed for a user.
			# any home/sub-dir/sub-file get the current user as owner.
			dir_info.uid = self.uidNumber
			is_user      = True

		except:
			# a group home gets "root" as owner, any subdir/sub-file keeps its
			# current owner.
			is_user = False
			if path == home:
					dir_info.uid = 0
			else:
				dir_info.uid = -1


		# determine good GID owner for the path:
		#	- 'acl' if an acl will be set to the path.
		#	- the primary group of the user owner of the path, if uid will not
		#		be changed.
		#	- 'acl' if we don't keep the same uid.
		try:
			if dir_info.root_dir_acl and (	':' in dir_info.root_dir_perm
											or ',' in dir_info.root_dir_perm):
					dir_info.gid = LMC.configuration.acls.gid

			else:
				if dir_info.uid == -1:
					# FIXME: shouldn't we force the current group ??
					dir_info.gid = LMC.users[entry_stat.st_uid].gidNumber

				else:
					if is_user:
						# in a user's home, every file should belong to the user's GID.
						dir_info.gid = self.gidNumber
					else:
						# in a group shared dir, there are always ACLs
						# (NOACL or RESTRICT are non-sense, the dir is *shared*).
						dir_info.gid = LMC.configuration.acls.gid

		except Exception, e:
			logging.warning(_(u'{0}: problem checking {1}, aborting '
				'(traceback and dir_info follow)').format(self.name, path))
			pyutils.print_exception_if_verbose()
			return

		# run the check, and catch expected events on the way: check_perms
		# yields touched paths along the way.
		with self.lock:

			self.__check_expected.update(fsapi.check_perms(dir_info, batch=True,
					file_type=(entry_stat.st_mode & 0170000),
					is_root_dir=(rule_name is ''), full_display=__debug__))

		with self.__expiry_lock:
			self.__last_fast_check[path] = time.time()
	def _expire_events(self):
		""" remove all expired events. """

		with self.__expiry_lock:
			for key, value in self.__last_fast_check.items():
				if time.time() - value >= self.__expire_time:
					assert ltrace(TRACE_CHECKS, '  %s: expired %s' % (self.name, key))
					del self.__last_fast_check[key]

__all__ = ('CoreUnitObject', 'CoreStoredObject', 'CoreFSUnitObject')
