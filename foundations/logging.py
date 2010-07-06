# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

logging - logging extensions and facilities (stderr/out messages, syslog, logfiles...)

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.

"""
import sys, termios

import hooks, styles, exceptions

from ltrace  import mytime
from objects import Singleton

from licorn.foundations import options
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
# FIXME: define a policy explaining where we can call logging.error() (which impliesexit()), where we can't,
# where we must raise an exception or an error.
#
# the short way:
#		- in *any* licorn modules or submodules, we MUST raise, not call logging.error().
#		- in the calling programs, we MUST catch the exceptions/errors raised and call
#		  logging.error() when appropriate.
#

@Singleton
class LicornWarningsDB(dict):
	""" a singleton dict, to hold all warnings already displayed. """
	pass

__warningsdb = LicornWarningsDB()

def error(mesg, returncode = 1):
	""" Display a styles.stylized error message and exit badly.
		Run hooks registered for 'onError' event, to cleanup
		things which must be.
	"""
	#
	# these hooks are supposed to contain only cleanup code,
	# which *must* be run before the program dies.
	#
	# FIXME: verify the hooks won't bork the program / system more
	# than it is (remember, if in the present function, we are already
	# dying... In reallity these checks are undoable, so we must define
	# a policy of what hook_funcs can/may/must do and can/may/must not.
	#
	hooks.run_hooks('onError')

	sys.stderr.write(styles.stylize(styles.ST_BAD, '!! %s %s' % (mytime(),
		mesg.replace(styles.colors[styles.ST_NO],
		styles.colors[styles.ST_NO] + styles.colors[styles.ST_BAD]))) + "\n")
	if __debug__:
		import traceback
		sys.stderr.write ('''>>> %s: %s
>>> %s:
''' 	% ( styles.stylize(styles.ST_BAD, "Exception"),
			styles.stylize(styles.ST_SPECIAL, str(sys.exc_type)),
			styles.stylize(styles.ST_OK, "Call trace")))
		traceback.print_tb( sys.exc_info()[2] )
		sys.stderr.write("\n")
	raise SystemExit(returncode)
def warning(mesg, once = False):
	"""Display a styles.stylized warning message on stderr."""

	if once:
		try:
			already_displayed = __warningsdb[mesg]
			return
		except KeyError, e:
			__warningsdb[mesg] = True

	sys.stderr.write( "%s %s %s\n" % (
		styles.stylize(styles.ST_WARNING, 'WARNING:'), mytime(), mesg) )

def notice(mesg):
	""" Display a non-styles.stylized informational message on stderr."""
	#print 'verbose is %s.' % options.verbose
	if options.verbose >= options.VLEVEL_NOTICE:
		sys.stderr.write(" %s %s %s\n" % (
			styles.stylize(styles.ST_INFO, '*'), mytime(), mesg))
def info(mesg):
	""" Display a styles.stylized informational message on stderr."""
	#print 'verbose is %s.' % options.verbose
	if options.verbose >= options.VLEVEL_INFO:
		sys.stderr.write(" * %s %s\n" % (mytime(), mesg))
def progress(mesg):
	""" Display a styles.stylized informational message on stderr. """
	#print 'verbose is %s.' % options.verbose
	if options.verbose >= options.VLEVEL_PROGRESS:
		sys.stderr.write(" > %s %s\n" % (mytime(), mesg))

if __debug__:
	def debug(mesg):
		"""Display a styles.stylized debug message on stderr."""
		if options.verbose >= options.VLEVEL_DEBUG:
			sys.stderr.write( "%s: %s\n" % (
				styles.stylize(styles.ST_DEBUG, 'DEBUG'), mesg) )
	def debug2(mesg):
		"""Display a styles.stylized debug2 message on stderr."""
		if options.verbose >= options.VLEVEL_DEBUG2:
			sys.stderr.write("%s: %s\n" % (
				styles.stylize(styles.ST_DEBUG, 'DEBUG2'), mesg))
else:
	def debug(mesg): pass
	def debug2(mesg): pass

@Singleton
class RepairChoice():
	"""a singleton, to be used in all checks."""

	__choice   = None

	def __getattr__(self, attrib):
		return RepairChoice.__choice.__getattr(attrib)

	def __setattr__(self, attrib, value):
		RepairChoice.__choice.__setattr__(attrib, value)
def ask_for_repair(message, auto_answer = None):
	"""ask the user if he wants to repair, store answer for next question."""

	warning(message)
	sys.stderr.write(MESG_FIX_PROBLEM_QUESTION)

	global repair_choice
	if auto_answer is not None:
		# auto-answer has biggest priority
		repair_choice = auto_answer

	if repair_choice is True:
		sys.stderr.write(styles.stylize(styles.ST_OK, "Yes") + "\n")
		return True

	elif repair_choice is False:
		sys.stderr.write(styles.stylize(styles.ST_BAD, "No") + "\n")
		return False

	else:
		while True:
			if sys.stdin.isatty():
				# see tty and termios modules for implementation details.
				fd = sys.stdin.fileno()
				old = termios.tcgetattr(fd)
				new = termios.tcgetattr(fd)

				# put the TTY is nearly raw mode to be able to get characters
				# one by one (not to wait for newline to get one).

				# lflags
				new[3] = new[3] & ~(termios.ECHO|termios.ICANON|termios.IEXTEN)
				new[6][termios.VMIN] = 1
				new[6][termios.VTIME] = 0
				try:
					try:
						termios.tcsetattr(fd, termios.TCSAFLUSH, new)
						char = sys.stdin.read(1)
					except KeyboardInterrupt:
						sys.stderr.write("\n")
						raise
				finally:
					# put it back in standard mode after input, whatever
					# happened. The terminal has to be restored.
					termios.tcsetattr(fd, termios.TCSADRAIN, old)
			else:
				char = sys.stdin.read(1)

			if char in ( 'y', 'Y' ):
				sys.stderr.write(styles.stylize(styles.ST_OK, "Yes") + "\n")
				return True
			elif char in ( 'n', 'N' ):
				sys.stderr.write(styles.stylize(styles.ST_BAD, "No") + "\n")
				return False
			elif char in ( 'a', 'A' ):
				sys.stderr.write(
					styles.stylize(styles.ST_OK, "Yes, all") + "\n")
				repair_choice = True
				return True
			elif char in ( 's', 'S' ):
				sys.stderr.write(
					styles.stylize(styles.ST_BAD, "No and skip all") + "\n")
				repair_choice = False
				return False
			elif char in ( '?', 'h' ):
				sys.stderr.write('''\n\nUsage:\n%s: fix the current problem
%s: don't fix the current problem, skip to next (if possible).\n%s: fix all '''
'''remaining problems\n%s: skip all remaining problems (don't fix them).''' % (
					styles.stylize(styles.ST_OK, 'y'),
					styles.stylize(styles.ST_BAD, 'n'),
					styles.stylize(styles.ST_OK, 'a'),
					styles.stylize(styles.ST_BAD, 's')))
			else:
				if not sys.stdin.isatty():
					raise exceptions.LicornRuntimeError(
						"wrong command piped on stdin !")

			sys.stderr.write("\n")
			warning(message)
			sys.stderr.write(MESG_FIX_PROBLEM_QUESTION)

# used during an interactive repair session to remember when the user
# answers "yes to all" or "skip all".
repair_choice = RepairChoice()

#
# Standard strings used manywhere. All strings are centralized here.
#

### get / add / modify / delete strings ###
GENERAL_CANT_ACQUIRE_HACKD_LOCK = "Can't acquire hackd global lock, hackd is probably already running. (original error was: %s)."
GENERAL_CANT_ACQUIRE_GIANT_LOCK = "Can't acquire giant lock. You probably have another licorn-{get,add,modify,delete,check} tool already running: wait for it to finish, or last execution didn't finish cleanly: check in your ~/.licorn directory and delete the file « giant.lock » (Original error was: %s)."
GENERAL_INTERRUPTED = "Interrupted, cleaning up !"
GENERAL_UNKNOWN_MODE = "Unknow mode %s !"

### Messages ###
MESG_FIX_PROBLEM_QUESTION = "Fix this problem ? [Ynas], or ? for help: "

### Config ###

# do not put unicode chars (or anything outside ascii chars) for this one,
# it is converted/displayed before the system is in utf-8 !!
CONFIG_NONASCII_CHARSET = "Licorn System Tools can't run on an ascii-only system, we need support for accentuated letters and foreign characters (chinese and others). Forcing system character encoding to utf-8.\n\nThe most probable cause of this error is that there is a « export LANG=C » or « unset LANG/LANGUAGE » somewhere. If you don't understand what all this stuff is about, please ask your system administrator."

CONFIG_SYSTEM_GROUP_REQUIRED = u"The system group %s is mandatory for the system to work properly, but it does not exist yet."
MODULE_POSIX1E_IMPORT_ERROR  = u"Module posix1e is not installed or broken, won't be able to use ACLs (was: %s) !"

### system.users: SYSU_* ###
SYSU_CREATED_USER        = "Created user %s (uid %s)."
SYSU_DELETED_USER        = "Deleted user account %s."
SYSU_ARCHIVED_USER       = "Archived %s as %s."
SYSU_AUTOGEN_PASSWD      = "Autogenerated password for user %s: %s"
SYSU_SET_EMPTY_PASSWD    = "Setting an empty password for user %s. This is dangerous and totally insecure !"
SYSU_USER_DOESNT_EXIST   = "User %s doesn't exist."

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
SYSG_GROUP_DOESNT_EXIST    = "The group %s doesn't exist on this system."
SYSG_SYSTEM_GROUP_REQUIRED = "The system group %s is required for the group %s to be fully operationnal."
SYSG_USER_LACKS_SYMLINK    = "The user %s lacks the symlink to group %s shared dir !"


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

