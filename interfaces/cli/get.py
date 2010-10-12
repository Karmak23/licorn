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

from licorn.foundations           import logging
from licorn.foundations.constants import filters
from licorn.foundations.ltrace    import ltrace

from licorn.interfaces.cli import cli_main, cli_select

_app = {
	"name"     		: "licorn-get",
	"description"	: "Licorn Get Entries",
	"author"   		: "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def get_users(opts, args, users, **kwargs):
	""" Get the list of POSIX user accounts (Samba / LDAP included). """

	ltrace('get', '> get_users(%s,%s)' % (opts, args))

	users_to_get = users.Select(
		cli_select(users, 'user',
			args,
			include_id_lists=[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			],
			exclude_id_lists=[
				(opts.exclude, users.guess_identifier),
				(opts.exclude_login, users.login_to_uid),
				(opts.exclude_uid, users.confirm_uid)
			],
			default_selection=filters.STANDARD,
			all=opts.all)
		)

	if opts.xml:
		data = users.ExportXML(selected=users_to_get, long_output=opts.long)
	else:
		data = users.ExportCLI(selected=users_to_get, long_output=opts.long)

	if data and data != '\n':
		output(data)

	ltrace('get', '< get_users()')
def get_groups(opts, args, groups, **kwargs):
	""" Get the list of POSIX groups (can be LDAP). """

	ltrace('get', '> get_groups(%s,%s)' % (opts, args))

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

	groups_to_get = groups.Select(
		cli_select(groups, 'group',
			args,
			[
				(opts.name, groups.name_to_gid),
				(opts.gid, groups.confirm_gid)
			],
			exclude_id_lists = [
				(opts.exclude, groups.guess_identifier),
				(opts.exclude_group, groups.name_to_gid),
				(opts.exclude_gid, groups.confirm_gid)
			],
			default_selection=selection,
			all=opts.all)
		)

	if opts.xml:
		data = groups.ExportXML(selected=groups_to_get, long_output=opts.long)
	else:
		data = groups.ExportCLI(selected=groups_to_get, long_output=opts.long,
			no_colors=opts.no_colors)

	if data and data != '\n':
		output(data)

	ltrace('get', '< get_groups()')
def get_profiles(opts, args, profiles, **kwargs):
	""" Get the list of user profiles. """

	ltrace('get', '> get_profiles(%s,%s)' % (opts, args))

	profiles_to_get = profiles.Select(
		cli_select(profiles, 'profile',
			args,
			include_id_lists=[
				(opts.name, profiles.name_to_group),
				(opts.group, profiles.confirm_group)
			],
			default_selection=filters.ALL)
		)

	if opts.xml:
		data = profiles.ExportXML(profiles_to_get)
	else:
		data = profiles.ExportCLI(profiles_to_get)

	if data and data != '\n':
		output(data)

	ltrace('get', '< get_profiles()')
def get_keywords(opts, args, keywords, **kwargs):
	""" Get the list of keywords. """

	ltrace('get', '> get_keywords(%s,%s)' % (opts, args))

	if opts.xml:
		data = keywords.ExportXML()
	else:
		data = keywords.Export()

	if data and data != '\n':
		output(data)

	ltrace('get', '< get_keywords()')
def get_privileges(opts, args, privileges, **kwargs):
	""" Return the current privileges whitelist, one priv by line. """

	ltrace('get', '> get_privileges(%s,%s)' % (opts, args))

	if opts.xml:
		data = privileges.ExportXML()
	else:
		data = privileges.ExportCLI()

	output(data)

	ltrace('get', '< get_privileges()')
def get_machines(opts, args, machines, **kwargs):
	""" Get the list of machines known from the server (attached or not). """

	ltrace('get', '> get_machines(%s,%s)' % (opts, args))

	if opts.mid is not None:
		try:
			machines_to_get = machines.Select("mid=" + unicode(opts.mid))
		except KeyError:
			logging.error("No matching machine found.")
			return

	if opts.xml:
		data = machines.ExportXML(selected=machines_to_get,
			long_output=opts.long)
	else:
		data = machines.ExportCLI(selected=machines_to_get,
			long_output=opts.long)

	if data and data != '\n':
		output(data)

	ltrace('get', '< get_machines()')
def get_configuration(opts, args, configuration, **kwargs):
	""" Output th current Licorn system configuration. """

	ltrace('get', '> get_configuration(%s,%s)' % (opts, args))

	if len(args) > 1:
		output(configuration.Export(args=args[1:], cli_format=opts.cli_format))
	else:
		output(configuration.Export())

	ltrace('get', '< get_configuration()')
def get_webfilters(*args, **kwargs):
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

def get_main():
	import argparser as agp

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

if __name__ == "__main__":
	get_main()
