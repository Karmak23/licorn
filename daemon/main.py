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
import time
dstart_time = time.time()

import os, sys, signal, resource

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
											roles, priorities
from licorn.daemon.wmi            import WMIThread
from licorn.daemon.threads        import DbusThread, LicornJobThread, \
											ServiceWorkerThread
from licorn.daemon.aclchecker     import ACLChecker
from licorn.daemon.inotifier      import INotifier
from licorn.daemon.cmdlistener    import CommandListener

#from licorn.daemon.cache         import Cache
#from licorn.daemon.searcher      import FileSearchServer
#from licorn.daemon.syncer        import ServerSyncer, ClientSyncer

import licorn.daemon.network as daemon_network

class LicornDaemon(Singleton):
	""" The big-balled daemon. """
	#: dname is used by daemon threads to set a part of their name. It's a
	#: constant.
	dname = 'licornd'
	def __init__(self):
		#NOTE: self.name will be overriten in run()
		self.name    = LicornDaemon.dname
		self.pid     = os.getpid()

		self.threads = LicornThreads('daemon_threads')
		self.queues  = LicornQueues('daemon_queues')
	def __str__(self):
		return '%s(%s)' % (self.name, self.pid)
	def __repr__(self):
		return '%s(%s)' % (self.name, self.pid)
	def __init_daemon_phase_1(self):
		""" TODO. """

		# NOTE: the CommandListener must be launched prior to anything, to
		# ensure connection validation form clients and other servers are
		# possible as early as possible.

		if self.configuration.role == roles.CLIENT:

			# the CommandListener needs the objects :obj:`LMC.groups`,
			# :obj:`LMC.system` and :obj:`LMC.msgproc` to be OK to run, that's
			# why there's a first pass.
			LMC.init_client_first_pass()

			self.threads.cmdlistener = CommandListener(self,
												pids_to_wake=self.pids_to_wake)
			self.threads.cmdlistener.start()

			from licorn.daemon import client
			client.ServerLMC.connect()
			LMC.init_client_second_pass(client.ServerLMC)

		else:
			LMC.init_server()
			self.threads.cmdlistener = CommandListener(self,
												pids_to_wake=self.pids_to_wake)
			self.threads.cmdlistener.start()

		# the new service facility: just start one thread, it will handle
		# thread pool size automatically when needed.
		self.queues.serviceQ = PriorityQueue()
		self.threads.append(ServiceWorkerThread(self.queues.serviceQ, self))
	def __collect_modules_threads(self):
		""" Collect and start extensions and backend threads; record them
			in our threads list to stop them on daemon shutdown.
		"""
		for module_manager in (LMC.backends, LMC.extensions):
			for module in module_manager:
				for thread in module.threads:
					self.threads[thread.name] = thread
					if not thread.is_alive():
						thread.start()
	def __init_daemon_phase_2(self):
		""" TODO. """

		# client and server mode get the benefits of periodic thread cleaner.
		self.threads.cleaner = LicornJobThread(
				pname=self.dname,
				tname='cleaner',
				target=self._job_periodic_cleaner,
				time=(time.time()+30.0),
				delay=LMC.configuration.licornd.threads.wipe_time
			)

		if LMC.configuration.licornd.role == roles.CLIENT:

			# start the greeter 1 second later, because our Pyro part must be fully
			# operational before the greeter starts to do anything.
			self.threads.greeter = LicornJobThread(
					tname='ClientToServerGreeter',
					target=client.thread_greeter,
					time=(time.time()+1.0), count=1
				)

			# self.threads.status = PULL IN the dbus status pusher
			#self.threads.syncer = ClientSyncer(self)

			# TODO: get the cache from the server, it has the
			# one in sync with the NFS-served files.

		else: # roles.SERVER

			#self.threads.syncer   = ServerSyncer(self)
			#self.threads.searcher = FileSearchServer(self)
			#self.threads.cache    = Cache(self, keywords)

			if self.configuration.wmi.enabled and self.options.wmi_enabled:
				self.threads.wmi = WMIThread(self)
			else:
				logging.info('%s(%s): not starting WMI, disabled on command '
					'line or by configuration directive.' % (
						self.name,self.pid))

			if self.configuration.network.lan_scan:
				self.queues.serviceQ.put(
								(priorities.NORMAL, LMC.machines.initial_scan))

			# TODO: move the aclchecker to the service-facility interface.
			self.threads.aclchecker = ACLChecker(self, None)

			if self.configuration.inotifier.enabled:
				self.threads.inotifier = INotifier(self,
												self.options.no_boot_check)
	def __start_threads(self):
		""" Iterate :attr:`self.threads` and start
			all not already started threads. """

		# this first message has to come after having daemonized, else it doesn't
		# show in the log, but on the terminal the daemon was launched.
		logging.notice("%s(%d): starting all threads." % (self.name, self.pid))

		for (thname, th) in self.threads.items():
			# check if threads are alive before starting them, because some
			# extensions already started them, to catch ealy events (which is
			# not a problem per se).
			if not th.is_alive():
				assert ltrace('daemon', 'starting thread %s.' % thname)
				th.start()
	def __stop_threads(self):
		logging.progress("%s(%s): stopping threads." % (self.name, self.pid))

		# don't use iteritems() in case we stop during start and not all threads
		# have been added yet.
		for (thname, th) in self.threads.items():
			assert ltrace('thread', 'stopping thread %s.' % thname)
			if th.is_alive():
				th.stop()

	def _job_periodic_cleaner(self):
		""" Ping all known machines. On online ones, try to connect to pyro and
		get current detailled status of host. Notify the host that we are its
		controlling server, and it should report future status change to us.

		LOCKED to avoid corruption if a reload() occurs during operations.
		"""

		caller = current_thread().name

		assert ltrace('daemon', '> %s:_job_periodic_cleaner()' % caller)

		for (tname, thread) in self.threads.items():
			if not thread.is_alive():
				del self.threads[tname]
				del thread
				logging.progress('%s: wiped dead thread %s from memory.' % (
					caller, stylize(ST_NAME, tname)))

		assert ltrace('daemon', '< %s:_job_periodic_cleaner()' % caller)
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
	def run(self):
		self.refork_if_not_root_or_die()

		# this is the first thing to do, because argparser needs default
		# configuration values.
		LMC.init_conf(batch=True)

		self.configuration = LMC.configuration.licornd
		self.pid_file      = self.configuration.pid_file

		(self.options, self.arguments) = self._cli_parse_arguments()

		self.name = '%s/master@%s' % (self.dname,
			roles[self.configuration.role].lower())

		# now that we have a pretty and explicit name, advertise it
		# to the outside world (for `ps`, `top`, etc).
		process.set_name(self.name)

		# NOTE: this method must be called *after*
		# :meth:`self._cli_parse_arguments()`, because it uses
		# :attr:`self.options` which must be already filled.
		self.replace_or_exit()

		# if still here (not exited before), its time to signify we are going
		# to stay: write the pid file.
		process.write_pid_file(self.pid_file)

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

		self.pids_to_wake = []

		if self.options.pid_to_wake:
			self.pids_to_wake.append(options.pid_to_wake)

		self.setup_signals_handler()

		# FIXME: migrate this outside of the daemon core (setup daemons modules
		# or whatever can be more clever that hardcoding it here).
		self.threads.dbus = DbusThread(self)
		self.threads.dbus.start()

		self.__init_daemon_phase_1()
		self.__collect_modules_threads()
		self.__init_daemon_phase_2()
		self.__start_threads()

		if options.daemon:
			logging.notice('%s(%s): all threads started, going to sleep '
				'waiting for signals.' % (self.name, self.pid))
			signal.pause()
		else:
			logging.notice('%s(%s): all threads started, ready for TTY '
				'interaction.' % (self.name, self.pid))
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

		data = ('-- Licorn® daemon %sstatus: '
			'up %s, %s threads, %s controllers, %s queues, %s locks, %d service threads (%d started so far)\n'
			'CPU: usr %.3fs, sys %.3fs MEM: res %.2fMb shr %.2fMb ush %.2fMb stk %.2fMb\n' % (
			stylize(ST_COMMENT, 'full ') if long_output else '',
			stylize(ST_COMMENT,
			pyutils.format_time_delta(time.time() - dstart_time)),
			_thcount(), stylize(ST_UGID, len(LMC)),
			stylize(ST_UGID, len(self.queues)), stylize(ST_UGID, len(LMC.locks)),
			ServiceWorkerThread.instances, ServiceWorkerThread.number,
			rusage.ru_utime, #format_time_delta(int(rusage.ru_utime), long=False),
			rusage.ru_stime, #format_time_delta(int(rusage.ru_stime), long=False),
			float(rusage.ru_maxrss * pagesize) / (1024.0*1024.0),
			float(rusage.ru_ixrss * pagesize) / (1024.0*1024.0),
			float(rusage.ru_idrss * pagesize) / (1024.0*1024.0),
			float(rusage.ru_isrss * pagesize) / (1024.0*1024.0)
			))

		data += ('Queues: %s.\n' %
				', '.join([ '%s(%s)' % (stylize(ST_NAME, qname),
					queue.qsize()) for qname, queue in self.queues.iteritems()]))

		if long_output:
			for controller in LMC:
				if hasattr(controller, 'dump_status'):
					data += 'controller %s\n' % controller.dump_status()

		for thread in self.threads.itervalues():
			if thread.is_alive():
				if hasattr(thread, 'dump_status'):
					data += 'thread %s\n' % thread.dump_status(long_output,
						precision)
				else:
					data += ('''thread %s%s(%s) doesn't implement '''
						'''dump_status().\n''' % (
							stylize(ST_NAME, thread.name),
							stylize(ST_OK, '&') if thread.daemon else '',
							thread.ident))
			else:
				data += 'thread %s%s(%d) has terminated.\n' % (
					stylize(ST_NAME, thread.name),
					stylize(ST_OK, '&') if thread.daemon else '',
					thread.ident)
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
						logging.notice('%s(%s): killed aborted '
							'instance @pid %s.' % (
								self.name, self.pid, entry))
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
				logging.notice('%s(%s): trying to replace existing instance '
					'@pid %s.' % (self.name, self.pid, old_pid))

				# kill the existing instance, gently
				os.kill(old_pid, signal.SIGTERM)

				counter = 0

				while os.path.exists(self.pid_file):
					time.sleep(0.1)

					if counter >= 25:
						logging.notice('%s(%s): existing instance still '
							'running, we\'re going to be more incisive in '
							'a few seconds.' % (self.name, self.pid))
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
						logging.notice('%s(%s): re-killing old instance '
							'softly with TERM signal and waiting a little '
							'more.' % (self.name, self.pid))

						os.kill(old_pid, signal.SIGTERM)
						time.sleep(0.2)
						counter += 2
						not_yet_displayed_one = False

					elif counter >= 50 and not_yet_displayed_two:
						logging.notice('%s(%s): old instance won\'t '
							'terminate after 8 seconds. Sending '
							'KILL signal.' % (self.name, self.pid))

						killed = True
						os.kill(old_pid, signal.SIGKILL)
						time.sleep(0.2)
						counter += 2
						not_yet_displayed_two = False

					counter += 1

				logging.notice("%s(%s): old instance %s terminated, we can "
					"play now." % (self.name, self.pid, 'nastily' if killed
						else 'successfully'))
			else:
				logging.notice("%s(%s): daemon already running (pid %s), "
					"not restarting." % (self.name, self.pid, old_pid))
				sys.exit(0)
	def refork_if_not_root_or_die(self):
		""" If the current process is not UID(0), try to refork as root. If
			this fails, exit with an error. """
		if os.getuid() != 0 or os.geteuid() != 0:
			try:
				process.refork_as_root_or_die('licorn-daemon')
			except exceptions.LicornRuntimeException, e:
				logging.error("%s(%s): must be run as %s (was: %s)." % (
					self.name, self.pid, stylize(ST_NAME, 'root'), e))
	def clean_before_terminating(self):
		""" stop threads and clear pid files. """

		#~ logging.progress("%s(%s): emptying queues." % (self.name, self.pid))
		#~ for (qname, queue) in self.queues.iteritems():
			#~ if queue.qsize() > 0:
				#~ assert ltrace('daemon', 'emptying queue %s (%d items left).' % (qname,
					#~ queue.qsize()))
