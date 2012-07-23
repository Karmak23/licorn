# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

fsapi - File System API

These functions interact with a posix compatible filesystem, to ease common
operations like finding files, recursively checking / changing permissions
and ACLs, making / removing symlinks, and so on.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import os, posix1e, time, shutil, errno, re, types
from stat import *

# ================================================= Licorn® foundations imports

# we need the getcwd() function from bootstrap. This is really an `fsapi`
# function, but `bootstrap` needs it first and can't import `fsapi` because
# it is... well... `bootstrap`.
from bootstrap import getcwd

from _settings import settings

import logging, exceptions, styles
import process, hlstr, cache

from base      import Enumeration
from ltrace    import *
from ltraces   import *
from styles    import *

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

from licorn.core import LMC

# =========================================================== Pseudo-constants

# On a Debian derivative, this should get `/usr/share/pyshared/licorn`
# In developper installation, this will get whatever like `~user/source/licorn`
# this is used in various places accross the code to symlink there.
licorn_python_path = os.path.dirname(os.path.dirname(
						os.path.realpath('/usr/sbin/licornd')))

# These are paths on wich everything fail. Don't know why.
special_invalid_paths = ('.gvfs', )

# ============================================================== FS API Classes

class FsapiObject(Enumeration):
	""" TODO. """
	def __init__(self, name=None, path=None, uid=-1, gid=-1,
		root_dir_perm=None, dirs_perm=None, files_perm=None, exclude=None,
		rule=None, system=False, content_acl=False, root_dir_acl=False,
		home=None, user_uid=-1, user_gid=-1, copy_from=None):

		super(FsapiObject, self).__init__(name=name, copy_from=copy_from)

		# This one is used only in core.classes.CoreFSController methods
		if home:
			self.home     = home
			self.user_uid = user_uid
			self.user_gid = user_gid
		# else:
		# do not define self.{home,user_uid,user_gid}

		# These other are used in fsapi.check*
		self.path           = path
		self.uid            = uid
		self.root_gid       = gid
		self.content_gid    = None
		self.root_dir_perm  = root_dir_perm
		self.dirs_perm      = dirs_perm
		self.files_perm     = files_perm
		self.rule           = rule
		self.system         = system
		self.content_acl    = content_acl
		self.root_dir_acl   = root_dir_acl
		self.already_loaded = False

		if exclude is None:
			self.exclude = set()

		else:
			self.exclude = set(exclude)
