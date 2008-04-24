#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn « modify » : modify system information, user accounts, etc.
Built on top of Licorn System Library, part of Licorn System Tools (H-S-T).

Copyright (C) 2005-2007 Olivier Cortès <oc@5sys.fr>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys

_app = {
	"name"     		 : "licorn-modify",
	"description"	 : "Licorn Modify Entries",
	"author"   		 : "Olivier Cortès <oc@5sys.fr>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

from licorn.foundations import logging, exceptions, options, hlstr, file_locks, styles
from licorn.core        import configuration, users, groups, profiles

def modify_user() :
	""" Modify a POSIX user account (Samba / LDAP included). """

	something_done = False
	
	if opts.newgecos is not None :
		something_done = True
		users.ChangeUserGecos(opts.login, unicode(opts.newgecos))

	if opts.newshell is not None :
		something_done = True
		users.ChangeUserShell(opts.login, opts.newshell)

	if opts.newpassword is not None :
		something_done = True
		users.ChangeUserPassword(opts.login, opts.newpassword)
	
	if opts.auto_passwd is not None :
		something_done = True
		users.ChangeUserPassword(opts.login, hlstr.generate_password(opts.passwd_size), display = True)

	if opts.lock is not None :
		something_done = True
		users.LockAccount(opts.login, opts.lock)

	if opts.groups_to_add is not None and opts.login is not None :
		something_done = True
		for g in opts.groups_to_add.split(',') :
			if g != "" :
				try :
					groups.AddUsersInGroup(g, [ opts.login ])
				except exceptions.LicornRuntimeException, e :
					logging.warning("Unable to add user %s in group %s (was: %s)." % (styles.stylize(styles.ST_LOGIN, opts.login), styles.stylize(styles.ST_NAME, g), str(e)))
				except exceptions.LicornException, e:
					raise exceptions.LicornRuntimeError("Unable to add user %s in group %s (was: %s)." % (styles.stylize(styles.ST_LOGIN, opts.login), styles.stylize(styles.ST_NAME, g), str(e)))

	if opts.groups_to_del is not None and opts.login is not None :
		something_done = True
		for g in opts.groups_to_del.split(',') :
			if g != "" :
				try :
					groups.RemoveUsersFromGroup(g, [ opts.login ])
				except exceptions.LicornRuntimeException, e :
					logging.warning("Unable to remove user %s from group %s (was: %s)." % (styles.stylize(styles.ST_LOGIN, opts.login), styles.stylize(styles.ST_NAME, g), str(e)))
				except exceptions.LicornException, e :
					raise exceptions.LicornRuntimeError("Unable to remove user %s from group %s (was: %s)." % (styles.stylize(styles.ST_LOGIN, opts.login), styles.stylize(styles.ST_NAME, g), str(e)))

	if opts.apply_skel is not None :
		something_done = True
		users.ApplyUserSkel(opts.login, opts.apply_skel)
	
	if not something_done :
		raise exceptions.BadArgumentError("What do you want to modify about user(s) ? Use --help to know !")
def modify_group() :
	""" Modify a group. """

	if opts.newskel is not None :
		groups.ChangeGroupSkel(opts.name, opts.newskel)
	if opts.newdescription is not None :
		groups.ChangeGroupDescription(opts.name, unicode(opts.newdescription))

	if opts.users_to_add != [] :
		groups.AddUsersInGroup(opts.name,opts.users_to_add.split(','))

	if opts.users_to_del != [] :
		groups.RemoveUsersFromGroup(opts.name, opts.users_to_del.split(','))
	
	if opts.resps_to_add != [] :
		groups.AddUsersInGroup(configuration.groups.resp_prefix + opts.name, opts.resps_to_add.split(','))

	if opts.resps_to_del != [] :
		groups.RemoveUsersFromGroup(configuration.groups.resp_prefix + opts.name, opts.resps_to_del.split(','))
		
	if opts.guests_to_add != [] :
		groups.AddUsersInGroup(configuration.groups.guest_prefix + opts.name, opts.guests_to_add.split(','))

	if opts.guests_to_del != [] :
		groups.RemoveUsersFromGroup(configuration.groups.guest_prefix + opts.name, opts.guests_to_del.split(','))
		
	#
	# FIXME : do the same for guests,  or make resp-guest simply --add-groups resp-...,group1,group2,guest-...
	#

	if opts.granted_profiles_to_add is not None :
		groups.AddGrantedProfiles(users, profiles, opts.name, opts.granted_profiles_to_add.split(','))
		profiles.WriteConf(configuration.profiles_config_file)
	if opts.granted_profiles_to_del is not None :
		groups.DeleteGrantedProfiles(users, profiles, opts.name, opts.granted_profiles_to_del.split(','))
		profiles.WriteConf(configuration.profiles_config_file)
	
	if opts.permissive is not None :
		groups.SetSharedDirPermissiveness(opts.name, opts.permissive)
	if opts.newname is not None :
		groups.RenameGroup(profiles, opts.name, opts.newname)
def modify_profile() :
	""" Modify a system wide User profile. """
	
	if opts.group is None :
		raise exceptions.BadArgumentError("Which profile do you want to modify ? Specify it with --group . Use --help for details.")
	
	if opts.newname is not None :
		profiles.ChangeProfileName(opts.group, unicode(opts.newname))
	if opts.newgroup is not None :
		profiles.ChangeProfileGroup(opts.group, opts.newgroup)
	if opts.newcomment is not None :
		profiles.ChangeProfileComment(opts.group, unicode(opts.newcomment))
	if opts.newshell is not None :
		profiles.ChangeProfileShell(opts.group, opts.newshell)
	if opts.newquota is not None :
		profiles.ChangeProfileQuota(opts.group, opts.newquota)
	if opts.newskel is not None :
		profiles.ChangeProfileSkel(opts.group, opts.newskel)
		
	if opts.groups_to_add is not None :
		profiles.AddGroupsInProfile(opts.group, opts.groups_to_add.split(','))
		if opts.instant_apply :
			prim_memb = groups.primary_members(opts.group)
			for group in opts.groups_to_add.split(',') :
				groups.AddUsersInGroup(group, prim_memb, batch=opts.no_sync)

	if opts.groups_to_del is not None :
		profiles.DeleteGroupsFromProfile(opts.group, opts.groups_to_del.split(','))
		if opts.instant_apply :
			prim_memb = groups.primary_members(opts.group)
			for group in opts.groups_to_del.split(',') :
				groups.RemoveUsersFromGroup(group, prim_memb, batch=opts.no_sync)
	
	if opts.no_sync :
		groups.WriteConf()
		
	profiles.WriteConf(configuration.profiles_config_file)
	
	_users = []
	
	# making users list (or not) to reapply profiles
	if opts.apply_to_all_accounts : # all users of standard groups
		users.Select(users.FILTER_STANDARD)
		_users = [ users.users[i]['login'] for i in users.filtered_users ]

	else :
		if opts.apply_to_members :
			_users.extend(groups.primary_members(opts.group))
		if opts.apply_to_users is not None :
			_users.extend(opts.apply_to_users.split(','))
		if opts.apply_to_groups is not None :
			for g in opts.apply_to_groups.split(',') :
				_users.extend(groups.primary_members(g))

	logging.debug("Selected users for profile re-applying : %s." % _users)

	if _users != [] :
		if opts.apply_all_attributes :
			profiles.ReapplyProfileOfUsers(_users, apply_groups=True, apply_skel=True, batch=opts.force)
		else :
			apply_groups = False
			apply_skel = False
			if opts.apply_skel is not None :
				apply_skel = opts.apply_skel
			if opts.apply_groups is not None :
				apply_groups = opts.apply_groups
			profiles.ReapplyProfileOfUsers(_users, apply_groups, apply_skel, batch=opts.force)
def modify_keyword() :
	""" Modify a keyword. """
	from licorn.system import keywords
	kw = keywords.KeywordsList(configuration)
	if opts.newname is not None :
		kw.RenameKeyword(opts.name, opts.newname)
	if opts.parent is not None :
		kw.ChangeParent(opts.name, opts.parent)
	elif opts.remove_parent :
		kw.RemoveParent(opts.name)
	if opts.description is not None :
		kw.ChangeDescription(opts.name, opts.description)
def modify_path() :
	""" Manage keywords of a file or directory. """
	from licorn.system import keywords
	kw = keywords.KeywordsList(configuration)
	
	# this should go directly into system.keywords.
	from licorn.harvester import HarvestClient
	hc = HarvestClient()
	hc.UpdateRequest(opts.path)
	return
	
	if opts.clear_keywords :
		kw.ClearKeywords(opts.path, opts.recursive)
	else :
		if opts.keywords_to_del is not None :
			kw.DeleteKeywordsFromPath(opts.path, opts.keywords_to_del.split(','), opts.recursive)
		if opts.keywords_to_add is not None :
			kw.AddKeywordsToPath(opts.path, opts.keywords_to_add.split(','), opts.recursive)

def modify_workstation() :
	raise NotImplementedError("modify_workstations not implemented.")
def modify_internet_type() :
	raise NotImplementedError("modify_internet_types not implemented.")
def modify_webfilter() :
	raise NotImplementedError("modify_webfilters_types not implemented.")
def modify_configuration() :
	""" Modify some aspects or abstract directives of the system configuration (use with caution)."""

	if opts.setup_shared_dirs :
		#
		# FIXME : this should go into checks.py
		#
		configuration.CheckBaseDirs(minimal = False, batch = True)

	elif opts.set_hostname :
		configuration.ModifyHostname(opts.set_hostname)

	elif opts.set_ip_address :
		raise exceptions.NotImplementedError("changing server IP address is not yet implemented.")
		
	elif opts.privileges_to_add :
		for privilege in opts.privileges_to_add.split(',') :
			configuration.groups.privileges_whitelist.append(privilege)
		configuration.groups.privileges_whitelist.WriteConf()
	
	elif opts.privileges_to_remove :
		for privilege in opts.privileges_to_remove.split(',') :
			configuration.groups.privileges_whitelist.remove(privilege)
		configuration.groups.privileges_whitelist.WriteConf()
		
	else :
		raise exceptions.BadArgumentError("what do you want to modify ? use --help to know !")

if __name__ == "__main__" :

	try :
		giantLock = file_locks.FileLock(configuration, "giant", 10)
		giantLock.Lock()
	except (IOError, OSError), e :
		logging.error(logging.GENERAL_CANT_ACQUIRE_GIANT_LOCK % str(e))

	try :
		try :
			if "--no-colors" in sys.argv :
				options.SetNoColors(True)

			from licorn.interfaces.cli import argparser

			if len(sys.argv) < 2 :
				# automatically display help if no arg/option is given.
				sys.argv.append("--help")
				argparser.general_parse_arguments(_app)

			if len(sys.argv) < 3 :
				# this will display help, but when parsed later by specific functions.
				# (for user/group/profile specific help)
				sys.argv.append("--help")
				help_appended = True
			else :
				help_appended = False

			mode = sys.argv[1]

			if mode == 'user' :
				(opts, args) = argparser.modify_user_parse_arguments(_app)
				if len(args) == 2 :
					opts.login = args[1]
				options.SetFrom(opts)
				modify_user()
			elif mode == 'group' :
				(opts, args) = argparser.modify_group_parse_arguments(_app)
				if len(args) == 2 :
					opts.name = args[1]
				options.SetFrom(opts)
				modify_group()
			elif mode == 'profile' :
				(opts, args) = argparser.modify_profile_parse_arguments(_app)
				if len(args) == 2 :
					opts.group = args[1]
				options.SetFrom(opts)
				modify_profile()
			elif mode == 'keyword' :
				(opts, args) = argparser.modify_keyword_parse_arguments(_app)
				if len(args) == 2 :
					opts.name = args[1]
				options.SetFrom(opts)
				modify_keyword()
			elif mode == 'path' :
				(opts, args) = argparser.modify_path_parse_arguments(_app)
				if len(args) == 2 :
					opts.path = args[1]
				options.SetFrom(opts)
				modify_path()
			elif mode in ('config', 'configuration') :
				(opts, args) = argparser.modify_configuration_parse_arguments(_app)
				options.SetFrom(opts)
				modify_configuration()
			else :
				if not help_appended :
					logging.warning(logging.GENERAL_UNKNOWN_MODE % mode)
					sys.argv.append("--help")

				argparser.general_parse_arguments(_app)

		except exceptions.LicornException, e :
			logging.error(str(e), e.errno)

		except KeyboardInterrupt :
			logging.warning(logging.GENERAL_INTERRUPTED)

	finally :
		configuration.CleanUp()
		giantLock.Unlock()
