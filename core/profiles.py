# -*- coding: utf-8 -*-
"""
Licorn core: profiles - http://docs.licorn.org/core/profiles.html

Barely compatible with gnome-system-tools profiles

:copyright:
	* 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	* partial 2010 Robin Lucbernet <robinlocbernet@gmail.com>
	* partial 2006 Régis Cobrun <reg53fr@yahoo.fr>
:license: GNU GPL version 2
"""

import sys, gc, os, re, shutil, weakref

from contextlib  import nested
from operator    import attrgetter
from xml.dom     import minidom
from xml         import dom as xmldom
from xml.parsers import expat

from licorn.foundations           import exceptions, logging
from licorn.foundations           import fsapi, hlstr, readers, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, Enumeration
from licorn.foundations.constants import filters

from licorn.core         import LMC
from licorn.core.groups  import Group
from licorn.core.classes import CoreController, CoreStoredObject
from licorn.daemon       import priorities, roles


# the bakend is a fake one because we don't have backends for profiles
# yet. The Controller handles the dirty job directly. But the
# :class:`~licorn.core.classes.CoreStoredObject` adds locking and
# controller informations, so we use it to avoid duplicating the work.
profile_fake_backend = Enumeration('fake_backend')

class Profile(CoreStoredObject):
	""" A Licorn® profile.

		:param name: the profile name, as :class:`str`.
		:param description: the profile description, as :class:`str`.

		:param group: a Licorn® :class:`~licorn.core.groups.Group`, from which
			name and other attributes will be taken. used on Profile creation,
			after the loading phase, when all Licorn® objects and controllers
			are available. **This parameter takes precedence** over ``groupName``:
			if both are given, ``groupName`` is ignored.
		:param groupName: optional :class:`str`, used to find the ``group``.
			Used in loading phase, by the backends. **Ignored if ``group`` if
			also present.

		:param profileShell: The profile shell, as :class:`str`, assigned to
			new users created from this profile.
		:param profileSkel: the profile shell, as :class:`str`.
		:param profileQuota: the profile quota as :class:`int`, in megabytes.

		:param groups:
		:param memberGid: same principle as ``group`` and ``groupName``, but
			for profile groups.

		.. versionadded:: 1.2.5
	"""
	by_name  = {}
	by_group = {}

	def __init__(self, name,
				group=None, groupName=None,
				description=None,
				profileShell=None, profileSkel=None, profileQuota=None,
				# one of these two must be given, the first will be guessed
				# and constructed from the second.
				groups=None, memberGid=None, backend=None):

		if backend is None:
			backend = profile_fake_backend

		CoreStoredObject.__init__(self,	LMC.profiles, backend)

		self.__name         = name
		self.__description  = description
		self.__profileShell = profileShell
		self.__profileSkel  = profileSkel
		self.__profileQuota = profileQuota

		if group is None:
			group = LMC.groups.by_name(groupName)

		self.__group     = group.weakref
		self.__groupName = group.name
		self.__gidNumber = group.gidNumber

		# the group will verify the profile GID, which must be set before.
		group.profile = self

		del group

		# the profile reverse mappings, weak references to avoid keeping the
		# object alive on deletion.
		Profile.by_name[self.__name]       = self.weakref
		Profile.by_group[self.__groupName] = self.weakref

		if groups is None:
			self.__groups = []

			if memberGid is not None:
				for group_name in memberGid:
					try:
						group = LMC.groups.by_name(group_name)
					except KeyError:
						logging.warning(_(u'profile {0}: group {1} does not '
							'exist, ignored.').format(name, group_name))
						continue

					self.__groups.append(group.weakref)
					group.link_Profile(self)
		else:
			self.__groups = [ group.weakref for group in groups ]
	def __str__(self):
		return '%s(%s‣%s) = {\n\t%s\n\t}\n' % (
			self.__class__,
			stylize(ST_UGID, self.__gidNumber),
			stylize(ST_NAME, self.__name),
			'\n\t'.join('%s: %s' % (attr_name, getattr(self, attr_name))
					for attr_name in dir(self)
						if attr_name not in ('__group', 'primaryGroup', 'group'))
			)
	def __repr__(self):
		return '%s(%s‣%s)' % (
			self.__class__,
			stylize(ST_UGID, self.__gidNumber),
			stylize(ST_NAME, self.__name))
	def __del__(self):

		assert ltrace('gc', '| Profile %s.__del__()' % self.__name)

		del self.__group

		for group in self.__groups:
			try:
				group().unlink_Profile(self)
			except AttributeError:
				pass

		del self.__groups

		# avoid deleting references to other instances with the same name
		# (created on backend reloads).
		if Profile.by_name[self.__name] == self.weakref:
			del Profile.by_name[self.__name]

		if Profile.by_group[self.__groupName] == self.weakref:
			del Profile.by_group[self.__groupName]

	@property
	def name(self):
		return self.__name
	@name.setter
	def name(self, new_name):

		if new_name in (None, ''):
			raise exceptions.BadArgumentError(_(u'A profile cannot have an '
				'empty name!'))

		if not hlstr.cregex['group_name'].match(new_name):
			raise exceptions.BadArgumentError(_(u'Malformed profile name '
				'"{0}", must match /{1}/i.').format(new_name,
				stylize(ST_REGEX, hlstr.regex['group_name'])))

		with self.lock:

			# do the real operation
			old_name = self.__name
			self.__name = new_name

			# update the reverse mapping cache entry
			del Profile.by_name[old_name]
			Profile.by_name[new_name] = self

			self.serialize()

			logging.notice(_(u'Changed profile {0} name to {1}.').format(
					stylize(ST_NAME, old_name), stylize(ST_NAME, new_name)))
	@property
	def gidNumber(self):
		""" R/O property returning the profile GID, which is the exact same
		value as the profile group GID. """
		return self.__gidNumber
	@property
	def groupName(self):
		""" R/O attribute:  profile group name (the underlying system group
			associated with the profile). """
		return self.__groupName
	@property
	def description(self):
		""" The profile description. Whatever you want, as long as you want. """
		return self.__description
	@description.setter
	def description(self, description):

		if description is None:
			raise exceptions.BadArgumentError(_(u'You must specify a '
				'description (an empty text is OK, but not `None`).'))

		if not hlstr.cregex['description'].match(description):
			raise exceptions.BadArgumentError(_(u'Malformed profile '
				'description "{0}", must match /{1}/i.').format(
					description, hlstr.regex['description']))

		with self.lock:
			self.__description = description
			self.serialize()

		logging.info(_(u'Changed profile {0} description to "{1}".').format(
			stylize(ST_NAME, self.__name), stylize(ST_COMMENT, description)))
	@property
	def profileSkel(self):
		""" The profile skel, applyed to any new member, if no other skel takes
			precedence. The setter internally calls the :meth:`mod_profileSkel`
			method, which does many other things and has other arguments. """
		return self.__profileSkel
	@profileSkel.setter
	def profileSkel(self, profileSkel):
		return self.mod_profileSkel(profileSkel)
	@property
	def profileShell(self):
		""" The profile shell, applyed to any new member, if no other shell
			takes precedence. The setter internally calls the
			:meth:`mod_profileShell` method, which does many other things
			and has other arguments. """
		return self.__profileShell
	@profileShell.setter
	def profileShell(self, profileShell):
		return self.mod_profileShell(profileShell)
	@property
	def profileQuota(self):
		""" Profile quota (individual for users), in Mb.

			the setter calls :meth:`mod_profileQuota`.
		"""
		return self.__profileQuota
	@profileQuota.setter
	def profileQuota(self, profileQuota):
		return self.mod_profileQuota(profileQuota)
	@property
	def group(self):
		""" R/O property, returning the Licorn®
			:class:`~licorn.core.groups.Group` instance corresponding
			to the profile gidNumber. """

		# turn the weakref into an object before returning
		return self.__group()
	@property
	def groups(self):
		""" Read-only list of Licorn® groups, corresponding to the names found
			in the original :attr:`memberGid` (stored in profiles XML), and
			expanded to real groups at loading time.
		"""
		return [ group() for group in self.__groups ]
	@property
	def memberGid(self):
		""" Compatibility property (for backends, used at save time), that
			returns a generator of group names, taken from the property
			:attr:`groups`. """

		return (group().name for group in self.__groups)

	# comfort properties aliases
	quota        = profileQuota
	shell        = profileShell
	skel         = profileSkel
	gid          = gidNumber
	primaryGroup = group
	profileName  = name

	def serialize(self):
		""" This method will call the controller serialize() method to write
			all profiles to disk. This is not optimized at all, but not
			important at all, considered the use of profiles nowadays. """
		return self.controller.serialize()
	def mod_profileSkel(self, profileSkel, instant_apply=True, batch=False,
															auto_answer=None):
		""" Change the skel, and auto-apply if asked for (default is ``YES``).
		"""

		assert ltrace('profiles', '| mod_ProfileSkel(%s, %s)' % (
			self.__name, profileSkel))

		if profileSkel in (None, ''):
			raise exceptions.BadArgumentError(_(u'You must specify a valid '
				'skel dir for the profile (use --help to know how).'))

		if profileSkel not in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError(_(u' Invalid skeleton "{0}". Valid '
				'skels are {1}.').format(profileSkel,
					', '.join(LMC.configuration.users.skels)))

		with self.lock:
			self.__profileSkel = profileSkel
			self.serialize()

		logging.info(_(u'Changed profile {0} skeleton to {1}.').format(
			stylize(ST_NAME, self.__name), stylize(ST_COMMENT, profileSkel)))

		if instant_apply:
			logging.info(_(u'Applying new skel to current members %s in the '
				'background.') % ', '.join(stylize(ST_LOGIN, user.login)
											for user in self.__group().members))
			for user in self.__group().members:
				L_service_enqueue(priorities.NORMAL,
								user.apply_skel, profileSkel, batch=True)
	def mod_profileShell(self, profileShell=None, instant_apply=False,
											batch=False, auto_answer=None):
		""" Change the profile shell, and instant_apply if asked for
			(default is ``Yes``). """

		assert ltrace('profiles', '| mod_ProfileShell(%s, %s)' % (
			self.__name, profileShell))

		if profileShell in (None, ''):
			raise exceptions.BadArgumentError(_(u'You must specify a valid '
				'shell for the profile (use --help to know how).'))

		if profileShell not in LMC.configuration.users.shells:
			raise exceptions.BadArgumentError(_(u'Invalid shell "{0}". Allowed '
				'shells are {1}.').format(profileShell,
					', '.join(LMC.configuration.users.shells)))

		with self.lock:
			self.__profileShell = profileShell
			self.serialize()

		logging.info(_(u'Changed profile {0} shell to {1}.').format(
			stylize(ST_NAME, self.__name), stylize(ST_COMMENT, profileShell)))

		if instant_apply:
			for user in self.__group().members:
				user.loginShell = profileShell
	def mod_profileQuota(self, profileQuota=None, instant_apply=True,
											batch=False, auto_answer=None):
		""" Change the profile Quota, and instant_apply it to all current users.
		"""

		assert ltrace('profiles', '| mod_profileQuota(%s, %s)' % (
												self.__name, profileQuota))

		try:
			profileQuota = int(profileQuota)
		except:
			raise exceptions.BadArgumentError(_(u'You must specify a quota '
				'as integer, not "{}".').format(profileQuota))

		with self.lock:
			self.__profileQuota = profileQuota
			self.serialize()

		logging.info(_(u'Changed profile {0} quota to {1}Mb.').format(
			stylize(ST_NAME, self.__name), profileQuota))

		if instant_apply:
			# on self.group.members, batch=True
			print '>> please implement core.profiles.Profile.mod_profileQuota() instant_apply parameter.'

	def add_Groups(self, groups_to_add=None, instant_apply=True):
		""" Add groups in the groups list of the profile 'group'. """

		assert ltrace('profiles', '> %s.add_Groups(%s)' % (
												self.__name, groups_to_add))

		if groups_to_add is None:
			raise exceptions.BadArgumentError(_(u'You must specify a list of '
											'groups to add to the profile.'))

		with nested(self.lock, LMC.groups.lock):
			something_done = False

			for group in groups_to_add:

				if group.weakref in self.__groups:
					logging.info(_(u'Skipped group {0}, already in '
						'profile {1}.').format(stylize(ST_NAME, group.name),
							stylize(ST_NAME, self.__name)))

				elif group.weakref == self.__group:
					logging.warning(_(u'Cannot add group {0} to its own '
						'profile {1}.').format(stylize(ST_NAME, group.name),
							stylize(ST_NAME, self.__name)))

				else:
					self.__groups.append(group.weakref)
					group.link_Profile(self)
					something_done = True

					logging.info(_(u'Added group {0} to profile {1}.{2}').format(
							stylize(ST_NAME, group.name),
							stylize(ST_NAME, self.__name),
							stylize(ST_EMPTY,
							_(u' Applying to current members '
								'in the background.'))
									if instant_apply else ''))

					if instant_apply:
						L_service_enqueue(priorities.NORMAL,
									group.add_Users,
									self.group.gidMembers, batch=True)

			if something_done:
				self.serialize()
	def del_Groups(self, groups_to_del=None, instant_apply=True):
		""" Delete groups from the groups list of the profile 'group'. """

		assert ltrace('profiles', '> %s.del_Groups(%s)' % (
												self.__name, groups_to_del))

		if groups_to_del is None:
			raise exceptions.BadArgumentError(_(u'You must specify a list of '
										'groups to delete from the profile.'))

		with nested(self.lock, LMC.groups.lock):
			something_done = False

			for group in groups_to_del:

				if group.weakref in self.__groups:

					something_done = True
					group.unlink_Profile(self)
					self.__groups.remove(group.weakref)

					logging.notice(_(u'Deleted group {0} '
						'from profile {1}.{2}').format(
							stylize(ST_NAME, group.name),
							stylize(ST_NAME, self.__name),
							stylize(ST_EMPTY,
							_(u' Applying to current members '
								'in the background.'))
									if instant_apply else ''))

					if instant_apply:
						L_service_enqueue(priorities.NORMAL, group.del_Users,
										self.group.gidMembers, batch=True)
				else:
					logging.info(_(u'Skipped group {0}, not in groups of '
						'profile {1}.').format(
							stylize(ST_NAME, group.name),
							stylize(ST_NAME, self.__name)))

			if something_done:
				self.serialize()
	def apply_skel(self, users_to_mod=None, batch=False, auto_answer=None):
		""" Reapply the profile's skel to all members. """

		if users_to_mod is None:
			users_to_mod = self.group.primaryMembers

		for user in users_to_mod:
			if user.gidNumber != self.__gidNumber:
				logging.warning(_(u'Not applying skel {0} of {1} profile on '
					'account {2} because this account is not in this '
					'profile.').format(
						stylize(ST_PATH, self.__profileSkel),
						stylize(ST_NAME, self.__name),
						stylize(ST_LOGIN, user.login)))
				continue

			something_done = False

			logging.progress(_(u'Applying skel {0} to user {1}.').format(
				stylize(ST_PATH, user.profile.profileSkel),
				stylize(ST_NAME, user.login)))

			def install_to_user_homedir(entry, user_home=user.homeDirectory):
				""" Copy a file/dir/link passed as an argument to
					the user home_dir, after having verified it
					doesn't exist (else remove it after having
					asked it should)."""

				entry_name = os.path.basename(entry)

				logging.progress(_(u'Installing skel part %s.') %
												stylize(ST_PATH, entry))

				def copy_profile_entry():
					# FIXME: don't recursively copy directories, but merge them
					# if possible.
					if os.path.islink(entry):
						os.symlink(os.readlink(entry),
							'%s/%s' % (user_home, entry_name))
					elif os.path.isdir(entry):
						shutil.copytree(entry, '%s/%s'
							% (user_home, entry_name),
							symlinks=True)
					else:
						shutil.copy2(entry, user_home)

					logging.info('Copied skel part %s to %s.' % (
						stylize(ST_PATH, entry),
						stylize(ST_PATH, user_home)))

				dst_entry = '%s/%s' % (user_home, entry_name)

				if os.path.exists(dst_entry):
					warn_message = '''profile entry %s already '''\
						'''exists in %s's home dir (%s), it should '''\
						'''be overwritten to fully reapply the '''\
						'''profile. Overwrite ?''' % (
						stylize(ST_PATH, entry_name),
						stylize(ST_NAME, user.login),
						stylize(ST_PATH, user_home))

					if batch or logging.ask_for_repair(warn_message,
						auto_answer):
						if os.path.islink(dst_entry):
							os.unlink(dst_entry)
						elif os.path.isdir(dst_entry):
							shutil.rmtree(dst_entry)
						else:
							os.unlink(dst_entry)

						copy_profile_entry()
						return True
					else:
						logging.notice(
							"Skipped entry %s for user %s." % (
							stylize(ST_PATH,
								entry_name),
							stylize(ST_NAME, user.login)))
				else:
					copy_profile_entry()
					return True
				return False

			# mindepth=1 and maxdepth=2 are important, the former to avoid
			# transfering the skel dir in the user's home, the later to not
			# waste resources, as everything is recursively copied anyway.
			something_done = reduce(pyutils.keep_true,
				map(install_to_user_homedir, fsapi.minifind(
					path=self.__profileSkel, mindepth=1)))

			if something_done:
				L_service_enqueue(priorities.NORMAL, user.check, batch=True)

				logging.notice(_(u'Applyed skel {0} to user {1}, permissions '
					'are checked in the background.').format(
						stylize(ST_PATH, self.__profileSkel),
						stylize(ST_NAME, user.login)))
			else:
				logging.info(_(u'Skel {0} already applied or skipped '
					'for user {1}.').format(
						stylize(ST_PATH, self.__profileSkel),
						stylize(ST_NAME, user.login)))

	def _cli_get(self, selected=None):
		""" Export the user profiles list to human readable form. """
		with self.lock:
			return '%s\n%s' % (
				_(u'{name} ({group}, gid={gid}): {descr}').format(
					name=stylize(ST_NAME, self.__name),
					group=stylize(ST_NAME, self.__groupName),
					gid=stylize(ST_UGID, self.__gidNumber),
					descr=stylize(ST_COMMENT, self.__description)),
				_('	{home_label} {home}, {skel_label} {skel}, '
					'{shell_label} {shell}, {quota_label} {quota}{quota_unit}'
					'{groups}').format(
					home_label=stylize(ST_EMPTY, _(u'Home:')),
					home=stylize(ST_PATH, LMC.configuration.users.base_path),
					skel_label=stylize(ST_EMPTY, _(u'skeleton:')),
					skel=stylize(ST_PATH, self.__profileSkel),
					shell_label=stylize(ST_EMPTY, _(u'shell:')),
					shell=stylize(ST_PATH, self.__profileShell),
					quota_label=stylize(ST_EMPTY, _(u'quota:')),
					quota=self.__profileQuota,
					quota_unit=_(u'Mb'),
					groups=('\n	%s %s' % (
						stylize(ST_EMPTY, _(u'Groups:')),
						', '.join(group._cli_get_small()
							for group in sorted(self.groups,
								key=attrgetter('sortName')) if group)
						) if self.__groups != [] else '')
					))
			return data
	def to_XML(self, selected=None):
		""" Export the user profiles list to XML. """

		with self.lock:
			return '''	<profile>
		<name>%s</name>
		<groupName>%s</groupName>
		<gidNumber>%d</gidNumber>
		<description>%s</description>
		<profileHome>%s</profileHome>
		<profileQuota>%s</profileQuota>
		<profileSkel>%s</profileSkel>
		<profileShell>%s</profileShell>
		%s
	</profile>\n''' % (
				self.__name,
				self.__groupName,
				self.__gidNumber,
				self.__description,
				LMC.configuration.users.base_path,
				self.__profileQuota,
				self.__profileSkel,
				self.__profileShell,
				'<memberGid>%s</memberGid>' %
					'\n'.join((
						'			<groupName>%s</groupName>' % x().name
							for x in self.__groups))
						if len(self.__groups) > 0 else ''
				)

