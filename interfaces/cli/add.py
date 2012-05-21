#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://ilcorn.org/documentation/cli

add - add something on the system, a user account, a group…

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

from licorn.interfaces.cli import LicornCliApplication

def add_main():

	LicornCliApplication({
		'users':         ('add_user_parse_arguments', 'dispatch_add_user'),
		'groups':        ('add_group_parse_arguments', 'add_group'),
		'profiles':      ('add_profile_parse_arguments', 'add_profile'),
		'privileges':	 ('add_privilege_parse_arguments', 'add_privilege'),
		'keywords':      ('add_keyword_parse_arguments', 'add_keyword'),
		'tags':          ('add_keyword_parse_arguments', 'add_keyword'),
		'machines':		 ('add_machine_parse_arguments', 'add_machine'),
		'clients':		 ('add_machine_parse_arguments', 'add_machine'),
		'volumes':       ('add_volume_parse_arguments', 'add_volume'),
		'tasks':         ('add_task_parse_arguments', 'add_task'),
		}, {
		"name"        : "licorn-add",
		"description" : "Licorn Add Entries",
		"author"      : 'Olivier Cortès <olive@deep-ocean.net>, '
						'Régis Cobrun <reg53fr@yahoo.fr>, '
						'Robin Lucbernet <robinlucbernet@gmail.com>'
		})

if __name__ == "__main__":
	add_main()
