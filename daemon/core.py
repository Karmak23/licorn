# -*- coding: utf-8 -*-
"""
Licorn Daemon core - http://docs.licorn.org/daemon/core.html

:copyright: 2007-2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, sys, time, signal, select, curses, termios, resource, code, readline
from rlcompleter import Completer
from optparse    import OptionParser

from licorn.foundations           import options, logging, process, exceptions
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace, dump, fulldump
from licorn.foundations.pyutils   import format_time_delta
from licorn.foundations.base      import NamedObject
from licorn.foundations.thread    import _threads, _thcount
from licorn.foundations.argparser import build_version_string, \
											common_behaviour_group

from licorn.core           import version, LMC
from licorn.daemon         import dname, dthreads, dqueues, dchildren, \
	dstart_time, uptime, terminate
from licorn.daemon.threads import LicornPoolJobThread

def get_daemon_status(long_output=False, precision=None):
	""" GET daemon status (all threads). """

	assert ltrace('daemon', '| get_daemon_status(%s, %s)' % (
		long_output, precision))

	# if not is_localhost(client) and not is_server_peer(client):
	# logging.warning('unauthorized call from %s!' % client)
	#	return

	rusage = resource.getrusage(resource.RUSAGE_SELF)
	pagesize = resource.getpagesize()

	data = ('-- Licorn® daemon %sstatus: '
		'up %s, %s threads, %s controllers, %s queues, %s locks\n'
		'CPU: usr %.3fs, sys %.3fs MEM: res %.2fMb shr %.2fMb ush %.2fMb stk %.2fMb\n' % (
		stylize(ST_COMMENT, 'full ') if long_output else '',
		stylize(ST_COMMENT, format_time_delta(time.time()-dstart_time)),
		_thcount(), stylize(ST_UGID, len(LMC)),
		stylize(ST_UGID, len(dqueues)), stylize(ST_UGID, len(LMC.locks)),
		rusage.ru_utime, #format_time_delta(int(rusage.ru_utime), long=False),
		rusage.ru_stime, #format_time_delta(int(rusage.ru_stime), long=False),
		float(rusage.ru_maxrss * pagesize) / (1024.0*1024.0),
		float(rusage.ru_ixrss * pagesize) / (1024.0*1024.0),
		float(rusage.ru_idrss * pagesize) / (1024.0*1024.0),
		float(rusage.ru_isrss * pagesize) / (1024.0*1024.0)
		))

	data += ('Queues: %s.\n' %
			', '.join([ '%s(%s)' % (stylize(ST_NAME, qname),
				queue.qsize()) for qname, queue in dqueues.iteritems()]))

	if long_output:
		for controller in LMC:
			if hasattr(controller, 'dump_status'):
				data += 'controller %s\n' % controller.dump_status()
			else:
				data += ('''controller %s%s doesn't implement '''
					'''dump_status().\n''' % (
					stylize(ST_NAME, controller.name),
					'(%s)' % stylize(ST_IMPORTANT, 'locked')
						if controller.is_locked() else ''))

	for thread in dthreads.values():
		if thread.is_alive():
			if long_output or ( not long_output
				and not isinstance(thread, LicornPoolJobThread)):
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
def licornd_parse_arguments(app):
	""" Integrated help and options / arguments for harvestd."""

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

	parser.add_option("-p", "--pid-to-wake",
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
def exit_or_replace_if_already_running(pname, my_pid, replace=False):
	""" See if another daemon process if already running. If it is and we're not
		asked to replace it, exit. Else, try to kill it and start. It the
		process won't die after a certain period of time (10 seconds), alert the
		user and exit. """

	pid_file = LMC.configuration.licornd.pid_file

	try:
		old_pid  = int(open(pid_file).read().strip())
	except (IOError, OSError), e:
		if e.errno != 2:
			raise
		else:
			# PID file doesn't exist, no other daemon is running.
			return

	if process.already_running(pid_file):
		if replace:
			logging.notice('%s(%s): trying to replace existing instance '
				'@pid %s.' % (pname, my_pid, old_pid))

			# kill the existing instance, gently
			os.kill(old_pid, signal.SIGTERM)

			counter = 0

			while os.path.exists(pid_file):
				time.sleep(0.1)

				if counter >= 30:
					# Exit now, this is too much. process should have removed
					# the pid file very earlier, this is the first thing the
					# daemon does before cleaning and killing everything.
					logging.notice("Existing instance still running, "
						"we're going to be a little more incisive in a few "
						"seconds.")
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
			killed  = False
			while os.path.exists(proc_pid):
				time.sleep(0.1)

				# wait a little more,
				# else Pyro & WMI ports will not be available.
				if counter == 20:
					logging.notice('%s(%s): waiting a little more for old '
						'instance to terminate.' % (pname, my_pid))

				elif counter == 60:
					logging.notice("%s(%s): re-killing old instance softly with"
						" TERM signal." % (pname, my_pid))

					os.kill(old_pid, signal.SIGTERM)
					time.sleep(0.2)
					counter += 2

				elif counter == 100:
					logging.notice("%s(%s): old instance won't terminate after "
						"10 seconds. Sending KILL signal." % (pname, my_pid))

					killed = True
					os.kill(old_pid, signal.SIGKILL)
					time.sleep(0.2)
					counter += 2

				counter += 1

			logging.notice("%s(%s): old instance %s terminated, we can "
				"play now." % (pname, my_pid, 'nastily' if killed
					else 'successfully'))
		else:
			logging.notice("%s: already running (pid %s), not restarting." % (
				dname, process.get_pid(LMC.configuration.licornd.pid_file)))
			sys.exit(0)
def refork_if_not_running_root_or_die():
	if os.getuid() != 0 or os.geteuid() != 0:
		try:
			process.refork_as_root_or_die(process_title='licorn-daemon')
		except exceptions.LicornRuntimeException, e:
			logging.error("%s: must be run as %s (was: %s)." % (dname,
				stylize(ST_NAME, 'root'), e))
def eventually_daemonize():
	if options.daemon:
		process.daemonize(LMC.configuration.licornd.log_file,
			LMC.configuration.licornd.pid_file)
	else:
		process.write_pid_file(LMC.configuration.licornd.pid_file)
# LicornDaemonInteractor is an object dedicated to user interaction when the
# daemon is started in the foreground.
class LicornDaemonInteractor(NamedObject):
	class HistoryConsole(code.InteractiveConsole):
		def __init__(self, locals=None, filename="<licornd_console>",
			histfile=os.path.expanduser('~/.licorn/licornd_history')):
			code.InteractiveConsole.__init__(self, locals, filename)
			self.histfile = histfile

		def init_history(self):
			readline.set_completer(Completer(namespace=self.locals).complete)
			readline.parse_and_bind("tab: complete")
			if hasattr(readline, "read_history_file"):
				try:
					readline.read_history_file(self.histfile)
				except IOError:
					pass
		def save_history(self):
			readline.write_history_file(self.histfile)

	def __init__(self, pname):
		NamedObject.__init__(self, 'interactor')
		self.long_output = False
		self.pname       = pname
		# make it daemon so that it doesn't block the master when stopping.
		#self.daemon = True
	def prepare_terminal(self):
		termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new)
	def restore_terminal(self):
		termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
	def run(self):
		""" prepare stdin for interaction and wait for chars. """
		if sys.stdin.isatty():
			assert ltrace('daemon', '> %s.run()' % self.name)

			curses.setupterm()
			clear = curses.tigetstr('clear')

			# see tty and termios modules for implementation details.
			self.fd = sys.stdin.fileno()
			self.old = termios.tcgetattr(self.fd)
			self.new = termios.tcgetattr(self.fd)

			# put the TTY in nearly raw mode to be able to get characters
			# one by one (not to wait for newline to get one).

			# lflags
			self.new[3] = \
				self.new[3] & ~(termios.ECHO|termios.ICANON|termios.IEXTEN)
			self.new[6][termios.VMIN] = 1
			self.new[6][termios.VTIME] = 0

			try:
				while True:
					try:
						self.prepare_terminal()

						readf, writef, errf = select.select(
							[ self.fd ], [], [], 0.1)
						if readf == []:
							continue
						else:
							char = sys.stdin.read(1)

					except KeyboardInterrupt:
						sys.stderr.write("^C\n")
						raise

					else:
						# control characters from
						# http://www.unix-manuals.com/refs/misc/ascii-table.html
						if char == '\n':
							sys.stderr.write('\n')

						elif char in ('m', 'M'):
							"""
							sys.stderr.write('\n'.join(['%s: %s' % (
								x, type(getattr(LMC.machines.machines, x)))
									for x in dir(LMC.machines.machines)
									if str(type(getattr(LMC.machines.machines, x))) == "<type 'weakproxy'>"]) + '\n')
							"""
							sys.stderr.write('\n'.join(['%s: %s' % (
								x, type(getattr(LMC.machines, x)))
									for x in dir(LMC.machines)
									]) + '\n')

						elif char in ('u', 'U'):
							sys.stderr.write('\n'.join(['%s: %s' % (
								x, type(getattr(LMC.users, x)))
									for x in dir(LMC.users)]) + '\n')

						elif char in ('f', 'F', 'l', 'L'):

							self.long_output = not self.long_output
							logging.notice('switched long_output status to %s.'
								% self.long_output)

						elif char in ('t', 'T'):
							sys.stderr.write('%s active threads: %s\n' % (
								_thcount(), _threads()))

						elif char == '\f': # ^L (form-feed, clear screen)
							sys.stdout.write(clear)
							sys.stdout.flush()

						elif char == '': # ^R (refresh / reload)
							#sys.stderr.write('\n')
							self.restore_terminal()
							os.kill(os.getpid(), signal.SIGUSR1)

						elif char == '': # ^U kill -15
							# no need to log anything, process will display
							# 'signal received' messages.
							#logging.warning('%s: killing ourselves softly.' %
							#	self.pname)

							# no need to kill WMI, terminate() will do it clean.
							self.restore_terminal()
							os.kill(os.getpid(), signal.SIGTERM)

						elif char == '\v': # ^K (Kill -9!!)
							logging.warning('%s: killing ourselves badly.' %
								self.pname)

							self.restore_terminal()
							os.kill(os.getpid(), signal.SIGKILL)

						elif char == '':
							sys.stderr.write(get_daemon_status(
								long_output=self.long_output))

						elif char in (' ', ''): # ^Y
							sys.stdout.write(clear)
							sys.stdout.flush()
							sys.stderr.write(get_daemon_status(
								long_output=self.long_output))
						elif char in ('i', 'I'):
							logging.notice('Entering interactive mode. '
								'Welcome into licornd\'s arcanes…')

							# trap SIGINT to avoid shutting down the daemon by
							# mistake. Now Control-C is used to reset the
							# current line in the interactor.
							def interruption(x,y):
								raise KeyboardInterrupt
							signal.signal(signal.SIGINT, interruption)

							# NOTE: we intentionnaly restrict the interpreter
							# environment, else it
							interpreter = self.__class__.HistoryConsole(
								locals={
									'LMC'      : LMC,
									'dqueues'  : dqueues,
									'dthreads' : dthreads,
									'version'  : version,
									'uptime'   : uptime,
									'dump'     : dump,
									'fulldump' : fulldump,
									})

							# put the TTY in standard mode (echo on).
							self.restore_terminal()
							sys.ps1 = 'licornd> '
							sys.ps2 = '...'
							interpreter.init_history()
							interpreter.interact(
								banner="Licorn® %s, Python %s on %s" % (
									version, sys.version.replace('\n', ''),
									sys.platform))
							interpreter.save_history()
							logging.notice('Leaving interactive mode. '
								'Welcome back to Real World™.')

							# restore signal and terminal handling
							signal.signal(signal.SIGINT,
								lambda x,y: terminate(x,y, self.pname))
							self.prepare_terminal()

						else:
							logging.warning2(
								"received unhandled char '%s', ignoring." % char)
			finally:
				# put it back in standard mode after input, whatever
				# happened. The terminal has to be restored.
				self.restore_terminal()

		# else:
		# stdin is not a tty, we are in the daemon, don't do anything.
		assert ltrace('thread', '%s ended' % self.pname)
