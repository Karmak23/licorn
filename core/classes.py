# -*- coding: utf-8 -*-
"""
Licorn core objects

Basic objects used in all core controllers, backends, plugins.

:copyright:
	* 2010 Olivier Cortès <oc@meta-it.fr>
	* partial 2010 Robin Lucbernet <robinlucbernet@gmail.com>

:license: GNU GPL version 2

"""

import Pyro.core, re, glob, os,posix1e
from threading import RLock, current_thread
from traceback import print_exc
from licorn.foundations           import hlstr, exceptions, logging, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import licornd_roles
from licorn.foundations.base      import Enumeration, FsapiObject, \
											NamedObject, MixedDictObject, \
											ReverseMappingDict, \
											pyro_protected_attrs, \
											LicornConfigObject

from licorn.core import LMC

class LockedController(MixedDictObject, Pyro.core.ObjBase):
	""" Thread-safe object, protected by a global :class:`~threading.RLock`. This
		doesn't mean its internal unit-object are not locked or lockable.
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
			MixedDictObject._licorn_protected_attrs
			+ pyro_protected_attrs
			+ ['warnings']
		)
	def __init__(self, name, warnings=True):
		MixedDictObject.__init__(self, name)
		Pyro.core.ObjBase.__init__(self)
		assert ltrace('objects', '| LockedController.__init__(%s, %s)' % (
			name, warnings))

		self.warnings = warnings

		# Create lock holder objects for the current LockedController
		# and all CoreUnitObjects stored inside us. The giant_lock is hidden,
		# in case we iter*() the master lock object, for it to return only the
		# UnitObject locks.
		lock_manager = MixedDictObject(name + '_lock')
		lock_manager._giant_lock = RLock()
		setattr(LMC.locks, self.name, lock_manager)
	def __getitem__(self, key):
		""" From :class:`LockedController`: this is a classic
			:meth:`__getitem__` method, made thread-safe by encapsulating it
			with the Controller's global :class:`~threading.RLock`. """
		with self.lock():
			return MixedDictObject.__getitem__(self, key)
	def __setitem__(self, key, value):
		""" the classic :meth:`__setitem__` method, encapsulated withn the
			controller's global :class:`~threading.RLock` to be thread-safe. """
		with self.lock():
			MixedDictObject.__setitem__(self, key, value)
	def __delitem__(self, key):
		""" Delete data inside us, protected with our lock. """
		with self.lock():
			MixedDictObject.__delitem__(self, key)
	def acquire(self):
		""" acquire the controller global lock. """
		assert ltrace('thread', '%s: acquiring %s %s.' % (
			current_thread().name, self.name, self.lock()))
		self.lock().acquire()
	def lock(self):
		""" Return the controller global :class:`~threading.RLock`. This is a method,
			not an attribute because the lock must be looked up: it is not
			stored inside the controller but in the :class:`LockManager`.
		"""
		return getattr(getattr(LMC.locks, self.name), '_giant_lock')
	def release(self):
		""" release the controller global lock. """
		assert ltrace('thread', '%s: releasing %s %s.' % (
			current_thread().name, self.name, self.lock()))
		self.lock().release()
	def is_locked(self):
		""" Return True if current controller lock is acquired, else False.

			.. warning:: calling this :meth:`is_locked` method costs a few CPU
				cycles, because of the object lookup (see note above). Try to
				avoid using it as much as possible. """
		the_lock = self.lock()
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
	def __init__(self, name, warnings=True, reverse_mappings=[]):
		LockedController.__init__(self, name=name, warnings=warnings)

		assert ltrace('objects', '| CoreController.__init__(%s, %s)' % (
			name, warnings))

		#: Keeping the reverse mapping dicts in a container permits having
		#: more than one reverse mapping available for UnitObjects (kind of an
		#: internal index) and update them fast when an object is altered.
		#:
		#: The mapping construct permits having different mapping names instead
		#: of fixed ones (e.g. "login" for users, "name" for groups, "hostname"
		#: for machines...).
		self._reverse_mappings = MixedDictObject(
				self.name + '_reverse_mappings')
		for mapping_name in reverse_mappings:
			mapping = ReverseMappingDict()
			self.__setattr__('by_' + mapping_name, mapping)
			self._reverse_mappings[mapping_name] = mapping

		#: prefixed with '_', prefered backend attributes are automatically
		#: protected and stored out of the dict() part of self, thanks to
		#: MixedDictObject.
		self._prefered_backend_name = None
		self._prefered_backend_prio = -1

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

		assert ltrace(self.name, '| CoreController.reload()')

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
		assert ltrace(self.name, '| load_extensions()')
		for ext in self.extensions:
			getattr(ext, self.name + '_load')()
	def __setitem__(self, key, value):
		""" Add a new element inside us and update all reverse mappings. """
		assert ltrace(self.name, '| CoreController.__setitem__(%s, %s)' % (
			key, value))
		with self.lock():
			LockedController.__setitem__(self, key, value)
			for mapping_name, mapping_dict in self._reverse_mappings.items():
				assert ltrace(self.name,
					'| CoreController.__setitem__(reverse %s for %s)' % (
						mapping_name, getattr(value, mapping_name)))
				try:
					mapping_dict[getattr(value, mapping_name)] = value
				except TypeError:
					# probably 'unhashable type: 'list' TypeError'. Try to index
					# every entry (and pray for them to be globally unique...).
					for key in getattr(value, mapping_name):
						mapping_dict[key] = value
	def __delitem__(self, key):
		""" Delete data inside us, but remove reverse mappings first. """
		with self.lock():
			for mapping_name, mapping_dict in self._reverse_mappings.items():
				del mapping_dict[getattr(self[key], mapping_name)]
			LockedController.__delitem__(self, key)
	def exists(self, oid=None, **kwargs):
		""" Return True if a given :obj:`oid` exists as a primary key of a
			stored :class:`CoreUnitObject`, or if one of the :obj:`kwarg`
			keys exists as one of our reverse mappings keys pointing to an
			existing object.

			:param oid: an :class:`integer` (Object ID)
			:param kwargs: any positional argument refering to an existing
							reverse mapping in the current controller. For
							example, in
							:class:`~licorn.core.users.UsersController`, we can
							call :meth:`exists` with argument ``login='olive'``
							to find if a :class:`~licorn.core.users.User` whose
							`login` is `olive` exists or not.
			:returns: boolean ``True`` or ``False``
			:raise exceptions.BadArgumentError: if both :obj:`oid` and
												:obj:`kwargs` are empty,
												``None`` or ``False``.
		"""
		if oid:
			return oid in self
		if kwargs:
			for mapping_name, value in kwargs.items():
				if value in self._reverse_mappings[mapping_name]:
					return True
			return False
		raise exceptions.BadArgumentError(
			"You must specify an ID or a name to test existence of.")
	def guess_identifier(self, value):
		""" Try to guess a real ID of one of our :class:`CoreUnitObject`, from
			an unknown-typed information given as argument.

			:param value: can be an ID, a name, whatever reverse mapping key.
			"""
		if value in self:
			return value
		for mapping in self._reverse_mappings:
			try:
				return mapping[value]._oid
			except KeyError:
				continue
		raise exceptions.DoesntExistsException
	def guess_identifiers(self, value_list):
		""" Try to guess the type of any identifier given, find it in our
			objects IDs or reverse mappings, and return the ID (numeric) of the
			object found. """
		valid_ids=set()
		for value in value_list:
			try:
				valid_ids.add(self.guess_identifier(value))
			except exceptions.DoesntExistsException:
				logging.notice("Skipped non-existing object / ID '%s'." %
					stylize(ST_NAME, value))
		return valid_ids
	def dump(self):
		""" Dump the internal data structures (debug and development use). """

		assert ltrace(self.name, '| dump()')

		with self.lock():

			dicts_to_dump = [ (self.name, self) ] + [
				(mapping_name, mapping)
					for mapping_name, mapping
						in self._reverse_mappings.items() ]

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

		assert ltrace(self.name, '> find_prefered_backend(%s)' %
			self.backends)

		changed = False

		# remove an old backend name if the corresponding just got disabled.
		# else we don't change if the old had a better priority than the
		# remaining ones.
		if self._prefered_backend_name not in LMC.backends.keys():
			self._prefered_backend_name = None
			self._prefered_backend_prio = -1

		for backend in self.backends:
			if self._prefered_backend_name is None:
				assert ltrace(self.name, ' found first prefered_backend(%s)' %
					backend.name)
				self._prefered_backend_name = backend.name
				changed = True
				if hasattr(backend, 'priority'):
					self._prefered_backend_prio = backend.priority
				else:
					# my backends don't handle priory, I stop when I found
					# the first.
					break
			else:
				if hasattr(backend, 'priority'):
					if backend.priority > self._prefered_backend_prio:
						assert ltrace(self.name,
							' found better prefered_backend(%s)' % backend.name)
						self._prefered_backend_name = backend.name
						self._prefered_backend_prio = backend.priority
						changed = True
					else:
						assert ltrace(self.name,
							' discard lower prefered_backend(%s)' %
								backend.name)
						pass
				else:
					assert ltrace(self.name,
						' no priority mechanism, skipping backend %s' %
							backend.name)

		assert ltrace(self.name, '< find_prefered_backend(%s, %s)' % (
			self._prefered_backend_name, changed))
		return changed
	def run_hooks(self, hook, **kwargs):
		""" Transitionnal method to run callbacks at some extend. As of now, we
			iterate extensions and run the specified callbacks.

			.. warning:: In the near future, this method will not stay here and
				will not do exactly the same. Don't rely on it, the `hooks` API
				hasn't settled.

		"""

		meth_name = hook + '_callback'

		for ext in self.extensions:
			if hasattr(ext, meth_name):
				getattr(ext, meth_name)(**kwargs)
