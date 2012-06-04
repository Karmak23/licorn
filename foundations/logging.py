# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

logging - logging extensions and facilities (stderr/out messages, syslog, logfiles…)

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import sys, Pyro.errors, traceback

from threading import current_thread
from types     import *

# licorn.foundations imports
import exceptions, styles
from threads   import RLock
from _options  import options
from styles    import *
from ltrace    import *
from ltraces   import *
from constants import verbose, interactions
from ttyutils  import interactive_ask_for_repair
from base      import ObjectSingleton
from messaging import LicornMessage, MessageProcessor

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

# FIXME: define a policy explaining where we can call logging.error() (which
# implies exit()), where we can't, where we must raise an exception or an error.
#
# the short way:
#		- in *any* licorn modules or submodules, we MUST raise, not call
#			logging.error().
#		- in the calling programs, we MUST catch the exceptions/errors raised
#			and call logging.error() when appropriate.
#

class LicornWarningsDB(ObjectSingleton):
	""" a singleton dict, to hold all warnings already displayed. """

	warnings = None

	def __init__(self):
		if LicornWarningsDB.warnings is None:
			LicornWarningsDB.warnings = {}
	def __getitem__(self, item):
		return LicornWarningsDB.warnings[item]
	def __setitem__(self, item, value):
		LicornWarningsDB.warnings[item] = value
	def keys(self):
		return LicornWarningsDB.warnings.keys()

__warningsdb = LicornWarningsDB()

#: we've got to synchronize all threads for outputing anything, else in rare
#: cases the display can be corrupted by two threads saying something at the
#: exact same time. Seen on 20101210 with 2 PyroFinders.
__output_lock = RLock()

def send_to_listener(message, verbose_level=verbose.QUIET):
	""" See if current thread has a listener (Remote Pyro object dedicated to
		inter-process communication), and send the message to it. """
	try:
		listener = current_thread().listener

	except AttributeError:
		return None
	else:
		if listener.verbose >= verbose_level:
			return listener.process(message,
					options.msgproc.getProxy())
def error(mesg, returncode=1, full=False, tb=None):
	""" Display a stylized error message and exit badly.	"""

	text_message = '%s %s %s\n' % (stylize(ST_BAD, 'ERROR:'), ltrace_time(), mesg)

	with __output_lock:
		if full:
			if tb:
				sys.stderr.write(tb + '\n')
			else:
				import traceback
				sys.stderr.write ('''>>> %s:
			''' 	% (stylize(ST_OK, "Call trace")))
				traceback.print_tb( sys.exc_info()[2] )
				sys.stderr.write("\n")

		sys.stderr.write(text_message)
		#sys.stderr.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_1, 'ERR{0}', mesg)

	sys.exit(returncode)
