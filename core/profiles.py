# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

profiles - compatible with gnome-system-tools profiles

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2
"""

import os, re, shutil

from licorn.foundations           import fsapi, hlstr, logging
from licorn.foundations           import exceptions, styles, readers, pyutils
from licorn.foundations.objects   import Singleton
from licorn.foundations.constants import filters
from licorn.foundations.ltrace    import ltrace

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
	def has_key(self, key):
		return ProfilesController.profiles.has_key(key)
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

		# filter_applied is used to note if something has been selected (or
		# tried to). Without this, «get profiles» on a system with no profiles
		# returns all system accounts. Even if nothing match the filter given
		# we must note that a filter has been applied, in order to output a
		# coherent result.
		self.filter_applied = True

		profiles = ProfilesController.profiles.keys()
		profiles.sort()

		self.filtered_profiles = []

		if filters.NONE == filter_string:
			self.filtered_profiles = []

		elif type(filter_string) == type([]):
			self.filtered_profiles = filter_string

		elif filter_string & filters.ALL:
			# dummy filter, to permit same means of selection as in users/groups
			self.filtered_profiles.extend(ProfilesController.profiles.keys())

		else:
			arg_re = re.compile("^profile=(?P<profile>.*)", re.UNICODE)
			arg = arg_re.match(filter_string)
			if arg is not None:
				profile = arg.group('profile')
				self.filtered_profiles.append(profile)

		return self.filtered_profiles
	def ExportCLI(self):
		""" Export the user profiles list to human readable form. """
		data = ""

		if self.filter_applied:								# see Select()
			profiles = self.filtered_profiles
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
			profiles = self.filtered_profiles
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

		if ProfilesController.groups.exists(name=group):
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
			except exceptions.DoesntExistsException:
				logging.notice("Skipped non-existing group '%s'." %
					styles.stylize(styles.ST_NAME,g))
				groups.remove(g)

		# Add the system group
		if create_group:
			gid, group = self.groups.AddGroup(group, description=description,
				system=True, groupSkel=profileSkel)

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

		logging.info("Added profile %s (group=%s, gid=%s)." % (
			styles.stylize(styles.ST_NAME, name),
			styles.stylize(styles.ST_NAME, group),
			styles.stylize(styles.ST_UGID, gid)))

		#except Exception, e:
			# Rollback
		#	print "ROLLBACK because " + str(e)
			#self.groups.DeleteGroup(self, group)
		#	raise e
	def DeleteProfile(self, name=None, group=None, gid=None, del_users=False,
		no_archive=False, batch=False):
		""" Delete a user profile (self.groups is an instance of
			GroupsController and is needed to delete the profile group)
		"""

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		ltrace('profiles', '> DeleteProfile(%s,%s,%s)' % (gid, group, name))

		try:
			self.groups.DeleteGroup(gid=gid, del_users=del_users,
				no_archive=no_archive, batch=batch)
		except exceptions.DoesntExistsException:
			logging.info('Group %s already deleted, skipped.' % group)

		del(ProfilesController.profiles[group])
		self.WriteConf()
		logging.info(logging.SYSP_DELETED_PROFILE % styles.stylize(styles.ST_NAME, group))

		ltrace('profiles', '< DeleteProfile()')
	def ChangeProfileSkel(self, gid=None, group=None, name=None,
		profileSkel=None):
		""" Modify the profile's skel. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		ltrace('profiles', '> ChangeProfileSkel(%s, %s)' % (
			name, profileSkel))

		# FIXME: shouldn't we auto-apply the new skel to all existing users ?
		# or give an optionnal auto-apply argument (I think it already exists
		# but this method isn't aware of it.

		if profileSkel is None:
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_SKEL))

		if profileSkel not in self.configuration.users.skels:
			raise exceptions.BadArgumentError(
				'skel %s not in list of allowed skels (%s)' % (profileSkel,
					self.configuration.users.skels))

		ProfilesController.profiles[group]['profileSkel'] = profileSkel
		self.WriteConf()

		logging.info('''Changed profile %s skel to '%s'.''' % (
			styles.stylize(styles.ST_NAME, name), profileSkel))

		ltrace('profiles', '< ChangeProfileSkel()')
	def ChangeProfileShell(self, gid=None, group=None, name=None,
		profileShell=None):
		""" Change the profile shell. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		ltrace('profiles', '> ChangeProfileShell(%s, %s)' % (
			name, profileShell))

		# FIXME: shouldn't we auto-apply the new shell to all existing users ?
		# or give an optionnal auto-apply argument (I think it already exists
		# but this method isn't aware of it.

		if profileShell is None:
			raise exceptions.BadArgumentError(logging.SYSP_SPECIFY_SHELL)

		if profileShell not in self.configuration.users.shells:
			raise exceptions.BadArgumentError(
				'shell %s not in list of allowed shells (%s)' % (profileShell,
					self.configuration.users.shells))

		ProfilesController.profiles[group]['profileShell'] = profileShell
		self.WriteConf()

		logging.info('''Changed profile %s shell to '%s'.''' % (
			styles.stylize(styles.ST_NAME, name), profileShell))

		ltrace('profiles', '< ChangeProfileShell()')
	def ChangeProfileQuota(self, gid=None, group=None, name=None,
		profileQuota=None):
		""" Chnge the profile Quota. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		ltrace('profiles', '> ChangeProfileQuota(%s, %s)' % (
			name, profileQuota))

		# FIXME: shouldn't we auto-apply the new quota to all existing users ?
		# or give an optionnal auto-apply argument (I think it already exists
		# but this method isn't aware of it.

		if group is None:
			raise exceptions.BadArgumentError, "You must specify a group"
		if profileQuota is None:
			raise exceptions.BadArgumentError, "You must specify a profileQuota"

		ProfilesController.profiles[group]['profileQuota'] = profileQuota
		self.WriteConf()

		logging.info('''Changed profile %s quota to '%s'.''' % (
			styles.stylize(styles.ST_NAME, name), profileQuota))

		ltrace('profiles', '< ChangeProfileQuota()')
	def ChangeProfileDescription(self, gid=None, group=None, name=None,
		description=None):
		""" Change profile's description. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		ltrace('profiles', '> ChangeProfileDescription(%s, %s)' % (
			name, description))

		if description is None:
			raise exceptions.BadArgumentError, "You must specify a description."

		if not hlstr.cregex['description'].match(str(description)):
			raise exceptions.BadArgumentError('''Malformed profile '''
				'''description « %s », must match /%s/i.''' % (
					description, hlstr.regex['description']))

		ProfilesController.profiles[group]['description'] = description
		self.WriteConf()

		logging.info('''Changed profile %s description to '%s'.''' % (
			styles.stylize(styles.ST_NAME, name), description))

		ltrace('profiles', '< ChangeProfileDescription()')
	def ChangeProfileName(self, gid=None, group=None, name=None, newname=None):
		""" Change the profile Display Name. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		ltrace('profiles', '> ChangeProfileName(%s, %s)' % (
			name, newname))

		if newname is None:
			raise exceptions.BadArgumentError, "You must specify a new name"

		ProfilesController.profiles[group]['name'] = newname
		self.WriteConf()

		logging.info('''Changed profile %s name to '%s'.''' % (
			styles.stylize(styles.ST_NAME, name), newname))

		ltrace('profiles', '< ChangeProfileName()')
	def ChangeProfileGroup(self, gid=None, group=None, name=None,
		newgroup=None):
		""" Change and Rename the profile primary group. """

		raise NotImplementedError('to be refreshed.')

		# FIXME: this is tough. we have to change the primary group of all
		# current members of the profile, and users.CheckUsers() to re-chown
		# all their home dirs. Along the RenameGroup(), this is quite a tricky
		# (and risky) operation. Be careful when implementing it.

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		if newgroup is None:
			raise exceptions.BadArgumentError, "You must specify a new group"

		self.groups.RenameGroup(self,
			ProfilesController.profiles[group]['groupName'], newgroup)
	def AddGroupsInProfile(self, gid=None, group=None, name=None,
		groups_to_add=None):
		""" Add groups in the groups list of the profile 'group'. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		ltrace('profiles', '> AddGroupsInProfile(%s, %s)' % (
			name, groups_to_add))

		if groups_to_add is None:
			raise exceptions.BadArgumentError(
				"You must specify a list of groups")

		gids_to_add = self.groups.guess_identifiers(groups_to_add)
		added_groups = []
		g2n = self.groups.gid_to_name

		for gid_to_add in gids_to_add:
			name_to_add=g2n(gid_to_add)

			if name_to_add in ProfilesController.profiles[group]['memberGid']:
				logging.info(
					"Group %s is already in groups of profile %s, skipped." % (
					styles.stylize(styles.ST_NAME, name_to_add),
					styles.stylize(styles.ST_NAME, group)))
			else:
				if name_to_add != group:
					logging.info(
						"Added group %s to profile %s." % (
						styles.stylize(styles.ST_NAME, name_to_add),
						styles.stylize(styles.ST_NAME, group)))
					ProfilesController.profiles[group]['memberGid'].append(
						name_to_add)
					added_groups.append(name_to_add)
				else:
					logging.warning(
						"Can't add group %s to its own profile %s." % (
						styles.stylize(styles.ST_NAME, name_to_add),
						styles.stylize(styles.ST_NAME, group)))

		self.WriteConf()

		ltrace('profiles', '< AddGroupsInProfile(%s, %s)' % (
			name, added_groups))

		return added_groups
	def DeleteGroupsFromProfile(self, gid=None, group=None, name=None,
		groups_to_del=None):
		""" Delete groups from the groups list of the profile 'group'. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		ltrace('profiles', '> DeleteGroupsFromProfile(%s, %s)' % (
			name, groups_to_del))

		if groups_to_del is None:
			raise exceptions.BadArgumentError(
				"You must specify a list of groups")

		gids_to_del = self.groups.guess_identifiers(groups_to_del)
		deleted_groups = []
		g2n = self.groups.gid_to_name

		for gid_to_del in gids_to_del:
			name_to_del=g2n(gid_to_del)

			if name_to_del in ProfilesController.profiles[group]['memberGid']:
				ProfilesController.profiles[group]['memberGid'].remove(name_to_del)
				deleted_groups.append(name_to_del)
				logging.info(
					"Deleted group %s from profile %s." % (
					styles.stylize(styles.ST_NAME, name_to_del),
					styles.stylize(styles.ST_NAME, group)))
			else:
				logging.notice(
					'''Group %s is not in groups of profile %s, ignored.''' % (
						styles.stylize(styles.ST_NAME, name_to_del),
						styles.stylize(styles.ST_NAME, group)))

		self.WriteConf()

		ltrace('profiles', '< DeleteGroupsFromProfile(%s, %s)' % (
			name, deleted_groups))

		return deleted_groups
	def ReapplyProfileOfUsers(self, users=None, apply_groups=False,
		apply_skel=False, batch=False, auto_answer=None):
		""" Reapply the profile of users.
			If apply_groups is True, each user will be put in groups listed
			in his profile. If apply_skel is True, the skel of each user will
			be copied as in user creation. """

		ltrace('profiles', '''> ReapplyProfilesOfUsers(users=%s, '''
			'''apply_groups=%s, apply_skel=%s)''' % (users, apply_groups,
				apply_skel))

		if apply_groups is False and apply_skel is False:
			raise exceptions.BadArgumentError(
				"You must choose to apply the groups or/and the skel")

		uids = self.users.guess_identifiers(users)

		users = ProfilesController.users
		groups = ProfilesController.groups
		profiles = ProfilesController.profiles

		u2l = ProfilesController.users.uid_to_login
		n2g = ProfilesController.groups.name_to_gid
		g2n = ProfilesController.groups.gid_to_name

		for uid in uids:
			login = u2l(uid)

			for profile in profiles:
				if users[uid]['gidNumber'] == \
					n2g(profiles[profile]['groupName']):

					if apply_groups:
						for name in profiles[profile]['memberGid']:
							groups.AddUsersInGroup(name=name,
								users_to_add=[ uid ])
					if apply_skel:

						something_done = False

						logging.progress('Applying skel %s to user %s.' % (
							styles.stylize(styles.ST_PATH,
							profiles[profile]['profileSkel']),
							styles.stylize(styles.ST_NAME, login)))

						def install_to_user_homedir(entry,
							user_home=users[uid]['homeDirectory']):
							""" Copy a file/dir/link passed as an argument to
								the user home_dir, after having verified it
								doesn't exist (else remove it after having
								asked it should)."""

							entry_name = os.path.basename(entry)

							logging.progress('Installing skel part %s.' %
								styles.stylize(styles.ST_PATH, entry))

							def copy_profile_entry():
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
									styles.stylize(styles.ST_PATH, entry),
									styles.stylize(styles.ST_PATH, user_home)))

							dst_entry = '%s/%s' % (user_home, entry_name)

							if os.path.exists(dst_entry):
								warn_message = '''profile entry %s already '''\
									'''exists in %s's home dir (%s), it should '''\
									'''be overwritten to fully reapply the '''\
									'''profile. Overwrite ?''' % (
									styles.stylize(styles.ST_PATH, entry_name),
									styles.stylize(styles.ST_NAME, login),
									styles.stylize(styles.ST_PATH, user_home))

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
										styles.stylize(styles.ST_PATH,
											entry_name),
										styles.stylize(styles.ST_NAME, login)))
							else:
								copy_profile_entry()
								return True

							return False

						#map(install_to_user_homedir, fsapi.minifind(
						# path = ProfilesController.profiles[p]['profileSkel'],
						# maxdepth = 1,
						# type = stat.S_IFLNK|stat.S_IFDIR|stat.S_IFREG))
						something_done = reduce(pyutils.keep_true,
							map(install_to_user_homedir,
								fsapi.minifind(
									path=profiles[profile]['profileSkel'],
									mindepth=1, maxdepth=2)))

						users.CheckUsers([ uid ],
							batch=batch, auto_answer=auto_answer)

						if something_done:
							logging.info('Applyed skel %s to user %s.' % (
								styles.stylize(styles.ST_PATH,
								profiles[profile]['profileSkel']),
								styles.stylize(styles.ST_NAME, login)))
						else:
							logging.info('''Skel %s already applied or skipped '''
								'''for user %s.''' % (
								styles.stylize(styles.ST_PATH,
								profiles[profile]['profileSkel']),
								styles.stylize(styles.ST_NAME, login)))

						# After having applyed the profile skel, break the
						# profile / apply_skel loop, because a given user has only
						# ONE profile.
						break

		ltrace('profiles', '''< ReapplyProfilesOfUsers()''')

	def change_group_name_in_profiles(self, old_name, new_name):
		""" Change a group's name in the profiles groups list """

		profiles = ProfilesController.profiles

		for profile in profiles:
			for group in profiles[profile]['memberGid']:
				if group == old_name:
					index = profiles[profile]['memberGid'].index(group)
					profiles[profile]['memberGid'][index] = new_name
			if name in profiles[profile]['groupName']:
				profiles[profile]['groupName'] = new_name
		self.WriteConf()
	def delete_group_in_profiles(self, name):
		""" Delete a group in the profiles groups list """

		found = False
		for profile in ProfilesController.profiles:
			try:
				ProfilesController.profiles[profile]['memberGid'].remove(name)
				found=True
				logging.info(
					"Deleted group %s from profile %s." % (
					styles.stylize(styles.ST_NAME, name),
					styles.stylize(styles.ST_NAME, profile)))

			except ValueError:
				# don't display this info if the group we want to delete is the
				# primary group of a profile, this is superfluous.
				if name not in ProfilesController.profiles:
					logging.info('Group %s already not present in profile %s.' % (
						styles.stylize(styles.ST_NAME, name),
						styles.stylize(styles.ST_NAME, profile)))

		if found:
			self.WriteConf()
	def confirm_group(self, group):
		""" verify a group or GID or raise DoesntExists. """
		try:
			return ProfilesController.profiles[group]['groupName']
		except KeyError:
			try:
				return ProfilesController.profiles[
					ProfilesController.groups.gid_to_name(group)
					]['groupName']
			except (KeyError, exceptions.DoesntExistsException):
				raise exceptions.DoesntExistsException(
					"group %s doesn't exist" % group)
	def resolve_from_gid(self, gid):
		group = ProfilesController.groups.gid_to_name(gid)
		return (group, ProfilesController.group_to_name(group))
	def resolve_from_group(self, group):
		return (ProfilesController.groups.name_to_gid(group),
			ProfilesController.group_to_name(group))
	def resolve_from_name(self, name):
		group = ProfilesController.name_to_group(name)
		return (group, ProfilesController.groups.name_to_gid(group))
	def resolve_gid_group_or_name(self, gid, group, name):
		""" method used every where to get gid / group / name of a profile
			object to do something onto. a non existing group / name will raise
			an exception from the group_to_name() / name_to_group() methods."""

		if gid is None and group is None and name is None:
			raise exceptions.BadArgumentError(
				"You must specify a GID, a name or a group to resolve from.")

		if gid:
			group, name = self.resolve_from_gid(gid)
		elif group:
			gid, name = self.resolve_from_group(group)
		else:
			gid, group = self.resolve_from_name(name)

		return (gid, group, name)
	def guess_identifier(self, value):
		""" Try to guess everything of a profile from a
			single and unknonw-typed info. """
		try:
			group =	ProfilesController.groups.gid_to_name(int(value))
		except ValueError, e:
			try:
				ProfilesController.group_to_name(value)
				group = value
			except exceptions.DoesntExistsException, e:
				group = ProfilesController.name_to_group(value)
		return group
	@staticmethod
	def exists(group=None, name=None):
		if group:
			return ProfilesController.profiles.has_key(group)
		if name:
			return ProfilesController.name_cache.has_key(name)
		raise exceptions.BadArgumentError('''You must specify a groupname or '''
		'''a profile name to test existence of.''')
	@staticmethod
	def group_to_name(group):
		""" Return the group of the profile 'name'."""
		try:
			return ProfilesController.profiles[group]['name']
		except KeyError:
			raise exceptions.DoesntExistsException(
				"Profile group %s doesn't exist." % group)
	@staticmethod
	def name_to_group(name):
		""" Return the group of the profile 'name'."""
		try:
			# use the cache, Luke !
			return ProfilesController.name_cache[name]
		except KeyError:
			raise exceptions.DoesntExistsException(
				"Profile %s doesn't exists" % name)
