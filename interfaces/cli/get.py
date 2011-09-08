#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

get - display and export system information / lists.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import uuid, signal
from traceback import print_exc
from licorn.interfaces.cli import cli_main

def get_events(RWI, opts, args):
	""" We need to build an UUID because every call to RWI gets handled by a
		separate thread on the remote side. We have to unregister the original,
		which did the first `register` call. """

	my_uuid = uuid.uuid4()

	RWI.register_monitor(my_uuid, opts.facilities)

	try:
		signal.pause()

	finally:
		RWI.unregister_monitor(my_uuid)

def get_main():

	cli_main({
		'users':         ('get_users_parse_arguments', 'get_users'),
		'passwd':        ('get_users_parse_arguments', 'get_users'),
		'groups':        ('get_groups_parse_arguments', 'get_groups'),
		'profiles':      ('get_profiles_parse_arguments', 'get_profiles'),
		'machines':      ('get_machines_parse_arguments', 'get_machines'),
		'clients':       ('get_machines_parse_arguments', 'get_machines'),
		'configuration': ('get_configuration_parse_arguments',
														'get_configuration'),
		'privileges':	 ('get_privileges_parse_arguments',	'get_privileges'),
		'tags':          ('get_keywords_parse_arguments', 'get_keywords'),
		'keywords':      ('get_keywords_parse_arguments', 'get_keywords'),
		'daemon_status': ('get_daemon_status_parse_arguments',
														'get_daemon_status'),
		'events'       : ('get_events_parse_arguments',
														None, get_events),
		'volumes':       ('get_volumes_parse_arguments', 'get_volumes'),
		}, {
		"name"     		: "licorn-get",
		"description"	: "Licorn Get Entries",
		"author"   		: 'Olivier Cortès <olive@deep-ocean.net>, '
							'Régis Cobrun <reg53fr@yahoo.fr>, '
							'Robin Lucbernet <robinlucbernet@gmail.com>'
		}, expected_min_args=2)

if __name__ == "__main__":
	get_main()