class ACLRule(Enumeration):
	""" Class representing a custom ACL rule for Licorn® check system.

		:param checked: boolean to indicate if the rule has already been
			checked.
		:param file_name: path of the file describing the rule.
		:param line_no: line number of the rule in the file.
		:param rule_text: string representing the rule.
		:param system_wide: boolean to know if it is a system rule or
			an user rule.
		:param base_dir: string representing the home dir of the object
			we are checking. Example: if we are checking
			/home/users/robin/file1, base_dir is /home/users/robin.
		:param uid: id of the owner of the dir/file that we are checking.

	"""
	separator = '	'
	invalid_dir_regex_text = r'^((~.\*|\$HOME.\*|\/|\*\/)|[^%s]*\/?\.\.\/)' % separator
	invalid_dir_regex = re.compile(invalid_dir_regex_text)

	@staticmethod
	def substitute_configuration_defaults(acl):
		""" return an acl (string) where parameters @acls or @default
			were used.

			:param acl: string to decode """
		#logging.notice(acl)

		def get_acl_part_from_object(object_name):
			if acl_tmp.find(':') != -1:
				temp_acl_part = acl_tmp[:acl_tmp.index('@')] + \
					eval('%s.%s' % (object_name, acl_tmp[
							acl_tmp.index('@')+1:acl_tmp.rfind(':')
							])) + acl_tmp[acl_tmp.rfind(':'):]
			else:
				temp_acl_part = eval('%s.%s' % (object_name, acl_tmp[1:]))

				if temp_acl_part is None:
					raise exceptions.LicornRuntimeException(
						"%s system entry '%s'" %
						(stylize(ST_BAD,"Invalid"),
						stylize(ST_NAME, acl_tmp)))

			return temp_acl_part

		splitted_acls = acl.split(',')
		acls=[]
		for acl_tmp in splitted_acls:
			try:
				if acl_tmp[acl_tmp.index('@'):12] == '@defaults.':

					# should get settings.defaults.*
					acls.append(get_acl_part_from_object('settings'))

				elif acl_tmp[acl_tmp.index('@'):6] == '@acls.' \
						or acl_tmp[acl_tmp.index('@'):7] == '@users.' \
						or acl_tmp[acl_tmp.index('@'):8] == '@groups.':

					# should get LMC.configuration.users/groups/acls}.*
					acls.append(get_acl_part_from_object('LMC.configuration'))

				else:
					acls.append(acl_tmp)

			except ValueError:
				acls.append(acl_tmp)
		return ','.join(acls)
	def __init__(self, controller, file_name=None, rule_text=None, line_no=0,
							base_dir=None, object_id=None, system_wide=True):

		name = self.generate_name(file_name, rule_text, system_wide, controller.name)

		super(ACLRule, self).__init__(name=name)

		assert ltrace_func(TRACE_CHECKS)

		self.checked     = False
		self.file_name   = file_name
		self.line_no     = line_no
		self.rule_text   = rule_text
		self.system_wide = system_wide
		self.base_dir    = base_dir
		self.uid         = object_id
		self.controller  = controller
	def generate_name(self, file_name, rule_text, system_wide, name):
		""" function that generate a name for a rule.
			Rule name is a keyword used to list rule into lists

			examples:

				- for default rules, return ~
				- for other rules following the synthax : DIR	ACL, return
					DIR

			:param filename: path of the file describing the rule
			:param rule_text: string representing the rule
			:param system_wide: boolean to know if it is a system rule or
				an user rule
		"""
		assert ltrace(TRACE_CHECKS, '''| generate_name(file_name=%s, '''
			'''rule_text=%s, system_wide=%s)''' % (
				file_name, rule_text, system_wide))

		if system_wide:
			if file_name.rsplit('/', 1)[1] == '%s.%s.conf' % (name,
				settings.defaults.check_homedir_filename):
				return '~'

		elif rule_text[0] in ('~', '$HOME'):
			return '~'

		return (hlstr.validate_name(
					self.substitute_configuration_defaults(
					rule_text.split(
					self.separator, 1)[0]), custom_keep='._')
					).replace('.', '_')
	def check_acl(self, acl):
		""" check if an acl is valid or not

			:param acl: string of the acl
		"""

		rebuilt_acl = []

		if acl.upper() in ['NOACL', 'RESTRICTED', 'POSIXONLY', 'RESTRICT',
			'PRIVATE']:
			return acl.upper()

		elif acl.find(':') == -1 and acl.find(',') == -1:
			raise exceptions.LicornSyntaxException(
						self.file_name, self.line_no, acl, desired_syntax=
							'NOACL, RESTRICTED, POSIXONLY, RESTRICT, PRIVATE')

		if acl.find('@') != -1:
			acl = self.substitute_configuration_defaults(acl)

		splitted_acls = []

		for acl_tmp in acl.split(','):
			splitted_acls.append(acl_tmp.split(':'))

		for splitted_acl in splitted_acls:
			if len(splitted_acl) == 3:
				bad_part = 0

				if not self.system_wide:
					if splitted_acl[1] in ('', settings.defaults.admin_group):
						bad_part = 2

					else:
						resolve_method = None

						if splitted_acl[0] in ('u', 'user'):
							resolve_method = LMC.users.guess_one

						elif splitted_acl[0] in ('g', 'group'):
							resolve_method = LMC.groups.guess_one

						if resolve_method:
							try:
								resolve_method(splitted_acl[1])

							except exceptions.DoesntExistException, e:
								raise exceptions.LicornACLSyntaxException(
											self.file_name,	self.line_no,
											text=':'.join(splitted_acl),
											text_part=splitted_acl[1],
											optional_exception=e)
						#FIXME:
						# else: what to do???
						# check if ('m', 'mask') else raise ?

					if splitted_acl[2] in ( '---', '-w-', '-wx' ):
						bad_part = 3

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
		""" check if the dir is ok

			:param directory: string of the directory we are checking
		"""

		# try to find insecure entries
		if self.invalid_dir_regex.search(directory):
			raise exceptions.LicornSyntaxException(self.file_name,
										self.line_no, text=directory,
										desired_syntax='NOT '
											+ self.invalid_dir_regex_text)

		if self.system_wide:
			uid = None

		else:
			if self.uid is -1:
				try:
					self.uid = os.lstat('%s/%s' % (
									self.base_dir, directory)).st_uid

				except (OSError, IOError), e:
					if e.errno == errno.ENOENT:
						raise exceptions.PathDoesntExistException(
							_(u'Ignoring unexisting entry "%s".') %
							stylize(ST_PATH, directory))
					else:
						raise e

			uid = self.uid

		directory = self.expand_tilde(directory, uid)

		if directory in ('', '/') or directory == self.base_dir:
			self.default = True

		else:
			self.default = False

		if self.system_wide:
			return self.substitute_configuration_defaults(directory)

		# if the directory exists in the user directory
		if os.path.exists('%s/%s' % (self.base_dir, directory)):
			return directory

		# implicit: else
		raise exceptions.PathDoesntExistException(
							_(u'Ignoring unexisting entry "%s".') %
								stylize(ST_PATH, directory))

	def check(self):
		""" general check function """

		line = self.rule_text.rstrip()

		try:
			dir, acl = line.split(self.separator)

		except ValueError:
			raise exceptions.LicornSyntaxException(self.file_name,
													self.line_no, text=line,
									desired_syntax='<dir><separator><acl>')

		dir = dir.strip()
		acl = acl.strip()

		self.dir = self.check_dir(directory=dir)
		self.acl = self.check_acl(acl=acl)

		self.checked = True
	def generate_dir_info(self, object_info, dir_info_base=None,
		system_wide=False, vars_to_replace=None):
		""" generate a FsapiObject from the rule. This object will be
			understandable by fsapi.check*()

			:param object_info: enumeration object containing home,
				uid and gid of the current file/dir checked
			:param dir_info_base: if specified, the dir_info_base will be
				modified, it may overwrite information of the dir_info_base.
			:param system_wide: boolean to know if it is a system rule or
				an user rule.
			:vars_to_replace: list of tuple to be replaced in the dir_info.
			"""

		acl = self.acl

		# if we are using a dir_info_base, we must be sure that permissions
		# will be ok.
		if dir_info_base is not None:
			if dir_info_base.rule.acl in ('NOACL', 'POSIXONLY'):
				# it is a NOACL perm on root_dir, the content could be
				# either RESTRICT or NOACL or a POSIX1E perm,
				# everything is possible.
				pass
			else:
				if ':' in dir_info_base.rule.acl:
					# if the root_dir is POSIX1E, either POSIX1E or RESTRICT
					# are allowed for the content.
					if acl in ('NOACL', 'POSIXONLY'):
						raise exceptions.LicornSyntaxException(
							self.file_name,
							self.line_no, text=acl,
							desired_syntax=_(u'Impossible to apply this '
								'perm or ACL.'))
				elif dir_info_base.rule.acl in (
									'PRIVATE', 'RESTRICT', 'RESTRICTED'):
					# if root_dir is RESTRICT, only RESTRICT could be set
					if ':' in acl or acl in ('NOACL', 'POSIXONLY'):
						raise exceptions.LicornSyntaxException(
							self.file_name,
							self.line_no, text=acl,
							desired_syntax=_(u'Impossible to apply this '
								'perm or ACL.'))
		if self.system_wide:
			dir_path = '%%s/%s' % self.dir if self.dir != '' else '%s'
			uid      = '%s'
			gid      = '%s'

		else:
			if self.dir in ('', '/'):
				dir_path = '%s%s' % (object_info.home, self.dir)

			else:
				dir_path = '%s/%s' % (object_info.home, self.dir)

			uid = object_info.user_uid
			gid = object_info.user_gid

		if dir_info_base is None:
			dir_info = FsapiObject(name=self.name, system=self.system_wide,
									path=dir_path, uid=uid, gid=gid,
									rule=self)
		else:
			# do not create a new dir_info, just modify the dir_info_base
			dir_info                = dir_info_base
			dir_info.content_gid    = gid
			dir_info.already_loaded = True

		if acl.upper() in ('NOACL', 'POSIXONLY'):

			if dir_info_base is None:
				dir_info.root_dir_perm = 00755

			dir_info.files_perm = 00644
			dir_info.dirs_perm = 00755

		elif acl.upper() in ('PRIVATE', 'RESTRICT', 'RESTRICTED'):

			if dir_info_base is None:
				dir_info.root_dir_perm = 00700

			dir_info.files_perm = 00600
			dir_info.dirs_perm = 00700

		elif self.system_wide and ':' in acl:

			if dir_info_base is None:
				dir_info.root_gid      = LMC.configuration.acls.gid
				dir_info.root_dir_perm = acl

			else:
				dir_info.content_gid = LMC.configuration.acls.gid

			dir_info.files_perm = acl
			dir_info.dirs_perm  = acl.replace('@UX','x').replace('@GX','x')

		elif not self.system_wide:
			# 3rd case: user sets a custom ACL on dir / file.
			# merge this custom ACL to the standard one (the
			# user cannot restrict ACLs, just add).

			if self.controller is LMC.users:
				acl_base = "%s,g:%s:rw-" % (
							LMC.configuration.acls.acl_base,
							settings.defaults.admin_group,
							)
				file_acl_base = "%s,g:%s:rw-" % (
							LMC.configuration.acls.file_acl_base,
							settings.defaults.admin_group
							)

			elif self.controller is LMC.groups:
				acl_base      = LMC.configuration.acls.group_acl_base
				file_acl_base = LMC.configuration.acls.group_file_acl_base


			if dir_info_base is None:
				dir_info.root_dir_perm = '%s,%s,%s' % (
										acl_base, acl,
										LMC.configuration.acls.acl_mask)
				dir_info.root_gid = LMC.configuration.acls.gid

			else:
				dir_info.content_gid = LMC.configuration.acls.gid

			dir_info.files_perm = '%s,%s,%s' % (
									acl_base, acl,
									LMC.configuration.acls.acl_mask)

			dir_info.dirs_perm = ('%s,%s,%s' % (
									file_acl_base,	acl,
									LMC.configuration.acls.file_acl_mask)
								).replace('@UX','x').replace('@GX','x')

		try:
			dir_info.content_acl = ':' in dir_info.files_perm

		except TypeError:
			dir_info.content_acl = False

		try:
			dir_info.root_dir_acl = ':' in dir_info.root_dir_perm

		except TypeError:
			dir_info.root_dir_acl = False

		# check the acl with the posix1e module.
		if not system_wide:
			if vars_to_replace is not None:
				for var, value in vars_to_replace:
					if dir_info.root_dir_acl:
						if var in dir_info.root_dir_perm:
							dir_info.root_dir_perm = \
								dir_info.root_dir_perm.replace(var, value)
					if dir_info.content_acl:
						if var in dir_info.dirs_perm:
							dir_info.dirs_perm = \
								dir_info.dirs_perm.replace(var, value)
						if var in dir_info.files_perm:
							dir_info.files_perm = \
								dir_info.files_perm.replace(var, value)

			if dir_info.root_dir_acl:
				# we replace the @*X to be able to posix1e.ACL.check() correctly
				# this forces us to put a false value in the ACL, so we copy it
				# [:] to keep the original in place.
				di_text = dir_info.root_dir_perm[:].replace(
					'@GX','x').replace('@UX','x')

				if posix1e.ACL(text=di_text).check():
					raise exceptions.LicornSyntaxException(
						self.file_name, self.line_no,
						text=acl,
						optional_exception=_(u'posix1e.ACL(text=%s)'
							'.check() call failed.') % di_text)

			if dir_info.content_acl:
				di_text = dir_info.dirs_perm[:].replace(
												'@GX','x').replace(
												'@UX','x')

				if posix1e.ACL(text=di_text).check():
					raise exceptions.LicornSyntaxException(
						self.file_name, self.line_no,
						text=acl,
						optional_exception=_(u'posix1e.ACL(text=%s)'
							'.check() call failed.') % dir_info.root_dir_perm)

		return dir_info
	def expand_tilde(self, text, object_id):
		""" replace '~' or '$HOME' by the path pointing to the object_id

			:param text: string to be modified
			:param object_id: id of the object we are checking (uid or gid)
		"""
		if object_id is None:
			home = ''

		else:
			if self.controller is LMC.groups:
				home = self.base_dir

			elif self.controller is LMC.users:
				home = LMC.users.by_uid(object_id).homeDirectory

			else:
				raise exceptions.LicornRuntimeError(_(u'Do not know how '
											u'to expand tildes for %s objects!')
												% self.controller._object_type)

		return text.replace(
				'~', home).replace(
				'$HOME', home).replace(
				home, '')

