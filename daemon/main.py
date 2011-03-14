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

# -*- coding: utf-8 -*-
"""
Licorn Daemon - http://docs.licorn.org/daemon/index.html

:copyright: 2009-2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

#: import gettext for all licorn code, and setup utf-8 codeset.
#: this is particularly needed to avoid #531 and all other kind
#: of equivalent problems.
import gettext
gettext.install('licorn', unicode=True)

import time
dstart_time = time.time()

import os, sys, signal, resource, gc

from threading   import current_thread
from Queue       import Empty, Queue, PriorityQueue
from optparse    import OptionParser

from licorn.foundations           import options, logging, exceptions
from licorn.foundations           import process, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace, insert_ltrace, dump, fulldump
from licorn.foundations.base      import NamedObject, MixedDictObject, Singleton
from licorn.foundations.thread    import _threads, _thcount

from licorn.core                  import version, LMC

from licorn.daemon                import LicornDaemonInteractor, \
											LicornThreads, LicornQueues, \
											priorities, roles, \
											client
from licorn.daemon.wmi            import WMIThread
from licorn.daemon.threads        import LicornJobThread, \
											ServiceWorkerThread, \
											ACLCkeckerThread, \
											NetworkWorkerThread
from licorn.daemon.inotifier      import INotifier
from licorn.daemon.cmdlistener    import CommandListener

#from licorn.daemon.cache         import Cache
#from licorn.daemon.searcher      import FileSearchServer
#from licorn.daemon.syncer        import ServerSyncer, ClientSyncer

class LicornDaemon(Singleton):
	""" The big-balled daemon. """
	#: dname is used by daemon threads to set a part of their name. It's a
	#: constant.
	dname = 'licornd'

	def __init__(self):
		#NOTE: self.name will be overriten in run()
		self.__name    = LicornDaemon.dname
		self.__pid     = os.getpid()

		self.__threads = LicornThreads('daemon_threads')
		self.__queues  = LicornQueues('daemon_queues')

		LMC.licornd    = self
		#print '>> licornd.__init__', LMC, LMC.licornd
	def __str__(self):
		return '%s(%s)' % (stylize(ST_NAME, self.name), self.pid)
	def __repr__(self):
		return '%s(%s)' % (stylize(ST_NAME, self.name), self.pid)

	@property
	def name(self):
		return self.__name
	@property
	def pid(self):
		return self.__pid
	@property
	def queues(self):
		return self.__queues
	@property
	def threads(self):
		return self.__threads

	def __init_daemon_phase_1(self):
		""" TODO. """

		# the service facility is the first thing started, to make it
		# available to LMC, controllers and others if they need to plan
		# background correction jobs, or the like.

		logging.info(_(u'%s: initializing facilities, backends, '
								'controllers and extensions.') % str(self))

		self.__queues.serviceQ = PriorityQueue()
		self.__threads.append(ServiceWorkerThread(
							in_queue=self.__queues.serviceQ,
							peers_min=self.configuration.threads.service.min,
							peers_max=self.configuration.threads.service.max,
							licornd=self,
							# Service threads are not daemon, they must
							# terminate before we quit.
							daemon=False))
		self.__queues.aclcheckQ = PriorityQueue()
		self.__threads.append(ACLCkeckerThread(
							in_queue=self.__queues.aclcheckQ,
							peers_min=self.configuration.threads.aclcheck.min,
							peers_max=self.configuration.threads.aclcheck.max,
							licornd=self,
							daemon=False))
		self.__queues.networkQ = PriorityQueue()
		self.__threads.append(NetworkWorkerThread(
							in_queue=self.__queues.networkQ,
							peers_min=self.configuration.threads.network.min,
							peers_max=self.configuration.threads.network.max,
							licornd=self))

		# create the INotifier thread, and map its WatchManager methods to
		# us, they will be used by controllers, extensions and every single
		# core object.
		if self.configuration.inotifier.enabled:
			self.__threads._inotifier = INotifier(self)

			ino = self.__threads._inotifier
			ino.start()

			# proxy methods to the INotifier (generally speaking, core objects
			# should cal them via the daemon, only.
			self.inotifier_add            = ino._wm.add_watch
			self.inotifier_del            = ino._wm.rm_watch
			self.inotifier_watches        = ino._wm.watches
			self.inotifier_watch_conf     = ino.inotifier_watch_conf
			self.inotifier_del_conf_watch = ino.inotifier_del_conf_watch

			del ino
		else:
			def inotifier_disabled(*args, **kwargs):
				pass

			self.inotifier_add            = inotifier_disabled
			self.inotifier_del            = inotifier_disabled
			self.inotifier_watches        = inotifier_disabled
			self.inotifier_watch_conf     = inotifier_disabled
			self.inotifier_del_conf_watch = inotifier_disabled

		# NOTE: the CommandListener must be launched prior to anything, to
		# ensure connection validation form clients and other servers are
		# possible as early as possible.
		if self.configuration.role == roles.CLIENT:

			# the CommandListener needs the objects :obj:`LMC.groups`,
			# :obj:`LMC.system` and :obj:`LMC.msgproc` to be OK to run, that's
			# why there's a first pass.
			LMC.init_client_first_pass()

			self.__threads.CommandListener = CommandListener(licornd=self,
											pids_to_wake=self.pids_to_wake)
			self.__threads.CommandListener.start()

			from licorn.daemon import client
			client.ServerLMC.connect()
			LMC.init_client_second_pass(client.ServerLMC)

		else:
			LMC.init_server()

			self.__threads.CommandListener = CommandListener(licornd=self,
											pids_to_wake=self.pids_to_wake)
			self.__threads.CommandListener.start()

			self.__threads._inotifier.collect()
	def __init_daemon_phase_2(self):
		""" TODO. """

		# client and server mode get the benefits of periodic thread cleaner.
		self.__threads.append(LicornJobThread(
				tname='DeadThreadCleaner',
				target=self.__job_periodic_cleaner,
				time=(time.time()+30.0),
				delay=LMC.configuration.licornd.threads.wipe_time
			))

		if self.configuration.role == roles.CLIENT:

			self.service_enqueue(priorities.NORMAL,
						client.client_hello, job_delay=1.0)

			# self.__threads.status = PULL IN the dbus status pusher
			#self.__threads.syncer = ClientSyncer(self)

			# TODO: get the cache from the server, it has the
			# one in sync with the NFS-served files.

		else: # roles.SERVER

			#self.__threads.syncer   = ServerSyncer(self)
			#self.__threads.searcher = FileSearchServer(self)
			#self.__threads.cache    = Cache(self, keywords)

			if self.configuration.wmi.enabled and self.options.wmi_enabled:
				self.__threads.wmi = WMIThread(self)
			else:
				logging.info('%s: not starting WMI, disabled on command '
					'line or by configuration directive.' % str(self))

			self.service_enqueue(priorities.NORMAL, LMC.machines.initial_scan)
	def __collect_modules_threads(self):
		""" Collect and start extensions and backend threads; record them
			in our threads list to stop them on daemon shutdown.
		"""
		for module_manager in (LMC.backends, LMC.extensions):
			for module in module_manager:
				for thread in module.threads:
					self.__threads[thread.name] = thread
					if not thread.is_alive():
						thread.start()
	def __start_threads(self):
		""" Iterate :attr:`self.__threads` and start
			all not already started threads. """

		# this first message has to come after having daemonized, else it doesn't
		# show in the log, but on the terminal the daemon was launched.
		logging.notice(_(u'%s: starting all threads.') % str(self))

		for (thname, th) in self.__threads.items():
			# check if threads are alive before starting them, because some
			# extensions already started them, to catch ealy events (which is
			# not a problem per se).
			if not th.is_alive():
				assert ltrace('daemon', 'starting thread %s.' % thname)
				th.start()
	def __stop_threads(self):
		logging.progress(_(u'%s: stopping threads.') % str(self))

		# don't use iteritems() in case we stop during start and not all threads
		# have been added yet.
		for (thname, th) in self.__threads.items():
			assert ltrace('thread', 'stopping thread %s.' % thname)
			if th.is_alive():
				th.stop()
				time.sleep(0.01)

		assert ltrace('thread', 'stopping thread INotifier.')
		if self.__threads._inotifier.is_alive():
			self.__threads._inotifier.stop()
			# we need to wait a little more for INotifier, it can take ages
			# to remove all directory watches.
			time.sleep(0.3)

	def run(self):
		self.refork_if_not_root_or_die()

		self.__setup_threaded_gettext()

		# this is the first thing to do, because argparser needs default
		# configuration values.
		LMC.init_conf(batch=True)

		self.configuration = LMC.configuration.licornd
		self.pid_file      = self.configuration.pid_file

		(self.options, self.arguments) = self._cli_parse_arguments()

		self.__name = '%s/%s' % (LicornDaemon.dname,
			roles[self.configuration.role].lower())

		# now that we have a pretty and explicit name, advertise it
		# to the outside world (for `ps`, `top`, etc).
		process.set_name(self.__name)

		# NOTE: this method must be called *after*
		# :meth:`self._cli_parse_arguments()`, because it uses
		# :attr:`self.options` which must be already filled.
		self.replace_or_exit()

		# NOTE: :arg:`--batch` is needed generally in the daemon, because it is
		# per nature a non-interactive process. At first launch, it will have to
		# tweak the system a little (in some conditions), and won't be able to ask
		# the user / admin if it is forked into the background. It must have the
		# ability to solve relatively simple problems on its own. Only
		# :arg:`--force` related questions will make it stop, and there should not
		# be any of these in its daemon's life.
		self.options.batch = True

		# setup the Licorn-global options object.
		options.SetFrom(self.options)

		if self.options.daemon:
			process.daemonize(self.configuration.log_file)

		# if still here (not exited before), its time to signify we are going
		# to stay: write the pid file.
		process.write_pid_file(self.pid_file)

		self.pids_to_wake = []

		if self.options.pid_to_wake:
			self.pids_to_wake.append(options.pid_to_wake)

		self.setup_signals_handler()

		self.__init_daemon_phase_1()
		self.__collect_modules_threads()
		self.__init_daemon_phase_2()
		self.__start_threads()

		if options.daemon:
			logging.notice(_(u'%s: all threads started, going to sleep '
				'waiting for signals.') % str(self))
			signal.pause()
		else:
			logging.notice(_(u'%s: all threads started, ready for TTY '
				'interaction.') % str(self))
			# set up the interaction with admin on TTY std*, only if we do not
			# fork into the background. This is a special thread case, not
			# handled by the global start / stop mechanism, to be able to start
			# it before every other thread, and stop it after all other have
			# been stopped.
			LicornDaemonInteractor(self).run()

		# if we get here (don't know how at all: we should only receive
		# signals), stop cleanly (as if a signal was received).
		self.terminate(None, None)
	def dump_status(self, long_output=False, precision=None):
		""" return daemon status (and all threads status, too). """

		assert ltrace('daemon', '| get_daemon_status(%s, %s)' % (
			long_output, precision))

		# if not is_localhost(client) and not is_server_peer(client):
		# logging.warning('unauthorized call from %s!' % client)
		#	return

		rusage   = resource.getrusage(resource.RUSAGE_SELF)
		pagesize = resource.getpagesize()

		data = ('-- Licorn® daemon {full}status: '
			'up {uptime}, {nb_threads} threads, {nb_controllers} controllers, '
			'{nb_queues} queues, {nb_locks} locks\n'
			'CPU: usr {ru_utime:.3}s, sys {ru_stime:.3}s '
			'MEM: res {mem_res:.2}Mb shr {mem_shr:.2}Mb '
				'ush {mem_ush:.2}Mb stk {mem_stk:.2}Mb\n'.format(
			full=stylize(ST_COMMENT, 'full ') if long_output else '',
			uptime=stylize(ST_COMMENT,
				pyutils.format_time_delta(time.time() - dstart_time)),
			nb_threads=_thcount(),
			nb_controllers=stylize(ST_UGID, len(LMC)),
			nb_queues= stylize(ST_UGID, len(self.__queues)),
			nb_locks=stylize(ST_UGID, len(LMC.locks)),
			ru_utime=rusage.ru_utime, #format_time_delta(int(rusage.ru_utime), long=False),
			ru_stime=rusage.ru_stime, #format_time_delta(int(rusage.ru_stime), long=False),
			mem_res=float(rusage.ru_maxrss * pagesize) / (1024.0*1024.0),
			mem_shr=float(rusage.ru_ixrss * pagesize) / (1024.0*1024.0),
			mem_ush=float(rusage.ru_idrss * pagesize) / (1024.0*1024.0),
			mem_stk=float(rusage.ru_isrss * pagesize) / (1024.0*1024.0)
			))

		data += ('Threads: %s\n' %
				''.join([ ('%s/%s %s' % (tcur, tmax, ttype)).center(20)
						for tcur, tmax, ttype in (
							(
								ServiceWorkerThread.instances,
								ServiceWorkerThread.peers_max,
								'servicers'
							),
							(
								ACLCkeckerThread.instances,
								ACLCkeckerThread.peers_max,
								'aclcheckers'
							),
							(
								NetworkWorkerThread.instances,
								NetworkWorkerThread.peers_max,
								'networkers'
							)
						)
					])
				)

		data += ('Queues:  %s\n' %
				''.join([ ('%s: %s' % (qname, queue.qsize())).center(20)
					for qname, queue in self.__queues.iteritems()]))

		#if long_output:
		#	for controller in LMC:
		#		if hasattr(controller, 'dump_status'):
		#			data += 'controller %s\n' % controller.dump_status(long_output)

		# don't use itervalues(), threads are moving target now.
		tdata = [ ((self.__threads._inotifier.name, 'thread %s\n' %
			self.__threads._inotifier.dump_status(long_output, precision))) ]

		for tname, thread in self.__threads.items():
			if thread.is_alive():
				if hasattr(thread, 'dump_status'):
					tdata.append((tname, 'thread %s\n' %
									thread.dump_status(long_output, precision)))
				else:
					tdata.append((tname, '''thread %s%s(%s) doesn't implement '''
						'''dump_status().\n''' % (
							stylize(ST_NAME, thread.name),
							stylize(ST_OK, '&') if thread.daemon else '',
							thread.ident)))
			else:
				tdata.append((tname, 'thread %s%s(%d) has terminated.\n' % (
					stylize(ST_NAME, thread.name),
					stylize(ST_OK, '&') if thread.daemon else '',
					0 if thread.ident is None else thread.ident)))

		data += ''.join([ value for key, value in sorted(tdata)])
		return data
	def setup_signals_handler(self):
		""" redirect termination signals to a the function which will clean everything. """

		#signal.signal(signal.SIGCHLD, signal.SIG_IGN)
		signal.signal(signal.SIGTERM, self.terminate)
		signal.signal(signal.SIGHUP,  self.terminate)
		signal.signal(signal.SIGINT,  self.terminate)
		signal.signal(signal.SIGUSR1, self.restart)
	def check_aborted_daemon(self, exclude):
		""" In some cases (unhandled internal crash, failed termination, stopped
			job, whatever), one or more dead daemons could still exist, occupying
			(or not) the pyro port, without a valid PID file.

			Find'em and kill'em all, callaghan.
		"""

		exclude.append(self.pid)
		my_process_name = sys.argv[0]

		for entry in os.listdir('/proc'):
			if entry.isdigit():
				if int(entry) in exclude:
					continue

				try:
					if my_process_name in open('/proc/%s/cmdline' % entry).read():
						os.kill(int(entry), signal.SIGKILL)
						time.sleep(0.2)
						logging.notice(_(u'{0}: killed aborted '
							'instance @pid {1}.').format(str(self), entry))
				except (IOError, OSError), e:
					# in rare cases, the process vanishes during the clean-up
					if e.errno != 2:
						raise e
	def replace_or_exit(self):
		""" See if another daemon process if already running. If it is and we're not
			asked to replace it, exit. Else, try to kill it and start. It the
			process won't die after a certain period of time (10 seconds), alert the
			user and exit.
		"""

		exclude = []

		if os.path.exists(self.pid_file):
			old_pid = int(open(self.pid_file).read().strip())
			exclude.append(old_pid)

		self.check_aborted_daemon(exclude)

		if process.already_running(self.pid_file):
			if self.options.replace:
				logging.notice(_(u'{0}: trying to replace existing instance '
					'@pid {1}.').format(str(self), old_pid))

				# kill the existing instance, gently
				os.kill(old_pid, signal.SIGTERM)

				counter = 0

				while os.path.exists(self.pid_file):
					time.sleep(0.1)

					if counter >= 25:
						logging.notice(_(u'%s: existing instance still '
							'running, we\'re going to be more incisive in '
							'a few seconds.') % str(self))
						break
					counter+=1

				# Pid file gone or not, old instance can take a bunch of time
				# shutting down, and even not suceed if something very low-level
				# is blocking. We have to verify it actually shuts down completely.
				#
				# Can't use os.waitpid(), this is not our child. We can only rely on
				# /proc/$PID to tell if it is still there. Not optimal but accurate.
				proc_pid = '/proc/%s' % old_pid

				counter = 0
				not_yet_displayed_one = True
				not_yet_displayed_two = True
				killed  = False
				while os.path.exists(proc_pid):
					time.sleep(0.1)

					if counter >= 25 and not_yet_displayed_one:
						logging.notice(_(u'%s: re-killing old instance '
							'softly with TERM signal and waiting a little '
							'more.') % str(self))

						try:
							os.kill(old_pid, signal.SIGTERM)
						except (OSError, IOError), e:
							if e.errno != 3:
								# errno 3 is "no such process": it died in the
								# meantime. Don't crash for this.
								raise
						time.sleep(0.2)
						counter += 2
						not_yet_displayed_one = False

					elif counter >= 50 and not_yet_displayed_two:
						logging.notice('%s: old instance won\'t '
							'terminate after 8 seconds. Sending '
							'KILL signal.' % str(self))

						killed = True
						try:
							os.kill(old_pid, signal.SIGKILL)
						except (OSError, IOError), e:
							if e.errno != 3:
								# errno 3 is "no such process": it died in the
								# meantime. Don't crash for this.
								raise
						time.sleep(0.2)
						counter += 2
						not_yet_displayed_two = False

					counter += 1

				logging.notice(_(u'{0}: old instance {1} terminated, we can '
					'play now.').format(str(self), _(u'nastily') if killed
							else _(u'successfully')))
			else:
				logging.notice(_(u'{0}: daemon already running (pid {1}), '
					'not restarting.').format(str(self), old_pid))
				sys.exit(0)
	def refork_if_not_root_or_die(self):
		""" If the current process is not UID(0), try to refork as root. If
			this fails, exit with an error. """
		if os.getuid() != 0 or os.geteuid() != 0:
			try:
				process.refork_as_root_or_die('licorn-daemon')
			except exceptions.LicornRuntimeException, e:
				logging.error(_(u'{0}: must be run as {1} '
					'(was: {2}).').format(str(self), stylize(ST_NAME, 'root'), e))
	def __setup_threaded_gettext(self):
		""" Make the gettext language switch be thread-dependant, to have
			multi-lingual parallel workers ;-) """
		import __builtin__

		def my_(*args, **kwargs):
			try:
				return current_thread()._(*args, **kwargs)
			except AttributeError:
				return __builtin__.__dict__['_orig__'](*args, **kwargs)

		if '_' in __builtin__.__dict__:
			__builtin__.__dict__['_orig__'] = __builtin__.__dict__['_']

		__builtin__.__dict__['_'] = my_

		fr_lang    = gettext.translation('licorn', languages=['fr'])
		self.langs = {
				'fr_FR.utf8' : fr_lang,
				'fr_FR'      : fr_lang,
				'fr'         : fr_lang,
			}

		# make the current thread (MainThread) not trigger the except everytime.
		current_thread()._ = __builtin__.__dict__['_orig__']

	def __daemon_shutdown(self):
		""" stop threads and clear pid files. """
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
			self.service_wait()
		except AttributeError, e:
			# this error arises when daemons kill each other. When I want to
			# take over a TS backgrounded daemon with -rvD and my attached
			# daemon gets rekilled immediately by another, launched by the TS.
			# This is harmless, but annoying.
			logging.warning(_(u'{0}: cannot announce shutdown '
				'to remote hosts (was: {1}).').format(str(self), e))

		self.__stop_threads()

		logging.progress(_(u'%s: joining threads.') % str(self))

		threads_pass2 = []

		for (thname, th) in self.__threads.items():
			# join threads in the reverse order they were started, and only the not
			# daemonized ones, in case daemons are stuck on blocking socket or
			# anything preventing a quick and gracefull stop.
			if th.daemon:
				assert ltrace('thread', 'skipping daemon thread %s.' % thname)
				pass
			else:
				assert ltrace('thread', 'joining %s.' % thname)
				if th.is_alive():
					logging.warning(_(u'{0}: waiting for thread {1} to '
						'finish{2}.').format(str(self),
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

		# we must join queues after threads, else we don't know why queues
		# are still full of jobs.
		#logging.progress("%s(%s): joining queues." % (self.name, self.pid))
		#for (qname, queue) in self.__queues.iteritems():
		#	assert ltrace('daemon', 'joining queue %s (%d items left).' % (
		#			qname, queue.qsize()))
		#	queue.join()

		# display the remaining active threads (presumably stuck hanging on
		# something very blocking).
		assert ltrace('thread', 'after joining threads, %s remaining: %s' % (
			_thcount(), _threads()))

		for (qname, queue) in self.__queues.iteritems():
			size = queue.qsize()
			if size > 0:
				assert ltrace('daemon', 'queue %s has %d items left: %s' % (
						qname, size, [
							str(item) for item in queue.get_nowait() ]))

		if LMC.configuration:
			LMC.configuration.CleanUp()

		LMC.terminate()

		self.unlink_pid_file()
	def unlink_pid_file(self):
		""" remove the pid file and bork if any error. """

		try:
			if os.path.exists(self.pid_file):
				os.unlink(self.pid_file)
		except (OSError, IOError), e:
			logging.warning(_(u'{0}: cannot remove {1} (was: {2}).').format(
				str(self), stylize(ST_PATH, self.pid_file), e))
	def uptime(self):
		return _(u' (up %s)') % stylize(ST_COMMENT,
				pyutils.format_time_delta(time.time() - dstart_time))
	def terminate(self, signum=None, frame=None):
		""" Close threads, wipe pid files, clean everything before closing. """

		if signum is None:
			logging.progress(_('%s: cleaning up and stopping threads…') % str(self))
		else:
			logging.notice(_('{0}: signal {1} received, '
				'shutting down…').format(str(self), signum))

		self.__daemon_shutdown()

		logging.notice(_(u'{0}: exiting{1}.').format(str(self), self.uptime()))
		sys.exit(0)
	def restart(self, signum=None, frame=None):
		logging.notice(_(u'{0}: SIGUSR1 received, preparing restart.').format(
						str(self)))

		self.__daemon_shutdown()

		# close every file descriptor (except stdin/out/err, used for logging and
		# on the console). This is needed for Pyro thread to release its socket,
		# else it's done too late and on restart the port can't be rebinded on.
		os.closerange(3, 32)

		# even after having reforked (see main.py and foundations.process) with
		# LTRACE arguments on, the first initial sys.argv hasn't bee modified,
		# we have to redo all the work here.
		cmd = ['licorn-daemon']
		cmd.extend(insert_ltrace())

		found = False
		for arg in ('-p', '--wake-pid', '--pid-to-wake'):
			try:
				wake_index = sys.argv.index(arg)
			except:
				continue

			found = True
			cmd.extend(sys.argv[0:wake_index])
			cmd.extend(sys.argv[wake_index+2:])
			# pray there is only one --wake_pid argument. As this is an internally
			# used flag only, it should be. Else we will forget to remove all other
			# and will send signals to dead processes.
			break

		if not found:
			cmd.extend(sys.argv[:])

		#print '>> daemon.restart %s' % cmd

		logging.notice(_(u'{0}: restarting{1}.').format(str(self), self.uptime()))

		# XXX: awful tricking for execvp but i'm tired of this.
		os.execvp(cmd[1], [cmd[0]] + cmd[2:])
	def reload(self):
		return "reload not implemented yet"

	def daemon_thread(klass, target, args=(), kwargs={}):
		""" TODO: turn this into a decorator, I think it makes a good candidate. """
		thread = klass(target, args, kwargs)
		daemon.threads[thread.name] = thread
		return thread
	def append_thread(self, thread, autostart=True):
		self.__threads.append(thread)
		if autostart:
			thread.start()
	def service_enqueue(self, prio, func, *args, **kwargs):
		#print '>> put', prio, func, args, kwargs
		self.__queues.serviceQ.put((prio, func, args, kwargs))

	def service_wait(self):
		if isinstance(current_thread(), ServiceWorkerThread):
			raise RuntimeError('cannot join the serviceQ from '
				'a ServiceWorkerThread instance, this would deadblock!')
		#print ">> waiting for", daemon.queues.serviceQ.qsize(), 'jobs to finish'
		self.__queues.serviceQ.join()

	def network_enqueue(self, prio, func, *args, **kwargs):
		#print '>> put', prio, func, args, kwargs
		self.__queues.networkQ.put((prio, func, args, kwargs))

	def network_wait(self):
		if isinstance(current_thread(), NetworkWorkerThread):
			raise RuntimeError('cannot join the networkQ from '
				'a NetworkWorkerThread instance, this would deadblock!')
		self.__queues.networkQ.join()

	def aclcheck_enqueue(self, prio, func, *args, **kwargs):
		#print '>> put', prio, func, args, kwargs
		self.__queues.aclcheckQ.put((prio, func, args, kwargs))

	def aclcheck_wait(self):
		if isinstance(current_thread(), ACLCkeckerThread):
			raise RuntimeError('cannot join the ackcheckerQ from '
				'a ACLCkeckerThread instance, this would deadblock!')
		self.__queues.aclcheckQ.join()
	def clean_objects(self, delay=None):
		self.__threads.DeadThreadCleaner.trigger(delay)

	def __job_periodic_cleaner(self):
		""" Ping all known machines. On online ones, try to connect to pyro and
		get current detailled status of host. Notify the host that we are its
		controlling server, and it should report future status change to us.

		LOCKED to avoid corruption if a reload() occurs during operations.
		"""

		caller = current_thread().name

		assert ltrace('daemon', '| %s:_job_periodic_cleaner()' % caller)

		for (tname, thread) in self.__threads.items():
			if not thread.is_alive():
				del self.__threads[tname]
				del thread
				logging.progress(_('{0}: wiped dead thread {1} '
					'from memory.').format(
						caller, stylize(ST_NAME, tname)))

		logging.progress(_(u'{0}: doing manual '
			'garbage collection on {1}.').format(caller,
				', '.join(str(x) for x in gc.garbage)))
		del gc.garbage[:]

		for controller in LMC:
			try:
				controller._expire_events()
			except AttributeError:
				pass
	def _cli_parse_arguments(self):
		""" Integrated help and options / arguments for licornd. """

		from licorn.foundations.argparser import (
				build_version_string,
				common_behaviour_group
			)

		app = {
			'name' : 'licornd',
			'description' : 'Licorn® Daemon:\n'
				'	Global system and service manager,\n'
				'	Command Line Interface proxy,\n'
				'	Network scanner and updater,\n'
				'	Posix1e ACL auto checker with inotify support,\n'
				'	Web Management Interface HTTP server,\n'
				'	File meta-data crawler.',
			'author' : 'Olivier Cortès <olive@deep-ocean.net>'
		}

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
			help="Don't fork as a daemon, stay on the current terminal instead."
				" Logs will be printed on standard output "
				"instead of beiing written into the logfile.")

		parser.add_option("-W", "--no-wmi",
			action="store_false", dest="wmi_enabled", default=True,
			help="Don't fork the WMI. This flag overrides the setting in %s." %
				stylize(ST_PATH, LMC.configuration.main_config_file))

		parser.add_option("-w", "--wmi-listen-address",
			action="store", dest="wmi_listen_address", default=None,
			help='Specify an IP address or a hostname to bind to. Only %s can '
				'be specified (the WMI cannot yet bind on multiple interfaces '
				'at the same time). This option takes precedence over the '
				'configuration directive, if present in %s.' % (
				stylize(ST_IMPORTANT, 'ONE address or hostname'),
				stylize(ST_PATH, LMC.configuration.main_config_file)))

		parser.add_option("-p", "--wake-pid", "--pid-to-wake",
			action="store", type="int", dest="pid_to_wake", default=None,
			help='Specify a PID to send SIGUSR1 to, when daemon is ready. Used '
				'internaly only when CLI tools start the daemon themselves.')

		parser.add_option("-r", "--replace",
			action="store_true", dest="replace", default=False,
			help='Replace an existing daemon instance. A comfort flag to avoid'
				'killing an existing daemon before relaunching a new one.')

		parser.add_option("-B", "--no-boot-check",
			action="store_true", dest="no_boot_check", default=False,
			help="Don't run the initial check on all shared directories. This "
				"makes daemon be ready faster to answer users legitimate "
				"requests, at the cost of consistency of shared data. %s: don't"
				" use this flag at server boot in init scripts. Only on daemon "
				"relaunch, on an already running system, for testing or "
				"debugging purposes." % stylize(ST_IMPORTANT,
				'EXTREME CAUTION'))

		parser.add_option_group(common_behaviour_group(app, parser, 'licornd'))

		return parser.parse_args()

daemon = LicornDaemon()

if __name__ == '__main__':
	daemon.run()
