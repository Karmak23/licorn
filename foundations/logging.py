# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

logging - logging extensions and facilities (stderr/out messages, syslog, logfiles…)

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import sys

from threading import current_thread

from licorn.foundations import options
from styles    import *
from constants import verbose, interactions
from ttyutils  import interactive_ask_for_repair
from ltrace    import ltrace, mytime
from base      import Singleton
from messaging import LicornMessage

# TODO: gettext this !
#import gettext
#from gettext           import gettext as _

#
# for now we use an unique gettext domain.

# drawback: performance when program grows (now it is not noticeable i think).
# advantage: don't need to pass a parameter or to call any function outside of
# this licorn.logging. All programs just need to use _(), period.
#

#_APP="licorn-tools"
#_DIR="/usr/share/locale"

#gettext.bindtextdomain(_APP, _DIR)
#gettext.textdomain(_APP)

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

__warningsdb = LicornWarningsDB()
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

	if full:
		if tb:
			sys.stderr.write(tb + '\n')
		else:
			import traceback
			sys.stderr.write ('''>>> %s:
		''' 	% (stylize(ST_OK, "Call trace")))
			traceback.print_tb( sys.exc_info()[2] )
			sys.stderr.write("\n")

	sys.stderr.write('%s %s %s\n' % (stylize(ST_BAD, 'ERROR:'),
		mytime(), mesg))

	raise SystemExit(returncode)
def warning(mesg, once=False, to_listener=True):
	"""Display a stylized warning message on stderr."""

	if once and mesg in __warningsdb:
		return

	__warningsdb[mesg] = True

	text_message = "%s%s %s\n" % (stylize(ST_WARNING, '/!\\'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message))
	sys.stderr.write(text_message)