# ============================================================ FS API functions

def minifind(path, itype=None, perms=None, mindepth=0, maxdepth=99, exclude=[],
	followlinks=False, followmounts=True, yield_type=False):
	""" Mimic the GNU find behaviour in python. returns an iterator. """

	if mindepth > maxdepth:
		raise  exceptions.BadArgumentError(
			_(u'minifind: mindepth must be <= maxdepth.'))

	if maxdepth > 99:
		raise  exceptions.BadArgumentError(
			_(u'minifind: please do not try to exhaust maxdepth.'))

	assert ltrace_func(TRACE_FSAPI)

	paths_to_walk      = [ path ]
	next_paths_to_walk = []
	current_depth      = 0
	if itype is None:
		itype = (S_IFDIR, S_IFREG)

	while True:

		if paths_to_walk != []:
			entry = paths_to_walk.pop(0)

		elif next_paths_to_walk != []:
			paths_to_walk      = next_paths_to_walk
			next_paths_to_walk = []
			entry              = paths_to_walk.pop(0)
			current_depth     += 1

		else:
			break

		# remove path from entry to get where we are.
		current_path = entry[len(path+os.sep):]

		if followlinks:
			stat_func = os.stat
		else:
			stat_func = os.lstat

		try:
			entry_stat = stat_func(entry)
			entry_type = entry_stat.st_mode & 0170000
			entry_mode = entry_stat.st_mode & 07777

		except (IOError, OSError), e:
			if e.errno == errno.ENOENT or (e.errno == errno.EACCES
					and os.path.basename(entry) in special_invalid_paths):
				logging.warning2(_(u'fsapi.minifind(): error on {0}: {1}').format(
										stylize(ST_PATH, entry), e))
			else:
				raise e
		else:
			if (current_depth >= mindepth
					and entry_type in itype
					and (perms is None or entry_mode & perms)):
				#ltrace(TRACE_FSAPI, '  minifind(yield=%s)' % entry)

				if current_path not in exclude:
					if yield_type:
						yield (entry, entry_type)

					else:
						yield entry

			if (entry_type == S_IFLNK and not followlinks) \
				or (os.path.ismount(entry) and not followmounts):
				logging.progress(_(u'minifind(): skipping link or '
					u'mountpoint {0}.').format(stylize(ST_PATH, entry)))
				continue

			if entry_type == S_IFDIR and current_depth < maxdepth:
				try:
					for x in os.listdir(entry):
						if os.path.join(current_path, x) not in exclude:
							next_paths_to_walk.append(os.path.join(entry, x))

						else:
							assert ltrace(TRACE_FSAPI, '  minifind(excluded=%s)' % entry)

				except (IOError, OSError), e:
					if e.errno == errno.ENOENT:
						# happens on recursive delete() applyed on minifind()
						# results: the dir vanishes during the os.listdir().
						logging.warning2(_(u'fsapi.minifind(): error on {0}: {1}').format(stylize(ST_PATH, entry), e))

					else:
						raise e
	assert ltrace_func(TRACE_FSAPI, True)
def check_dirs_and_contents_perms_and_acls_new(dirs_infos, batch=False,
										auto_answer=None, full_display=True):
	""" General function to check file/directory. """

	assert ltrace_func(TRACE_FSAPI)

	conf_acls = LMC.configuration.acls
	conf_dflt = settings.defaults

	def check_one_dir_and_acl(dir_info, batch=batch, auto_answer=auto_answer,
													full_display=full_display):
		path = dir_info['path']

		# Does the file/dir exist ?
		try:
			# WARNING: do not use os.stat(), this could lead to checking
			# files out of scope, and can be considered as a security
			# vulnerability in some situations.
			entry_stat = os.lstat(path)

		except (IOError, OSError), e:
			if e.errno == errno.EACCES:
				raise exceptions.InsufficientPermissionsError(str(e))

			elif e.errno == errno.ENOENT:
				if batch or logging.ask_for_repair(_(u'Directory %s does not '
								u'exist. Create it?') % stylize(ST_PATH, path),
							auto_answer=auto_answer):

					# NOTE: don't yield path here, this would make the
					# INotifier related thing expect it, and ignore it. And
					# we need the event to propagate, to make the watch manager
					# auto_add the dir.
					#
					# yield path

					os.mkdir(path)

					# We need to re-stat because we use the stat result after
					# this point. NO `os.stat()`!!
					entry_stat = os.lstat(path)

					if full_display:
						logging.info(_(u'Created directory {0}.').format(
													stylize(ST_PATH, path)))
				else:
					# we cannot continue if dir does not exist.
					raise exceptions.LicornCheckError(_(u'Cannot continue '
						u'checks for directory {0} (was: {1}).').format(
							path, e))
			else:
				# FIXME: do more things to recover from more system errors…
				raise e

		mode = entry_stat.st_mode & 0170000

		# if it is a file
		if mode == S_IFREG:
			if full_display:
				logging.progress(_(u'Checking file %s…') % stylize(ST_PATH, path))

			for event in check_perms(file_type=S_IFREG, dir_info=dir_info,
						batch=batch, auto_answer=auto_answer,
						full_display=full_display):
				yield event

		# if it is a dir
		elif mode == S_IFDIR:
			if full_display:
				logging.progress(_(u'Checking directory %s…') %
										stylize(ST_PATH, path))

			# if the directory ends with '/' that mean that we will only
			# affect the content of the dir.
			# the dir itself will receive default licorn ACL rights (those
			# defined in the configuration)
			if dir_info.path[-1] == '/':
				dir_info_root = dir_info.copy()
				dir_info_root.root_dir_acl  = True
				dir_info_root.root_dir_perm = "%s,g:%s:rwx,%s" % (
										conf_acls.acl_base,
										conf_dflt.admin_group,
										conf_acls.acl_mask)
				dir_info_root.gid = conf_acls.gid

				# now that the "root dir" has its special treatment,
				# prepare dir_info for the rest (its contents)
				dir_info.path = dir_info.path[:-1]

			else:
				dir_info_root = dir_info

			if full_display:
				logging.progress(_(u'Checking {1} on {0}…').format(
						stylize(ST_PATH, path), _(u'ACLs')
							if dir_info.root_dir_acl else _(u'posix perms')))

			# deal with root dir
			for event in check_perms(is_root_dir=True, file_type=S_IFDIR,
							dir_info=dir_info_root, batch=batch,
							auto_answer=auto_answer, full_display=full_display):
				yield event

			if dir_info.files_perm != None or dir_info.dirs_perm != None:
				try:
					exclude_list = dir_info.exclude

				except AttributeError :
					exclude_list = []

			if dir_info.files_perm != None:
				if full_display:
					logging.progress(_(u'Checking {1} on {0} contents…').format(
							stylize(ST_PATH, path), _(u'ACLs')
								if dir_info.content_acl else _(u'posix perms')))

				if dir_info.dirs_perm != None:
					itype = (S_IFREG, S_IFDIR)

				else:
					itype = (S_IFREG, )

				for entry, etype in minifind(path, itype=itype,
									exclude=exclude_list, mindepth=1,
									yield_type=True):

						dir_info.path = entry
						for event in check_perms(file_type=etype,
												dir_info=dir_info,
												batch=batch,
												auto_answer=auto_answer,
												full_display=full_display):
							yield event

		else:
			logging.warning2(_(u'Not touching %s, it is not a file nor a '
														u'directory.') % path)

	# NOTE: below this point, every dir_info must be copy()ed, else next check
	# procedure will fail because we would have changed them in place.

	if dirs_infos != None:

		# first, check default rule, if it exists. /home/groups, /home/archives
		# and such kind of 'base paths' don't have any, and it is perfectly
		# normal... But home dirs and group shared dirs should have one.
		try:
			for event in check_one_dir_and_acl(dirs_infos._default.copy()):
				yield event

		except AttributeError:
			pass

		# check all specials_dirs, those who have custom rules.
		for dir_info in dirs_infos:
			for event in check_one_dir_and_acl(dir_info.copy()):
				yield event
	else:
		raise exceptions.BadArgumentError(
			_(u'You must pass something through dirs_infos to check!'))

	assert ltrace_func(TRACE_FSAPI, True)
