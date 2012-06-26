# -*- coding: utf-8 -*-
"""
Licorn core controllers

:copyright:
	* 2010 Olivier Cortès <oc@meta-it.fr>
	* partial 2010 Robin Lucbernet <robinlucbernet@gmail.com>

:license: GNU GPL version 2

"""

import glob, os, time

from threading import current_thread


from licorn.foundations           import settings, exceptions, logging
from licorn.foundations           import fsapi
from licorn.foundations.threads   import RLock
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.constants import filters
from licorn.foundations.base      import Enumeration, NamedObject, \
											MixedDictObject

from licorn.core                  import LMC

class SelectableController(NamedObject, dict):
	""" This class makes the current controller be selectable by
		`daemon.rwi.select()`. This is used in many places across CLI tools,
		WMI, and core internals.

		The :class:`SelectableController` inherits :class:`dict` and indexes
		held :class:`CoreUnitObjects` on their ID.

		.. note:: the only **big** difference with the :class:`dict` behavior
			is iteration: when you run `for object in controller`, it will
			**iterate the values**, not the keys. This is the prefered way
			in Licorn®.

		.. versionadded:: long ago in the past. perhaps Licorn® 1.1 or 1.2, I
			can't seem to remember.
	"""

	instances = {}

	_licorn_protected_attrs = (
			MixedDictObject._licorn_protected_attrs
			+ [ 'instances' ]
		)

	def __init__(self, *args, **kwargs):

		super(SelectableController, self).__init__(*args, **kwargs)

		SelectableController.instances[self.name] = self
	def guess_one(self, value):
		""" Try to guess everything of a user from a
			single and unknown-typed info. """
		try:
			return self.by_id(value)

		except (TypeError, ValueError):
				return self.by_name(value)
	def guess_list(self, value_list):
		objs = set()

		for value in value_list:
			try:
				objs.add(self.guess_one(value))

			except (KeyError, exceptions.DoesntExistException):
				logging.notice(_(u'Skipped non-existing {0} or {1} {2}.').format(
								self.object_type_str, self.object_id_str, value))

		return list(objs)
	def __iter__(self):
		return dict.itervalues(self)
	def __getattr__(self, attr_name):
		try:
			return dict.__getitem__(self, attr_name)
		except KeyError:
			raise AttributeError(_(u'"{0}" is neither an attribute nor an '
								u'item of {1}.').format(attr_name, str(self)))
