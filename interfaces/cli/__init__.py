# -*- coding: utf-8 -*-
"""
Licorn CLI basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Licensed under the terms of the GNU GPL version 2.

"""

import gettext
gettext.install('licorn', unicode=True)

import os, signal, sys, time, operator
import Pyro.core, Pyro.util, Pyro.configuration

from threading import Thread

from licorn.foundations           import options, exceptions, logging
from licorn.foundations           import pyutils, hlstr
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.styles    import *
from licorn.foundations.constants import filters
from licorn.foundations.messaging import MessageProcessor

from licorn.core           import LMC
from licorn.interfaces.cli import argparser

#: Proxy to `daemon.cmdlistener.rwi` used in all CLI tools to transmit commands
#: to the Licorn® daemon.
RWI=None

pyroStarted=False
pyroExit=0

def PyroLoop(daemon):
	global pyroExit
	daemon.requestLoop(lambda: not pyroExit, 0.1)
def cli_main(functions, app_data, giant_locked=False, expected_min_args=3):
	""" common structure for all licorn cli tools. """

	global pyroStarted
	global pyroExit
	global RWI

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

		try:
			# we need to copy the keys because they will be modified by the
			# function.
			mode = hlstr.word_match(sys.argv[1].lower(), sorted(functions.keys()))

		except IndexError:
			mode = None

		if mode is None:

			if len(sys.argv) < expected_min_args:
				# auto-display usage when called with no arguments or just one.
				sys.argv.append("--help")

			if len(sys.argv) > 1 and sys.argv[1] not in (
												'-h', '--help', '--version'):
				logging.warning(_(u'Unknow mode %s!') % sys.argv[1])

			argparser.general_parse_arguments(app_data, sorted(functions.iterkeys()))

		else:

			assert ltrace('cli', '  cli_main: connecting to core')
			RWI = LMC.connect()

			try:
				(opts, args) = getattr(argparser, functions[mode][0])(app=app_data)

			except IndexError, e:
				sys.argv.append("--help")
				argparser.general_parse_arguments(app_data)

			options.SetFrom(opts)

			assert ltrace('cli', '  cli_main: starting pyro')
			pyroStarted=True
			pyro_start_time = time.time()

			# this is important for Pyro to be able to create temp files
			# in a self-writable directory, else it will lamentably fail
			# because default value for PYRO_STORAGE is '.', and the user
			# is not always positionned in a welcomed place.
			Pyro.config.PYRO_STORAGE=os.getenv('HOME', os.path.expanduser('~'))

			Pyro.core.initServer()
			Pyro.core.initClient()

			client_daemon = Pyro.core.Daemon()
			listener      = MessageProcessor(verbose=opts.verbose)
			client_daemon.connect(listener)

			# NOTE: an AttrProxy is needed, not a simple Proxy. Because the
			# daemon will check listener.verbose, which is not accessible
			# through a simple Pyro Proxy.
			RWI.set_listener(listener.getAttrProxy())

			msgth = Thread(target=PyroLoop, args=(client_daemon,))
			msgth.start()

			assert ltrace('timings', '@pyro_start_delay: %.4fs' % (
				time.time() - pyro_start_time))
			del pyro_start_time

			# not used yet, but kept for future use.
			#server=Pyro.core.getAttrProxyForURI(
			#	"PYROLOC://localhost:%s/msgproc" %
			#		configuration.licornd.pyro.port)

			if giant_locked:
				from licorn.foundations.classes import FileLock
				with FileLock(configuration, app_data['name'], 10):
					getattr(RWI, functions[mode][1])(opts=opts, args=args)

			else :
				cmd_start_time = time.time()
				getattr(RWI, functions[mode][1])(opts=opts, args=args)

			LMC.release()

			assert ltrace('timings', '@cli_main_exec_time: %.4fs' % (
				time.time() - cmd_start_time))
			del cmd_start_time

	except exceptions.NeedHelpException, e:
		logging.warning(e)
		sys.argv.append("--help")
		getattr(argparser, functions[mode][0])(app=app_data)

	except KeyboardInterrupt, e:
		logging.warning(_(u'Interrupted, cleaning up!'))

	except exceptions.NeedRestartException, e:
		logging.notice(_(u'daemon needs a restart, sending USR1 signal.'))
		os.kill(e.pid, signal.SIGUSR1)

	except exceptions.LicornError, e:
		logging.error('%s (%s, errno=%s).' % (
			str(e), stylize(ST_SPECIAL, str(e.__class__).replace(
			"<class '",'').replace("'>", '')), e.errno), e.errno,
			full=True if options.verbose > 2 else False,
			tb=''.join(Pyro.util.getPyroTraceback(e)
				if options.verbose > 2 else ''))

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