class ProfilesController(Singleton, CoreController):
	""" Controller and representation of /etc/licorn/profiles.xml, compatible
		with GNOME system tools (as much as possible but as of 20110211, the
		same XML file works for both of us).

		.. versionadded:: 1.2.5
	"""
	init_ok = False
	load_ok = False

	#: used in RWI.
	@property
	def object_type_str(self):
		return _(u'profile')
	@property
	def object_id_str(self):
		return _(u'PrID')
	@property
	def sort_key(self):
		return 'name'

	def __init__(self):
		""" Load profiles from system configuration file. """

		assert ltrace('profiles', '> ProfilesController.__init__(%s)' %
			ProfilesController.init_ok)

		if ProfilesController.init_ok:
			return

		CoreController.__init__(self, 'profiles')

		ProfilesController.init_ok = True
		assert ltrace('profiles', '< ProfilesController.__init__(%s)' %
			ProfilesController.init_ok)
	@property
	def names(self):
		return (name for name in Profile.by_name)
	def by_name(self, name):
		# turn the weakref into an object before returning
		return Profile.by_name[name]()
	@property
	def groups(self):
		return (group for group in Profile.by_group)
	def by_group(self, group):
		# turn the weakref into an object before returning
		return Profile.by_group[group]()
	def by_gid(self, gid):
		return self[gid]
	def load(self):

		if ProfilesController.load_ok:
			return

		assert ltrace('profiles', '| load()')

		# be sure our dependancies are OK.
		LMC.groups.load()

		self.reload()

		self.check_default_profile()

		ProfilesController.load_ok = True
	def reload(self):

		CoreController.reload(self)

		with self.lock:
			self.update(self.__fake_backend_load_Profiles())
	def check_default_profile(self):
		""" If no profile exists on the system, create a default one with
			system group "users". """

		try:
			with self.lock:
				if len(self) == 0:
					logging.warning(_(u'Adding a default {0} profile on the '
						'system (this is mandatory).').format(stylize(ST_NAME,
							_(u'Users'))))

					# Create a default profile with 'users' as default primary
					# group, and use the Debian pre-existing group without
					# complaining if it exists.

					self.add_Profile(name=_(u'Users'),
						# group must be a string.
						group=LMC.configuration.users.group,
						description=_(u'Standard desktop users'),
						profileShell=LMC.configuration.users.default_shell,
						profileSkel=LMC.configuration.users.default_skel,
						force_existing=True)
		except (OSError, IOError), e:
			# if 'permission denied', likely to be that we are not root. pass.
			if e.errno != 13:
				raise e
	def serialize(self):
		""" Write internal data into our file. """
		assert ltrace('profiles', '| serialize()')

		# FIXME: lock our datafile with a FileLock() ?
		with self.lock:
			open(LMC.configuration.profiles_config_file,
					'w').write(self.to_XML())
	def handle_config_changes(self):
		print '>> please implement ProfilesController.handle_config_changes()'
	def select(self, filter_string):
		""" Filter profiles on different criteria. """

		assert ltrace('profiles', '> Select(%s)' % filter_string)

		with self.lock:

			filtered_profiles = []

			if filters.NONE == filter_string:
				filtered_profiles = []

			elif type(filter_string) == type([]):
				filtered_profiles = filter_string

			elif filter_string & filters.ALL:
				# dummy filter, to permit same means of selection as in users/groups
				filtered_profiles.extend(self.itervalues())

			else:
				arg_re = re.compile("^profile=(?P<profile>.*)", re.UNICODE)
				arg = arg_re.match(filter_string)
				if arg is not None:
					profile = arg.group('profile')
					filtered_profiles.append(profile)

		assert ltrace('profiles', '< Select(%s)' % filtered_profiles)

		return filtered_profiles
	def _validate_fields(self, name, group, description, profileShell,
		profileSkel, profileQuota):

		if description in ('', None):
			description = _(u'The %s profile') % name

		if group is None:
			group = Group.make_name(name)

		if not profileShell in LMC.configuration.users.shells:
			raise exceptions.BadArgumentError(_(u'Invalid shell "{0}". '
				'Valid shells are {1}.').format(profileShell,
					', '.join(LMC.configuration.users.shells)))

		if not profileSkel in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError(_(u'Invalid skeleton "{0}". '
				'Valid skels are {1}.').format(profileSkel,
					', '.join(LMC.configuration.users.skels)))

		if not hlstr.cregex['profile_name'].match(name):
			raise exceptions.BadArgumentError(_(u'Malformed profile name '
				'"{0}", must match /{1}/i.').format(
					name, hlstr.regex['profile_name']))

		if not hlstr.cregex['group_name'].match(group):
			raise exceptions.BadArgumentError(_(u'Malformed profile group '
				'"{0}", must match /{1}/i.').format(
						group, hlstr.regex['group_name']))

		if not hlstr.cregex['description'].match(description):
			raise exceptions.BadArgumentError(_(u'Malformed profile '
				'description "{0}", must match /{1}/i.').format(
					description, hlstr.regex['description']))

		if profileQuota is None:
			profileQuota = 1024
		else:
			try:
				profileQuota = int(profileQuota)

				if profileQuota < 0:
					profileQuota = abs(profileQuota)
					logging.notice(_(u'Clamped negative quota value to '
						'absolute value {0}.').format(profileQuota))

				# don't put a 'elif', the absolute value could be more than max.
				if profileQuota > 1024*1024:
					profileQuota = 1024*1024
					logging.notice(_(u'Clamped quota to maximum '
						'value {0}Mb.').format(profileQuota))

			except ValueError:
				raise exceptions.BadArgumentError(_(u'Malformed profile '
					'quota "{0}": must be an integer, specifying a '
					'size in Mb.').format(profileQuota))

		return name, group, description, profileShell, profileSkel, profileQuota
	def add_Profile(self, name, group=None, profileQuota=None, groups=None,
		description=None, profileShell=None, profileSkel=None,
		force_existing=False):
		""" Add a user profile (LMC.groups is an instance of GroupsController
			and is needed to create the profile group). """

		assert ltrace('profiles', '''> AddProfile(%s): '''
			'''group=%s, profileQuota=%d, groups=%s, description=%s, '''
			'''profileShell=%s, profileSkel=%s, force_existing=%s''' % (
				stylize(ST_NAME, name), group,
				0 if profileQuota is None else profileQuota,
				groups, description, profileShell, profileSkel, force_existing))

		name, group, description, profileShell, profileSkel, profileQuota = \
			self._validate_fields(name, group, description, profileShell,
				profileSkel, profileQuota)

		if name in self.names:
			raise exceptions.AlreadyExistsException(_(u'A profile with name '
				'"%s" already exists on the system. Please choose another '
				'one.') % stylize(ST_NAME, name))

		# at this point, group is just a string
		if group in self.groups:
			raise exceptions.AlreadyExistsException(_(u'The group {0} is '
				'already taken by profile {1}. Please choose another '
				'one.').format(stylize(ST_NAME, group),
					stylize(ST_NAME, self.by_group(group).name)))

		with nested(self.lock, LMC.groups.lock):

			create_group = True

			if LMC.groups.exists(name=group):
				if force_existing:
					create_group = False
				else:
					raise exceptions.AlreadyExistsError(_(u'A system group '
						'named "%s" already exists. Please choose another '
						'group name for your profile, or use --force-existing '
						'to override and use it anyway (this is not '
						'recommended because the group will be deleted when '
						'you delete the profile).')	% group)

			# Add the system group
			if create_group:
				group = LMC.groups.add_Group(group, system=True,
									description=description,
									groupSkel=profileSkel,
									# force the profile group in shadow
									# backend, because profiles are
									# stored on file, anyway.
									backend=LMC.backends.guess_one('shadow'))
			else:
				group = LMC.groups.by_name(group)

				if group.is_standard:
					raise exceptions.BadArgumentError(_(u'The group {0} '
						'(gid={1}) is not a system group. It cannot be '
						'used as primary group for a profile. Please choose '
						'another one, or do not specify any, and a default '
						'one will be automatically created.').format(
						stylize(ST_NAME, group.name),
						stylize(ST_UGID, group.gidNumber)))

			# Add the profile in the list
			self[group.gid] = Profile(
									name=name,
									group=group,
									description=description,
									profileSkel=profileSkel,
									profileShell=profileShell,
									profileQuota=profileQuota,
									groups=groups)

			self.serialize()

		logging.notice(_(u'Added profile {0} (group={1}, gid={2}).').format(
			stylize(ST_NAME, name),
			stylize(ST_NAME, group.name),
			stylize(ST_UGID, group.gid)))
	def del_Profile(self, profile, del_users=False, no_archive=False, batch=False):
		""" Delete a user profile (LMC.groups is an instance of
			GroupsController and is needed to delete the profile group). """

		assert ltrace('profiles', '> del_Profile(%s)' % (profile.name))

		# we need to hold the users lock, in case we need to delete users.

		assert ltrace('locks', '  del_Profile locks: %s, %s, %s' % (self.lock, LMC.groups.lock, LMC.users.lock))

		with nested(self.lock, LMC.groups.lock, LMC.users.lock):

			# delete the reference in the controller.
			del self[profile.gid]

			# flush the controler data to disk.
			self.serialize()

			if profile.group.is_system_restricted:
				logging.info(_(u'Kept restricted system group %s.') %
															profile.groupName)
			else:
				try:
					LMC.groups.del_Group(profile.group, del_users=del_users,
						no_archive=no_archive, batch=batch,
						# this one is needed to avoid looping...
						check_profiles=False)
				except exceptions.DoesntExistException:
					logging.info('Group %s does not already exist, skipped.' %
															profile.groupName)

			name = profile.name

			assert ltrace('gc', '  profile ref count before del: %d %s' % (
				sys.getrefcount(profile), gc.get_referrers(profile)))
			# delete the hopefully last reference to the object. This will
			# delete it from the reverse mapping caches too.
			del profile

		# checkpoint, needed for multi-delete (users-groups-profile) operation,
		# to avoid collecting the deleted users at the end of the run, making
		# throw false-negative operation about non-existing groups.
		gc.collect()

		logging.notice(_(u'Deleted profile %s.') % stylize(ST_NAME, name))

		assert ltrace('locks', '  del_Profile locks: %s, %s, %s' % (self.lock, LMC.groups.lock, LMC.users.lock))
	def reapply_Profile(self, users_to_mod=None, apply_groups=False,
		apply_skel=False, batch=False, auto_answer=None):
		""" Reapply the profile of users.
			If apply_groups is True, each user will be put in groups listed
			in his profile. If apply_skel is True, the skel of each user will
			be copied as in user creation.

			NOT locked because we don't care if it fails during any file-system
			operations. This is harmless, besides a bunch or error messages in
			the daemon log.
		"""

		assert ltrace('profiles', '''> ReapplyProfilesOfUsers(users=%s, '''
			'''apply_groups=%s, apply_skel=%s)''' % (users, apply_groups,
				apply_skel))

		if apply_groups is False and apply_skel is False:
			raise exceptions.BadArgumentError(
				_(u'You must choose to apply the groups or/and the skel'))

		for user in users_to_mod:

			if user.is_system:
				logging.notice(_(u'Skipped system account %s (we do not '
					'reapply skels on them for safety reasons).')
											% stylize(ST_LOGIN, user.login))
				continue

			if user.profile is None:
				logging.notice(_(u'Skipped account %s, which has no profile.')
											% stylize(ST_LOGIN, user.login))
				continue

			if apply_groups:
				for group in user.profile.groups:
					group.add_Users([ user ], batch, auto_answer)

			if apply_skel:
				user.profile.apply_skel([ user ], batch, auto_answer)

		assert ltrace('profiles', '''< ReapplyProfilesOfUsers()''')
	def _cli_get(self, selected=None):
		""" Export the user profiles list to human readable form. """

		with self.lock:
			if selected is None:
				profiles = self.iterkeys()
			else:
				profiles = selected
			profiles.sort()

			assert ltrace('profiles', '| _get_cli(%s)' % profiles)

			return '%s\n' % '\n'.join(profile._cli_get()
					for profile in sorted(profiles, key=attrgetter('name')))
	def to_XML(self, selected=None):
		""" Export the user profiles list to XML. """

		with self.lock:
			if selected is None:
				profiles = self.values()
			else:
				profiles = selected

			assert ltrace('profiles', '| to_XML(%s)' % profiles)

			return '''<?xml version='1.0' encoding=\"UTF-8\"?>
<profiledb>
%s
</profiledb>
''' % ('\n'.join(profile.to_XML()
		for profile in sorted(profiles, key=attrgetter('name'))))
	# LOCKS: not locked besides this point, because we consider locking is done
	# in calling methods.
	def guess_one(self, value):
		""" Try to guess everything of a profile from a
			single and unknonw-typed info. """

		#assert ltrace('profiles', '| guess_identifier(%s)' % value)

		try:
			profile = self.by_group(value)
		except KeyError:
			try:
				profile = self.by_gid(int(value))
			except (ValueError, TypeError, KeyError):
				profile = self.by_name(value)

		return profile
	def exists(self, group=None, name=None):

		if group:
			return group in ProfilesController.groups
		if name:
			return name in ProfilesController.names

		raise exceptions.BadArgumentError(_(u'You must specify a groupname or '
			'a profile name to test existence of.'))
	def group_to_name(self, group):
		""" Return the group of the profile 'name'."""

		try:
			return self.by_group(group).name
		except KeyError:
			raise exceptions.DoesntExistException(_(u'Profile group %s does '
				'not exist.') % group)
	def name_to_group(self, name):
		""" Return the group **name** of the profile 'name'."""

		try:
			return self.by_name(name).groupName
		except KeyError:
			raise exceptions.DoesntExistException(_(u'Profile %s does '
				'not exist.') % name)
	def __fake_backend_load_Profiles(self):
		""" Read a user profiles file (XML format) and yield found profiles as
			tuples (group_name, Profile), to conform to other major core objects
			(users and groups).

			This function is sort of a micro-backend-loader for profiles, because
			as of now (20110211), profiles don't have backends, and they are
			likely not to have one someday, because I plan to obsolete them in
			favor of "groups of groups" and/or "extended groups"; but this could
			be subject to change.

			.. versionadded:: 1.2.5
				for the 1.2.5 rewrite (users/groups/profiles as objects), this
					function was rewritten to yield
					:class:`~licorn.core.profiles.Profile` instances instead of
					barely returning a dict.
		"""

		filename           = LMC.configuration.profiles_config_file
		empty_allowed_tags = ( 'description', )

		def get_profile_data(rootelement, leaftag, isoptional=False):
			""" Return a list of content of a leaftag (tag which has no child)
				which has rootelement as parent.
			"""
			data = []
			tags = rootelement.getElementsByTagName(leaftag)

			if tags == [] and rootelement.nodeName != 'memberGid':
				raise exceptions.CorruptFileError(reason=_(u'The tag <{0}> '
					'was not found in {1}.').format(leaftag, filename))

			for e in tags:
				for node in e.childNodes:
					if node.parentNode.parentNode == rootelement:
						# needed to ignore the other levels
						data.append(unicode(node.data))

			if data == []:
				if leaftag not in empty_allowed_tags \
								and rootelement.nodeName != 'memberGid':
					raise exceptions.CorruptFileError(reason=_(u'The tag '
						'<{0}> must not have an empty value (in {1}).').format(
							leaftag, filename))
				else:
					data = [ '' ]

			return data

		try:
			if os.lstat(filename).st_size == 0:
				return

			dom = minidom.parse(filename)

			for profile in dom.getElementsByTagName('profile'):

				name      = get_profile_data(profile, 'name').pop()
				comment   = get_profile_data(profile, 'description').pop()
				skel_dir  = get_profile_data(profile, 'profileSkel').pop()
				shell     = get_profile_data(profile, 'profileShell').pop()
				pri_group = get_profile_data(profile, 'groupName').pop()
				quota     = get_profile_data(profile, 'profileQuota').pop()

				# «groups» XML tag contains nothing except « group » children.
				# keep them as a list, don't pop().
				try:
					groups = get_profile_data(
								profile.getElementsByTagName('memberGid').pop(),
								'groupName')
					groups.sort()
				except IndexError:
					# this profile has no default groups to set users in.
					# this is awesome, but this could be normal.
					groups = []


				yield LMC.groups.name_to_gid(pri_group), Profile(
								name=name,
								description=comment,
								profileSkel=skel_dir,
								groupName=pri_group,
								memberGid=groups,
								profileQuota=quota,
								profileShell=shell)

		except exceptions.CorruptFileError, e:
			e.SetFilename(filename)
			raise e
		except xmldom.DOMException, e:
			raise exceptions.CorruptFileError(filename, str(e))
		except expat.ExpatError, e:
			raise exceptions.CorruptFileError(filename, str(e))
		except (OSError, IOError):
			# FIXME: do something when there is no profiles on the system…
			return
