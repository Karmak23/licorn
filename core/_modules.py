# -*- coding: utf-8 -*-
"""
Licorn core modules base classes

:copyright:
	* 2010 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2

"""
import os

from licorn.foundations.threads import RLock

from licorn.foundations           import settings, exceptions, logging
from licorn.foundations           import hlstr, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.events    import LicornEvent
from licorn.foundations.constants import roles
from licorn.foundations.base      import NamedObject, MixedDictObject, \
											LicornConfigObject

# local core imports
from _controllers                 import LockedController
from _objects                     import CoreUnitObject

class ModulesManager(LockedController):
	""" The basics of a module manager. Backends and extensions are just
		particular cases of this class.

		.. note:: TODO: implement module_sym_path auto-detection, for the day
			we will use it. For now we don't care about it.

		.. versionadded:: 1.3

	"""
	#: In this class we've got some reserved attributes to hide from dict-like
	#: methods.
	_licorn_protected_attrs = (
			LockedController._licorn_protected_attrs
			+ ['module_type', 'module_path', 'module_sym_path']
		)

	# the "selectable" controller attributes
	# the modules must have an '_id_field' class attribute, too.
	@property
	def sort_key(self):
		return 'name'
	@property
	def object_type_str(self):
		return _(u'module')
	@property
	def object_id_str(self):
		return _(u'module name')
	def by_name(self, name):
		return self[name]
	#: the generic way, called from `RWI.select()`
	by_key = by_name
	by_id  = by_name

	def word_match(self, word):
		return hlstr.word_match(word, self.keys())

	def __init__(self, *args, **kwargs):

		# add this argument for LockedController.__init__()
		kwargs['look_deeper_for_callbacks'] = True

		super(ModulesManager, self).__init__(*args, **kwargs)

		assert ltrace_func(TRACE_OBJECTS)

		self.module_type     = kwargs.pop('module_type')
		self.module_path     = kwargs.pop('module_path')
		self.module_sym_path = kwargs.pop('module_sym_path')

		if __debug__:
			self._trace_name = globals()['TRACE_' + self.name.upper()]
	def load(self, server_side_modules=None):
		""" load our modules (can be different type but the principle is the
			always the same).

			If we are on the server, activate every module we can.
			If we are on a client, activate module only if module is enable
			on the server.

			.. note:: TODO: implement module dependancies resolution. this is
				needed for the upcoming rdiff-backup/volumes extensions
				couple (at least).
		"""

		assert ltrace(self._trace_name, '> load(type=%s, path=%s, server=%s)' % (
			self.module_type, self.module_path, server_side_modules))

		def gather_modules_and_dependancies():
			""" Gather .py files, import classes and resolve dependancies via
				classes attributes. Modules are not yet instanciated, only
				classes are collected.
			"""

			for entry in os.listdir(self.module_path):

				if os.path.isdir(os.path.join(self.module_path, entry)) \
								and os.path.exists(os.path.join(
									self.module_path, entry, '__init__.py')):
					# extension is a subdir.
					module_name = entry

				elif entry[0] == '_' or entry[-3:] != '.py' or 'test' in entry:
					# this is nothing interesting, skip.
					continue

				else:
					# extension is a simple <file>.py; remove suffix '.py'
					module_name = entry[:-3]

				# class name is a convention, guessed from the file / dir name.
				class_name  = module_name.title() + self.module_type.title()

				try:
					python_module = __import__(self.module_sym_path
												+ '.' + module_name,
												globals(), locals(), class_name)
					module_class  = getattr(python_module, class_name)

				except (ImportError, SyntaxError, AttributeError):
					logging.exception(_(u'{0} unusable {1} {2}, exception '
										u'encountered during import.'),
										(ST_BAD, _(u'Skipped')), self.module_type,
										(ST_NAME, module_name))
					continue

				modules_classes[module_name] = module_class

				try:
					modules_dependancies[module_name] = module_class.module_depends[:]

				except AttributeError:
					modules_dependancies[module_name] = []
		def not_manually_ignored(module_name):
			""" See if module has been manually ignored in the main
				configuration file, and return the result as expected
				from the name of the method.
			"""

			# find the "extension" or "backend" node of settings.
			if hasattr(settings, self.name):
				conf = getattr(settings, self.name)

				# Try the global ignore directive.
				if hasattr(conf, 'ignore'):
					assert ltrace(self._trace_name, '| not_manually_ignored(%s) → %s '
						'(global)' % (module_name, (module_name
											not in getattr(conf, 'ignore'))))

					return module_name not in getattr(conf, 'ignore')

				# Else try the individual module ignore directive.
				if hasattr(conf, module_name):
					module_conf = getattr(conf, module_name)

					if hasattr(module_conf, 'ignore'):
						assert ltrace(self._trace_name, '| not_manually_ignored(%s) → %s '
							'(individually)' % (module_name,
											module_conf.ignore))

						return not module_conf.ignore

			# if no configuration directive is found, the module is considered
			# not ignored by default, it will be loaded.
			assert ltrace(self._trace_name, '| not_manually_ignored(%s) → %s (no match)' % (
																module_name, True))
			return True

		# We've got to check the server_side_modules argument too, because at
		# first load of client LMC (first pass), server modules are not known:
		# we must first start, then connect, then reload with server_modules
		# known.
		# Thus, if server_side_modules is None, we simulate a SERVER mode to
		# load everything possible. Superfluous modules will be disabled on
		# subsequent passes.
		if settings.role == roles.CLIENT and server_side_modules != None:
			is_client = True

		else:
			is_client = False

		modules_classes      = {}
		modules_dependancies = {}

		gather_modules_and_dependancies()

		assert ltrace(self._trace_name, 'resolved dependancies module order: %s.' %
				', '.join(pyutils.resolve_dependancies_from_dict_strings(modules_dependancies)))

		changed = False
		depended_disabled_modules = []

		for module_name in pyutils.resolve_dependancies_from_dict_strings(modules_dependancies):

			if module_name in depended_disabled_modules:
				logging.warning(_(u'{0}: will not try to load {1} {2} because '
					u'one or more of its dependancies failed to load.').format(
						self.pretty_name, self.module_type,
							stylize(ST_NAME, module_name)))
				continue

			module_class = modules_classes[module_name]

			# Is module already loaded ?

			if module_name in self.iterkeys():
				module = self[module]

				if module.enabled:
					# module already loaded locally. Enventually sync with the
					# server, else just jump to next module.
					if is_client and module_name not in server_side_modules:
						self.disable_func(module_name)
						changed = True
					continue

				else:
					# Module already loaded locally, but only available.
					# Eventually sync if enabled on the server, else just
					# jump to next module.
					if is_client and module_name in server_side_modules:
						self.enable_func(module_name)
						changed = True
					continue

			# module is not already loaded. Load and sync client/server

			assert ltrace(self._trace_name, 'importing %s %s' % (self.module_type,
				stylize(ST_NAME, module_name)))

			# the module instanciation, at last!
			module = module_class()

			assert ltrace(self._trace_name, 'imported %s %s, now loading.' % (
				self.module_type, stylize(ST_NAME, module_name)))

			if not_manually_ignored(module.name):

				LicornEvent('%s_%s_loads' % (
									self.module_type, module_name),
							synchronous=True).emit()

				try:
					module.load(server_modules=server_side_modules)

					# Automatically collect all events and
					# callbacks of the module.
					events.collect(module)

					LicornEvent('%s_%s_loaded' % (
									self.module_type, module_name)).emit()

				except Exception, e:
					# an uncatched exception occured, the module is buggy or
					# doesn't handle a very specific situation. The module
					# didn't load, we must disable other modules which depend
					# on it.

					r_depended = [m for m in
						modules_dependancies.keys()
							if module_name in modules_dependancies[m]]

					logging.exception(_(u'{0}: Exception in {1} {2} during load'),
						self.pretty_name, self.module_type, (ST_NAME, module_name))

					if r_depended:
						depended_disabled_modules.extend(r_depended)

						logging.warning(_(u'Disabling dependant {0}(s) {1} '
										u'to avoid further problems.').format(
											self.module_type,
											', '.join(stylize(ST_NAME, name)
												for name in r_depended)))
					continue

				if module.available:

					# register the module in the controller
					self[module.name] = module

					if module.enabled:
						assert ltrace(self._trace_name, 'loaded %s %s' % (
							self.module_type, stylize(ST_NAME, module.name)))

						if is_client and module_name not in server_side_modules:
							try:
								self.disable_func(module_name)
								changed = True

							except exceptions.DoesntExistException, e:
								logging.warning2(_(u'cannot disable '
											u'non-existing {0} {1}.').format(
												self.module_type,
												stylize(ST_NAME, module.name)))
					else:
						assert ltrace(self._trace_name, '%s %s is only available'
							% (self.module_type, stylize(ST_NAME, module.name)))

						if is_client and module_name in server_side_modules:
							self.enable_func(module_name)
							changed = True
				else:
					assert ltrace(self._trace_name, '%s %s NOT available' % (
						self.module_type, stylize(ST_NAME, module.name)))

					if is_client and module_name in server_side_modules:
						raise exceptions.LicornRuntimeError(_(u'{0} {1} is '
							u'enabled on the server side but not available '
							u'locally, probably an installation '
							u'problem.').format(self.module_type, module_name))
			else:
				if is_client:
					if module_name in server_side_modules:
						raise exceptions.LicornRuntimeError(_(u'{0} {1} is '
							u'enabled on the server side but manually ignored '
							u'locally in {2}, please fix the problem before '
							u'continuing.').format(
								self.module_type, module_name,
								stylize(ST_PATH, settings.main_config_file)))
				else:
					logging.warning(_(u'{0} {1} {2}, manually ignored in {3}.').format(
									stylize(ST_DISABLED, _(u'Skipped')),
									self.module_type,
									stylize(ST_NAME, module.name),
									stylize(ST_PATH,
										settings.main_config_file)))

		assert ltrace(self._trace_name, '< load(%s)' % changed)
		return changed
	def find_compatibles(self, controller):
		""" Return a list of modules (real instances, not just
			names) compatible with a given controller.

			:param controller: the controller for which we want to lookup
				compatible extensions, passed as intance reference (not just
				the name, please).
		"""

		assert ltrace(self._trace_name, '| find_compatibles() %s for %s from %s → %s'
			% (stylize(ST_COMMENT, self.name),
				stylize(ST_NAME, controller.name),
					', '.join([x.name for x in self]),
					stylize(ST_ENABLED, ', '.join([module.name for module
						in self if controller.name in module.controllers_compat]
			))))

		return [ module for module in self
									if module.enabled
										and controller.name
											in module.controllers_compat ]
	def enable_module(self, module_name):
		""" Try to **enable** a given module_name. What is exactly done is left
			to the module itself, because the current method will just call the
			:meth:`~licorn.core.classes.CoreModule.enable` method of the module.

		"""

		assert ltrace_func(self._trace_name)

		with self.lock:
			try:
				module = self[module_name]

			except KeyError:
				raise exceptions.DoesntExistException(_(u'No {0} by that '
					'name "{1}".').format(self.module_type, module_name))

			if module.enabled:
				logging.notice(_(u'{0} {1} already enabled.').format(
								module_name, self.module_type))
				return False

			try:
				if module.enable():
					# (re-)collect all event handlers and callbacks of module.
					events.collect(module)

					logging.notice(_(u'successfully enabled {0} {1}.').format(
										module_name, self.module_type))
					return True

				else:
					logging.notice(_(u'{0} {1} would not enable itself.').format(
										module_name, self.module_type))
					return False

			except:
				logging.exception(_(u'Exception while enabling {0} {1}.'),
										self.module_type, module_name)
				return False

	# this will eventually be overwritten in subclasses.
	enable_func = enable_module
	def disable_module(self, module_name):
		""" Try to **disable** a given module. What is exactly done is left
			to the module itself, because the current method will just call the
			:meth:`~licorn.core.classes.CoreModule.disable` method of the module.

		"""

		assert ltrace_func(self._trace_name)

		with self.lock:
			try:
				module = self[module_name]

			except KeyError:
				raise exceptions.DoesntExistException(_(u'No {0} by that '
					'name "{1}".').format(self.module_type, module_name))


			if not module.enabled:
				logging.notice(_(u'{0} {1} already disabled.').format(
									module_name, self.module_type))
				return False

			try:
				try:
					# un(re-)collect all event handlers and callbacks of module.
					events.uncollect(module)

				except:
					logging.exception(_(u'Exception while unregistering '
									u'events handlers/callbacks of {0} {1}'),
										self.module_type, module_name)


				if module.disable():

					logging.notice(_(u'successfully disabled {0} {1}.').format(
										module_name, self.module_type))
					return True

				else:
					logging.notice(_(u'{0} {1} would not disable itself.').format(
										module_name, self.module_type))
					return False


			except:
				logging.exception(_(u'Exception while disabling {0} {1}.'),
										self.module_type, module_name)
				return False

	# this will eventually be overwritten in subclasses.
	disable_func = disable_module
	def check(self, batch=False, auto_answer=None):
		""" Check all **enabled** modules, then all **available** modules.
			Checking them will make them configure themselves, configure the
			required underlying system daemons, services or files, and
			eventually start services (depending of which type of module it
			is).

			For more details, refer to the
			:meth:`~licorn.core.classes.CoreModule.check` method of the desired
			module.
		"""

		assert ltrace_func(self._trace_name)

		to_disable = []

		with self.lock:
			# check our modules, AND available (not enabled) modules too. It's
			# the only way to make sure they can be fully usable before
			# enabling them.
			for module in self:
				#assert ltrace(self._trace_name, '  check(%s)' % module.name)
				try:
					module.check(batch=batch, auto_answer=auto_answer)

				except:
					# an uncatched exception occured, the module is buggy or
					# doesn't handle a very specific situation. Disable it to
					# avoir further problems.
					#
					# We disable it later to avoid dictionnary changes during
					# present iteration cycle, and will disable them in the
					# reverse order to avoid dependancies-related problems.
					logging.exception(_(u'{0}: unhandled exception during '
										u'{1} {2} check. Disabling it.'),
											self.pretty_name,
											self.module_type,
											(ST_NAME, module.name))

					to_disable.append(module)

			for module in reversed(to_disable):
				if module.enabled:
					# demote the module to available-only state
					self.disable_func(module.name)

				if module.available:
					# anyway, if the exception was not catched inside the
					# module, it should even not be available, because
					# check() will re-fail if nothing is done.
					module.available = False
					#del self[module.name]
					#del module

			del to_disable

		logging.info(_(u'{0}: global check finished.').format(
												self.pretty_name))
		assert ltrace_func(self._trace_name, True)
	def guess_one(self, module_name):
		try:
			return self[module_name]

		except KeyError:
			raise exceptions.DoesntExistException(_(u'{0} {1} does not exist '
				u'or is not enabled.').format(self.module_type, module_name))
	def _inotifier_install_watches(self, inotifier):
		""" forward the inotifier call to our enabled modules, and to
			our available modules, too: a change in a configuration file
			could trigger a module auto-enable or auto-disable (this seems
			dangerous, but so sexy that i'll try). """

		for module in self:
			if hasattr(module, '_inotifier_install_watches'):
				try:
					module._inotifier_install_watches(inotifier)

				except Exception, e:
					logging.warning(_(u'{name}: problem '
						'while installing inotifier watches for {type} '
						'{module} (was: {exc}).').format(
							name=self.pretty_name,
							type=self.module_type,
							module=module.name, exc=e))