#~
				#~ # manually empty the queue by munging all remaining items.
				#~ try:
					#~ obj = queue.get(False)
					#~ queue.task_done()
					#~ while obj:
						#~ obj = queue.get(False)
						#~ queue.task_done()
					#~ # be sure to reput a None object in the queue, to stop the last
					#~ # threads of the pool, waiting for the None we have munged here.
					#~ queue.put(None)
				#~ except Empty:
					#~ pass

		self.__stop_threads()

		logging.progress("%s(%s): joining queues." % (self.name, self.pid))
		for (qname, queue) in self.queues.iteritems():
			assert ltrace('daemon', 'joining queue %s (%d items left).' % (qname,
				queue.qsize()))
			queue.join()

		logging.progress("%s(%s): joining threads." % (self.name, self.pid))

		for (thname, th) in self.threads.items():
			# join threads in the reverse order they were started, and only the not
			# daemonized ones, in case daemons are stuck on blocking socket or
			# anything preventing a quick and gracefull stop.
			if th.daemon:
				assert ltrace('thread', 'skipping daemon thread %s.' % thname)
				pass
			else:
				assert ltrace('thread', 'joining %s.' % thname)
				if th.is_alive():
					assert ltrace('thread',
						"re-stopping thread %s (shouldn't happen)." % thname)
					logging.warning2('%s(%s): thread %s still alive.' % (
												self.name, self.pid, th.name))
					th.stop()
					time.sleep(0.05)
				th.join()
				del th
				del self.threads[thname]

		# display the remaining active threads (presumably stuck hanging on
		# something very blocking).
		assert ltrace('thread', 'after joining all, %s remaining: %s' % (
			_thcount(), _threads()))

		if LMC.configuration:
			LMC.configuration.CleanUp()

		self.unlink_pid_file()
	def unlink_pid_file(self):
		""" remove the pid file and bork if any error. """

		try:
			if os.path.exists(self.pid_file):
				os.unlink(self.pid_file)
		except (OSError, IOError), e:
			logging.warning("%s(%s): can't remove %s (was: %s)." % (self.name,
				self.pid, stylize(ST_PATH, self.pid_file), e))
	def uptime(self):
		return ' (up %s)' % stylize(ST_COMMENT,
				pyutils.format_time_delta(time.time() - dstart_time))
	def terminate(self, signum=None, frame=None):
		""" Close threads, wipe pid files, clean everything before closing. """

		if signum is None:
			logging.progress("%s(%s): cleaning up and stopping threads…" % \
				(self.name, self.pid))
		else:
			logging.notice('%s(%s): signal %s received, shutting down…' % (
				self.name, self.pid, signum))

		self.clean_before_terminating()

		logging.notice("%s(%s): exiting%s." % (
										self.name, self.pid, self.uptime()))
		sys.exit(0)
	quit = terminate
	def restart(self, signum=None, frame=None):
		logging.notice('%s(%s): SIGUSR1 received, restarting%s.' % (
										self.name, self.pid, self.uptime()))

		self.clean_before_terminating()

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

		# XXX: awful tricking for execvp but i'm tired of this.
		os.execvp(cmd[1], [cmd[0]] + cmd[2:])
	reboot = restart
	def reload(self):
		return "reload not implemented yet"

daemon = LicornDaemon()

if __name__ == '__main__':
	daemon.run()