def warning2(mesg, once=False, to_listener=True):
	""" Display a stylized warning message on stderr, only if verbose
		level > INFO. """

	if once and mesg in __warningsdb:
		return

	__warningsdb[mesg] = True

	text_message = "%s%s %s\n" % (stylize(ST_WARNING, '/2\\'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.INFO)

	if options.verbose >= verbose.INFO:
		sys.stderr.write(text_message)
def notice(mesg, to_listener=True):
	""" Display a non-stylized notice message on stderr."""

	text_message = " %s %s %s\n" % (stylize(ST_INFO, '*'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.NOTICE)

	if options.verbose >= verbose.NOTICE:
		sys.stderr.write(text_message)
def info(mesg, to_listener=True):
	""" Display a stylized information message on stderr."""

	text_message = " * %s %s\n" % (mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.INFO)

	if options.verbose >= verbose.INFO:
		sys.stderr.write(text_message)
def progress(mesg, to_listener=True):
	""" Display a stylized progress message on stderr. """

	text_message = " > %s %s\n" % (mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.PROGRESS)

	if options.verbose >= verbose.PROGRESS:
		sys.stderr.write(text_message)

	# make logging.progress() be compatible with potential assert calls.
	return True
def debug(mesg, to_listener=True):
	"""Display a stylized debug message on stderr."""

	text_message = '%s%s %s\n' % (stylize(ST_DEBUG, 'DB1'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.DEBUG)

	if options.verbose >= verbose.DEBUG:
		sys.stderr.write(text_message)

	# be compatible with assert calls
	return True
def debug2(mesg, to_listener=True):
	"""Display a stylized debug2 message on stderr."""

	text_message = '%s%s %s\n' % (stylize(ST_DEBUG, 'DB2'), mytime(), mesg)

	if to_listener:
		send_to_listener(LicornMessage(text_message), verbose.DEBUG2)

	if options.verbose >= verbose.DEBUG2:
		sys.stderr.write(text_message)

	# be compatible with assert calls
	return True
def ask_for_repair(message, auto_answer=None):
	"""ask the user if he wants to repair, store answer for next question."""

	assert ltrace('logging', '| ask_for_repair(%s)' % auto_answer)

	answer = send_to_listener(LicornMessage(data=message,
				interaction=interactions.ASK_FOR_REPAIR,
				auto_answer=auto_answer))

	if answer is not None:
		return answer
	else:
		return interactive_ask_for_repair(message, auto_answer)

#
# Standard strings used manywhere. All strings are centralized here.
#

### get / add / modify / delete strings ###
GENERAL_CANT_ACQUIRE_HACKD_LOCK = "Can't acquire hackd global lock, hackd is probably already running. (original error was: %s)."
GENERAL_CANT_ACQUIRE_GIANT_LOCK = "Can't acquire giant lock. You probably have another licorn-{get,add,modify,delete,check} tool already running: wait for it to finish, or last execution didn't finish cleanly: check in your ~/.licorn directory and delete the file « giant.lock » (Original error was: %s)."
GENERAL_INTERRUPTED = "Interrupted, cleaning up !"
GENERAL_UNKNOWN_MODE = "Unknow mode %s !"

### Config ###

# do not put unicode chars (or anything outside ascii chars) for this one,
# it is converted/displayed before the system is in utf-8 !!
CONFIG_NONASCII_CHARSET = "Licorn System Tools can't run on an ascii-only system, we need support for accentuated letters and foreign characters (chinese and others). Forcing system character encoding to utf-8.\n\nThe most probable cause of this error is that there is a « export LANG=C » or « unset LANG/LANGUAGE » somewhere. If you don't understand what all this stuff is about, please ask your system administrator."

CONFIG_SYSTEM_GROUP_REQUIRED = u"The system group %s is mandatory for the system to work properly, but it does not exist yet."
MODULE_POSIX1E_IMPORT_ERROR  = u"Module posix1e is not installed or broken, won't be able to use ACLs (was: %s) !"

### system.users: SYSU_* ###
SYSU_CREATED_USER        = "Created %suser %s (uid=%s)."
SYSU_DELETED_USER        = "Deleted user account %s."
SYSU_ARCHIVED_USER       = "Archived %s as %s."
SYSU_AUTOGEN_PASSWD      = "Autogenerated password for user %s (uid=%s): %s"
SYSU_SET_EMPTY_PASSWD    = "Setting an empty password for user %s. This is dangerous and totally insecure !"
SYSU_USER_DOESNT_EXIST   = "User %s doesn't exist"

SYSU_MALFORMED_LOGIN     = "Malformed login `%s', must match /%s/."
SYSU_MALFORMED_GECOS     = "Malformed GECOS field `%s', must match /%s/i."

SYSU_CANT_CREATE_USER    = "Unable to create user %s !"

SYSU_SPECIFY_LOGIN       = "You must specify a login (use --help to know how)."
SYSU_SPECIFY_LGN_OR_UID  = "You must specify a login or a UID (use --help to know how)."
SYSU_SPECIFY_LGN_FST_LST = "You must specify a login, or firstname *and* lastname (login will be automatically built from them)."
SYSU_SPECIFY_LF_OR_GECOS = "You must specify a lastname and a firstname *or* a GECOS. If you specify the GECOS, don't specify first/last and vice-versa."

### system.groups: SYSG_* ###
SYSG_CREATED_GROUP         = "Created group %s."
SYSG_DELETED_GROUP         = "Deleted group %s."
SYSG_GROUP_DOESNT_EXIST    = "The group %s doesn't exist"
SYSG_SYSTEM_GROUP_REQUIRED = "The system group %s is required for the group %s to be fully operationnal."
SYSG_USER_LACKS_SYMLINK    = "User %s lacks the symlink to group %s shared dir. Create it?"


### system.profiles: SYSP_* ###
SYSP_DELETED_PROFILE = "Deleted profile %s."

SYSP_SPECIFY_GROUP   = "You must specify a group to find the profile (use --help to know how)."
SYSP_SPECIFY_SKEL    = "You must specify a shell for the profile (use --help to know how)."
SYSP_SPECIFY_SHELL   = "You must specify a valid skel dir for the profile (use --help to know how)."


### system.keywords: SYSK_* ###
SYSK_SPECIFY_KEYWORD   = "You must specify a keyword name."
SYSK_MALFORMED_KEYWORD = "Malformed keyword name `%s', must match /%s/i."
SYSK_MALFORMED_DESCR   = "Malformed keyword description `%s', must match /%s/i."

### Swissknives ###
SWKN_DIR_IS_NOT_A_DIR  = "The directory %s is *not* a directory !"
SWKN_DIR_BAD_OWNERSHIP = "Invalid ownership for %s (it is %s:%s but should be %s:%s)."
SWKN_INVALID_ACL       = "Invalid %s ACL for %s (it is %s but should be %s)."
SWKN_INVALID_MODE      = "Invalid Unix mode for %s (it is %s but should be %s)."

