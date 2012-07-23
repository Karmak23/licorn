#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn® daemon - http://docs.licorn.org/daemon/core.html

- monitor shared group dirs and other special paths, and reapply posix
  perms and posix1e ACsL the Way They Should Be (TM) (as documented in posix1e
  manuals).
- crawls against all shared group dirs, indexes metadata and provides a global
  search engine for all users.

This daemon exists:

- to add user functionnality to Licorn® systems.
- because of bugs in external apps (which don't respect posix1e semantics and
  can't or won't be easily fixed).

:copyright: 2005-2010 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2

"""

import time
dstart_time = time.time()

import os, sys, signal, resource, gc, __builtin__

from threading  import current_thread, Thread, active_count

from licorn.foundations           import options, settings, logging, ttyutils
from licorn.foundations           import gettext, process, pyutils, events
from licorn.foundations.events    import LicornEvent
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.constants import priorities, roles
from licorn.foundations.threads   import Event, _threads, _thcount
from licorn.foundations.workers   import workers

from licorn.core                  import LMC, version

#from licorn.daemon                import client
from licorn.daemon.base           import LicornDaemonInteractor, \
											LicornBaseDaemon, \
											LicornThreads
from licorn.daemon.threads        import GQWSchedulerThread, \
											ServiceWorkerThread, \
											ACLCkeckerThread, \
											NetworkWorkerThread, \
											LicornJobThread
from licorn.daemon.inotifier      import INotifier
from licorn.daemon.cmdlistener    import CommandListener

from licorn.daemon.rwi            import RealWorldInterface

#from licorn.daemon.cache         import Cache
#from licorn.daemon.searcher      import FileSearchServer
#from licorn.daemon.syncer        import ServerSyncer, ClientSyncer

class LicornDaemon(ObjectSingleton, LicornBaseDaemon):
	""" The big-balled daemon. """
	#: dname is used by daemon threads to set a part of their name. It's a
	#: constant.
	dname = 'licornd'

	def __init__(self):
		LicornBaseDaemon.__init__(self, dstart_time)

		self.__restart_event = Event()

		self.__threads = LicornThreads('daemon_threads')

		LMC.licornd = self
		events.collect(self)
	def __str__(self):
		return LicornBaseDaemon.__str__(self)
	@property
	def threads(self):
		return self.__threads
	def start_servicers(self):
		self.__threads.append(
			ServiceWorkerThread.setup(self,
				workers.serviceQ,
				self.configuration.threads.service.min,
				self.configuration.threads.service.max
			)
		)
	def start_aclcheckers(self):
		self.__threads.append(
			ACLCkeckerThread.setup(self,
				workers.aclcheckQ,
				self.configuration.threads.aclcheck.min,
				self.configuration.threads.aclcheck.max
			)
		)
	def start_networkers(self):
		self.__threads.append(
			NetworkWorkerThread.setup(self,
				workers.networkQ,
				self.configuration.threads.network.min,
				self.configuration.threads.network.max,
				# Network threads are daemon, because they can
				# take ages to terminate and usually block on
				# sockets. We can't afford waiting for them.
				daemon=True
			)
		)
	def init_daemon_services(self):
		""" TODO. """

		# the service facility is the first thing started, to make it
		# available to LMC, controllers and others if they need to plan
		# background correction jobs, or the like.

		if self.opts.initial_check:
			# Wait for things to be completed. For now we start
			# and consider them "not completed"
			self.initial_check_wait = {
					'threads'     : False,
					'wmi'         : False,
					'cmdlistener' : False
				}

		logging.info(_(u'{0}: initializing facilities, backends, '
								u'controllers and extensions.').format(self))

		self.start_servicers()

		if settings.role != roles.CLIENT:
			self.start_aclcheckers()
			self.start_networkers()

		events.run()

		# `upgrades` is a collection of handlers/callbacks that will be run on
		# various `*load*` events, to check that the system verifies some
		# conditions. They will "repair" it if not. Importing them is
		# sufficient to make them registered and run by the `EventManager`.
		from licorn import upgrades

		logging.info(_(u'{0}: {1} callbacks collected.').format(self,
										stylize(ST_NAME, 'upgrades')))

		# NOTE: the CommandListener must be launched prior to anything, to
		# ensure connection validation form clients and other servers are
		# possible as early as possible.
		if settings.role != roles.CLIENT:

			# if we are forking into the background, there will be no possibility
			# for the user to answer questions he won't see. Load everything in
			# batch mode for the daemon not to be halted by any question about
			# configuration alteration. If we need to make a change, Just Do It!
			LMC.init_server(batch=(self.opts.initial_check or self.opts.daemon))

			# start the WMI as soon as possible, to answer HTTP requests
			self.start_wmi()

			# The RWI must be up for the CommandListener to pick it up.
			self.rwi = RealWorldInterface(self)

			self.__threads.CommandListener = CommandListener(licornd=self,
											pids_to_wake1=self.pids_to_wake1,
											pids_to_wake2=set(self.pids_to_wake2))
			self.__threads.CommandListener.start()

		else:
			# the CommandListener needs the objects :obj:`LMC.groups`,
			# :obj:`LMC.system` and :obj:`LMC.msgproc` to be OK to run, that's
			# why there's a first pass.
			LMC.init_client_first_pass()

			# The remaining client configuration occurs in the
			# `configuration_loaded` callback below.

		# see foundations.settings (CLIENT -> inotifier disabled)
		# create the INotifier thread, and map its WatchManager methods to
		# us, they will be used by controllers, extensions and every single
		# core object.
		if self.configuration.inotifier.enabled and not self.opts.initial_check:
			ino = self.__threads._inotifier = INotifier(self)
			ino.start()

			# proxy methods to the INotifier (generally speaking, core objects
			# should cal them via the daemon, only.
			__builtin__.__dict__['L_inotifier_add']            = ino._wm.add_watch
			__builtin__.__dict__['L_inotifier_del']            = ino._wm.rm_watch
			__builtin__.__dict__['L_inotifier_watches']        = ino._wm.watches
			__builtin__.__dict__['L_inotifier_watch_conf']     = ino.inotifier_watch_conf
			__builtin__.__dict__['L_inotifier_del_conf_watch'] = ino.inotifier_del_conf_watch

			# TODO: make the collection automatic for settings (or
			# globally for foundations), too.
			settings._inotifier_install_watches()

			ino.collect()

		else:
			def inotifier_disabled(*args, **kwargs):
				pass

			__builtin__.__dict__['L_inotifier_add']            = inotifier_disabled
			__builtin__.__dict__['L_inotifier_del']            = inotifier_disabled
			__builtin__.__dict__['L_inotifier_watches']        = inotifier_disabled
			__builtin__.__dict__['L_inotifier_watch_conf']     = inotifier_disabled
			__builtin__.__dict__['L_inotifier_del_conf_watch'] = inotifier_disabled

		# client and server mode get the benefits of periodic thread cleaner.
		self.__threads.append(LicornJobThread(
				tname='DeadThreadCleaner',
				target=self.__job_periodic_cleaner,
				time=(time.time()+30.0),
				delay=self.configuration.threads.wipe_time
			))

		if settings.role == roles.SERVER:

			self.collect_and_start_threads()

			workers.service_enqueue(priorities.NORMAL, LMC.machines.initial_scan)

			#self.__threads.syncer   = ServerSyncer(self)
			#self.__threads.searcher = FileSearchServer(self)
			#self.__threads.cache    = Cache(self, keywords)
	@events.handler_method
	def settings_changed(self, event, *args, **kwargs):
		""" TODO. """

		# TODO: implement inotifier shutdown if settings say it is now.
		#		- idem for extensions / backends, etc.
		#	This method can do tricky things, that's why it's not
		# implemented for now.
		pass

	@events.callback_method
	def configuration_loaded(self, event, *args, **kwargs):
		if settings.role == roles.CLIENT:

			self.__threads.CommandListener = CommandListener(licornd=self,
											pids_to_wake1=self.pids_to_wake1)
			self.__threads.CommandListener.start()

			# NOTE: the remaining of the client processing takes place later,
			# in the 'configuration_loaded' callback.

			from licorn.daemon import client
			client.ServerLMC.connect()

			LMC.init_client_second_pass(client.ServerLMC)

			workers.service_enqueue(priorities.NORMAL,
						client.client_hello, job_delay=1.0)

			# self.__threads.status = PULL IN the dbus status pusher
			#self.__threads.syncer = ClientSyncer(self)

			# TODO: get the cache from the server, it has the
			# one in sync with the NFS-served files.

			self.collect_and_start_threads()

	def collect_and_start_threads(self, collect_only=False, full_display=True):
		""" Collect and start extensions and backend threads; record them
			in our threads list to stop them on daemon shutdown.
		"""

		if full_display:
			logging.info(_(u'{0}: collecting all threads.').format(self))

		for module_manager in (LMC.backends, LMC.extensions):
			for module in module_manager:
				for thread in module.threads:
					if thread.name not in self.__threads:
						self.__threads[thread.name] = thread

		if collect_only:
			return

		# this first message has to come after having daemonized, else it doesn't
		# show in the log, but on the terminal the daemon was launched.
		logging.notice(_(u'{0}: starting all threads.').format(self))

		for (thname, th) in self.__threads.items():
			# Check for non-GenericQueueWorkerThread and non-already-started
			# threads, and start them. Some extensions already started them,
			# to catch early events.
			if not isinstance(th, GQWSchedulerThread) \
						and not th.is_alive():
				try:
					assert ltrace(TRACE_DAEMON, 'starting thread %s.' % thname)
					th.start()

				except RuntimeError:
					logging.exception(_(u'Could not start thread {0}'), th.name)

		LicornEvent('all_thread_started').emit()
	def __stop_threads(self):
		logging.progress(_(u'{0}: stopping threads.').format(self))

		# don't use iteritems() in case we stop during start and not all threads
		# have been added yet.
		for (thname, th) in self.__threads.items():
			assert ltrace(TRACE_THREAD, 'stopping thread %s.' % thname)
			if th.is_alive():
				try:
					th.stop()

				except AttributeError:
					try:
						th.cancel()

					except AttributeError:
						logging.warning(_(u'{0}: thread {1} has no stop() '
								u'nor cancel() method! It is probably still '
								u'running.').format(self, th.name))
				time.sleep(0.01)

		if not self.opts.initial_check:
			# These 2 are not started in initial checks mode.

			if '_wmi' in self.__threads.keys():
				assert ltrace(TRACE_THREAD, 'stopping thread WMI.')
				if self.__threads._wmi.is_alive():
					self.__threads._wmi.stop()
					time.sleep(0.3)

			if settings.role != roles.CLIENT and self.configuration.inotifier.enabled:
				assert ltrace(TRACE_THREAD, 'stopping thread INotifier.')
				if self.__threads._inotifier.is_alive():
					self.__threads._inotifier.stop()
					# we need to wait a little more for INotifier, it can take ages
					# to remove all directory watches.
					time.sleep(0.3)

		events.stop()
		time.sleep(0.01)
	def start_wmi(self):
		""" Fork the WMI HTTP Server, and eventually tell it to shutdown
			existing instances (the -K option). These functionnalities seem
			to be exact opposites, but they both imply a fork()/exec()
			procedure, and are very simple to execute. That's why they are
			merged in this method."""
		assert ltrace_func(TRACE_DAEMON)

		if self.configuration.wmi.enabled and self.opts.wmi_enabled:
				# This event will trigger handlers in the `upgrades` module,
				# to check the current machine setup, and then call in turn
				# the callback below, which will really launch the WMI.
				LicornEvent('wmi_starts').emit()

		else:
			logging.info(_(u'{0}: not starting WMI, disabled on command '
				u'line or by configuration directive.').format(self))
	@events.callback_method
	def wmi_starts(self, event, *args, **kwargs):
		""" When `LicornEvent('licornd_wmi_forks')` returns, fork the WMI process.
			Used as a callback because WMI2 setup can take a while (installing
			packages and al.).
		"""

		self.eventually_end_initial_check('wmi')

		if self.opts.initial_check:
			logging.notice(_(u'{0}: not starting the WMI because initial '
									u'check in progress.').format(self))
			return

		# we cannot import this earlier, because we need the `upgrades`
		# mechanism to install twisted-web if missing.
		from licorn.daemon.wmi import WebManagementInterface

		self.__threads._wmi = WebManagementInterface().start()
	@events.callback_method
	def command_listener_starts(self, event, *args, **kwargs):
		self.eventually_end_initial_check('cmdlistener')
	@events.callback_method
	def all_thread_started(self, event, *args, **kwargs):
		self.eventually_end_initial_check('threads')

	def eventually_end_initial_check(self, event_waited_name):

		if self.opts.initial_check:
			self.initial_check_wait[event_waited_name] = True

			if False not in self.initial_check_wait.values():
				logging.notice(_(u'{0}: initial check finished, '
									u'terminating.').format(self))

				# we can't call self.terminate(), we are in a worker thread,
				# this would raise a RuntimeError when blocking on queues.
				os.kill(self.pid, signal.SIGTERM)

	def run(self):

		assert ltrace_func(TRACE_DAEMON)

		# this has to be done before anything else.
		self.load_settings()

		self.configuration = settings.licornd
		self.pid_file      = self.configuration.pid_file

		(self.opts, self.args) = self.parse_arguments()

		# setup the Licorn® global options.
		options.SetFrom(self.opts)

		self.__setup_threaded_gettext()

		self.refork_if_not_root_or_die()

		self.__name = '%s/%s' % (LicornDaemon.dname,
						roles[settings.role].lower())

		# now that we have a pretty and explicit name, advertise it
		# to the outside world (for `ps`, `top`, etc).
		process.set_name(self.__name)

		# NOTE: this method must be called *after*
		# :meth:`self.parse_arguments()`, because it uses
		# :attr:`self.opts` which must be already filled.
		self.replace_or_shutdown()

		# we were called only to shutdown the current instance. Don't go further.
		if self.opts.shutdown:
			sys.exit(0)

		# NOTE: :arg:`--batch` is needed generally in the daemon, because it is
		# per nature a non-interactive process. At first launch, it will have to
		# tweak the system a little (in some conditions), and won't be able to ask
		# the user / admin if it is forked into the background. It must have the
		# ability to solve relatively simple problems on its own. Only
		# :arg:`--force` related questions will make it stop, and there should not
		# be any of these in its daemon's life.
		self.opts.batch = True

		if self.opts.daemon:
			self.pid = process.daemonize(self.configuration.log_file,
												process_name=self.name)

		# Mark the new daemon start.
		if sys.stderr.isatty():
			sys.stderr.write('-' * (ttyutils.terminal_size()[1] or 80) + '\n')

		logging.notice(_(u'{0}: Licorn® daemon version {1} '
						u'role {2} warming up…').format(
							self, stylize(ST_SPECIAL, version),
							stylize(ST_SPECIAL, roles[settings.role].lower())))

		if self.opts.initial_check:
			# disable the LAN scan during the initial check,
			# without saving the setting for it to be still active
			# at next launch, whatever the real-on-file-setting is.
			settings.licornd.network.lan_scan = False

		# if still here (not exited before), its time to signify we are going
		# to stay: write the pid file.
		process.write_pid_file(self.pid_file)

		self.pids_to_wake1 = []
		self.pids_to_wake2 = []

		# NOTE: the optparse arguments names are "pid_to_wake1" (without "S")
		# and pids_to_wake2 (WITH 's')

		if self.opts.pid_to_wake1:
			self.pids_to_wake1.append(options.pid_to_wake1)

		if self.opts.pids_to_wake2:
			self.pids_to_wake2 = [ int(x) for x in options.pids_to_wake2.split(',') ]

		self.setup_signals_handler()

		self.init_daemon_services()

		if options.daemon:
			logging.notice(_(u'{0}: all threads started, going to sleep '
									u'waiting for signals.').format(self))

			# This will trigger a lot of things.
			LicornEvent('licornd_cruising').emit()
			signal.pause()

		elif self.opts.initial_check:
			logging.notice(_(u'{0}: all threads started, waiting for the end '
											u'of initial check.').format(self))
			signal.pause()

		else:
			logging.notice(_(u'{0}: all threads started, ready for TTY '
											u'interaction.').format(self))
			# set up the interaction with admin on TTY std*, only if we do not
			# fork into the background. This is a special thread case, not
			# handled by the global start / stop mechanism, to be able to start
			# it before every other thread, and stop it after all other have
			# been stopped.

			# This will trigger a lot of things. Delay it until interactor is started.
			LicornEvent('licornd_cruising').emit(delay=5.0)

			self.interactor = LicornDaemonInteractor(daemon=self)
			self.interactor.run()

		# if we get here (don't know how at all: we should only receive
		# signals), stop cleanly (as if a signal was received).
		self.terminate()

		assert ltrace(TRACE_DAEMON, '< run()')
	def dump_status(self, long_output=False, precision=None, as_string=True):
		""" return daemon status (and all threads status, too). """

		assert ltrace_func(TRACE_DAEMON)

		rusage   = resource.getrusage(resource.RUSAGE_SELF)
		pagesize = resource.getpagesize()

		master_locks  = []
		master_locked = []

		sub_locks  = []
		sub_locked = []

		for controller in LMC:
			if hasattr(controller, 'is_locked'):
				master_locks.append(controller.name)
				if controller.is_locked():
					master_locked.append(controller.name)

			try:
				with controller.lock:
					for objekt in controller.itervalues():
						if hasattr(objekt, '_is_locked'):
							local_name = '%s_%s' % (controller.name, objekt.name)
							sub_locks.append(local_name)
							if objekt.is_ro_locked() or objekt.is_rw_locked():
								sub_locked.append(local_name)

			except AttributeError:
				pass

		service_threads_infos = { u'servicers': (
									ServiceWorkerThread.instances,
									ServiceWorkerThread.peers_max
									)
								}

		if settings.role != roles.CLIENT:
			service_threads_infos.update({
								u'aclcheckers': (
									ACLCkeckerThread.instances,
									ACLCkeckerThread.peers_max,
									),
								u'networkers': (
									NetworkWorkerThread.instances,
									NetworkWorkerThread.peers_max,
									)
								})

		if self.configuration.inotifier.enabled:
			tdata = [ self.__threads._inotifier.dump_status(long_output, precision, as_string) ]

		else:
			tdata = []

		if '_wmi' in self.__threads.keys():
			tdata.append(self.__threads._wmi.dump_status(long_output, precision, as_string))

		# Event loop status
		tdata.append(events.dump_status(long_output, precision, as_string))

		# don't use iteritems(), threads are moving targets now and the items
		# can change very quickly.
		for tname, thread in self.__threads.items():
			if hasattr(thread, 'dump_status'):
				tdata.append(thread.dump_status(long_output, precision, as_string))
			else:
				tdata.append(process.thread_basic_info(thread, as_string))

		controllers = {}

		if long_output:
			for controller in LMC:
				if hasattr(controller, 'dump_status'):
					controllers[controller.name] = controller.dump_status(
											long_output, precision, as_string)

		if as_string:
			data = _(u'Licorn® {role} daemon {full}status: '
				u'up {uptime}, {nb_threads} threads, {nb_controllers} controllers, '
				u'{nb_queues} queues, {nb_locked}/{nb_locks} Mlocks, {sub_locked}/{sub_locks} Ulocks\n'
				u'CPU: usr {ru_utime:.3}s, sys {ru_stime:.3}s '
				u'MEM: res {mem_res:.2}Mb shr {mem_shr:.2}Mb '
					u'ush {mem_ush:.2}Mb stk {mem_stk:.2}Mb\n').format(
				full=stylize(ST_COMMENT, 'full ') if long_output else '',
				role=stylize(ST_ATTR, roles[settings.role]),
				uptime=stylize(ST_COMMENT,
					pyutils.format_time_delta(time.time() - dstart_time)),
				nb_threads=_thcount(),
				nb_controllers=stylize(ST_UGID, len(LMC)),
				nb_queues=stylize(ST_UGID, len(workers.queues)),
				nb_locked=stylize(ST_IMPORTANT, len(master_locked)),
				nb_locks=stylize(ST_UGID, len(master_locks)),
				sub_locked=stylize(ST_IMPORTANT, len(sub_locked)),
				sub_locks=stylize(ST_UGID, len(sub_locks)),
				ru_utime=rusage.ru_utime, #format_time_delta(int(rusage.ru_utime), long=False),
				ru_stime=rusage.ru_stime, #format_time_delta(int(rusage.ru_stime), long=False),
				mem_res=float(rusage.ru_maxrss * pagesize) / (1024.0*1024.0),
				mem_shr=float(rusage.ru_ixrss * pagesize) / (1024.0*1024.0),
				mem_ush=float(rusage.ru_idrss * pagesize) / (1024.0*1024.0),
				mem_stk=float(rusage.ru_isrss * pagesize) / (1024.0*1024.0)
				)

			if len(master_locked) > 0:
				data += _(u'Mlocks:  %s\n') % u', '.join(stylize(ST_IMPORTANT, x)
														for x in master_locked)

			if len(sub_locked) > 0:
				data += _(u'Ulocks:  %s\n') % u', '.join(stylize(ST_IMPORTANT, x)
													for x in sub_locked)

			data += _(u'Threads: %s\n') % u''.join([ (u'%s/%s %s' %
						(nbs[0], nbs[1], ttype)).center(20)
							for ttype, nbs in service_threads_infos.iteritems()
						])

			data += _(u'Queues:  %s\n') % u''.join([ (u'%s: %s' %
						(qname, queue.qsize())).center(20)
							for qname, queue in workers.queues.iteritems()])


			"""
			if thread.is_alive():
				if hasattr(thread, 'dump_status'):
					tdata.append((tname, _(u'thread %s\n') %
									thread.dump_status(long_output, precision, as_string)))
				else:
					if as_string:
						tdata.append((tname, _(u'thread {0}{1}({2}) does not '
							u'implement dump_status().\n').format(
								stylize(ST_NAME, thread.name),
								stylize(ST_OK, u'&') if thread.daemon else '',
								thread.ident)))
			else:
				tdata.append((tname, _(u'thread {0}{1}({2}) '
					u'has terminated.\n').format(
						stylize(ST_NAME, thread.name),
						stylize(ST_OK, u'&') if thread.daemon else '',
						0 if thread.ident is None else thread.ident)))
			"""
			data += u'\n'.join(sorted(tdata)) + '\n'

			return data

		else:
			return dict(
				role=settings.role,
				uptime=time.time() - dstart_time,
				nb_threads=active_count(),
				nb_controllers=len(LMC),
				mlocks=master_locks,
				mlocked=master_locked,
				slocks=sub_locks,
				slocked=sub_locked,
				ru_utime=rusage.ru_utime, #format_time_delta(int(rusage.ru_utime), long=False),
				ru_stime=rusage.ru_stime, #format_time_delta(int(rusage.ru_stime), long=False),
				mem_res=float(rusage.ru_maxrss * pagesize) / (1024.0*1024.0),
				mem_shr=float(rusage.ru_ixrss * pagesize) / (1024.0*1024.0),
				mem_ush=float(rusage.ru_idrss * pagesize) / (1024.0*1024.0),
				mem_stk=float(rusage.ru_isrss * pagesize) / (1024.0*1024.0),
				threads_infos=service_threads_infos,
				queues_infos=dict((qname, queue.qsize())
								for qname, queue
									in workers.queues.iteritems()),
				threads_data=tdata,
			)
	@events.handler_method
	def need_restart(self, *args, **kwargs):

		if self.__restart_event.is_set():
			# be sure we restart only one time. The Event can be
			# sent more than once time when backend change.
			return

		self.__restart_event.set()

		# We've got to be sure everyone is ready to restart !
		LicornEvent('daemon_will_restart', reason=kwargs.get('reason'), synchronous=True).emit()

		# TODO: mark the 'restart' status in LMC.system. This needs
		# system.status become a property...

		# we need to start a separate daemon thread, else restart() will
		# do some cleanup work that will deadblock serviceQ.
		t = Thread(target=self.restart)
		t.daemon = True
		t.start()
	def __setup_threaded_gettext(self):
		""" Make the gettext language switch be thread-dependant, to have
			multi-lingual parallel workers ;-)

			.. note:: it seems `foundations.options` is not yet setup when
				this method launches. No output
		"""

		assert ltrace(TRACE_DAEMON, '| __setup_threaded_gettext()')

		def my_(*args, **kwargs):
			try:
				return current_thread()._(*args, **kwargs)

			except AttributeError:
				return __builtin__.__dict__['_orig__'](*args, **kwargs)

		if '_' in __builtin__.__dict__:
			__builtin__.__dict__['_orig__'] = __builtin__.__dict__['_']

		__builtin__.__dict__['_'] = my_

		self.langs = {}
		langs      = {
				'fr': (u'fr_FR.utf8', u'fr_FR'),
			}

		for lang, alternatives in langs.iteritems():
			try:
				gtlang = gettext.translation('licorn', languages=[ lang ])

			except (IOError, OSError):
				if os.geteuid() == 0:
					# Don't bother when we are not root, the daemon will
					# refork/re-exec and re-encounter this error anyway.
					logging.exception(_(u'Could not load gettext translations '
									u'for language {0}'), (ST_NAME, lang))

			else:
				logging.progress(_('Successfully loaded gettext translations '
						u'for language {0}.').format(stylize(ST_NAME, lang)))

				# setup aliases
				# FIXME: shouldn't we get them from /etc/locale.alias ?
				for alternative in alternatives:
					self.langs[alternative] = gtlang

				self.langs[lang] = gtlang

		# make the current thread (MainThread) not trigger the except everytime.
		current_thread()._ = __builtin__.__dict__['_orig__']
	def daemon_shutdown(self):
		""" stop threads and clear pid files. """

		LicornEvent('daemon_shutdown', synchronous=True).emit(priorities.HIGH)

		try:
			# before stopping threads (notably cmdlistener), we've got to announce
			# out shutdown to peers, for them not to look for us in the future.
			LMC.system.announce_shutdown()

			# we now have to wait, else we would terminate while we are announcing
			# shutdown and this will imply some timeouts and (false negative)
			# connection denied errors.
			#
			# NOTE: this could deadblock for other reasons (serviceQ very busy)
			# but for now I hope not, else we would have to find a very
			# complicated system, or make announce_shutdown() completely
			# synchronous, which is not a problem per se but would remove
			# parallelism from it and make announcing last sightly longer.
			workers.service_wait()

		except AttributeError, e:
			# this error arises when daemons kill each other. When I want to
			# take over a TS backgrounded daemon with -rvD and my attached
			# daemon gets rekilled immediately by another, launched by the TS.
			# This is harmless, but annoying.
			logging.warning(_(u'{0}: cannot announce shutdown '
				u'to remote hosts (was: {1}).').format(self, e))

		self.__stop_threads()

		logging.progress(_(u'{0}: joining threads.').format(self))

		threads_pass2 = []

		for (thname, th) in self.__threads.items():
			# join threads in the reverse order they were started, and only the not
			# daemonized ones, in case daemons are stuck on blocking socket or
			# anything preventing a quick and gracefull stop.
			if th.daemon:
				assert ltrace(TRACE_THREAD, 'skipping daemon thread %s.' % thname)
				pass
			else:
				assert ltrace(TRACE_THREAD, 'joining %s.' % thname)
				if th.is_alive():
					logging.warning(_(u'{0}: waiting for thread {1} to '
						u'finish{2}.').format(self,
							stylize(ST_NAME, thname),
							_(u' (currently working on %s)')
									% stylize(ST_NAME, th.job)
								if isinstance(th,
									ServiceWorkerThread) else ''))
					threads_pass2.append((th.name, th))
					th.stop()
					time.sleep(0.05)
				else:
					th.join()

		for thname, th in threads_pass2:
			th.join()

		# display the remaining active threads (presumably stuck hanging on
		# something very blocking).
		assert ltrace(TRACE_THREAD, 'after joining threads, %s remaining: %s' % (
			_thcount(), _threads()))

		workers.stop()

		if LMC.configuration:
			LMC.configuration.CleanUp()

		LMC.terminate()

		# do this last, to keep the interactor usable until the end.
		if not self.opts.daemon and not self.opts.initial_check:
			self.interactor.stop()
	def restart_command(self):
		# even after having reforked (see main.py and foundations.process) with
		# LTRACE arguments on, the first initial sys.argv hasn't bee modified,
		# we have to redo all the work here.

		cmd = [ 'licornd' ]
		cmd.extend(insert_ltrace())
		cmd.extend(self.clean_sys_argv())

		if CommandListener.listeners_pids != []:
			cmd.extend([ '--pids-to-wake2', ','.join(str(p)
						for p in CommandListener.listeners_pids)])

		logging.notice(_(u'{0}: restarting{1}.').format(self, self.uptime()))

		self.execvp(cmd)
	def reload(self):
		return "reload not implemented yet"

	def daemon_thread(self, klass, target, args=(), kwargs={}):
		""" TODO: turn this into a decorator, I think it makes a good candidate. """
		thread = klass(target, args, kwargs)
		daemon.threads[thread.name] = thread
		return thread
	def append_thread(self, thread, autostart=True):
		self.__threads.append(thread)
		if autostart and not thread.is_alive():
			thread.start()
	def clean_objects(self, delay=None):
		self.__threads.DeadThreadCleaner.trigger(delay)
	def __job_periodic_cleaner(self):
		""" Ping all known machines. On online ones, try to connect to pyro and
		get current detailled status of host. Notify the host that we are its
		controlling server, and it should report future status change to us.

		LOCKED to avoid corruption if a reload() occurs during operations.
		"""

		caller = current_thread().name

		assert ltrace(TRACE_DAEMON, '| %s:__job_periodic_cleaner()' % caller)

		for (tname, thread) in self.__threads.items():
			if thread.is_alive():
				if isinstance(thread, GQWSchedulerThread):
					for worker in thread.scheduled_class._instances[:]:
						if not worker.is_alive():
							assert ltrace(TRACE_THREAD, _(u'{0}: wiped dead '
								u'thread {1} from memory.').format(caller,
									stylize(ST_NAME, worker.name)))
							thread.scheduled_class._instances.remove(worker)
							del worker
			else:
				del self.__threads[tname], thread
				assert ltrace(TRACE_THREAD, _(u'{0}: wiped dead thread {1} '
					u'from memory.').format(caller, stylize(ST_NAME, tname)))

		assert ltrace(TRACE_THREAD, _(u'{0}: doing manual '
			u'garbage collection on {1}.').format(caller,
				', '.join(str(x) for x in gc.garbage)))
		del gc.garbage[:]

		for controller in LMC:
			try:
				controller._expire_events()
			except AttributeError:
				pass

daemon = LicornDaemon()

if __name__ == '__main__':
	daemon.run()