check_full = check_dirs_and_contents_perms_and_acls_new
def check_utf8_filename(path, batch=False, auto_answer=None, full_display=True):
	try:
		# try to decode the filename to unicode. If this fails, we need
		# to rename the file to something better, else all logging() operation
		# will fail on this file.
		return u'%s' % path

	except UnicodeDecodeError:
		valid_name = path.decode('utf8', 'replace')

		if batch or logging.ask_for_repair(_(u'Invalid utf8 filename '
							u'"{0}". Rename it?').format(
								stylize(ST_PATH, valid_name)),
						auto_answer=auto_answer):

			splitted = os.path.splitext(valid_name)
			new_name = u'{0}{1}{2}'.format(splitted[0],
						_(u' (invalid utf8 filename)'), splitted[1])

			# Avoid overwriting an existing file.
			counter = 1
			while os.path.exists(new_name):
				new_name = u'{0}{1}{2}'.format(splitted[0],
						_(u' (invalid utf8 filename, copy #{0})').format(counter),
						 splitted[1])
				counter += 1

			os.rename(path, new_name)

			if full_display:
				logging.info(_(u'Renamed file {0} to {1}.').format(
									stylize(ST_PATH, valid_name),
									stylize(ST_PATH, new_name)))
			return new_name

		else:
			raise exceptions.LicornCheckError(_(u'File {0} has an invalid utf8 '
				u'filename, it must be renamed before beiing checked further.'))
def __raise_or_return(pretty_path, batch, auto_answer):
	""" Exceptions should not be re-raised in batch mode, or if the user
		wants to continue despite them.

		This is an helper function for `check_*()` ones.
	"""

	return not (batch or logging.ask_for_repair(_(u'Do you want to try to '
												u'continue checking {0} '
												u'despite of this '
												u'exception?').format(
													pretty_path),
													auto_answer=auto_answer))