class LockedController(SelectableController):
	""" Thread-safe object, protected by a global :class:`~threading.RLock`,
		with a :attr:`licornd` property giving access to the Licorn® daemon
		(to benefit from the service* facility).

		The :meth:`__getitem__`, :meth:`__setitem__`, and :meth:`__delitem__`
		methods automatically aquire and release the global  :attr:`lock`.

		.. note:: the :attr:`lock` attribute is really a method returning the
			:class:`~threading.RLock` object, because the lock object itself is not stored
			inside the instance: as Pyro can't pickle a :class:`~threading.RLock` object,
			it must be stored in the :class:`LockManager` and looked up
			everytime, until we found a better solution.

		.. versionadded:: 1.3

	"""

	_licorn_protected_attrs = (
			SelectableController._licorn_protected_attrs
			+ [ 'lock' ]
		)

	@property
	def licornd(self):
		return self.__licornd

	def __init__(self, *args, **kwargs):

		super(LockedController, self).__init__(*args, **kwargs)

		assert ltrace_func(TRACE_OBJECTS)

		self.__warnings = kwargs.pop('warnings', True)

		# this will be set to True if the EventManager needs to walk through
		# all our *contained* objects, looking for event callbacks. By default,
		# this is false, but ModulesManager and other special controllers will
		# set it to True.
		self._look_deeper_for_callbacks = kwargs.pop('look_deeper_for_callbacks', False)

		# Create lock holder objects for the current LockedController
		# and all CoreUnitObjects stored inside us. The giant_lock is hidden,
		# in case we iter*() the master lock object, for it to return only the
		# UnitObject locks.
		self.lock = RLock()

		self.__licornd = LMC.licornd
	def __getitem__(self, key):
		""" From :class:`LockedController`: this is a classic
			:meth:`__getitem__` method, made thread-safe by encapsulating it
			with the Controller's global :class:`~threading.RLock`. """
		with self.lock:
			return super(LockedController, self).__getitem__(key)
	def __setitem__(self, key, value):
		""" the classic :meth:`__setitem__` method, encapsulated withn the
			controller's global :class:`~threading.RLock` to be thread-safe. """
		with self.lock:
			return super(LockedController, self).__setitem__(key, value)
	def __delitem__(self, key):
		""" Delete data inside us, protected with our lock. """
		with self.lock:
			return super(LockedController, self).__delitem__(key)
	def acquire(self):
		""" acquire the controller global lock. """
		assert ltrace(TRACE_THREAD, '%s: acquiring %s %s.' % (
			current_thread().name, self.name, self.lock))
		return self.lock.acquire()
	def release(self):
		""" release the controller global lock. """
		assert ltrace(TRACE_THREAD, '%s: releasing %s %s.' % (
			current_thread().name, self.name, self.lock))
		return self.lock.release()
	def is_locked(self):
		""" Return True if current controller lock is acquired, else False.

			.. warning:: calling this :meth:`is_locked` method costs a few CPU
				cycles, because of the object lookup (see note above). Try to
				avoid using it as much as possible. """
		the_lock = self.lock
		if the_lock.acquire(blocking=False):
			the_lock.release()
			return False
		return True
