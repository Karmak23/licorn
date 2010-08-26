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

	if len(args) == 2:
		opts.users = args[1]

	if opts.all:
		users_to_check = []
	else:
		if opts.users is None:
			logging.error("You didn't specify any user !")
		else:
			# don't unicode the logins, they should be standard strings.
			users_to_check = opts.users.split(',')

	users.CheckUsers(users_to_check, opts.minimal, auto_answer=opts.auto_answer,
		batch=opts.batch)
def chk_group(opts, args):
	""" Check one or more group(s). """

	configuration = LicornConfiguration()
	users = UsersController(configuration)

	# don't show warnings. If user has asked for a check, he already
	# thinks there is something wrong, which *will* be raised by the check,
	# so don't print twice !
	groups = GroupsController(configuration, users, warnings=False)

	if len(args) == 2:
		opts.groups = args[1]

	if opts.all:
		groups_to_check = []
	else:
		if opts.groups is None:
			logging.error("You didn't specify any group !")
		else:
			# don't unicode the groups name, they should be standard strings.
			groups_to_check = opts.groups.split(',')

	#print str(groups_to_check)

	# TODO: do this more cleanly and not so hard-coded:
	try:
		#os.system("/etc/init.d/licornd stop >/dev/null 2>&1")
		pass
	except:
		pass

	groups.CheckGroups(groups_to_check, opts.minimal,
		batch=opts.batch, auto_answer=opts.auto_answer, force=opts.force)

	# TODO: do this more cleanly and not so hard-coded:
	try:
		#os.system("/etc/init.d/licornd start >/dev/null 2>&1")
		pass
	except:
		pass
def chk_profile(opts, args):
	""" TODO: to be implemented. """
	if len(args) == 2:
		opts.name = args[1]

	raise NotImplementedError("Sorry, not yet.")
def chk_configuration(opts, args):
	""" TODO: to be implemented. """

	configuration = LicornConfiguration()
	configuration.check(opts.minimal, opts.batch, opts.auto_answer)

if __name__ == "__main__":

	import argparser as agp
	from licorn.interfaces.cli import cli_main

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
