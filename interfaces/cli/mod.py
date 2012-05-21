#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

mod - modify system information and data.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

from licorn.interfaces.cli import LicornCliApplication

def mod_main():

	LicornCliApplication({
		'users':         ('mod_user_parse_arguments', 'mod_user'),
		'groups':        ('mod_group_parse_arguments', 'mod_group'),
		'profiles':      ('mod_profile_parse_arguments', 'mod_profile'),
		'configuration': ('mod_configuration_parse_arguments',
													'mod_configuration'),
		'machines':      ('mod_machine_parse_arguments', 'mod_machine'),
		'clients':       ('mod_machine_parse_arguments', 'mod_machine'),
		'volumes':       ('mod_volume_parse_arguments', 'mod_volume'),
		'tags':          ('mod_keyword_parse_arguments', 'mod_keyword'),
		'keywords':      ('mod_keyword_parse_arguments', 'mod_keyword'),
		'path':          ('mod_path_parse_arguments', 'mod_path'),
		}, {
		"name"     		: "licorn-modify",
		"description"	: "Licorn Modify Entries",
		"author"   		: 'Olivier Cortès <olive@deep-ocean.net>, '
							'Régis Cobrun <reg53fr@yahoo.fr>, '
							'Robin Lucbernet <robinlucbernet@gmail.com>'
		})

if __name__ == "__main__":
	mod_main()
