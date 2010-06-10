#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

getent - display and export system information / lists.

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import sys
output = sys.stdout.write
from licorn.foundations import logging, exceptions, options

_app = {
	"name"     		: "licorn-getent",
	"description"	: "Licorn Get Entries",
	"author"   		: "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def getent_users(opts, args):
	""" Get the list of POSIX user accounts (Samba / LDAP included). """

	from licorn.core import users

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
def getent_groups(opts, args):
	""" Get the list of POSIX groups (can be LDAP). """

	from licorn.core import groups

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
		data = groups.ExportXML()
	else:
		data = groups.ExportCLI()

	if data and data != '\n':
		output(data)
def getent_profiles(opts, args):
	""" Get the list of user profiles. """

	from licorn.core import profiles

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
def getent_keywords(opts, args):
	""" Get the list of keywords. """

	from licorn.core import keywords
	
	if opts.xml:
		data = keywords.ExportXML()
	else:		
		data = keywords.Export()
	
	if data and data != '\n':
		output(data)
def getent_webfilters(opts, args):
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
def getent_workstations(opts, args):
	""" Get the list of workstations known from the server (attached or not).
	"""
	raise NotImplementedError("getent_workstations not implemented.")
def getent_internet_types(opts, args):
	""" Get the list of known internet connection types.

		This list is static: there are only a fixed number of connexions
		we know (pppoe, router on (eth0|eth1), analog modem, manual).
	"""
	raise NotImplementedError("getent_internet_types not implemented.")
def getent_configuration(opts, args):
	""" Output th current Licorn system configuration.
	"""
	from licorn.core import configuration

	if len(args) > 1:
		output(configuration.Export(args = args[1:], cli_format = opts.cli_format))
	else:
		output(configuration.Export())

if __name__ == "__main__":

	import argparser
	from licorn.interfaces.cli import cli_main
	
	functions = {
		'user':	         (argparser.getent_users_parse_arguments, getent_users),
		'users':         (argparser.getent_users_parse_arguments, getent_users),
		'passwd':        (argparser.getent_users_parse_arguments, getent_users),
		'group':         (argparser.getent_groups_parse_arguments, getent_groups),
		'groups':        (argparser.getent_groups_parse_arguments, getent_groups),
		'profile':       (argparser.getent_profiles_parse_arguments, getent_profiles),
		'profiles':      (argparser.getent_profiles_parse_arguments, getent_profiles),
		'config':        (argparser.getent_configuration_parse_arguments, getent_configuration),
		'configuration': (argparser.getent_configuration_parse_arguments, getent_configuration),
		'kw':            (argparser.getent_keywords_parse_arguments, getent_keywords),
		'keywords':      (argparser.getent_keywords_parse_arguments, getent_keywords),
	}

	cli_main(functions, _app)

