# -*- coding: utf-8 -*-
"""
Licorn CLI basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Licensed under the terms of the GNU GPL version 2.

"""

import os, signal, sys, time, Pyro.core
from threading import Thread

from licorn.foundations           import options, exceptions, logging
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.styles    import *
from licorn.foundations.constants import filters
from licorn.foundations.objects   import MessageProcessor

pyroStarted=False
pyroExit=0

def PyroLoop(daemon):
	global pyroExit
	daemon.requestLoop(lambda: not pyroExit, 0.1)
def cli_main(functions, app_data, giant_locked=False, expected_min_args=3):
	""" common structure for all licorn cli tools. """

	global pyroStarted
	global pyroExit

	assert ltrace('cli', '> cli_main(%s)' % sys.argv[0])

	cli_main_start_time = time.time()

	# This 'utf-8' thing is needed for a bunch of reasons in our code. We do
	# unicode stuff internally and need utf-8 to deal with real world problems.
	# Ascii comes from another age…
	# We need to set this here, because before it was done ONCE by the
	# configuration object, but with the pyro changes, configuration is now only
	# initialized on the daemon side, and CLI doesn't benefit of it.
	if sys.getdefaultencoding() == "ascii":
		reload(sys)
		sys.setdefaultencoding("utf-8")

	try:
		# this is the first thing to do, else all help and usage will get colors
		# even if no_colors is True, because it is parsed too late.
		if "--no-colors" in sys.argv:
			options.SetNoColors(True)

		import argparser, Pyro.util

		mode = sys.argv[1]

		if mode in functions.keys():

			if len(sys.argv) < expected_min_args:
				# auto-display usage when called with no arguments or just one.
				sys.argv.append("--help")

			assert ltrace('cli', '  cli_main: connecting to core')
			import licorn.core
			configuration, users, groups, profiles, privileges, keywords, \
				machines = licorn.core.connect()

			(opts, args) = functions[mode][0](app=app_data,
				configuration=configuration)
			options.SetFrom(opts)

			assert ltrace('cli', '  cli_main: starting pyro')
			pyroStarted=True
			pyro_start_time = time.time()
			Pyro.core.initServer()
			Pyro.core.initClient()

			client_daemon = Pyro.core.Daemon()
			listener = MessageProcessor(verbose=opts.verbose)
			client_daemon.connect(listener)
			opts.listener = listener.getAttrProxy()

			msgth=Thread(target=PyroLoop, args=(client_daemon,))
			msgth.start()

			assert ltrace('timings', '@pyro_start_delay: %.4fs' % (
				time.time() - pyro_start_time))
			del pyro_start_time

			# not used yet, but kept for future use.
			#server=Pyro.core.getAttrProxyForURI("PYROLOC://localhost:7766/msgproc")

			if giant_locked:
				from licorn.foundations.objects import FileLock
				with FileLock(configuration, app_data['name'], 10):
					functions[mode][1](opts=opts, args=args,
					configuration=configuration, users=users, groups=groups,
					profiles=profiles, privileges=privileges, keywords=keywords,
					machines=machines)
			else :
				cmd_start_time = time.time()
				functions[mode][1](opts=opts, args=args,
					configuration=configuration, users=users, groups=groups,
					profiles=profiles, privileges=privileges, keywords=keywords,
					machines=machines)

			assert ltrace('timings', '@cli_main_exec_time: %.4fs' % (
				time.time() - cmd_start_time))
			del cmd_start_time
		else:
			if mode not in ('-h', '--help', '--version'):
				logging.warning(logging.GENERAL_UNKNOWN_MODE % mode)
			argparser.general_parse_arguments(app_data)

	except IndexError, e:
		sys.argv.append("--help")
		argparser.general_parse_arguments(app_data)

	except KeyboardInterrupt, e:
		logging.warning(logging.GENERAL_INTERRUPTED)

	except exceptions.NeedRestartException, e:
		logging.notice('daemon needs a restart, sending USR1.')
		os.kill(e.pid, signal.SIGUSR1)

	except exceptions.LicornError, e:
		logging.error('%s (%s, errno=%s).' % (
			str(e), stylize(ST_SPECIAL, str(e.__class__).replace(
			"<class '",'').replace("'>", '')), e.errno), e.errno,
			full=True if options.verbose > 2 else False,
			tb=''.join(Pyro.util.getPyroTraceback(e)))

	except exceptions.LicornException, e:
		logging.error('%s: %s (errno=%s).' % (
			stylize(ST_SPECIAL, str(e.__class__).replace(
			"<class '",'').replace("'>", '')),
			str(e), e.errno), e.errno, full=True,
			tb=''.join(Pyro.util.getPyroTraceback(e)))

	except Exception, e:
		logging.error('%s: %s.' % (
			stylize(ST_SPECIAL, str(e.__class__).replace(
			"<class '",'').replace("<type '",'').replace("'>", '')),
			str(e)), 254, full=True, tb=''.join(Pyro.util.getPyroTraceback(e)))

	finally:
		assert ltrace('cli', '  cli_main: stopping pyro.')
		if pyroStarted:
			pyroExit=1
			msgth.join()

	assert ltrace('timings', '@cli_main(): %.4fs' % (
		time.time() - cli_main_start_time))
	del cli_main_start_time

	assert ltrace('cli', '< cli_main(%s)' % sys.argv[0])
