#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

get - display and export system information / lists.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

from licorn.interfaces.cli import cli_main

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
