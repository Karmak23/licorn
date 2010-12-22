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

import os, re, shutil

from licorn.foundations           import exceptions, logging
from licorn.foundations           import fsapi, hlstr, readers, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton
from licorn.foundations.constants import filters

from licorn.core         import LMC
from licorn.core.classes import CoreController

class ProfilesController(Singleton, CoreController):
	""" representation of /etc/licorn/profiles.xml, compatible with
		gnome-system-tools. """
	init_ok = False
	load_ok = False

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
	def load(self):
		if ProfilesController.load_ok:
			return
		else:
			assert ltrace('profiles', '| load()')
			# be sure our dependancies are OK.
			LMC.groups.load()
			self.reload()

			#
			self.check_default_profile()
			ProfilesController.load_ok = True
	def __getitem__(self, item):
		return self.profiles[item]
	def __setitem__(self, item, value):
		self.profiles[item]=value
	def keys(self):
		return self.profiles.keys()
	def has_key(self, key):
		return self.profiles.has_key(key)
	def reload(self):

		CoreController.reload(self)

		with self.lock():
			self.profiles = readers.profiles_conf_dict(
				LMC.configuration.profiles_config_file)
			self.name_cache = {}

			# build the name cache a posteriori
			for group in self.profiles:
				self.name_cache[self.profiles[group]['name']] = group
	def check_default_profile(self):
		"""If no profile exists on the system, create a default one with system group "users"."""

		try:
			with self.lock():
				if self.profiles == {}:
					logging.warning('''Adding a default %s profile on the system '''
						'''(this is mandatory).''' %
							stylize(ST_NAME, 'Users'))
					# Create a default profile with 'users' as default primary
					# group, and use the Debian pre-existing group without
					# complaining if it exists.
					# TODO: translate/i18n these names ?
					self.AddProfile('Users', 'users',
						description='Standard desktop users',
						profileShell=LMC.configuration.users.default_shell,
						profileSkel=LMC.configuration.users.default_skel,
						force_existing=True)
		except (OSError, IOError), e:
			# if 'permission denied', likely to be that we are not root. pass.
			if e.errno != 13:
				raise e
	def WriteConf(self, filename=None):
		""" Write internal data into our file.

			NOT locked because always called from already locked methods.
		"""

		if filename is None:
			filename = LMC.configuration.profiles_config_file

		assert ltrace('profiles', '> WriteConf(%s)' % filename)

		# FIXME: lock our datafile with a FileLock() ?
		open(filename, "w").write(self.ExportXML())

		assert ltrace('profiles', '< WriteConf()')
	def Select(self, filter_string):
		""" Filter profiles on different criteria. """

		assert ltrace('profiles', '> Select(%s)' % filter_string)

		with self.lock():
			profiles = self.profiles.keys()
			profiles.sort()

			filtered_profiles = []

			if filters.NONE == filter_string:
				filtered_profiles = []

			elif type(filter_string) == type([]):
				filtered_profiles = filter_string

			elif filter_string & filters.ALL:
				# dummy filter, to permit same means of selection as in users/groups
				filtered_profiles.extend(self.profiles.keys())

			else:
				arg_re = re.compile("^profile=(?P<profile>.*)", re.UNICODE)
				arg = arg_re.match(filter_string)
				if arg is not None:
					profile = arg.group('profile')
					filtered_profiles.append(profile)

		assert ltrace('profiles', '< Select(%s)' % filtered_profiles)

		return filtered_profiles
	def ExportCLI(self, selected=None):
		""" Export the user profiles list to human readable form. """
		data = ""

		with self.lock():
			if selected is None:
				profiles = self.profiles.keys()
			else:
				profiles = selected
			profiles.sort()

			assert ltrace('profiles', '| ExportCLI(%s)' % profiles)

			for profile in profiles:
				data += ''' %s Profile %s:
	Group: %s (gid=%d)
	description: %s
	Home: %s
	Default skel: %s
	Default shell: %s
	Quota: %sMb%s
''' % (
			stylize(ST_LIST_L1, '*'),
			self.profiles[profile]['name'],
			self.profiles[profile]['groupName'],
			LMC.groups.name_to_gid(
				self.profiles[profile]['groupName']),
			self.profiles[profile]['description'],
			LMC.configuration.users.base_path,
			self.profiles[profile]['profileSkel'],
			self.profiles[profile]['profileShell'],
			self.profiles[profile]['profileQuota'],
			'\n	Groups: %s' % \
				", ".join(self.profiles[profile]['memberGid']) \
				if self.profiles[profile]['memberGid'] != [] else ''
				)
			return data
	def ExportXML(self, selected=None):
		""" Export the user profiles list to XML. """

		with self.lock():
			if selected is None:
				profiles = self.profiles.keys()
			else:
				profiles = selected
			profiles.sort()

			assert ltrace('profiles', '| ExportXML(%s)' % profiles)

			data = "<?xml version='1.0' encoding=\"UTF-8\"?>\n<profiledb>\n"

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
				self.profiles[profile]['name'],
				self.profiles[profile]['groupName'],
				LMC.groups.name_to_gid(
					self.profiles[profile]['groupName']),
				self.profiles[profile]['description'] ,
				LMC.configuration.users.base_path,
				self.profiles[profile]['profileQuota'],
				self.profiles[profile]['profileSkel'],
				self.profiles[profile]['profileShell'],
				'''<memberGid>%s</memberGid>''' % \
					"\n".join( [ "\t\t\t<groupName>%s</groupName>" % x \
						for x in self.profiles[profile]['memberGid'] ]) \
						if self.profiles[profile]['memberGid'] != []	\
						else ''
				)

			data += "</profiledb>\n"

			return data
	def _validate_fields(self, name, group, description, profileShell,
		profileSkel):

		if description in ('', None):
			description = "The %s profile" % name

		if group is None:
			group = name

		if not profileShell in LMC.configuration.users.shells:
			raise exceptions.BadArgumentError('''The shell you specified '''
				'''doesn't exist on this system. Valid shells are: %s.''' %
				str(LMC.configuration.users.shells))

		if not profileSkel in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError('''The skel you specified '''
				'''doesn't exist on this system. Valid skels are: %s.''' %
				str(LMC.configuration.users.skels))

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

		return name, group, description, profileShell, profileSkel
	def AddProfile(self, name, group, profileQuota=1024, groups=[],
		description=None, profileShell=None, profileSkel=None,
		force_existing=False):
		""" Add a user profile (LMC.groups is an instance of GroupsController
			and is needed to create the profile group). """

		assert ltrace('profiles', '''> AddProfile(%s): '''
			'''group=%s, profileQuota=%d, groups=%s, description=%s, '''
			'''profileShell=%s, profileSkel=%s, force_existing=%s''' % (
				stylize(ST_NAME, name), group, profileQuota,
				groups, description, profileShell, profileSkel, force_existing))

		name, group, description, profileShell, profileSkel = \
			self._validate_fields(name, group, description, profileShell,
				profileSkel)

		with self.lock():
			if name in self.name_cache:
				raise exceptions.AlreadyExistsException(
				'''The profile '%s' already exists on the system''' % name)

			if group in self.profiles.keys():
				raise exceptions.AlreadyExistsException(
				'''The group '%s' is already taken by another profile (%s). '''
				'''Please choose another one.''' % (
					group, self.group_to_name(group)))

			create_group = True

			with LMC.groups.lock():
				if LMC.groups.exists(name=group):
					if force_existing:
						create_group = False
					else:
						raise exceptions.AlreadyExistsError(
							'''A system group named "%s" already exists.'''
							''' Please choose another group name for your '''
							'''profile, or use --force-existing to override.'''
							% group)

				# Verify groups
				for g in groups:
					try:
						gid = LMC.groups.name_to_gid(g)
					except exceptions.DoesntExistsException:
						logging.notice("Skipped non-existing group '%s'." %
							stylize(ST_NAME,g))
						groups.remove(g)

				# Add the system group
				if create_group:
					gid, group = LMC.groups.AddGroup(group,
						description=description, system=True,
						groupSkel=profileSkel)
				else:
					if LMC.groups.is_standard_group(group):
						raise exceptions.BadArgumentError(
							'''The group %s (gid=%s) is not a system group. It '''
							'''cannot be added as primary group of a '''
							'''profile.''' % (
							stylize(ST_NAME, group),
							stylize(ST_UGID,
								LMC.groups.name_to_gid(group))))
					else:
						gid = LMC.groups.name_to_gid(group)

				# Add the profile in the list
				self.profiles[group] = {
					'name': name,
					'groupName': group,
					'description': description,
					'profileSkel': profileSkel,
					'profileShell': profileShell,
					'profileQuota': profileQuota,
					'memberGid': groups
					}

				# feed the cache
				self.name_cache[name] = group
				self.WriteConf()

		logging.info("Added profile %s (group=%s, gid=%s)." % (
			stylize(ST_NAME, name),
			stylize(ST_NAME, group),
			stylize(ST_UGID, gid)))

		assert ltrace('profiles', '< AddProfile(%s)' % self.profiles)
	def DeleteProfile(self, name=None, group=None, gid=None, del_users=False,
		no_archive=False, batch=False):
		""" Delete a user profile (LMC.groups is an instance of
			GroupsController and is needed to delete the profile group). """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		assert ltrace('profiles', '> DeleteProfile(%s,%s,%s)' % (gid, group, name))

		with self.lock():
			with LMC.groups.lock():

				try:
					LMC.groups.DeleteGroup(gid=gid, del_users=del_users,
						no_archive=no_archive, batch=batch, check_profiles=False)
				except exceptions.DoesntExistsException:
					logging.info('Group %s already deleted, skipped.' % group)

				# del from the profiles and the cache
				del self.profiles[group]
				del self.name_cache[name]
				self.WriteConf()

		logging.info(logging.SYSP_DELETED_PROFILE %
			stylize(ST_NAME, name))

		assert ltrace('profiles', '< DeleteProfile()')
	def ChangeProfileSkel(self, gid=None, group=None, name=None,
		profileSkel=None):
		""" Modify the profile's skel. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		assert ltrace('profiles', '> ChangeProfileSkel(%s, %s)' % (
			name, profileSkel))

		# FIXME: shouldn't we auto-apply the new skel to all existing users ?
		# or give an optionnal auto-apply argument (I think it already exists
		# but this method isn't aware of it.

		if profileSkel is None:
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_SKEL))

		if profileSkel not in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError(
				'skel %s not in list of allowed skels (%s)' % (profileSkel,
					LMC.configuration.users.skels))

		with self.lock():
			self.profiles[group]['profileSkel'] = profileSkel
			self.WriteConf()

		logging.info('''Changed profile %s skel to '%s'.''' % (
			stylize(ST_NAME, name), profileSkel))

		assert ltrace('profiles', '< ChangeProfileSkel()')
	def ChangeProfileShell(self, gid=None, group=None, name=None,
		profileShell=None):
		""" Change the profile shell. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		assert ltrace('profiles', '> ChangeProfileShell(%s, %s)' % (
			name, profileShell))

		# FIXME: shouldn't we auto-apply the new shell to all existing users ?
		# or give an optionnal auto-apply argument (I think it already exists
		# but this method isn't aware of it.

		if profileShell is None:
			raise exceptions.BadArgumentError(logging.SYSP_SPECIFY_SHELL)

		if profileShell not in LMC.configuration.users.shells:
			raise exceptions.BadArgumentError(
				'shell %s not in list of allowed shells (%s)' % (profileShell,
					LMC.configuration.users.shells))

		with self.lock():
			self.profiles[group]['profileShell'] = profileShell
			self.WriteConf()

		logging.info('''Changed profile %s shell to '%s'.''' % (
			stylize(ST_NAME, name), profileShell))

		assert ltrace('profiles', '< ChangeProfileShell()')
	def ChangeProfileQuota(self, gid=None, group=None, name=None,
		profileQuota=None):
		""" Chnge the profile Quota. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		assert ltrace('profiles', '> ChangeProfileQuota(%s, %s)' % (
			name, profileQuota))

		# FIXME: shouldn't we auto-apply the new quota to all existing users ?
		# or give an optionnal auto-apply argument (I think it already exists
		# but this method isn't aware of it.

		if group is None:
			raise exceptions.BadArgumentError, "You must specify a group"
		if profileQuota is None:
			raise exceptions.BadArgumentError, "You must specify a profileQuota"

		with self.lock():
			self.profiles[group]['profileQuota'] = profileQuota
			self.WriteConf()

		logging.info('''Changed profile %s quota to '%s'.''' % (
			stylize(ST_NAME, name), profileQuota))

		assert ltrace('profiles', '< ChangeProfileQuota()')
	def ChangeProfileDescription(self, gid=None, group=None, name=None,
		description=None):
		""" Change profile's description. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		assert ltrace('profiles', '> ChangeProfileDescription(%s, %s)' % (
			name, description))

		if description is None:
			raise exceptions.BadArgumentError, "You must specify a description."

		if not hlstr.cregex['description'].match(str(description)):
			raise exceptions.BadArgumentError('''Malformed profile '''
				'''description « %s », must match /%s/i.''' % (
					description, hlstr.regex['description']))

		with self.lock():
			self.profiles[group]['description'] = description
			self.WriteConf()

		logging.info('''Changed profile %s description to '%s'.''' % (
			stylize(ST_NAME, name), description))

		assert ltrace('profiles', '< ChangeProfileDescription()')
	def ChangeProfileName(self, gid=None, group=None, name=None, newname=None):
		""" Change the profile Display Name. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		assert ltrace('profiles', '> ChangeProfileName(%s, %s)' % (
			name, newname))

		if newname is None:
			raise exceptions.BadArgumentError, "You must specify a new name"

		with self.lock():
			self.profiles[group]['name'] = newname
			del self.name_cache[name]
			self.name_cache[newname] = group
			self.WriteConf()

		logging.info('''Changed profile %s's name to %s.''' % (
			stylize(ST_NAME, name),
			stylize(ST_NAME, newname)
			))

		assert ltrace('profiles', '< ChangeProfileName()')
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

		LMC.groups.RenameGroup(self,
			self.profiles[group]['groupName'], newgroup)
	def AddGroupsInProfile(self, gid=None, group=None, name=None,
		groups_to_add=None):
		""" Add groups in the groups list of the profile 'group'. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		assert ltrace('profiles', '> AddGroupsInProfile(%s, %s)' % (
				name, groups_to_add))

		if groups_to_add is None:
			raise exceptions.BadArgumentError(
				'''You must specify a list of groups''')

		with self.lock():
			with LMC.groups.lock():

				gids_to_add = LMC.groups.guess_identifiers(groups_to_add)
				added_groups = []
				g2n = LMC.groups.gid_to_name

				for gid_to_add in gids_to_add:
					name_to_add=g2n(gid_to_add)

					if name_to_add in self.profiles[group]['memberGid']:
						logging.info('''Group %s is already in groups of '''
							'''profile %s, skipped.''' % (
							stylize(ST_NAME, name_to_add),
							stylize(ST_NAME, group)))
					else:
						if name_to_add != group:
							self.profiles[group]['memberGid'].append(
								name_to_add)
							added_groups.append(name_to_add)
							logging.info('''Added group %s to profile %s.''' % (
								stylize(ST_NAME, name_to_add),
								stylize(ST_NAME, group)))
						else:
							logging.warning('''Can't add group %s to its own '''
								'''profile %s.''' % (
								stylize(ST_NAME, name_to_add),
								stylize(ST_NAME, group)))

				self.WriteConf()

		assert ltrace('profiles', '< AddGroupsInProfile(%s, %s)' % (
			name, added_groups))

		return added_groups
	def DeleteGroupsFromProfile(self, gid=None, group=None, name=None,
		groups_to_del=None):
		""" Delete groups from the groups list of the profile 'group'. """

		gid, group, name = self.resolve_gid_group_or_name(gid, group, name)

		assert ltrace('profiles', '> DeleteGroupsFromProfile(%s, %s)' % (
			name, groups_to_del))

		if groups_to_del is None:
			raise exceptions.BadArgumentError(
				"You must specify a list of groups")

		with self.lock():
			with LMC.groups.lock():
				gids_to_del = LMC.groups.guess_identifiers(groups_to_del)
				deleted_groups = []
				g2n = LMC.groups.gid_to_name

				for gid_to_del in gids_to_del:
					name_to_del=g2n(gid_to_del)

					if name_to_del in self.profiles[group]['memberGid']:
						self.profiles[group]['memberGid'].remove(name_to_del)
						deleted_groups.append(name_to_del)
						logging.info(
							"Deleted group %s from profile %s." % (
							stylize(ST_NAME, name_to_del),
							stylize(ST_NAME, group)))
					else:
						logging.notice(
							'''Group %s is not in groups of profile %s, ignored.''' % (
								stylize(ST_NAME, name_to_del),
								stylize(ST_NAME, group)))

				self.WriteConf()

		assert ltrace('profiles', '< DeleteGroupsFromProfile(%s, %s)' % (
			name, deleted_groups))

		return deleted_groups
	def ReapplyProfileOfUsers(self, users=None, apply_groups=False,
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
				"You must choose to apply the groups or/and the skel")

		uids = LMC.users.guess_identifiers(users)

		users = LMC.users
		groups = LMC.groups
		profiles = self.profiles

		u2l = LMC.users.uid_to_login
		n2g = LMC.groups.name_to_gid

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
							stylize(ST_PATH,
							profiles[profile]['profileSkel']),
							stylize(ST_NAME, login)))

						def install_to_user_homedir(entry,
							user_home=users[uid]['homeDirectory']):
							""" Copy a file/dir/link passed as an argument to
								the user home_dir, after having verified it
								doesn't exist (else remove it after having
								asked it should)."""

							entry_name = os.path.basename(entry)

							logging.progress('Installing skel part %s.' %
								stylize(ST_PATH, entry))

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
									stylize(ST_PATH, entry),
									stylize(ST_PATH, user_home)))

							dst_entry = '%s/%s' % (user_home, entry_name)

							if os.path.exists(dst_entry):
								warn_message = '''profile entry %s already '''\
									'''exists in %s's home dir (%s), it should '''\
									'''be overwritten to fully reapply the '''\
									'''profile. Overwrite ?''' % (
									stylize(ST_PATH, entry_name),
									stylize(ST_NAME, login),
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
										stylize(ST_NAME, login)))
							else:
								copy_profile_entry()
								return True
							return False

						something_done = reduce(pyutils.keep_true,
							map(install_to_user_homedir, fsapi.minifind(
								path=profiles[profile]['profileSkel'],
								mindepth=1, maxdepth=2)))

						users.CheckUsers([ uid ], batch=batch,
							auto_answer=auto_answer)

						if something_done:
							logging.info('Applyed skel %s to user %s.' % (
								stylize(ST_PATH,
								profiles[profile]['profileSkel']),
								stylize(ST_NAME, login)))
						else:
							logging.info('''Skel %s already applied or '''
								'''skipped for user %s.''' % (
								stylize(ST_PATH,
								profiles[profile]['profileSkel']),
								stylize(ST_NAME, login)))

						# After having applyed the profile skel, break the
						# profile / apply_skel loop, because a given user has
						# only ONE profile.
						break

		assert ltrace('profiles', '''< ReapplyProfilesOfUsers()''')
	def change_group_name_in_profiles(self, old_name, new_name):
		""" Change a group's name in the profiles groups list """

		with self.lock():
			for profile in self.profiles:
				for group in self.profiles[profile]['memberGid']:
					if group == old_name:
						index = self.profiles[profile]['memberGid'].index(group)
						self.profiles[profile]['memberGid'][index] = new_name
				if name in self.profiles[profile]['groupName']:
					self.profiles[profile]['groupName'] = new_name
			self.WriteConf()
	def delete_group_in_profiles(self, name):
		""" Delete a group in the profiles groups list """

		found = False

		with self.lock():
			for profile in self.profiles:
				try:
					self.profiles[profile]['memberGid'].remove(name)
					found=True
					logging.info("Deleted group %s from profile %s." % (
						stylize(ST_NAME, name),
						stylize(ST_NAME, profile)))

				except ValueError:
					# don't display this info if the group we want to delete is the
					# primary group of a profile, this is superfluous.
					if name not in self.profiles:
						logging.info('Group %s already not present in profile %s.'
							% (stylize(ST_NAME, name),
							stylize(ST_NAME, profile)))

			if found:
				self.WriteConf()
	# LOCKS: not locked besides this point, because we consider locking is done
	# in calling methods.
	def confirm_group(self, group):
		""" verify a group or GID or raise DoesntExists. """
		try:
			return self.profiles[group]['groupName']
		except KeyError:
			try:
				return self.profiles[
					LMC.groups.gid_to_name(group)
					]['groupName']
			except (KeyError, exceptions.DoesntExistsException):
				raise exceptions.DoesntExistsException(
					"group %s doesn't exist" % group)
	def resolve_from_gid(self, gid):
		group = LMC.groups.gid_to_name(gid)
		return (group, self.group_to_name(group))
	def resolve_from_group(self, group):
		return (LMC.groups.name_to_gid(group),
			self.group_to_name(group))
	def resolve_from_name(self, name):
		group = self.name_to_group(name)
		return (group, LMC.groups.name_to_gid(group))
	def resolve_gid_group_or_name(self, gid, group, name):
		""" method used every where to get gid / group / name of a profile
			object to do something onto. a non existing group / name will raise
			an exception from the group_to_name() / name_to_group() methods."""

		if gid is None and group is None and name is None:
			raise exceptions.BadArgumentError(
				"You must specify a GID, a name or a group to resolve from.")

		#assert ltrace('profiles', '| resolve_gid_group_or_name(%s, %s, %s)' % (
		#	gid, group, name))

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

		#assert ltrace('profiles', '| guess_identifier(%s)' % value)

		try:
			group =	LMC.groups.gid_to_name(int(value))
		except ValueError:
			try:
				self.group_to_name(value)
				group = value
			except exceptions.DoesntExistsException:
				group = self.name_to_group(value)
		return group
	def exists(self, group=None, name=None):
		if group:
			return self.profiles.has_key(group)
		if name:
			return self.name_cache.has_key(name)
		raise exceptions.BadArgumentError('''You must specify a groupname or '''
		'''a profile name to test existence of.''')
	def group_to_name(self, group):
		""" Return the group of the profile 'name'."""

		#assert ltrace('profiles', '| group_to_name(%s)' % group)

		try:
			return self.profiles[group]['name']
		except KeyError:
			raise exceptions.DoesntExistsException(
				"Profile group %s doesn't exist." % group)
	def name_to_group(self, name):
		""" Return the group of the profile 'name'."""

		#assert ltrace('profiles', '| name_to_group(%s, %s)' % (
		#	name, self.name_cache.keys()))

		try:
			# use the cache, Luke !
			return self.name_cache[name]
		except KeyError:
			raise exceptions.DoesntExistsException(
				"Profile %s doesn't exists" % name)
