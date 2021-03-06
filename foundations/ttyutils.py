# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ttyutils - manipulate TTY; display messages and interact with TTY user.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""
import sys, os, termios, threading, curses, struct, fcntl
import select, signal, errno

# licorn.foundations
import logging
from styles    import *
from base      import ObjectSingleton, NamedObject
from ltrace    import *
from ltraces   import *

try:
	curses.setupterm()
	clear_char = curses.tigetstr('clear')

except:
	# the terminal won't be cleared; there is probably no terminal, BTW.
	clear_char = ''

### Messages ###
try:
	MESG_FIX_PROBLEM_QUESTION = _(u" [Ynas], or ? for help: ")

except NameError:
	# gettext is not loaded, try to make things works without it.
	_ = lambda a: a
	MESG_FIX_PROBLEM_QUESTION = u" [Ynas], or ? for help: "


# used during an interactive repair session to remember when the user
# answers "yes to all" or "skip all".
class RepairChoice(ObjectSingleton):
	"""a singleton, to be used in all checks."""

	__choice   = None

	def __getattr__(self, attrib):
		return RepairChoice.__choice.__getattr(attrib)

	def __setattr__(self, attrib, value):
		RepairChoice.__choice.__setattr__(attrib, value)

repair_choice = RepairChoice()
def clear_terminal(channel=None):
	""" This function will do nothing if `curses` failed to initialize. """
	if channel is None:
		channel = sys.stdout
	channel.write(clear_char)
	channel.flush()
def terminal_size():
	""" We could also get it from a more feature complete function at
		http://stackoverflow.com/a/566752 in case we need more. """
	#print '(rows, cols, x pixels, y pixels) =',
	return struct.unpack("HHHH",
		fcntl.ioctl(
			sys.stdout.fileno(),
			termios.TIOCGWINSZ,
			struct.pack("HHHH", 0, 0, 0, 0)
			)
		)
def question(mesg):
	""" Display a stylized question message on stderr."""

	sys.stderr.write(" %s %s %s" % (
		stylize(ST_INFO, '?'), ltrace_time(), mesg))
def interactive_ask_for_repair(message, auto_answer=None):
	"""ask the user if he wants to repair, store answer for next question."""

	question(message + MESG_FIX_PROBLEM_QUESTION)

	global repair_choice

	if auto_answer is not None:
		# auto-answer has higher priority than repair choice, because it is
		# given on command-line arguments.
		repair_choice = auto_answer

	if repair_choice is True:
		sys.stderr.write(stylize(ST_OK, _(u"Yes")) + '\n')
		return True

	elif repair_choice is False:
		sys.stderr.write(stylize(ST_BAD, _(u"No")) + '\n')
		return False

	else:
		if sys.stdin.isatty():
			is_a_tty = True

			# see tty and termios modules for implementation details.
			fd = sys.stdin.fileno()
			old = termios.tcgetattr(fd)
			new = termios.tcgetattr(fd)
			# lflags
			new[3] = new[3] & ~(termios.ECHO|termios.ICANON|termios.IEXTEN)
			new[6][termios.VMIN] = 1
			new[6][termios.VTIME] = 0

			def restore_terminal(flush=True):
				termios.tcsetattr(fd, termios.TCSADRAIN, old)
				if flush:
					sys.stderr.write('\n')

		else:
			is_a_tty = False

		while True:
			if is_a_tty:
				# We need to add a method to restore the terminal to the MainThread,
				# because in CLI programs only the MainThread receives the
				# SIGINT, and it doesn't directly know if it has to restore the
				# terminal because the current function is usually called from the
				# Pyro thread.
				threading.enumerate()[0].restore_terminal = restore_terminal

				# put the TTY in nearly raw mode to be able to get characters
				# one by one (not to wait for newline to get one).
				termios.tcsetattr(fd, termios.TCSAFLUSH, new)

				char = sys.stdin.read(1)

				# put the terminal back in standard mode after input.
				restore_terminal(flush=False)

				del threading.enumerate()[0].restore_terminal

			else:
				char = sys.stdin.read(1).lower()

			# We still accept the english letters, besides the translated ones.
			if char in ( 'y', _(u'y') ):
				sys.stderr.write(stylize(ST_OK, _(u'Yes')) + '\n')
				return True
			elif char in ( 'n', _(u'n')):
				sys.stderr.write(stylize(ST_BAD, _(u'No')) + '\n')
				return False
			elif char in ( 'a', _(u'a') ):
				sys.stderr.write(
					stylize(ST_OK, _(u'Yes, all')) + '\n')
				repair_choice = True
				return True
			elif char in ( 's', _(u's') ):
				sys.stderr.write(
					stylize(ST_BAD, _(u'No and skip all')) + '\n')
				repair_choice = False
				return False
			elif char in ( '?', 'h', _(u'h') ):
				sys.stderr.write(_(u'\n\nUsage:\n'
					u'{0}: fix the current problem and continue until next.\n'
					u'{1}: do not fix the current problem, skip to next (if '
						u'possible).\n'
					u'{2}: fix this problem and all remaining without '
						u'asking further questions.\n'
					u'{3}: skip this problem and all remaining ones (if '
					u'possible).').format(
						stylize(ST_OK, u'y/%s' % _(u'y')),
						stylize(ST_BAD, u'n/%s' % _(u'n')),
						stylize(ST_OK, u'a/%s' % _(u'a')),
						stylize(ST_BAD, u's/%s' % _(u's'))))
			else:
				if not sys.stdin.isatty():
					raise exceptions.LicornRuntimeError(
						_(u"wrong command piped on stdin!"))

			sys.stderr.write('\n')
			question(message + MESG_FIX_PROBLEM_QUESTION)
