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

import os, signal, time

from licorn.foundations         import process, logging, options
from licorn.foundations.objects import MessageProcessor
from licorn.foundations.threads import LicornJobThread

from licorn.core.configuration    import LicornConfiguration
from licorn.core.users            import UsersController
from licorn.core.groups           import GroupsController
from licorn.core.profiles         import ProfilesController
from licorn.core.privileges       import PrivilegesWhiteList
from licorn.core.keywords         import KeywordsController
from licorn.core.machines         import MachinesController

from licorn.daemon.core                  import dname, terminate_cleanly, \
	exit_if_already_running, refork_if_not_running_root_or_die, \
	eventually_daemonize, setup_signals_handler, licornd_parse_arguments

from licorn.daemon.internals.wmi         import fork_wmi
from licorn.daemon.internals.acl_checker import ACLChecker
from licorn.daemon.internals.inotifier   import INotifier
from licorn.daemon.internals.cmdlistener import CommandListener
#from licorn.daemon.internals.scheduler   import BasicScheduler
#from licorn.daemon.internals.cache       import Cache
#from licorn.daemon.internals.searcher    import FileSearchServer
#from licorn.daemon.internals.syncer       import ServerSyncer, ClientSyncer

if __name__ == "__main__":

	exit_if_already_running()
	refork_if_not_running_root_or_die()

	configuration = LicornConfiguration(batch=True)

	(opts, args) = licornd_parse_arguments(current_app, configuration)

	# This is needed generally in the daemon, because it is per nature a
	# non-interactive process. At first launch, it will have to tweak the system
	# a little (in some conditions), and won't be able to as user / admin if
	# forked in the background. It must have the ability to solve relatively
	# simple problems on its own. Only --force related questions will make it
	# stop, and there should not be any of these in its daemon's life.
	opts.batch = True
	options.SetFrom(opts)

	# remember our children threads.
	threads = []

	pname = '%s/master' % dname
	process.set_name(pname)

	eventually_daemonize(opts)

	pids_to_wake = []

	if opts.pid_to_wake:
		pids_to_wake.append(opts.pid_to_wake)

	if configuration.licornd.wmi.enabled:
		wmi_pid = fork_wmi(opts)
		pids_to_wake.append(wmi_pid)
	else:
		wmi_pid = None
		logging.info('''%s: not starting WMI, disabled by '''
			'''configuration directive.''' % pname)

	# log things after having daemonized, else it doesn't show in the log,
	# but on the terminal.
	logging.notice("%s(%d): starting all threads." % (
		pname, os.getpid()))

	setup_signals_handler(pname, configuration, threads, opts, wmi_pid)

	if configuration.licornd.role == "client":
		pass
		#syncer = ClientSyncer(dname)
		#threads.append(syncer)

		# TODO: get the cache from the server, it has the
		# one in sync with the NFS-served files.

	else:
		users = UsersController(configuration)
		groups = GroupsController(configuration, users)
		privileges = PrivilegesWhiteList(configuration,
			configuration.privileges_whitelist_data_file)
		privileges.set_groups_controller(groups)

		# Now that the daemon holds every core object, this check must be done
		# prior to everything else, to ensure the system is in a good state
		# before modifying it. Not a minimal check, to be sure every needed
		# group is created.
		configuration.check(minimal=False, batch=True)

		profiles = ProfilesController(configuration, groups, users)
		machines = MachinesController(configuration)
		keywords = KeywordsController(configuration)


		# here is the Message processor, used to communicate with clients, via Pyro.
		msgproc = MessageProcessor()
		options.msgproc = msgproc

		#syncer     = ServerSyncer(dname)
		#searcher   = FileSearchServer(dname)
		#cache      = Cache(keywords, dname)

		# launch a machine status update every 30 seconds, but the first update
		# will be in only 1.0 seconds, else we don't have any info when opening
		# the WMI right now.
		msu         = LicornJobThread(dname, machines.update_statuses,
						time=(time.time()+1.0), delay=30.0,
						tname='MachineStatusesUpdater')
		aclchecker  = ACLChecker(None, dname)
		inotifier    = INotifier(aclchecker, None, configuration, groups,
			dname, opts.no_boot_check)
		groups.set_inotifier(inotifier)
		cmdlistener = CommandListener(dname,
			pids_to_wake=pids_to_wake,
			configuration=configuration,
			users=users,
			groups=groups,
			profiles=profiles,
			privileges=privileges,
			keywords=keywords,
			machines=machines,
			msgproc=msgproc)
		#threads.append(cache)
		threads.append(aclchecker)
		threads.append(inotifier)
		threads.append(cmdlistener)
		threads.append(msu)
		#threads.append(syncer)
		#threads.append(searcher)

	for th in threads:
		th.start()

	logging.notice('''%s(%s): all threads started, going to sleep waiting '''
		'''for signals.''' % (pname, os.getpid()))

	while True:
		signal.pause()

	terminate_cleanly(None, None, threads)
