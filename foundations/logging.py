# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

logging - logging extensions and facilities (stderr/out messages, syslog, logfiles…)

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import sys
from threading import current_thread, RLock

from licorn.foundations import options
from styles    import *
from constants import verbose, interactions
from ttyutils  import interactive_ask_for_repair
from ltrace    import ltrace, mytime
from base      import Singleton
from messaging import LicornMessage
from licorn.foundations.messaging import MessageProcessor
from BaseHTTPServer	import BaseHTTPRequestHandler

#
# FIXME: define a policy explaining where we can call logging.error() (which
# implies exit()), where we can't, where we must raise an exception or an error.
#
# the short way:
#		- in *any* licorn modules or submodules, we MUST raise, not call
#			logging.error().
#		- in the calling programs, we MUST catch the exceptions/errors raised
#			and call logging.error() when appropriate.
#
def warn_exception(func):
	""" Catch any exception and display a warning about it, but don't fail.
		Meant to be used as a decorator in various places. """
	def internal_func(*args, **kwargs):
		try:
			func(*args, **kwargs)
		except Exception, e:
			warning(_(u'Exception occured in {0}: {1}.').format(func, e),
				# this is propably an obscure and harmless internal error,
				# don't forward it to the CLI user.
				to_listener=False)
	return internal_func

class LicornWarningsDB(Singleton):
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
#: cases the display can be corrupted by two threads saying somthing at the
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
			# WARNING: should test Pyro object instead of WMI one, but 
			# listener is not type(MessageProcessor) but type(instance) 
			# instead because in pyro only the remote object will be 
			# the wanted type.
			if isinstance(listener, BaseHTTPRequestHandler):
				return listener.process(message.data, verbose_level)
			else:
				return listener.process(message,
					options.msgproc.getProxy())
def error(mesg, returncode=1, full=False, tb=None):
	""" Display a stylized error message and exit badly.	"""

	if full:
		if tb:
			sys.stderr.write(tb + '\n')
		else:
			import traceback
			sys.stderr.write ('''>>> %s:
		''' 	% (stylize(ST_OK, "Call trace")))
			traceback.print_tb( sys.exc_info()[2] )
			sys.stderr.write("\n")

	with __output_lock:
		sys.stderr.write('%s %s %s\n' % (stylize(ST_BAD, 'ERROR:'),
			mytime(), mesg))

	raise SystemExit(returncode)
def warning(mesg, once=False, to_listener=True, to_local=True):
	"""Display a stylized warning message on stderr."""

	if once and mesg in __warningsdb:
		return

	__warningsdb[mesg] = True

	text_message = "%s%s %s\n" % (stylize(ST_WARNING, '/!\\'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.NOTICE)

	if to_local:
		with __output_lock:
			sys.stderr.write(text_message)
def warning2(mesg, once=False, to_listener=True, to_local=True):
	""" Display a stylized warning message on stderr, only if verbose
		level > INFO. """

	if once and mesg in __warningsdb:
		return

	__warningsdb[mesg] = True

	text_message = "%s%s %s\n" % (stylize(ST_WARNING, '/2\\'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.INFO)

	if to_local and options.verbose >= verbose.INFO:
		with __output_lock:
			sys.stderr.write(text_message)
def notice(mesg, to_listener=True, to_local=True):
	""" Display a stylized NOTICE message on stderr, and publish it to the
		remote listener if not told otherwise. """

	text_message = " %s %s %s\n" % (stylize(ST_INFO, '*'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.NOTICE)

	if to_local and options.verbose >= verbose.NOTICE:
		with __output_lock:
			sys.stderr.write(text_message)
def info(mesg, to_listener=True, to_local=True):
	""" Display a stylized INFO message on stderr, and publish it to the
		remote listener if not told otherwise. """

	text_message = " * %s %s\n" % (mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.INFO)

	if to_local and options.verbose >= verbose.INFO:
		sys.stderr.write(text_message)
def progress(mesg, to_listener=True, to_local=True):
	""" Display a stylized PROGRESS message on stderr, and publish it to the
		remote listener if not told otherwise. """

	text_message = " > %s %s\n" % (mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.PROGRESS)

	if to_local and options.verbose >= verbose.PROGRESS:
		with __output_lock:
			sys.stderr.write(text_message)

	# make logging.progress() be compatible with potential assert calls.
	return True
def debug(mesg, to_listener=True):
	"""Display a stylized DEBUG (level1) message on stderr, and publish it to
		the remote listener if not told otherwise. """

	text_message = '%s%s %s\n' % (stylize(ST_DEBUG, 'DB1'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.DEBUG)

	if options.verbose >= verbose.DEBUG:
		with __output_lock:
			sys.stderr.write(text_message)

	# be compatible with assert calls
	return True
def debug2(mesg, to_listener=True):
	"""Display a stylized DEBUG (level2) message on stderr, and publish it to
		the remote listener if not told otherwise. """

	text_message = '%s%s %s\n' % (stylize(ST_DEBUG, 'DB2'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.DEBUG2)

	if options.verbose >= verbose.DEBUG2:
		with __output_lock:
			sys.stderr.write(text_message)

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

	assert ltrace('logging', '| ask_for_repair(%s)' % auto_answer)

	answer = send_to_listener(LicornMessage(data=message,
				interaction=interactions.ASK_FOR_REPAIR,
				auto_answer=auto_answer))

	if answer is not None:
		return answer
	else:
		return interactive_ask_for_repair(message, auto_answer)
