#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

check - check and repair things on an Licorn System.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

from licorn.foundations           import logging
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import filters
from licorn.interfaces.cli        import cli_main

_app = {
	"name"     		: "licorn-check",
	"description"	: "Licorn Check Entries",
	"author"   		: 'Olivier Cortès <olive@deep-ocean.net>, '
		'Régis Cobrun <reg53fr@yahoo.fr>, '
		'Robin Lucbernet <robinlucbernet@gmail.com>, '
	}

def chk_main():

	functions = {
		'usr':	         ('chk_user_parse_arguments', 'chk_user'),
		'user':	         ('chk_user_parse_arguments', 'chk_user'),
		'users':         ('chk_user_parse_arguments', 'chk_user'),
		'grp':           ('chk_group_parse_arguments', 'chk_group'),
		'group':         ('chk_group_parse_arguments', 'chk_group'),
		'groups':        ('chk_group_parse_arguments', 'chk_group'),
		'profile':       ('chk_profile_parse_arguments', 'chk_profile'),
		'profiles':      ('chk_profile_parse_arguments', 'chk_profile'),
		'conf':			 ('chk_configuration_parse_arguments',
			'chk_configuration'),
		'config':		 ('chk_configuration_parse_arguments',
			'chk_configuration'),
		'configuration': ('chk_configuration_parse_arguments',
			'chk_configuration'),
	}

	cli_main(functions, _app)

if __name__ == "__main__":
	chk_main()