class CoreController(LockedController):
	""" The :class:`CoreController` class implements multiple functionnalities:

		- storage for :class:`CoreUnitObject` s, via the dict part of
		  :class:`~licorn.foundations.base.MixedDictObject`.
		- backends and extensions resolution via the generic method
		  :meth:`load_modules`. Backend priorities are handled if supported by
		  the backends themselves (some do, and some don't).
		- reverse mappings via one or more protected dictionnary, created and
		  updated on the fly.

		.. warning:: updating :class:`CoreUnitObject` s attributes directly
			doesn't update the reverse mappings yet. This may be implemented in
			a future release. The reverse mapping functionnality may thus be
			considered incomplete, because a part of the update process must be
			done manually. Sorry for that, folks.

		.. versionadded:: 1.3

	"""

	_licorn_protected_attrs = (
			LockedController._licorn_protected_attrs
			+ [ 'backends', 'extensions' ]
		)

	def __init__(self, *args, **kwargs):

		super(CoreController, self).__init__(*args, **kwargs)

		assert ltrace_func(TRACE_OBJECTS)

		if __debug__:
			self._trace_name = globals()['TRACE_' + self.name.upper()]

		#: Keeping the reverse mapping dicts in a container permits having
		#: more than one reverse mapping available for UnitObjects (kind of an
		#: internal index) and update them fast when an object is altered.
		#:
		#: The mapping construct permits having different mapping names instead
		#: of fixed ones (e.g. "login" for users, "name" for groups, "hostname"
		#: for machines...).

		# TODO: still usefull ?
		#self._reverse_mappings = MixedDictObject(
		#		self.name + '_reverse_mappings')
		#for mapping_name in kwargs.pop('reverse_mappings', []):
		#	mapping = {}
		#	self.__setattr__('by_' + mapping_name, mapping)
		#	self._reverse_mappings[mapping_name] = mapping

		#: prefixed with '_', prefered backend attributes are automatically
		#: protected and stored out of the dict() part of self, thanks to
		#: MixedDictObject.
		self._prefered_backend = None

		self.backends = LMC.backends.find_compatibles(self)

		self.find_prefered_backend()

		# on client first pass, extensions are not yet loaded.
		if hasattr(LMC, 'extensions'):
			self.extensions = LMC.extensions.find_compatibles(self)

		else:
			self.extensions = None
	def reload(self):
		""" load extensions if possible. This could not be possible if the
			controller is :meth:`reload` ing during the CLIENT-daemon first
			launch of its method
			:meth:`~licorn.core.LicornMasterController.init_client_first_pass`.
		"""

		assert ltrace_func(self._trace_name)

		self.reload_extensions()
	def reload_extensions(self):
		""" load all our extensions. """

		if hasattr(self, 'extensions') and self.extensions:
			self.load_extensions()
		else:
			if hasattr(LMC, 'extensions'):
				self.extensions = LMC.extensions.find_compatibles(self)
				self.load_extensions()
			else:
				self.extensions = None
	def load_extensions(self):
		""" special case for SystemController. """
		assert ltrace_func(self._trace_name)

		for ext in self.extensions:
			getattr(ext, self.name + '_load')()
	def dump(self):
		""" Dump the internal data structures (debug and development use). """

		assert ltrace_func(self._trace_name)

		with self.lock:

			dicts_to_dump = [ (self.name, self) ]
				#+ [
				#(mapping_name, mapping)
				#	for mapping_name, mapping
				#		in self._reverse_mappings.items() ]

			return '\n'.join([
				'%s:\n%s' % (
					stylize(ST_IMPORTANT, mapping_name),
					'\n'.join([
							'\t%s: %s' % (key, value)
								for key, value in sorted(mapping_dict.items())
						])
					)
					for mapping_name, mapping_dict in dicts_to_dump
				])
	def find_prefered_backend(self):
		""" iterate through active backends and find the prefered one.
			We use a copy, in case there is no prefered yet: LMC.backends
			will change and this would crash the for_loop.

			.. note:: TODO: this method may soon move into the
				:class:`~licorn.core.backends.BackendsManager` instead of the
				controller.
			"""

		assert ltrace(self._trace_name, '> find_prefered_backend(current=%s, mine=%s, existing=%s, mine_is_ok:by_key=%s,by_value=%s)' % (
				self._prefered_backend.name if self._prefered_backend != None else 'none',
				', '.join(backend.name for backend in self.backends),
				', '.join(backend.name for backend in LMC.backends.itervalues()),
				(self._prefered_backend.name if self._prefered_backend != None else None) in LMC.backends.iterkeys(),
				self._prefered_backend in LMC.backends.itervalues()))

		if self.backends == []:
			assert ltrace(self._trace_name, '  no backends for %s, aborting prefered search.' % self.name)
			return

		changed = False

		# remove an old backend name if the corresponding just got disabled.
		# else we don't change if the old had a better priority than the
		# remaining ones.
		#
		# NOTE: we can't use "and self._prefered_backend not in LMC.backends.itervalues()",
		# for an obscure reason, it doesn't work as expected, even if the backend
		# seems not to be in the current values.
		if self._prefered_backend != None \
			and self._prefered_backend.name not in LMC.backends.iterkeys():
			self._prefered_backend = None

		# start with nothing to be sure
		#self._prefered_backend = None

		for backend in self.backends:
			if self._prefered_backend is None:
				assert ltrace(self._trace_name, ' found first prefered_backend(%s)' %
					backend.name)
				self._prefered_backend = backend
				changed = True

			else:
				if hasattr(backend, 'priority'):
					if backend.priority > self._prefered_backend.priority:
						assert ltrace(self._trace_name,
							' found better prefered_backend(%s)' % backend.name)
						self._prefered_backend = backend
						changed = True
					else:
						assert ltrace(self._trace_name,
							' discard lower prefered_backend(%s)' %
								backend.name)
						pass
				else:
					assert ltrace(self._trace_name,
						' no priority mechanism, skipping backend %s' %
							backend.name)

		assert ltrace(self._trace_name, '< find_prefered_backend(%s, %s)' % (
			self._prefered_backend.name, changed))
		return changed
