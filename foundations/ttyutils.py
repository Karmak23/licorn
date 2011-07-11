# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ttyutils - manipulate TTY; display messages and interact with TTY user.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""
import sys, termios, threading

from styles    import *
from base      import Singleton
from ltrace    import mytime

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
