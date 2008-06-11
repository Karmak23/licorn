# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2006 Olivier Cortès <oc@5sys.fr>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""

import os, stat, posix1e, re
from time import strftime, gmtime

from licorn.foundations    import logging, exceptions, hlstr, styles, fsapi, pyutils, file_locks
from licorn.core.internals import readers

class GroupsList :
	""" Manages the groups and the associated shared data on a Linux system. """

	groups       = None  # dict
	name_cache   = None  # dict

	# cross-references to other common objects
	configuration = None  # LicornConfiguration
	users         = None  # UsersList
	profiles      = None  # ProfilesList

	# Filters for Select() method.
	FILTER_STANDARD    = 1
	FILTER_SYSTEM      = 2
	FILTER_PRIVILEGED  = 3
	FILTER_GUEST       = 4
	FILTER_RESPONSIBLE = 5
	FILTER_EMPTY       = 6

	def __init__ (self, configuration, users, warnings = True) :

		GroupsList.configuration = configuration

		GroupsList.users = users
		users.SetGroups(self)

		self.warnings = warnings

		# see licorn.system.users for details
		self.filter_applied = False

		if GroupsList.groups is None :
			self.reload()
	def reload(self) :
		""" load or reload internal data structures from files on disk. """
		GroupsList.groups     = {}
		GroupsList.name_cache = {}

		# FIXME : move all this stuff to configreader.py

		etc_group = readers.ug_conf_load_list("/etc/group")

		# if some inconsistency is detected during load and it can be corrected automatically, do it !
		need_rewriting = False

		extras      = []
		etc_gshadow = []
		is_allowed  = True
		try :
			extras      = readers.ug_conf_load_list(GroupsList.configuration.extendedgroup_data_file)
		except IOError, e :
			if e.errno != 2 : raise e # no such file
		try :
			etc_gshadow = readers.ug_conf_load_list("/etc/gshadow")
		except IOError, e :
			if e.errno == 13 :
				# don't raise an exception or display a warning, this is harmless if we
				# are loading data for getent, and any other operation (add/mod/del) will
				# fail anyway if we are not root or @admin.
				is_allowed = False
			else : raise e 

		if GroupsList.users :
			l2u      = GroupsList.users.login_to_uid
			users = GroupsList.users.users

		# TODO: transform this in 'for (gname, gid, gpass, gmembers) in etc_group :'

		for entry in etc_group :
			if len(entry) != 4 : continue # why continue ? why not raise CorruptFileError ??
			
			# implicitly index accounts on « int(gid) »
			gid = int(entry[2])
			
			if entry[3] == '' :
				# this happends when the group has no members.
				members = []
			else :
				members = entry[3].split(',')
				
				# update the cache to avoid massive CPU load in getent users --long
				# this code is also present in users.__init__, to cope with users/groups load
				# in different orders.
				if GroupsList.users :
					for member in members :
						try :
							GroupsList.users.users[l2u(member)]['groups'].add(entry[0])
						except exceptions.LicornRuntimeException :
							if self.warnings :
								logging.warning("User %s is referenced in members of group %s but doesn't really exist on the system, removing it." % (styles.stylize(styles.ST_BAD, member), styles.stylize(styles.ST_NAME,entry[0])))
							members.remove(member)
							need_rewriting = True

			GroupsList.groups[gid] = 	{
									'name' 			 : entry[0],
									'passwd'		 : entry[1],
									'gid'			 : gid,
									'members'		 : members,
									'description'	 :  "" , # empty string needed to skip error when we type GroupsList.groups[gid]['description']
									'skel'			 :  "" , # idem
									'permissive'     : None
								}
			# this will be used as a cache by name_to_gid()
			GroupsList.name_cache[ entry[0] ] = gid

			try :
				GroupsList.groups[gid]['permissive']	= self.__is_permissive(GroupsList.groups[gid]['name'])
			except exceptions.InsufficientPermissionsError :
				#logging.warning("You don't have enough permissions to display permissive states.", once = True)
				pass

			#
			# TODO : we could load the extras data in another structure before loading groups from /etc/group
			# to avoid this for() loop and just get extras[GroupsList.groups[gid]['name']] directly. this could
			# gain some time on systems with many groups.
			#

			extra_found = False
			for extra_entry in extras :
				if GroupsList.groups[gid]['name'] ==  extra_entry[0] :
					try :
						GroupsList.groups[gid]['description'] = extra_entry[1]
						GroupsList.groups[gid]['skel']        = extra_entry[2]
					except IndexError, e :
						raise exceptions.CorruptFileError(GroupsList.configuration.extendedgroup_data_file, '''for group "%s" (was: %s).''' % (extra_entry[0], str(e)))
					extra_found = True
					break

			if not extra_found :
				logging.warning('added missing %s record for group %s.' % (styles.stylize(styles.ST_PATH, GroupsList.configuration.extendedgroup_data_file), styles.stylize(styles.ST_NAME, GroupsList.groups[gid]['name'])))
				need_rewriting = True
				GroupsList.groups[gid]['description'] = ""
				GroupsList.groups[gid]['skel']        = ""
					
			gshadow_found = False
			for gshadow_entry in etc_gshadow :
				if GroupsList.groups[gid]['name'] ==  gshadow_entry[0] :
					try :
						GroupsList.groups[gid]['crypted_password'] = gshadow_entry[1]
					except IndexError, e :
						raise exceptions.CorruptFileError("/etc/gshadow", '''for group "%s" (was: %s).''' % (extra_entry[0], str(e)))
					gshadow_found = True
					break

			if not gshadow_found and is_allowed : 
				# do some auto-correction stuff if we are able too.
				# this happens if debian tools were used between 2 Licorn CLI calls, 
				# or on first call of CLI tools on a Debian/Ubuntu system.
				logging.warning('added missing %s record for group %s.' 
					% ( styles.stylize(styles.ST_PATH, '/etc/gshadow'), 
						styles.stylize(styles.ST_NAME, GroupsList.groups[gid]['name'])))
				need_rewriting = True
				GroupsList.groups[gid]['crypted_password'] = 'x'

		if need_rewriting and is_allowed :
			try :
				self.WriteConf()
			except (OSError, IOError), e :
				if self.warnings :
					logging.warning("licorn.core.groups: can't correct inconsistencies (was: %s)." % e)
	def SetProfiles(self, profiles) :
		GroupsList.profiles = profiles

	def WriteConf(self) :
		""" Write the groups data in appropriate system files."""

		if not GroupsList.groups[0].has_key('crypted_password') :
			logging.error("You are not root or member of the shadow group, can't write configuration data.")
		
		lock_etc_group   = file_locks.FileLock(self.configuration, "/etc/group")
		lock_etc_gshadow = file_locks.FileLock(self.configuration, "/etc/gshadow")
		lock_ext_group   = file_locks.FileLock(self.configuration, GroupsList.configuration.extendedgroup_data_file)

		logging.progress("Writing groups configuration to disk...")
		
		etcgroup   = []
		etcgshadow = []
		extgroup   = []

		gids = GroupsList.groups.keys()
		gids.sort()

		for gid in gids :
			#logging.debug2("Writing group %s (%s)." % (GroupsList.groups[gid]['name'], GroupsList.groups[gid]))

			etcgroup.append(":".join((
										GroupsList.groups[gid]['name'],
										GroupsList.groups[gid]['passwd'],
										str(gid),
										','.join(GroupsList.groups[gid]['members'])
									))
							)
			etcgshadow.append(":".join((
										GroupsList.groups[gid]['name'],
										GroupsList.groups[gid]['crypted_password'],
										"",
										','.join(GroupsList.groups[gid]['members'])
									))
							)
			extgroup.append(':'.join((
										GroupsList.groups[gid]['name'],
										GroupsList.groups[gid]['description'],
										GroupsList.groups[gid]['skel']
									))
							)

		lock_etc_group.Lock()
		open("/etc/group", "w").write("\n".join(etcgroup) + "\n")
		lock_etc_group.Unlock()

		lock_etc_gshadow.Lock()
		open("/etc/gshadow", "w").write("\n".join(etcgshadow) + "\n")
		lock_etc_gshadow.Unlock()

		lock_ext_group.Lock()
		open(GroupsList.configuration.extendedgroup_data_file, "w").write("\n".join(extgroup) + "\n")
		lock_ext_group.Unlock()

		logging.progress("Done writing groups configuration.")
	def HasGroup(self, name = None, gid = None) :
		"""Return true if the group or gid exists on the system. """

		if gid is None :
			return GroupsList.name_cache.has_key(name)

		if name is None :
			return GroupsList.groups.has_key(gid)
		
		raise exceptions.BadArgumentError("You must specify a GID or a name to test existence of.")
	def Select(self, filter_string) :
		""" Filter group accounts on different criteria :
			- 'system groups' : show only «system» groups (root, bin, daemon, apache...),
				not normal group account.
			- 'normal groups' : keep only «normal» groups, which includes Licorn administrators
			The criteria values are defined in /etc/{login.defs,adduser.conf}
		"""

		# see users.Select() for details
		self.filter_applied  = True
		self.filtered_groups = []

		if GroupsList.FILTER_STANDARD == filter_string :
			self.filtered_groups = filter(self.is_standard_gid, GroupsList.groups.keys())

		elif GroupsList.FILTER_SYSTEM == filter_string :
			self.filtered_groups = filter(self.is_system_gid, GroupsList.groups.keys())

		elif GroupsList.FILTER_PRIVILEGED == filter_string :
			for name in GroupsList.configuration.groups.privileges_whitelist :
				try :
					gid = GroupsList.name_to_gid(name)
					self.filtered_groups.append(gid)
				except exceptions.LicornRuntimeException :
					# this system group doesn't exist on the system
					pass

		elif GroupsList.FILTER_GUEST == filter_string :
			for gid in GroupsList.groups.keys() :
				if GroupsList.groups[gid]['name'].startswith(GroupsList.configuration.groups.guest_prefix) :
					self.filtered_groups.append(gid)

		elif GroupsList.FILTER_RESPONSIBLE == filter_string :
			for gid in GroupsList.groups.keys() :
				if GroupsList.groups[gid]['name'].startswith(GroupsList.configuration.groups.resp_prefix) :
					self.filtered_groups.append(gid)

		elif GroupsList.FILTER_EMPTY == filter_string :
			self.filtered_groups = filter(self.is_empty_gid, GroupsList.groups.keys())

		else :
			gid_re    = re.compile("^gid=(?P<gid>\d+)")
			gid_match = gid_re.match(filter_string)
			if gid_match is not None:
				gid = int(gid_match.group('gid'))
				self.filtered_groups.append(gid)

	def ExportCLI(self) :
		""" Export the groups list to human readable (= « getent group ») form.  """
		if self.filter_applied :
			gids = self.filtered_groups
		else :
			gids = GroupsList.groups.keys()
		gids.sort()
		
		def ExportOneGroupFromGid(gid, mygroups = GroupsList.groups) :
			""" Export groups the way UNIX getent does, separating fields with ":" """

			accountdata = [	GroupsList.groups[gid]['name'],
						mygroups[gid]['passwd'],
						str(gid) ]

			#
			# TODO: implement a fully compatible output with traditionnal getent
			# when there is no «long» option. For exemple, skel is an addition, it must
			# not be displayed (only when options.long).
			# HINT: put LICORN additions *after* standard getent values.
			#
			if self.is_system_gid(gid) :
				accountdata.extend( [ "", ",".join(mygroups[gid]['members']), mygroups[gid]['description'] ] )
			else :
				accountdata.extend( [ mygroups[gid]['skel'], ",".join(mygroups[gid]['members']),mygroups[gid]['description'] ] )

				if mygroups[gid]['permissive'] is None :
					accountdata.append("UNKNOWN")
				elif mygroups[gid]['permissive'] :
					accountdata.append("permissive")
				else :
					accountdata.append("NOT permissive")

			return ':'.join(accountdata)

		return "\n".join(map(ExportOneGroupFromGid, gids)) + "\n"
	def ExportXML(self) :
		""" Export the groups list to XML. """

		data = "<?xml version='1.0' encoding=\"UTF-8\"?>" + "\n" + "<groups-list>" + "\n"

		if self.filter_applied :
			gids = self.filtered_groups
		else :
			gids = GroupsList.groups.keys()
		gids.sort()

		for gid in gids :
			# TODO: put this into formatted strings.
			group = GroupsList.groups[gid]
			data += "	<group>\n" \
				+ "		<name>"			+ group['name'] + "</name>\n" \
				+ "		<passwd>" 		+ group['passwd'] + "</passwd>\n" \
				+ "		<gid>"			+ str(gid) + "</gid>\n" \
				+ "		<description>"			+ group['description'] + "</description>\n"
			if not self.is_system_gid(gid) :
				data += "		<skel>"			+ group['skel'] + "</skel>\n"
				if group['permissive'] is None :
					data += "		<permissive>[unknown]</permissive>\n"
				else :
					data += "		<permissive>"	+ str(group['permissive']) + "</permissive>\n"
				if group['members'] != "" :
					data += "		<members>" + ", ".join(group['members']) + "</members>\n"
			data += "	</group>\n"

		data += "</groups-list>\n"

		return data
	def AddGroup(self, name, gid=None, description="", skel="", system=False, permissive=False, batch=False) :
		""" Add an Licorn group (the group + the responsible group + the shared dir + permissions). """

		if name in (None, '') :
			raise exceptions.BadArgumentError, "You must specify a group name."
		if len(str(name)) > GroupsList.configuration.groups.name_maxlenght :
			raise exceptions.LicornRuntimeError, "Group name must be smaller than %d characters." % GroupsList.configuration.groups.name_maxlenght
		if description == '' :
			description = 'Les membres du groupe "%s"' % name
		if not system and skel is "" :
			raise exceptions.BadArgumentError, "You must specify a skel dir."

		if skel == "" :
			skel = GroupsList.configuration.users.default_skel
		elif skel not in GroupsList.configuration.users.skels :
			raise exceptions.BadArgumentError("The skel you specified doesn't exist on this system. Valid skels are : %s." 
				% GroupsList.configuration.users.skels)

		if description == '' :
			description = '''Les membres du groupe "%s"''' % name

		if not hlstr.cregex['group_name'].match(name) :
			raise exceptions.BadArgumentError("Malformed group name `%s', must match /%s/i."  
				% (name, styles.stylize(styles.ST_REGEX, hlstr.regex['group_name'])) )

		#logging.warning('descr: %s.' % description)

		if not hlstr.cregex['description'].match(description) :
			raise exceptions.BadArgumentError("Malformed group description `%s', must match /%s/i." 
				% (description, styles.stylize(styles.ST_REGEX, hlstr.regex['description'])))

		home = '%s/%s/%s' % (GroupsList.configuration.defaults.home_base_path,
			GroupsList.configuration.groups.names['plural'], name)

		# TODO: permit to specify GID. Currently this doesn't seem to be done yet.

		try :
			not_already_exists = True
			gid = self.__add_group(name, system, gid, description, skel)
			
		except exceptions.AlreadyExistsException, e:
			# don't bork if the group already exists, just continue.
			# some things could be missing (resp- , guest- , shared dir or ACLs),
			# it is a good idea to verify everything is really OK by continuing the
			# creation procedure.
			logging.notice(str(e))
			gid = GroupsList.name_to_gid(name)
			not_already_exists = False
		
		if system :
			# system groups don't have shared group dir nor resp- nor guest- nor special ACLs.
			# so we don't execute the rest of the procedure.
			self.WriteConf()
			if not_already_exists :
				logging.info(logging.SYSG_CREATED_GROUP % styles.stylize(styles.ST_NAME, name))

			return

		GroupsList.groups[gid]['permissive'] = permissive

		try :
			self.CheckGroups([ name ], minimal = True, batch = True)
			self.WriteConf()

			if not_already_exists :
				logging.info(logging.SYSG_CREATED_GROUP % styles.stylize(styles.ST_NAME, name))

		except exceptions.SystemCommandError, e :
			logging.warning ("ROLLBACK of group creation : " + str(e))

			import shutil
			shutil.rmtree(home)

			try :
				self.__delete_group(name)
			except : pass
			try :
				self.__delete_group('%s%s' % (GroupsList.configuration.groups.resp_prefix, name))
			except : pass
			try :
				self.__delete_group('%s%s' %(GroupsList.configuration.groups.guest_prefix, name))
			except : pass

			if not batch :
				self.WriteConf()

			# re-raise the exception, for the calling program to know what happened...
			raise e
		return (gid, name)
	def __add_group(self, name, system, manual_gid=None, description = "", skel = "") :
		"""Add a POSIX group, write the system data files. Return the gid of the group created."""

		try :
			# Verify existance of group, don't use name_to_gid() else the exception is not KeyError.
			# TODO: use "has_key()" and make these tests more readable (simple !!).
			existing_gid = GroupsList.name_cache[name]
			if manual_gid is None :
				# automatic GID selection upon creation.
				if system and self.is_system_gid(existing_gid) :
					raise exceptions.AlreadyExistsException ("The group %s already exists." % styles.stylize(styles.ST_NAME, name))
				else :
					raise exceptions.AlreadyExistsError("The group %s already exists but has not the same type. Please choose another name for your group." % styles.stylize(styles.ST_NAME, name))
			else :
				# user has manually specified a GID to affect upon creation.
				if system and self.is_system_gid(existing_gid) :
					if existing_gid == manual_gid :
						raise exceptions.AlreadyExistsException ("The group %s already exists." % styles.stylize(styles.ST_NAME, name))
					else :
						raise exceptions.AlreadyExistsError ("The group %s already exists with a different GID. Please check." % styles.stylize(styles.ST_NAME, name))
				else :
					raise exceptions.AlreadyExistsError ("The group %s already exists but has not the same type. Please choose another name for your group." % styles.stylize(styles.ST_NAME, name))
		except KeyError :
			# the group doesn't exist, its name is not in the cache.
			pass

		# Due to a bug of adduser perl script, we must check that there is no user which has 'name' as login
		# see https ://launchpad.net/distros/ubuntu/+source/adduser/+bug/45970 for details
		if GroupsList.users.login_cache.has_key(name) :
			raise exceptions.UpstreamBugException("A user account called %s already exists, this could trigger a bug"
				"in the Ubuntu adduser code when deleting the user. Please choose another name for your group."
				% styles.stylize(styles.ST_NAME, name))

		# Find a new GID
		if manual_gid is None :
			if system :
				gid = pyutils.next_free(GroupsList.groups.keys(), self.configuration.groups.system_gid_min, self.configuration.groups.system_gid_max)
			else :
				gid = pyutils.next_free(GroupsList.groups.keys(), self.configuration.groups.gid_min, self.configuration.groups.gid_max)
		else :
			gid = manual_gid

		# Add group in groups dictionary
		temp_group_dict             = { 'name' : name, 'passwd' : 'x', 'gid' : gid, 'members' : [],
										'description' : description, 'skel' : skel, 'crypted_password' : 'x' }

		if system :
			# we must fill the permissive status here, else WriteConf() will fail with a KeyError.
			# if not system, this has been filled elsewhere.
			temp_group_dict['permissive'] = False

		GroupsList.groups[gid]      = temp_group_dict
		GroupsList.name_cache[name] = gid

		return gid
	def DeleteGroup(self, name, del_users, no_archive, bygid = None, batch=False) :
		""" Delete an Licorn group
		"""
		if name is None and bygid is None :
			raise exceptions.BadArgumentError, "You must specify a name or a GID."

		if bygid :
			gid = bygid
			name = GroupsList.groups[gid]["name"]
		else :
			gid = self.name_to_gid(name)

		prim_memb = GroupsList.primary_members(GroupsList.groups[gid]["name"])
		
		if not del_users :
			# search if some users still have the group has their primary group
			if prim_memb != [] :
				raise exceptions.BadArgumentError, "The group still has members. You must delete them first, or force their automatic deletion with an option."

		home = '%s/%s/%s' % (GroupsList.configuration.defaults.home_base_path, GroupsList.configuration.groups.names['plural'], name)

		# Delete the group and its (primary) member(s) even if it is not empty
		if del_users :
			for login in prim_memb :
				GroupsList.users.DeleteUser(login, no_archive, batch=batch)

		if self.is_system_gid(gid) :
			self.__delete_group(name)
			# no more to do for a system group
			return

		# Delete the responsible and guest groups, then the group
		self.__delete_group('%s%s' % (GroupsList.configuration.groups.resp_prefix, name))
		self.__delete_group('%s%s' % (GroupsList.configuration.groups.guest_prefix, name))

		# Remove the shared dir
		if no_archive :
			import shutil
			shutil.rmtree(home)
		else :
			group_archive_dir = "%s/%s.deleted.%s" % (GroupsList.configuration.home_archive_dir, name, strftime("%Y%m%d-%H%M%S", gmtime()))
			try :
				os.rename(home, group_archive_dir)
				logging.info("Archived %s as %s." % (home, styles.stylize(styles.ST_PATH, group_archive_dir)))
			except OSError, e :
				if e.errno == 2 :
					# fix #608
					logging.warning("Can't archive %s, it doesn't exist !" % styles.stylize(styles.ST_PATH, home))
				else :
					raise e

		self.CheckGroupSymlinks(gid = gid, group = name, delete = True, batch = True)
		self.__delete_group(name)
			
	def __delete_group(self, name) :
		""" Delete a POSIX group."""

		# Remove the group in the groups list of profiles
		GroupsList.profiles.delete_group_in_profiles(name)

		del(GroupsList.groups[GroupsList.name_cache[name]])
		del(GroupsList.name_cache[name])

		self.WriteConf()

		logging.info(logging.SYSG_DELETED_GROUP % styles.stylize(styles.ST_NAME, name))

	def RenameGroup(self, profilelist, name, new_name) :
		""" Modify the name of a group."""

		raise NotImplementedError("This function is disabled, it is not yet complete.")

		if name is None :
			raise exceptions.BadArgumentError, "You must specify a name."
		if new_name is None :
			raise exceptions.BadArgumentError, "You must specify a new name."
		try :
			self.name_to_gid(new_name)

		except exceptions.LicornRuntimeException : # new_name is not an existing group

			gid 		= self.name_to_gid(name)
			home		= "%s/%s/%s" % (GroupsList.configuration.defaults.home_base_path,
				GroupsList.configuration.groups.names['plural'], GroupsList.groups[gid]['name'])
			new_home	= "%s/%s/%s" % (GroupsList.configuration.defaults.home_base_path,
				GroupsList.configuration.groups.names['plural'], new_name)

			GroupsList.groups[gid]['name'] = new_name

			if not self.is_system_gid(gid) :
				tmpname = GroupsList.configuration.groups.resp_prefix + name
				resp_gid = self.name_to_gid(tmpname)
				GroupsList.groups[resp_gid]['name'] = tmpname
				GroupsList.name_cache[tmpname] = resp_gid

				tmpname = GroupsList.configuration.groups.guest_prefix + name
				guest_gid = self.name_to_gid(tmpname)
				GroupsList.groups[guest_gid]['name'] = tmpname
				GroupsList.name_cache[tmpname] = guest_gid

				del tmpname

				os.rename(home, new_home) # Rename shared dir

				# reapply new ACLs on shared group dir.
				self.CheckGroups( [ new_name ], batch = True)

				# delete symlinks to the old name... and create new ones.
				self.CheckGroupSymlinks(gid, oldname = name, batch = True)

			# The name has changed, we have to update profiles
			profilelist.change_group_name_in_profiles(name, new_name)

			# update GroupsList.users.users[*]['groups']
			for u in GroupsList.users.users :
				try :
					i = GroupsList.users.users[u]['groups'].index(name)
				except ValueError : pass # user u is not in the group which was renamed
				else :
					GroupsList.users.users[u]['groups'][i] = new_name
			
			self.WriteConf()

		#
		# TODO : parse members, and sed -ie ~/.recently_used and other user files...
		# this will not work for OOo files with links to images files (not included in documents), etc.
		#

		else :
			raise exceptions.AlreadyExistsError("the new name you have choosen, %s, is already taken by another group !" % styles.stylize(styles.ST_NAME, new_name))
	def ChangeGroupDescription(self, name, description) :
		""" Change the description of a group
		"""
		if name is None :
			raise exceptions.BadArgumentError, "You must specify a name"
		if description is None :
			raise exceptions.BadArgumentError, "You must specify a description"

		gid = self.name_to_gid(name)
		GroupsList.groups[gid]['description'] = description

		self.WriteConf()
	def ChangeGroupSkel(self, name, skel) :
		""" Change the description of a group
		"""
		if name is None :
			raise exceptions.BadArgumentError, "You must specify a name"
		if skel is None :
			raise exceptions.BadArgumentError, "You must specify a skel"

		if not skel in GroupsList.configuration.users.skels :
			raise exceptions.BadArgumentError("The skel you specified doesn't exist on this system. Valid skels are : %s." % str(GroupsList.configuration.users.skels))

		gid = self.name_to_gid(name)
		GroupsList.groups[gid]['skel'] = skel

		self.WriteConf()
	def AddGrantedProfiles(self, users, profiles, name) :
		""" Allow the users of the profiles given to access to the shared dir
			Warning : Don't give [] for profiles, but [""]
		"""
		if name is None :
			raise exceptions.BadArgumentError, "You must specify a group name to add."

		assert(GroupsList.profiles != None)

		# TODO: verify group is valid !! (regex match and exists on the system)

		# The profiles exist ? Delete bad profiles
		for p in profiles :
			if p in GroupsList.profiles :
				# Add the group in groups list of profiles
				if name in GroupsList.profiles[p]['groups'] :
					logging.progress("Group %s already in the list of profile %s." % (styles.stylize(styles.ST_NAME, name), styles.stylize(styles.ST_NAME, p)) )
				else :
					profiles.AddGroupsInProfile([name])
					logging.info("Added group %s in the groups list of profile %s." % (styles.stylize(styles.ST_NAME, name), styles.stylize(styles.ST_NAME, p)) )
					# Add all 'p''s users in the group 'name'
					_users_to_add = self.__find_group_members(users, GroupsList.profiles[p]['primary_group'])
					self.AddUsersInGroup(name, _users_to_add, users)
			else :
				logging.warning("Profile %s doesn't exist, ignored." % styles.stylize(styles.ST_NAME, p))

		self.WriteConf()
	def DeleteGrantedProfiles(self, users, profiles, name) :
		""" Disallow the users of the profiles given to access to the shared dir. """

		if name is None :
			raise exceptions.BadArgumentError, "You must specify a name"

		assert(GroupsList.profiles != None)

		# The profiles exist ?
		for p in profiles :
			if p in profiles.profiles :
				# Delete the group from groups list of profiles
				if name in profiles.profiles[p]['groups'] :
					print "Delete group '" + name + "' from the groups list of the profile '" + p + "'"
					profiles.DeleteGroupsFromProfile([name])
					# Delete all 'p''s users from the group 'name'
					_users_to_del = self.__find_group_members(users, profiles.profiles[p]['primary_group'])
					self.RemoveUsersFromGroup(name, _users_to_del, users)
				else :
					print "The group '" + name + "' is not present in groups list of the profile '" + p + "'"
			else :
				print "Profile '" + str(p) + "' doesn't exist, it's ignored"

		self.WriteConf()
	def AddUsersInGroup(self, name, users_to_add, batch=False) :
		""" Add a user list in the group 'name'. """

		if name is None :
			raise exceptions.BadArgumentError, "You must specify a group name"
		if users_to_add is None :
			raise exceptions.BadArgumentError, "You must specify a users list"

		# remove inexistant users from users_to_add
		tmp = []
		for login in users_to_add :
			uid = self.users.login_to_uid(login)
			try :
				self.users.users[uid]
			except KeyError :
				continue
			else :
				tmp.append(login)
		users_to_add = tmp

		gid = self.name_to_gid(name)

		for u in users_to_add :
			if u == "" : continue

			if u in GroupsList.groups[gid]['members'] :
				logging.progress("User %s is already a member of %s, skipped." % (styles.stylize(styles.ST_LOGIN, u), styles.stylize(styles.ST_NAME, name)))
			else :
				GroupsList.groups[gid]['members'].append(u)

				logging.info("Added user %s to members of %s." % (styles.stylize(styles.ST_LOGIN, u), styles.stylize(styles.ST_NAME, name)) )

				# update the users cache.
				GroupsList.users.users[GroupsList.users.login_to_uid(u)]['groups'].add(name)
				
				if not batch :
					self.WriteConf()
				
				if self.is_standard_gid(gid) :
					# create the symlink to the shared group dir in the user's home dir.
					link_basename = GroupsList.groups[gid]['name']
				elif name.startswith(GroupsList.configuration.groups.resp_prefix) :
					# fix #587 : make symlinks for resps and guests too.
					link_basename = GroupsList.groups[gid]['name'].replace(GroupsList.configuration.groups.resp_prefix, "", 1)
				elif name.startswith(GroupsList.configuration.groups.guest_prefix) :
					link_basename = GroupsList.groups[gid]['name'].replace(GroupsList.configuration.groups.guest_prefix, "", 1)
				else :
					# this is a system group, don't make any symlink !
					continue
				
				uid      = GroupsList.users.login_to_uid(u)
				link_src = os.path.join(GroupsList.configuration.defaults.home_base_path, GroupsList.configuration.groups.names['plural'], link_basename)
				link_dst = os.path.join(GroupsList.users.users[uid]['homeDirectory'], link_basename)
				fsapi.make_symlink(link_src, link_dst)

	def RemoveUsersFromGroup(self, name, users_to_remove, batch=False) :
		""" Delete a users list in the group 'name'. """
		if name is None :
			raise exceptions.BadArgumentError, "You must specify a name"
		if users_to_remove is None :
			raise exceptions.BadArgumentError, "You must specify a users list"

		# remove inexistant users from users_to_remove
		tmp = []
		for login in users_to_remove :
			uid = self.users.login_to_uid(login)
			try :
				self.users.users[uid]
			except KeyError :
				continue
			else :
				tmp.append(login)
		users_to_remove = tmp

		logging.progress("Going to remove users %s from group %s." % (styles.stylize(styles.ST_NAME, str(users_to_remove)), styles.stylize(styles.ST_NAME, name)) )

		gid = self.name_to_gid(name)

		for u in users_to_remove :
			if u == "" : continue

			if u in GroupsList.groups[gid]['members'] :
				index = GroupsList.groups[gid]['members'].index(u)
				del(GroupsList.groups[gid]['members'][index])
				# update the users cache
				try :
					GroupsList.users.users[GroupsList.users.login_to_uid(u)]['groups'].remove(name)
				except ValueError :
					# don't bork if the group is not in the cache : when removing a user from a group, we don't
					# rebuild the cache before removing it, hence the cache is totally empty (this happens only
					# because all licorn operations are deconnected between each other, this wouldn't happen if
					# we had an Licorn daemon).
					pass

				#logging.debug("groups of user %s are now : %s " % (u, GroupsList.users.users[GroupsList.users.login_to_uid(u)]['groups']))
				
				self.WriteConf()
				
				if not self.is_system_gid(gid) :
					# delete the shared group dir symlink in user's home.
					uid      = GroupsList.users.login_to_uid(u)
					link_src = os.path.join(GroupsList.configuration.defaults.home_base_path,
						GroupsList.configuration.groups.names['plural'], GroupsList.groups[gid]['name'])

					for link in fsapi.minifind(GroupsList.users.users[uid]['homeDirectory'], maxdepth = 2, type = stat.S_IFLNK) :
						try :
							if os.path.abspath(os.readlink(link)) == link_src :
								os.unlink(link)
								logging.info("Deleted symlink %s." % styles.stylize(styles.ST_LINK, link) )
						except (IOError, OSError), e :
							if e.errno == 2 :
								# this is a broken link, readlink failed...
								pass
							else :
								raise exceptions.LicornRuntimeError("Unable to delete symlink %s (was: %s)." % (styles.stylize(styles.ST_LINK, link), str(e)) )
				logging.info("Removed user %s from members of %s." % (styles.stylize(styles.ST_LOGIN, u), styles.stylize(styles.ST_NAME, name)) )
			else :
				logging.progress("User %s is already not a member of %s, skipped." % (styles.stylize(styles.ST_LOGIN, u), styles.stylize(styles.ST_NAME, name)))

	def BuildGroupACL(self, gid, path = "") :
		""" Return an ACL triolet (a dict) that will be used to check something in the group shared dir.
			path must be the name of a file/dir, relative from group_home (this will help affining the ACL).
			EG : path in [ 'toto.odt', 'somedir', 'public_html/images/logo.img' ], etc.

			the "@GE" and "@UE" strings will be later replaced by individual execution bits of certain files
			which must be kept executable.
		"""

		group = GroupsList.groups[gid]['name']

		if GroupsList.groups[gid]['permissive'] :
			group_default_acl = "rwx"
			group_file_acl    = "rw@GE"
		else :
			group_default_acl = "r-x"
			group_file_acl    = "r-@GE"

		acl_base      = "u::rwx,g::---,o:---,g:%s:rwx,g:%s:r-x,g:%s:rwx" \
			% (GroupsList.configuration.defaults.admin_group, 
			GroupsList.configuration.groups.guest_prefix + group,
			GroupsList.configuration.groups.resp_prefix + group)
		file_acl_base = "u::rw@UE,g::---,o:---,g:%s:rw@GE,g:%s:r-@GE,g:%s:rw@GE" \
			% (GroupsList.configuration.defaults.admin_group,
			GroupsList.configuration.groups.guest_prefix + group,
			GroupsList.configuration.groups.resp_prefix + group)
		acl_mask      = "m:rwx"
		file_acl_mask = "m:rw@GE"

		if path.find("public_html") == 0 :
			return {
					'group'       : 'acl',
					'access_acl'  : "%s,g:%s:rwx,g:www-data:r-x,%s" % (acl_base,      group, acl_mask),
					'default_acl' : "%s,g:%s:%s,g:www-data:r-x,%s" %  (acl_base,      group, group_default_acl, acl_mask),
					'content_acl' : "%s,g:%s:%s,g:www-data:r--,%s" %  (file_acl_base, group, group_file_acl,    file_acl_mask),
					'exclude'     : []
				}
		else :
			return {
					'group'       : 'acl',
					'access_acl'  : "%s,g:%s:rwx,g:www-data:--x,%s" % (acl_base,      group, acl_mask),
					'default_acl' : "%s,g:%s:%s,%s" %                 (acl_base,      group, group_default_acl, acl_mask),
					'content_acl' : "%s,g:%s:%s,%s" %                 (file_acl_base, group, group_file_acl,    file_acl_mask),
					'exclude'     : [ 'public_html' ]
				}
	def CheckAssociatedSystemGroups(self, group, minimal = True, batch = False, auto_answer = None) :
		"""Check the system groups that a standard group need to fuction flawlessly.
			For example, a group "toto" need 2 system groups "resp-toto" and "guest-toto" for its ACLs.
		"""	

		all_went_ok = True

		for (prefix, title) in ( ( GroupsList.configuration.groups.resp_prefix, "responsables" ), ( GroupsList.configuration.groups.guest_prefix, "invités" ) ) :

			group_name = prefix + group
			logging.progress("Checking system group %s..." % styles.stylize(styles.ST_NAME, group_name))

			try :
				# FIXME : (convert this into an LicornKeyError ?) and use name_to_gid() inside of direct cache access.
				prefix_gid = GroupsList.name_cache[group_name]

			except KeyError :
				
				warn_message = logging.SYSG_SYSTEM_GROUP_REQUIRED % (styles.stylize(styles.ST_NAME, group_name), styles.stylize(styles.ST_NAME, group))

				if batch or logging.ask_for_repair(warn_message, auto_answer) :
					try :
						temp_gid = self.__add_group(group_name, system=True)
						GroupsList.groups[temp_gid]['description'] = "Les %s du groupe « %s »" % (title, group)
						GroupsList.groups[temp_gid]['skel'] = ""
						GroupsList.name_cache[ prefix[0] + group ] = temp_gid
						prefix_gid = temp_gid
						del(temp_gid)
						self.WriteConf()
						logging.info("Created system group %s." % styles.stylize(styles.ST_NAME, group_name))
					except exceptions.AlreadyExistsException, e :
						logging.notice(str(e))
						pass
				else :
					logging.warning(warn_message)
					all_went_ok &= False

			# WARNING : don't even try to remove() group_name from the list of groups_to_check.
			# this will not behave as expected because groups_to_check is used with map() and not
			# a standard for() loop. This will skip some groups, which will not be checked !! BAD !

			if not minimal :
				all_went_ok &= self.CheckGroupSymlinks(prefix_gid, strip_prefix = prefix, batch = batch, auto_answer = auto_answer)

		return all_went_ok

	def CheckGroups(self, groups_to_check = [], minimal = True, batch = False, auto_answer = None) :
		"""Check the groups, the cache. If not system, check the shared dir, the resps/guests, the members symlinks."""

		if groups_to_check == [] :
			groups_to_check = GroupsList.name_cache.keys()

		# dependancy : base dirs must be OK before checking groups shared dirs.
		GroupsList.configuration.CheckBaseDirs(minimal, batch, auto_answer)

		def check_group(group, minimal = minimal, batch = batch, auto_answer = auto_answer) :

			all_went_ok = True
			gid         = self.name_to_gid(group)

			if self.is_system_gid(gid) :
				return True

			logging.progress("Checking group %s..." % styles.stylize(styles.ST_NAME, group))
			
			all_went_ok &= self.CheckAssociatedSystemGroups(group, minimal, batch, auto_answer)

			group_home              = "%s/%s/%s" % (GroupsList.configuration.defaults.home_base_path, 
				GroupsList.configuration.groups.names['plural'], group)
			group_home_acl          = self.BuildGroupACL(gid)
			group_home_acl['path']  = group_home
			group_home_only         = group_home_acl.copy()
			group_home_only['path'] = group_home

			# check only the group home dir (not its contents), its uid/gid and its (default) ACL.
			# to check a dir without its content, just delete the content_acl or content_mode
			# dictionnary key.
			
			try :
				logging.progress("Checking shared group dir %s..." % styles.stylize(styles.ST_PATH,group_home))
				del group_home_only['content_acl']
				group_home_only['user'] = 'root'
				all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls([ group_home_only ], batch, auto_answer, self)

			except exceptions.LicornCheckError :
				logging.warning("Shared group dir %s is missing, please repair this first." % styles.stylize(styles.ST_PATH, group_home))
				return False

			# check the contents of the group home dir, without UID (fix #520 ; this is necessary for non-permissive groups
			# to be functionnal). this will recheck the home dir, but this 2nd check does less than the previous. The 
			# previous is necessary, and this one is unavoidable due to fsapi.check_dirs_and_contents_perms_and_acls() conception.
			logging.progress("Checking shared group dir contents...")
			all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls([ group_home_acl ], batch, auto_answer, self)
			
			public_html             = "%s/public_html" % group_home
			public_html_acl         = self.BuildGroupACL(gid, 'public_html')
			public_html_acl['path'] =  public_html
			public_html_only         = public_html_acl.copy()
			public_html_only['path'] = public_html

			try :
				logging.progress("Checking shared dir %s..." % styles.stylize(styles.ST_PATH, public_html))
				del public_html_only['content_acl']
				public_html_only['user'] = 'root'
				all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls([ public_html_only ], batch, auto_answer, self)

			except exceptions.LicornCheckError :
				logging.warning("Shared dir %s is missing, please repair this first." % styles.stylize(styles.ST_PATH, public_html))
				return False

			# check public_html contents, without UID too (#520).
			all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls([ public_html_acl ], batch, auto_answer, self)


			if not minimal :
				logging.progress("Checking %s symlinks in members homes, this can take a while..." % styles.stylize(styles.ST_NAME, group))
				all_went_ok &= self.CheckGroupSymlinks(gid, batch = batch, auto_answer = auto_answer)

				# TODO : tous les membres du groupe existent et sont OK (CheckUsers recursif)
				# WARNING : Forcer minimal = True pour éviter les checks récursifs avec CheckUsers()

			return all_went_ok

		if reduce(pyutils.keep_false, map(check_group, groups_to_check)) is False :
			# don't test just "if reduce() :", the result could be None and everything is OK when None
			raise exceptions.LicornCheckError("Some group(s) check(s) didn't pass, or weren't corrected.")
	def CheckGroupSymlinks(self, gid = None, group = None, oldname = None, delete = False, strip_prefix = None, batch = False, auto_answer = None) :
		"""For each member of a group, verify member has a symlink to the shared group dir inside his home (or under level 2 directory). If not, create the link. Eventually delete links pointing to the old group name if it is set."""

		if gid is None :
			gid = self.name_to_gid(group)

		if group is None :
			group = GroupsList.groups[gid]['name']

		all_went_ok = True

		for user in GroupsList.groups[gid]['members'] :

			uid = GroupsList.users.login_to_uid(user)

			link_not_found = True

			if strip_prefix is None :
				link_basename = GroupsList.groups[gid]['name']
			else :
				link_basename = GroupsList.groups[gid]['name'].replace(strip_prefix, '', 1)
			

			link_src = os.path.join(GroupsList.configuration.defaults.home_base_path, GroupsList.configuration.groups.names['plural'], link_basename)
			link_dst = os.path.join(GroupsList.users.users[uid]['homeDirectory'], link_basename)

			if oldname :
				link_src_old = os.path.join(GroupsList.configuration.defaults.home_base_path, GroupsList.configuration.groups.names['plural'], oldname)
			else :
				link_src_old = None

			for link in fsapi.minifind(GroupsList.users.users[uid]['homeDirectory'], maxdepth = 2, type = stat.S_IFLNK) :
				try :
					link_src_abs = os.path.abspath(os.readlink(link))
					if link_src_abs == link_src :
						if delete :
							try :
								os.unlink(link)
								logging.info("Deleted symlink %s." % styles.stylize(styles.ST_LINK, link) )
							except (IOError, OSError), e :
								if e.errno != 2 :
									raise exceptions.LicornRuntimeError("Unable to delete symlink %s (was: %s)." % (styles.stylize(styles.ST_LINK, link), str(e)) )
						else :	
							link_not_found = False
				except (IOError, OSError), e :
					# TODO: verify there's no bug in this logic ? pida signaled an error I didn't previously notice.
					#if e.errno == 2 and link_src_old and link_dst_old == os.readlink(link) :
					if e.errno == 2 and link_src_old and link_src_old == os.readlink(link) :
						# delete links to old group name.
						os.unlink(link)
						logging.info("Deleted old symlink %s." % styles.stylize(styles.ST_LINK, link) )
					else :
						# errno == 2 is a broken link, don't bother.
						raise exceptions.LicornRuntimeError("Unable to read symlink %s (error was : %s)." % (link, str(e)) )

			if link_not_found and not delete :
				warn_message = logging.SYSG_USER_LACKS_SYMLINK % (styles.stylize(styles.ST_LOGIN, user), styles.stylize(styles.ST_NAME, group))

				if batch or logging.ask_for_repair(warn_message, auto_answer) : 
					fsapi.make_symlink(link_src, link_dst)
				else :
					logging.warning(warn_message)
					all_went_ok = False

		return all_went_ok

	# TODO : make this @staticmethod
	def SetSharedDirPermissiveness(self, name = None, permissive = True) :
		""" Set permissive or not permissive the shared directory of the group 'name'. """
		if name is None :
			raise exceptions.BadArgumentError, "You must specify a group name."

		gid = self.name_to_gid(name)

		if permissive :
			qualif = ""
		else :
			qualif = " not"

		#print "trying to set %s, original %s." % (permissive, GroupsList.groups[gid]['permissive'])

		if GroupsList.groups[gid]['permissive'] != permissive :
			GroupsList.groups[gid]['permissive'] = permissive

			# auto-apply the new permissiveness
			self.CheckGroups( [ name ], batch = True)
		else :
			logging.progress("Group %s is already%s permissive." % (styles.stylize(styles.ST_NAME, name), qualif) )

	# TODO : make this @staticmethod
	def __is_permissive(self, name) :
		""" Return True if the shared dir of the group is permissive."""

		if self.is_system_group(name) :
			return None

		gid = self.name_to_gid(name)

		home = '%s/%s/%s' % (GroupsList.configuration.defaults.home_base_path, GroupsList.configuration.groups.names['plural'], name)

		try :
			# only check default ACLs, which is what we need for testing permissiveness.
			for line in posix1e.ACL(filedef=home) :
				if line.tag_type & posix1e.ACL_GROUP :
					if line.qualifier == gid :
						return line.permset.write
		except IOError, e :
			if e.errno == 13 :
				raise exceptions.InsufficientPermissionsError(str(e))
			elif e.errno == 2 :
				if self.warnings :
					logging.warning('''Shared dir %s doesn't exist, please run "licorn-check group --name %s" to fix.''' % (styles.stylize(styles.ST_PATH, home), styles.stylize(styles.ST_NAME, name)), once = True)
			else :
				raise exceptions.LicornIOError("IO error on %s (was : %s)." % (home, e))
		except ImportError, e :
			logging.warning(logging.MODULE_POSIX1E_IMPORT_ERROR % e, once = True)
			return None

	@staticmethod
	def primary_members(name) :
		"""Get the list of users which are in group 'name'."""
		ru    = []
		gid   = GroupsList.name_to_gid(name)

		for u in GroupsList.users.users :
			if GroupsList.users.users[u]['gid'] == gid :
				ru.append(GroupsList.users.users[u]['login'])
		return ru

	@staticmethod
	def auxilliary_members(name) :
		"""Return all members of a group, which are not members of this group in their primary group."""

		# TODO: really verify, for each user, that their member ship is not
		# duplicated between primary and auxilliary groups.
		
		return GroupsList.groups[GroupsList.name_to_gid(name)]['members']

	@staticmethod
	def all_members(name) :
		"""Return all members of a given group name."""
		
		return GroupsList.primary_members(name) + GroupsList.auxilliary_members(name)
		
	@staticmethod
	def name_to_gid(name) :
		""" Return the gid of the group 'name'."""

		try :
			# use the cache, Luke !
			return GroupsList.name_cache[name]
		except KeyError :
			try :
				int(name)
				logging.warning('''You passed a gid to name_to_gid() : %s (guess its name is "%s").''' % (styles.stylize(styles.ST_UGID, name), styles.stylize(styles.ST_NAME, GroupsList.groups[name]['name'])))
			except ValueError :
				pass
			raise exceptions.LicornRuntimeException, "The group `%s' doesn't exist." % name

	@staticmethod
	def is_system_gid(gid) :
		""" Return true if gid is system. """
		return gid < GroupsList.configuration.groups.gid_min or gid > GroupsList.configuration.groups.gid_max

	@staticmethod
	def is_standard_gid(gid) :
		""" Return true if gid is system. """
		logging.debug2("filtering %d against %d and %d." % (gid,  GroupsList.configuration.groups.gid_min, GroupsList.configuration.groups.gid_max))
		return gid >= GroupsList.configuration.groups.gid_min and gid <= GroupsList.configuration.groups.gid_max

	@staticmethod
	def is_system_group(name) :
		""" Return true if group is system. """
		try :
			return GroupsList.is_system_gid(GroupsList.name_to_gid(name))
		except KeyError :
			raise exceptions.LicornRuntimeException, "The group %s doesn't exist." % name

	@staticmethod
	def is_standard_group(name) :
		""" Return true if group is system. """
		try :
			return GroupsList.is_standard_gid(GroupsList.name_to_gid(name))
		except KeyError :
			raise exceptions.LicornRuntimeException, "The group `%s' doesn't exist." % name

	@staticmethod
	def is_empty_gid(gid) :
			return GroupsList.is_standard_gid(gid) and GroupsList.groups[gid]['members'] == []

	@staticmethod
	def is_empty_group(name) :
		try :
			return GroupsList.is_empty_gid(GroupsList.name_to_gid(name))
		except KeyError :
			raise exceptions.LicornRuntimeException, "The group `%s' doesn't exist." % name

	@staticmethod
	def make_name(inputname) :
		""" Make a valid login from  user's firstname and lastname."""

		maxlenght = GroupsList.configuration.groups.name_maxlenght
		groupname = inputname

		groupname = hlstr.validate_name(groupname, maxlenght = maxlenght)

		if not hlstr.cregex['group_name'].match(groupname) :
			raise exceptions.LicornRuntimeError('''Can't build a valid UNIX group name (got %s, which doesn't verify %s) with the string you provided "%s".''' % (groupname, hlstr.regex['group_name'], inputname) )
			
		return groupname

		# TODO : verify if the group doesn't already exist.
		#while potential in UsersList.users :
