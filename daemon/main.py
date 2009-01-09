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

_app = {
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

from licorn.daemon.core               import ACLChecker, INotifier, pid_path, wpid_path, log_path, dname
from licorn.daemon.internals.wmi      import fork_wmi_server
from licorn.daemon.internals.cache    import Cache
from licorn.daemon.internals.searcher import FileSearchServer

def terminate(signum, frame) :
	""" Close threads, wipe pid files, clean everything before closing. """

	global is_running

	if is_running :
		if signum is None :
			logging.progress("%s/master: cleaning up and stopping threads..." % dname)
		else :
			logging.warning('%s/master: signal %s received, shutting down...' % (dname,
				signum))

		server.stop()
		notifier.stop()
		aclchecker.stop()
		cache.stop()

		configuration.CleanUp()
		try : 
			for pid_file in (pid_path, wpid_path) :
				if os.path.exists(pid_file) :
					os.unlink(pid_file)
		except (OSError, IOError), e :
			logging.warning("Can't remove %s (was: %s)." % (
				styles.stylize(styles.ST_PATH, pid_path), e))

		logging.progress("%s/master: joining threads." % dname)
		server.join()
		cache.join()
		notifier.join()
		aclchecker.join()

		logging.progress("%s/master: exiting." % dname)
		is_running = False
		sys.exit(0)

if __name__ == "__main__" :

	(opts, args) = argparser.licornd_parse_arguments(_app)

	options.SetFrom(opts)

	if process.already_running(pid_path) :
		logging.notice("%s: already running (pid %s), not restarting." % (
			dname, open(pid_path, 'r').read()[:-1]))
		sys.exit(0)

	if os.getuid() != 0 or os.geteuid() != 0 :
		logging.error("%s: must be run as %s." % (dname,
			styles.stylize(styles.ST_NAME, 'root')))	

	if opts.daemon : 
		process.daemonize(log_path, pid_path)
	else : 
		open(pid_path, 'w').write("%s\n" % os.getpid())

	fork_wmi_server()

	process.set_name('%s/master' % dname)
	logging.progress("%s/master: starting (pid %d)." % (dname, os.getpid()))

	is_running = True

	signal.signal(signal.SIGINT, terminate)
	signal.signal(signal.SIGTERM, terminate)
	signal.signal(signal.SIGHUP, terminate)

	# create thread instances.
	server     = FileSearchServer(dname)
	cache      = Cache(keywords, dname)
	aclchecker = ACLChecker(cache, dname)
	notifier   = INotifier(aclchecker, cache, dname)
			
	try :
		try :
			# start all threads.
			cache.start()
			notifier.start()
			aclchecker.start()
			server.start()

			# TODO : auto check /home/backup and /home/archives
			# TODO : auto check standard user's homes
			# TODO : receive messages to :
			#	     - remove watches on group deletion
			#	     - stop watching during checks to avoid DDoS (can be very precise, 
			#          eg stop monitoring only one group if the check is only about 
			#          *one* group).
			# TODO : create a Thread which watches keywords_data_file and
			#        updates the cache when it changes. NOTE: this will eventually go
			# into configuration module, which will launch its separate and dedicated 
			# thread, to watch configuration files.

			logging.progress("%s/master: going to sleep." % dname)

			while True :
				# wait for signals.
				signal.pause()

		except exceptions.LicornException, e :
			logging.warning(str(e), e.errno)

	finally :
		terminate(None, None)
