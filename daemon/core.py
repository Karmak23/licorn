# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, sys, time, signal, select, curses, termios, resource

from optparse import OptionParser, OptionGroup

from licorn.foundations           import options, logging, styles, process, \
	exceptions
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.pyutils   import format_time_delta
from licorn.foundations.base      import Enumeration
from licorn.foundations.thread    import _threads, _thcount
from licorn.foundations.argparser import build_version_string, \
											common_behaviour_group

from licorn.core           import version, LMC
from licorn.daemon         import dname, dthreads, dqueues, dchildren, dstart_time
from licorn.daemon.threads import LicornBasicThread, LicornPoolJobThread

def get_daemon_status(long_output=False, precision=None):
	""" GET daemon status (all threads). """

	system = LMC.system

	assert ltrace('daemon', '| get_daemon_status(%s, %s)' % (
		long_output, precision))

	# if not is_localhost(client) and not is_server_peer(client):
	# logging.warning('unauthorized call from %s!' % client)
	#	return

	rusage = resource.getrusage(resource.RUSAGE_SELF)
	pagesize = resource.getpagesize()

	data = ('-- Licorn® daemon %sstatus: '
		'up %s, %s threads, %s controllers, %s queues, %s locks\n'
		'CPU: usr %.3fs, sys %.3fs MEM: res %.2fMb shr %.2fMb ush %.2fMb stk %.2fMb\n' % (
		stylize(ST_COMMENT, 'full ') if long_output else '',
		stylize(ST_COMMENT, format_time_delta(time.time()-dstart_time)),
		_thcount(), stylize(ST_UGID, len(LMC)),
		stylize(ST_UGID, len(dqueues)), stylize(ST_UGID, len(LMC.locks)),
		rusage.ru_utime, #format_time_delta(int(rusage.ru_utime), long=False),
		rusage.ru_stime, #format_time_delta(int(rusage.ru_stime), long=False),
		float(rusage.ru_maxrss * pagesize) / (1024.0*1024.0),
		float(rusage.ru_ixrss * pagesize) / (1024.0*1024.0),
		float(rusage.ru_idrss * pagesize) / (1024.0*1024.0),
		float(rusage.ru_isrss * pagesize) / (1024.0*1024.0)
		))

	data += ('Queues: %s.\n' %
			', '.join([ '%s(%s)' % (stylize(ST_NAME, qname),
				queue.qsize()) for qname, queue in dqueues.iteritems()]))

	if long_output:
		for controller in LMC:
			if hasattr(controller, 'dump_status'):
				data += 'controller %s\n' % controller.dump_status()
			else:
				data += ('''controller %s%s doesn't implement '''
					'''dump_status().\n''' % (
					stylize(ST_NAME, controller.name),
					'(%s)' % stylize(ST_IMPORTANT, 'locked')
						if controller.is_locked() else ''))

	for thread in dthreads.values():
		if thread.is_alive():
			if long_output or ( not long_output
				and not isinstance(thread, LicornPoolJobThread)):
				if hasattr(thread, 'dump_status'):
					data += 'thread %s\n' % thread.dump_status(long_output,
						precision)
				else:
					data += ('''thread %s%s(%s) doesn't implement '''
						'''dump_status().\n''' % (
							stylize(ST_NAME, thread.name),
							stylize(ST_OK, '&') if thread.daemon else '',
							thread.ident))
		else:
			data += 'thread %s%s(%d) has terminated.\n' % (
				stylize(ST_NAME, thread.name),
				stylize(ST_OK, '&') if thread.daemon else '',
				thread.ident)
	return data
def licornd_parse_arguments(app):
	""" Integrated help and options / arguments for harvestd."""

	usage_text = '''
	%s [-D|--no-daemon] ''' \
		'''[-W|--wmi-listen-address <IP_or_hostname|iface:…>] ''' \
		'''[-p|--pid-to-wake <PID>] ''' \
		'''[…]''' \
		% (stylize(ST_APPNAME, "%prog"))

	parser = OptionParser(
		usage=usage_text,
		version=build_version_string(app, version)
		)

	parser.add_option("-D", "--no-daemon",
		action="store_false", dest="daemon", default=True,
		help='''Don't fork as a daemon, stay on the current terminal instead.'''
			''' Logs will be printed on standard output '''
			'''instead of beiing written into the logfile.''')

	parser.add_option("-W", "--no-wmi",
		action="store_false", dest="wmi_enabled", default=True,
		help='''Don't fork the WMI. This flag overrides the setting in %s.''' %
			stylize(ST_PATH, LMC.configuration.main_config_file))

	parser.add_option("-w", "--wmi-listen-address",
		action="store", dest="wmi_listen_address", default=None,
		help='''Specify an IP address or a hostname to bind to. Only %s can '''
			'''be specified (the WMI cannot yet bind on multiple interfaces '''
			'''at the same time). This option takes precedence over the '''
			'''configuration directive, if present in %s.''' % (
			stylize(ST_IMPORTANT, 'ONE address or hostname'),
			stylize(ST_PATH, LMC.configuration.main_config_file)))

	parser.add_option("-p", "--pid-to-wake",
		action="store", type="int", dest="pid_to_wake", default=None,
		help='''Specify a PID to send SIGUSR1 to, when daemon is ready. Used '''
			'''internaly only when CLI tools start the daemon themselves.''')

	parser.add_option("-B", "--no-boot-check",
		action="store_true", dest="no_boot_check", default=False,
		help='''Don't run the initial check on all shared directories. This '''
			'''makes daemon be ready faster to answer users legitimate '''
			'''requests, at the cost of consistency of shared data. %s: don't'''
			''' use this flag at server boot in init scripts. Only on daemon '''
			'''relaunch, on an already running system, for testing or '''
			'''debugging purposes.''' % stylize(ST_IMPORTANT,
			'EXTREME CAUTION'))

	parser.add_option_group(common_behaviour_group(app, parser, 'licornd'))

	return parser.parse_args()
def exit_if_already_running():
	if process.already_running(LMC.configuration.licornd.pid_file):
		logging.notice("%s: already running (pid %s), not restarting." % (
			dname, process.get_pid(LMC.configuration.licornd.pid_file)))
		sys.exit(0)
def refork_if_not_running_root_or_die():
	if os.getuid() != 0 or os.geteuid() != 0:
		try:
			process.refork_as_root_or_die(process_title='licorn-daemon')
		except exceptions.LicornRuntimeException, e:
			logging.error("%s: must be run as %s (was: %s)." % (dname,
				stylize(ST_NAME, 'root'), e))
def eventually_daemonize():
	if options.daemon:
		process.daemonize(LMC.configuration.licornd.log_file,
			LMC.configuration.licornd.pid_file)
	else:
		process.write_pid_file(LMC.configuration.licornd.pid_file)
