# -*- coding: utf-8 -*-
"""
Licorn CLI basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Licensed under the terms of the GNU GPL version 2.

"""

from licorn.foundations           import exceptions, logging
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.styles    import *
from licorn.foundations.constants import filters

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

	except KeyboardInterrupt, e:
		logging.warning(logging.GENERAL_INTERRUPTED)

	except exceptions.LicornError, e:
		logging.error('%s (%s, errno=%s).' % (
			str(e), stylize(ST_SPECIAL, str(e.__class__).replace(
			"<class '",'').replace("'>", '')), e.errno), e.errno)

	except exceptions.LicornException, e:
		logging.error('%s: %s (errno=%s).' % (
			stylize(ST_SPECIAL, str(e.__class__).replace(
			"<class '",'').replace("'>", '')),
			str(e), e.errno), e.errno,
			full=True)

	except Exception, e:
		logging.error('%s: %s.' % (stylize(ST_SPECIAL, str(e.__class__).replace(
			"<class '",'').replace("<type '",'').replace("'>", '')),
			str(e)), 254, full=True)

	ltrace('cli', '< cli_main(%s).' % sys.argv[0])
def cli_select(controller, ctype, args, id_lists, default_selection, all=False):

	ltrace('cli', '> cli_select()')

	if all:
		ltrace('cli', '< cli_select(all)')
		return controller.keys()
	else:
		# use a set() to avoid duplicates
		ids = set()
		something_tried = False

		if len(args) > 1:
			for arg in args[1:]:
				#ltrace('cli', '  cli_select(add_arg=%s)' % arg)
				id_lists.append((arg, controller.guess_identifier))

		for id_arg, resolver in id_lists:
			if id_arg is None:
				continue
			for id in id_arg.split(','):
				if id is '':
					continue

				try:
					something_tried = True
					ids.add(resolver(id))
				except (KeyError, exceptions.DoesntExistsException):
					logging.notice('''Skipped non existing %s or ID '%s'.''' % (
						ctype, stylize(ST_NAME, id)))
					continue

		if ids != set():
			selection = list(ids)
		else:
			if something_tried:
				selection = []
			else:
				if default_selection is filters.NONE:
					logging.warning('You must specify at least one %s!' % ctype)
					selection = []
				else:
					selection = controller.Select(default_selection)

		ltrace('cli', '< cli_select(return=%s)' % selection)
		return selection