class CoreFSController(CoreController):
	""" FIXME: TO BE DOCUMENTED

		.. versionadded:: 1.3

	"""
	class ACLRule(Enumeration):
		""" Class representing a custom rule.
			# rule : Enumeration object representing a rule
			# 	rule.dir
			#	rule.acl
			#	rule.system = True if system rule else False
		"""
		separator = '	'
		invalid_dir_regex_text = r'^((~.\*|\$HOME.\*|\/|\*\/)|[^%s]*\/?\.\.\/)' % separator
		invalid_dir_regex = re.compile(invalid_dir_regex_text)

		@staticmethod
		def substitute_configuration_defaults(acl):
			""" return an acl (string) where parameters @acls or @default
				were used. """
			#logging.notice(acl)
			splitted_acls = acl.split(',')
			acls=[]
			for acl_tmp in splitted_acls:
				try:
					if acl_tmp[acl_tmp.index('@'):6] == '@acls.' \
							or acl_tmp[acl_tmp.index('@'):12] == '@defaults.' \
							or acl_tmp[acl_tmp.index('@'):7] == '@users.' \
							or acl_tmp[acl_tmp.index('@'):8] == '@groups.':
						if acl_tmp.find(':') != -1:
							temp = acl_tmp[:acl_tmp.index('@')] + \
								eval('LMC.configuration.%s' %
									acl_tmp[
										acl_tmp.index('@')+1:acl_tmp.rfind(':')
										]) + acl_tmp[acl_tmp.rfind(':'):]
						else:
							temp = eval('LMC.configuration.%s' % acl_tmp[1:])
							if temp is None:
								raise exceptions.LicornRuntimeException(
									"%s system entry '%s'" %
									(stylize(ST_BAD,"Invalid"),
									stylize(ST_NAME, acl_tmp)))
						acls.append(temp)
					else:
						acls.append(acl_tmp)
				except ValueError:
					acls.append(acl_tmp)
			return ','.join(acls)
		def __init__(self, file_name=None, rule_text=None, line_no=0,
			base_dir=None, uid=None, system_wide=True, controller=None):
			name = self.generate_name(file_name, rule_text, system_wide, controller)
			Enumeration.__init__(self, name)
			assert ltrace('checks', '| ACLRule.__init__(%s, %s)' % (
				name, system_wide))
			self.checked = False
			self.file_name = file_name
			self.line_no = line_no
			self.rule_text = rule_text
			self.system_wide = system_wide
			self.base_dir = base_dir
			self.uid = uid
		def generate_name(self, file_name, rule_text, system_wide, controller):
			""" for a system configuration file named
				/etc/licorn/check.d/users.dropbox.conf, return "dropbox"

				for a user config file named
				/home/users/guillaume/.licorn/check.conf, return "user_defined"
			"""
			if system_wide:
				if file_name.rsplit('/', 1)[1] == '%s.%s.conf' % (
					controller.name,
					LMC.configuration.defaults.check_homedir_filename):
					return '~'
				else:
					return (hlstr.validate_name(
						self.substitute_configuration_defaults(
						rule_text.split(
						self.separator, 1)[0]), custom_keep='._')
						).replace('.', '_')
			else:
				if rule_text == '~' or rule_text == '$HOME':
					return '~'
				else:
					return (hlstr.validate_name(
						self.substitute_configuration_defaults(
						rule_text.split(
						self.separator, 1)[0]), custom_keep='._')
						).replace('.', '_')
		def check_acl(self, acl, directory):
			""" check if an acl is valid or not """
			rebuilt_acl = []
			if acl.upper() in ['NOACL', 'RESTRICTED', 'POSIXONLY', 'RESTRICT',
				'PRIVATE']:
				return acl.upper()

			elif acl.find(':') == -1:
				raise exceptions.LicornSyntaxException(self.file_name,
					self.line_no, acl,
					desired_syntax='NOACL, RESTRICTED, POSIXONLY, RESTRICT'
					', PRIVATE')

			if acl.find('@') != -1:
				acl = self.substitute_configuration_defaults(acl)

			splitted_acls = []
			for acl_tmp in acl.split(','):
				splitted_acls.append(acl_tmp.split(':'))

			return_value = True

			for splitted_acl in splitted_acls:
				if len(splitted_acl) == 3:
					bad_part=0

					if not self.system_wide:
						if splitted_acl[1] in ['',
							LMC.configuration.defaults.admin_group]:
							bad_part=2

						else:
							must_resolve = False
							if splitted_acl[0] in ('u', 'user'):
								resolve_method = LMC.users.guess_identifier
								must_resolve = True
							elif splitted_acl[0] in ('g', 'group'):
								resolve_method = LMC.groups.guess_identifier
								must_resolve = True

							if must_resolve:
								try:
									id = resolve_method(splitted_acl[1])
								except exceptions.DoesntExistsException, e:
									raise exceptions.LicornACLSyntaxException(
										self.file_name,	self.line_no,
										text=':'.join(splitted_acl),
										text_part=splitted_acl[1],
										optional_exception=e)

						if splitted_acl[2] in [ '---', '-w-', '-wx' ]:
							bad_part=3

					if bad_part:
						raise exceptions.LicornACLSyntaxException(
							self.file_name,	self.line_no,
							text=':'.join(splitted_acl),
							text_part=splitted_acl[bad_part-1])

				else:
					if not self.system_wide:
						raise exceptions.LicornSyntaxException(self.file_name,
							self.line_no, text=':'.join(splitted_acl),
							desired_syntax='(u[user]|g[roup]|o[ther]):'
								'<login_or_group>:[r-][w-][x-]')

				splitted_acl[1] = self.substitute_configuration_defaults(
					splitted_acl[1])

				rebuilt_acl.append(':'.join(splitted_acl))

			return ','.join(rebuilt_acl)
		def check_dir(self, directory):
			""" check if the dir is ok """

			# try to find insecure entries
			if self.invalid_dir_regex.search(directory):
				raise exceptions.LicornSyntaxException(self.file_name,
					self.line_no, text=directory,
					desired_syntax='NOT ' + self.invalid_dir_regex_text)

			if self.system_wide:
				uid = None
			else:
				uid = self.uid
			directory = pyutils.expand_vars_and_tilde(directory, uid=uid)

			if directory in ('', '/') or directory == self.base_dir:
				self.default = True
			else:
				self.default = False
			if self.system_wide:
				return self.substitute_configuration_defaults(directory)

			# if the directory exists in the user directory
			if not os.path.exists('%s/%s' % (self.base_dir, directory)):
				raise exceptions.PathDoesntExistsException('''%s unexisting '''
					'''entry '%s' ''' %	(stylize(ST_BAD,"Ignoring"),
					stylize(ST_NAME, directory)))

			return directory
		def check(self):
			""" general check function """
			line=self.rule_text.rstrip()
			try:
				dir, acl = line.split(self.separator)
			except ValueError, e:
				logging.warning("%s->%s" % (line,e))
			dir = dir.strip()
			acl = acl.strip()

			self.dir = self.check_dir(directory=dir)
			self.acl = self.check_acl(acl=acl, directory=dir)

			self.checked = True
		def generate_dir_info(self, user_info=None, dir_info_base=None):
			""" generate a FsapiObject from the rule. This object will be
				understandable by fsapi """
			acl=self.acl

			if dir_info_base is not None:
				if dir_info_base.rule.acl in ('NOACL', 'POSIXONLY'):
					# it is a NOACL perm on root_dir, the content could be
					# either RESTRICT or NOACL or a POSIX1E perm, everything is possible
					pass
				else:
					if ':' in dir_info_base.rule.acl:
						# if the root_dir is POSIX1E, either POSIX1E or RESTRICT
						# are allowed for the content.
						if acl in ('NOACL', 'POSIXONLY'):
							raise exceptions.LicornSyntaxException(self.file_name,
								self.line_no, text=acl,
								desired_syntax=" impossible to apply this perm")
					elif dir_info_base.rule.acl in ('PRIVATE','RESTRICT','RESTRICTED'):
						# if root_dir is RESTRICT, only RESTRICT could be set
						if ':' in acl or acl in ('NOACL', 'POSIXONLY'):
							raise exceptions.LicornSyntaxException(self.file_name,
								self.line_no, text=acl,
								desired_syntax=" impossible to apply this perm")
			if self.system_wide:
				dir_path = '%%s%s' % "/" + self.dir if self.dir != '' else '%s'
				uidNumber = '%s'
				gidNumber = '%s'
			else:
				if self.dir in ("", "/"):
					dir_path = '%s%s' % (user_info.user_home, self.dir)
				else:
					dir_path = '%s/%s' % (user_info.user_home, self.dir)
				uidNumber = user_info.uidNumber
				gidNumber = user_info.gidNumber

			if dir_info_base is None:
				dir_info = FsapiObject(name=self.name)
				dir_info.system = self.system_wide
				dir_info.path = '%s' % dir_path
				dir_info.user = uidNumber
				dir_info.group = gidNumber
				dir_info.rule = self
			else:
				dir_info = dir_info_base.copy()

			if acl.upper() in ('NOACL', 'POSIXONLY'):
				if dir_info_base is None:
					dir_info.root_dir_perm = 00755
				dir_info.files_perm = 00644
				dir_info.dirs_perm = 00755
			elif acl.upper() in ('PRIVATE','RESTRICT','RESTRICTED'):
				if dir_info_base is None:
					dir_info.root_dir_perm = 00700
				dir_info.files_perm = 00600
				dir_info.dirs_perm = 00700
			elif self.system_wide and ':' in acl:
				if dir_info_base is None:
					dir_info.group = LMC.configuration.acls.group
					dir_info.root_dir_perm = acl
				dir_info.files_perm = acl
				dir_info.dirs_perm = acl.replace('@UX','x').replace('@GX','x')
			elif not self.system_wide:
				# 3rd case: user sets a custom ACL on dir / file.
				# merge this custom ACL to the standard one (the
				# user cannot restrict ACLs, just add).

				dir_info.group = LMC.configuration.acls.group
				if dir_info_base is None:
					dir_info.root_dir_perm = "%s,g:%s:r-x,%s,%s" % \
						(LMC.configuration.acls.acl_base,
						LMC.configuration.defaults.admin_group,
						acl,
						LMC.configuration.acls.acl_mask)
				dir_info.files_perm = "%s,g:%s:rwx,%s,%s" % \
					(LMC.configuration.acls.acl_base,
					LMC.configuration.defaults.admin_group,
					acl,
					LMC.configuration.acls.acl_mask)
				dir_info.dirs_perm = ("%s,g:%s:rw-,%s,%s" % \
					(LMC.configuration.acls.file_acl_base,
					LMC.configuration.defaults.admin_group,
					acl,
					LMC.configuration.acls.file_acl_mask)).replace(
						'@UX','x').replace('@GX','x')

			try:
				dir_info.content_acl = True if ':' in dir_info.files_perm else \
					False
			except TypeError:
				dir_info.content_acl = False
			try:
				dir_info.root_dir_acl = True if ':' in dir_info.root_dir_perm \
					else False
			except TypeError:
				dir_info.root_dir_acl = False

			# check the acl with the posix1e module.
			if dir_info.root_dir_acl:
				# we replace the @*X to be able to posix1e.ACL.check() correctly
				# this forces us to put a false value in the ACL, so we copy it
				# [:] to keep the original in place.
				di_text = dir_info.root_dir_perm[:].replace(
					'@GX','x').replace('@UX','x').replace('rsp-',
					'remotessh').replace('gst-', 'acl')
				if posix1e.ACL(text=di_text).check():
					raise exceptions.LicornSyntaxException(
						self.file_name, self.line_no,
						text=acl, optional_exception='''posix1e.ACL(text=%s)'''
						'''.check() fail''' % di_text)
			if dir_info.content_acl:
				if posix1e.ACL(text=dir_info.dirs_perm[:].replace(
					'@GX','x').replace('@UX','x').replace('rsp-',
					'remotessh').replace('gst-', 'acl')).check():
					raise exceptions.LicornSyntaxException(
						self.file_name, self.line_no,
						text=acl, optional_exception='''posix1e.ACL(text=%s)'''
						'''.check() fail''' % dir_info.root_dir_perm)

			return dir_info
	def __init__(self, name):
		CoreController.__init__(self, name)
		assert ltrace('checks', 'CoreFSController.__init__()')
		self.system_special_dirs_templates = Enumeration()
	def reload(self):
		""" reload the templates rules generated from systems rules. """
		assert ltrace('checks', '| LicornCoreFSController.reload(%s)' %
			LMC.configuration.check_config_dir + '/' + self.name + '.*.conf')

		CoreController.reload(self)

		for filename in glob.glob(
			LMC.configuration.check_config_dir + '/' + self.name + '.*.conf'):

			rules = self.parse_rules(rules_path=filename)
			assert ltrace('checks', '  EVAL rule %s' % rules.dump_status(True))
			if '_default' in rules.name:
				assert ltrace('checks', '  ADD rule %s (%s)' % (
					rules.dump_status(True), rules['~'].dump_status(True)))
				self.system_special_dirs_templates['~'] = rules['~']
			else:
				for acl_rule in rules:
					assert ltrace('checks', '  ADD rule %s' %
						acl_rule.dump_status(True))
					self.system_special_dirs_templates[acl_rule.name] = acl_rule
	def parse_rules(self, rules_path, user_info=None, system_wide=True):
		""" parse a rule from a line to a FsapiObject. """
		assert ltrace('checks', "> parse_rules(%s, %s, %s)" % (rules_path,
			user_info, system_wide))
		special_dirs = None
		if os.path.exists(rules_path):
			handler=open(rules_path,'r')
			rules = []
			special_dirs = Enumeration(name=rules_path)
			line_no = 0
			list_line = []
			for line in handler.readlines():
				line_no+=1
				list_line.append((line, line_no))

			list_line.sort()

			for line, line_no in list_line:
				if line[0] == '#':
					continue

				try:
					rule = self.ACLRule(file_name=rules_path, rule_text=line,
						line_no=line_no, system_wide=system_wide,
						base_dir=user_info.user_home
							if not system_wide else None,
						uid=user_info.uidNumber if not system_wide else None,
						controller=self)
					#logging.notice("rule = %s" % rule.dump_status(True))
				except exceptions.LicornRuntimeException, e:
					logging.warning2(e)
					continue

				try:
					rule.check()
					if system_wide:
						logging.progress('''%s %s template ACL rule: '%s' for '%s'.''' %
							(stylize(ST_OK,"Added"),
							self.name,
							stylize(ST_NAME, rule.acl),
							stylize(ST_NAME, rule.dir)))
				except exceptions.LicornSyntaxException, e:
					logging.warning(e)
					continue
				except exceptions.PathDoesntExistsException, e:
					logging.warning2(e)
					continue
				else:
					assert ltrace('checks', '  parse_rules(add rule %s)' %
						rule.dump_status(True))
					rules.append(rule)

			del line_no

			for rule in rules:
				try:
					if rule.name in special_dirs.keys():
						if rule.dir.endswith('/'):
							dir_info = rule.generate_dir_info(
								user_info=user_info,
								dir_info_base=dir_info)
					else:
						dir_info = rule.generate_dir_info(user_info=user_info)
				except exceptions.LicornSyntaxException, e:
					logging.warning(e)
					continue
				#logging.notice("dir_info = %s" % dir_info.dump_status(True))
				special_dirs.append(dir_info)

				assert ltrace('fsapi', '  parse_rules(add dir_info %s)' %
						dir_info.dump_status(True))

			handler.close()
		assert ltrace('checks', '< parse_rules(%s)' % special_dirs)

		if special_dirs == None:
			special_dirs = Enumeration()

		#logging.notice("special_dirs = %s" % special_dirs.dump_status(True))
		return special_dirs
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
			+ ['_available_modules', 'module_type', 'module_path',
				'module_sym_path']
		)
	def __init__(self, name, module_type, module_path, module_sym_path):
		LockedController.__init__(self, name)
		self._available_modules = MixedDictObject('<no_type_yet>')
		self.module_type = module_type
		self.module_path = module_path
		self.module_sym_path = module_sym_path
	def available(self):
		""" just a shortcut to get :attr:`self._available_modules`. When I
			type::

				LMC.extensions.available()
				# or
				LMC.backends.available()

			It just feels natural to me to get an interator over available
			modules. :attr:`self._available_modules` is currently a
			:class:`~licorn.foundations.base.MixedDictObject` and writing::

				for ext in LMC.extensions.available():
					# ext name is always accessible via ext.name
					...

			Just does what you expect it to do.

		"""
		return self._available_modules
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

		assert ltrace(self.name, '> load(type=%s, path=%s, server=%s)' % (
			self.module_type, self.module_path, server_side_modules))

		# We've got to check the server_side_modules argument too, because at
		# first load of client LMC (first pass), server modules are not known:
		# we must first start, then connect, then reload with server_modules
		# known.
		# Thus, if server_side_modules is None, we simulate a SERVER mode to
		# load everything possible. Superfluous modules will be disabled on
		# subsequent passes.
		if LMC.configuration.licornd.role == licornd_roles.CLIENT \
				and server_side_modules != None:
			is_client = True
		else:
			is_client = False

		module_classes_list = []

		for entry in os.listdir(self.module_path):

			if entry[0] == '_' or entry[-3:] != '.py' \
					or os.path.isdir(self.module_path + '/' + entry):
				continue

			# remove '.py'
			module_name = entry[:-3]

			class_name    = module_name.title() + self.module_type.title()
			try:
				python_module = __import__(self.module_sym_path + '.' + module_name,
												globals(), locals(), class_name)
				module_class  = getattr(python_module, class_name)
			except ImportError, e:
				logging.warning('{0} unusable {1} {2}: {3}. Traceback follows:'.format(
					stylize(ST_BAD, 'Skipped'), self.module_type,
					stylize(ST_NAME, module_name), stylize(ST_COMMENT, e)))
				print_exc()
				continue

			# VERY VERY basic dependancies resolver.
			# FIXME: please, stop joking and implement a real deps-resolver.
			if hasattr(module_class, 'module_depends'):
				module_classes_list.append((module_name, module_class))
			else:
				module_classes_list.insert(0, (module_name, module_class))

		assert ltrace(self.name, 'resolved dependancies module order: %s.' %
				', '.join([ str(klass) for klass in module_classes_list]))

		# dependancies are resolved, now instanciate in the good order:
		changed = False
		for (module_name, module_class) in module_classes_list:

			# Is module already loaded ?

			if module_name in self.keys():
				# module already loaded locally. Enventually sync with the
				# server, else just jump to next module.
				if is_client and module_name not in server_side_modules:
					self.disable_func(module_name)
					changed = True
				continue

			if module_name in self._available_modules.keys():
				# module already loaded locally, but only available. Eventually
				# sync if enabled on the server, else just jump to next module.
				if is_client and module_name in server_side_modules:
					self.enable_func(module_name)
					changed = True
				continue

			# module is not already loaded. Load and sync client/server

			assert ltrace(self.name, 'importing %s %s' % (self.module_type,
				stylize(ST_NAME, module_name)))

			# the module instance, at last!
			module = module_class()

			assert ltrace(self.name, 'imported %s %s, now loading.' % (
				self.module_type, stylize(ST_NAME, module_name)))

			if self.__not_manually_ignored(module.name):
				module.load(server_modules=server_side_modules)

				if module.available:
					if module.enabled:
						self[module.name] = module
						assert ltrace(self.name, 'loaded %s %s' % (
							self.module_type,
							stylize(ST_NAME, module.name)))

						if is_client and module_name not in server_side_modules:
							self.disable_func(module_name)
							changed = True

					else:
						self._available_modules[module.name] = module
						assert ltrace(self.name, '%s %s is only available'
							% (self.module_type,
								stylize(ST_NAME, module.name)))

						if is_client and module_name in server_side_modules:
							self.enable_func(module_name)
							changed = True
				else:
					assert ltrace(self.name, '%s %s NOT available' % (
						self.module_type, stylize(ST_NAME, module.name)))

					if is_client and module_name in server_side_modules:
						raise exceptions.LicornRuntimeError('%s %s is enabled '
							'on the server side but not available locally, '
							'there is probably an installation problem.' % (
								self.module_type, module_name))
			else:
				if is_client:
					if module_name in server_side_modules:
						raise exceptions.LicornRuntimeError('%s %s is enabled '
							'on the server side but manually ignored locally '
							'in %s, please fix the problem before continuing.'
								% (self.module_type, module_name,
									stylize(ST_PATH,
										LMC.configuration.main_config_file)))
				else:
					logging.info('%s %s %s, manually ignored in %s.' %
								(stylize(ST_DISABLED, 'Skipped'),
									self.module_type,
									stylize(ST_NAME, module.name),
									stylize(ST_PATH,
										LMC.configuration.main_config_file)))

		assert ltrace(self.name, '< load(%s)' % changed)
		return changed
	def __not_manually_ignored(self, module_name):
		""" See if module has been manually ignored in the main configuration
			file, and return the result as expected from the name of the method.
		"""

		# find the "extension" or "backend" node of LMC.configuration.
		if hasattr(LMC.configuration, self.name):
			conf = getattr(LMC.configuration, self.name)

			# Try the global ignore directive.
			if hasattr(conf, 'ignore'):
				assert ltrace(self.name, '| not_manually_ignored(%s) → %s '
					'(global)' % (module_name, (module_name
										not in getattr(conf, 'ignore'))))

				return module_name not in getattr(conf, 'ignore')

			# Else try the individual module ignore directive.
			if hasattr(conf, module_name):
				module_conf = getattr(conf, module_name)

				if hasattr(module_conf, 'ignore'):
					assert ltrace(self.name, '| not_manually_ignored(%s) → %s '
						'(individually)' % (module_name,
										getattr(module_conf, 'ignore')))

					return getattr(module_conf, 'ignore')

		# if no configuration directive is found, the module is considered
		# not ignored by default, it will be loaded.
		assert ltrace(self.name, '| not_manually_ignored(%s) → %s (no match)'
			% (module_name, True))
		return True
	def find_compatibles(self, controller):
		""" Return a list of modules (real instances, not just
			names) compatible with a given controller.

			:param controller: the controller for which we want to lookup
				compatible extensions, passed as intance reference (not just
				the name, please).
		"""

		assert ltrace(self.name, '| find_compatibles() %s for %s from %s → %s'
			% (stylize(ST_COMMENT, self.name),
				stylize(ST_NAME, controller.name),
					', '.join([x.name for x in self]),
					stylize(ST_ENABLED, ', '.join([module.name for module
						in self if controller.name in module.controllers_compat]
			))))

		return [ module for module in self \
				if controller.name in module.controllers_compat ]
	def enable_module(self, module_name):
		""" Try to **enable** a given module_name. What is exactly done is left
			to the module itself, because the current method will just call the
			:meth:`~licorn.core.classes.CoreModule.enable` method of the module.

		"""

		assert ltrace(self.name, '| enable_module(%s, active=%s, available=%s)'
			% (module_name, self.keys(), self._available_modules.keys()))

		with self.lock():
			if module_name in self.keys():
				logging.notice('%s %s already enabled.' % (module_name,
					self.module_type))
				return

			try:
				if self._available_modules[module_name].enable():
					module = self._available_modules[module_name]
					self[module_name] = module
					del self._available_modules[module_name]
					logging.notice('''successfully enabled %s %s.'''% (
						module_name, self.module_type))
			except KeyError:
				raise exceptions.DoesntExistsException('No %s by that name "%s", '
					'sorry.' % (self.module_type, module_name))
	# this will eventually be overwritten in subclasses.
	enable_func = enable_module
	def disable_module(self, module_name):
		""" Try to **disable** a given module. What is exactly done is left
			to the module itself, because the current method will just call the
			:meth:`~licorn.core.classes.CoreModule.disable` method of the module.

		"""

		assert ltrace(self.name, '| disable_module(%s, active=%s, available=%s)'
			% (module_name, self.keys(), self._available_modules.keys()))

		with self.lock():
			if module_name in self._available_modules.keys():
				logging.notice('%s %s already disabled.' % (module_name,
					self.module_type))
				return

			try:
				if self[module_name].disable():
					self._available_modules[module_name] = self[module_name]
					del self[module_name]

					logging.notice('''successfully disabled %s %s. ''' % (
						module_name, self.module_type))
			except KeyError:
				raise exceptions.DoesntExistsException('No %s by that name "%s", '
					'sorry.' % (self.module_type, module_name))
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

		assert ltrace(self.name, '> check(%s, %s)' % (batch, auto_answer))

		with self.lock():
			for module in self:
				assert ltrace(self.name, '  check(%s)' % module.name)
				module.check(batch=batch, auto_answer=auto_answer)

			# check the available_backends too. It's the only way to make sure they
			# can be fully usable before enabling them.
			for module in self._available_modules:
				assert ltrace(self.name, '  check(%s)' % module.name)
				module.check(batch=batch, auto_answer=auto_answer)

		assert ltrace(self.name, '< check()')
