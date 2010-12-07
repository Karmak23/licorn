#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn « modify »: modify system information, user accounts, etc.
Built on top of Licorn System Library, part of Licorn System Tools (H-S-T).

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""
from licorn.foundations           import logging, exceptions
from licorn.foundations           import hlstr
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import filters, host_status
from licorn.interfaces.cli        import cli_main

_app = {
	"name"     		: "licorn-modify",
	"description"	: "Licorn Modify Entries",
	"author"   		: 'Olivier Cortès <olive@deep-ocean.net>, '
		'Régis Cobrun <reg53fr@yahoo.fr>, '
		'Robin Lucbernet <robinlucbernet@gmail.com>, '
	}

def mod_main():

	functions = {
		'usr':	         ('mod_user_parse_arguments', 'mod_user'),
		'user':	         ('mod_user_parse_arguments', 'mod_user'),
		'users':         ('mod_user_parse_arguments', 'mod_user'),
		'grp':           ('mod_group_parse_arguments', 'mod_group'),
		'group':         ('mod_group_parse_arguments', 'mod_group'),
		'groups':        ('mod_group_parse_arguments', 'mod_group'),
		'profile':       ('mod_profile_parse_arguments', 'mod_profile'),
		'profiles':      ('mod_profile_parse_arguments', 'mod_profile'),
		'conf':			 ('mod_configuration_parse_arguments',
			'mod_configuration'),
		'config':		 ('mod_configuration_parse_arguments',
			'mod_configuration'),
		'configuration': ('mod_configuration_parse_arguments',
			'mod_configuration'),
		'machine':       ('mod_machine_parse_arguments', 'mod_machine'),
		'machines':      ('mod_machine_parse_arguments', 'mod_machine'),
		'client':        ('mod_machine_parse_arguments', 'mod_machine'),
		'clients':       ('mod_machine_parse_arguments', 'mod_machine'),
		'kw':            ('mod_keyword_parse_arguments', 'mod_keyword'),
		'tag':           ('mod_keyword_parse_arguments', 'mod_keyword'),
		'tags':          ('mod_keyword_parse_arguments', 'mod_keyword'),
		'keyword':       ('mod_keyword_parse_arguments', 'mod_keyword'),
		'keywords':      ('mod_keyword_parse_arguments', 'mod_keyword'),
		'path':          ('mod_path_parse_arguments', 'mod_path'),
	}

	cli_main(functions, _app)

if __name__ == "__main__":
	mod_main()
