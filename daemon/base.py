# -*- coding: utf-8 -*-
"""
Licorn Daemon base - http://docs.licorn.org/daemon/index.html

:copyright: 2009-2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import sys, os, signal, time, re, errno, atexit

#def exitfunc():
#	print '>> EXIT'
#	pass
#atexit.register(exitfunc)

#if __debug__:
#	import pycallgraph; pycallgraph.start_trace()

from threading import current_thread, Event
from optparse  import OptionParser, SUPPRESS_HELP

from licorn.foundations           import options, settings, logging, exceptions
from licorn.foundations           import process, pyutils, ttyutils, styles
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import NamedObject, MixedDictObject, EnumDict, Singleton
from licorn.foundations.threads   import _threads, _thcount
from licorn.foundations.constants import verbose, roles, priorities

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

from licorn.core import LMC, version

class LicornThreads(Singleton, MixedDictObject):
	pass
class LicornQueues(Singleton, MixedDictObject):
	pass

class LicornDaemonInteractor(ttyutils.LicornInteractor):
	""" The daemon interactor, used to interact with console user when
		:program:`licornd` is launched with `-D`. """
	def __init__(self, daemon, wmi=False):

		assert ltrace_func(TRACE_INTERACTOR)

		super(LicornDaemonInteractor, self).__init__('interactor')

		self.long_output   = False
		self.daemon        = daemon
		self.terminate     = self.daemon.terminate
		self.pname         = daemon.name

		if wmi:
			self.handled_chars = {
				'f'   : self.toggle_long_output,
				'l'   : self.toggle_long_output,
				't'   : self.show_threads,
				'v'   : self.raise_verbose_level,
				'q'   : self.lower_verbose_level,
				'' : self.send_sigusr1_signal,	# ^R (refresh / reload)
				}
		else:
			self.handled_chars = {
				'f'   : self.toggle_long_output,
				'l'   : self.toggle_long_output,
				'c'   : self.garbage_collection,
				'w'   : self.show_watches,
				't'   : self.show_threads,
				'v'   : self.raise_verbose_level,
				'q'   : self.lower_verbose_level,
				'' : self.send_sigusr1_signal,	# ^R (refresh / reload)
				'' : self.dump_daemon_status,	# ^T (display status; idea from BSD, ZSH)
				' '   : self.clear_then_dump_status,
				''  : self.clear_then_dump_status, # ^Y (display status after clearing the screen
				}
		self.avoid_help = (' ', )
	def toggle_long_output(self):
		self.long_output = not self.long_output

		logging.notice(_(u'{0}: switched '
			u'long_output status to {1}.').format(
				self.name, _(u'enabled')
					if self.long_output
					else _(u'disabled')))
	toggle_long_output.__doc__ = _(u'toggle [dump status] long ouput on or off')
	def garbage_collection(self):
		sys.stderr.write(_(u'Console-initiated '
			u'garbage collection and dead thread '
			u'cleaning.') + '\n')

		self.daemon.clean_objects()
	garbage_collection.__doc__ = _(u'operate a manual garbage collection in '
									u'the daemon\'s memory, and run other '
									u'clean-related things')
	def show_watches(self):
		w = self.daemon.threads.INotifier._wm.watches

		sys.stderr.write('\n'.join(repr(watch)
			for key, watch in w)
			+ 'total: %d watches\n' % len(w))
	show_watches.__doc__ = _(u'show the INotifier watches (WARNING: this '
							u'can flood your terminal)')
	def show_threads(self):
		sys.stderr.write(_(u'{0} active threads: '
			u'{1}').format(
				_thcount(), _threads()) + '\n')
	show_threads.__doc__ = _(u'show all threads names and their current status')
	def raise_verbose_level(self):
		if options.verbose < verbose.DEBUG:
			options.verbose += 1

			#self.daemon.options.verbose += 1

			logging.notice(_(u'{0}: increased '
				u'verbosity level to '
				u'{1}.').format(self.name,
					stylize(ST_COMMENT,
						verbose[options.verbose])))

		else:
			logging.notice(_(u'{0}: verbosity '
				u'level already at the maximum '
				u'value ({1}).').format(
					self.name, stylize(ST_COMMENT,
						verbose[options.verbose])))
	raise_verbose_level.__doc__ = _(u'increase the daemon console verbosity level')
	def lower_verbose_level(self):
		if options.verbose > verbose.NOTICE:
			options.verbose -= 1

			#self.daemon.options.verbose -= 1

			logging.notice(_(u'{0}: decreased '
				u'verbosity level to '
				u'{1}.').format(self.name,
					stylize(ST_COMMENT,
						verbose[options.verbose])))

		else:
			logging.notice(_(u'{0}: verbosity '
				u'level already at the minimum '
				u'value ({1}).').format(
					self.name, stylize(ST_COMMENT,
						verbose[options.verbose])))
	lower_verbose_level.__doc__ = _(u'decrease the daemon console verbosity level')
	def send_sigusr1_signal(self):
		#sys.stderr.write('\n')
		self.restore_terminal()
		os.kill(os.getpid(), signal.SIGUSR1)
	send_sigusr1_signal.__doc__ = _(u'{0}: Send URS1 signal (and '
									u'consequently reload daemon)').format(
										stylize(ST_OK, 'Control-R'))
	def dump_daemon_status(self):
		sys.stderr.write(self.daemon.dump_status(
							long_output=self.long_output))
	dump_daemon_status.__doc__ = _(u'{0}: dump daemon status').format(
										stylize(ST_OK, 'Control-T'))
	def clear_then_dump_status(self):
		ttyutils.clear_terminal(sys.stderr)
		sys.stderr.write(self.daemon.dump_status(
			long_output=self.long_output))
	clear_then_dump_status.__doc__ = _(u'{0} or {1}: dump daemon status '
										u'after having cleared the '
										u'screen').format(
											stylize(ST_OK, _(u'Space')),
											stylize(ST_OK, 'Control-Y'))
class LicornBaseDaemon:
	""" The licorn daemon base class. The WMI daemon inherits from this class. """
	def __init__(self, dstart_time):
		#NOTE: self.name will be overriten in run()
		self.__name         = self.__class__.dname
		self.pid            = os.getpid()
		self.dstart_time    = dstart_time
		self.stopping_event = Event()
	def __str__(self):
		try:
			return _('{0}({1})').format(stylize(ST_NAME, self.__name), self.pid)

		except AttributeError:
			return '<under construction>'
	@property
	def name(self):
		return self.__name
	def load_settings(self):
		self.__load_factory_settings()
		self.__check_settings()
	def __load_factory_settings(self):

		assert ltrace_func(TRACE_SETTINGS)

		settings.merge_settings({
			# We don't set this in case there is no "eth0" on the system.
			# Default will be '*', which is sane.
			#'licornd.pyro.listen_address': 'if:eth0'

			# ACLChecker will ruin I/O performance if we create too much.
			'licornd.threads.aclcheck.min' : 1,
			'licornd.threads.aclcheck.max' : 10,

			# ServiceWorker is a generic thread, we could need much of them.
			'licornd.threads.service.min'  : 1,
			'licornd.threads.service.max'  : 50,

			# NetWorkWorker is a consuming service, for short operations, we need a lot.
			'licornd.threads.network.min'     : 1,
			'licornd.threads.network.max'     : 100,

			# Wipe dead thread every 10 minutes
			'licornd.threads.wipe_time'       : 600,

			# disabled services.
			#'licornd.syncer.port'             : 3344,
			#'licornd.searcher.port'           : 3355,
			#'licornd.cache_file'              : '/var/cache/licorn/licornd.db',
			#'licornd.socket_path'             : '/var/run/licornd.sock',

			'licornd.buffer_size'             : 16*1024,
			'licornd.log_file'                : '/var/log/licornd.log',
			'licornd.pid_file'                : '/var/run/licornd.pid',

			# the inotifier on users/groups is enabled by default
			'licornd.inotifier.enabled'       : True,

			# We scan the LANs connected to each network interface
			'licornd.network.lan_scan'        : True,

			# But we don't scan a LAN if it has a public IP address,
			# e.g if if is not a private LAN (10.*.*.*, 172.16.*.*, 192.168.*.*)
			'licornd.network.lan_scan_public' : False,

			# ==================================================== WMI settings
			'licornd.wmi.enabled'          : True,
			'licornd.wmi.group'            : 'licorn-wmi',

			# WMI listens on all interfaces by default (empty == *)
			'licornd.wmi.listen_address'   : '',
			'licornd.wmi.port'             : 3356,
			'licornd.wmi.log_file'         : '/var/log/licornd-wmi.log',
			'licornd.wmi.pid_file'         : '/var/run/licornd-wmi.pid',
			'licornd.wmi.ssl_cert'         : '/etc/ssl/certs/licornd-wmi.crt',
			'licornd.wmi.ssl_key'          : '/etc/ssl/private/licornd-wmi.key',
		}, overwrite=False, emit_event=False)
	def __check_settings(self):

		assert ltrace_func(TRACE_SETTINGS)

		self.__convert_settings_values()
		self.__check_settings_daemon_role()
		self.__check_settings_daemon_threads()
		self.__check_settings_daemon_address()
	def __convert_settings_values(self):

		assert ltrace_func(TRACE_SETTINGS)

		if settings.role not in roles:
			# use upper() to avoid bothering user if he has typed "server"
			# instead of "SERVER". Just be cool when possible.
			if hasattr(roles, settings.role.upper()):
				settings.role = getattr(roles, settings.role.upper())
	def __check_settings_daemon_address(self):

		assert ltrace_func(TRACE_SETTINGS)

		if hasattr(settings.licornd, 'pyro'):
			if hasattr(settings.licornd.pyro, 'listen_address'):
				if settings.licornd.pyro.listen_address[:3] == 'if:' \
					or settings.licornd.pyro.listen_address[:6] == 'iface:':
						try:
							settings.licornd.pyro.listen_address = \
								network.interface_address(
									settings.licornd.pyro.listen_address.split(':')[1])
						except (IOError, OSError), e:
							raise exceptions.BadConfigurationError(_(u'Problem '
								u'getting interface %s address (was: %s).') % (
								settings.licornd.pyro.listen_address.split(':')[1], e))
				else:
					try:
						# validate the IP address
						socket.inet_aton(settings.licornd.pyro.listen_address)
					except socket.error:
						try:
							socket.gethostbyname(settings.licornd.pyro.listen_address)
							# keep the hostname, it resolves.
						except socket.gaierror:
							raise exceptions.BadConfigurationError(_(u'Bad IP '
								u'address or hostname %s. Please check syntax.') %
								settings.licornd.pyro.listen_address)
				# TODO: check if the IP or the hostname is really on the local host.
				# check if settings.licornd.pyro.listen_address \
				# in [ network.interface_address(x) for x in network.list_interfaces() ]
	def __check_settings_daemon_role(self):
		""" Some roles imply other directives default values. """

		assert ltrace_func(TRACE_SETTINGS)

		if settings.role == roles.CLIENT:
			settings.licornd.inotifier.enabled   = False
			settings.licornd.network.lan_scan    = False
			settings.licornd.wmi.enabled         = False
	def __check_settings_daemon_threads(self):
		""" check the pingers number for correctness. """

		assert ltrace_func(TRACE_SETTINGS)

		err_message = ''

		for directive, vmin, vmax, directive_name in (
				(settings.licornd.threads.aclcheck.min, 1,   5,
									'licornd.threads.aclcheck.min'),
				(settings.licornd.threads.aclcheck.max, 1,   10,
									'licornd.threads.aclcheck.max'),
				(settings.licornd.threads.service.min,  1,   25,
									'licornd.threads.service.min'),
				(settings.licornd.threads.service.max,  25,  100,
									'licornd.threads.service.max'),
				(settings.licornd.threads.network.min,  1,   50,
									'licornd.threads.network.min'),
				(settings.licornd.threads.network.max,  50,  200,
									'licornd.threads.network.max')
				):
			if directive < vmin or directive > vmax:
				err_message += ('\n\tinvalid value %s for configuration '
					'directive %s: must be an integer between '
					'%s and %s.' % (stylize(ST_BAD, directive),
						stylize(ST_COMMENT, directive_name),
						stylize(ST_COMMENT, vmin), stylize(ST_COMMENT, vmax)))

		if err_message:
			raise exceptions.BadConfigurationError(err_message)
	def execvp(self, cmd, raise_exc=False):
		""" Wraps os.execvp() with bells-and-whistles features. """

		os.closerange(3, 32)

		try:
			try:
				logging.progress(_(u'{0}: execvp({1})').format(self,
										u' '.join([cmd[0]] + cmd[2:])))

				# XXX: awful tricking for `execvp()` but i'm tired of
				# trying to find a way to do this cleaner.
				os.execvp(cmd[1], [cmd[0]] + cmd[2:])

			except (OSError, IOError), e:
				logging.exception(_(u'transient process {0}: cannot execvp() {1}.'),
									os.getpid(), (ST_ATTR, u' '.join(cmd)))
				if raise_exc:
					raise
		finally:
			# Exiting here is wise. exec() is so often used after a
			# fork that failing and thus continuing to run the forked
			# process could be harmfull.
			from threading import current_thread

			if current_thread().name == 'MainThread':
				# this is the documented way of doing things.
				# cf. http://docs.python.org/library/sys.html#sys.exit
				# and http://docs.python.org/library/os.html#os._exit
				sys.exit(91)

			else:
				# This won't work. Can't kill myself.
				#os.kill(os.getpid(), signal.SIGKILL)
				#
				# When licornd forks the WMI, this doesn't suffice
				# to exit completely (the process will stay zombie).
				# Hoppefully licornd will notice it
				# and will kill us one more time.
				os._exit(91)
	def setup_signals_handler(self):
		""" Redirect termination signals (`TERM`, `HUP`, `INT`) to the
			:meth:`terminate` method.

			Redirect restart signals (`USR1`, `USR2`) to the
			:meth:`restart` method. `USR2` is connected only if the current
			instance has a :meth:`USR2_signal_handler` method. Just define
			it if you want the signal to be catched.
		"""

		assert ltrace_func(TRACE_DAEMON)

		#signal.signal(signal.SIGCHLD, signal.SIG_IGN)
		signal.signal(signal.SIGTERM, self.terminate)
		signal.signal(signal.SIGHUP,  self.terminate)
		signal.signal(signal.SIGINT,  self.terminate)
		signal.signal(signal.SIGUSR1, self.restart)

		if hasattr(self, 'USR2_signal_handler'):
			signal.signal(signal.SIGUSR2, self.USR2_signal_handler)
	def check_aborted_daemon(self, exclude):
		""" In some cases (unhandled internal crash, failed termination, stopped
			job, whatever), one or more dead daemons could still exist, occupying
			(or not) the pyro port, without a valid PID file.

			Find'em and kill'em all, callaghan.

			.. todo:: merge this method with :func:`~licorn.foundations.process.pidof`,
				they share the same for-loop.

			.. versionadded:: 1.2.5
		"""

		assert ltrace_func(TRACE_DAEMON)

		assert ltrace(TRACE_DAEMON, '> my_pid=%s' % self.pid)

		# exclude ourselves from the search, and our parent, too. If we are in
		# refork_as_root() phase, the parent pid still exists for a moment. On
		# Ubuntu Lucid / Maverick, we didn't encounter any problem not having
		# the parent pid here (which was probably only because of luck!), but
		# on Natty, we die after every launch, by killing our parent. Hopefully
		# this is fixed now, and this will fix random "kill: 95: no such
		# process" errors encountered on Maverick and previous releases.
		exclude.extend((self.pid, os.getppid()))

		try:
			# linux 3.x only
			my_process_name = open('/proc/{0}/comm'.format(self.pid)).read().strip()

		except:
			# the standard good'ol' way of finding my process name
			my_process_name = sys.argv[0]

		# About names: sudo re-executed processes are `sudo` in /proc/.../comm,
		# but we name name them `licorn-daemon` in the exec() phase. We must look
		# to them prior to our own name, because when sudo gets hung, the licorn
		# process seems completely stalled and doesn't respond even to SIGKILL.
		my_process_names = [ self.dname, my_process_name, my_process_name.replace('/', '-')]

		for entry in os.listdir('/proc'):
			if entry.isdigit():
				if int(entry) in exclude:
					continue

				try:
					try:
						# linux 3.x only
						command_line1 = open('/proc/{0}/comm'.format(entry)).read().strip()

					except:
						command_line1 = ''

					command_line2 = open('/proc/{0}/cmdline'.format(entry)).read().strip()

					for pname in my_process_names:
						if pname == command_line1 or pname+'\0' in command_line2:
							os.kill(int(entry), signal.SIGKILL)

							time.sleep(0.2)
							logging.notice(_(u'{0:s}: killed aborted '
								u'instance @pid {1}.').format(self, entry))

				except (IOError, OSError), e:
					# in rare cases, the process vanishes during the kill
					# ESRCH == "no such process"
					# and in some other rare cases, it can vanish during the search.
					if e.errno not in (errno.ENOENT, errno.ESRCH):
						logging.exception('{0}: ignored exception in check_aborted_daemon()', self)
						continue
	def parse_arguments(self):
		""" Integrated help and options / arguments for licornd. """

		from licorn.foundations.argparser import (
				build_version_string,
				common_behaviour_group
			)

		app = {
			u'name' : u'licornd',
			u'description' : u'Licorn® Daemon:\n'
				u'	Global system and service manager,\n'
				u'	Command Line Interface proxy,\n'
				u'	Network scanner and updater,\n'
				u'	Posix1e ACL auto checker with inotify support,\n'
				u'	Web Management Interface HTTP server,\n'
				u'	File meta-data crawler.',
			u'author' : u'Olivier Cortès <olive@deep-ocean.net>'
		}

		usage_text = '''
		%s [-D|--no-daemon] ''' \
			'''[-W|--wmi-listen-address <IP_or_hostname|iface:…>] ''' \
			'''[-p|--pid-to-wake1 <PID>] ''' \
			'''[…]''' \
			% (stylize(ST_APPNAME, "%prog"))

		parser = OptionParser(
			usage=usage_text,
			version=build_version_string(app, version)
			)

		parser.add_option("-D", "--no-daemon",
			action="store_false", dest="daemon", default=True,
			help=_(u"Don't fork as a daemon, stay on the current terminal instead."
				u" Logs will be printed on standard output "
				u"instead of beiing written into the logfile."))

		parser.add_option('-r', '--replace', '--restart',
			action='store_true', dest='replace', default=False,
			help=_(u'Replace an existing daemon instance. A comfort flag to avoid'
				u'killing an existing daemon before relaunching a new one.'))

		parser.add_option('-k', '--kill', '--shutdown',
			action="store_true", dest='shutdown', default=False,
			help=_(u'Shutdown any currently running Licorn® daemon. We will try '
				u'to terminate them nicely, before beiing more agressive after '
				u'a given period of time.'))

		parser.add_option("-w", "--wmi-listen-address",
			action="store", dest="wmi_listen_address", default=None,
			help=_(u'Specify an IP address or a hostname to bind to. Only {0} can '
				u'be specified (the WMI cannot yet bind on multiple interfaces '
				u'at the same time). This option takes precedence over the '
				u'configuration directive, if present in {1}.').format(
				stylize(ST_IMPORTANT, 'ONE address or hostname'),
				stylize(ST_PATH, settings.main_config_file)))

		parser.add_option("-W", "--no-wmi",
			action="store_false", dest="wmi_enabled", default=True,
			help=_(u"Don't fork the WMI. This flag overrides the setting in %s.") %
				stylize(ST_PATH, settings.main_config_file))

		parser.add_option("-p", "--wake-pid1", "--pid-to-wake1",
			action="store", type="int", dest="pid_to_wake1", default=None,
			help=SUPPRESS_HELP)

		parser.add_option("-P", "--wake-pids2", "--pids-to-wake2",
			action="store", type="string", dest="pids_to_wake2", default=None,
			help=SUPPRESS_HELP)

		parser.add_option("-B", "--no-boot-check",
			action="store_true", dest="no_boot_check", default=False,
			help=_(u"Don't run the initial check on all shared directories. This "
				u"makes daemon be ready faster to answer users legitimate "
				u"requests, at the cost of consistency of shared data. {0}: don't"
				u" use this flag at server boot in init scripts. Only on daemon "
				u"relaunch, on an already running system, for testing or "
				u"debugging purposes.").format(stylize(ST_IMPORTANT,
				'EXTREME CAUTION')))

		parser.add_option_group(common_behaviour_group(app, parser, 'licornd'))

		opts, args = parser.parse_args()

		if hasattr(opts, 'replace_all') and opts.replace_all:
			opts.replace = True

		return opts, args
	def clean_sys_argv(self, for_slaves=False):
		""" Remove from current command-line arguments the one that we can't keep
			when the current process needs to restart, most notably `--wake-pid1``,
			``--wake-pid2`` and all their variants. """

		args = []

		found1 = False
		for arg in sys.argv[:]:
			if arg in ('-p', '-P',
					'--wake-pid1', '--wake-pid2',
					'--pid-to-wake1', '--pid-to-wake2',
					'--pids-to-wake1', '--pids-to-wake2'):
				found1 = True
				# implicit: continue

			elif found1:
				# skip the current argument (a PID)
				found1 = False
				# implicit: continue

			else:
				args.append(arg)

		if for_slaves:
			for arg in ("-W", "--no-wmi", "-B", "--no-boot-check",):
				try:
					args.remove(arg)

				except ValueError:
					pass

			for args_list, replacement in (
							(('-R', '--replace-all', '--restart-all', ), '-r'),
							(('-K', '--kill-all', '--shutdown-all', ), '-k'),
							(('-D', '--no-daemon'), '')
						):
				for arg in args_list:
					try:
						args[args.index(arg)] = replacement

					except ValueError:
						pass

		return args
	def replace_or_shutdown(self):
		""" See if another daemon process if already running. If it is and we're not
			asked to replace it, exit. Else, try to kill it and start. It the
			process won't die after a certain period of time (10 seconds), alert the
			user and exit.
		"""

		assert ltrace_func(TRACE_DAEMON)

		exclude = []

		if os.path.exists(self.pid_file):
			old_pid = int(open(self.pid_file).read().strip())
			exclude.append(old_pid)

		self.check_aborted_daemon(exclude)

		if process.already_running(self.pid_file):
			if self.opts.replace or self.opts.shutdown:
				logging.notice(_(u'{0:s}: trying to {1} existing instance '
					u'@pid {2}.').format(self, _(u'replace')
						if self.opts.replace else _(u'shutdown'), old_pid))

				# kill the existing instance, gently
				os.kill(old_pid, signal.SIGTERM)

				counter = 0

				while os.path.exists(self.pid_file):
					time.sleep(0.1)

					if counter >= 25:
						logging.notice(_(u'{0:s}: existing instance still '
							u'running, we\'re going to be more incisive in '
							u'a few seconds.').format(self))
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
				not_yet_displayed_one   = True
				not_yet_displayed_two   = True
				not_yet_displayed_three = True
				killed  = False
				while os.path.exists(proc_pid):
					time.sleep(0.1)

					if counter >= 25 and not_yet_displayed_one:
						logging.notice(_(u'{0:s}: re-killing old instance '
							u'softly with TERM signal and waiting a little '
							u'more.').format(self))

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
						logging.notice(_(u'{0:s}: old instance has not '
							u'terminated after 8 seconds. Sending '
							u'KILL signal.').format(self))

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

					elif counter >= 60 and not_yet_displayed_three:
						# on ubuntu Natty, sudo doesn't work as on older systems.
						# it stays in the process list, instead of exec'ing the
						# wanted program on top of itself. Thus, Control-Z
						# stops it instead of stopping licornd. Thus, trying to
						# kill the child has no effect at all. We must find the
						# parent and kill it instead.
						parent_pid = int(re.findall('PPid:\t(.*)',
								open('/proc/%s/status' % old_pid).read())[0])

						if 'sudo' in open('/proc/%s/cmdline' % parent_pid).read():
							logging.notice(_(u'{0:s}: killing old instance\'s '
								u'father (sudo, pid %s) without any '
								u'mercy.').format(self, parent_pid))

							killed = True
							try:
								os.kill(parent_pid, signal.SIGKILL)

							except (OSError, IOError), e:
								if e.errno != 3:
									# errno 3 is "no such process": it died in the
									# meantime. Don't crash for this.
									raise
							time.sleep(0.2)
							counter += 2

						else:
							logging.warning(_(u'{0:s}: old instance has not '
								u'terminated after 9 seconds and cannot '
								u'be killed. We will not try to kill any other '
								u'parent than "{1}", you are in a non-trivial '
								u'situation. Up to you to solve it.').format(
									self, stylize(ST_NAME, 'sudo')))
							sys.exit(-10)

						not_yet_displayed_three = False

					elif counter >=120:
						logging.warning(_(u'{0:s}: old instance has not '
							u'terminated after 15 seconds and cannot '
							u'be killed directly or by killing its direct '
							u'parent, bailing out. You are in trouble '
							u'on a system where "kill -9" does not work '
							u'as advertised. Sorry for you.').format(self))
						sys.exit(-9)

					counter += 1

				logging.notice(_(u'{0:s}: old instance {1} terminated{2}').format(
						self, _(u'nastily') if killed else _(u'successfully'),
						_(u', we can play now.')
									if self.opts.replace else '.'))

			else:
				logging.notice(_(u'{0:s}: daemon already running (pid {1}), '
					u'not restarting.').format(self, old_pid))
				sys.exit(5)
	def refork_if_not_root_or_die(self):
		""" If the current process is not UID(0), try to refork as root. If
			this fails, exit with an error. """

		assert ltrace_func(TRACE_DAEMON)

		if os.getuid() != 0 or os.geteuid() != 0:
			try:
				process.refork_as_root_or_die(self.dname)

			except exceptions.LicornRuntimeException, e:
				logging.error(_(u'{0:s}: must be run as {1} '
								u'(was: {2}).').format(self,
								stylize(ST_NAME, 'root'), e))
	def unlink_pid_file(self):
		""" Remove the PID file, and output any error. """

		try:
			if os.path.exists(self.pid_file):
				logging.progress(_(u'{0:s}: unlinking PID file {1}.').format(
										self, stylize(ST_PATH, self.pid_file)))
				os.unlink(self.pid_file)

		except (OSError, IOError), e:
			if e.errno != errno.ENOENT:
				logging.exception(_(u'{0:s}: cannot unlink {1}.').format(
									self, stylize(ST_PATH, self.pid_file)))
	def uptime(self):

		assert ltrace_func(TRACE_DAEMON)

		return _(u' (up {0})').format(stylize(ST_COMMENT,
				pyutils.format_time_delta(time.time() - self.dstart_time)))
	def terminate(self, signum=None, frame=None):
		""" Close threads, wipe pid files, clean everything before closing. """

		if self.stopping_event.is_set():
			if signum is None:
				logging.warning2(_(u'{0:s}: already stopping, ignored '
								u'another terminate() call.').format(self))
			else:
				logging.warning2(_(u'{0:s}: already stopping, ignored '
								u'signal {1}.').format(self, signum))
			return

		self.stopping_event.set()

		assert ltrace(TRACE_DAEMON, '| terminate({0}, {1})', signum, frame)

		if signum is None:
			logging.progress(_(u'{0:s}: cleaning up and stopping threads…').format(self))

		else:
			logging.notice(_(u'{0:s}: signal {1} received, '
							u'shutting down…').format(self, signum))

		if hasattr(self, 'daemon_shutdown'):
			self.daemon_shutdown()

		# NOTE: don't close file descriptors ourselfves, this would crash
		# the WMI twisted reactor badly. Pyro should do it cleanly too, if we
		# want to reuse the socket quickly.
		#
		#os.closerange(3, 32)

		self.unlink_pid_file()

		logging.notice(_(u'{0:s}: exiting{1}.').format(self, self.uptime()))

		print '>>', _threads()
		#if __debug__:
		#	pycallgraph.make_dot_graph('/home/%s.svg' % self.name, format='svg')

		# This is not needed if the application / daemon is coded correctly.
		# Additionnaly, it will crash the twisted reactor.
		#sys.exit(0)
	def restart(self, signum=None, frame=None):

		try:
			LicornEvent('daemon_is_restarting').emit(priorities.HIGH)

		except (NameError, TypeError, AttributeError):
			# the call will fail in any other daemon than the main licornd,
			# because only this daemon has an event manager and this builtin
			# function name.
			pass

		assert ltrace(TRACE_DAEMON, '| restart(signum={0}, frame={1})',
			(ST_UGID, signum), frame)

		if signum:
			logging.notice(_(u'{0:s}: SIGUSR1 received, preparing our '
												u'restart.').format(self))
		else:
			logging.notice(_(u'{0:s}: restart needed, shutting '
										u'everything down.').format(self))

		if hasattr(self, 'daemon_shutdown'):
			self.daemon_shutdown()

		# close every file descriptor (except stdin/out/err, used for logging and
		# on the console). This is needed for Pyro thread to release its socket,
		# else it's done too late and on restart the port can't be rebinded on.
		os.closerange(3, 32)

		# unlink the pid_file, else the new exec'ed process will try to kill
		# itself in the check_or_replace() method.
		self.unlink_pid_file()

		self.restart_command()