class CoreModule(CoreUnitObject, NamedObject):
	""" CoreModule is the base class for backends and extensions. It provides
		the :meth:`generate_exception` method, called by controllers when a
		high-level problem occurs (for example, a conflict between
		duplicate-data coming from different backends; this is the typical
		problem a backend can't detect).

		A module class defines these class attributes:

		* modules_depends: a list of modules **instance names** (not class)
		  which must be available before the current one gets enabled.
		* modules_conflicts: other modules **instance names** which conflict
		  with the current one.

		It must also define these instance attributes:

		* controllers_compat: a list of controller names which will get data
		  (methods or contents) from the current module.

		.. note:: [**work in progress**] if :attr:`self.controllers_compat`
			contains ``system`` (name
			of :class:`~licorn.core.system.SystemController` global instance),
			the current class must implement the special :meth:`system_load`
			method. This method will be called *after* module load and *after*
			:class:`~licorn.core.system.SystemController` instanciation, to
			reconnect the module data to its controller.

			This is mainly because extensions are loaded after the
			:class:`~licorn.core.system.SystemController` instanciation in
			``LMC``, and we currently can't do it differently, ``system`` needs
			to be up very early in the inter-daemon connection process.

		.. versionadded:: 1.2

	"""

	_id_field = 'name'
	_lpickle_ = {
		'to_drop': [
				'threads', 'locks', 'events'
			]
		}

	def __init__(self, *args, **kwargs):

		# arguments conversion for CoreUnitObject.__init__()
		kwargs['controller'] = kwargs.pop('manager')

		super(CoreModule, self).__init__(*args, **kwargs)

		assert ltrace_func(TRACE_OBJECTS)

		if __debug__:
			self._trace_name = globals()['TRACE_' + self.name.upper()]

		# abstract defaults

		#: FIXME: better comment
		self.available = False

		#: FIXME: better comment
		self.enabled = False

		#: FIXME: better comment
		self.controllers_compat = kwargs.pop('controllers_compat', [])

		#: Filenames of useful files, stored as strings.
		self.paths         = LicornConfigObject()

		#: Internal configuration and data, loaded as objects.
		self.configuration = LicornConfigObject()
		self.data          = LicornConfigObject()

		#: Threads that will be collected by daemon to be started/stopped.
		self.threads = MixedDictObject(name='module_threads')

		#: A collection of :class:`Event` used to synchronize my threads.
		self.events = MixedDictObject(name='module_events')

		#: a collection of RLocks for multi-thread safety.
		self.locks = MixedDictObject(name='module_locks')

		#: a global, kind of "master" lock.
		self.locks._global = RLock()

		#: A list of compatible modules. See :ref:`modules` for details
		self.peer_compat = []

		#: indicates that this module is meant to be used on server only (not
		#: replicated / configured on CLIENTS).
		self.server_only = False
	def event(self, event_name):
		assert ltrace_locks(self.events[event_name])
		return self.events[event_name].is_set()
	def lock(self, lock_name):
		the_lock = self.locks[lock_name]
		if the_lock.acquire(blocking=False):
			the_lock.release()
			return False
		return True
	def _cli_get_configuration(self):
		""" Return the configuration subset of us, ready to be displayed in CLI.
		"""

		paths = '\n'.join(_(u'{0}: {1}').format(key.rjust(16), value)
							for key, value in self.paths.iteritems())

		if paths:
			extended_data = paths + '\n'

		else:
			extended_data = ''

		# TODO: more things to add into extended_data.

		return _(u'↳ {0} ({1} {2}):\n	{3}\n{4}').format(
						stylize(ST_ENABLED if self.enabled else ST_DISABLED,
														self.name),
						(u'server only') if self.server_only else _(u'client/server'),
						self.controller.module_type,
						_(u'depends on: {0}').format(', '.join(str(x) for x in self.module_depends))
							if hasattr(self, 'module_depends') else _(u'no dependancies'),
						extended_data
					)
	def __str__(self):
		return '<%s %s %s at 0x%x>' % (_('enabled') if self.enabled else _('disabled'),
			self.__class__.__name__, self.pretty_name, id(self))
	def generate_exception(self, extype, *args, **kwargs):
		""" Generic mechanism for :class:`Exception` dynamic generation.

			Every module (backend or extension) can implement only the
			exceptions it handles, by defining special methods whose names
			start with ``genex_``.

			:param extype: the type of the extension (most generally an
				Exception class name, passed as a string). This parameter will
				be used to resolve the wanted ``genex_extype()`` method, with
				Python's builtin function :func:`getattr` on :obj:`self`.

				The existence of the wanted ``genex_*`` method is checked only
				at debbuging time with :func:`assert`. At normal runtime, a non
				existing method will make the program crash. You're warned.
			:param args:
			:param kwargs: arguments that will be blindly passed to the
				``genex_*`` methods.
		"""

		assert ltrace_func(self._trace_name)

		# it's up to the developper to implement the right methods, don't
		# enclose the getattr() call in try .. except.
		assert hasattr(self, 'genex_' % extype)

		getattr(self, 'genex_' % extype)(*args, **kwargs)
	def is_enabled(self):
		""" In standard operations, this method checks if the module can be
			enabled (in particular conditions). but the abstract method of the
			base class just return :attr:`self.available`:

			* for modules which don't make a difference between available
			  and enabled, this is perfect.
			* for module which can enable/disable a system service (thus
			  inherit from :class:`~licorn.extensions.ServiceExtension`, they
			  must overload this method and provide the good implementation.

		"""
		assert ltrace(self._trace_name, '| is_enabled(%s)' % self.available)
		return self.available
	def enable(self):
		""" In this abstract method, just return ``False`` (an abstract module
			can't be enabled in any way).

			It's up to derivatives to overload this method to implement
			whatever they need.

			.. note:: your own module's :meth:`enable` method has to return
				``True`` if the enable process succeeds, otherwise ``False``.
		"""
		assert ltrace(self._trace_name, '| enable(False)')
		return False
	def disable(self):
		""" In this abstract method, just return ``True`` (an abstract module
			is always disabled).

			It's up to derivatives to overload this method to implement
			whatever they need.

			.. note:: your own module's :meth:`disable` method has to return
				``True`` if the disable process succeeds, otherwise ``False``.
		"""
		assert ltrace(self._trace_name, '| disable(True)')
		return True
	def initialize(self):
		""" For an abstract module, this method always return ``False``.
			For a standard module, it must return the attribute
			:attr:`self.available`, after having determined if the module
			**is** available or not.

			Conditions of availability vary from a module to another. Generally
			speaking, a service-helper module should gather its service main
			configuration file and main binary, to check if they are installed.

			* if not installed, just return :attr:`self.available` (it's
			  assigned ``False`` in :meth:`self.__init__` and if you didn't
			  change it, it's ready.
			* if installed, change :attr:`self.available` value to ``True`` and
			  return it, too.

			.. note:: For more specific details, see classes
				:class:`~licorn.extensions.LicornExtension` and derivatives, and
				:class:`~licorn.core.backends.CoreBackend` and derivatives,
				because there are other things to take in consideration when
				implementing *end-of-road* modules.

		"""

		assert ltrace(self._trace_name, '| initialize(%s)' % self.available)
		return self.available
	def check(self, batch=False, auto_answer=None):
		""" default check method. """
		assert ltrace_func(self._trace_name)

		_type = self.controller.module_type
		_dict = {
			_type        : self,
			'synchronous': True
			}

		LicornEvent('%s_%s_check_starts' % (_type, self.name), **_dict).emit()

		if hasattr(self, 'check_func'):
			checked = self.check_func(batch, auto_answer)
		else:
			checked = True

		LicornEvent('%s_%s_check_finished' % (_type, self.name), success=checked, **_dict).emit()
	def load_defaults(self):
		""" A real backend will setup its own needed attributes with values
		*strictly needed* to work. This is done in case these values are not
		present in configuration files.

		Any configuration file containing these values, will be loaded
		afterwards and will overwrite these attributes. """
		pass

__all__ = ('ModulesManager', 'CoreModule', )
