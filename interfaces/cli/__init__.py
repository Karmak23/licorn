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

from threading import Thread, current_thread

from licorn.foundations           import options, exceptions, logging
from licorn.foundations           import pyutils, hlstr, ttyutils
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces   import *
from licorn.foundations.styles    import *
from licorn.foundations.constants import filters, verbose
from licorn.foundations.messaging import MessageProcessor

from licorn.core           import LMC
from licorn.interfaces.cli import argparser

#: Proxy to `daemon.cmdlistener.rwi` used in all CLI tools to transmit commands
#: to the Licorn® daemon.
RWI = None

#: the local listener, which receives output from the daemon.
_listener = None

#: various Pyro related variables.
pyroStarted = False
pyroExit = 0

class CliInteractor(ttyutils.LicornInteractor):
	def __init__(self, opts=None, opts_lock=None):
		super(CliInteractor, self).__init__('interactor')

		global RWI
		global _listener

		self.rwi      = RWI
		self.listener = _listener

		if opts is None:
			self.handled_chars = {
				'v'   : self.raise_verbose_level,
				'q'   : self.lower_verbose_level,
			}
		else:
			self.opts = opts
			self.lock = opts_lock

			self.handled_chars = {
				'f'   : self.toggle_long_output,
				'l'   : self.toggle_long_output,
				'q'   : self.quit_interactor,
			}
	def toggle_long_output(self):
		with self.lock:
			self.opts.long_output = not self.opts.long_output

		logging.notice(_(u'{0}: switched '
			u'long_output status to {1}.').format(
				self.name, _(u'enabled')
					if self.opts.long_output
					else _(u'disabled')))
	toggle_long_output.__doc__ = _(u'toggle [dump status] long ouput on or off')
	def raise_verbose_level(self):
		if options.verbose < verbose.DEBUG:
			options.verbose += 1

			# the local side (CLI process)
			self.listener.verbose += 1

			# the daemon side (remote Pyro thread)
			self.rwi.set_listener_verbose(
						self.listener.verbose)

			logging.notice(_(u'{0}: increased '
				u'verbosity level to '
				u'{1}.').format(self.name,
					stylize(ST_COMMENT,
						verbose[options.verbose])))

		else:
			logging.notice(_(u'{0}: verbosity '
				u'level already at the maximum '
				u'value ({1}).').format(
					self.name, stylize(ST_COMMENT,
						verbose[options.verbose])))
	raise_verbose_level.__doc__ = _(u'increase the daemon console verbosity level')
	def lower_verbose_level(self):
		if options.verbose > verbose.NOTICE:
			options.verbose -= 1

			# the local side (not really needed,
			# but keeping it in sync doesn't
			# hurt).
			self.listener.verbose -= 1

			# the daemon side (remote thread)
			self.rwi.set_listener_verbose(
						self.listener.verbose)

			logging.notice(_(u'{0}: decreased '
				u'verbosity level to '
				u'{1}.').format(self.name,
					stylize(ST_COMMENT,
						verbose[options.verbose])))

		else:
			logging.notice(_(u'{0}: verbosity '
				u'level already at the minimum '
				u'value ({1}).').format(
					self.name, stylize(ST_COMMENT,
						verbose[options.verbose])))
	lower_verbose_level.__doc__ = _(u'decrease the daemon console verbosity level')
	def quit_interactor(self):
		self._stop_event.set()
	quit_interactor.__doc__ = _(u'end the interactive session cleanly')
def PyroLoop(daemon):
	global pyroExit
	daemon.requestLoop(lambda: not pyroExit, 0.1)
def cli_main(functions, app_data, giant_locked=False, expected_min_args=3):
	""" common structure for all licorn cli tools. """

	global pyroStarted
	global pyroExit
	global RWI
	global _listener

	def cli_exec_function():
		if functions[mode][1] is None:
			functions[mode][2](RWI, opts, args)

		else:
			getattr(RWI, functions[mode][1])(opts=opts, args=args)


	assert ltrace(TRACE_CLI, '> cli_main(%s)' % sys.argv[0])

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

			assert ltrace(TRACE_CLI, '  cli_main: connecting to core.')
			RWI = LMC.connect()

			try:
				(opts, args) = getattr(argparser, functions[mode][0])(app=app_data)

			except IndexError, e:
				sys.argv.append("--help")
				argparser.general_parse_arguments(app_data)

			options.SetFrom(opts)

			# options._rwi is needed for the Interactor
			options._rwi = RWI

			assert ltrace(TRACE_CLI, '  cli_main: starting pyro!')
			pyroStarted = True
			pyro_start_time = time.time()

			# this is important for Pyro to be able to create temp files
			# in a self-writable directory, else it will lamentably fail
			# because default value for PYRO_STORAGE is '.', and the user
			# is not always positionned in a welcomed place.
			Pyro.config.PYRO_STORAGE=os.getenv('HOME', os.path.expanduser('~'))

			Pyro.core.initServer()
			Pyro.core.initClient()

			client_daemon = Pyro.core.Daemon()
			# opts._listener is needed for the Interactor
			_listener = MessageProcessor(verbose=opts.verbose)

			client_daemon.connect(_listener)

			# NOTE: an AttrProxy is needed, not a simple Proxy. Because the
			# daemon will check listener.verbose, which is not accessible
			# through a simple Pyro Proxy.
			RWI.set_listener(_listener.getAttrProxy())

			msgth = Thread(target=PyroLoop, args=(client_daemon,))
			msgth.start()

			assert ltrace(TRACE_TIMINGS, '@pyro_start_delay: %.4fs' % (
				time.time() - pyro_start_time))
			del pyro_start_time

			# not used yet, but kept for future use.
			#server=Pyro.core.getAttrProxyForURI(
			#	"PYROLOC://localhost:%s/msgproc" %
			#		configuration.licornd.pyro.port)

			if giant_locked:
				from licorn.foundations.classes import FileLock
				with FileLock(configuration, app_data['name'], 10):
					cli_exec_function()

			else :
				cmd_start_time = time.time()
				cli_exec_function()

			LMC.release()

			assert ltrace(TRACE_TIMINGS, '@cli_main_exec_time: %.4fs' % (
				time.time() - cmd_start_time))
			del cmd_start_time

	except exceptions.NeedHelpException, e:
		logging.warning(e)
		sys.argv.append("--help")
		getattr(argparser, functions[mode][0])(app=app_data)

	except KeyboardInterrupt, e:
		t = current_thread()
		if hasattr(t, 'restore_terminal'):
			t.restore_terminal()
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
		assert ltrace(TRACE_CLI, '  cli_main: stopping pyro.')
		if pyroStarted:
			pyroExit = 1
			msgth.join()

	assert ltrace(TRACE_TIMINGS, '@cli_main(): %.4fs' % (
		time.time() - cli_main_start_time))
	del cli_main_start_time

	assert ltrace(TRACE_CLI, '< cli_main(%s)' % sys.argv[0])