class CoreFSController(CoreController):
	""" FIXME: TO BE DOCUMENTED

		.. versionadded:: 1.3

	"""
	_licorn_protected_attrs = (
		CoreController._licorn_protected_attrs
		+ [  'check_templates' ]
	)
	def __init__(self, *args, **kwargs):

		super(CoreFSController, self).__init__(*args, **kwargs)

		assert ltrace(TRACE_CHECKS, 'CoreFSController.__init__()')

		self._rules_base_conf = '%s/%s.*.conf' % (
						settings.check_config_dir,
						self.name)

		self.__last_expire_time = 0.0
	def reload(self):
		""" reload the templates rules generated from systems rules. """


		assert ltrace(TRACE_CHECKS, '| LicornCoreFSController.reload(%s)' %
														self._rules_base_conf)

		CoreController.reload(self)
	def load_system_rules(self, vars_to_replace):
		""" load system rules """
		# if system rules have already been loaded, do not reload them.
		try:
			self.check_templates

		except AttributeError:
			assert ltrace(TRACE_CHECKS, '| load_system_rules(%s)' %
														self._rules_base_conf)

			self.check_templates = Enumeration()

			# a default enumeration that will serve as base for all rules.
			enum_base = Enumeration(home='%%s', user_uid=-1, user_gid=-1)

			for filename in glob.glob(self._rules_base_conf):
				rules = self.parse_rules(rules_path=filename,
											object_info=enum_base,
											vars_to_replace=vars_to_replace)

				if '_default' in rules.name:
					self.check_templates['~'] = rules['~']

				else:
					for rule in rules:
						self.check_templates[rule.name] = rule
	def load_rules(self, core_obj, rules_path, object_info, vars_to_replace=None):
		""" load special rules (rules defined by user) and merge system rules
			with them.
			Only the system default rule can be overwriten by the user default
			rule. If any other user rule is in conflict with a system rule, the
			system one will be used.

			This function return only applicable rules """

		assert ltrace(TRACE_CHECKS, '> load_rules(rules_path=%s, object_info=%s, '
					'core_obj=%s, vars_to_replace=%s)' % (rules_path, object_info,
					core_obj.name, vars_to_replace))

		def path_to_exclude(dir_info):
			tmp_path = dir_info.path[:]

			if tmp_path.endswith('/'):
				tmp_path = tmp_path[:-1]

			return tmp_path.replace('%s%s' % (object_info.home, os.sep), '')

		# load system rules.
		self.load_system_rules(vars_to_replace=vars_to_replace)

		# load user rules.
		rules = self.parse_rules(
								rules_path,
								object_info=object_info,
								system_wide=False,
								vars_to_replace=vars_to_replace)

		# check system rules, if the directory/file they are managing exists add
		# them the the *valid* system rules enumeration.
		system_special_dirs = Enumeration(name='system_special_dirs')

		#assert ltrace(self._trace_name, '  check_templates %s '
		#	% self.check_templates.dump_status(True))

		for dir_info in self.check_templates:
			#assert ltrace(self._trace_name, '  using dir_info %s ' % dir_info.dump_status(True))
			temp_dir_info = dir_info.copy()
			temp_dir_info.path = temp_dir_info.path % object_info.home

			if os.path.exists(temp_dir_info.path):

				if temp_dir_info.uid == '%s':
					temp_dir_info.uid = object_info.user_uid

				if temp_dir_info.root_gid == '%s':
					temp_dir_info.root_gid = object_info.user_gid

				if temp_dir_info.content_gid == '%s':
					temp_dir_info.content_gid = object_info.user_gid

				system_special_dirs.append(temp_dir_info)

		default_exclusions = set()

		# we need to know if there is a user default rule.
		user_default = False
		for dir_info in rules:
			if dir_info.rule.default:
				user_default = True

		# If user rules contains a default rule, we keep the user one.
		# Else, a system rule has priority on user rules
		for dir_info in system_special_dirs:

			# if it is a system default rule, and if there is a user default
			# rule, skip the system one.
			if dir_info.rule.default and user_default:
				logging.progress(_(u'{0} user rule that wanted to overwrite '
									u'system default rule.').format(
										stylize(ST_BAD, _(u'Skipped'))))
				continue

			# if there are variables to replace, do it
			if vars_to_replace is not None:
				for var, value in vars_to_replace:

					if type(dir_info.dirs_perm) is not int and var in dir_info.dirs_perm:
						dir_info.dirs_perm = dir_info.dirs_perm.replace(var, value)

					if type(dir_info.files_perm) is not int and var in dir_info.files_perm:
						dir_info.files_perm = dir_info.files_perm.replace(var, value)

					if type(dir_info.root_dir_perm) is not int and var in dir_info.root_dir_perm:
						dir_info.root_dir_perm = dir_info.root_dir_perm.replace(var, value)

					if var in dir_info.rule.acl:
						dir_info.rule.acl = dir_info.rule.acl.replace(var, value)

			# if the system rule name is already present in the user rules, keep
			# the system one.
			if dir_info.name in rules.keys():
				overriden_dir_info = rules[dir_info.name]

				logging.warning(_(u'{0} group rule for path {1} '
								u'({2}:{3}), overriden by system '
								u'rule ({4}:{5}).').format(
									stylize(ST_BAD, _(u'Ignored')),
									stylize(ST_PATH, dir_info.path),
									overriden_dir_info.rule.file_name,
									overriden_dir_info.rule.line_no,
									dir_info.rule.file_name,
									dir_info.rule.line_no))
			# if the system rule is not in the user rules, add it.
			else:

				tmp_path = path_to_exclude(dir_info)

				if tmp_path != dir_info.path:
					default_exclusions.add(tmp_path)

				logging.progress(_(u'{0} {1} ACL rule: '
									u'"{2}" for "{3}".').format(
									stylize(ST_OK, _(u'Added')),
									_(u'system')
										if dir_info.rule.system_wide
										else self.name,
									stylize(ST_NAME, dir_info.rule.acl),
									stylize(ST_NAME, dir_info.path)))

			rules[dir_info.name] = dir_info

		# last loop, to prepare the rules.
		for di in rules:
			if di.rule.default:
				rules._default = di.copy()
				rules.remove(di.name)

			else:
				tmp_path = path_to_exclude(di)

				# exclude the rule path from the default rule, but only if
				# it is a sub-sub-dir; because subdirs (only 1 level) will
				# already be excluded by the next inner loop.
				if os.sep in tmp_path:
					default_exclusions.add(tmp_path)

				# Then, exclude the rule path from other "surrounding" rules.
				# Eg. if we have 2 rules for 'rep1/' and 'rep1/subrep', we
				# have to exclude 'subrep' from the 'rep1/' rule, else it
				# will be checked twice.
				for other_rule in rules:
					if os.path.dirname(di.path) == other_rule.path:
						other_rule.exclude.add(os.path.basename(di.path))

		# add dirs/files exclusions to the default rule.
		try:
			rules._default.exclude |= default_exclusions

		except AttributeError:
			raise exceptions.LicornCheckError(_(u'There is no default '
					u'rule. Check %s.') % stylize(ST_BAD, _(u'aborted')))

		assert ltrace(TRACE_CHECKS, '< load_rules()')
		return rules
	def parse_rules(self, rules_path, vars_to_replace, object_info,
														system_wide=True):
		""" parse a rule from a line to a fsapi.FsapiObject. Returns
			a single :class:`~licorn.foundations.base.Enumeration`, containing
			either ONE '~' rule, or a bunch of rules. """

		assert ltrace(TRACE_CHECKS, "> parse_rules(%s, %s, %s)" % (rules_path,
			object_info, system_wide))

		special_dirs = None

		if os.path.exists(rules_path):
			rules        = []
			special_dirs = Enumeration(name=rules_path)

			with open(rules_path, 'r') as f:
				file_contents = enumerate(f.readlines())

			for line_no, line in file_contents:

				# skip comments
				if line[0] == '#':
					continue

				try:
					# generate rule
					rule = fsapi.ACLRule(file_name=rules_path,
										rule_text=line,
										line_no=line_no,
										system_wide=system_wide,
										base_dir=object_info.home
											if not system_wide else None,
										object_id=object_info.user_uid
											if not system_wide else None,
										controller=self)
					#logging.notice(">>> rule = %s" % rule.dump_status(True))

				except exceptions.LicornRuntimeException, e:
					logging.warning2(e)
					continue

				try:
					# check the rule
					rule.check()

					# create a readable directory
					directory = rule.dir
					if directory == '':
						directory = rule.name

					elif directory == '/':
						directory = rule.name + '/'

					logging.progress(_(u'{0} {1} ACL rule {2}: "{3}" for '
						u'"{4}".').format(stylize(ST_OK,_('Added')),
							self.name,
							_(u'template') if system_wide else u'',
							stylize(ST_NAME, rule.acl),
							stylize(ST_NAME, directory)))

				except exceptions.LicornSyntaxException, e:
					logging.warning(_(u'{0}.parse_rules: {1}').format(self.name, e))
					continue

				except exceptions.PathDoesntExistException, e:
					logging.warning2(_('{0}.parse_rules: {1}').format(self.name, e))
					continue

				else:
					rules.append(rule)

			for rule in rules:
				try:
					if rule.name in special_dirs.keys():
						if rule.dir.endswith('/'):
							dir_info = rule.generate_dir_info(
								object_info=object_info,
								# FIXME: WTF is this dir_info?
								# Where does it come from?
								dir_info_base=dir_info,
								system_wide=system_wide,
								vars_to_replace=vars_to_replace)
						#else:
							#print '>>> not a /'
					else:
						dir_info = rule.generate_dir_info(
							object_info=object_info,
							system_wide=system_wide,
							vars_to_replace=vars_to_replace)

				except exceptions.LicornSyntaxException, e:
					logging.exception(_(u'parse_rules(): Exception on {0} '
						u'(special={1}).'), (ST_NAME, rule.name),
							(ST_ATTR, rule.name in special_dirs.keys()))
					continue

				if dir_info.name not in special_dirs.keys():
					special_dirs.append(dir_info)

				assert ltrace(TRACE_CHECKS, '  parse_rules(%s dir_info %s)' %
						('add' if not dir_info.already_loaded else 'modify',
						dir_info.dump_status(True) ))

		if special_dirs == None:
			special_dirs = Enumeration()

		assert ltrace(TRACE_CHECKS, '< parse_rules(%s)' % special_dirs)

		return special_dirs
	def _inotifier_install_watches(self, inotifier):
		""" Install all initial inotifier watches, for all existing standard
			objects (users, groups, whatever). This method is meant to be
			called directly by the inotifier thread. """

		logging.progress(_(u'{0:s}: installing watches…').format(self))

		for obj in self.select(filters.STD):
			try:
				# NOTE: if the object is not inotified, it will only install
				# the configuration file watch, not all the rest.
				obj._inotifier_add_watch()

			except:
				logging.exception(_(u'{0}: exception while installing '
									u'inotifier watches for {1} {2}'),
										stylize(ST_NAME, self.name),
										self.object_type_str,
										stylize(ST_NAME, obj.name))

	def _expire_events(self):
		""" iterate all our unit objects and make them verify they expired data. """

		# we need to lock in case this method is trigerred during a massive
		# unit object deletion (I encountered the 'dictionnary size changed'
		# error during tests of TS#62 (massive imports/deletes).

		#assert ltrace_locks(self.lock)

		with self.lock:
			if (time.time() - self.__last_expire_time) >= settings.defaults.global_expire_time:

				self.__last_expire_time = time.time()

				for object in self:
					object._expire_events()

		#assert ltrace_locks(self.lock)

__all__ = ('SelectableController', 'LockedController', 'CoreController', 'CoreFSController')
