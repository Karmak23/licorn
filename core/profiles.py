# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

profiles - compatible with gnome-system-tools profiles

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""

import os, re, time, stat, shutil

from licorn.foundations         import process, fsapi, hlstr, logging
from licorn.foundations         import exceptions, styles, readers
from licorn.foundations.objects import Singleton
from licorn.foundations.ltrace  import ltrace

class ProfilesController(Singleton):
	""" representation of /etc/licorn/profiles.xml, compatible with gnome-system-tools.
	"""
	profiles      = None # Dictionary
	name_cache    = None  # dict
	init_ok       = False

	users         = None # UsersController
	groups        = None # GroupsController
	configuration = None # LicornConfiguration

	def __init__(self, configuration, groups, users):
		""" Load profiles from system configuration file. """

		if ProfilesController.init_ok:
			return

		ProfilesController.configuration = configuration

		ProfilesController.groups = groups
		groups.SetProfiles(self)

		ProfilesController.users = users
		users.SetProfiles(self)

		self.filtered_profiles = {}
		# see Select()
		self.filter_applied    = False

		if ProfilesController.profiles is None:
			self.reload()

		self.checkDefaultProfile()

		ProfilesController.init_ok = True
	def __getitem__(self, item):
		return ProfilesController.profiles[item]
	def __setitem__(self, item, value):
		ProfilesController.profiles[item]=value
	def keys(self):
		return ProfilesController.profiles.keys()
	def reload(self):
		ProfilesController.profiles   = readers.profiles_conf_dict(
			self.configuration.profiles_config_file)
		ProfilesController.name_cache = {}

		# build the name cache a posteriori
		for profile in self.profiles:
			ProfilesController.name_cache[
				ProfilesController.profiles[profile]['name']] = profile
	def checkDefaultProfile(self):
		"""If no profile exists on the system, create a default one with system group "users"."""

		try:
			if self.profiles == {}:
				logging.warning(
				'Adding a default profile on the system (this is mandatory).')
				# Create a default profile with 'users' as default primary
				# group, and use the Debian pre-existing group without
				# complaining if it exists.
				# TODO: translate/i18n these names ?
				self.AddProfile('Users', 'users',
					description = 'Standard desktop users',
					profileShell = self.configuration.users.default_shell,
					profileSkel = self.configuration.users.default_skel,
					force_existing = True)

		except (OSError, IOError), e:
			# if 'permission denied', likely to be that we are not root. pass.
			if e.errno != 13:
				raise e
	def WriteConf(self, filename = None):
		""" Write internal data into filename. """

		if filename is None:
			filename = ProfilesController.configuration.profiles_config_file

		ltrace('profiles', '> WriteConf(%s).' % filename)

		conffile = open(filename , "w")
		conffile.write(self.ExportXML())
		conffile.close()

		ltrace('profiles', '< WriteConf().')

	def Select(self, filter_string):
		""" Filter profiles on different criteria. """

		#
		# filter_applied is used to note if something has been selected (or tried to).
		# without this, «get profiles» on a system with no profiles returns all system accounts.
		# even if nothing match the filter given we must note that a filter has been applied,
		# in order to output a coherent result.
		#
		self.filter_applied = True

		profiles = ProfilesController.profiles.keys()
		profiles.sort()

		arg_re = re.compile("^profile=(?P<profile>.*)", re.UNICODE)
		arg = arg_re.match(filter_string)
		if arg is not None:
			profile = arg.group('profile')
			self.filtered_profiles[profile] = ProfilesController.profiles[profile]
	def ExportCLI(self):
		""" Export the user profiles list to human readable form. """
		data = ""

		if self.filter_applied:								# see Select()
			profiles = self.filtered_profiles.keys()
		else:
			profiles = ProfilesController.profiles.keys()
		profiles.sort()

		#
		# TODO: make all these strings "+" become "%s" % (... , ...)
		#

		for profile in profiles:

			data += ''' %s Profile %s:
	Group: %s(%d)
	description: %s
	Home: %s
	Default skel: %s
	Default shell: %s
	Quota: %sMb%s
''' % (
		styles.stylize(styles.ST_LIST_L1, '*'),
		ProfilesController.profiles[profile]['name'],
		ProfilesController.profiles[profile]['groupName'],
		ProfilesController.groups.name_to_gid(
			ProfilesController.profiles[profile]['groupName']),
		ProfilesController.profiles[profile]['description'],
		ProfilesController.configuration.users.base_path,
		ProfilesController.profiles[profile]['profileSkel'],
		ProfilesController.profiles[profile]['profileShell'],
		ProfilesController.profiles[profile]['profileQuota'],
		'\n	Groups: %s' % \
			", ".join(ProfilesController.profiles[profile]['memberGid']) \
			if ProfilesController.profiles[profile]['memberGid'] != [] else ''
			)
		return data
	def ExportXML(self):
		""" Export the user profiles list to XML. """

		data = "<?xml version='1.0' encoding=\"UTF-8\"?>\n<profiledb>\n"

		if self.filter_applied:								# see Select()
			profiles = self.filtered_profiles.keys()
		else:
			profiles = ProfilesController.profiles.keys()
		profiles.sort()

		# TODO: make all these "+s become "%s"


		for profile in profiles:
			data += '''	<profile>
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
			ProfilesController.profiles[profile]['name'],
			ProfilesController.profiles[profile]['groupName'],
			ProfilesController.groups.name_to_gid(
				ProfilesController.profiles[profile]['groupName']),
			ProfilesController.profiles[profile]['description'] ,
			ProfilesController.configuration.users.base_path,
			ProfilesController.profiles[profile]['profileQuota'],
			ProfilesController.profiles[profile]['profileSkel'],
			ProfilesController.profiles[profile]['profileShell'],
			'''<memberGid>%s</memberGid>''' % \
				"\n".join( [ "\t\t\t<groupName>%s</groupName>" % x \
					for x in ProfilesController.profiles[profile]['memberGid'] ]) \
					if ProfilesController.profiles[profile]['memberGid'] != []	\
					else ''
			)

		data += "</profiledb>\n"

		return data
	def AddProfile(self, name, group, profileQuota=1024, groups=[],
		description='', profileShell=None, profileSkel=None, force_existing=False):
		""" Add a user profile (self.groups is an instance of GroupsController
			and is needed to create the profile group). """

		if description == '':
			description = "The %s profile" % name

		if group is None:
			group = name

		ltrace('profiles', '''AddProfile(%s): '''
			'''group=%s, profileQuota=%d, groups=%s, description=%s, '''
			'''profileShell=%s, profileSkel=%s, force_existing=%s''' % (
				styles.stylize(styles.ST_NAME, name), group, profileQuota,
				groups, description, profileShell, profileSkel, force_existing))

		if not profileShell in self.configuration.users.shells:
			raise exceptions.BadArgumentError('''The shell you specified '''
				'''doesn't exist on this system. Valid shells are: %s.''' %
				str(self.configuration.users.shells))

		if not profileSkel in self.configuration.users.skels:
			raise exceptions.BadArgumentError('''The skel you specified '''
				'''doesn't exist on this system. Valid skels are: %s.''' %
				str(self.configuration.users.skels))

		if not hlstr.cregex['profile_name'].match(name):
			raise exceptions.BadArgumentError(
			"Malformed profile Name « %s », must match /%s/i." % (
				name, hlstr.regex['profile_name']))

		if not hlstr.cregex['group_name'].match(group):
			raise exceptions.BadArgumentError(
				"Malformed profile group name « %s », must match /%s/i." % (
					group, hlstr.regex['group_name']))

		if not hlstr.cregex['description'].match(description):
			raise exceptions.BadArgumentError(
				"Malformed profile description « %s », must match /%s/i." % (
					description, hlstr.regex['description']))

		if group in ProfilesController.profiles.keys():
			raise exceptions.AlreadyExistsException(
			"The profile '%s' already exists." % group)

		create_group = True

		if ProfilesController.groups.group_exists(name=group):
			if force_existing:
				create_group = False
			else:
				raise exceptions.AlreadyExistsError(
					'''A system group named "%s" already exists.'''
					''' Please choose another group name for your profile,'''
					''' or use --force-existing to override.'''
					% group)

		# Verify groups
		for g in groups:
			try:
				gid = self.groups.name_to_gid(g)
			except:
				logging.notice("The group '%s' doesn't exist, ignored." % g)
				groups.remove(g)

		# Add the system group
		if create_group:
			self.groups.AddGroup(group, description=description, system=True,
				groupSkel=profileSkel)

		#try:
			# Add the profile in the list
		ProfilesController.profiles[group] = {
			'name': name,
			'groupName': group,
			'description': description,
			'profileSkel': profileSkel,
			'profileShell': profileShell,
			'profileQuota': profileQuota,
			'memberGid': groups
			}
		self.WriteConf()
		#except Exception, e:
			# Rollback
		#	print "ROLLBACK because " + str(e)
			#self.groups.DeleteGroup(self, group)
		#	raise e
	def DeleteProfile(self, group, del_users, no_archive, allusers, batch=False):
		""" Delete a user profile (self.groups is an instance of GroupsController and is needed to delete the profile group)
		"""
		if group is None:
			raise exceptions.BadArgumentError, "You must specify a group."
		if no_archive is None:
			no_archive = False
		if group not in ProfilesController.profiles.keys():
			exceptions.LicornException, "The profile `%s' doesn't exist." % group

		try:
			self.groups.DeleteGroup(ProfilesController.profiles[group]['groupName'], del_users, no_archive, batch=batch)
		except exceptions.LicornRuntimeException:
			# don't fail if the group doesn't exist, it could have been previously deleted.
			# just try tro continue and delete the profile.
			pass
		except KeyError:
			raise exceptions.LicornException, "The profile `%s' doesn't exist." % group


		del(ProfilesController.profiles[group])
		self.WriteConf(self.configuration.profiles_config_file)
		logging.info(logging.SYSP_DELETED_PROFILE % styles.stylize(styles.ST_NAME, group))

	def ChangeProfileSkel(self, group, skel):
		"""
		"""
		if group is None:
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_GROUP))
		if skel is None:
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_SKEL))
		# FIXME: test the skel properly from configuration.
		if not os.path.isabs(skel) or not os.path.isdir(skel):
			raise exceptions.AbsolutePathError(skel)
		ProfilesController.profiles[group]['profileSkel'] = skel
	def ChangeProfileShell(self, group, profileShell):
		""" Setter
		"""
		if group is None:
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_GROUP))
		if profileShell is None:
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_profileShell))
		if not os.path.isabs(profileShell) or not os.path.exists(profileShell):
			raise exceptions.AbsolutePathError(profileShell)
		ProfilesController.profiles[group]['profileShell'] = profileShell
	def ChangeProfileQuota(self, group, profileQuota):
		""" Setter
		"""
		if group is None:
			raise exceptions.BadArgumentError, "You must specify a group"
		if profileQuota is None:
			raise exceptions.BadArgumentError, "You must specify a profileQuota"
		ProfilesController.profiles[group]['profileQuota'] = profileQuota
	def ChangeProfiledescription(self, group, description):
		""" Change profile's description. """

		if group is None:
			raise exceptions.BadArgumentError, "You must specify a group."
		if description is None:
			raise exceptions.BadArgumentError, "You must specify a description."
		if not hlstr.cregex['description'].match(str(description)):
			raise exceptions.BadArgumentError, "Malformed profile description « %s », must match /%s/i." % (description, hlstr.regex['description'])

		ProfilesController.profiles[group]['description'] = [description]
	def ChangeProfileName(self, group, newname):
		""" Setter
		"""
		if group is None:
			raise exceptions.BadArgumentError, "You must specify a group"
		if newname is None:
			raise exceptions.BadArgumentError, "You must specify a new name"


		ProfilesController.profiles[group]['name'] = [newname]
	def ChangeProfileGroup(self, group, newgroup):
		""" Setter """
		if group is None:
			raise exceptions.BadArgumentError, "You must specify a group"
		if newgroup is None:
			raise exceptions.BadArgumentError, "You must specify a new group"

		self.groups.RenameGroup(self, ProfilesController.profiles[group]['groupName'], newgroup)
		# Rename group
	def AddGroupsInProfile(self, group, groups):
		""" Add groups in the groups list of the profile 'group'
		"""
		if group is None:
			raise exceptions.BadArgumentError, "You must specify a group"
		if groups is None:
			raise exceptions.BadArgumentError, "You must specify a list of groups"

		added_groups = []

		for g in groups:
			if g in ProfilesController.profiles[group]['memberGid']:
				logging.info(
					"Group %s is already in groups of profile %s, skipped." % (
					styles.stylize(styles.ST_NAME, g),
					styles.stylize(styles.ST_NAME, group)))
			else:
				try:
					self.groups.name_to_gid(g)
				except exceptions.LicornRuntimeException:
					logging.warning("Group %s doesn't exist, ignored." %
						styles.stylize(styles.ST_NAME, g))
				else:
					ProfilesController.profiles[group]['memberGid'].append(g)
					added_groups.append(g)
		self.WriteConf()
		return added_groups
	def DeleteGroupsFromProfile(self, profile_group, groups_to_del):
		""" Delete groups from the groups list of the profile 'profile_group'. """

		if profile_group is None:
			raise exceptions.BadArgumentError, "You must specify a group"

		deleted_groups = []

		for g in groups_to_del:
			if g in ProfilesController.profiles[profile_group]['memberGid']:
				ProfilesController.profiles[profile_group]['memberGid'].remove(g)
				deleted_groups.append(g)
			else:
				logging.notice(
					'''Group %s is not in groups of profile %s, ignored.''' % (
						styles.stylize(styles.ST_NAME, g),
						styles.stylize(styles.ST_NAME, profile_group)))
		self.WriteConf()
		return deleted_groups
	def ReapplyProfileOfUsers(self, users, apply_groups=False, apply_skel=False, batch=False, auto_answer = None):
		""" Reapply the profile of users.
			If apply_groups is True, each user will be put in groups listed in his profile
			If apply_skel is True, the skel of each user will be copied as in user creation
		"""
		if apply_groups is False and apply_skel is False:
			raise exceptions.BadArgumentError, "You must choose to apply the groups or/and the skel"

		for u in users:
			try:
				uid = ProfilesController.users.login_to_uid(u)
			except exceptions.LicornRuntimeException, e:
				# most probably "the user does not exist".
				logging.warning(str(e))
			else:
				# search u's profile to
				for p in ProfilesController.profiles:
					if ProfilesController.users.users[uid]['gidNumber'] == ProfilesController.groups.name_to_gid(ProfilesController.profiles[p]['groupName']):
						if apply_groups:
							for g in ProfilesController.profiles[p]['memberGid']:
								ProfilesController.groups.AddUsersInGroup(g, [u])
						if apply_skel:

							logging.progress('Applying skel %s to user %s.' % (styles.stylize(styles.ST_PATH, ProfilesController.profiles[p]['profileSkel']), styles.stylize(styles.ST_NAME, u)))

							def install_to_user_homedir(entry, user_home = ProfilesController.users.users[uid]['homeDirectory']):
								""" Copy a file/dir/link passed as an argument to the user home_dir,
									after having verified it doesn't exist (else remove it after having asked it should)."""

								entry_name = os.path.basename(entry)

								logging.progress('Installing skel part %s.' % styles.stylize(styles.ST_PATH, entry))

								def copy_profile_entry():
									if os.path.islink(entry):
										os.symlink(os.readlink(entry), '%s/%s' % (user_home, entry_name))
									elif os.path.isdir(entry):
										shutil.copytree(entry, '%s/%s' % (user_home, entry_name), symlinks = True)
									else:
										shutil.copy2(entry, user_home)

								logging.info('Copied skel part %s to %s.' % (styles.stylize(styles.ST_PATH, entry), styles.stylize(styles.ST_PATH, user_home)))

								dst_entry = '%s/%s' % (user_home, entry_name)

								if os.path.exists(dst_entry):
									warn_message = '''profile entry %s already exists in user's home dir, it should be overwritten to fully reapply the profile.''' % styles.stylize(styles.ST_PATH, entry_name)
									if batch or logging.ask_for_repair(warn_message, auto_answer):
										if os.path.islink(dst_entry):
											os.unlink(dst_entry)
										elif os.path.isdir(dst_entry):
											shutil.rmtree(dst_entry)
										else:
											os.unlink(dst_entry)

										copy_profile_entry()
									else:
										logging.notice("Skipped entry %s." % styles.stylize(styles.ST_PATH, entry_name))
								else:
									copy_profile_entry()

							#map(install_to_user_homedir, fsapi.minifind(path = ProfilesController.profiles[p]['profileSkel'], maxdepth = 1, type = stat.S_IFLNK|stat.S_IFDIR|stat.S_IFREG))
							map(install_to_user_homedir, fsapi.minifind(path = ProfilesController.profiles[p]['profileSkel'], mindepth = 1, maxdepth = 2))
							ProfilesController.users.CheckUsers([ProfilesController.users.users[uid]['login']], batch = batch, auto_answer = auto_answer)

						# after having applyed the profile, break ; because a given user has only ONE profile.
						break
	def change_group_name_in_profiles(self, name, new_name):
		""" Change a group's name in the profiles groups list """
		for profile in ProfilesController.profiles:
			for group in ProfilesController.profiles[profile]['memberGid']:
				if group == name:
					index = ProfilesController.profiles[profile]['memberGid'].index(group)
					ProfilesController.profiles[profile]['memberGid'][index] = new_name
			if name in ProfilesController.profiles[profile]['groupName']:
				ProfilesController.profiles[profile]['groupName'] = [ new_name ]
		self.WriteConf(self.configuration.profiles_config_file)
	def delete_group_in_profiles(self, name):
		""" Delete a group in the profiles groups list """
		for profile in ProfilesController.profiles:
			for group in ProfilesController.profiles[profile]['memberGid']:
				if group == name:
					index = ProfilesController.profiles[profile]['memberGid'].index(group)
					del(ProfilesController.profiles[profile]['memberGid'][index])

		self.WriteConf()

	@staticmethod
	def profile_exists(profile):
		return ProfilesController.profiles.has_key(profile)
	@staticmethod
	def name_to_group(name):
		""" Return the group of the profile 'name'."""
		try:
			# use the cache, Luke !
			return ProfilesController.name_cache[name]
		except KeyError:
			raise exceptions.LicornRuntimeException(
				"The profile '%s' doesn't exist." % name)