def check_perms(dir_info, file_type=None, is_root_dir=False, check_symlinks=False,
					batch=False, auto_answer=None, full_display=True):
	""" Check if permissions and ACLs conforms on a file or directory.

		Many sub-operations in this function can fail and will produce
		exceptions. Eg. if an inotify event is catched on a transient file
		(just created, just deleted), an mkstemp() operation, etc.

		We try to be nice about it:

		- a deleted file (``ENOENT``) makes the function stop processing and return.
		- an unsupported operation (``EOPNOTSUPP``) on ACLs makes it display
		  a warning and continue processing non-ACL related operations.
		- any other error needs more background and maturity to be handled
		  properly (when possible). Currently, if the check is batched (``batch=True``),
		  the processing will continue, else the function will re-raise the
		  exception.
	"""

	assert ltrace_func(TRACE_FSAPI)

	pretty_name = stylize(ST_NAME, 'fsapi.check_perms()')

	if file_type == S_IFLNK and not check_symlinks:
		# This check is very important (see #835).
		logging.progress(_(u'{0}: check of symlink {1} skipped.').format(
							pretty_name, stylize(ST_PATH, dir_info.path)))
		return

	try:
		path = check_utf8_filename(dir_info.path, batch=batch,
											auto_answer=auto_answer,
											full_display=full_display)
	except (OSError, IOError), e:
		logging.exception(_(u': exception while checking '
						u'filename validity of {0}.'), (ST_PATH, dir_info.path))

		if e.errno == errno.ENOENT:
			return

		if __raise_or_return(path, batch, auto_answer):
			raise

	except exceptions.LicornCheckError:
		logging.exception(_(u'fsapi.check_perms(): Error while checking '
							u'filename validity of {0}, cannot continue.'),
								(ST_PATH, dir_info.path))

		if __raise_or_return(stylize(ST_PATH, path), batch, auto_answer):
			return

	pretty_path = stylize(ST_PATH, path)

	logging.progress(_(u'{0}: checking permissions on {1}…').format(
													pretty_name, pretty_path))

	# get the access_perm and the type of perm (POSIX1E or POSIX) that will be
	# applyed on path
	if file_type == S_IFDIR:
		if is_root_dir:
			access_perm = dir_info.root_dir_perm
			perm_acl    = dir_info.root_dir_acl

		else:
			access_perm = dir_info.dirs_perm
			perm_acl    = dir_info.content_acl

	else:
		access_perm = dir_info.files_perm
		perm_acl    = dir_info.content_acl

		# fix #545: NOACL should retain the exec bit on files
		# fix #748: RESTRICTED should honner the exec bit on files
		if not perm_acl and access_perm in (00644, 00640, 00600):

			try:
				perm = execbits2str(path, check_other=True)

			except (IOError, OSError), e:
				logging.exception(_(u'fsapi.check_perms(): exception while '
						u'`execbits2str()` on {0}.').format(pretty_path))

				if e.errno == errno.ENOENT:
					return

				if __raise_or_return(pretty_path, batch, auto_answer):
					raise

			if perm[0] == "x": # user
				access_perm += S_IXUSR

			if perm[1] == "x" and access_perm in (00644, 00640): # group
				access_perm += S_IXGRP

			if perm[2] == "x" and access_perm == 00644: # other
				access_perm += S_IXOTH

	# if we are going to set POSIX1E acls, check '@GX' or '@UX' vars
	if perm_acl:
		# FIXME : allow @X only.

		try:
			execperms = execbits2str(path)

		except (IOError, OSError), e:
			# this can fail if an inotify event is catched on a transient file
			# (just created, just deleted), like mkstemp() ones.
			logging.exception(_(u'fsapi.check_perms(): exception while '
						u'`execbits2str()` on {0}.').format(pretty_path))

			if e.errno == errno.ENOENT:
				return

			if __raise_or_return(pretty_path, batch, auto_answer):
				raise

		if '@GX' in access_perm or '@UX' in access_perm:
			access_perm = access_perm.replace(
							'@GX', execperms[1]).replace(
							'@UX', execperms[0])

		access_perm = posix1e.ACL(text='%s' % access_perm)

	if is_root_dir:
		gid = dir_info.root_gid

	elif dir_info.content_gid is not None:
		gid = dir_info.content_gid

	else:
		gid = dir_info.root_gid

	uid = dir_info.uid

	for event in check_uid_and_gid(path=path,
									uid=uid, gid=gid,
									batch=batch,
									full_display=full_display):
		yield event

	if full_display:
		logging.progress(_(u'Checking {0} of {1}…').format(
							_(u'posix.1e ACL')
								if perm_acl
								else _(u'posix permissions'),
							pretty_path))

	acls_supported = True

	if perm_acl:
		# apply posix1e access perm on the file/dir
		try:
			current_perm = posix1e.ACL(file=path)

		except (IOError, OSError), e:
			# this can fail if an inotify event is catched on a transient file
			# (just created, just deleted), like mkstemp() ones.
			logging.exception(_(u'Exception while getting the posix.1e ACL '
												u'of {0}'), (ST_PATH, path))

			if e.errno == errno.EOPNOTSUPP:
				acls_supported = False

			if e.errno == errno.ENOENT:
				return

			if __raise_or_return(pretty_path, batch, auto_answer):
				raise

		if acls_supported and current_perm != access_perm:

			if batch or logging.ask_for_repair(
							_(u'Invalid access ACL for {path} '
								u'(it is {current_acl} but '
								u'should be {access_acl}).').format(
								path=pretty_path,
								current_acl=stylize(ST_BAD,
											_(u'empty')
												if current_perm.to_any_text(
													separator=',',
													options=posix1e.TEXT_ABBREVIATE
													| posix1e.TEXT_SOME_EFFECTIVE) == ''
												else current_perm.to_any_text(
													separator=',',
													options=posix1e.TEXT_ABBREVIATE
													| posix1e.TEXT_SOME_EFFECTIVE)),
								access_acl=stylize(ST_ACL,
												access_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE))),
							auto_answer=auto_answer):

					try:
						# yield the applied event, to be catched in the
						# inotifier part of the core, who will build an
						# expected event from it.
						yield path

						# be sure to pass an str() to acl.applyto(), else it will
						# raise a TypeError if onpath is an unicode string…
						# (checked 2006 08 08 on Ubuntu Dapper)
						# TODO: recheck this, as we don't use any unicode strings
						# anywhere (or we are before the move to using them
						# everywhere).
						posix1e.ACL(acl=access_perm).applyto(str(path),
														posix1e.ACL_TYPE_ACCESS)

						if full_display:
							logging.info(
								_(u'Applyed access ACL '
								u'{access_acl} on {path}.').format(
									access_acl=stylize(ST_ACL,
												access_perm.to_any_text(
													separator=',',
													options=posix1e.TEXT_ABBREVIATE
													| posix1e.TEXT_SOME_EFFECTIVE)),
									path=pretty_path))
					except (IOError, OSError), e:
						logging.exception(_(u'fsapi.check_perms(): Exception '
											u'while setting a posix.1e ACL on {0}'),
											pretty_path)

						if e.errno == errno.ENOENT:
							return

						if __raise_or_return(pretty_path, batch, auto_answer):
							raise

			else:
				all_went_ok = False

		# if it is a directory, apply default ACLs
		if acls_supported and file_type == S_IFDIR:

			current_default_perm = posix1e.ACL(filedef=path)

			if dir_info.dirs_perm != None \
						and ':' in str(dir_info.dirs_perm):
				default_perm = dir_info.dirs_perm

			else:
				default_perm = dir_info.root_dir_perm

			default_perm = posix1e.ACL(text=default_perm)

			if current_default_perm != default_perm:

				if batch or logging.ask_for_repair(
							_(u'Invalid default ACL for {path} '
							u'(it is {current_acl} but '
							u'should be {access_acl}).').format(
								path=pretty_path,
								current_acl=stylize(ST_BAD,
									_(u'empty')
										if 	current_default_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE) == ''
										else current_default_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE)),
								access_acl=stylize(ST_ACL,
											default_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE))),
							auto_answer=auto_answer):

					try:
						# yield the applied event, to be catched in the
						# inotifier part of the core, who will build an
						# expected event from it.
						yield path

						# Don't remove str() (see above).
						default_perm.applyto(str(path),
												posix1e.ACL_TYPE_DEFAULT)

						if full_display:
							logging.info(
									_(u'Applyed default ACL {access_acl} '
									u'on {path}.').format(
										path=pretty_path,
										access_acl=stylize(ST_ACL,
											default_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE)
									)))
					except (IOError, OSError), e:
						logging.exception(_(u'fsapi.check_perms(): exception '
									u'while setting a default ACL on {0}'),
									(ST_PATH, path))

						if e.errno == errno.ENOENT:
							return

						if __raise_or_return(pretty_path, batch, auto_answer):
							raise

				else:
					all_went_ok = False
	else:
		# delete previous ACL perms in case of existance
		try:
			# `has_extended_acl()` complains if we pass it an unicode string.
			# It explicitly wants an str(). Here we go...
			extended_acl = has_extended_acl(str(path))

		except (IOError, OSError), e:
			logging.exception(_(u'Exception while looking for an ACL on {0}'), pretty_path)

			if e.errno == errno.EOPNOTSUPP:
				acls_supported = False

			if e.errno == errno.ENOENT:
				return

			if __raise_or_return(pretty_path, batch, auto_answer):
				raise

		except TypeError:
			logging.exception(_(u'Exception while looking for an ACL on {0}'), pretty_path)

			if __raise_or_return(pretty_path, batch, auto_answer):
				raise

		if acls_supported and extended_acl:
			# if an ACL is present, this could be what is borking the Unix mode.
			# an ACL is present if it has a mask, else it is just standard posix
			# perms expressed in the ACL grammar. No mask == Not an ACL.

			if batch or logging.ask_for_repair(
							_(u'An ACL is present on {path}, '
							u'but it should not.').format(
								path=pretty_path),
							auto_answer=auto_answer):

				try:
					# if it is a directory we need to delete DEFAULT ACLs too
					if file_type == S_IFDIR:

						# yield the applied event, to be catched in the
						# inotifier part of the core, who will build an
						# expected event from it.
						yield path

						posix1e.ACL(text='').applyto(str(path),
												posix1e.ACL_TYPE_DEFAULT)

						if full_display:
							logging.info(_(u'Deleted default ACL from '
								u'{0}.').format(pretty_path))

					# yield the applied event, to be catched in the
					# inotifier part of the core, who will build an
					# expected event from it.
					yield path

					# delete ACCESS ACLs if it is a file or a directory
					posix1e.ACL(text='').applyto(str(path),
												posix1e.ACL_TYPE_ACCESS)

					if full_display:
						logging.info(_(u'Deleted access ACL from '
							u'{0}.').format(pretty_path))

				except (IOError, OSError), e:
					logging.exception(_(u'Exception while deleting the '
								u'posix.1e ACL on {0}'), pretty_path)
					return

			else:
				all_went_ok = False

		try:
			# WARNING: do not use os.stat(), this could lead to check
			# files in unwanted places and can be considered as a
			# security vulnerability.
			pathstat     = os.lstat(path)
			current_perm = pathstat.st_mode & 07777

		except (IOError, OSError), e:
			logging.exception(_(u'Exception while trying to `stat()` {0}'), pretty_path)

			if e.errno == errno.ENOENT:
				return

			if __raise_or_return(pretty_path, batch, auto_answer):
				raise

		if current_perm != access_perm:

			if batch or logging.ask_for_repair(
							_(u'Invalid posix permissions for {path} '
							u'(it is {current_mode} but '
							u'should be {wanted_mode}).').format(
								path=stylize(ST_PATH, path),
								current_mode=stylize(ST_BAD,
									perms2str(current_perm)),
								wanted_mode=stylize(ST_ACL,
									perms2str(access_perm))),
							auto_answer=auto_answer):
					try:
						# yield the applied event, to be catched in the
						# inotifier part of the core, who will build an
						# expected event from it.
						yield path

						os.chmod(path, access_perm)

						if full_display:
							logging.info(_(u'Applyed posix permissions '
								u'{wanted_mode} on {path}.').format(
									wanted_mode=stylize(ST_ACL,
										perms2str(access_perm)),
									path=pretty_path))

					except (IOError, OSError), e:
						logging.exception(_(u'Exception while trying to change '
								u'posix permissions on {0}.'), pretty_path)

						if e.errno == errno.ENOENT:
							return

						if __raise_or_return(pretty_path, batch, auto_answer):
							raise

			else:
				all_went_ok = False

	assert ltrace_func(TRACE_FSAPI, True)
