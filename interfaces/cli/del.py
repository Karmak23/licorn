#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

delete - delete sompething on the system, an unser account, a group, etc.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

from licorn.interfaces.cli import LicornCliApplication

def del_main():

	LicornCliApplication({
		'users':         ('del_user_parse_arguments', 'dispatch_del_user'),
		'groups':        ('del_group_parse_arguments', 'dispatch_del_group'),
		'profiles':      ('del_profile_parse_arguments', 'del_profile'),
		'privileges':	 ('del_privilege_parse_arguments', 'del_privilege'),
		'tags':          ('del_keyword_parse_arguments', 'del_keyword'),
		'keywords':      ('del_keyword_parse_arguments', 'del_keyword'),
		'volumes':       ('del_volume_parse_arguments', 'del_volume'),
		'tasks':         ('del_task_parse_arguments', 'del_task'),
		}, {
		"name"        : "licorn-delete",
		"description" : "Licorn Delete Entries",
		"author"      : 'Olivier Cortès <olive@deep-ocean.net>, '
						'Régis Cobrun <reg53fr@yahoo.fr>, '
						'Robin Lucbernet <robinlucbernet@gmail.com>'
		})

if __name__ == "__main__":
	del_main()
