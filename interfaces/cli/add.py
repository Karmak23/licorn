#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://ilcorn.org/documentation/cli

add - add something on the system, a user account, a group…

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys

from licorn.foundations           import logging, exceptions
from licorn.foundations           import hlstr, fsapi
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import filters
from licorn.interfaces.cli        import cli_main

_app = {
	"name"        : "licorn-add",
	"description" : "Licorn Add Entries",
	"author"   		: 'Olivier Cortès <olive@deep-ocean.net>, '
		'Régis Cobrun <reg53fr@yahoo.fr>, '
		'Robin Lucbernet <robinlucbernet@gmail.com>, '
	}

def add_main():

	functions = {
		'usr':	         ('add_user_parse_arguments', 'dispatch_add_user'),
		'user':	         ('add_user_parse_arguments', 'dispatch_add_user'),
		'users':         ('addimport_parse_arguments', 'import_users'),
		'grp':           ('add_group_parse_arguments', 'add_group'),
		'group':         ('add_group_parse_arguments', 'add_group'),
		'groups':        ('add_group_parse_arguments', 'add_group'),
		'profile':       ('add_profile_parse_arguments', 'add_profile'),
		'profiles':      ('add_profile_parse_arguments', 'add_profile'),
		'priv':			 ('add_privilege_parse_arguments', 'add_privilege'),
		'privs':		 ('add_privilege_parse_arguments', 'add_privilege'),
		'privilege':	 ('add_privilege_parse_arguments', 'add_privilege'),
		'privileges':	 ('add_privilege_parse_arguments', 'add_privilege'),
		'kw':            ('add_keyword_parse_arguments', 'add_keyword'),
		'tag':           ('add_keyword_parse_arguments', 'add_keyword'),
		'tags':          ('add_keyword_parse_arguments', 'add_keyword'),
		'keyword':       ('add_keyword_parse_arguments', 'add_keyword'),
		'keywords':      ('add_keyword_parse_arguments', 'add_keyword'),
		'machine':		 ('add_machine_parse_arguments', 'add_machine'),
		'machines':		 ('add_machine_parse_arguments', 'add_machine'),
		'client':		 ('add_machine_parse_arguments', 'add_machine'),
		'clients':		 ('add_machine_parse_arguments', 'add_machine'),
	}

	cli_main(functions, _app)

if __name__ == "__main__":
	add_main()