def check_uid_and_gid(path, uid=-1, gid=-1, batch=None, auto_answer=None,
														full_display=True):
	""" function that check the uid and gid of a file or a dir. """

	users  = LMC.users
	groups = LMC.groups

	pretty_path = stylize(ST_PATH, path)

	if full_display:
		logging.progress(_(u'Checking POSIX uid/gid/perms of %s.') %
													stylize(ST_PATH, path))
	try:
		# WARNING: do not use os.stat(), this could lead to checking
		# a completely different file/dir and can be considered as
		# a security vulnerability in some situations.
		pathstat = os.lstat(path)

	except (IOError, OSError), e:
			# causes of this error:
			#     - this is a race condition: the dir/file has been deleted
			#		between the minifind() and the check_*() call.
			#		Don't blow out on this.
			#     - when we explicitely want to check a path which does not
			#		exist because it has not been created yet (eg: ~/.dmrc
			#		on a brand new user account).
		logging.exception(_(u'Exception while trying to `stat()` {0}'), pretty_path)

		if e.errno == errno.ENOENT:
			return

		if __raise_or_return(pretty_path, batch, auto_answer):
			raise

	# if one or both of the uid or gid are empty, don't check it, use the
	# current one present in the file meta-data.
	if uid == -1:
		uid = pathstat.st_uid
		try:
			desired_login = users[uid].login

		except KeyError:
			desired_login = 'root'
			uid           = 0
	else:
		try:
			desired_login = users.uid_to_login(uid)

		except exceptions.DoesntExistException:
			desired_login = 'root'
			uid           = 0

	if gid == -1:
		gid = pathstat.st_gid
		try:
			desired_group = groups[gid].name

		except KeyError:
			desired_group = gid
	else:
		desired_group = groups.gid_to_name(gid)

	if pathstat.st_uid != uid or pathstat.st_gid != gid:

		if batch or logging.ask_for_repair(_(u'Invalid owership for {0}: '
						u'currently {1}:{2} but should be {3}:{4}. '
						u'Correct it?').format(
							pretty_path,
							stylize(ST_BAD, users[pathstat.st_uid].login
								if pathstat.st_uid in users.iterkeys()
								else str(pathstat.st_uid)),
							stylize(ST_BAD, groups[pathstat.st_gid].name
								if pathstat.st_uid in groups.iterkeys()
								else str(pathstat.st_gid)),
							stylize(ST_UGID, desired_login),
							stylize(ST_UGID, desired_group),
						),
						auto_answer=auto_answer):

			try:
				# yield the applied event, to be catched in the
				# inotifier part of the core, who will build an
				# expected event from it.
				yield path

				os.chown(path, uid, gid)

				if full_display:
					logging.info(_(u'Changed owner of {0} '
									u'to {1}:{2}.').format(
										stylize(ST_PATH, path),
										stylize(ST_UGID, desired_login),
										stylize(ST_UGID, desired_group)))

			except (IOError, OSError), e:
				if e.errno == errno.ENOENT:
					return

				if __raise_or_return(pretty_path, batch, auto_answer):
					raise
		else:
			logging.warning2(_(u'Invalid owership for {0}: '
						u'currently {1}:{2} but should be {3}:{4}.').format(
					pretty_path,
					stylize(ST_BAD, LMC.users[pathstat.st_uid].login
						if pathstat.st_uid in LMC.users.iterkeys()
						else str(pathstat.st_uid)),
					stylize(ST_BAD, LMC.groups[pathstat.st_gid].name
						if pathstat.st_uid in LMC.groups.iterkeys()
						else str(pathstat.st_gid)),
					stylize(ST_UGID, desired_login),
					stylize(ST_UGID, desired_group),
				))
def make_symlink(link_src, link_dst, batch=False, auto_answer=None):
	"""Try to make a symlink cleverly."""
	try:
		os.symlink(link_src, link_dst)
		logging.info(_(u'Created symlink {link}, pointing to {orig}.').format(
							link=stylize(ST_LINK, link_dst),
							orig=stylize(ST_PATH, link_src)))
	except OSError, e:
		if e.errno == 17:
			# 17 == file exists
			if os.path.islink(link_dst):
				try:
					read_link = os.path.abspath(os.readlink(link_dst))

					if read_link != link_src:
						if os.path.exists(read_link):
							if batch or logging.ask_for_repair(
											_(u'A symlink {link} '
											u'already exists, but points '
											u'to {dest}, instead of {good}. '
											u'Correct it?').format(
											link=stylize(ST_LINK, link_dst),
											dest=stylize(ST_PATH, read_link),
											good=stylize(ST_PATH, link_src)
										),
										auto_answer=auto_answer):

								os.unlink(link_dst)
								os.symlink(link_src, link_dst)

								logging.info(_(u'Overwritten symlink {link} '
										u'with destination {good} '
										u'instead of {dest}.').format(
										link=stylize(ST_LINK, link_dst),
										good=stylize(ST_PATH, link_src),
										dest=stylize(ST_PATH, read_link))
									)
							else:
								raise exceptions.LicornRuntimeException(
									_(u'Cannot create symlink {0} to {1}!').format(
										link_dst, link_src))
						else:
							# TODO: should we ask the question ? This isn't
							# really needed, as the link is broken.
							# Just replace it and don't bother the administrator.
							logging.info(_(u'Symlink {link} is currently '
									u'broken, pointing to non-existing '
									u'target {dest}); making it point '
									u'to {good}.').format(
										link=stylize(ST_LINK, link_dst),
										dest=stylize(ST_PATH, read_link),
										good=stylize(ST_PATH, link_src)
									)
								)
							os.unlink(link_dst)
							os.symlink(link_src, link_dst)

				except OSError, e:
					if e.errno == errno.ENOENT:
						# no such file or directory, link has disapeared…
						os.symlink(link_src, link_dst)
						logging.info(_(u'Repaired vanished symlink %s.') %
											stylize(ST_LINK, link_dst))
			else:
				if batch or logging.ask_for_repair(_(u'{link} already '
								u'exists but it is not a symlink, thus '
								u'it does not point to {dest}. '
								u'Rename and replace it with '
								u'a correct symlink?').format(
									link=stylize(ST_LINK, link_dst),
									dest=stylize(ST_PATH, link_src)
								),
								auto_answer=auto_answer):

					pathname, ext = os.path.splitext(link_dst)
					newname = _(u'{0} ({1} conflict){2}').format(pathname,
							time.strftime(_(u'%d %m %Y at %H:%M:%S')), ext)
					os.rename(link_dst, newname)
					os.symlink(link_src, link_dst)

					logging.info(_(u'Renamed {link} to {newname} '
							u'and replaced it by a symlink '
							u'pointing to {dest}.').format(
								link=stylize(ST_LINK, link_dst),
								newname=stylize(ST_PATH, newname),
								dest=stylize(ST_PATH, link_src)
							)
						)
				else:
					raise exceptions.LicornRuntimeException(_(u'While making '
								u'symlink to {dest}, the destination {link} '
								u'already exists and is not a link.').format(
									dest=link_src, link=link_dst))
