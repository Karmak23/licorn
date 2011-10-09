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

from threading import Thread, RLock, Event

from licorn.foundations    import logging, options, pyutils
from licorn.interfaces.cli import cli_main, CliInteractor
from licorn.core           import version, LMC

def get_events(opts, args):
	system = LMC.system

	monitor_id = system.register_monitor(opts.facilities)

	try:
		CliInteractor().run()

	finally:
		try:
			system.unregister_monitor(monitor_id)

		except Pyro.errors.ConnectionClosedError:
			# the connection has been closed by the server side.
			pass
def get_status(opts, args):

	system = LMC.system

	if opts.monitor:
		def get_status_thread(opts, args, opts_lock, stop_event):

			with opts_lock:
				if opts.monitor_time:
					# TODO: hlstr.to_seconds(opts.monitor_time)
					monitor_time_stop = time.time() + opts.monitor_time

			count = 1

			while not stop_event.is_set():
				with opts_lock:
					try:
						system.get_daemon_status(opts, args)

					except Exception, e:
						logging.warning(e)
						pyutils.print_exception_if_verbose()
						stop_event.set()

					interval = opts.monitor_interval

					if (
							opts.monitor_count
							and count >= opts.monitor_count
							) or (
							opts.monitor_time
							and time.time() >= monitor_time_stop):
						raise SystemExit(0)

				time.sleep(interval)
				count += 1

		opts_lock  = RLock()
		stop_event = Event()

		output_thread = Thread(target=get_status_thread,
								args=(opts, args, opts_lock, stop_event))
		output_thread.start()

		try:
			CliInteractor(opts, opts_lock).run()

		finally:
			stop_event.set()
			output_thread.join()

	else:
		# we don't clear the screen for only one output.
		opts.clear_terminal = False
		try:
			system.get_daemon_status(opts, args)

		except Exception, e:
			logging.warning(e)
			pyutils.print_exception_if_verbose()
			stop_event.set()
def get_inside(opts, args):

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

			return LMC.system.console_complete(phrase, state)
		def runsource(self, source, filename=None, symbol="single"):

			if filename is None:
				filename = "<licorn_remote_console>"

			more, output = LMC.system.console_runsource(source, filename)

			if output:
				self.write(output)

			return more
		def write(self, data):
			#if output[0] == 'u' and output[-1] in ('"', '"'):
			#	output = eval(output)
			sys.stdout.write(data)

	console      = ProxyConsole()
	history_file = os.path.expanduser('~/.licorn/interactor_history')

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
		LMC.system.console_start()
		sys.ps1 = u'licornd> '

		console.interact(banner=_(u'Licorn® {0}, Python {1} '
						u'on {2}').format(version,
							sys.version.replace('\n', ''),
							sys.platform))

	finally:
		LMC.system.console_stop()
		if history_file:
			readline.write_history_file(history_file)

def get_main():

	cli_main({
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
														None, get_events),
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
