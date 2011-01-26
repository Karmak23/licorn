# -*- coding: utf-8 -*-
"""
Licorn Daemon - http://docs.licorn.org/daemon/index.html

:copyright: 2009-2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import sys, os, select, code, readline, curses
import signal, termios
from threading import current_thread

from rlcompleter import Completer
from licorn.foundations           import options, logging, exceptions
from licorn.foundations           import process, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace, insert_ltrace, dump, fulldump
from licorn.foundations.base      import NamedObject, MixedDictObject, EnumDict, Singleton
from licorn.foundations.thread    import _threads, _thcount

class LicornThreads(MixedDictObject, Singleton):
	pass
class LicornQueues(MixedDictObject, Singleton):
	pass

roles = EnumDict('licornd_roles', from_dict={
		'UNSET':  1,
		'SERVER': 2,
		'CLIENT': 3
	})

priorities = EnumDict('service_priorities', from_dict={
		'LOW':  20,
		'NORMAL': 10,
		'HIGH': 0
	})

def daemon_thread(klass, target, args=(), kwargs={}):
	""" TODO: turn this into a decorator, I think it makes a good candidate. """
	from licorn.daemon.main import daemon
	thread = klass(target, args, kwargs)
	daemon.threads[thread.name] = thread
	return thread

def service_enqueue(prio, func, *args, **kwargs):
	from licorn.daemon.main import daemon
	#print '>> put', prio, func, args, kwargs
	daemon.queues.serviceQ.put((prio, func, args, kwargs))

def service_wait():
	from licorn.daemon.threads import ServiceWorkerThread
	if isinstance(current_thread(), ServiceWorkerThread):
		raise RuntimeError('cannot join the serviceQ from '
			'a ServiceWorkerThread instance, this would deadblock!')
	from licorn.daemon.main import daemon
	#print ">> waiting for", daemon.queues.serviceQ.qsize(), 'jobs to finish'
	daemon.queues.serviceQ.join()

def network_enqueue(prio, func, *args, **kwargs):
	from licorn.daemon.main import daemon
	#print '>> put', prio, func, args, kwargs
	daemon.queues.networkQ.put((prio, func, args, kwargs))

def network_wait():
	from licorn.daemon.threads import NetworkWorkerThread
	if isinstance(current_thread(), NetworkWorkerThread):
		raise RuntimeError('cannot join the networkQ from '
			'a NetworkWorkerThread instance, this would deadblock!')
	from licorn.daemon.main import daemon
	daemon.queues.networkQ.join()

def aclcheck_enqueue(prio, func, *args, **kwargs):
	from licorn.daemon.main import daemon
	#print '>> put', prio, func, args, kwargs
	daemon.queues.aclcheckQ.put((prio, func, args, kwargs))

def aclcheck_wait():
	from licorn.daemon.threads import ACLCkeckerThread
	if isinstance(current_thread(), ACLCkeckerThread):
		raise RuntimeError('cannot join the ackcheckerQ from '
			'a ACLCkeckerThread instance, this would deadblock!')
	from licorn.daemon.main import daemon
	daemon.queues.aclcheckQ.join()


# LicornDaemonInteractor is an object dedicated to user interaction when the
# daemon is started in the foreground.
class LicornDaemonInteractor(NamedObject):
	class HistoryConsole(code.InteractiveConsole):
		def __init__(self, locals=None, filename="<licornd_console>",
			histfile=os.path.expanduser('~/.licorn/licornd_history')):
			assert ltrace('interactor', '| HistoryConsole.__init__()')
			code.InteractiveConsole.__init__(self, locals, filename)
			self.histfile = histfile

		def init_history(self):
			assert ltrace('interactor', '| HistoryConsole.init_history()')
			readline.set_completer(Completer(namespace=self.locals).complete)
			readline.parse_and_bind("tab: complete")
			if hasattr(readline, "read_history_file"):
				try:
					readline.read_history_file(self.histfile)
				except IOError:
					pass
		def save_history(self):
			assert ltrace('interactor', '| HistoryConsole.save_history()')
			readline.write_history_file(self.histfile)

	def __init__(self, daemon):
		assert ltrace('interactor', '| LicornDaemonInteractor.__init__()')
		NamedObject.__init__(self, 'interactor')
		self.long_output = False
		self.daemon      = daemon
		self.pname       = daemon.name
		# make it daemon so that it doesn't block the master when stopping.
		#self.daemon = True
	def prepare_terminal(self):
		assert ltrace(self.name, '| prepare_terminal()')
		termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new)
	def restore_terminal(self):
		assert ltrace(self.name, '| restore_terminal()')
		termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
	def run(self):
		""" prepare stdin for interaction and wait for chars. """
		if sys.stdin.isatty():
			assert ltrace(self.name, '> run()')

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
				self.prepare_terminal()

				while True:
					try:
						readf, writef, errf = select.select([self.fd], [], [])
						if readf == []:
							continue
						else:
							char = sys.stdin.read(1)

					except select.error, e:
						if e.args[0] == 4:
							sys.stderr.write("^C\n")
							self.restore_terminal()
							self.daemon.terminate(2)
						else:
							raise e

					else:
						# control characters from
						# http://www.unix-manuals.com/refs/misc/ascii-table.html
						if char == '\n':
							sys.stderr.write('\n')

						elif char in ('f', 'F', 'l', 'L'):

							self.long_output = not self.long_output
							logging.notice('%s: switched long_output status '
								'to %s.' % (self.name, self.long_output))

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
								self.name)

							self.restore_terminal()
							os.kill(os.getpid(), signal.SIGKILL)

						elif char == '':
							sys.stderr.write(self.daemon.dump_status(
								long_output=self.long_output))

						elif char in (' ', ''): # ^Y
							sys.stdout.write(clear)
							sys.stdout.flush()
							sys.stderr.write(self.daemon.dump_status(
								long_output=self.long_output))
						elif char in ('i', 'I'):
							logging.notice('%s: ntering interactive mode. '
								'Welcome into licornd\'s arcanes…' % self.name)

							# trap SIGINT to avoid shutting down the daemon by
							# mistake. Now Control-C is used to reset the
							# current line in the interactor.
							def interruption(x,y):
								raise KeyboardInterrupt
							signal.signal(signal.SIGINT, interruption)

							from licorn.core import version, LMC

							# NOTE: we intentionnaly restrict the interpreter
							# environment, else it
							interpreter = self.__class__.HistoryConsole(
								locals={
									'version'       : version,
									'daemon'        : self.daemon,
									'queues'        : self.daemon.queues,
									'threads'       : self.daemon.threads,
									'uptime'        : self.daemon.uptime,
									'LMC'           : LMC,
									'dump'          : dump,
									'fulldump'      : fulldump,
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
							logging.notice('%s: leaving interactive mode. '
								'Welcome back to Real World™.' % self.name)

							# restore signal and terminal handling
							signal.signal(signal.SIGINT,
								lambda x,y: self.daemon.terminate)

							# take the TTY back into command mode.
							self.prepare_terminal()

						else:
							logging.warning2(
								"%s: received unhandled char '%s', ignoring."
								% (self.name, char))
			finally:
				# put it back in standard mode after input, whatever
				# happened. The terminal has to be restored.
				self.restore_terminal()

		# else:
		# stdin is not a tty, we are in the daemon, don't do anything.
		assert ltrace(self.name, '< run()')

