# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, sys, time, signal

from optparse import OptionParser, OptionGroup

from licorn.foundations         import logging, styles, process, exceptions
from licorn.foundations.argparser import build_version_string, \
	common_behaviour_group

from licorn.core import version

from licorn.core.configuration  import LicornConfiguration
#from licorn.core.users          import UsersController
#from licorn.core.groups         import GroupsController

configuration = LicornConfiguration()
#users = UsersController(configuration)
#groups = GroupsController(configuration, users)

### status codes ###
LCN_MSG_STATUS_OK      = 1
LCN_MSG_STATUS_PARTIAL = 2
LCN_MSG_STATUS_ERROR   = 254
LCN_MSG_STATUS_UNAVAIL = 255

LCN_MSG_CMD_QUERY       = 1
LCN_MSG_CMD_STATUS      = 2
LCN_MSG_CMD_REFRESH     = 3
LCN_MSG_CMD_UPDATE      = 4
LCN_MSG_CMD_END_SESSION = 254

### default paths ###
cache_path    = '/var/cache/licorn/licornd.db'
socket_path   = '/var/run/licornd.sock'
syncer_port   = 3344
searcher_port = 3355
wmi_port      = 3356
buffer_size   = 16*1024
wmi_group     = 'licorn-wmi'
log_path      = '/var/log/licornd.log'
pid_path      = '/var/run/licornd.pid'
wpid_path     = '/var/run/licornd-wmi.pid'
wlog_path     = '/var/log/licornd-wmi.log'
dname         = 'licornd'

def licornd_parse_arguments(app, configuration):
	""" Integrated help and options / arguments for harvestd."""

	usage_text = '''
	%s [-D|--no-daemon] ''' \
		'''[-W|--wmi-listen-address <IP_or_hostname|iface:…>] ''' \
		'''[-p|--pid-to-wake <PID>] ''' \
		'''[…]''' \
		% (styles.stylize(styles.ST_APPNAME, "%prog"))

	parser = OptionParser(
		usage=usage_text,
		version=build_version_string(app, version)
		)

	parser.add_option("-D", "--no-daemon",
		action="store_false", dest="daemon", default=True,
		help='''Don't fork as a daemon, stay on the current terminal instead.'''
			''' Logs will be printed on standard output '''
			'''instead of beiing written into the logfile.''')

	parser.add_option("-W", "--wmi-listen-address",
		action="store", dest="wmi_listen_address", default=None,
		help='''specify an IP address or a hostname to bind to. Only %s can '''
			'''be specified (the WMI cannot yet bind on multiple interfaces '''
			'''at the same time). This option takes precedence over the '''
			'''configuration directive, if present in %s.''' % (
			styles.stylize(styles.ST_IMPORTANT, 'ONE address or hostname'),
			styles.stylize(styles.ST_PATH, configuration.main_config_file)))

	parser.add_option("-p", "--pid-to-wake",
		action="store", type="int", dest="pid_to_wake", default=None,
		help='''specify a PID to be sent SIGUSR1 when daemon is ready. Used '''
			'''when CLI starts the daemon itself, else not used. ''')

	parser.add_option_group(common_behaviour_group(app, parser, 'licornd'))

	return parser.parse_args()
def terminate_cleanly(signum, frame, pname, threads = []):
	""" Close threads, wipe pid files, clean everything before closing. """

	if signum is None:
		logging.progress("%s: cleaning up and stopping threads…" % \
			pname)
	else:
		logging.notice('%s: signal %s received, shutting down…' % (
			pname, signum))

	for th in reversed(threads):
		# stop threads in the reverse order they were started.
		th.stop()

	for pid_file in (pid_path, wpid_path):
		try:
			if os.path.exists(pid_file):
				os.unlink(pid_file)
		except (OSError, IOError), e:
			logging.warning("Can't remove %s (was: %s)." % (
				styles.stylize(styles.ST_PATH, pid_file), e))

	if threads != []:
		logging.progress("%s: joining threads." % pname)

	for th in reversed(threads):
		# join threads in the reverse order they were started.
		th.join()

	configuration.CleanUp()

	logging.progress("%s: exiting." % pname)

	# be sure there aren't any exceptions left anywhere…
	time.sleep(0.5)

	sys.exit(0)
def setup_signals_handler(pname, threads=[]):
	""" redirect termination signals to a the function which will clean everything. """

	def terminate(signum, frame):
		return terminate_cleanly(signum, frame, pname, threads)

	signal.signal(signal.SIGINT, terminate)
	signal.signal(signal.SIGTERM, terminate)
	signal.signal(signal.SIGHUP, terminate)

	if pname == 'licornd/wmi':
		# wmi will receive this signal from master when all threads are started,
		# this will wake it from its signal.pause().
		signal.signal(signal.SIGUSR1, lambda x,y: True)

	#signal.signal(signal.SIGCHLD, signal.SIG_IGN)
def exit_if_already_running():
	if process.already_running(pid_path):
		logging.notice("%s: already running (pid %s), not restarting." % (
			dname, process.get_pid(pid_path)))
		sys.exit(0)
def refork_if_not_running_root_or_die():
	if os.getuid() != 0 or os.geteuid() != 0:
		try:
			process.refork_as_root_or_die(process_title='licorn-daemon')
		except exceptions.LicornRuntimeException, e:
			logging.error("%s: must be run as %s (was: %s)." % (dname,
				styles.stylize(styles.ST_NAME, 'root'), e))
def eventually_daemonize(opts):
	if opts.daemon:
		process.daemonize(log_path, pid_path)
	else:
		process.write_pid_file(pid_path)