class CoreUnitObject(NamedObject):
	""" Common attributes for unit objects and
		:class:`modules <~licorn.core.classes.CoreModule>` in Licorn® core.

		This class defines the following attributes:

		.. attribute:: oid

			this attribute is the Licorn® object internal unique number (it's
			unique among all instances of a given class). If not given in
			:meth:`__init__`, it will be determined from next free
			oid stored in the :attr:`CoreUnitObject.counter` class attribute.

		.. attribute:: _controller

			a reference to the object's container (manager or controller). Must
			be passed as :meth:`__init__` argument, else the object won't be
			able to easily find it's parent when it needs it.

		.. warning:: every derivative class of this one should overload the
			:attr:`counter` class attribute with its own, to avoid oid
			confusion between classes.

		.. versionadded:: 1.3

	"""

	#: no need to add our _* attributes, because we don't inherit from
	#: :class:`~licorn.foundations.base.MixedDictObject`. This class attribute
	#: won't be used unless using
	#: :class:`~licorn.foundations.base.MixedDictObject` or one of its
	#: inherited classes.
	_licorn_protected_attrs = NamedObject._licorn_protected_attrs

	#: the static oid generation counter.
	counter = 0

	def __init__(self, name=None, oid=None, controller=None):
		NamedObject.__init__(self, name)
		assert ltrace('objects',
			'| CoreUnitObject.__init__(%s, %s, %s)' % (
				name, oid, controller))

		#assert oid is not None
		assert controller is not None

		if oid:
			self._oid = oid
		else:
			self._oid = self.__class__.counter
			self.__class__.counter +=1

		# FIXME: find a way to store the reference to the controller, not only
		# its name. This will annoy Pyro which cannot pickle weakproxy objects,
		# but will be cleaner than lookup the object by its name...
		self._controller = controller
