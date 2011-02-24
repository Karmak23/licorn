#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

check - check and repair things on an Licorn System.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

from licorn.interfaces.cli import cli_main

def chk_main():

	cli_main({
		'users':         ('chk_user_parse_arguments', 'chk_user'),
		'groups':        ('chk_group_parse_arguments', 'chk_group'),
		'profiles':      ('chk_profile_parse_arguments', 'chk_profile'),
		'configuration': ('chk_configuration_parse_arguments',
														'chk_configuration'),
		'volumes':       ('chk_volume_parse_arguments', 'chk_volume'),
		}, {
		"name"        : "licorn-check",
		"description" : "Licorn Check Entries",
		"author"      : 'Olivier Cortès <olive@deep-ocean.net>, '
						'Régis Cobrun <reg53fr@yahoo.fr>, '
						'Robin Lucbernet <robinlucbernet@gmail.com>'
		})

if __name__ == "__main__":
	chk_main()
