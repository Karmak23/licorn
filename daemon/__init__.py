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

import sys, os, select, code, readline, curses, signal, termios

from threading   import current_thread
from rlcompleter import Completer

from licorn.foundations           import options, logging, exceptions
from licorn.foundations           import process, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace, insert_ltrace, dump, fulldump
from licorn.foundations.base      import NamedObject, MixedDictObject, EnumDict, Singleton
from licorn.foundations.thread    import _threads, _thcount
from licorn.foundations.constants import verbose


class LicornThreads(MixedDictObject, Singleton):
	pass
class LicornQueues(MixedDictObject, Singleton):
	pass

class InternalEvent(NamedObject):
	def __init__(self, _event_name, *args, **kwargs):
		NamedObject.__init__(self, _event_name)

		if 'synchronous' in kwargs:
			self.synchronous = kwargs['synchronous']
			del kwargs['synchronous']
		else:
			self.synchronous = False

		if 'callback' in kwargs:
			self.callback = kwargs['callback']
			del kwargs['callback']
		else:
			self.callback = None

		self.args        = args
		self.kwargs      = kwargs

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

# LicornDaemonInteractor is an object dedicated to user interaction when the
# daemon is started in the foreground.
class LicornDaemonInteractor(NamedObject):
	class HistoryConsole(code.InteractiveConsole):
		def __init__(self, locals=None, filename="<licornd_console>",
			histfile=os.path.expanduser('~/.licorn/licornd_history')):
			assert ltrace('interactor', '| HistoryConsole.__init__()')
			code.InteractiveConsole.__init__(self, locals, filename)
			self.histfile = histfile
			readline.set_completer(Completer(namespace=self.locals).complete)
			readline.parse_and_bind("tab: complete")

		def init_history(self):
			assert ltrace('interactor', '| HistoryConsole.init_history()')
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

							logging.notice(_(u'{0}: switched long_output status '
								'to {1}.').format(self.name, _(u'enabled')
									if self.long_output else _(u'disabled')))

						elif char in ('c', 'C'):
							sys.stderr.write(_('Console-initiated garbage '
								'collection and dead thread cleaning.') + '\n')

							self.daemon.clean_objects()

						elif char in ('w', 'W'):
							w = self.daemon.threads.INotifier._wm.watches

							sys.stderr.write('\n'.join(repr(watch)
								for key, watch in w)
								+ 'total: %d watches\n' % len(w))

						elif char in ('t', 'T'):
							sys.stderr.write(_(u'{0} active threads: {1}').format(
								_thcount(), _threads()) + '\n')

						elif char in ('v', 'V'):
							if options.verbose < verbose.DEBUG:
								options.verbose += 1
								self.daemon.options.verbose += 1

								logging.notice(_(u'{0}: increased verbosity level '
									'to {1}.').format(self.name,
										stylize(ST_COMMENT,
											verbose[options.verbose])))

							else:
								logging.notice(_(u'{0}: verbosity level already '
									'at the maximum value ({1}).').format(
										self.name, stylize(ST_COMMENT,
											verbose[options.verbose])))

						elif char in ('q', 'Q'):
							if options.verbose > verbose.NOTICE:
								options.verbose -= 1
								self.daemon.options.verbose -= 1

								logging.notice(_(u'{0}: decreased verbosity level '
									'to {1}.').format(self.name,
										stylize(ST_COMMENT,
											verbose[options.verbose])))

							else:
								logging.notice(_(u'{0}: verbosity level already '
									'at the minimum value ({1}).').format(
										self.name, stylize(ST_COMMENT,
											verbose[options.verbose])))

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
							logging.warning(_(u'%s: killing ourselves badly.') %
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
							logging.notice(_('%s: Entering interactive mode. '
								'Welcome into licornd\'s arcanes…') % self.name)

							# trap SIGINT to avoid shutting down the daemon by
							# mistake. Now Control-C is used to reset the
							# current line in the interactor.
							def interruption(x, y):
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
									'options'       : options,
									})

							# put the TTY in standard mode (echo on).
							self.restore_terminal()
							sys.ps1 = 'licornd> '
							sys.ps2 = '...'
							interpreter.init_history()

							interpreter.interact(
									banner=_(u'Licorn® {0}, Python {1} '
										'on {2}').format(version,
										sys.version.replace('\n', ''),
										sys.platform))

							interpreter.save_history()

							# restore signal and terminal handling
							signal.signal(signal.SIGINT,
								lambda x, y: self.daemon.terminate)

							# take the TTY back into command mode.
							self.prepare_terminal()

							logging.notice(_('%s: leaving interactive mode. '
								'Welcome back to Real World™.') % self.name)

						else:
							logging.warning2(_(u'{0}: received unhandled '
								'char "{1}", ignoring.').format(
									self.name, char))
			finally:
				# put it back in standard mode after input, whatever
				# happened. The terminal has to be restored.
				self.restore_terminal()

		# else:
		# stdin is not a tty, we are in the daemon, don't do anything.
		assert ltrace(self.name, '< run()')

