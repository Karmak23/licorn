# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2006 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""

import os, stat, posix1e, re
from time import strftime, gmtime

from licorn.foundations        import logging, exceptions, hlstr, styles
from licorn.foundations        import fsapi, pyutils
from licorn.foundations.ltrace import ltrace

class GroupsController:
	""" Manages the groups and the associated shared data on a Linux system. """

	groups       = None  # dict
	name_cache   = None  # dict

	# cross-references to other common objects
	configuration = None  # LicornConfiguration
	users         = None  # UsersController
	profiles      = None  # ProfilesController

	# Filters for Select() method.
	FILTER_STANDARD    = 1
	FILTER_SYSTEM      = 2
	FILTER_PRIVILEGED  = 3
	FILTER_GUEST       = 4
	FILTER_RESPONSIBLE = 5
	FILTER_EMPTY       = 6

	def __init__ (self, configuration, users, warnings = True):

		self.pretty_name = str(self.__class__).rsplit('.', 1)[1]

		GroupsController.configuration = configuration

		GroupsController.users = users
		users.SetGroups(self)

		self.warnings = warnings

		GroupsController.backends = configuration.backends

		for bkey in GroupsController.backends.keys() :
			if bkey=='prefered':
				continue
			GroupsController.backends[bkey].set_groups_controller(self)

		# see licorn.core.users for details
		self.filter_applied = False

		if GroupsController.groups is None:
			self.reload()

		configuration.groups.hidden = self.GetHiddenState()

		logging.progress('%s: new instance created.' % self.pretty_name)
	def __getitem__(self, item):
		return GroupsController.groups[item]
	def __setitem__(self, item, value):
		GroupsController.groups[item]=value
	def keys(self):
		return GroupsController.groups.keys()
	def reload(self):
		""" load or reload internal data structures from files on disk. """

		GroupsController.groups     = {}
		GroupsController.name_cache = {}

		for bkey in GroupsController.backends.keys():
			if bkey=='prefered':
				continue
			g, c = GroupsController.backends[bkey].load_groups()
			GroupsController.groups.update(g)
			GroupsController.name_cache.update(c)

	def GetHiddenState(self):
		""" See if /home/groups is readable or not.
		"""

		try:
			for line in posix1e.ACL( file='%s/%s' % (GroupsController.configuration.defaults.home_base_path,
				GroupsController.configuration.groups.names['plural']) ):
				if line.tag_type & posix1e.ACL_GROUP:
					#
					# FIXME: do not hardcode "users".
					#
					if line.qualifier == GroupsController.name_to_gid('users'):
						return not line.permset.read
		except exceptions.LicornRuntimeException:
			# the group "users" doesn't exist, or is not yet created.
			return None
		except (IOError, OSError), e:
			if e.errno == 13:
				LicornConfiguration.groups.hidden = None
			elif e.errno != 2:
				# 2 will be corrected in this function
				raise e

	def SetProfiles(self, profiles):
		GroupsController.profiles = profiles

	def WriteConf(self, gid=None):
		""" Save Configuration (internal data structure to disk). """

		ltrace('groups', '> WriteConf(%s)' % gid)

		if gid:
			GroupsController.backends[
				GroupsController.groups[gid]['backend']
				].save_group(gid)

		else:
			for bkey in GroupsController.backends.keys():
				if bkey=='prefered':
					continue
				GroupsController.backends[bkey].save_groups()

		ltrace('groups', '< WriteConf()')

	def Select(self, filter_string):
		""" Filter group accounts on different criteria:
			- 'system groups': show only «system» groups (root, bin, daemon, apache...),
				not normal group account.
			- 'normal groups': keep only «normal» groups, which includes Licorn administrators
			The criteria values are defined in /etc/{login.defs,adduser.conf}
		"""

		# see users.Select() for details
		self.filter_applied  = True
		self.filtered_groups = []

		if GroupsController.FILTER_STANDARD == filter_string:
			self.filtered_groups = filter(self.is_standard_gid, GroupsController.groups.keys())

		elif GroupsController.FILTER_SYSTEM == filter_string:
			self.filtered_groups = filter(self.is_system_gid, GroupsController.groups.keys())

		elif GroupsController.FILTER_PRIVILEGED == filter_string:
			for name in GroupsController.configuration.groups.privileges_whitelist:
				try:
					gid = GroupsController.name_to_gid(name)
					self.filtered_groups.append(gid)
				except exceptions.LicornRuntimeException:
					# this system group doesn't exist on the system
					pass

		elif GroupsController.FILTER_GUEST == filter_string:
			for gid in GroupsController.groups.keys():
				if GroupsController.groups[gid]['name'].startswith(GroupsController.configuration.groups.guest_prefix):
					self.filtered_groups.append(gid)

		elif GroupsController.FILTER_RESPONSIBLE == filter_string:
			for gid in GroupsController.groups.keys():
				if GroupsController.groups[gid]['name'].startswith(GroupsController.configuration.groups.resp_prefix):
					self.filtered_groups.append(gid)

		elif GroupsController.FILTER_EMPTY == filter_string:
			self.filtered_groups = filter(self.is_empty_gid, GroupsController.groups.keys())

		else:
			gid_re    = re.compile("^gid=(?P<gid>\d+)")
			gid_match = gid_re.match(filter_string)
			if gid_match is not None:
				gid = int(gid_match.group('gid'))
				self.filtered_groups.append(gid)

	def ExportCLI(self, long):
		""" Export the groups list to human readable (= « get group ») form.  """
		if self.filter_applied:
			gids = self.filtered_groups
		else:
			gids = GroupsController.groups.keys()
		gids.sort()

		def ExportOneGroupFromGid(gid, mygroups = GroupsController.groups):
			""" Export groups the way UNIX get does, separating fields with ":" """

			accountdata = [
				GroupsController.groups[gid]['name'],
				mygroups[gid]['userPassword'] \
					if mygroups[gid].has_key('userPassword') else '',
				str(gid) ]

			#
			# TODO: implement a fully compatible output with traditionnal get
			# when there is no «long» option. For exemple, skel is an addition, it must
			# not be displayed (only when options.long).
			# HINT: put LICORN additions *after* standard get values.
			#
			if self.is_system_gid(gid):
				accountdata.extend(
					[
						"",
						",".join(mygroups[gid]['memberUid']),
						mygroups[gid]['description'] \
							if mygroups[gid].has_key('description') else ''
					] )
			else:
				accountdata.extend(
					[
						mygroups[gid]['groupSkel'] \
							if mygroups[gid].has_key('groupSkel') else '',
						",".join(mygroups[gid]['memberUid']),
						mygroups[gid]['description'] \
							if mygroups[gid].has_key('description') else ''
					] )

				if mygroups[gid]['permissive'] is None:
					accountdata.append("UNKNOWN")
				elif mygroups[gid]['permissive']:
					accountdata.append("permissive")
				else:
					accountdata.append("NOT permissive")

			if long:
				accountdata.append('[%s]' % styles.stylize(
					styles.ST_LINK, mygroups[gid]['backend']))

			return ':'.join(accountdata)

		return "\n".join(map(ExportOneGroupFromGid, gids)) + "\n"
	def ExportXML(self, long):
		""" Export the groups list to XML. """

		data = ('''<?xml version='1.0' encoding=\"UTF-8\"?>\n'''
				'''<groups-list>\n''')

		if self.filter_applied:
			gids = self.filtered_groups
		else:
			gids = GroupsController.groups.keys()
		gids.sort()

		for gid in gids:
			# TODO: put this into formatted strings.
			group = GroupsController.groups[gid]
			data += "	<group>\n" \
				+ "		<name>"			+ group['name'] + "</name>\n" \
				+ "		<userPassword>" 		+ group['userPassword'] + "</userPassword>\n" \
				+ "		<gid>"			+ str(gid) + "</gid>\n" \
				+ "		<description>"			+ group['description'] + "</description>\n"
			if not self.is_system_gid(gid):
				data += "		<groupSkel>"			+ group['groupSkel'] + "</groupSkel>\n"
				if group['permissive'] is None:
					data += "		<permissive>[unknown]</permissive>\n"
				else:
					data += "		<permissive>"	+ str(group['permissive']) + "</permissive>\n"
				if group['memberUid'] != set():
					data += "		<memberUid>" + ", ".join(group['memberUid']) + "</memberUid>\n"
				if long:
					data += "		<backend>%s</backend>\n" %  group['backend']
			data += "	</group>\n"

		data += "</groups-list>\n"

		return data
	def AddGroup(self, name, gid=None, description="", groupSkel="",
		system=False, permissive=False, batch=False, force=False):
		""" Add a Licorn group (the group + the guest/responsible group +
			the shared dir + permissions (ACL)). """

		if name in (None, ''):
			raise exceptions.BadArgumentError("You must specify a group name.")

		if not hlstr.cregex['group_name'].match(name):
			raise exceptions.BadArgumentError(
				"Malformed group name '%s', must match /%s/i." % (name,
				styles.stylize(styles.ST_REGEX, hlstr.regex['group_name'])))

		if len(name) > GroupsController.configuration.groups.name_maxlenght:
			raise exceptions.LicornRuntimeError('''Group name must be '''
				'''smaller than %d characters.''' % \
					GroupsController.configuration.groups.name_maxlenght)

		ltrace('groups', '> AddGroup(%s)' % name)

		if not system and groupSkel is "":
			raise exceptions.BadArgumentError(
				"You must specify a groupSkel dir.")

		if groupSkel == "":
			groupSkel = GroupsController.configuration.users.default_skel
		elif groupSkel not in GroupsController.configuration.users.skels:
			raise exceptions.BadArgumentError('''The skel you specified '''
				'''doesn't exist on this system. Valid skels are: %s.'''
				% GroupsController.configuration.users.skels)

		if description == '':
			description = 'members of group “%s”' % name
		elif not hlstr.cregex['description'].match(description):
			raise exceptions.BadArgumentError('''Malformed group description '''
				''''%s', must match /%s/i.'''
				% (description, styles.stylize(
					styles.ST_REGEX, hlstr.regex['description'])))

		home = '%s/%s/%s' % (
			GroupsController.configuration.defaults.home_base_path,
			GroupsController.configuration.groups.names['plural'],
			name)

		# TODO: permit to specify GID.
		# Currently this doesn't seem to be done yet.

		try:
			not_already_exists = True
			gid = self.__add_group(name, system, gid, description, groupSkel,
				batch=batch, force=force)

		except exceptions.AlreadyExistsException, e:
			# don't bork if the group already exists, just continue.
			# some things could be missing (resp- , guest- , shared dir or ACLs),
			# it is a good idea to verify everything is really OK by continuing the
			# creation procedure.
			logging.notice(str(e))
			gid = GroupsController.name_to_gid(name)
			not_already_exists = False

		if system:

			if not_already_exists:
				logging.info(logging.SYSG_CREATED_GROUP % \
					styles.stylize(styles.ST_NAME, name))

			# system groups don't have shared group dir nor resp-
			# nor guest- nor special ACLs.
			# so we don't execute the rest of the procedure.
			return

		GroupsController.groups[gid]['permissive'] = permissive

		try:
			self.CheckGroups([ name ], minimal=True, batch=True, force=force)

			if not_already_exists:
				logging.info(logging.SYSG_CREATED_GROUP % \
					styles.stylize(styles.ST_NAME, name))

		except exceptions.SystemCommandError, e:
			logging.warning ("ROLLBACK of group creation: " + str(e))

			import shutil
			shutil.rmtree(home)

			try:
				self.__delete_group(name)
			except:
				pass
			try:
				self.__delete_group('%s%s' % (
					GroupsController.configuration.groups.resp_prefix, name))
			except:
				pass
			try:
				self.__delete_group('%s%s' % (
					GroupsController.configuration.groups.guest_prefix, name))
			except:
				pass

			# re-raise the exception, for the calling program to know what happened...
			raise e

		ltrace('groups', '< AddGroup(%s): gid %d' % (name, gid))
		return (gid, name)
	def __add_group(self, name, system, manual_gid=None, description = "",
		groupSkel = "", batch=False, force=False):
		""" Add a POSIX group, write the system data files.
			Return the gid of the group created."""

		ltrace('groups', '> __add_group(%s)'%name)

		try:
			# Verify existance of group, don't use name_to_gid() else the
			# exception is not KeyError.
			# TODO: use "has_key()" and make these tests more readable.
			existing_gid = GroupsController.name_cache[name]
			if manual_gid is None:
				# automatic GID selection upon creation.
				if system and self.is_system_gid(existing_gid):
					raise exceptions.AlreadyExistsException(
						"The group %s already exists." %
						styles.stylize(styles.ST_NAME, name))
				else:
					raise exceptions.AlreadyExistsError(
						'''The group %s already exists but has not the same '''
						'''type. Please choose another name for your group.'''
						% styles.stylize(styles.ST_NAME, name))
			else:
				# user has manually specified a GID to affect upon creation.
				if system and self.is_system_gid(existing_gid):
					if existing_gid == manual_gid:
						raise exceptions.AlreadyExistsException(
							"The group %s already exists." %
							styles.stylize(styles.ST_NAME, name))
					else:
						raise exceptions.AlreadyExistsError(
							'''The group %s already exists with a different '''
							'''GID. Please check.''' %
							styles.stylize(styles.ST_NAME, name))
				else:
					raise exceptions.AlreadyExistsError(
						'''The group %s already exists but has not the same '''
						'''type. Please choose another name for your group.'''
						% styles.stylize(styles.ST_NAME, name))
		except KeyError:
			# the group doesn't exist, its name is not in the cache.
			pass

		# Due to a bug of adduser perl script, we must check that there is
		# no user which has 'name' as login. For details, see
		# https://launchpad.net/distros/ubuntu/+source/adduser/+bug/45970
		if GroupsController.users.login_cache.has_key(name) and not force:
			raise exceptions.UpstreamBugException('''A user account called '''
				'''%s already exists, this could trigger a bug in the Ubuntu '''
				'''adduser code when deleting the user. Please choose '''
				'''another name for your group, or use --force argument if '''
				'''you really want to add this group on the system.'''
				% styles.stylize(styles.ST_NAME, name))

		# Find a new GID
		if manual_gid is None:
			if system:
				gid = pyutils.next_free(GroupsController.groups.keys(),
					self.configuration.groups.system_gid_min,
					self.configuration.groups.system_gid_max)
			else:
				gid = pyutils.next_free(GroupsController.groups.keys(),
					self.configuration.groups.gid_min,
					self.configuration.groups.gid_max)
		else:
			gid = manual_gid

		# Add group in groups dictionary
		temp_group_dict = {
			'name'        : name,
			'userPassword': 'x',
			'gidNumber'   : gid,
			'memberUid'   : set(),
			'description' : description,
			'groupSkel'   : groupSkel,
			'backend'     : GroupsController.backends['prefered'].name,
			'action'      : 'create'
			}

		if system:
			# we must fill the permissive status here, else WriteConf() will fail with a KeyError.
			# if not system, this has been filled elsewhere.
			temp_group_dict['permissive'] = False

		GroupsController.groups[gid]      = temp_group_dict
		GroupsController.name_cache[name] = gid

		# do not skip the write/save part, else future actions could fail. E.g.
		# when creating a group, skipping save() on rsp/gst group creation will
		# result in unaplicable ACLs because of (yet) non-existing groups in the
		# system files (or backends).
		# DO NOT UNCOMMENT: -- if not batch:
		GroupsController.groups[gid]['action'] = 'create'
		GroupsController.backends[
			GroupsController.groups[gid]['backend']
			].save_group(gid)

		ltrace('groups', '< __add_group(%s): gid %d.'% (name, gid))

		return gid
	def DeleteGroup(self, name, del_users, no_archive, bygid = None, batch=False):
		""" Delete an Licorn group
		"""
		if name is None and bygid is None:
			raise exceptions.BadArgumentError, "You must specify a name or a GID."

		if bygid:
			gid = bygid
			name = GroupsController.groups[gid]["name"]
		else:
			gid = self.name_to_gid(name)

		prim_memb = GroupsController.primary_members(name)

		if not del_users:
			# search if some users still have the group has their primary group
			if prim_memb != set():
				raise exceptions.BadArgumentError, "The group still has members. You must delete them first, or force their automatic deletion with an option."

		home = '%s/%s/%s' % (GroupsController.configuration.defaults.home_base_path, GroupsController.configuration.groups.names['plural'], name)

		# Delete the group and its (primary) member(s) even if it is not empty
		if del_users:
			for login in prim_memb:
				GroupsController.users.DeleteUser(login, no_archive,
					batch=batch)

		if self.is_system_gid(gid):
			# a system group has no data on disk (no shared directory), just
			# delete its system data and exit.
			self.__delete_group(name)
			return

		#
		# For a standard group, there are a few steps more :
		# 	- delete the responsible and guest groups,
		#	- then delete the symlinks and the group,
		#	- then the shared data.
		# For responsible and guests symlinks, don't do anything : all symlinks
		# point to <group_name>, not rsp-* / gst-*. No need to duplicate the
		# work.
		#
		self.__delete_group('%s%s' % (
			GroupsController.configuration.groups.resp_prefix, name))
		self.__delete_group('%s%s' % (
			GroupsController.configuration.groups.guest_prefix, name))

		self.CheckGroupSymlinks(gid = gid, group = name, delete=True,
			batch=True)
		self.__delete_group(name)

		#
		# the group information has been wiped out, remove or archive the shared
		# directory. If anything fails now, this is not a real problem, because
		# the system configuration data is safe. At worst, there is an orphaned
		# directory remaining in the arbo, which is harmless.
		#
		if no_archive:
			import shutil
			shutil.rmtree(home)
		else:
			group_archive_dir = "%s/%s.deleted.%s" % (
				GroupsController.configuration.home_archive_dir, name,
				strftime("%Y%m%d-%H%M%S", gmtime()))
			try:
				os.rename(home, group_archive_dir)
				logging.info("Archived %s as %s." % (home,
					styles.stylize(styles.ST_PATH, group_archive_dir)))
			except OSError, e:
				if e.errno == 2:
					# fix #608
					logging.warning("Can't archive %s, it doesn't exist !" % \
						styles.stylize(styles.ST_PATH, home))
				else:
					raise e

	def __delete_group(self, name):
		""" Delete a POSIX group."""

		# Remove the group in the groups list of profiles
		GroupsController.profiles.delete_group_in_profiles(name)

		try:

			gid     = GroupsController.name_cache[name]
			backend = GroupsController.groups[gid]['backend']

			del(GroupsController.groups[gid])
			del(GroupsController.name_cache[name])

			# delete the group in the backend after deleting it locally, else
			# Unix backend will not know what to delete (this is quite a hack).
			GroupsController.backends[backend].delete_group(name)

			logging.info(logging.SYSG_DELETED_GROUP % \
				styles.stylize(styles.ST_NAME, name))
		except KeyError:
			logging.warning(logging.SYSG_GROUP_DOESNT_EXIST % styles.stylize(
				styles.ST_NAME, name))

	def RenameGroup(self, profilelist, name, new_name):
		""" Modify the name of a group."""

		raise NotImplementedError("This function is disabled, it is not yet complete.")

		if name is None:
			raise exceptions.BadArgumentError, "You must specify a name."
		if new_name is None:
			raise exceptions.BadArgumentError, "You must specify a new name."
		try:
			self.name_to_gid(new_name)

		except exceptions.LicornRuntimeException: # new_name is not an existing group

			gid 		= self.name_to_gid(name)
			home		= "%s/%s/%s" % (GroupsController.configuration.defaults.home_base_path,
				GroupsController.configuration.groups.names['plural'], GroupsController.groups[gid]['name'])
			new_home	= "%s/%s/%s" % (GroupsController.configuration.defaults.home_base_path,
				GroupsController.configuration.groups.names['plural'], new_name)

			GroupsController.groups[gid]['name'] = new_name

			if not self.is_system_gid(gid):
				tmpname = GroupsController.configuration.groups.resp_prefix + name
				resp_gid = self.name_to_gid(tmpname)
				GroupsController.groups[resp_gid]['name'] = tmpname
				GroupsController.name_cache[tmpname] = resp_gid

				tmpname = GroupsController.configuration.groups.guest_prefix + name
				guest_gid = self.name_to_gid(tmpname)
				GroupsController.groups[guest_gid]['name'] = tmpname
				GroupsController.name_cache[tmpname] = guest_gid

				del tmpname

				os.rename(home, new_home) # Rename shared dir

				# reapply new ACLs on shared group dir.
				self.CheckGroups( [ new_name ], batch=True)

				# delete symlinks to the old name... and create new ones.
				self.CheckGroupSymlinks(gid, oldname=name, batch=True)

			# The name has changed, we have to update profiles
			profilelist.change_group_name_in_profiles(name, new_name)

			# update GroupsController.users.users[*]['groups']
			for u in GroupsController.users.users:
				try:
					i = GroupsController.users.users[u]['groups'].index(name)
				except ValueError: pass # user u is not in the group which was renamed
				else:
					GroupsController.users.users[u]['groups'][i] = new_name

			GroupsController.groups[gid]['action'] = 'rename'
			GroupsController.backends[
				GroupsController.groups[gid]['backend']
				].save_group(gid)

		#
		# TODO: parse members, and sed -ie ~/.recently_used and other user files...
		# this will not work for OOo files with links to images files (not included in documents), etc.
		#

		else:
			raise exceptions.AlreadyExistsError("the new name you have choosen, %s, is already taken by another group !" % styles.stylize(styles.ST_NAME, new_name))
	def ChangeGroupDescription(self, name, description):
		""" Change the description of a group
		"""
		if name is None:
			raise exceptions.BadArgumentError, "You must specify a name"
		if description is None:
			raise exceptions.BadArgumentError, "You must specify a description"

		gid = self.name_to_gid(name)
		GroupsController.groups[gid]['description'] = description

		GroupsController.groups[gid]['action'] = 'update'
		GroupsController.backends[
			GroupsController.groups[gid]['backend']
			].save_group(gid)

	def ChangeGroupSkel(self, name, groupSkel):
		""" Change the description of a group
		"""
		if name is None:
			raise exceptions.BadArgumentError, "You must specify a name"
		if groupSkel is None:
			raise exceptions.BadArgumentError, "You must specify a groupSkel"

		if not groupSkel in GroupsController.configuration.users.skels:
			raise exceptions.BadArgumentError("The skel you specified doesn't exist on this system. Valid skels are: %s." % str(GroupsController.configuration.users.skels))

		gid = self.name_to_gid(name)
		GroupsController.groups[gid]['groupSkel'] = groupSkel

		GroupsController.groups[gid]['action'] = 'update'
		GroupsController.backends[
			GroupsController.groups[gid]['backend']
			].save_group(gid)
	def AddGrantedProfiles(self, users, profiles, name):
		""" Allow the users of the profiles given to access to the shared dir
			Warning: Don't give [] for profiles, but [""]
		"""
		if name is None:
			raise exceptions.BadArgumentError, "You must specify a group name to add."

		assert(GroupsController.profiles != None)

		# TODO: verify group is valid !! (regex match and exists on the system)

		# The profiles exist ? Delete bad profiles
		for p in profiles:
			if p in GroupsController.profiles:
				# Add the group in groups list of profiles
				if name in GroupsController.profiles[p]['groups']:
					logging.progress("Group %s already in the list of profile %s." % (
						styles.stylize(styles.ST_NAME, name), styles.stylize(styles.ST_NAME, p)) )
				else:
					profiles.AddGroupsInProfile([name])
					logging.info("Added group %s in the groups list of profile %s." % (
						styles.stylize(styles.ST_NAME, name), styles.stylize(styles.ST_NAME, p)) )
					# Add all 'p''s users in the group 'name'
					_users_to_add = self.__find_group_members(users, GroupsController.profiles[p]['primary_group'])
					self.AddUsersInGroup(name, _users_to_add, users)
			else:
				logging.warning("Profile %s doesn't exist, ignored." % styles.stylize(styles.ST_NAME, p))

		#
		# FIXME: is it needed to save() here ? isn't it already done by the
		# profile() and the AddUsersInGroup() calls ?
		GroupsController.groups[gid]['action'] = 'update'
		GroupsController.backends[
			GroupsController.groups[gid]['backend']
			].save_group(gid)
	def DeleteGrantedProfiles(self, users, profiles, name):
		""" Disallow the users of the profiles given to access to the shared dir. """

		if name is None:
			raise exceptions.BadArgumentError, "You must specify a name"

		assert(GroupsController.profiles != None)

		# The profiles exist ?
		for p in profiles:
			if p in profiles.profiles:
				# Delete the group from groups list of profiles
				if name in profiles.profiles[p]['groups']:
					print "Delete group '" + name + "' from the groups list of the profile '" + p + "'"
					profiles.DeleteGroupsFromProfile([name])
					# Delete all 'p''s users from the group 'name'
					_users_to_del = self.__find_group_members(users, profiles.profiles[p]['primary_group'])
					self.RemoveUsersFromGroup(name, _users_to_del, users)
				else:
					print "The group '" + name + "' is not present in groups list of the profile '" + p + "'"
			else:
				print "Profile '" + str(p) + "' doesn't exist, it's ignored"

		# FIXME: same as preceding method: not already done ??
		self.WriteConf()
	def AddUsersInGroup(self, name, users_to_add, batch = False):
		""" Add a user list in the group 'name'. """

		if name is None:
			raise exceptions.BadArgumentError, "You must specify a group name"
		if users_to_add is None:
			raise exceptions.BadArgumentError, "You must specify a users list"

		ltrace('groups', '> AddUsersInGroup() %s->%s.' % (
			name, users_to_add))

		# remove non-existing users and duplicate logins from users_to_add
		tmp = {}
		for login in users_to_add:
			if login == '': continue

			try:
				uid = self.users.login_to_uid(login)
			except:
				logging.notice('Skipping non-existing user %s.' % login)
				continue
			else:
				tmp[login] = 1

		work_done = False
		users_to_add = tmp.keys()

		gid = self.name_to_gid(name)

		for u in users_to_add:
			if u in GroupsController.groups[gid]['memberUid']:
				logging.progress("User %s is already a member of %s, skipped." % (
					styles.stylize(styles.ST_LOGIN, u), styles.stylize(styles.ST_NAME, name)))
			else:
				GroupsController.groups[gid]['memberUid'].add(u)

				ltrace('groups', 'members are: %s.' % \
					GroupsController.groups[gid]['memberUid'])

				logging.info("Added user %s to members of %s." % (
					styles.stylize(styles.ST_LOGIN, u), styles.stylize(styles.ST_NAME, name)) )

				# update the users cache.
				GroupsController.users.users[
					GroupsController.users.login_to_uid(u)
					]['groups'].add(name)

				if batch:
					work_done = True
				else:
					#
					# save the group after each user addition.
					# this is a quite expansive operation, it seems to me quite
					# superflous, but you can make bets on security and
					# reliability.
					#
					GroupsController.groups[gid]['action'] = 'update'
					GroupsController.backends[
						GroupsController.groups[gid]['backend']
						].save_group(gid)

				if self.is_standard_gid(gid):
					# create the symlink to the shared group dir in the user's home dir.
					link_basename = GroupsController.groups[gid]['name']
				elif name.startswith(GroupsController.configuration.groups.resp_prefix):
					# fix #587: make symlinks for resps and guests too.
					link_basename = GroupsController.groups[gid]['name'].replace(
						GroupsController.configuration.groups.resp_prefix, "", 1)
				elif name.startswith(GroupsController.configuration.groups.guest_prefix):
					link_basename = GroupsController.groups[gid]['name'].replace(
						GroupsController.configuration.groups.guest_prefix, "", 1)
				else:
					# this is a system group, don't make any symlink !
					continue

				# brutal fix for #43, batched for convenience.
				self.AddUsersInGroup('users', [ u ], batch = True)

				uid      = GroupsController.users.login_to_uid(u)
				link_src = os.path.join(GroupsController.configuration.defaults.home_base_path,
					GroupsController.configuration.groups.names['plural'], link_basename)
				link_dst = os.path.join(GroupsController.users.users[uid]['homeDirectory'],
					link_basename)
				fsapi.make_symlink(link_src, link_dst, batch = batch)

		if batch and work_done:
			# save the group after having added all users. This seems more fine
			# than saving between each addition
			GroupsController.groups[gid]['action'] = 'update'
			GroupsController.backends[
				GroupsController.groups[gid]['backend']
				].save_group(gid)

		ltrace('groups', '< AddUsersInGroup() %s = %s.' % (
			name, GroupsController.groups[gid]['memberUid']))

	def RemoveUsersFromGroup(self, name, users_to_remove, batch=False):
		""" Delete a users list in the group 'name'. """
		if name is None:
			raise exceptions.BadArgumentError, "You must specify a name"
		if users_to_remove is None:
			raise exceptions.BadArgumentError, "You must specify a users list"

		# remove inexistant users from users_to_remove
		tmp = []
		for login in users_to_remove:
			uid = self.users.login_to_uid(login)
			try:
				self.users.users[uid]
			except KeyError:
				continue
			else:
				tmp.append(login)
		users_to_remove = tmp
		work_done = False

		logging.progress("Going to remove users %s from group %s." % (
			styles.stylize(styles.ST_NAME, str(users_to_remove)),
			styles.stylize(styles.ST_NAME, name)) )

		gid = self.name_to_gid(name)

		for u in users_to_remove:
			if u == "": continue

			if u in GroupsController.groups[gid]['memberUid']:
				GroupsController.groups[gid]['memberUid'].remove(u)
				# update the users cache
				try:
					GroupsController.users.users[GroupsController.users.login_to_uid(u)]['groups'].remove(name)
				except ValueError:
					# don't bork if the group is not in the cache: when removing a user from a group, we don't
					# rebuild the cache before removing it, hence the cache is totally empty (this happens only
					# because all licorn operations are deconnected between each other, this wouldn't happen if
					# we had an Licorn daemon).
					pass

				#logging.debug("groups of user %s are now: %s " % (u, GroupsController.users.users[GroupsController.users.login_to_uid(u)]['groups']))
				if batch:
					work_done = True
				else:
					GroupsController.groups[gid]['action'] = 'update'
					GroupsController.backends[
						GroupsController.groups[gid]['backend']
						].save_group(gid)

				if not self.is_system_gid(gid):
					# delete the shared group dir symlink in user's home.
					uid      = GroupsController.users.login_to_uid(u)
					link_src = os.path.join(GroupsController.configuration.defaults.home_base_path,
						GroupsController.configuration.groups.names['plural'], GroupsController.groups[gid]['name'])

					for link in fsapi.minifind(GroupsController.users.users[uid]['homeDirectory'], maxdepth = 2, type = stat.S_IFLNK):
						try:
							if os.path.abspath(os.readlink(link)) == link_src:
								os.unlink(link)
								logging.info("Deleted symlink %s." % styles.stylize(styles.ST_LINK, link) )
						except (IOError, OSError), e:
							if e.errno == 2:
								# this is a broken link, readlink failed...
								pass
							else:
								raise exceptions.LicornRuntimeError("Unable to delete symlink %s (was: %s)." % (styles.stylize(styles.ST_LINK, link), str(e)) )
				logging.info("Removed user %s from members of %s." % (styles.stylize(styles.ST_LOGIN, u), styles.stylize(styles.ST_NAME, name)) )
			else:
				logging.progress("User %s is already not a member of %s, skipped." % (styles.stylize(styles.ST_LOGIN, u), styles.stylize(styles.ST_NAME, name)))

		if batch and work_done:
			GroupsController.groups[gid]['action'] = 'update'
			GroupsController.backends[
				GroupsController.groups[gid]['backend']
				].save_group(gid)

	def BuildGroupACL(self, gid, path = ""):
		""" Return an ACL triolet (a dict) that will be used to check something in the group shared dir.
			path must be the name of a file/dir, relative from group_home (this will help affining the ACL).
			EG: path in [ 'toto.odt', 'somedir', 'public_html/images/logo.img' ], etc.

			the "@GE" and "@UE" strings will be later replaced by individual execution bits of certain files
			which must be kept executable.
		"""

		group = GroupsController.groups[gid]['name']

		if GroupsController.groups[gid]['permissive']:
			group_default_acl = "rwx"
			group_file_acl    = "rw@GE"
		else:
			group_default_acl = "r-x"
			group_file_acl    = "r-@GE"

		acl_base      = "u::rwx,g::---,o:---,g:%s:rwx,g:%s:r-x,g:%s:rwx" \
			% (GroupsController.configuration.defaults.admin_group,
			GroupsController.configuration.groups.guest_prefix + group,
			GroupsController.configuration.groups.resp_prefix + group)
		file_acl_base = "u::rw@UE,g::---,o:---,g:%s:rw@GE,g:%s:r-@GE,g:%s:rw@GE" \
			% (GroupsController.configuration.defaults.admin_group,
			GroupsController.configuration.groups.guest_prefix + group,
			GroupsController.configuration.groups.resp_prefix + group)
		acl_mask      = "m:rwx"
		file_acl_mask = "m:rw@GE"

		if path.find("public_html") == 0:
			return {
					'group'     : 'acl',
					'access_acl': "%s,g:%s:rwx,g:www-data:r-x,%s" % (acl_base,      group, acl_mask),
					'default_acl': "%s,g:%s:%s,g:www-data:r-x,%s" %  (acl_base,      group, group_default_acl, acl_mask),
					'content_acl': "%s,g:%s:%s,g:www-data:r--,%s" %  (file_acl_base, group, group_file_acl,    file_acl_mask),
					'exclude'   : []
				}
		else:
			return {
					'group'     : 'acl',
					'access_acl': "%s,g:%s:rwx,g:www-data:--x,%s" % (acl_base,      group, acl_mask),
					'default_acl': "%s,g:%s:%s,%s" %                 (acl_base,      group, group_default_acl, acl_mask),
					'content_acl': "%s,g:%s:%s,%s" %                 (file_acl_base, group, group_file_acl,    file_acl_mask),
					'exclude'   : [ 'public_html' ]
				}
	def CheckAssociatedSystemGroups(self, group, minimal=True, batch=False,
		auto_answer=None, force=False):
		"""Check the system groups that a standard group need to fuction flawlessly.
			For example, a group "toto" need 2 system groups "resp-toto" and "guest-toto" for its ACLs.
		"""

		all_went_ok = True

		for (prefix, title) in ( ( GroupsController.configuration.groups.resp_prefix, "responsibles" ), ( GroupsController.configuration.groups.guest_prefix, "guests" ) ):

			group_name = prefix + group
			logging.progress("Checking system group %s..." % styles.stylize(styles.ST_NAME, group_name))

			try:
				# FIXME: (convert this into an LicornKeyError ?) and use name_to_gid() inside of direct cache access.
				prefix_gid = GroupsController.name_cache[group_name]

			except KeyError:

				warn_message = logging.SYSG_SYSTEM_GROUP_REQUIRED % (styles.stylize(styles.ST_NAME, group_name), styles.stylize(styles.ST_NAME, group))

				if batch or logging.ask_for_repair(warn_message, auto_answer):
					try:
						temp_gid = self.__add_group(group_name,
							system=True,
							manual_gid=None,
							description="%s of group “%s”" % (title, group),
							groupSkel="", batch=batch, force=force)
						GroupsController.name_cache[ prefix[0] + group ] = temp_gid
						prefix_gid = temp_gid
						del(temp_gid)

						logging.info("Created system group %s." % styles.stylize(styles.ST_NAME, group_name))
					except exceptions.AlreadyExistsException, e:
						logging.notice(str(e))
						pass
				else:
					logging.warning(warn_message)
					all_went_ok &= False

			# WARNING: don't even try to remove() group_name from the list of groups_to_check.
			# this will not behave as expected because groups_to_check is used with map() and not
			# a standard for() loop. This will skip some groups, which will not be checked !! BAD !

			if not minimal:
				all_went_ok &= self.CheckGroupSymlinks(prefix_gid,
					strip_prefix=prefix, batch=batch, auto_answer=auto_answer,
					force=false)

		return all_went_ok

	def __check_group(self, group, minimal=True, batch=False, auto_answer=None,
		force=False):

		all_went_ok = True
		gid         = self.name_to_gid(group)

		if self.is_system_gid(gid):
			return True

		logging.progress("Checking group %s..." % styles.stylize(styles.ST_NAME, group))

		all_went_ok &= self.CheckAssociatedSystemGroups(group, minimal, batch, auto_answer)

		group_home              = "%s/%s/%s" % (GroupsController.configuration.defaults.home_base_path,
			GroupsController.configuration.groups.names['plural'], group)
		group_home_acl          = self.BuildGroupACL(gid)
		group_home_acl['path']  = group_home

		if os.path.exists("%s/public_html" % group_home):
			group_home_acl['exclude'] = [ 'public_html' ]


		# follow the symlink for the group home, only if link destination is a dir.
		# this allows administrator to put big group dirs on different volumes (fixes #66).

		if os.path.islink(group_home):
			if os.path.exists(group_home) and os.path.isdir(os.path.realpath(group_home)):
				group_home = os.path.realpath(group_home)
				group_home_acl['path']  = group_home

		# check only the group home dir (not its contents), its uid/gid and its (default) ACL.
		# to check a dir without its content, just delete the content_acl or content_mode
		# dictionnary key.

		try:
			logging.progress("Checking shared group dir %s..." % \
				styles.stylize(styles.ST_PATH, group_home))
			group_home_only         = group_home_acl.copy()
			group_home_only['path'] = group_home
			group_home_only['user'] = 'root'
			del group_home_only['content_acl']
			all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
				[ group_home_only ], batch, auto_answer, self, self.users)

		except exceptions.LicornCheckError:
			logging.warning("Shared group dir %s is missing, please repair this first." \
				% styles.stylize(styles.ST_PATH, group_home))
			return False

		# check the contents of the group home dir, without checking UID (fix old#520;
		# this is necessary for non-permissive groups to be functionnal). this will
		# recheck the home dir, but this 2nd check does less than the previous. The
		# previous is necessary, and this one is unavoidable due to
		# fsapi.check_dirs_and_contents_perms_and_acls() conception.
		logging.progress("Checking shared group dir contents...")
		all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
			[ group_home_acl ], batch, auto_answer, self, self.users)

		if os.path.exists("%s/public_html" % group_home):
			public_html             = "%s/public_html" % group_home
			public_html_acl         = self.BuildGroupACL(gid, 'public_html')
			public_html_acl['path'] =  public_html

			try:
				logging.progress("Checking shared dir %s..." % \
					styles.stylize(styles.ST_PATH, public_html))
				public_html_only         = public_html_acl.copy()
				public_html_only['path'] = public_html
				public_html_only['user'] = 'root'
				del public_html_only['content_acl']
				all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
					[ public_html_only ],
					batch, auto_answer, self, self.users)

			except exceptions.LicornCheckError:
				logging.warning(
					"Shared dir %s is missing, please repair this first." \
					% styles.stylize(styles.ST_PATH, public_html))
				return False

			# check only ~group/public_html and its contents, without checking UID, too.
			all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
				[ public_html_acl ], batch, auto_answer, self, self.users)

		if not minimal:
			logging.progress(
				"Checking %s symlinks in members homes, this can take a while..." \
				% styles.stylize(styles.ST_NAME, group))
			all_went_ok &= self.CheckGroupSymlinks(gid, batch=batch,
				auto_answer=auto_answer)

			# TODO: tous les membres du groupe existent et sont OK (CheckUsers recursif)
			# WARNING: Forcer minimal = True pour éviter les checks récursifs avec CheckUsers()

		return all_went_ok

	def CheckGroups(self, groups_to_check = [], minimal=True, batch=False,
		auto_answer=None, force=False):
		"""Check the groups, the cache. If not system, check the shared dir, the resps/guests, the members symlinks."""

		if groups_to_check == []:
			groups_to_check = GroupsController.name_cache.keys()

		# dependancy: base dirs must be OK before checking groups shared dirs.
		GroupsController.configuration.CheckBaseDirs(minimal, batch, auto_answer)

		def _chk(group):
			return self.__check_group(group, minimal=minimal, batch=batch,
				auto_answer=auto_answer, force=force)

		if reduce(pyutils.keep_false, map(_chk, groups_to_check)) is False:
			# don't test just "if reduce(…):", the result could be None and everything is OK when None
			raise exceptions.LicornCheckError("Some group(s) check(s) didn't pass, or weren't corrected.")
	def CheckGroupSymlinks(self, gid=None, group=None, oldname=None,
		delete=False, strip_prefix=None, batch=False, auto_answer=None):
		"""For each member of a group, verify member has a symlink to the shared group dir inside his home (or under level 2 directory). If not, create the link. Eventually delete links pointing to the old group name if it is set."""

		if gid is None:
			gid = self.name_to_gid(group)

		if group is None:
			group = GroupsController.groups[gid]['name']

		all_went_ok = True

		for user in GroupsController.groups[gid]['memberUid']:

			uid = GroupsController.users.login_to_uid(user)

			link_not_found = True

			if strip_prefix is None:
				link_basename = GroupsController.groups[gid]['name']
			else:
				link_basename = GroupsController.groups[gid]['name'].replace(strip_prefix, '', 1)


			link_src = os.path.join(
				GroupsController.configuration.defaults.home_base_path,
				GroupsController.configuration.groups.names['plural'],
				link_basename)

			link_dst = os.path.join(
				GroupsController.users.users[uid]['homeDirectory'],
				link_basename)

			if oldname:
				link_src_old = os.path.join(
					GroupsController.configuration.defaults.home_base_path,
					GroupsController.configuration.groups.names['plural'],
					oldname)
			else:
				link_src_old = None

			for link in fsapi.minifind(
				GroupsController.users.users[uid]['homeDirectory'], maxdepth=2,
					type=stat.S_IFLNK):
				try:
					link_src_abs = os.path.abspath(os.readlink(link))
					if link_src_abs == link_src:
						if delete:
							try:
								os.unlink(link)
								logging.info("Deleted symlink %s." % \
									styles.stylize(styles.ST_LINK, link) )
							except (IOError, OSError), e:
								if e.errno != 2:
									raise exceptions.LicornRuntimeError(
										"Unable to delete symlink %s (was: %s)." \
											% (styles.stylize(styles.ST_LINK,
												link), str(e)) )
						else:
							link_not_found = False
				except (IOError, OSError), e:
					# TODO: verify there's no bug in this logic ? pida signaled an error I didn't previously notice.
					#if e.errno == 2 and link_src_old and link_dst_old == os.readlink(link):
					if e.errno == 2 and link_src_old and link_src_old == os.readlink(link):
						# delete links to old group name.
						os.unlink(link)
						logging.info("Deleted old symlink %s." % styles.stylize(styles.ST_LINK, link) )
					else:
						# errno == 2 is a broken link, don't bother.
						raise exceptions.LicornRuntimeError("Unable to read symlink %s (error was: %s)." % (link, str(e)) )

			if link_not_found and not delete:
				warn_message = logging.SYSG_USER_LACKS_SYMLINK % (styles.stylize(styles.ST_LOGIN, user), styles.stylize(styles.ST_NAME, link_basename))

				if batch or logging.ask_for_repair(warn_message, auto_answer):
					fsapi.make_symlink(link_src, link_dst, batch = batch, auto_answer = auto_answer)
				else:
					logging.warning(warn_message)
					all_went_ok = False

		return all_went_ok

	# TODO: make this @staticmethod
	def SetSharedDirPermissiveness(self, name=None, permissive=True):
		""" Set permissive or not permissive the shared directory of the group 'name'. """
		if name is None:
			raise exceptions.BadArgumentError, "You must specify a group name."

		gid = self.name_to_gid(name)

		if permissive:
			qualif = ""
		else:
			qualif = " not"

		#print "trying to set %s, original %s." % (permissive, GroupsController.groups[gid]['permissive'])

		if GroupsController.groups[gid]['permissive'] != permissive:
			GroupsController.groups[gid]['permissive'] = permissive

			# auto-apply the new permissiveness
			self.CheckGroups( [ name ], batch=True)
		else:
			logging.progress("Group %s is already%s permissive." % (styles.stylize(styles.ST_NAME, name), qualif) )

	# TODO: make this @staticmethod
	def is_permissive(self, name = None, gid = None):
		""" Return True if the shared dir of the group is permissive."""

		if gid is None:
			if name is None:
				raise exceptions.BadArgumentError, "You must specify a group name or a GID."

			gid = self.name_to_gid(name)

		if self.is_system_gid(gid):
			return None

		home = '%s/%s/%s' % (GroupsController.configuration.defaults.home_base_path, GroupsController.configuration.groups.names['plural'], name)

		try:
			# only check default ACLs, which is what we need for testing permissiveness.
			for line in posix1e.ACL(filedef=home):
				if line.tag_type & posix1e.ACL_GROUP:
					if line.qualifier == gid:
						return line.permset.write
		except IOError, e:
			if e.errno == 13:
				raise exceptions.InsufficientPermissionsError(str(e))
			elif e.errno == 2:
				if self.warnings:
					logging.warning('''Shared dir %s doesn't exist, please run "licorn-check group --name %s" to fix.''' % (styles.stylize(styles.ST_PATH, home), styles.stylize(styles.ST_NAME, name)), once = True)
			else:
				raise exceptions.LicornIOError("IO error on %s (was: %s)." % (home, e))
		except ImportError, e:
			logging.warning(logging.MODULE_POSIX1E_IMPORT_ERROR % e, once = True)
			return None

	@staticmethod
	def group_exists(name = None, gid = None):
		"""Return true if the group or gid exists on the system. """

		if name:
			return GroupsController.name_cache.has_key(name)

		if gid:
			return GroupsController.groups.has_key(gid)

		raise exceptions.BadArgumentError("You must specify a GID or a name to test existence of.")
	@staticmethod
	def primary_members(name):
		"""Get the list of users which are in group 'name'."""
		ru    = set()
		gid   = GroupsController.name_to_gid(name)

		for u in GroupsController.users.users:
			if GroupsController.users.users[u]['gidNumber'] == gid:
				ru.add(GroupsController.users.users[u]['login'])
		return ru

	@staticmethod
	def auxilliary_members(name):
		"""Return all members of a group, which are not members of this group in their primary group."""

		# TODO: really verify, for each user, that their member ship is not
		# duplicated between primary and auxilliary groups.

		return GroupsController.groups[GroupsController.name_to_gid(name)]['memberUid']

	@staticmethod
	def all_members(name):
		"""Return all members of a given group name."""

		return GroupsController.primary_members(name).union(GroupsController.auxilliary_members(name))

	@staticmethod
	def name_to_gid(name):
		""" Return the gid of the group 'name'."""

		try:
			# use the cache, Luke !
			return GroupsController.name_cache[name]
		except KeyError:
			try:
				int(name)
				logging.warning('''You passed a gid to name_to_gid(): '''
					'''%s (guess its name is "%s").''' % (
					styles.stylize(styles.ST_UGID, name),
					styles.stylize(styles.ST_NAME,
						GroupsController.groups[name]['name'])))
			except ValueError:
				pass
			raise exceptions.LicornRuntimeException(
				"The group '%s' doesn't exist." % name)

	@staticmethod
	def is_system_gid(gid):
		""" Return true if gid is system. """
		return gid < GroupsController.configuration.groups.gid_min or gid > GroupsController.configuration.groups.gid_max

	@staticmethod
	def is_standard_gid(gid):
		""" Return true if gid is system. """
		logging.debug2("filtering %d against %d and %d." % (gid,  GroupsController.configuration.groups.gid_min, GroupsController.configuration.groups.gid_max))
		return gid >= GroupsController.configuration.groups.gid_min and gid <= GroupsController.configuration.groups.gid_max

	@staticmethod
	def is_system_group(name):
		""" Return true if group is system. """
		try:
			return GroupsController.is_system_gid(GroupsController.name_to_gid(name))
		except KeyError:
			raise exceptions.LicornRuntimeException, "The group %s doesn't exist." % name

	@staticmethod
	def is_standard_group(name):
		""" Return true if group is system. """
		try:
			return GroupsController.is_standard_gid(GroupsController.name_to_gid(name))
		except KeyError:
			raise exceptions.LicornRuntimeException, "The group `%s' doesn't exist." % name

	@staticmethod
	def is_empty_gid(gid):
			return GroupsController.is_standard_gid(gid) and GroupsController.groups[gid]['memberUid'] == set()

	@staticmethod
	def is_empty_group(name):
		try:
			return GroupsController.is_empty_gid(GroupsController.name_to_gid(name))
		except KeyError:
			raise exceptions.LicornRuntimeException, "The group `%s' doesn't exist." % name

	@staticmethod
	def make_name(inputname):
		""" Make a valid login from  user's firstname and lastname."""

		maxlenght = GroupsController.configuration.groups.name_maxlenght
		groupname = inputname

		groupname = hlstr.validate_name(groupname, maxlenght = maxlenght)

		if not hlstr.cregex['group_name'].match(groupname):
			raise exceptions.LicornRuntimeError('''Can't build a valid UNIX group name (got %s, which doesn't verify %s) with the string you provided "%s".''' % (groupname, hlstr.regex['group_name'], inputname) )

		return groupname

		# TODO: verify if the group doesn't already exist.
		#while potential in UsersController.users:
