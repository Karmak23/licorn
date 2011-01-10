#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

delete - delete sompething on the system, an unser account, a group, etc.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import sys, re, os

from licorn.foundations           import logging, exceptions
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import filters
from licorn.interfaces.cli        import cli_main

_app = {
	"name"        : "licorn-delete",
	"description" : "Licorn Delete Entries",
	"author"      : 'Olivier Cortès <olive@deep-ocean.net>, '
		'Régis Cobrun <reg53fr@yahoo.fr>, '
		'Robin Lucbernet <robinlucbernet@gmail.com>, '
	}

def del_main():
	""" DELETE main function. """

	functions = {
		'usr':	         ('del_user_parse_arguments', 'dispatch_del_user'),
		'user':	         ('del_user_parse_arguments', 'dispatch_del_user'),
		'users':         ('del_user_parse_arguments', 'dispatch_del_user'),
		'grp':           ('del_group_parse_arguments', 'del_group'),
		'group':         ('del_group_parse_arguments', 'del_group'),
		'groups':        ('delimport_parse_arguments', 'desimport_groups'),
		'profile':       ('del_profile_parse_arguments', 'del_profile'),
		'profiles':      ('del_profile_parse_arguments', 'del_profile'),
		'priv':			 ('del_privilege_parse_arguments', 'del_privilege'),
		'privs':		 ('del_privilege_parse_arguments', 'del_privilege'),
		'privilege':	 ('del_privilege_parse_arguments', 'del_privilege'),
		'privileges':	 ('del_privilege_parse_arguments', 'del_privilege'),
		'kw':            ('del_keyword_parse_arguments', 'del_keyword'),
		'tag':           ('del_keyword_parse_arguments', 'del_keyword'),
		'tags':          ('del_keyword_parse_arguments', 'del_keyword'),
		'keyword':       ('del_keyword_parse_arguments', 'del_keyword'),
		'keywords':      ('del_keyword_parse_arguments', 'del_keyword'),
		'volume':        ('del_volume_parse_arguments', 'del_volume'),
		'volumes':       ('del_volume_parse_arguments', 'del_volume'),
	}

	cli_main(functions, _app)

if __name__ == "__main__":
	del_main()