# LicornInteractor is an object dedicated to user interaction, either in CLI
# or when the daemon is in the foreground. CLI and the daemon define inherited
# classes of this one, which does pretty nothing.
class LicornInteractor(NamedObject):
	def __init__(self, name):
		assert ltrace(TRACE_INTERACTOR, '| LicornInteractor.__init__()')

		NamedObject.__init__(self, name=name)

		if __debug__:
			self._trace_name  = globals()['TRACE_' + self.name.upper()]

		self._stop_event = threading.Event()
		self.exit_pipe   = os.pipe()
		self.avoid_help  = ()
	def prepare_terminal(self):
		assert ltrace(globals()['TRACE_' + self.name.upper()], '| prepare_terminal()')
		termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new)
	def restore_terminal(self):
		""" Put the terminal back in standard mode. """
		assert ltrace(globals()['TRACE_' + self.name.upper()], '| restore_terminal()')
		termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
	def stop(self, with_restore=True):
		""" Stop the interactor gracefully and restore the terminal if told so. """

		self._stop_event.set()

		if with_restore:
			try:
				self.restore_terminal()

			except:
				pass
	def run(self):
		""" prepare stdin for interaction and wait for chars. """
		if sys.stdin.isatty():
			assert ltrace(self._trace_name, '> run()')

			# see tty and termios modules for implementation details.
			self.fd = sys.stdin.fileno()
			self.old = termios.tcgetattr(self.fd)
			self.new = termios.tcgetattr(self.fd)

			# put the TTY in nearly raw mode to be able to get characters
			# one by one (not to wait for newline to get one).

			# lflags
			self.new[3] = self.new[3] & ~ ( termios.ECHO
											| termios.ICANON
											| termios.IEXTEN)
			self.new[6][termios.VMIN] = 1
			self.new[6][termios.VTIME] = 0

			self.prepare_terminal()

			interrupted = False

			while not self._stop_event.is_set():
				try:
					readf, writef, errf = select.select([self.fd, self.exit_pipe[0]], [], [])

				except (IOError, OSError), e:
					if e.errno != errno.EBADF:
						raise

					else:
						self.stop()
						break

				except select.error, e:
					if e.args[0] == errno.EINTR:

						self.stop()

						try:
							self.terminate(2)

						except AttributeError:
							pass

						interrupted = True
					else:
						raise e

				else:

					if interrupted:
						# if we are still here, the current process didn't
						# terminate. Re-prepare the terminal, else
						# interactive mode will not work anymore.
						self.prepare_terminal()
						interrupted = False

					if readf == []:
						continue

					else:
						if self.exit_pipe[0] in readf:
							break

						char = sys.stdin.read(1)

					# control characters from
					# http://www.unix-manuals.com/refs/misc/ascii-table.html
					if char == '\n':
						sys.stderr.write('\n')

					# ^L (form-feed, clear screen)
					elif char == '\f':
						clear_terminal()

					# ^U kill -15
					elif char == '' :
						# no need to log anything, process will display
						# 'signal received' messages.
						#logging.warning('%s: killing ourselves softly.' %
						#	self.pname)

						# no need to kill WMI, terminate() will do it clean.
						self.restore_terminal()
						os.kill(os.getpid(), signal.SIGTERM)

					# ^K (Kill -9!!)
					elif char == '\v':
						logging.warning(_(u'%s: killing ourselves badly.') %
							stylize(ST_NAME, self.name))

						self.restore_terminal()
						os.kill(os.getpid(), signal.SIGKILL)

					elif char.lower() in self.handled_chars:
						self.handled_chars[char.lower()]()

					elif char in ( '?', 'h', 'H' ):
						sys.stderr.write(_(u'\n\tInteractive session commands:\n'
							u'\t"{0}", "{1}" or "{2}": display this help message,\n'
							u'\t{3}: display a new-line (for readability purposes),\n'
							u'\t{4}: clear the screen (idem),\n'
							u'\t{5}: interrupt the current program (kill -INT self),\n'
							u'\t{6}: terminate (kill -TERM self),\n'
							u'\t{7}: die badly (kill -KILL self),\n').format(
							stylize(ST_OK, u'?'),
							stylize(ST_OK, u'h'),
							stylize(ST_OK, u'H'),
							stylize(ST_OK, _(u'Return')),
							stylize(ST_OK, u'Control-L'),
							stylize(ST_OK, u'Control-C'),
							stylize(ST_OK, u'Control-U'),
							stylize(ST_OK, u'Control-K')) +
							u',\n'.join(u'\t{letter}{explanation}'.format(
								letter=_(u'"{letter_lower}" or "{letter_upper}": ').format(
										letter_lower=stylize(ST_OK, key),
										letter_upper=stylize(ST_OK, key.upper()))
									if key.isalnum()
									else (_(u'" ": ') if key == ' ' else u''),
								explanation=value.__doc__
								) for key, value
									in self.handled_chars.iteritems()
									if key not in self.avoid_help)
							+ u'.\n\n')
					else:
						try:
							logging.warning2(_(u'{0}: received unhandled '
								u'char "{1}", ignoring.').format(
									stylize(ST_NAME, self.name),
									stylize(ST_BAD, char)))
						except:
							logging.exception(_(u'{0}: bad character received on input, ignored.').format(
									stylize(ST_NAME, self.name)))

		# else: (isatty())
		# don't do anything.
		assert ltrace(self._trace_name, '< run()')

