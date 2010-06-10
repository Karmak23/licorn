# -*- coding: utf-8 -*-
"""
Licorn CLI basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Licensed under the terms of the GNU GPL version 2.

"""

def __cli_main(functions, app_data):
	""" cli_main() internals. """

	import sys
	from licorn.foundations import options, exceptions, logging

	try:
		if "--no-colors" in sys.argv:
			options.SetNoColors(True)

		import argparser

		if len(sys.argv) < 2:
			# auto-display usage when called with no arguments or just one.
			sys.argv.append("--help")
			argparser.general_parse_arguments(app_data)

		mode = sys.argv[1]

		if mode in functions.keys():
			(opts, args) = functions[mode][0](app_data)
			options.SetFrom(opts)
			from licorn.core import configuration, users, groups, profiles, \
				keywords
			functions[mode][1](opts, args)
		else:
			if mode != '--version':
				logging.warning(logging.GENERAL_UNKNOWN_MODE % mode)
			sys.argv.append("--help")
			argparser.general_parse_arguments(app_data)

	except exceptions.LicornException, e:
		logging.error (str(e), e.errno)

	except KeyboardInterrupt:
		logging.warning(logging.GENERAL_INTERRUPTED)

def cli_main(functions, app_data, second_level_help = False,
				giant_locked = False):
	""" common structure for all licorn cli tools.
		Set second_level_help if commands have a more precise help messages
		(this is mostly the case for all licorn commands).
	"""

	from licorn.core import configuration
	from licorn.foundations.file_locks import FileLock

	with configuration:
		if giant_locked:
			with FileLock(configuration, 'giant', 10):
				__cli_main(functions, app_data)
		else :
			__cli_main(functions, app_data)

