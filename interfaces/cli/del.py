#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

delete - delete sompething on the system, an unser account, a group, etc.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import sys, re

from licorn.foundations           import logging, exceptions, options, objects, \
	styles
from licorn.foundations.constants import filters

from licorn.core.configuration    import LicornConfiguration
from licorn.core.users            import UsersController
from licorn.core.groups           import GroupsController
from licorn.core.profiles         import ProfilesController
from licorn.core.keywords         import KeywordsController

_app = {
	"name"        : "licorn-delete",
	"description" : "Licorn Delete Entries",
	"author"      : "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def desimport_groups(opts,args):
	""" Delete the groups (and theyr members) present in a import file.	"""

	configuration = LicornConfiguration()
	users = UsersController(configuration)
	groups = GroupsController(configuration, users, warnings=False)

	if opts.filename is None:
		raise exceptions.BadArgumentError, "You must specify a file name"

	delete_file = file(opts.filename, 'r')

	groups_to_del = []

	user_re = re.compile("^\"?\w*\"?;\"?\w*\"?;\"?(?P<group>\w*)\"?$", re.UNICODE)
	for ligne in delete_file:
		mo = user_re.match(ligne)
		if mo is not None:
			u = mo.groupdict()
			g = u['group']
			if g not in groups_to_del:
				groups_to_del.append(g)

	delete_file.close()

	# Deleting
	length_groups = len(groups_to_del)
	quantity = length_groups
	if quantity <= 0:
		quantity = 1
	delta = 100.0 / float(quantity) # increment for progress indicator
	progression = 0.0
	i = 0 # to print i/length

	for g in groups_to_del:
		try:
			i += 1
			sys.stdout.write("\rDeleting groups (" + str(i) + "/" + str(length_groups) + "). Progression: " + str(int(progression)) + "%")
			groups.DeleteGroup(profiles, g, True, True, users)
			progression += delta
			sys.stdout.flush()
		except exceptions.LicornException, e:
			logging.warning(str(e))
	profiles.WriteConf(configuration.profiles_config_file)
	print "\nFinished"
def del_user(opts, args):
	""" delete a user account. """

	configuration = LicornConfiguration()
	users = UsersController(configuration)
	# groups is needed to delete the user from its groups, else its name will
	# stay dangling in memberUid.
	groups = GroupsController(configuration, users, warnings=False)

	uids_to_del = cli_select(users, 'user',
			args,
			[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			])

	for uid in uids_to_del:
		users.DeleteUser(uid=uid, no_archive=opts.no_archive)
def del_user_from_groups(opts, args):
	configuration = LicornConfiguration()
	users = UsersController(configuration)
	groups = GroupsController(configuration, users, warnings=False)

	uids_to_del = cli_select(users, 'user',
			args,
			[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			])

	for g in opts.groups_to_del.split(','):
		if g != "":
			try:
				groups.DeleteUsersFromGroup(name=g, users_to_del=uids_to_del)
			except exceptions.DoesntExistsException, e:
				logging.warning(
					"Unable to remove user(s) %s from group %s (was: %s)."
					% (styles.stylize(styles.ST_LOGIN, opts.login),
					styles.stylize(styles.ST_NAME, g), str(e)))
			except exceptions.LicornException, e:
				raise exceptions.LicornRuntimeError(
					"Unable to remove user(s) %s from group %s (was: %s)."
					% (styles.stylize(styles.ST_LOGIN, opts.login),
					styles.stylize(styles.ST_NAME, g), str(e)))
def dispatch_del_user(opts, args):
	if opts.login is None:
		if len(args) == 2:
			opts.login = args[1]
			args[1] = ''
			del_user(opts, args)
		elif len(args) == 3:
			opts.login = args[1]
			opts.groups_to_del = args[2]
			args[1] = ''
			args[2] = ''
			del_user_from_groups(opts, args)
		else:
			del_user(opts, args)
	else:
		del_user(opts, args)

def del_group(opts, args):
	""" delete an Licorn group. """

	configuration = LicornConfiguration()
	users = UsersController(configuration)
	groups = GroupsController(configuration, users, warnings=False)
	profiles = ProfilesController(configuration, groups, users)

	gids_to_del = cli_select(groups, 'group',
			args,
			[
				(opts.name, groups.name_to_gid),
				(opts.gid, groups.confirm_gid)
			])

	for gid in gids_to_del:
		groups.DeleteGroup(gid=gid, del_users=opts.del_users,
			no_archive=opts.no_archive)
def del_profile(opts, args):
	""" Delete a system wide User profile. """

	configuration = LicornConfiguration()
	users = UsersController(configuration)
	groups = GroupsController(configuration, users, warnings=False)
	profiles = ProfilesController(configuration, groups, users)

	profiles_to_del = cli_select(profiles, 'profile',
			args,
			[
				(opts.name, profiles.name_to_group),
				(opts.group, profiles.confirm_group)
			])

	for p in profiles_to_del:
		profiles.DeleteProfile(group=p, del_users=opts.del_users,
			no_archive=opts.no_archive)
def del_keyword(opts, args):
	""" delete a system wide User profile. """

	configuration = LicornConfiguration()
	keywords = KeywordsController(configuration)

	if opts.name is None and len(args) == 2:
		opts.name = args[1]

	keywords.DeleteKeyword(opts.name, opts.del_children)
def del_privilege(opts, args):
	configuration = LicornConfiguration()

	if opts.privileges_to_remove is None and len(args) == 2:
		opts.privileges_to_remove = args[1]

	configuration.groups.privileges_whitelist.delete(
		opts.privileges_to_remove.split(','))

if __name__ == "__main__":

	import argparser as agp
	from licorn.interfaces.cli import cli_main, cli_select

	functions = {
		'usr':	         (agp.del_user_parse_arguments, dispatch_del_user),
		'user':	         (agp.del_user_parse_arguments, dispatch_del_user),
		'users':         (agp.del_user_parse_arguments, dispatch_del_user),
		'grp':           (agp.del_group_parse_arguments, del_group),
		'group':         (agp.del_group_parse_arguments, del_group),
		'groups':        (agp.delimport_parse_arguments, desimport_groups),
		'profile':       (agp.del_profile_parse_arguments, del_profile),
		'profiles':      (agp.del_profile_parse_arguments, del_profile),
		'priv':			 (agp.del_privilege_parse_arguments, del_privilege),
		'privs':		 (agp.del_privilege_parse_arguments, del_privilege),
		'privilege':	 (agp.del_privilege_parse_arguments, del_privilege),
		'privileges':	 (agp.del_privilege_parse_arguments, del_privilege),
		'kw':            (agp.del_keyword_parse_arguments, del_keyword),
		'tag':           (agp.del_keyword_parse_arguments, del_keyword),
		'tags':          (agp.del_keyword_parse_arguments, del_keyword),
		'keyword':       (agp.del_keyword_parse_arguments, del_keyword),
		'keywords':      (agp.del_keyword_parse_arguments, del_keyword),
	}

	cli_main(functions, _app)
