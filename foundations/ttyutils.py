# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ttyutils - manipulate TTY; display messages and interact with TTY user.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""
import sys, os, termios, threading, curses, code
import select, signal, errno

# licorn.foundations
import logging
from styles    import *
from base      import Singleton, NamedObject
from ltrace    import mytime, ltrace
from ltraces   import *

curses.setupterm()
clear_char = curses.tigetstr('clear')


### Messages ###
MESG_FIX_PROBLEM_QUESTION = " [Ynas], or ? for help: "

# used during an interactive repair session to remember when the user
# answers "yes to all" or "skip all".
class RepairChoice(Singleton):
	"""a singleton, to be used in all checks."""

	__choice   = None

	def __getattr__(self, attrib):
		return RepairChoice.__choice.__getattr(attrib)

	def __setattr__(self, attrib, value):
		RepairChoice.__choice.__setattr__(attrib, value)

repair_choice = RepairChoice()
def clear_terminal(channel=None):
	if channel is None:
		channel = sys.stdout
	#channel.write('\x1B[2J')
	channel.write(clear_char)
	channel.flush()
def question(mesg):
	""" Display a stylized question message on stderr."""

	sys.stderr.write(" %s %s %s" % (
		stylize(ST_INFO, '?'), mytime(), mesg))
def interactive_ask_for_repair(message, auto_answer=None):
	"""ask the user if he wants to repair, store answer for next question."""

	question(message + MESG_FIX_PROBLEM_QUESTION)

	global repair_choice

	if auto_answer is not None:
		# auto-answer has higher priority than repair choice, because it is
		# given on command-line arguments.
		repair_choice = auto_answer

	if repair_choice is True:
		sys.stderr.write(stylize(ST_OK, "Yes") + "\n")
		return True

	elif repair_choice is False:
		sys.stderr.write(stylize(ST_BAD, "No") + "\n")
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
					sys.stderr.write("\n")

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
				char = sys.stdin.read(1)

			if char in ( 'y', 'Y' ):
				sys.stderr.write(stylize(ST_OK, "Yes") + "\n")
				return True
			elif char in ( 'n', 'N' ):
				sys.stderr.write(stylize(ST_BAD, "No") + "\n")
				return False
			elif char in ( 'a', 'A' ):
				sys.stderr.write(
					stylize(ST_OK, "Yes, all") + "\n")
				repair_choice = True
				return True
			elif char in ( 's', 'S' ):
				sys.stderr.write(
					stylize(ST_BAD, "No and skip all") + "\n")
				repair_choice = False
				return False
			elif char in ( '?', 'h' ):
				sys.stderr.write('''\n\nUsage:\n%s: fix the current problem '''
					'''%s: don't fix the current problem, skip to next (if '''
					'''possible).\n%s: fix all remaining problems\n%s: skip '''
					'''all remaining problems (don't fix them).''' % (
					stylize(ST_OK, 'y'),
					stylize(ST_BAD, 'n'),
					stylize(ST_OK, 'a'),
					stylize(ST_BAD, 's')))
			else:
				if not sys.stdin.isatty():
					raise exceptions.LicornRuntimeError(
						"wrong command piped on stdin !")

			sys.stderr.write("\n")
			question(message + MESG_FIX_PROBLEM_QUESTION)
# LicornInteractor is an object dedicated to user interaction, either in CLI
# or when the daemon is in the foreground. CLI and the daemon define inherited
# classes of this one, which does pretty nothing.
class LicornInteractor(NamedObject):
	def __init__(self, name):
		assert ltrace(TRACE_INTERACTOR, '| LicornInteractor.__init__()')

		NamedObject.__init__(self, name)

		if __debug__:
			self._trace_name  = globals()['TRACE_' + self.name.upper()]

		self._stop_event = threading.Event()
		self.avoid_help  = ()
	def prepare_terminal(self):
		assert ltrace(globals()['TRACE_' + self.name.upper()], '| prepare_terminal()')
		termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new)
	def restore_terminal(self):
		assert ltrace(globals()['TRACE_' + self.name.upper()], '| restore_terminal()')
		termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
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

			try:
				self.prepare_terminal()

				while not self._stop_event.is_set():
					try:
						readf, writef, errf = select.select([self.fd], [], [])

						if readf == []:
							continue

						else:
							char = sys.stdin.read(1)

					except (IOError, OSError), e:
						if e.errno != errno.EBADF:
							raise
						else:
							self._stop_event.set()
							break

					except select.error, e:
						if e.args[0] == 4:
							sys.stderr.write(u'^C\n')
							self.restore_terminal()

							try:
								self.terminate(2)

							except AttributeError:
								pass

						else:
							raise e

					else:
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

						elif char in self.handled_chars:
							self.handled_chars[char]()

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
							logging.warning2(_(u'{0}: received unhandled '
								u'char "{1}", ignoring.').format(
									stylize(ST_NAME, self.name),
									stylize(ST_BAD,char)))
			finally:
				# put it back in standard mode after input, whatever
				# happened. The terminal has to be restored.
				self.restore_terminal()

		# else: (isatty())
		# don't do anything.
		assert ltrace(self._trace_name, '< run()')

