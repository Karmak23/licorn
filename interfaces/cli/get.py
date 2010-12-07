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

from licorn.interfaces.cli import cli_main

_app = {
	"name"     		: "licorn-get",
	"description"	: "Licorn Get Entries",
	"author"   		: 'Olivier Cortès <olive@deep-ocean.net>, '
		'Régis Cobrun <reg53fr@yahoo.fr>, '
		'Robin Lucbernet <robinlucbernet@gmail.com>, '
	}

def get_main():

	functions = {
		'usr':	         ('get_users_parse_arguments', 'get_users'),
		'user':	         ('get_users_parse_arguments', 'get_users'),
		'users':         ('get_users_parse_arguments', 'get_users'),
		'passwd':        ('get_users_parse_arguments', 'get_users'),
		'grp':           ('get_groups_parse_arguments', 'get_groups'),
		'group':         ('get_groups_parse_arguments', 'get_groups'),
		'groups':        ('get_groups_parse_arguments', 'get_groups'),
		'profile':       ('get_profiles_parse_arguments', 'get_profiles'),
		'profiles':      ('get_profiles_parse_arguments', 'get_profiles'),
		'machine':       ('get_machines_parse_arguments', 'get_machines'),
		'machines':      ('get_machines_parse_arguments', 'get_machines'),
		'client':        ('get_machines_parse_arguments', 'get_machines'),
		'clients':       ('get_machines_parse_arguments', 'get_machines'),
		'workstation':   ('get_machines_parse_arguments', 'get_machines'),
		'workstations':  ('get_machines_parse_arguments', 'get_machines'),
		'conf':          ('get_configuration_parse_arguments',
			'get_configuration'),
		'config':        ('get_configuration_parse_arguments',
			'get_configuration'),
		'configuration': ('get_configuration_parse_arguments',
			'get_configuration'),
		'priv':			 ('get_privileges_parse_arguments',
			'get_privileges'),
		'privs':		 ('get_privileges_parse_arguments',
			'get_privileges'),
		'privilege':	 ('get_privileges_parse_arguments',
			'get_privileges'),
		'privileges':	 ('get_privileges_parse_arguments',
			'get_privileges'),
		'kw':            ('get_keywords_parse_arguments', 'get_keywords'),
		'tag':           ('get_keywords_parse_arguments', 'get_keywords'),
		'tags':          ('get_keywords_parse_arguments', 'get_keywords'),
		'keyword':       ('get_keywords_parse_arguments', 'get_keywords'),
		'keywords':      ('get_keywords_parse_arguments', 'get_keywords'),
		'status':        ('get_daemon_status_parse_arguments',
			'get_daemon_status'),
		'daemon_status': ('get_daemon_status_parse_arguments',
			'get_daemon_status'),
	}

	cli_main(functions, _app, expected_min_args=2)

if __name__ == "__main__":
	get_main()
