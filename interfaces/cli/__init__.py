# -*- coding: utf-8 -*-
"""
Licorn CLI basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Licensed under the terms of the GNU GPL version 2.

"""

def cli_main(functions, app_data, giant_locked=False, expected_min_args=3):
	""" common structure for all licorn cli tools. """

	import sys
	from licorn.foundations import options, exceptions, logging
	from licorn.foundations.ltrace import ltrace

	ltrace('cli', '> cli_main(%s).' % sys.argv[0])

	try:
		if "--no-colors" in sys.argv:
			options.SetNoColors(True)

		import argparser

		mode = sys.argv[1]

		if mode in functions.keys():

			if len(sys.argv) < expected_min_args:
				# auto-display usage when called with no arguments or just one.
				sys.argv.append("--help")

			(opts, args) = functions[mode][0](app_data)

			options.SetFrom(opts)

			from licorn.core.configuration import LicornConfiguration
			configuration = LicornConfiguration()

			with configuration:
				if giant_locked:
					from licorn.foundations.objects import FileLock
					with FileLock(configuration, app_data['name'], 10):
						functions[mode][1](opts, args)
				else :
					functions[mode][1](opts, args)
		else:
			if mode not in ('-h', '--help', '--version'):
				logging.warning(logging.GENERAL_UNKNOWN_MODE % mode)
			argparser.general_parse_arguments(app_data)

	except IndexError, e:
		sys.argv.append("--help")
		argparser.general_parse_arguments(app_data)

	except exceptions.LicornException, e:
		logging.error (str(e), e.errno)

	except KeyboardInterrupt:
		logging.warning(logging.GENERAL_INTERRUPTED)

	ltrace('cli', '< cli_main(%s).' % sys.argv[0])

