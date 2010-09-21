#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

get - display and export system information / lists.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import sys
output = sys.stdout.write

from licorn.foundations           import logging, exceptions, options
from licorn.foundations.constants import filters

from licorn.core.configuration    import LicornConfiguration
from licorn.core.users            import UsersController
from licorn.core.groups           import GroupsController
from licorn.core.profiles         import ProfilesController
from licorn.core.keywords         import KeywordsController
from licorn.core.machines         import MachinesController

_app = {
	"name"     		: "licorn-get",
	"description"	: "Licorn Get Entries",
	"author"   		: "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def get_users(opts, args):
	""" Get the list of POSIX user accounts (Samba / LDAP included). """

	configuration = LicornConfiguration()
	users = UsersController(configuration)

	if opts.long:
		groups = GroupsController(configuration, users)

	users.Select(
		cli_select(users, 'user',
			args,
			[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			],
			filters.STANDARD,
			opts.all)
		)

	if opts.xml:
		data = users.ExportXML(opts.long)
	else:
		data = users.ExportCLI(opts.long)

	if data and data != '\n':
		output(data)
def get_groups(opts, args):
	""" Get the list of POSIX groups (can be LDAP). """

	configuration = LicornConfiguration()
	users = UsersController(configuration)
	groups = GroupsController(configuration, users)

	selection = filters.NONE

	if opts.privileged:
		selection = filters.PRIVILEGED
	elif opts.responsibles:
		selection = filters.RESPONSIBLE
	elif opts.guests:
		selection = filters.GUEST
	elif opts.system:
		selection = filters.SYSTEM
	elif opts.empty:
		selection = filters.EMPTY
	elif not opts.all:
		# must be the last case !
		selection = filters.STANDARD

	groups.Select(
		cli_select(groups, 'group',
			args,
			[
				(opts.name, groups.name_to_gid),
				(opts.gid, groups.confirm_gid)
			],
			selection,
			opts.all)
		)

	if opts.xml:
		data = groups.ExportXML(opts.long)
	else:
		data = groups.ExportCLI(opts.long)

	if data and data != '\n':
		output(data)
def get_profiles(opts, args):
	""" Get the list of user profiles. """

	configuration = LicornConfiguration()
	users = UsersController(configuration)
	groups = GroupsController(configuration, users)
	profiles = ProfilesController(configuration, groups, users)

	profiles.Select(
		cli_select(profiles, 'profile',
			args,
			[
				(opts.name, profiles.name_to_group),
				(opts.group, profiles.confirm_group)
			],
			filters.ALL)
		)

	if opts.xml:
		data = profiles.ExportXML()
	else:
		data = profiles.ExportCLI()

	if data and data != '\n':
		output(data)
def get_keywords(opts, args):
	""" Get the list of keywords. """

	configuration = LicornConfiguration()
	keywords = KeywordsController(configuration)

	if opts.xml:
		data = keywords.ExportXML()
	else:
		data = keywords.Export()

	if data and data != '\n':
		output(data)
def get_privileges(opts, args):
	configuration = LicornConfiguration()
	output(configuration.Export(args = ['privileges']))
def get_webfilters(opts, args):
	""" Get the list of webfilter databases and entries.
		This function wraps SquidGuard configuration files.
	"""

	if args is None:
		pass # Tout afficher
	elif args == "time-constraints":
		import licorn.system.time_constraints as timeconstraints
		tc = timeconstraints.TimeConstraintsList()
		if opts.timespace is None:
			if opts.xml is None:
				print "timepause:"
				print tc.Export("timepause")
				print "timeworkingday:"
				print tc.Export("timeworkingday")
			else:
				print tc.ExportXML("timepause")
				print tc.ExportXML("timeworkingday")
		else:
			if opts.xml is None:
				print tc.Export(opts.timespace)
			else:
				print tc.ExportXML(opts.timespace)
 	elif args == "forbidden-destinations":
 		import licorn.system.forbidden_dest as forbiddendest
		fd = forbiddendest.ForbiddenDestList()
		if opts.xml:
			print "<?xml version='1.0'?>"
			print "<blacklist>"
			print fd.ExportXML("blacklist", "urls")
			print fd.ExportXML("blacklist", "domains")
			print "</blacklist>"
			print "<whitelist>"
			print fd.ExportXML("whitelist", "urls")
			print fd.ExportXML("whitelist", "domains")
			print "</whitelist>"
		else:
			print "* BLACKLIST:"
			print "Urls:"
			print fd.Export("blacklist", "urls")
			print ""
			print "Domains:"
			print fd.Export("blacklist", "domains")
			print "\n"
			print "* WHITELIST:"
			print "Urls:"
			print fd.Export("whitelist", "urls")
			print ""
			print "Domains:"
			print fd.Export("whitelist", "domains")
	else:
		print "Options are: time-constraints | forbidden-destinations"
def get_machines(opts, args):
	""" Get the list of machines known from the server (attached or not). """
	configuration = LicornConfiguration()
	machines = MachinesController(configuration)

	if opts.mid is not None:
		try:
			machines.Select("mid=" + unicode(opts.mid))
		except KeyError:
			logging.error(_("No matching machine found."))
			return

	if opts.xml:
		data = machines.ExportXML(opts.long)
	else:
		data = machines.ExportCLI(opts.long)

	if data and data != '\n':
		output(data)

def get_internet_types(opts, args):
	""" Get the list of known internet connection types.

		This list is static: there are only a fixed number of connexions
		we know (pppoe, router on (eth0|eth1), analog modem, manual).
	"""
	raise NotImplementedError("get_internet_types not implemented.")
def get_configuration(opts, args):
	""" Output th current Licorn system configuration. """

	configuration = LicornConfiguration()

	if len(args) > 1:
		output(configuration.Export(args = args[1:], cli_format = opts.cli_format))
	else:
		output(configuration.Export())

if __name__ == "__main__":

	import argparser as agp
	from licorn.interfaces.cli import cli_main, cli_select

	functions = {
		'usr':	         (agp.get_users_parse_arguments, get_users),
		'user':	         (agp.get_users_parse_arguments, get_users),
		'users':         (agp.get_users_parse_arguments, get_users),
		'passwd':        (agp.get_users_parse_arguments, get_users),
		'grp':           (agp.get_groups_parse_arguments, get_groups),
		'group':         (agp.get_groups_parse_arguments, get_groups),
		'groups':        (agp.get_groups_parse_arguments, get_groups),
		'profile':       (agp.get_profiles_parse_arguments, get_profiles),
		'profiles':      (agp.get_profiles_parse_arguments, get_profiles),
		'machine':       (agp.get_machines_parse_arguments, get_machines),
		'machines':      (agp.get_machines_parse_arguments, get_machines),
		'client':        (agp.get_machines_parse_arguments, get_machines),
		'clients':       (agp.get_machines_parse_arguments, get_machines),
		'workstation':   (agp.get_machines_parse_arguments, get_machines),
		'workstations':  (agp.get_machines_parse_arguments, get_machines),
		'conf':          (agp.get_configuration_parse_arguments, get_configuration),
		'config':        (agp.get_configuration_parse_arguments, get_configuration),
		'configuration': (agp.get_configuration_parse_arguments, get_configuration),
		'priv':			 (agp.get_privileges_parse_arguments, get_privileges),
		'privs':		 (agp.get_privileges_parse_arguments, get_privileges),
		'privilege':	 (agp.get_privileges_parse_arguments, get_privileges),
		'privileges':	 (agp.get_privileges_parse_arguments, get_privileges),
		'kw':            (agp.get_keywords_parse_arguments, get_keywords),
		'tag':           (agp.get_keywords_parse_arguments, get_keywords),
		'tags':          (agp.get_keywords_parse_arguments, get_keywords),
		'keyword':       (agp.get_keywords_parse_arguments, get_keywords),
		'keywords':      (agp.get_keywords_parse_arguments, get_keywords),
	}

	cli_main(functions, _app, expected_min_args=2)

