#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

check - check and repair things on an Licorn System.

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys, os

from licorn.foundations import logging, exceptions, options, objects
from licorn.core        import configuration, users, groups

_app = {
	"name"     		: "licorn-check",
	"description"	: "Licorn Check Entries",
	"author"   		: "Olivier Cortès <olive@deep-ocean.net>"
	}

def check_users():
	""" Check one or more user account(s). """

	if opts.all:
		users_to_check = []
	else:
		if opts.users is None:
			logging.error("You didn't specify any user !")
		else:
			# don't unicode the logins, they should be standard strings.
			users_to_check = opts.users.split(',')

	users.CheckUsers(users_to_check, opts.minimal, auto_answer = opts.auto_answer, batch = opts.batch)
def check_groups():
	""" Check one or more group(s). """

	# don't show warnings. If user has asked for a check, he already
	# thinks there is something wrong, which *will* be raised by the check,
	# so don't print twice !

	# XXX: in Licorn, groups are initialized earlyer, this can't be done anymore.
	# groups.SetWarnings(False)

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

	groups.CheckGroups(groups_to_check, opts.minimal, auto_answer = opts.auto_answer, batch = opts.batch)

	# TODO: do this more cleanly and not so hard-coded:
	try:
		#os.system("/etc/init.d/licornd start >/dev/null 2>&1")
		pass
	except:
		pass
def check_profiles():
	""" TODO: to be implemented. """
	raise NotImplementedError("Sorry, not yet.")
def check_configuration():
	""" TODO: to be implemented. """

	from licorn.core import configuration

	configuration.check(opts.minimal, opts.batch, opts.auto_answer)

if __name__ == "__main__":

	try:
		giantLock = objects.FileLock(configuration, "giant", 10)
		giantLock.Lock()
	except (IOError, OSError), e:
		logging.error(logging.GENERAL_CANT_ACQUIRE_GIANT_LOCK % str(e))

	try:
		try:

			if "--no-colors" in sys.argv:
				options.SetNoColors(True)

			from licorn.interfaces.cli import argparser

			if len(sys.argv) < 2:
				# auto-display usage when called with no arguments or just one.
				sys.argv.append("--help")
				argparser.general_parse_arguments(_app)

			if len(sys.argv) < 3:
				# this will display help, but when parsed later by specific functions.
				# (for user/group/profile specific help)
				sys.argv.append("--help")
				help_appended = True
			else:
				help_appended = False

			mode = sys.argv[1]

			if mode in ('user', 'users'):
				(opts, args) = argparser.check_users_parse_arguments(_app)
				if len(args) == 2:
					opts.users = args[1]
				options.SetFrom(opts)
				check_users()
			elif mode in ('group', 'groups'):
				(opts, args) = argparser.check_groups_parse_arguments(_app)
				if len(args) == 2:
					opts.groups = args[1]
				options.SetFrom(opts)
				check_groups()
			elif mode in ('profile', 'profiles'):
				(opts, args) = argparser.check_profiles_parse_arguments(_app)
				if len(args) == 2:
					opts.name = args[1]
				options.SetFrom(opts)
				check_profiles()
			elif mode in ('config', 'configuration'):
				(opts, args) = argparser.check_configuration_parse_arguments(_app)
				options.SetVerbose(opts.verbose)
				check_configuration()
			else:
				if not help_appended:
					logging.warning(logging.GENERAL_UNKNOWN_MODE % mode)
					sys.argv.append("--help")

				argparser.general_parse_arguments(_app)

		except exceptions.LicornException, e:
			logging.error (str(e), e.errno)

		except KeyboardInterrupt:
			logging.warning(logging.GENERAL_INTERRUPTED)

	finally:
		configuration.CleanUp()
		giantLock.Unlock()
