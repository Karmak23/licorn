#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

getent - display and export system information / lists.

Copyright (C) 2005-2007 Olivier Cortès <oc@5sys.fr>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import sys
from licorn.foundations import logging, exceptions, options
from licorn.core        import configuration, users, groups, profiles, keywords

_app = {
	"name"     		 : "licorn-getent",
	"description"	 : "Licorn Get Entries",
	"author"   		 : "Olivier Cortès <oc@5sys.fr>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def getent_users() :
	""" Get the list of POSIX user accounts (Samba / LDAP included). """

	if opts.uid is not None :
		try :
			users.Select("uid=" + unicode(opts.uid))
		except KeyError :
			logging.error("No user found")
			return
	elif not opts.factory :
		users.Select(users.FILTER_STANDARD)
	if opts.xml :
		data = users.ExportXML(opts.long)
	else :
		data = users.ExportCLI(opts.long)

	if data and data != '\n' :
		sys.stdout.write(data)
def getent_groups() :
	""" Get the list of POSIX groups (can be LDAP). """

	if opts.gid is not None :
		try :
			groups.Select("gid=" + unicode(opts.gid))
		except KeyError :
			logging.error("No group found")

	elif opts.privileged :
		groups.Select(groups.FILTER_PRIVILEGED)

	elif opts.responsibles :
		groups.Select(groups.FILTER_RESPONSIBLE)

	elif opts.guests :
		groups.Select(groups.FILTER_GUEST)

	elif opts.empty :
		groups.Select(groups.FILTER_EMPTY)

	# must be the last case !
	elif not opts.factory :
		groups.Select(groups.FILTER_STANDARD)

	if opts.xml :
		data = groups.ExportXML()
	else :
		data = groups.ExportCLI()

	if data and data != '\n' :
		sys.stdout.write(data)
def getent_profiles() :
	""" Get the list of user profiles. """

	if opts.profile is not None :
		try :
			profiles.Select("profile=" + unicode(opts.profile))
		except KeyError :
			logging.error("No profile found")
			return
	if opts.xml :
		data = profiles.ExportXML()
	else :
		data = profiles.ExportCLI()

	if data :
		sys.stdout.write(data)
def getent_keywords() :
	""" Get the list of keywords. """

	if opts.xml :
		data = keywords.ExportXML()
	else :		
		data = keywords.Export()
	
	if data and data != '\n' :
		sys.stdout.write(data)
def getent_webfilters(args) :
	""" Get the list of webfilter databases and entries.
		This function wraps SquidGuard configuration files.
	"""

	if args is None :
		pass # Tout afficher
	elif args == "time-constraints" :
		import licorn.system.time_constraints as timeconstraints
		tc = timeconstraints.TimeConstraintsList()
		if opts.timespace is None :
			if opts.xml is None :
				print "timepause :"
				print tc.Export("timepause")
				print "timeworkingday :"
				print tc.Export("timeworkingday")
			else :
				print tc.ExportXML("timepause")
				print tc.ExportXML("timeworkingday")
		else :
			if opts.xml is None :
				print tc.Export(opts.timespace)
			else :
				print tc.ExportXML(opts.timespace)
 	elif args == "forbidden-destinations" :
 		import licorn.system.forbidden_dest as forbiddendest
		fd = forbiddendest.ForbiddenDestList()
		if opts.xml :
			print "<?xml version='1.0'?>"
			print "<blacklist>"
			print fd.ExportXML("blacklist", "urls")
			print fd.ExportXML("blacklist", "domains")
			print "</blacklist>"
			print "<whitelist>"
			print fd.ExportXML("whitelist", "urls")
			print fd.ExportXML("whitelist", "domains")
			print "</whitelist>"
		else :
			print "* BLACKLIST :"
			print "Urls :"
			print fd.Export("blacklist", "urls")
			print ""
			print "Domains :"
			print fd.Export("blacklist", "domains")
			print "\n"
			print "* WHITELIST :"
			print "Urls :"
			print fd.Export("whitelist", "urls")
			print ""
			print "Domains :"
			print fd.Export("whitelist", "domains")
	else :
		print "Options are : time-constraints | forbidden-destinations"
def getent_workstations() :
	""" Get the list of workstations known from the server (attached or not).
	"""
	raise NotImplementedError("getent_workstations not implemented.")
def getent_internet_types() :
	""" Get the list of known internet connection types.

		This list is static : there are only a fixed number of connexions
		we know (pppoe, router on (eth0|eth1), analog modem, manual).
	"""
	raise NotImplementedError("getent_internet_types not implemented.")
def getent_configuration() :
	""" Output th current Licorn system configuration.
	"""

	if len(args) > 1 :
		sys.stdout.write(configuration.Export(args = args[1:], cli_format = opts.cli_format))
	else :
		sys.stdout.write(configuration.Export())

if __name__ == "__main__" :

	try :
		try :
			if "--no-colors" in sys.argv :
				options.SetNoColors(True)

			import argparser

			if len(sys.argv) < 2 :
				# auto-display usage when called with no arguments or just one.
				sys.argv.append("--help")
				argparser.general_parse_arguments(_app)

			mode = sys.argv[1]

			if mode in ('user', 'users', 'passwd') :
				(opts, args) = argparser.getent_users_parse_arguments(_app)
				options.SetFrom(opts)
				getent_users()
			elif mode in ('group', 'groups') :
				(opts, args) = argparser.getent_groups_parse_arguments(_app)
				options.SetFrom(opts)
				getent_groups()
			elif mode in ('profile', 'profiles') :
				(opts, args) = argparser.getent_profiles_parse_arguments(_app)
				options.SetFrom(opts)
				getent_profiles()
			elif mode in ('config', 'configuration') :
				(opts, args) = argparser.getent_configuration_parse_arguments(_app)
				options.SetFrom(opts)
				getent_configuration()
			elif mode in ('kw', 'keywords') :
				(opts, args) = argparser.getent_keywords_parse_arguments(_app)
				options.SetFrom(opts)
				getent_keywords()
			else :
				if mode != '--version' :
					logging.warning(logging.GENERAL_UNKNOWN_MODE % mode)
				sys.argv.append("--help")
				argparser.general_parse_arguments(_app)

		except exceptions.LicornException, e :
			logging.error (str(e), e.errno)

		except KeyboardInterrupt :
			logging.warning(logging.GENERAL_INTERRUPTED)

	finally :
		configuration.CleanUp()