def remove_directory(path):
	""" Remove a directory hierarchy. But first, rename it to something
		quite convoluted, in case the system (or administrator) wants to
		reuse the exact same name in the same place.

		.. warning:: TODO: the renaming part is left to be implemented.

		.. versionadded:: 1.3
	"""

	try:
		shutil.rmtree(path)
	except (IOError, OSError), e:
		if e.errno == errno.ENOENT:
			logging.info(_(u'Cannot remove %s, it does not exist!') %
													stylize(ST_PATH, path))
		else:
			raise e
def archive_directory(path, orig_name='unknown'):
	"""
		Archive a directory and all its contents in :file:`/home/archives`.

		.. warning:: this function needs `LMC.configuration` to be initialized
			before beiing called. This is a special case and will probably
			change in the near future.

		.. versionadded:: 1.3
	"""

	# /home/archives must be OK before moving
	LMC.configuration.check_base_dirs(minimal=True,	batch=True)

	archive_dir = "%s/%s.deleted.%s" % (
		settings.home_archive_dir, orig_name,
		time.strftime("%Y%m%d-%H%M%S", time.gmtime()))
	try:
		shutil.move(path, archive_dir)

		logging.info(_(u"Archived {0} as {1}.").format(stylize(ST_PATH, path),
												stylize(ST_PATH, archive_dir)))

		LMC.configuration.check_archive_dir(archive_dir, batch=True,
													full_display=__debug__)
	except (OSError, IOError), e:
		if e.errno == errno.ENOENT:
			logging.info(_(u'Cannot archive %s, it does not exist!') %
														stylize(ST_PATH, path))
		else:
			raise
def has_extended_acl(pathname):
	# return True if the posix1e representation of pathname's ACL has a MASK.
	for acl_entry in posix1e.ACL(file = pathname):
		if acl_entry.tag_type == posix1e.ACL_MASK:
			return True
	return False

# use pylibacl 0.4.0 accelerated C function if possible.
if hasattr(posix1e, 'HAS_EXTENDED_CHECK'):
	if posix1e.HAS_EXTENDED_CHECK:
		has_extended_acl = posix1e.has_extended

if hasattr(os, "chflags"):
	def has_flags(filename, flags):

		# Stay compatible with our shell implementation used
		# when `os.chflags()` does not exist.
		if type(flags) == types.ListType:
			nflags = 0
			for f in flags:
				nflags |= f
		# WARNING: no os.stat() here, we do not want to follow a symlink!!
		return os.lstat(filename).st_flags & nflags

else:
	# because of LP#969032, we must implement wheels, hands and foots...
	# lsattr /etc/squid3/squid.conf
	# ----i--------e- /etc/squid3/squid.conf
	# Then from e2progs/lib/e2p/pf.c :
	#~ static struct flags_name flags_array[] = {
			#~ { EXT2_SECRM_FL, "s", "Secure_Deletion" },
			#~ { EXT2_UNRM_FL, "u" , "Undelete" },
			#~ { EXT2_SYNC_FL, "S", "Synchronous_Updates" },
			#~ { EXT2_DIRSYNC_FL, "D", "Synchronous_Directory_Updates" },
			#~ { EXT2_IMMUTABLE_FL, "i", "Immutable" },
			#~ { EXT2_APPEND_FL, "a", "Append_Only" },
			#~ { EXT2_NODUMP_FL, "d", "No_Dump" },
			#~ { EXT2_NOATIME_FL, "A", "No_Atime" },
			#~ { EXT2_COMPR_FL, "c", "Compression_Requested" },
	#~ #ifdef ENABLE_COMPRESSION
			#~ { EXT2_COMPRBLK_FL, "B", "Compressed_File" },
			#~ { EXT2_DIRTY_FL, "Z", "Compressed_Dirty_File" },
			#~ { EXT2_NOCOMPR_FL, "X", "Compression_Raw_Access" },
			#~ { EXT2_ECOMPR_FL, "E", "Compression_Error" },
	#~ #endif
			#~ { EXT3_JOURNAL_DATA_FL, "j", "Journaled_Data" },
			#~ { EXT2_INDEX_FL, "I", "Indexed_directory" },
			#~ { EXT2_NOTAIL_FL, "t", "No_Tailmerging" },
			#~ { EXT2_TOPDIR_FL, "T", "Top_of_Directory_Hierarchies" },
			#~ { EXT4_EXTENTS_FL, "e", "Extents" },
			#~ { EXT4_HUGE_FILE_FL, "h", "Huge_file" },
			#~ { 0, NULL, NULL }
	#~ };


	# in the order they are encountered in the `lsattr` output.
	shellflags = {
		UF_IMMUTABLE: 'i',
		UF_APPEND: 'a',
		UF_NODUMP: '?',
		UF_OPAQUE: '?',
		SF_APPEND: 'a',
		SF_NOUNLINK: 'u',
		SF_ARCHIVED: '?',
		SF_IMMUTABLE: 'i',
		SF_SNAPSHOT: '?',
	}

	def has_flags(filename, flags):
		""" take a list of flags an return ``True`` if the file has all
			of them, else ``False``. """

		assert type(flags) == types.ListType

		out, err = process.execute(['lsattr', filename])
		outflags = out.strip().split(' ')[0].replace('-', '')
		for flag in flags:
			if shellflags[flag] not in outflags:
				return False
		return True

backup_ext = '.licorn.bak'
def clone_stat(src, dst, clone_owner=True, clone_group=True, clone_acl=False):
	""" Does the same job as :meth:`shutil.copystat`, but preserves owner,
		group and posix1e ACL if not told otherwise.

		.. versionadded:: 1.3

		.. note:: as of version 1.3, cloning ACL is not yet implemented because
			we don't need it.
	"""

	src_stat = os.lstat(src)
	src_mode = S_IMODE(src_stat.st_mode)

	if hasattr(os, 'utime'):
		os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

	if hasattr(os, 'chmod'):
		os.chmod(dst, src_mode)

	if hasattr(os, 'chflags') and hasattr(st, 'st_flags'):
		try:
			os.chflags(dst, src_stat.st_flags)

		except OSError, why:
			if (not hasattr(errno, 'EOPNOTSUPP') or
				why.errno != errno.EOPNOTSUPP):
				raise

	if clone_owner or clone_group:
		dst_stat = os.lstat(dst)
		os.chown(dst, src_stat.st_uid if clone_owner else dst_stat.st_uid,
					src_stat.st_gid if clone_group else dst_stat.st_gid)

	if clone_acl:
		logging.warning(_(u'Cloning ACLs is not yet implemented in fsapi.clone_stat(), sorry.'))
def backup_file(filename):
	""" Make a backup copy of a given file, with the extension :file:`.licorn.bak`.

		File contents are copied verbatim. Unix mode is preserved. ACLs are not
		guaranteed to be preserved because no particular operation is done
		on them.

		.. warning:: backup filename extension is currently fixed, without any
			timestamp. Thus, there can only be one backup at a time for a given
			file.
	"""
	backup_name = filename + backup_ext

	open(backup_name, 'wb').write(open(filename, 'rb').read())

	clone_stat(filename, backup_name)

	logging.progress(_(u'Backed up {orig} as {backup}.').format(
			orig=stylize(ST_PATH, filename),
			backup=stylize(ST_COMMENT, backup_name)))
def is_backup_file(filename):
	"""Return true if file is a backup file (~,.bak,…)."""
	if filename[-1] == '~':
		return True
	if filename[-4:] in ('.bak', '.old', '.swp'):
		return True
	return False