def cli_select(controller, ctype, args, include_id_lists, exclude_id_lists=[],
	default_selection=filters.NONE, all=False):

	assert ltrace('cli', '''> cli_select(controller=%s, ctype=%s, args=%s, '''
		'''include_id_lists=%s, exclude_id_lists=%s, default_selection=%s, '''
		'''all=%s)''' % (controller, ctype, args, include_id_lists,
			exclude_id_lists, default_selection, all))
	# use a set() to avoid duplicates during selections. This will allow us,
	# later in implementation to do more complex selections (unions,
	# differences, intersections and al.
	xids = set()
	if all:
		# if --all: manually included IDs (with --login, --group, --uid, --gid)
		# will be totally discarded (--all gets precedence). But excluded items
		# will still be excluded, to allow "--all --exclude-login toto"
		# semi-complex selections.
		ids = set(controller.keys())
	else:
		ids = set()

		something_tried = False

		if len(args) > 1:
			for arg in args[1:]:
				#assert ('cli', '  cli_select(add_arg=%s)' % arg)
				include_id_lists.append((arg, controller.guess_identifier))

		# select included IDs
		for id_arg, resolver in include_id_lists:
			if id_arg is None:
				continue
			for id in id_arg.split(',') if hasattr(id_arg, 'split') else id_arg:
				if id is '':
					continue

				try:
					something_tried = True
					ids.add(resolver(id))
					assert ltrace('cli', '  cli_select %s(%s) -> %s' %
						(resolver._RemoteMethod__name, id, resolver(id)))
				except (KeyError, exceptions.DoesntExistsException):
					logging.notice('''Skipped non existing or invalid %s or '''
						'''%sID '%s'.''' % (ctype, ctype[0].upper(),
						stylize(ST_NAME, id)))
					continue

	# select excluded IDs, to remove them from included ones
	for id_arg, resolver in exclude_id_lists:
		if id_arg is None:
			continue
		for id in id_arg.split(',') if hasattr(id_arg, 'split') else id_arg:
			if id is '':
				continue
			try:
				xids.add(resolver(id))
			except (KeyError, exceptions.DoesntExistsException):
				logging.notice('''Skipped non existing or invalid %s or '''
					'''%sID '%s'.''' % (ctype, ctype[0].upper(),
					stylize(ST_NAME, id)))
				continue

	# now return included IDs, minux excluded IDs, in different conditions.
	if ids != set():
		selection = list(ids.difference(xids))
	else:
		if something_tried:
			selection = []
		else:
			if default_selection is filters.NONE:
				logging.warning('You must specify at least one %s!' % ctype)
				selection = []
			else:
				selection = list(set(
					controller.Select(default_selection)).difference(xids))

	assert ltrace('cli', '< cli_select(return=%s)' % selection)
	return selection
