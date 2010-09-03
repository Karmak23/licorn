#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn® daemon:
  - monitor shared group dirs and other special paths, and reapply posix
	perms and posix1e ACsL the Way They Should Be (TM) (as documented in posix1e
	manuals).
  - crawls against all shared group dirs, indexes metadata and provides a global
    search engine for all users.

This daemon exists:
  - to add user functionnality to Licorn® systems.
  - because of bugs in external apps (which don't respect posix1e semantics and
	can't or won't be fixed easily).

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>.
Licensed under the terms of the GNU GPL version 2.
"""

current_app = {
	"name"       : "licornd",
	"description": '''Licorn® Daemon: posix1e ACL auto checker, Web ''' \
		'''Management Interface server and file meta-data crawler''',
	"author"     : "Olivier Cortès <olive@deep-ocean.net>"
	}

import sys, os, signal
from Queue              import Queue

from licorn.foundations         import process, logging, exceptions
from licorn.foundations         import styles, options
from licorn.core.configuration  import LicornConfiguration
from licorn.core.users          import UsersController
from licorn.core.groups         import GroupsController
from licorn.core.keywords       import KeywordsController

configuration = LicornConfiguration()
users = UsersController(configuration)
groups = GroupsController(configuration, users)
keywords = KeywordsController(configuration)

# TODO: make our own argparser, for the daemon.
from licorn.interfaces.cli import argparser

from licorn.daemon.core                  import dname, terminate_cleanly, \
	exit_if_already_running, exit_if_not_running_root, eventually_daemonize, \
	setup_signals_handler
from licorn.daemon.internals.wmi         import fork_wmi
from licorn.daemon.internals.acl_checker import ACLChecker
from licorn.daemon.internals.inotifier   import INotifier
from licorn.daemon.internals.cache       import Cache
from licorn.daemon.internals.searcher    import FileSearchServer
#from licorn.daemon.internals.syncer       import ServerSyncer, ClientSyncer

if __name__ == "__main__":

	(opts, args) = argparser.licornd_parse_arguments(current_app)
	options.SetFrom(opts)

	exit_if_not_running_root()
	exit_if_already_running()

	# remember our children threads.
	threads = []

	pname = '%s/master' % dname
	process.set_name(pname)

	eventually_daemonize(opts)

	# do this after having daemonized, else it doesn't get in the log, but on
	# the console...
	logging.progress("%s: starting (pid %d)." % (pname, os.getpid()))

	if configuration.daemon.wmi.enabled:
		fork_wmi(opts)
	else:
		logging.progress('''%s: not starting WMI because disabled by '''
			'''configuration directive.''' % pname)

	# do this after having forked the WMI, else she gets the same setup and
	# tries to do things twice.
	setup_signals_handler(pname, threads)

	if configuration.daemon.role == "client":
		pass
		#syncer = ClientSyncer(dname)
		#threads.append(syncer)

		# TODO: get the cache from the server, it has the
		# one in sync with the NFS-served files.

	else:
		#syncer     = ServerSyncer(dname)
		#searcher   = FileSearchServer(dname)
		#cache      = Cache(keywords, dname)
		aclchecker = ACLChecker(None, dname)
		notifier   = INotifier(aclchecker, None, dname)
		#threads.append(cache)
		threads.append(aclchecker)
		threads.append(notifier)
		#threads.append(syncer)
		#threads.append(searcher)

	for th in threads:
		th.start()

	logging.progress("%s: going to sleep, waiting for signals." % pname)

	while True:
		signal.pause()

	terminate_cleanly(None, None, threads)
