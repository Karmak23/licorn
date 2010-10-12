#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn « modify »: modify system information, user accounts, etc.
Built on top of Licorn System Library, part of Licorn System Tools (H-S-T).

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

from licorn.foundations           import logging, exceptions
from licorn.foundations           import hlstr, styles
from licorn.foundations.constants import filters, host_status
from licorn.foundations.ltrace    import ltrace

from licorn.interfaces.cli import cli_main, cli_select

_app = {
	"name"     		: "licorn-modify",
	"description"	: "Licorn Modify Entries",
	"author"   		: "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def mod_user(opts, args, users, groups, **kwargs):
	""" Modify a POSIX user account (Samba / LDAP included). """

	uids_to_mod = cli_select(users, 'user',
			args,
			[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			],
			exclude_id_lists=[
				(opts.exclude, users.guess_identifier),
				(opts.exclude_login, users.login_to_uid),
				(opts.exclude_uid, users.confirm_uid)
			])

	ltrace('mod', '> mod_user(%s)' % uids_to_mod)

	something_done = False

	for uid in uids_to_mod:

		if opts.newgecos is not None:
			something_done = True
			users.ChangeUserGecos(uid=uid, gecos=unicode(opts.newgecos),
			listener=opts.listener)

		if opts.newshell is not None:
			something_done = True
			users.ChangeUserShell(uid=uid, shell=opts.newshell,
			listener=opts.listener)

		if opts.newpassword is not None:
			something_done = True
			users.ChangeUserPassword(uid=uid, password=opts.newpassword,
			listener=opts.listener)

		if opts.auto_passwd is not None:
			something_done = True
			users.ChangeUserPassword(uid=uid,
				password=hlstr.generate_password(opts.passwd_size),
				display=True, listener=opts.listener)

		if opts.lock is not None:
			something_done = True
			users.LockAccount(uid=uid, lock=opts.lock, listener=opts.listener)

		if opts.groups_to_add:
			something_done = True
			for g in opts.groups_to_add.split(','):
				if g != '':
					try:
						groups.AddUsersInGroup(name=g, users_to_add=[ uid ],
							listener=opts.listener)
					except exceptions.LicornRuntimeException, e:
						logging.warning('''Unable to add user %s in group '''
							'''%s (was: %s).''' % (
								styles.stylize(styles.ST_LOGIN,
									users.uid_to_login(uid)),
								styles.stylize(styles.ST_NAME, g), str(e)))
					except exceptions.LicornException, e:
						raise exceptions.LicornRuntimeError(
							'''Unable to add user %s in group %s (was: %s).'''
								% (styles.stylize(styles.ST_LOGIN,
									users.uid_to_login(uid)),
									styles.stylize(styles.ST_NAME, g), str(e)))

		if opts.groups_to_del:
			something_done = True
			for g in opts.groups_to_del.split(','):
				if g != '':
					try:
						groups.DeleteUsersFromGroup(name=g,
							users_to_del=[ uid ], listener=opts.listener)
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
			users.ApplyUserSkel(opts.login, opts.apply_skel,
				listener=opts.listener)

	if not something_done:
		raise exceptions.BadArgumentError('''What do you want to modify '''
			'''about user(s) ? Use --help to know !''')
def mod_group(opts, args, groups, configuration, **kwargs):
	""" Modify a group. """

	gids_to_mod = cli_select(groups, 'group',
			args,
			include_id_lists=[
				(opts.name, groups.name_to_gid),
				(opts.gid, groups.confirm_gid)
			],
			exclude_id_lists = [
				(opts.exclude, groups.guess_identifier),
				(opts.exclude_group, groups.name_to_gid),
				(opts.exclude_gid, groups.confirm_gid)
			])

	ltrace('mod', '> mod_group(%s)' % gids_to_mod)

	g2n = groups.gid_to_name

	for gid in gids_to_mod:

		if opts.permissive is not None:
			groups.SetSharedDirPermissiveness(gid=gid,
				permissive=opts.permissive, listener=opts.listener)

		if opts.newname is not None:
			groups.RenameGroup(gid=gid, newname=opts.newname,
				listener=opts.listener)

		if opts.newskel is not None:
			groups.ChangeGroupSkel(gid=gid, groupSkel=opts.newskel,
				listener=opts.listener)

		if opts.newdescription is not None:
			groups.ChangeGroupDescription(gid=gid,
				description=unicode(opts.newdescription),
				listener=opts.listener)

		if opts.users_to_add != []:
			groups.AddUsersInGroup(gid=gid,
				users_to_add=opts.users_to_add.split(','),
				listener=opts.listener)

		if opts.users_to_del != []:
			groups.DeleteUsersFromGroup(gid=gid,
				users_to_del=opts.users_to_del.split(','),
				listener=opts.listener)

		if opts.resps_to_add != []:
			groups.AddUsersInGroup(
				name=configuration.groups.resp_prefix + g2n(gid),
				users_to_add=opts.resps_to_add.split(','),
				listener=opts.listener)

		if opts.resps_to_del != []:
			groups.DeleteUsersFromGroup(
				name=configuration.groups.resp_prefix + g2n(gid),
				users_to_del=opts.resps_to_del.split(','),
				listener=opts.listener)

		if opts.guests_to_add != []:
			groups.AddUsersInGroup(
				name=configuration.groups.guest_prefix + g2n(gid),
				users_to_add=opts.guests_to_add.split(','),
				listener=opts.listener)

		if opts.guests_to_del != []:
			groups.DeleteUsersFromGroup(
				name=configuration.groups.guest_prefix + g2n(gid),
				users_to_del=opts.guests_to_del.split(','),
				listener=opts.listener)

		# FIXME: do the same for guests,  or make resp-guest simply
		# --add-groups resp-…,group1,group2,guest-…

		if opts.granted_profiles_to_add is not None:
			groups.AddGrantedProfiles(gid=gid,
				profiles=opts.granted_profiles_to_add.split(','),
				listener=opts.listener)
		if opts.granted_profiles_to_del is not None:
			groups.DeleteGrantedProfiles(gid=gid,
				profiles=opts.granted_profiles_to_del.split(','),
				listener=opts.listener)
def mod_profile(opts, args, users, groups, profiles, **kwargs):
	""" Modify a system wide User profile. """

	profiles_to_mod = cli_select(profiles, 'profile',
			args,
			include_id_lists=[
				(opts.name, profiles.name_to_group),
				(opts.group, profiles.confirm_group)
			])

	ltrace('mod', '> mod_profile(%s)' % profiles_to_mod)

	ggi = groups.guess_identifiers

	for group in profiles_to_mod:

		if opts.newname is not None:
			profiles.ChangeProfileName(group=group,
				newname=unicode(opts.newname), listener=opts.listener)

		if opts.newgroup is not None:
			profiles.ChangeProfileGroup(group=group, newgroup=opts.newgroup,
				listener=opts.listener)

		if opts.description is not None:
			profiles.ChangeProfileDescription(group=group,
				description=unicode(opts.description),
				listener=opts.listener)

		if opts.newshell is not None:
			profiles.ChangeProfileShell(group=group, profileShell=opts.newshell,
				listener=opts.listener)

		if opts.newquota is not None:
			profiles.ChangeProfileQuota(group=group, profileQuota=opts.newquota,
				listener=opts.listener)

		if opts.newskel is not None:
			profiles.ChangeProfileSkel(group=group, profileSkel=opts.newskel,
				listener=opts.listener)

		if opts.groups_to_add is not None:
			added_groups = profiles.AddGroupsInProfile(group=group,
				groups_to_add=opts.groups_to_add.split(','),
				listener=opts.listener)
			if opts.instant_apply:
				prim_memb = groups.primary_members(name=group)
				for added_group in added_groups:
					groups.AddUsersInGroup(name=added_group,
						users_to_add=prim_memb,	batch=opts.no_sync,
						listener=opts.listener)

		if opts.groups_to_del is not None:
			deleted_groups = profiles.DeleteGroupsFromProfile(group=group,
				groups_to_del=opts.groups_to_del.split(','),
				listener=opts.listener)
			if opts.instant_apply:
				prim_memb = groups.primary_members(name=group)
				for deleted_group in deleted_groups:
					groups.DeleteUsersFromGroup(name=deleted_group,
						users_to_del=prim_memb,	batch=opts.no_sync,
						listener=opts.listener)

		if opts.no_sync:
			groups.WriteConf()

		include_id_lists = []

		if opts.apply_to_members:
			include_id_lists.append(
				(groups.primary_members(name=group), users.login_to_uid))
		if opts.apply_to_users is not None:
			include_id_lists.append(
				(opts.apply_to_users.split(','), users.guess_identifier))
		if opts.apply_to_groups is not None:
			for gid in ggi(opts.apply_to_groups.split(',')):
				include_id_lists.append(
					(groups.primary_members(gid=gid), users.login_to_uid))

		if opts.apply_all_attributes or opts.apply_skel or opts.apply_groups:

			_users = users.Select(
				cli_select(users, 'user',
					args,
					include_id_lists=include_id_lists,
					exclude_id_lists=[
						(opts.exclude, users.guess_identifier),
						(opts.exclude_login, users.login_to_uid),
						(opts.exclude_uid, users.confirm_uid)
					],
					default_selection=filters.NONE,
					all=opts.apply_to_all_accounts)
				)

			ltrace('mod',"  mod_profile(on_users=%s)" % _users)

			if _users != []:
				profiles.ReapplyProfileOfUsers(_users,
					apply_groups=opts.apply_groups,
					apply_skel=opts.apply_skel,
					batch=opts.batch, auto_answer=opts.auto_answer,
					listener=opts.listener)
	ltrace('mod', '< mod_profile()')
def shut(i, listener=None):
	""" FIXME: find a way to get the listener, else we have no output.
	opts.listener doesn't work here because opts doesn't yet exist.

	putting the def in mo_machines isn't compatible with multithreading.Pool."""
	return machines.shutdown(i, listener=listener)
def mod_machine(opts, args, machines, **kwargs):
	""" Modify a machine. """

	if opts.all:
		selection = host_status.IDLE | host_status.ASLEEP | host_status.ACTIVE
	else:
		selection = filters.NONE

		if opts.idle:
			selection |= host_status.IDLE

		if opts.asleep:
			selection |= host_status.ASLEEP

		if opts.active:
			selection |= host_status.ACTIVE

	mids_to_mod = cli_select(machines, 'machine',
			args,
			[
				(opts.hostname, machines.hostname_to_mid),
				(opts.mid, machines.confirm_mid)
			],
			selection)

	if opts.shutdown:
		from multiprocessing import Pool
		p = Pool(5)
		p.map(shut, mids_to_mod)
def mod_keyword(opts, args, keywords, **kwargs):
	""" Modify a keyword. """

	if len(args) == 2:
		opts.name = args[1]

	if opts.newname is not None:
		keywords.RenameKeyword(opts.name, opts.newname, listener=opts.listener)
	if opts.parent is not None:
		keywords.ChangeParent(opts.name, opts.parent, listener=opts.listener)
	elif opts.remove_parent:
		keywords.RemoveParent(opts.name, listener=opts.listener)
	if opts.description is not None:
		keywords.ChangeDescription(opts.name, opts.description,
			listener=opts.listener)
def mod_path(opts, args):
	""" Manage keywords of a file or directory. """

	raise NotImplementedError('not yet anymore.')

	if len(args) == 2:
		opts.path = args[1]

	# this should go directly into system.keywords.
	from licorn.harvester import HarvestClient
	hc = HarvestClient()
	hc.UpdateRequest(opts.path)
	return

	if opts.clear_keywords:
		keywords.ClearKeywords(opts.path, opts.recursive)
	else:
		if opts.keywords_to_del is not None:
			keywords.DeleteKeywordsFromPath(opts.path, opts.keywords_to_del.split(','), opts.recursive)
		if opts.keywords_to_add is not None:
			keywords.AddKeywordsToPath(opts.path, opts.keywords_to_add.split(','), opts.recursive)
def mod_configuration(opts, args, configuration, privileges, **kwargs):
	""" Modify some aspects or abstract directives of the system configuration
		(use with caution)."""

	if opts.setup_shared_dirs:
		configuration.check_base_dirs(minimal=False, batch=True,
			listener=opts.listener)

	elif opts.set_hostname:
		configuration.ModifyHostname(opts.set_hostname)

	elif opts.set_ip_address:
		raise exceptions.NotImplementedError(
			"changing server IP address is not yet implemented.")

	elif opts.privileges_to_add:
		privileges.add(opts.privileges_to_add.split(','),
			listener=opts.listener)

	elif opts.privileges_to_remove:
		privileges.delete(opts.privileges_to_remove.split(','),
			listener=opts.listener)

	elif opts.hidden_groups != None:
		configuration.SetHiddenGroups(opts.hidden_groups,
			listener=opts.listener)

	elif opts.disable_backends != None:
		for backend in opts.disable_backends.split(','):
			configuration.disable_backend(backend, listener=opts.listener)

	elif opts.enable_backends != None:
		for backend in opts.enable_backends.split(','):
			configuration.enable_backend(backend, listener=opts.listener)

	else:
		raise exceptions.BadArgumentError(
			"what do you want to modify ? use --help to know !")
def mod_main():
	import argparser as agp

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
		'machine':       (agp.mod_machine_parse_arguments, mod_machine),
		'machines':      (agp.mod_machine_parse_arguments, mod_machine),
		'client':        (agp.mod_machine_parse_arguments, mod_machine),
		'clients':       (agp.mod_machine_parse_arguments, mod_machine),
		'kw':            (agp.mod_keyword_parse_arguments, mod_keyword),
		'tag':           (agp.mod_keyword_parse_arguments, mod_keyword),
		'tags':          (agp.mod_keyword_parse_arguments, mod_keyword),
		'keyword':       (agp.mod_keyword_parse_arguments, mod_keyword),
		'keywords':      (agp.mod_keyword_parse_arguments, mod_keyword),
		'path':          (agp.mod_path_parse_arguments, mod_path),
	}

	cli_main(functions, _app)

if __name__ == "__main__":
	mod_main()
