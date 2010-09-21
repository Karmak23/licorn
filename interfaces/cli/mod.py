#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn « modify »: modify system information, user accounts, etc.
Built on top of Licorn System Library, part of Licorn System Tools (H-S-T).

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys

_app = {
	"name"     		: "licorn-modify",
	"description"	: "Licorn Modify Entries",
	"author"   		: "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

from licorn.foundations           import logging, exceptions, options
from licorn.foundations           import hlstr, objects, styles
from licorn.foundations.constants import filters
from licorn.foundations.ltrace    import ltrace

from licorn.core.configuration import LicornConfiguration
from licorn.core.users         import UsersController
from licorn.core.groups        import GroupsController
from licorn.core.profiles      import ProfilesController
from licorn.core.keywords      import KeywordsController

def mod_user(opts, args):
	""" Modify a POSIX user account (Samba / LDAP included). """

	configuration = LicornConfiguration()
	users = UsersController(configuration)

	uids_to_mod = cli_select(users, 'user',
			args,
			[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			],
			filters.NONE)

	ltrace('mod', '> mod_user(%s)' % uids_to_mod)

	something_done = False

	for uid in uids_to_mod:

		if opts.newgecos is not None:
			something_done = True
			users.ChangeUserGecos(uid=uid, gecos=unicode(opts.newgecos))

		if opts.newshell is not None:
			something_done = True
			users.ChangeUserShell(uid=uid, shell=opts.newshell)

		if opts.newpassword is not None:
			something_done = True
			users.ChangeUserPassword(uid=uid, password=opts.newpassword)

		if opts.auto_passwd is not None:
			something_done = True
			users.ChangeUserPassword(uid=uid,
				password=hlstr.generate_password(opts.passwd_size),
				display=True)

		if opts.lock is not None:
			something_done = True
			users.LockAccount(uid, opts.lock)

		if opts.groups_to_add:
			something_done = True
			for g in opts.groups_to_add.split(','):
				if g != '':
					try:
						groups = GroupsController(configuration, users)
						groups.AddUsersInGroup(name=g, users_to_add=[ uid ])
					except exceptions.LicornRuntimeException, e:
						logging.warning('''Unable to add user %s in group '''
							'''%s (was: %s).''' % (
								styles.stylize(styles.ST_LOGIN,
									UsersController.uid_to_login(uid)),
								styles.stylize(styles.ST_NAME, g), str(e)))
					except exceptions.LicornException, e:
						raise exceptions.LicornRuntimeError(
							'''Unable to add user %s in group %s (was: %s).'''
								% (styles.stylize(styles.ST_LOGIN,
									UsersController.uid_to_login(uid)),
									styles.stylize(styles.ST_NAME, g), str(e)))

		if opts.groups_to_del:
			something_done = True
			for g in opts.groups_to_del.split(','):
				if g != '':
					try:
						groups = GroupsController(configuration, users)
						groups.DeleteUsersFromGroup(name=g, users_to_del=[ uid ])
					except exceptions.LicornRuntimeException, e:
						logging.warning('''Unable to remove user %s from '''
							'''group %s (was: %s).''' % (
								styles.stylize(styles.ST_LOGIN, opts.login),
								styles.stylize(styles.ST_NAME, g),
								str(e)))
					except exceptions.LicornException, e:
						raise exceptions.LicornRuntimeError(
							'''Unable to remove user %s from '''
							'''group %s (was: %s).''' % (
								styles.stylize(styles.ST_LOGIN, opts.login),
								styles.stylize(styles.ST_NAME, g),
								str(e)))

		if opts.apply_skel is not None:
			something_done = True
			users.ApplyUserSkel(opts.login, opts.apply_skel)

	if not something_done:
		raise exceptions.BadArgumentError('''What do you want to modify '''
			'''about user(s) ? Use --help to know !''')
def mod_group(opts, args):
	""" Modify a group. """

	configuration = LicornConfiguration()
	users = UsersController(configuration)
	groups = GroupsController(configuration, users)
	profiles = ProfilesController(configuration, groups, users)

	gids_to_mod = cli_select(groups, 'group',
			args,
			[
				(opts.name, groups.name_to_gid),
				(opts.gid, groups.confirm_gid)
			],
			filters.NONE)

	ltrace('mod', '> mod_group(%s)' % gids_to_mod)

	g2n = groups.gid_to_name

	for gid in gids_to_mod:

		if opts.permissive is not None:
			groups.SetSharedDirPermissiveness(gid=gid,
				permissive=opts.permissive)

		if opts.newname is not None:
			groups.RenameGroup(gid=gid, newname=opts.newname)

		if opts.newskel is not None:
			groups.ChangeGroupSkel(gid=gid, groupSkel=opts.newskel)

		if opts.newdescription is not None:
			groups.ChangeGroupDescription(gid=gid,
				description=unicode(opts.newdescription))

		if opts.users_to_add != []:
			groups.AddUsersInGroup(gid=gid,
				users_to_add=opts.users_to_add.split(','))

		if opts.users_to_del != []:
			groups.DeleteUsersFromGroup(gid=gid,
				users_to_del=opts.users_to_del.split(','))

		if opts.resps_to_add != []:
			groups.AddUsersInGroup(
				name=configuration.groups.resp_prefix + g2n(gid),
				users_to_add=opts.resps_to_add.split(','))

		if opts.resps_to_del != []:
			groups.DeleteUsersFromGroup(
				name=configuration.groups.resp_prefix + g2n(gid),
				users_to_del=opts.resps_to_del.split(','))

		if opts.guests_to_add != []:
			groups.AddUsersInGroup(
				name=configuration.groups.guest_prefix + g2n(gid),
				users_to_add=opts.guests_to_add.split(','))

		if opts.guests_to_del != []:
			groups.DeleteUsersFromGroup(
				name=configuration.groups.guest_prefix + g2n(gid),
				users_to_del=opts.guests_to_del.split(','))

		# FIXME: do the same for guests,  or make resp-guest simply
		# --add-groups resp-...,group1,group2,guest-...

		if opts.granted_profiles_to_add is not None:
			groups.AddGrantedProfiles(gid=gid,
				profiles=opts.granted_profiles_to_add.split(','))
		if opts.granted_profiles_to_del is not None:
			groups.DeleteGrantedProfiles(gid=gid,
				profiles=opts.granted_profiles_to_del.split(','))
def mod_profile(opts, args):
	""" Modify a system wide User profile. """

	configuration = LicornConfiguration()
	users = UsersController(configuration)
	groups = GroupsController(configuration, users)
	profiles = ProfilesController(configuration, groups, users)

	profiles_to_mod = cli_select(profiles, 'profile',
			args,
			[
				(opts.name, profiles.name_to_group),
				(opts.group, profiles.confirm_group)
			],
			filters.NONE)

	ltrace('mod', '> mod_profile(%s)' % profiles_to_mod)

	ggi = groups.guess_identifiers

	for group in profiles_to_mod:

		if opts.newname is not None:
			profiles.ChangeProfileName(group=group,
				newname=unicode(opts.newname))

		if opts.newgroup is not None:
			profiles.ChangeProfileGroup(group=group, newgroup=opts.newgroup)

		if opts.description is not None:
			profiles.ChangeProfileDescription(group=group,
				description=unicode(opts.description))

		if opts.newshell is not None:
			profiles.ChangeProfileShell(group=group, profileShell=opts.newshell)

		if opts.newquota is not None:
			profiles.ChangeProfileQuota(group=group, profileQuota=opts.newquota)

		if opts.newskel is not None:
			profiles.ChangeProfileSkel(group=group, profileSkel=opts.newskel)

		if opts.groups_to_add is not None:
			added_groups = profiles.AddGroupsInProfile(group=group,
				groups_to_add=opts.groups_to_add.split(','))
			if opts.instant_apply:
				prim_memb = groups.primary_members(name=group)
				for group in added_groups:
					groups.AddUsersInGroup(name=group, users_to_add=prim_memb,
						batch=opts.no_sync)

		if opts.groups_to_del is not None:
			deleted_groups = profiles.DeleteGroupsFromProfile(group=group,
				groups_to_del=opts.groups_to_del.split(','))
			if opts.instant_apply:
				prim_memb = groups.primary_members(name=group)
				for group in deleted_groups:
					groups.DeleteUsersFromGroup(name=group,
						users_to_del=prim_memb,	batch=opts.no_sync)

		if opts.no_sync:
			groups.WriteConf()

		# this should have been already done by profiles.*() methods.
		#profiles.WriteConf(configuration.profiles_config_file)

		_users = []

		# making users list (or not) to reapply profiles
		if opts.apply_to_all_accounts: # all users of standard groups
			users.Select(filters.STANDARD)
			_users = [ users.users[i]['login'] for i in users.filtered_users ]

		else:
			if opts.apply_to_members:
				_users.extend(groups.primary_members(name=group))
			if opts.apply_to_users is not None:
				_users.extend(opts.apply_to_users.split(','))
			if opts.apply_to_groups is not None:
				for gid in ggi(opts.apply_to_groups.split(',')):
					_users.extend(groups.primary_members(gid=gid))

		logging.debug("Selected users for profile re-applying: %s." % _users)

		if _users != []:
			if opts.apply_all_attributes:
				profiles.ReapplyProfileOfUsers(_users, apply_groups=True,
					apply_skel=True, batch=opts.batch, auto_answer=opts.auto_answer)
			else:
				apply_groups = False
				apply_skel = False
				if opts.apply_skel is not None:
					apply_skel = opts.apply_skel
				if opts.apply_groups is not None:
					apply_groups = opts.apply_groups
				profiles.ReapplyProfileOfUsers(_users, apply_groups, apply_skel,
					batch=opts.batch, auto_answer=opts.auto_answer)
	ltrace('mod', '< mod_profile()')
def mod_keyword(opts, args):
	""" Modify a keyword. """

	configuration = LicornConfiguration()
	kw = KeywordsController(configuration)

	if len(args) == 2:
		opts.name = args[1]

	if opts.newname is not None:
		kw.RenameKeyword(opts.name, opts.newname)
	if opts.parent is not None:
		kw.ChangeParent(opts.name, opts.parent)
	elif opts.remove_parent:
		kw.RemoveParent(opts.name)
	if opts.description is not None:
		kw.ChangeDescription(opts.name, opts.description)
def mod_path(opts, args):
	""" Manage keywords of a file or directory. """

	from licorn.core.keywords import KeywordsController
	kw = KeywordsController(configuration)

	if len(args) == 2:
		opts.path = args[1]

	# this should go directly into system.keywords.
	from licorn.harvester import HarvestClient
	hc = HarvestClient()
	hc.UpdateRequest(opts.path)
	return

	if opts.clear_keywords:
		kw.ClearKeywords(opts.path, opts.recursive)
	else:
		if opts.keywords_to_del is not None:
			kw.DeleteKeywordsFromPath(opts.path, opts.keywords_to_del.split(','), opts.recursive)
		if opts.keywords_to_add is not None:
			kw.AddKeywordsToPath(opts.path, opts.keywords_to_add.split(','), opts.recursive)
def mod_configuration(opts, args):
	""" Modify some aspects or abstract directives of the system configuration (use with caution)."""

	configuration = LicornConfiguration()

	if opts.setup_shared_dirs:
		#
		# FIXME: this should go into checks.py
		#
		configuration.check_base_dirs(minimal = False, batch = True)

	elif opts.set_hostname:
		configuration.ModifyHostname(opts.set_hostname)

	elif opts.set_ip_address:
		raise exceptions.NotImplementedError("changing server IP address is not yet implemented.")

	elif opts.privileges_to_add:
		configuration.groups.privileges_whitelist.add(
			opts.privileges_to_add.split(','))

	elif opts.privileges_to_remove:
		configuration.groups.privileges_whitelist.delete(
			opts.privileges_to_remove.split(','))

	elif opts.hidden_groups != None:
		configuration.SetHiddenGroups(opts.hidden_groups)

	elif opts.disable_backends != None:
		for backend in opts.disable_backends.split(','):
			configuration.disable_backend(backend)

	elif opts.enable_backends != None:
		for backend in opts.enable_backends.split(','):
			configuration.enable_backend(backend)

	else:
		raise exceptions.BadArgumentError("what do you want to modify ? use --help to know !")

if __name__ == "__main__":

	import argparser as agp
	from licorn.interfaces.cli import cli_main, cli_select

	functions = {
		'usr':	         (agp.mod_user_parse_arguments, mod_user),
		'user':	         (agp.mod_user_parse_arguments, mod_user),
		'users':         (agp.mod_user_parse_arguments, mod_user),
		'grp':           (agp.mod_group_parse_arguments, mod_group),
		'group':         (agp.mod_group_parse_arguments, mod_group),
		'groups':        (agp.mod_group_parse_arguments, mod_group),
		'profile':       (agp.mod_profile_parse_arguments, mod_profile),
		'profiles':      (agp.mod_profile_parse_arguments, mod_profile),
		'conf':			 (agp.mod_configuration_parse_arguments, mod_configuration),
		'config':		 (agp.mod_configuration_parse_arguments, mod_configuration),
		'configuration': (agp.mod_configuration_parse_arguments, mod_configuration),
		'kw':            (agp.mod_keyword_parse_arguments, mod_keyword),
		'tag':           (agp.mod_keyword_parse_arguments, mod_keyword),
		'tags':          (agp.mod_keyword_parse_arguments, mod_keyword),
		'keyword':       (agp.mod_keyword_parse_arguments, mod_keyword),
		'keywords':      (agp.mod_keyword_parse_arguments, mod_keyword),
		'path':          (agp.mod_path_parse_arguments, mod_path),
	}

	cli_main(functions, _app)
