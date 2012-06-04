#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

get - display and export system information / lists.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""
import sys, os, Pyro.errors, time

from threading import Thread
from licorn.foundations.threads import RLock, Event

from licorn.foundations    import logging, options, pyutils
from licorn.interfaces.cli import LicornCliApplication, CliInteractor
from licorn.core           import version, LMC

def get_events(opts, args, listener):

	monitor_id = LMC.rwi.register_monitor(opts.facilities)

	try:
		CliInteractor(listener).run()

	finally:
		try:
			LMC.rwi.unregister_monitor(monitor_id)

		except Pyro.errors.ConnectionClosedError:
			# the connection has been closed by the server side.
			pass
def get_events_reconnect(opts, args, listener):
	LMC.rwi.register_monitor(opts.facilities)
def get_status(opts, args, listener):

	if opts.monitor:
		def get_status_thread(opts, args, opts_lock, stop_event, quit_func):

			with opts_lock:
				if opts.monitor_time:
					# TODO: hlstr.to_seconds(opts.monitor_time)
					monitor_time_stop = time.time() + opts.monitor_time

			count = 1
			stop_count = 0

			while not stop_event.is_set():
				with opts_lock:
					try:
						LMC.rwi.get_daemon_status(opts, args)

					except Pyro.errors.ConnectionClosedError:
						# wait a little before exiting, in case the daemon
						# reconnects automatically.
						if stop_count > 5:
							logging.warning(_(u'Daemon connection lost, bailing out.'))
							quit_func()

						stop_count += 1

					except:
						logging.exception(_(u'Could not get daemon status'))
						quit_func()

					interval = opts.monitor_interval

				if (opts.monitor_count
						and count >= opts.monitor_count
						) or (
						opts.monitor_time
						and time.time() >= monitor_time_stop):
					quit_func()

				time.sleep(interval)
				count += 1

		opts_lock      = RLock()
		cli_interactor = CliInteractor(listener, opts, opts_lock)
		stop_event     = cli_interactor._stop_event
		quit_func      = cli_interactor.quit_interactor
		output_thread  = Thread(target=get_status_thread,
								args=(opts, args, opts_lock, stop_event, quit_func))
		output_thread.start()

		try:
			try:
				cli_interactor.run()

			except KeyboardInterrupt:
				# This is needed to restore the terminal state.
				# Relying on the "finally" clause isn't sufficient.
				cli_interactor.quit_interactor()
				raise

		finally:
			if not stop_event.is_set():
				stop_event.set()

			output_thread.join()

	else:
		# we don't clear the screen for only one output.
		opts.clear_terminal = False
		try:
			LMC.rwi.get_daemon_status(opts, args)

		except:
			logging.exception(_(u'Could not obtain daemon status'))
def get_inside(opts, args, listener):

	import code

	class ProxyConsole(code.InteractiveConsole):
		"""(local) Proxy interactive console to remote interpreter. Taken from
			rfoo nearly verbatim and adapted to Pyro / Licorn needs. """

		def __init__(self):
			code.InteractiveConsole.__init__(self)
		def complete(self, phrase, state):
			"""Auto complete support for interactive console."""

			# Allow tab key to simply insert spaces when proper.
			if phrase == '':
				if state == 0:
					return '	'
				return None

			return LMC.rwi.console_complete(phrase, state)
		def runsource(self, source, filename=None, symbol="single"):

			if filename is None:
				filename = "<licorn_remote_console>"

			more, output = LMC.rwi.console_runsource(source, filename)

			if output:
				self.write(output)

			return more
		def write(self, data):
			sys.stdout.write(data)

	console      = ProxyConsole()
	history_file = os.path.expanduser('~/.licorn/interactor_history')

	if history_file:
		history_dir  = os.path.dirname(history_file)

		if not os.path.exists(history_dir):
			os.makedirs(history_dir)

	try:
		import readline
		readline.set_completer(console.complete)
		readline.parse_and_bind('tab: complete')
		try:
			readline.read_history_file(history_file)

		except IOError:
			pass

	except ImportError:
		history_file = None

	try:
		try:
			LMC.rwi.console_start()
			sys.ps1 = u'licornd> '

			console.interact(banner=_(u'Licorn® {0}, Python {1} '
							u'on {2}').format(version,
								sys.version.replace('\n', ''),
								sys.platform))
		except:
			logging.exception('Error running the remote console!')

	finally:
		# save the history file locally before stopping the console,
		# in case the console can't be stopped for any reason (mainly
		# network disconnect, but anything can happen).
		if history_file:
			try:
				readline.write_history_file(history_file)

			except:
				logging.exception(_(u'unable to write history file!'))

		try:
			LMC.rwi.console_stop()

		except Pyro.errors.ConnectionClosedError:
			pass

def get_main():

	LicornCliApplication({
		'users':         ('get_users_parse_arguments', 'get_users'),
		'passwd':        ('get_users_parse_arguments', 'get_users'),
		'groups':        ('get_groups_parse_arguments', 'get_groups'),
		'profiles':      ('get_profiles_parse_arguments', 'get_profiles'),
		'machines':      ('get_machines_parse_arguments', 'get_machines'),
		'clients':       ('get_machines_parse_arguments', 'get_machines'),
		'configuration': ('get_configuration_parse_arguments',
														'get_configuration'),
		'privileges':	 ('get_privileges_parse_arguments',	'get_privileges'),
		'tags':          ('get_keywords_parse_arguments', 'get_keywords'),
		'keywords':      ('get_keywords_parse_arguments', 'get_keywords'),
		'daemon_status': ('get_daemon_status_parse_arguments',
														None, get_status),
		'events'       : ('get_events_parse_arguments',
														None, get_events,
														get_events_reconnect),
		'inside'       : ('get_inside_parse_arguments',
														None, get_inside),
		'volumes':       ('get_volumes_parse_arguments', 'get_volumes'),
		}, {
		"name"     		: "licorn-get",
		"description"	: "Licorn Get Entries",
		"author"   		: 'Olivier Cortès <olive@deep-ocean.net>, '
							'Régis Cobrun <reg53fr@yahoo.fr>, '
							'Robin Lucbernet <robinlucbernet@gmail.com>'
		}, expected_min_args=2)

if __name__ == "__main__":
	get_main()
