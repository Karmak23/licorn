#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

check - check and repair things on an Licorn System.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys, os

from licorn.foundations         import logging, exceptions
from licorn.foundations.objects import FileLock
from licorn.foundations.constants import filters
from licorn.foundations.ltrace    import ltrace

from licorn.core.configuration  import LicornConfiguration
from licorn.core.users          import UsersController
from licorn.core.groups         import GroupsController

_app = {
	"name"     		: "licorn-check",
	"description"	: "Licorn Check Entries",
	"author"   		: "Olivier Cortès <olive@deep-ocean.net>"
	}

def chk_user(opts, args):
	""" Check one or more user account(s). """

	configuration = LicornConfiguration()
	users = UsersController(configuration)

	uids_to_chk = cli_select(users, 'user',
			args,
			[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			],
			filters.NONE,
			opts.all)

	ltrace('chk', '> chk_user(%s)' % uids_to_chk)

	if uids_to_chk != []:
		users.CheckUsers(uids_to_chk, opts.minimal, auto_answer=opts.auto_answer,
			batch=opts.batch)

	ltrace('chk', '< chk_user()')
def chk_group(opts, args):
	""" Check one or more group(s). """

	configuration = LicornConfiguration()
	users = UsersController(configuration)

	# don't show warnings. If user has asked for a check, he already
	# thinks there is something wrong, which *will* be raised by the check,
	# so don't print twice !
	groups = GroupsController(configuration, users, warnings=False)

	gids_to_chk = cli_select(groups, 'group',
			args,
			[
				(opts.name, groups.name_to_gid),
				(opts.gid, groups.confirm_gid)
			],
			filters.STD,
			opts.all)

	ltrace('chk', '> chk_group(%s)' % gids_to_chk)

	if gids_to_chk != []:
		groups.CheckGroups(gids_to_chk, minimal=opts.minimal,
			batch=opts.batch, auto_answer=opts.auto_answer, force=opts.force)
	ltrace('chk', '< chk_group()')
def chk_profile(opts, args):
	""" TODO: to be implemented. """

	raise NotImplementedError("Sorry, not yet.")
def chk_configuration(opts, args):
	""" TODO: to be implemented. """

	configuration = LicornConfiguration()
	configuration.check(opts.minimal, opts.batch, opts.auto_answer)

if __name__ == "__main__":

	import argparser as agp
	from licorn.interfaces.cli import cli_main, cli_select

	functions = {
		'usr':	         (agp.chk_user_parse_arguments, chk_user),
		'user':	         (agp.chk_user_parse_arguments, chk_user),
		'users':         (agp.chk_user_parse_arguments, chk_user),
		'grp':           (agp.chk_group_parse_arguments, chk_group),
		'group':         (agp.chk_group_parse_arguments, chk_group),
		'groups':        (agp.chk_group_parse_arguments, chk_group),
		'profile':       (agp.chk_profile_parse_arguments, chk_profile),
		'profiles':      (agp.chk_profile_parse_arguments, chk_profile),
		'conf':			 (agp.chk_configuration_parse_arguments, chk_configuration),
		'config':		 (agp.chk_configuration_parse_arguments, chk_configuration),
		'configuration': (agp.chk_configuration_parse_arguments, chk_configuration),
	}

	cli_main(functions, _app)
