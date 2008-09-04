# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

profiles - compatible with gnome-system-tools profiles

Copyright (C) 2005-2007 Olivier Cortès <oc@5sys.fr>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""

import os, re, time, stat, shutil

from licorn.foundations    import process, fsapi, hlstr, logging, exceptions, styles
from licorn.core.internals import readers

class ProfilesList :
	""" representation of /etc/licorn/profiles.xml, compatible with gnome-system-tools.
	"""
	profiles      = None # Dictionary
	users         = None # UsersList
	groups        = None # GroupsList
	configuration = None # LicornConfiguration

	def __init__(self, configuration, groups, users) :
		""" Load profiles from system configuration file. """

		ProfilesList.configuration = configuration
		
		ProfilesList.groups = groups
		groups.SetProfiles(self)

		ProfilesList.users = users
		users.SetProfiles(self)

		self.filtered_profiles = {}
		# see Select()
		self.filter_applied    = False
		
		if ProfilesList.profiles is None :
			self.reload()

		self.checkDefaultProfile()
	def reload(self) :
		ProfilesList.profiles = readers.profiles_conf_dict(self.configuration.profiles_config_file)
	def checkDefaultProfile(self) :
		"""If no profile exists on the system, create a default one with system group "users"."""

		try :
			if self.profiles == {} :
				logging.warning('adding a default profile on the system (this is mandatory).')
				# Create a default profile with 'users' as default primary group, and use the Debian pre-existing group
				# without complaining if it exists.
				# TODO: translate/i18n these names ?
				self.AddProfile('Users', 'users', 
					comment = 'Standard desktop users',
					shell = self.configuration.users.default_shell,
					skeldir  = self.configuration.users.default_skel,
					force_existing = True)

				self.WriteConf()
		except (OSError, IOError), e :
			# if 'permission denied', likely to be that we are not root. pass.
			if e.errno != 13 : raise e
	def WriteConf(self, filename = None) :
		""" Write internal data into filename. """

		if filename is None :
			filename = ProfilesList.configuration.profiles_config_file

		conffile = open(filename , "w")
		conffile.write(self.ExportXML())
		conffile.close()
	def Select(self, filter_string) :
		""" Filter profiles on different criteria. """

		#
		# filter_applied is used to note if something has been selected (or tried to).
		# without this, «getent profiles» on a system with no profiles returns all system accounts.
		# even if nothing match the filter given we must note that a filter has been applied,
		# in order to output a coherent result.
		#
		self.filter_applied = True
		
		profiles = ProfilesList.profiles.keys()
		profiles.sort()
		
		arg_re = re.compile("^profile=(?P<profile>.*)", re.UNICODE)
		arg = arg_re.match(filter_string)
		if arg is not None :
			profile = arg.group('profile')
			self.filtered_profiles[profile] = ProfilesList.profiles[profile]
	def ExportCLI(self) :
		""" Export the user profiles list to human readable form. """
		data = ""

		if self.filter_applied :								# see Select()
			profiles = self.filtered_profiles.keys()
		else :
			profiles = ProfilesList.profiles.keys()
		profiles.sort()
		
		#
		# TODO : make all these strings "+" become "%s" % (... , ...)
		#

		for profile in profiles :
			data += " %s Profile %s:\n" % (styles.stylize(styles.ST_LIST_L1, '*'), ProfilesList.profiles[profile]['name']) \
				+ "	Group   : " + ProfilesList.profiles[profile]['primary_group'] + "\n" \
				+ "	Comment : " + ProfilesList.profiles[profile]['comment'] + "\n" \
				+ "	Skeldir : " + ProfilesList.profiles[profile]['skel_dir'] + "\n" \
				+ "	Home    : " + self.configuration.users.home_base_path + "/" + ProfilesList.profiles[profile]['primary_group'] + "\n" \
				+ "	Shell   : " + ProfilesList.profiles[profile]['shell'] + "\n" \
				+ "	Quota   : " + str(ProfilesList.profiles[profile]['quota']) + " Mo\n" \
				+ "	Groups  : " + ", ".join(ProfilesList.profiles[profile]['groups']) + "\n"
		return data
	def ExportXML(self) :
		""" Export the user profiles list to XML. """

		data = "<?xml version='1.0' encoding=\"UTF-8\"?>\n<profiledb>\n"
		
		if self.filter_applied :								# see Select()
			profiles = self.filtered_profiles.keys()
		else :
			profiles = ProfilesList.profiles.keys()
		profiles.sort()
		
		# TODO: make all these "+s become "%s"

		for profile in profiles :
			data += "\t<profile>\n" \
					+ "\t\t<name>"     + ProfilesList.profiles[profile]['name']          + "</name>\n"     \
					+ "\t\t<comment>"  + ProfilesList.profiles[profile]['comment']       + "</comment>\n"  \
					+ "\t\t<home>"     + self.configuration.users.home_base_path + "/" \
					                    + ProfilesList.profiles[profile]['primary_group'] + "</home>\n"     \
					+ "\t\t<quota>"    + str(ProfilesList.profiles[profile]['quota'])    + "</quota>\n"    \
					+ "\t\t<shell>"    + ProfilesList.profiles[profile]['shell']         + "</shell>\n"    \
					+ "\t\t<skel_dir>" + ProfilesList.profiles[profile]['skel_dir']      + "</skel_dir>\n" \
					+ "\t\t<group>"    + ProfilesList.profiles[profile]['primary_group'] + "</group>\n"
			if ProfilesList.profiles[profile]['groups'] :
				groups = []
				for g in ProfilesList.profiles[profile]['groups'] :
					if g != '' :
						groups.append("\t\t\t<group>%s</group>" % g)
				data += "\t\t<groups>\n%s\t\t</groups>\n" % "\n".join(groups)
			data += "\t</profile>\n"
		data += "</profiledb>\n"

		return data
	def AddProfile(self, name, group, quota = 1024, groups = [], comment = '', shell = None, skeldir = None, force_existing = False) :
		""" Add a user profile (self.groups is an instance of GroupsList and is needed to create the profile group). """

		if comment is '' :
			comment = "The %s profile." % name

		if not shell in self.configuration.users.shells :
			raise exceptions.BadArgumentError("The shell you specified doesn't exist on this system. Valid shells are : %s." \
				% str(self.configuration.users.shells))

		if not skeldir in self.configuration.users.skels :
			raise exceptions.BadArgumentError("The skel you specified doesn't exist on this system. Valid skels are : %s." \
				% str(self.configuration.users.skels))

		if not hlstr.cregex['profile_name'].match(name) :
			raise exceptions.BadArgumentError, "Malformed profile Name « %s », must match /%s/i." % (name, hlstr.regex['profile_name'])
		if not hlstr.cregex['group_name'].match(group) :
			raise exceptions.BadArgumentError, "Malformed profile group name « %s », must match /%s/i." % (group, hlstr.regex['group_name'])
		if not hlstr.cregex['description'].match(comment) :
			raise exceptions.BadArgumentError, "Malformed profile description « %s », must match /%s/i." % (comment, hlstr.regex['description'])
			
		if group in ProfilesList.profiles.keys() :
			raise exceptions.AlreadyExistsException, "The profile '" + group + "' already exists."

		create_group = True
		
		if ProfilesList.groups.group_exists(name = group) :
			if force_existing :
				create_group = False
			else :
				raise exceptions.AlreadyExistsError('A system group named "%s" already exists. Please choose another group name for your profile.' \
					% group)
		
		# Verify groups
		for g in groups :
			try :
				gid = self.groups.name_to_gid(g)
			except :
				logging.info("The group '%s' doesn't exist, ignored." % g)
				index = groups.index(g)
				del(groups[index])

		# Add the system group
		if create_group :
			self.groups.AddGroup(group, description = comment, system = True, skel = skeldir)

		try :
			# Add the profile in the list
			ProfilesList.profiles[group] = {'name' : name, 'primary_group' : group, 'comment' : comment, 'skel_dir' : skeldir, 'shell' : shell, 'quota' : quota, 'groups' : groups}
		except Exception, e :
			# Rollback
			print "ROLLBACK because " + str(e)
			self.groups.DeleteGroup(self, group)
			raise e
	def DeleteProfile(self, group, del_users, no_archive, allusers, batch=False) :
		""" Delete a user profile (self.groups is an instance of GroupsList and is needed to delete the profile group)
		"""
		if group is None :
			raise exceptions.BadArgumentError, "You must specify a group."
		if no_archive is None :
			no_archive = False
		if group not in ProfilesList.profiles.keys() :
			exceptions.LicornException, "The profile `%s' doesn't exist." % group
		
		try :
			self.groups.DeleteGroup(ProfilesList.profiles[group]['primary_group'], del_users, no_archive, batch=batch)
		except exceptions.LicornRuntimeException :
			# don't fail if the group doesn't exist, it could have been previously deleted.
			# just try tro continue and delete the profile.
			pass
		except KeyError :
			raise exceptions.LicornException, "The profile `%s' doesn't exist." % group


		del(ProfilesList.profiles[group])
		self.WriteConf(self.configuration.profiles_config_file)
		logging.info(logging.SYSP_DELETED_PROFILE % styles.stylize(styles.ST_NAME, group))

		# Delete the profile's base dir. All users accounts must have been previously deleted.
		profile_home_dir = "%s/%s" % (self.configuration.users.home_base_path, group) 
	
		if no_archive :
			try :
				os.rmdir(profile_home_dir)
				logging.info("Deleted profile base directory %s." % styles.stylize(styles.ST_PATH, profile_home_dir) )
			except OSError, e :
				if e.errno == 39 :
					# directory not empty
					logging.warning("Can't delete the profile base directory %s (this is harmless) (was: %s)." % (styles.stylize(styles.ST_PATH, profile_home_dir), e))
				else :
					raise e
		else :
			archive_dir = "%s/%s.deleted.%s" % (self.configuration.home_archive_dir, group, time.strftime("%Y%m%d-%H%M%S", time.gmtime()))
			try :
				os.rename(profile_home_dir, archive_dir)
				logging.info("Archived %s as %s." % (profile_home_dir, archive_dir) )
			except OSError, e :
				raise exceptions.LicornRuntimeException("Can't archive profile base dir %s, but other profile related stuff was successfully deleted (was: %s)." % (styles.stylize(styles.ST_PATH, profile_home_dir), e))

	def ChangeProfileSkel(self, group, skel) :
		"""
		"""
		if group is None :
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_GROUP))
		if skel is None :
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_SKEL))
		# FIXME : test the skel properly from configuration.
		if not os.path.isabs(skel) or not os.path.isdir(skel) :
			raise exceptions.AbsolutePathError(skel)
		ProfilesList.profiles[group]['skel_dir'] = skel
	def ChangeProfileShell(self, group, shell) :
		""" Setter
		"""
		if group is None :
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_GROUP))
		if shell is None :
			raise exceptions.BadArgumentError((logging.SYSP_SPECIFY_SHELL))
		if not os.path.isabs(shell) or not os.path.exists(shell) :
			raise exceptions.AbsolutePathError(shell)
		ProfilesList.profiles[group]['shell'] = shell
	def ChangeProfileQuota(self, group, quota) :
		""" Setter
		"""
		if group is None :
			raise exceptions.BadArgumentError, "You must specify a group"
		if quota is None :
			raise exceptions.BadArgumentError, "You must specify a quota"
		ProfilesList.profiles[group]['quota'] = quota
	def ChangeProfileComment(self, group, comment) :
		""" Change profile's comment. """

		if group is None :
			raise exceptions.BadArgumentError, "You must specify a group."
		if comment is None :
			raise exceptions.BadArgumentError, "You must specify a comment."
		if not hlstr.cregex['description'].match(str(comment)) :
			raise exceptions.BadArgumentError, "Malformed profile comment « %s », must match /%s/i." % (comment, hlstr.regex['description']) 
			
		ProfilesList.profiles[group]['comment'] = [comment]
	def ChangeProfileName(self, group, newname) :
		""" Setter
		"""
		if group is None :
			raise exceptions.BadArgumentError, "You must specify a group"
		if newname is None :
			raise exceptions.BadArgumentError, "You must specify a new name"
		
			
		ProfilesList.profiles[group]['name'] = [newname]
	def ChangeProfileGroup(self, group, newgroup) :
		""" Setter """
		if group is None :
			raise exceptions.BadArgumentError, "You must specify a group"
		if newgroup is None :
			raise exceptions.BadArgumentError, "You must specify a new group"

		self.groups.RenameGroup(self, ProfilesList.profiles[group]['primary_group'], newgroup)
		# Rename group
		os.rename(self.configuration.users.home_base_path + "/" + ProfilesList.profiles[group]['primary_group'], self.configuration.users.home_base_path + "/" + group) # rename home
	def AddGroupsInProfile(self, group, groups) :
		""" Add groups in the groups list of the profile 'group'
		"""
		if group is None :
			raise exceptions.BadArgumentError, "You must specify a group"
		if groups is None :
			raise exceptions.BadArgumentError, "You must specify a list of groups"
			
		for g in groups :
			if g in ProfilesList.profiles[group]['groups'] :
				logging.progress("Group %s is already in groups of profile %s, skipped." % (styles.stylize(styles.ST_NAME, g), styles.stylize(styles.ST_NAME, group)))
			else :
				try :
					self.groups.name_to_gid(g)
				except :
					logging.warning("Group %s doesn't exist, ignored." % styles.stylize(styles.ST_NAME, g))
				else :
					ProfilesList.profiles[group]['groups'].append(g)
	def DeleteGroupsFromProfile(self, profile_group, groups_to_del) :
		""" Delete groups from the groups list of the profile 'profile_group'. """

		if profile_group is None :
			raise exceptions.BadArgumentError, "You must specify a group"
			
		for g in groups_to_del :
			if g in ProfilesList.profiles[profile_group]['groups'] :
				index = ProfilesList.profiles[profile_group]['groups'].index(g)
				del(ProfilesList.profiles[profile_group]['groups'][index])
			else :
				logging.progress("Group %s is not in groups of profile %s, ignored." % (styles.stylize(styles.ST_NAME, g), styles.stylize(styles.ST_NAME, profile_group)))
	def ReapplyProfileOfUsers(self, users, apply_groups=False, apply_skel=False, batch=False, auto_answer = None) :
		""" Reapply the profile of users.
			If apply_groups is True, each user will be put in groups listed in his profile
			If apply_skel is True, the skel of each user will be copied as in user creation
		"""
		if apply_groups is False and apply_skel is False :
			raise exceptions.BadArgumentError, "You must choose to apply the groups or/and the skel"

		for u in users :
			try :
				uid = ProfilesList.users.login_to_uid(u)
			except exceptions.LicornRuntimeException, e :
				# most probably "the user does not exist".
				logging.warning(str(e))
			else :
				# search u's profile to 
				for p in ProfilesList.profiles :
					if ProfilesList.users.users[uid]['gid'] == ProfilesList.groups.name_to_gid(ProfilesList.profiles[p]['primary_group']) :
						if apply_groups :
							for g in ProfilesList.profiles[p]['groups'] :
								ProfilesList.groups.AddUsersInGroup(g, [u])
						if apply_skel :

							logging.progress('Applying skel %s to user %s.' % (styles.stylize(styles.ST_PATH, ProfilesList.profiles[p]['skel_dir']), styles.stylize(styles.ST_NAME, u)))

							def install_to_user_homedir(entry, user_home = ProfilesList.users.users[uid]['homeDirectory']) :
								""" Copy a file/dir/link passed as an argument to the user home_dir,
									after having verified it doesn't exist (else remove it after having asked it should)."""

								entry_name = os.path.basename(entry)

								logging.progress('Installing skel part %s.' % styles.stylize(styles.ST_PATH, entry))

								def copy_profile_entry() :
									if os.path.islink(entry) :
										os.symlink(os.readlink(entry), '%s/%s' % (user_home, entry_name))
									elif os.path.isdir(entry) :
										shutil.copytree(entry, '%s/%s' % (user_home, entry_name), symlinks = True)
									else :
										shutil.copy2(entry, user_home)

								logging.info('Copied skel part %s to %s.' % (styles.stylize(styles.ST_PATH, entry), styles.stylize(styles.ST_PATH, user_home)))

								dst_entry = '%s/%s' % (user_home,entry_name)

								if os.path.exists(dst_entry) :
									warn_message = '''profile entry %s already exists in user's home dir, it should be overwritten to fully reapply the profile.''' % styles.stylize(styles.ST_PATH, entry_name)
									if batch or logging.ask_for_repair(warn_message, auto_answer) :
										if os.path.islink(dst_entry) :
											os.unlink(dst_entry)
										elif os.path.isdir(dst_entry) :
											shutil.rmtree(dst_entry)
										else :
											os.unlink(dst_entry)

										copy_profile_entry()
									else :
										logging.notice("Skipped entry %s." % styles.stylize(styles.ST_PATH, entry_name))
								else :
									copy_profile_entry()

							#map(install_to_user_homedir, fsapi.minifind(path = ProfilesList.profiles[p]['skel_dir'], maxdepth = 1, type = stat.S_IFLNK|stat.S_IFDIR|stat.S_IFREG))
							map(install_to_user_homedir, fsapi.minifind(path = ProfilesList.profiles[p]['skel_dir'], mindepth = 1, maxdepth = 2))
							ProfilesList.users.CheckUsers([ProfilesList.users.users[uid]['login']], batch = batch, auto_answer = auto_answer)
						
						# after having applyed the profile, break ; because a given user has only ONE profile.
						break
	def change_group_name_in_profiles(self, name, new_name) :
		""" Change a group's name in the profiles groups list """
		for profile in ProfilesList.profiles :
			for group in ProfilesList.profiles[profile]['groups'] :
				if group == name :
					index = ProfilesList.profiles[profile]['groups'].index(group)
					ProfilesList.profiles[profile]['groups'][index] = new_name
			if name in ProfilesList.profiles[profile]['primary_group'] :
				ProfilesList.profiles[profile]['primary_group'] = [ new_name ]
		self.WriteConf(self.configuration.profiles_config_file)
	def delete_group_in_profiles(self, name) :
		""" Delete a group in the profiles groups list """
		for profile in ProfilesList.profiles :
			for group in ProfilesList.profiles[profile]['groups'] :
				if group == name :
					index = ProfilesList.profiles[profile]['groups'].index(group)
					del(ProfilesList.profiles[profile]['groups'][index])

		self.WriteConf()
	
	@staticmethod
	def profile_exists(profile) :
		return ProfilesList.profiles.has_key(profile)