def warning(mesg, once=False, to_listener=True, to_local=True):
	"""Display a stylized warning message on stderr."""

	if once and mesg in __warningsdb:
		return

	__warningsdb[mesg] = True

	text_message = "%s%s %s\n" % (stylize(ST_WARNING, '/!\\'), ltrace_time(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.NOTICE)

	if to_local:
		with __output_lock:
			sys.stderr.write(text_message)
			#sys.stderr.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_1, '/!\\{0}', mesg)
def warning2(mesg, once=False, to_listener=True, to_local=True):
	""" Display a stylized warning message on stderr, only if verbose
		level > INFO. """

	if once and mesg in __warningsdb:
		return

	__warningsdb[mesg] = True

	text_message = "%s%s %s\n" % (stylize(ST_WARNING, '/2\\'), ltrace_time(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.INFO)

	if to_local and options.verbose >= verbose.INFO:
		with __output_lock:
			sys.stderr.write(text_message)
			#sys.stderr.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_2, '/2\\{0}', mesg)
	# be compatible with potential assert calls.
	return True
def notice(mesg, to_listener=True, to_local=True):
	""" Display a stylized NOTICE message on stderr, and publish it to the
		remote listener if not told otherwise. """

	text_message = " %s %s %s\n" % (stylize(ST_INFO, '*'), ltrace_time(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.NOTICE)

	if to_local and options.verbose >= verbose.NOTICE:
		with __output_lock:
			sys.stdout.write(text_message)
			#sys.stdout.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_1, ' ! {0}', mesg)
def info(mesg, to_listener=True, to_local=True):
	""" Display a stylized INFO message on stderr, and publish it to the
		remote listener if not told otherwise. """

	text_message = " * %s %s\n" % (ltrace_time(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.INFO)

	if to_local and options.verbose >= verbose.INFO:
		with __output_lock:
			sys.stdout.write(text_message)
			#sys.stdout.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_2, ' * {0}', mesg)
def progress(mesg, to_listener=True, to_local=True):
	""" Display a stylized PROGRESS message on stderr, and publish it to the
		remote listener if not told otherwise. """

	text_message = " > %s %s\n" % (ltrace_time(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.PROGRESS)

	if to_local and options.verbose >= verbose.PROGRESS:
		with __output_lock:
			sys.stdout.write(text_message)
			#sys.stdout.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_3, ' > {0}', mesg)

	# make logging.progress() be compatible with potential assert calls.
	return True
def exception(*args, **kwargs):
	""" display full exception if >= PROGRESS, else just display a message. """

	if options.verbose >= verbose.PROGRESS:
		text_message = "%s%s %s\n%s" % (stylize(ST_WARNING, '{E}'), ltrace_time(),
							args[0].format(*(stylize(*x)
								if type(x) == TupleType
								else x
								for x in args[1:])),
							# full traceback.
							traceback.format_exc())

	else:
		text_message = "%s%s %s: %s\n" % (stylize(ST_WARNING, '{E}'), ltrace_time(),
							args[0].format(*(stylize(*x)
								if type(x) == TupleType
								else x
								for x in args[1:])),
							# only last line of traceback.
							traceback.format_exc(1).split('\n')[-2])

	# else:
	# implicit: as this function is meant to display exceptions but not exit
	# in case we hit one, we don't display them in NOTICE production
	# environments. This will avoid polluting the output and logs.

	if kwargs.get('to_listener', True):
		send_to_listener(LicornMessage(text_message), verbose.INFO)

	if kwargs.get('to_local', True) and options.verbose >= verbose.INFO:
		with __output_lock:
			sys.stderr.write(text_message)
			#sys.stderr.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_1, '{{E}}{0}', text_message)
def monitor(facility, level, *args):
	""" Send a message to all (network-)attached monitoring sessions, if the
		facility of the message is wanted by the remote monitor. """

	with options.monitor_lock:
		for listener_thread in options.monitor_listeners:

			with listener_thread.monitor_lock:
				try:
					if listener_thread.monitor_facilities & facility \
								and listener_thread.listener.verbose >= level:
						try:
							listener_thread.listener.process(
								LicornMessage(
									u'%s %s %s %s\n' % (
										stylize(ST_YELLOW, '⧎'),
										stylize(ST_COMMENT,
											facility.name.ljust(TRACES_MAXWIDTH)),
										ltrace_time(),
										args[0].format(*(stylize(*x)
											if type(x) == TupleType
											else x
											for x in args[1:]))
										)),
								options.msgproc.getProxy())

						except AttributeError, e:
							# we have to remove the thread before issuing the warning,
							# else it will create a cycle (warning() calls monitor()).
							options.monitor_listeners.remove(listener_thread)
							warning(_(u'Thread {0} has no listener '
								u'anymore, desengaging from monitors '
								u'(was: {1}).').format(
									stylize(ST_NAME, listener_thread.name), e))

				except Pyro.errors.ConnectionClosedError, e:
					# we have to remove the thread before issuing the warning,
					# else it will create a cycle (warning() calls monitor()).
					options.monitor_listeners.remove(listener_thread)
					warning(_(u'Thread {0} has lost its remote '
						u'end, desengaging from monitors (was: {1}).').format(
							stylize(ST_NAME, listener_thread.name), e))

	# be compatible with assert calls, if some monitor() calls needs to be
	# dinamically added/removed from the code.
	return True
def debug(mesg, to_listener=True):
	"""Display a stylized DEBUG (level1) message on stderr, and publish it to
		the remote listener if not told otherwise. """

	text_message = '%s%s %s\n' % (stylize(ST_DEBUG, 'DB1'), ltrace_time(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.DEBUG)

	if options.verbose >= verbose.DEBUG:
		with __output_lock:
			sys.stderr.write(text_message)
			#sys.stderr.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_3, '{0}', text_message[0:4] + text_message[30:-1])

	# be compatible with assert calls
	return True
def debug2(mesg, to_listener=True):
	"""Display a stylized DEBUG (level2) message on stderr, and publish it to
		the remote listener if not told otherwise. """

	text_message = '%s%s %s\n' % (stylize(ST_DEBUG, 'DB2'), ltrace_time(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.DEBUG2)

	if options.verbose >= verbose.DEBUG2:
		with __output_lock:
			sys.stderr.write(text_message)
			#sys.stderr.flush()

	monitor(TRACE_LOGGING, TRACELEVEL_3, '{0}', text_message[0:4] + text_message[30:-1])

	# be compatible with assert calls
	return True
def ask_for_repair(message, auto_answer=None):
	""" Ask the user to answer Yes/No/Skip/All to a question. Return True/False
		for Yes/No answers, and store the answer for next questions if Skip/All.

		If there is a listener, forward the question to it (don't ask locally)
		and get back the answer from it.

		When asking the question locally, use :func:`interactive_ask_for_repair`
		from the :mod:`ttyutils` module.
	"""

	assert ltrace(TRACE_LOGGING, '| ask_for_repair(%s)' % auto_answer)

	answer = send_to_listener(LicornMessage(data=message,
				interaction=interactions.ASK_FOR_REPAIR,
				auto_answer=auto_answer))

	if answer is not None:
		return answer

	else:
		return interactive_ask_for_repair(message, auto_answer)
def warn_or_raise(msg, once=False, to_listener=True, to_local=True, warn_only=False, exc_class=None):
	if warn_only:
		warning(msg, once, to_listener, to_local)

	else:
		if exc_class is None:
			raise exceptions.LicornRuntimeException(msg)

		else:
			raise exc_class(msg)