class CoreModule(CoreUnitObject):
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

		.. versionadded:: 1.3

	"""
	_licorn_protected_attrs = CoreUnitObject._licorn_protected_attrs
	def __init__(self, name='core_module', manager=None,
		controllers_compat=[]):
		CoreUnitObject.__init__(self, name=name, controller=manager)
		assert ltrace(self.name, '| CoreModule.__init__(controllers_compat=%s)'
			% controllers_compat)

		# abstract defaults

		#: FIXME: better comment
		self.available = False

		#: FIXME: better comment
		self.enabled = False

		#: FIXME: better comment
		self.controllers_compat = controllers_compat

		#: Filenames of useful files, stored as strings.
		self.paths         = LicornConfigObject()

		#: Internal configuration and data, loaded as objects.
		self.configuration = LicornConfigObject()
		self.data          = LicornConfigObject()

		#: Threads that will be collected by daemon to be started/stopped.
		self.threads = MixedDictObject('module_threads')

		#: A collection of :class:`Event` used to synchronize my threads.
		self.events = MixedDictObject('module_events')


		#: A list of compatible modules. See :ref:`modules` for details
		self.peer_compat = []

		#: indicates that this module is meant to be used on server only (not
		#: replicated / configured on CLIENTS).
		self.server_only = False
	def _cli_get_configuration(self):
		""" Return the configuration subset of us, ready to be displayed in CLI.
		"""
		paths = '\n'.join('%s: %s' % (key.rjust(16), value)
							for key, value in self.paths.iteritems()),


		return u'↳ %s (%s %s):%s' % (
						stylize(ST_ENABLED if self.enabled else ST_DISABLED,
														self.name),
						'server only' if self.server_only else 'client/server',
						self._controller.module_type,
						'\n%s\n' % paths if paths != '' else ''
					)
	def __str__(self):
		data = ''
		for i in sorted(self.__dict__):
			if i[0:2] == '__' or i in ('enabled', 'available'):
				continue
			if isinstance(getattr(self, i), LicornConfigObject):
				data += u'%s\u21b3 %s:\n%s%s' % (
						'\t' * getattr(self, i)._level,
						i,
						'\t' * getattr(self, i)._level,
						str(getattr(self, i)))
			else:
				data += u"%s\u21b3 %s = %s\n" % ('\t', str(i), str(getattr(self, i)))
		return data
	def generate_exception(extype, *args, **kwargs):
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

		assert ltrace(self.name, '| CoreModule.generate_exception(%s,%s,%s)' % (
			extype, args, kwargs))

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
		assert ltrace(self.name, '| is_enabled(%s)' % self.available)
		return self.available
	def enable(self):
		""" In this abstract method, just return ``False`` (an abstract module
			can't be enabled in any way).

			It's up to derivatives to overload this method to implement
			whatever they need.

			.. note:: your own module's :meth:`enable` method has to return
				``True`` if the enable process succeeds, otherwise ``False``.
		"""
		assert ltrace(self.name, '| enable(False)')
		return False
	def disable(self):
		""" In this abstract method, just return ``True`` (an abstract module
			is always disabled).

			It's up to derivatives to overload this method to implement
			whatever they need.

			.. note:: your own module's :meth:`disable` method has to return
				``True`` if the disable process succeeds, otherwise ``False``.
		"""
		assert ltrace(self.name, '| disable(True)')
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

		assert ltrace(self.name, '| initialize(%s)' % self.available)
		return self.available
	def check(self, batch=False, auto_answer=None):
		""" default check method. """
		assert ltrace(self.name, '| ckeck(%s)' % batch)
		pass
	def load_defaults(self):
		""" A real backend will setup its own needed attributes with values
		*strictly needed* to work. This is done in case these values are not
		present in configuration files.

		Any configuration file containing these values, will be loaded
		afterwards and will overwrite these attributes. """
		pass
class CoreStoredObject(CoreUnitObject):
	""" Common attributes for stored objects (users, groups...). Add individual
		locking capability (better fine grained than global controller lock when
		possible), and the backend name of the current object storage. """

	# no need to add our _* attributes, because we don't inherit from
	# MixedDictObject. This Class attribute won't be used unless using
	# MixedDictObject or one of its inherited classes.
	_licorn_protected_attrs = CoreUnitObject._licorn_protected_attrs
	def __init__(self, name=None, oid=None, controller=None, backend=None):
		CoreUnitObject.__init__(self, name=name, oid=oid, controller=controller)
		assert ltrace('objects',
			'| CoreStoredObject.__init__(%s, %s, %s, %s)' % (
				name, oid, controller.name, backend.name))

		self._backend  = backend.name

		# store the lock outside of us, else Pyro can't pickle us.
		LMC.locks[self._controller.name][self._oid] = RLock()
	def lock(self):
		""" return our unit RLock(). """
		return LMC.locks[self._controller.name][self._oid]
