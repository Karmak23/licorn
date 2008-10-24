#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn daemon :
  - monitor shared group dirs and other special paths, and reapply posix perms or
posix ACL the Right Way They Should Be (TM).

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

import sys, os, time, signal

# argparser ?
from licorn.foundations import process, logging, exceptions, styles, options
from licorn.core        import keywords, configuration

# TODO: make our own argparser, for the daemon.
from licorn.interfaces.cli import argparser

from licorn.daemon.internals import Cache, FileSearchServer, INotifier, ACLChecker, pid_path, wpid_path, log_path, pname, fork_http_server

def terminate(signum, frame) :

	global is_running

	if is_running :
		if signum is None :
			logging.progress("%s/master: cleaning up and stopping threads..." % pname)
		else :
			logging.warning('%s/master: signal %s received, shutting down...' % (pname, signum))

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
			logging.warning("Can't remove %s (was: %s)." % (styles.stylize(styles.ST_PATH, pid_path), e))

		logging.progress("%s/master: joining threads." % pname)
		server.join()
		cache.join()
		notifier.join()
		aclchecker.join()

		logging.progress("%s/master: exiting." % pname)
		is_running = False
		sys.exit(0)

if __name__ == "__main__" :

	(opts, args) = argparser.licornd_parse_arguments(_app)

	options.SetFrom(opts)

	if process.already_running(pid_path) :
		logging.notice("%s: already running (pid %s), not restarting." % (pname, open(pid_path, 'r').read()[:-1]))
		sys.exit(0)

	if os.getuid() != 0 or os.geteuid() != 0 :
		logging.error("%s: must be run as %s." % (pname, styles.stylize(styles.ST_NAME, 'root')))	

	if opts.daemon : 
		process.daemonize(log_path, pid_path)
	else : 
		open(pid_path, 'w').write("%s\n" % os.getpid())

	fork_http_server()

	process.set_name('%s/master' % pname)
	logging.progress("%s/master: starting (pid %d)." % (pname, os.getpid()))

	is_running = True

	signal.signal(signal.SIGINT, terminate)
	signal.signal(signal.SIGTERM, terminate)
	signal.signal(signal.SIGHUP, terminate)

	# create thread instances.
	server     = FileSearchServer(pname)
	cache      = Cache(keywords, pname)
	aclchecker = ACLChecker(cache, pname)
	notifier   = INotifier(aclchecker, cache, pname)
			
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

			logging.progress("%s/master: going to sleep." % pname)

			while True :
				# wait for signals.
				signal.pause()

		except exceptions.LicornException, e :
			logging.warning(str(e), e.errno)

	finally :
		terminate(None, None)
