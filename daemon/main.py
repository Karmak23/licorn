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
	can't or won't be easily fixed).

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>.
Licensed under the terms of the GNU GPL version 2.
"""

# import this first, this will initialize start_time.
# these objects are just containers which are empty yet.
from licorn.daemon import dname, dthreads, dqueues, dchildren

_app = {
	"name"       : "licornd",
	"description": '''Licorn® Daemon: posix1e ACL auto checker, Web ''' \
		'''Management Interface server and file meta-data crawler''',
	"author"     : "Olivier Cortès <olive@deep-ocean.net>"
	}

import os, signal, time, socket
from Queue import Queue

from licorn.foundations           import options, logging
from licorn.foundations           import process
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import licornd_roles

from licorn.core                  import LMC

from licorn.daemon                import terminate, setup_signals_handler
from licorn.daemon.core           import  exit_or_replace_if_already_running, \
										refork_if_not_running_root_or_die, \
										eventually_daemonize, \
										licornd_parse_arguments
from licorn.daemon.wmi            import WMIThread
from licorn.daemon.threads        import LicornJobThread, \
									LicornPoolJobThread, \
									thread_periodic_cleaner
from licorn.daemon.aclchecker     import ACLChecker
from licorn.daemon.inotifier      import INotifier
#from licorn.daemon.scheduler     import BasicScheduler
#from licorn.daemon.cache         import Cache
#from licorn.daemon.searcher      import FileSearchServer
#from licorn.daemon.syncer        import ServerSyncer, ClientSyncer

import licorn.daemon.network as daemon_network

if __name__ == "__main__":

	LMC.init_conf(batch=True)

	(opts, args) = licornd_parse_arguments(_app)

	refork_if_not_running_root_or_die()

	pname = '%s/master@%s' % (dname,
		licornd_roles[LMC.configuration.licornd.role].lower())

	my_pid = os.getpid()

	exit_or_replace_if_already_running(pname, my_pid, opts.replace)

	# NOTE: :arg:`--batch` is needed generally in the daemon, because it is
	# per nature a non-interactive process. At first launch, it will have to
	# tweak the system a little (in some conditions), and won't be able to ask
	# the user / admin if it is forked into the background. It must have the
	# ability to solve relatively simple problems on its own. Only
	# :arg:`--force` related questions will make it stop, and there should not
	# be any of these in its daemon's life.
	opts.batch = True
	options.SetFrom(opts)
	del opts, args

	process.set_name(pname)
	eventually_daemonize()

	pids_to_wake = []

	if options.pid_to_wake:
		pids_to_wake.append(options.pid_to_wake)

	# this first message has to come after having daemonized, else it doesn't
	# show in the log, but on the terminal the daemon was launched.
	logging.notice("%s(%d): starting all threads." % (pname, os.getpid()))

	setup_signals_handler(pname)

	# NOTE: the CommandListener must be launched prior to anything, to ensure
	# connection validation is feasible as early as possible.
	from licorn.daemon.cmdlistener import CommandListener

	if LMC.configuration.licornd.role == licornd_roles.CLIENT:

		# the CommandListener needs the objects :obj:`LMC.groups`,
		# :obj:`LMC.system` and :obj:`LMC.msgproc` to be OK to run, that's
		# why there's a first pass.
		LMC.init_client_first_pass()

		dthreads.cmdlistener = CommandListener(dname, pids_to_wake=pids_to_wake)
		dthreads.cmdlistener.start()

		from licorn.daemon import client
		client.ServerLMC.connect()
		LMC.init_client_second_pass(client.ServerLMC)

	else:
		LMC.init_server()
		dthreads.cmdlistener = CommandListener(dname,
			pids_to_wake=pids_to_wake)
		dthreads.cmdlistener.start()

	# FIXME: why do that ?
	options.msgproc = LMC.msgproc

	# client and server mode get the benefits of periodic thread cleaner.
	dthreads.cleaner = LicornJobThread(dname,
		target=thread_periodic_cleaner,
		time=(time.time()+30.0),
		delay=LMC.configuration.licornd.threads.wipe_time,
		tname='PeriodicThreadsCleaner')

	if LMC.configuration.licornd.role == licornd_roles.CLIENT:

		# start the greeter 1 second later, because our Pyro part must be fully
		# operational before the greeter starts to do anything.
		dthreads.greeter = LicornJobThread(dname,
				target=client.thread_greeter,
				time=(time.time()+1.0), count=1, tname='ClientToServerGreeter')

		# dthreads.status = PULL IN the dbus status pusher

		#dthreads.syncer = ClientSyncer(dname)

		# TODO: get the cache from the server, it has the
		# one in sync with the NFS-served files.

	else: # licornd_roles.SERVER

		#dthreads.syncer   = ServerSyncer(dname)
		#dthreads.searcher = FileSearchServer(dname)
		#dthreads.cache    = Cache(keywords, dname)

		if LMC.configuration.licornd.wmi.enabled and options.wmi_enabled:
			dthreads.wmi = WMIThread(pname)
		else:
			logging.info('''%s: not starting WMI, disabled on command line '''
				'''or by configuration directive.''' % pname)

		#: machines to be pinged across the network, to see if up or not. If up,
		#: a Machine() will be created.
		dqueues.ipscans = Queue()

		# machines to be pinged across the network, to update "up" status.
		dqueues.pings = Queue()

		# machines to be arp pinged across the network, to find ether address.
		dqueues.arpings = Queue()

		# IPs to be reverse resolved to hostnames.
		dqueues.reverse_dns = Queue()

		# machines to be scanned for pyro presence
		dqueues.pyrosys = Queue()

		# FIXME: verify this thread and reactivate it.
		#dthreads.periodic_scanner = LicornJobThread(dname,
		#	target=daemon_network.thread_periodic_scanner,
		#	time=(time.time()+10.0), delay=30.0, tname='PeriodicNetworkScanner')

		# FIXME: this is not the right test here...
		if LMC.configuration.licornd.threads.pool_members == 0:
			logging.warning('''Status gathering of unmanaged network '''
					'''clients disabled by configuration rule.''')
		else:
			# launch a machine status update every 30 seconds. The first update
			# will be run ASAP (in 1 second), else we don't have any info to
			# display if opening the WMI immediately.
			dthreads.network_builder = LicornJobThread(dname,
				target=daemon_network.thread_network_links_builder, daemon=True,
				time=(time.time()+1.0), count=1, tname='NetworkLinksBuilder')

		for i in range(0, LMC.configuration.licornd.threads.pool_members):

			t = daemon_network.IPScannerThread()
			dthreads[t.name] = t

			t = daemon_network.PingerThread()
			dthreads[t.name] = t

			t = daemon_network.ArpingerThread()
			dthreads[t.name] = t

			t = daemon_network.DNSReverserThread()
			dthreads[t.name] = t

			t = daemon_network.PyroFinderThread()
			dthreads[t.name] = t

		dthreads.aclchecker = ACLChecker(None, dname)

		if LMC.configuration.licornd.inotifier.enabled:
			dthreads.inotifier = INotifier(dname, options.no_boot_check)

	for (thname, th) in dthreads.iteritems():
		if not th.is_alive():
			assert ltrace('daemon', 'starting thread %s.' % thname)
			th.start()

	if options.daemon:
		logging.notice('''%s(%s): all threads started, going to sleep waiting '''
			'''for signals.''' % (pname, os.getpid()))
		signal.pause()
	else:
		logging.notice('''%s(%s): all threads started, ready for '''
			'''interaction.''' % (pname, os.getpid()))
		# set up the interaction with admin on TTY std*, only if we do not
		# fork into the background. This is a special thread case, not handled
		# by the global start / stop mechanism, to be able to start it before
		# every other thread, and stop it after all other have been stopped.
		from licorn.daemon.core import LicornDaemonInteractor
		LicornDaemonInteractor(pname).run()

	terminate(None, None)
