# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os
import sys
import time
import signal

from threading   import Thread, Event, Semaphore
from collections import deque

from licorn.foundations         import fsapi
from licorn.foundations         import logging
from licorn.foundations         import exceptions
from licorn.foundations         import styles
from licorn.foundations         import process
from licorn.foundations.objects import LicornThread
from licorn.foundations.objects import Singleton
from licorn.core.configuration  import LicornConfiguration
from licorn.core.users          import UsersController
from licorn.core.groups         import GroupsController

configuration = LicornConfiguration()
users = UsersController(configuration)
groups = GroupsController(configuration, users)

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

def terminate_cleanly(signum, frame, pname, threads = []):
	""" Close threads, wipe pid files, clean everything before closing. """

	if signum is None:
		logging.progress("%s: cleaning up and stopping threads…" % \
			pname)
	else:
		logging.notice('%s: signal %s received, shutting down…' % (
			pname, signum))

	for th in threads:
		th.stop()

	configuration.CleanUp()

	for pid_file in (pid_path, wpid_path):
		try:
			if os.path.exists(pid_file):
				os.unlink(pid_file)
		except (OSError, IOError), e:
			logging.warning("Can't remove %s (was: %s)." % (
				styles.stylize(styles.ST_PATH, pid_file), e))

	if threads != []:
		logging.progress("%s: joining threads." % pname)

	for th in threads:
		th.join()

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
def exit_if_already_running():
	if process.already_running(pid_path):
		logging.notice("%s: already running (pid %s), not restarting." % (
			dname, process.get_pid(pid_path)))
		sys.exit(0)
def exit_if_not_running_root():
	if os.getuid() != 0 or os.geteuid() != 0:
		logging.error("%s: must be run as %s." % (dname,
			styles.stylize(styles.ST_NAME, 'root')))
def eventually_daemonize(opts):
	if opts.daemon:
		process.daemonize(log_path, pid_path)
	else:
		process.write_pid_file(pid_path)

