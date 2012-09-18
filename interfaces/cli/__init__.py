# -*- coding: utf-8 -*-
"""
Licorn CLI basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Licensed under the terms of the GNU GPL version 2.

"""

import os, signal, sys, time, operator

from licorn.foundations           import settings, options, logging
from licorn.foundations           import ttyutils, hlstr
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.styles    import *
from licorn.foundations.constants import verbose

from licorn.core           import LMC
from licorn.interfaces     import LicornInterfaceBaseApplication
from licorn.interfaces.cli import argparser

class CliInteractor(ttyutils.LicornInteractor):
	def __init__(self, listener, opts=None, opts_lock=None):
		super(CliInteractor, self).__init__('interactor')

		self.listener = listener

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

			# The daemon side (remote Pyro connections)
			LMC.system.set_listener_verbose(
						self.listener.getAttrProxy(),
						self.listener.verbose)
			LMC.rwi.set_listener_verbose(
						self.listener.getAttrProxy(),
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
			LMC.system.set_listener_verbose(
						self.listener.getAttrProxy(),
						self.listener.verbose)
			LMC.rwi.set_listener_verbose(
						self.listener.getAttrProxy(),
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
		self.stop()
		# be sure to wake up the select.select() waiting on stdin...
		# see http://stackoverflow.com/questions/4660756/interrupting-select-to-add-another-socket-to-watch-in-python
		os.write(self.exit_pipe[1], 'quit')
	quit_interactor.__doc__ = _(u'end the interactive session cleanly')
class LicornCliApplication(ObjectSingleton, LicornInterfaceBaseApplication):
	def __init__(self, *args, **kwargs):
		LicornInterfaceBaseApplication.__init__(self)
		self.run(*args, **kwargs)
	def parse_arguments(self, functions, app_data, giant_locked=False, expected_min_args=3, *args, **kwargs): #CLI
		""" CLI specific """
		try:
			return getattr(argparser, functions[self.mode][0])(app=app_data)

		except IndexError, e:
			sys.argv.append("--help")
			argparser.general_parse_arguments(app_data)
	def main_pre_parse_arguments(self, functions, app_data, giant_locked=False, expected_min_args=3, *args, **kwargs):
		try:
			# we need to copy the keys because they will be modified by the
			# function.
			self.mode = hlstr.word_match(sys.argv[1].lower(), sorted(functions.keys()))

		except IndexError:
			self.mode = None

		if self.mode is None:

			if len(sys.argv) < expected_min_args:
				# auto-display usage when called with no arguments or just one.
				sys.argv.append("--help")

			if len(sys.argv) > 1 and sys.argv[1] not in (
												'-h', '--help', '--version'):
				logging.warning(_(u'Unknow mode %s!') % sys.argv[1])

			argparser.general_parse_arguments(app_data, sorted(functions.iterkeys()))
			sys.exit(1)

		# CLI tools need the RWI to be connected to parse arguments.
		self.connect()
	def main_body(self, functions, app_data, giant_locked=False, expected_min_args=3, *args, **kwargs): # CLI

		def cli_exec_function():
			if functions[self.mode][1] is None:

				try:
					self.resync_specific = functions[self.mode][3]

				except IndexError:
					pass

				functions[self.mode][2](self.opts, self.args, listener=self.local_listener)

			else:
				getattr(LMC.rwi, functions[self.mode][1])(opts=self.opts, args=self.args)

		cmd_start_time = time.time()

		if giant_locked:
			from licorn.foundations.classes import FileLock
			with FileLock(LMC.configuration, self.app_data['name'], 10):
				cli_exec_function()

		else :
			cli_exec_function()

		assert ltrace(TRACE_TIMINGS, '@cli_main_exec_time: %.4fs' % (
			time.time() - cmd_start_time))
