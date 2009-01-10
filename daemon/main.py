#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn daemon :
  - monitor shared group dirs and other special paths, and reapply posix
	perms or posix ACL the Right Way They Should Be (TM).

This daemon exists :
  - to add user functionnality to Licorn systems.
  - because of bugs in other apps.
  
Built on top of Licorn System Library, part of Licorn System Tools (H-S-T).

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>.
Licensed under the terms of the GNU GPL version 2.
"""

current_app = {
	"name"        : "licorn-daemon",
	"description" : "Licorn Daemon: ACL auto check and file meta-data crawler",
	"author"      : "Olivier Cortès <olive@deep-ocean.net>"
	}

import sys, os, signal

# argparser ?
from licorn.foundations import process, logging, exceptions, styles, options
from licorn.core        import keywords, configuration

# TODO: make our own argparser, for the daemon.
from licorn.interfaces.cli import argparser

from licorn.daemon.core               import ACLChecker, INotifier, dname, terminate_cleanly
from licorn.daemon.core               import exit_if_already_running, exit_if_not_running_root
from licorn.daemon.core               import eventually_daemonize, setup_signals_handler
from licorn.daemon.internals.wmi      import eventually_fork_wmi_server
from licorn.daemon.internals.cache    import Cache
from licorn.daemon.internals.searcher import FileSearchServer
from licorn.daemon.internals.syncer   import ServerSyncer, ClientSyncer

if __name__ == "__main__" :

	(opts, args) = argparser.licornd_parse_arguments(current_app)
	options.SetFrom(opts)

	exit_if_not_running_root()
	exit_if_already_running()

	# remember our children threads.
	threads = []

	process.set_name('%s/master' % dname)
	logging.progress("%s/master: starting (pid %d)." % (dname, os.getpid()))

	setup_signals_handler(threads)
	eventually_daemonize(opts)
	eventually_fork_wmi_server()

	if configuration.daemon.role == "client" :
		syncer = ClientSyncer(dname)
		threads.append(syncer)

		# TODO: get the cache from the server, it has the
		# one in sync with the NFS-served files.

	else :
		syncer     = ServerSyncer(dname)
		searcher   = FileSearchServer(dname)
		aclchecker = ACLChecker(cache, dname)
		notifier   = INotifier(aclchecker, cache, dname)
		cache      = Cache(keywords, dname)
		threads.append(aclchecker)
		threads.append(notifier)
		threads.append(syncer)
		threads.append(search)
		threads.append(cache)

	for th in threads :
		th.start()

	logging.progress("%s/master: going to sleep, waiting for signals." % dname)

	while True :
		signal.pause()

	terminate_cleanly(None, None, threads)
