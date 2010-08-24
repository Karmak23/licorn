#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

get - display and export system information / lists.

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import sys
output = sys.stdout.write

from licorn.foundations        import logging, exceptions, options
from licorn.core.configuration import LicornConfiguration
from licorn.core.users         import UsersController
from licorn.core.groups        import GroupsController
from licorn.core.profiles      import ProfilesController
from licorn.core.keywords      import KeywordsController

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

	if opts.uid is not None:
		try:
			users.Select("uid=" + unicode(opts.uid))
		except KeyError:
			logging.error("No user found")
			return
	elif not opts.factory:
		users.Select(users.FILTER_STANDARD)
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

	if opts.gid is not None:
		try:
			groups.Select("gid=" + unicode(opts.gid))
		except KeyError:
			logging.error("No group found")

	elif opts.privileged:
		groups.Select(groups.FILTER_PRIVILEGED)

	elif opts.responsibles:
		groups.Select(groups.FILTER_RESPONSIBLE)

	elif opts.guests:
		groups.Select(groups.FILTER_GUEST)

	elif opts.empty:
		groups.Select(groups.FILTER_EMPTY)

	# must be the last case !
	elif not opts.factory:
		groups.Select(groups.FILTER_STANDARD)

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

	if opts.profile is not None:
		try:
			profiles.Select("profile=" + unicode(opts.profile))
		except KeyError:
			logging.error("No profile found")
			return
	if opts.xml:
		data = profiles.ExportXML()
	else:
		data = profiles.ExportCLI()

	if data:
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
	output(configuration.Export(args = ['privileges'], cli_format = opts.cli_format))
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
def get_workstations(opts, args):
	""" Get the list of workstations known from the server (attached or not).
	"""
	raise NotImplementedError("get_workstations not implemented.")
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
	from licorn.interfaces.cli import cli_main

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
		'conf':          (agp.get_configuration_parse_arguments, get_configuration),
		'config':        (agp.get_configuration_parse_arguments, get_configuration),
		'configuration': (agp.get_configuration_parse_arguments, get_configuration),
		'priv':			 (agp.get_configuration_parse_arguments, get_privileges),
		'privs':		 (agp.get_configuration_parse_arguments, get_privileges),
		'privilege':	 (agp.get_configuration_parse_arguments, get_privileges),
		'privileges':	 (agp.get_configuration_parse_arguments, get_privileges),
		'kw':            (agp.get_keywords_parse_arguments, get_keywords),
		'tag':           (agp.get_keywords_parse_arguments, get_keywords),
		'tags':          (agp.get_keywords_parse_arguments, get_keywords),
		'keyword':       (agp.get_keywords_parse_arguments, get_keywords),
		'keywords':      (agp.get_keywords_parse_arguments, get_keywords),
	}

	cli_main(functions, _app)