def get_file_encoding(filename):
	""" Try to find the encoding of a given file.
		(python's file.encoding is not very reliable, or I don't use use it like I should).

		TODO: use python mime module to do this ?
	"""

	# file -b: brief (the file name is not printed)
	encoding = process.execute(['file', '-b', filename])[0][:-1].split(' ')

	if encoding[0] == "ISO-8859":
		ret_encoding = "ISO-8859-15"
	elif encoding[0] == "UTF-8" and encoding[1] == "Unicode":
		ret_encoding = "UTF-8"
	elif encoding[0] == "Non-ISO" and encoding[1] == "extended-ASCII":
		# FIXME: find the correct encoding when a file comme from Windows ?
		ret_encoding = None
	else:
		ret_encoding = None

	return ret_encoding
def execbits2str(filename, check_other=False):
	"""Find if a file has executable bits and return (only) then as
		a list of strings, used later to build an ACL permission string.

		TODO: as these exec perms are used for ACLs only, should not
		we avoid testing setuid and setgid bits ? what does setguid
		means in a posix1e ACL ?
	"""

	# WARNING: no os.stat(); see elsewhere in this file for comment.
	fileperms = os.lstat(filename).st_mode & 07777
	execperms = []

	# exec bit for owner ?
	if fileperms & S_IXUSR:
		execperms.append('x')
	else:
		execperms.append('-')

	# exec bit for group ?
	if fileperms & S_IXGRP:
		execperms.append('x')
	else:
		execperms.append('-')

	if check_other:
		# exec bit for other ?
		if fileperms & S_IXOTH:
			execperms.append('x')
		else:
			execperms.append('-')

	return execperms
def perms2str(perms, acl_form = False):
	""" Convert an int mode to a readable string like "ls" does.  """

	string = ''

	# USER

	if acl_form:
		string += "user::"

	if perms & S_IRUSR:
		string += 'r'
	else:
		string += '-'

	if perms & S_IWUSR:
		string += 'w'
	else:
		string += '-'

	if perms & S_IXUSR:
		if perms & S_ISUID:
			string += 's'
		else:
			string += 'x'
	else:
		if perms & S_ISUID:
			string += 'S'
		else:
			string += '-'

	if acl_form:
		string += "\ngroup::"

	# GROUP

	if perms & S_IRGRP:
		string += 'r'
	else:
		string += '-'

	if perms & S_IWGRP:
		string += 'w'
	else:
		string += '-'

	if perms & S_IXGRP:
		if perms & S_ISGID:
			string += 's'
		else:
			string += 'x'
	else:
		if perms & S_ISGID:
			string += 'S'
		else:
			string += '-'

	if acl_form:
		string += "\nother::"

	# OTHER

	if perms & S_IROTH:
		string += 'r'
	else:
		string += '-'

	if perms & S_IWOTH:
		string += 'w'
	else:
		string += '-'

	if perms & S_IXOTH:
		if perms & S_ISVTX:
			string += 't'
		else:
			string += 'x'
	else:
		if perms & S_ISVTX:
			string += 'T'
		else:
			string += '-'

	if acl_form:
		string += "\n"

	return string
def touch(fname, times=None):
	""" this touch reimplementation comes from
	`http://stackoverflow.com/questions/1158076/implement-touch-using-python`_
	and I find it great.
	"""
	with file(fname, 'a'):
		os.utime(fname, times)
def remove_files(*args):
	""" Remove some files whose names are passed as string arguments, and
		raise exceptions only if the deletion failed for a real reason.

		Notably, failing to remove a file because it doesn't exist isn't a
		real reason, thus this error is muted and the operation continue
		as if there was no problem.
	"""

	for filename in args:
		try:
			os.unlink(filename)

		except (IOError, OSError), e:
			if e.errno != errno.ENOENT:
				raise
def check_file_path(filename, good_paths_list):
	""" Check that a file is in a path from a list of wanted "good" paths. The
		function does a ``realpath(abspath(…))`` before checking, to be sure
		we are not abused.

		it returns the normalized path if the check succeeds, else ``None``.

		Returning the normalized path avoids the need for the caller to
		re-operate the path resolution (`realpath` is an expensive syscall).
	"""

	_fname = os.path.realpath(os.path.abspath(filename))

	for good_path in good_paths_list:
		if _fname.startswith(good_path):
			return _fname

	return None
class BlockDeviceID(object):
	""" UUID="c2576193-0b70-497a-b998-870b6096b55d" TYPE="swap"  """
	__slots__ = ('name', 'uuid', 'type')
	def __init__(self, *args, **kwargs):
		attrs = kwargs.pop('from_line').split(' ')

		# remove ending ':'
		self.name = attrs[0][:-1]

		for attr in attrs[1:]:
			name, value = attr.split('=')

			# remove surrounding '"'
			setattr(self, name.lower(), value[1:-1])
def find_mount_point(origpath):
	while not os.path.ismount(origpath):
		origpath = os.path.dirname(origpath)
	return origpath
def remount(mount_point):
	""" Remount a given `mount_point` with ``-o remount``, generally to
		commit a change to :file:`/etc/fstab`.

		:param mount_point: a string, like '/' or '/home'. No checking is made
			at all about the mount point validity. It's up to you to find the
			right path with :func:`find_mount_point`.
	"""
	process.execute([ 'mount', '-o', 'remount', mount_point ])
	logging.notice(_(u'Remounted {0} to apply new mount options.').format(
					stylize(ST_PATH, mount_point)))
def check_needed_fstab_options(mount_point, mount_options):
	""" Check :file:`/etc/fstab` to see if the given mount_point has the wanted
		mount options or not.

		In case it doesn't, `fstab` will be edited and the options added,
		one by one. If it already has one or more, only the missing will
		be inserted.

		The function returns a list of really inserted options, or an empty
		list if no option was inserted.

		:param mount_point: a string, like '/' or '/home'.
		:param mount_options: an iterable containing strings like 'acl', 'rsize=8192'…

		.. note:: :file:`/etc/fstab` will be backed up with :func:`backup_file`
			before processing.
	"""
	altered = []

	fstab = open('/etc/fstab', 'r').read()

	# NOTE: don't add '^' nor '$' to a find/replace RE.
	replace_re = re.compile(r'''
						(
						[-_=\w/]+	# device, can be `/dev/…` or `UUID=…`
							\s+
						{0}			# {{mount_point}}
							\s+
						\w+			# fs type
							\s+
						)			# keep everything until now
						([-\w,=]+)	# keep current mount options separated
						(.*)		# and keep anything until end of line
						'''.format(mount_point), re.X)

	for mount_option in mount_options:
		if re.findall(r'\s+{0}\s+.*[^\w]{1}[^\w].*'.format(
				mount_point, mount_option), fstab) == []:
			fstab = replace_re.sub(r'\1\2,{0}\3'.format(mount_option), fstab)

			altered.append(mount_option)

	if altered:
		backup_file('/etc/fstab')

		with open('/etc/fstab', 'wb') as f:
			f.write(fstab)

		logging.notice(_(u'Added option(s) {0} to {1} permanently.').format(
							','.join(stylize(ST_ATTR, x) for x in altered),
							stylize(ST_PATH, mount_point)))

	return altered

@cache.cached(cache.half_a_day)
def blkid(partition=None, *args, **kwargs):
	"""	Return either the full :program:`blkid` output, converted to
		simple objects,

		Or return or just the line for the asked partition,
		as a simple object.

		:param partition: a string, containing something like ``sda1`` or
			``/dev/sda1``.
	"""
	result = process.execute([ 'blkid' ])[1].split('\n')
	blkids = []

	for res in result:
		bid = BlockDeviceID(from_line=res)
		if partition and bid.name.endswith(partition):
			return bid
		blkids.append(partition)

	return blkids


