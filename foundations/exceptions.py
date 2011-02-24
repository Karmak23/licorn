# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2
"""

#
# WARNING: please do not import anything from licorn here.
#
import os

class LicornException(Exception):
	""" !!! NOT TO BE RAISED DIRECTLY !!!
		This exception class is to be derivated to create every other *Exception subclasses.
		It is meant to be able to catch every subclass in main Licorn programs with only one
		«except» statement, to distinguish between an Licorn Exception/Error and a standard Python error.
	"""
	errno = 1
	pass
class LicornError(LicornException):
	""" !!! NOT TO BE RAISED DIRECTLY !!!
		This exception class is to be derivated to create every other *Error subclasses.
		It is derivated from LicornException to stick to the python Exception classes,
		and to permit to catch only one general Licorn class at the lowest levels in
		Licorn programs.
	"""
	errno = 2
	pass
class LicornConfigurationException(LicornException):
	""" Raised when a fatal configuration error is encountered.

		This exception is used when parsing a configuration file can't be done,
		or if a configuration directive needed by Licorn is missing.
	"""
	errno = 3
	pass
class LicornSyntaxException(LicornConfigurationException):
	""" Raised when a bad syntax is encountered in any file.
	"""
	errno = 31
	def __init__(self, file_name=None, line_no=None, text=None, text_part=None,
		desired_syntax=None, optional_exception=None):
		self.file_name = file_name
		self.line_no = line_no
		self.text = text
		self.text_part = text_part
		self.desired_syntax = desired_syntax
		self.opt = optional_exception
	def __str__(self):
		return '%s: invalid syntax at line %d: %s %s.' % (
				self.file_name,
				self.line_no,
				self.text,
				'must match %s' % self.desired_syntax \
					if self.opt is None else '(was: %s)' % self.opt)
class LicornACLSyntaxException(LicornSyntaxException):
	""" Raised when a bad syntax is encountered in any file.
	"""
	errno = 311
	#def __init__(self, file_name, line_no, text, text_part=None,
	#	desired_syntax=None):
	#	LicornSyntaxException.__init__(file_name, line_no, text, text_part=None,
	#	desired_syntax=None)
	def __str__(self):
		return '''%s: invalid ACL %s at line %d ''' \
			'''(part '%s' is faulty%s).''' % (
			#stylize(ST_PATH, self.file_name),
			#stylize(ST_COMMENT, splitted_acl),
			#self.line_no,
			#stylize(ST_BAD, splitted_acl[bad_part-1]))
			self.file_name,
			self.text,
			self.line_no,
			self.text_part,
			'' if self.opt is None else ', %s' % self.opt)
class LicornConfigurationError(LicornError):
	""" Raised when a correctable configuration problem is encountered.

		This exception is used when parsing a configuration file can't be done,
		or if a configuration directive needed by Licorn is missing.
	"""
	errno = 4
	pass
class LicornManualConfigurationException(LicornConfigurationException):
	""" Raised when system needs manual intervention of administrator to work properly or activate a feature.
	"""
	errno = 41
	pass

class LicornRuntimeException(LicornException):
	""" [UNSTABLE] Something not expected has happened during program run.
		This is not clear exactly when this exception must be used. beware.  """
	errno = 5
	pass
class LicornStopException(LicornRuntimeException):
	""" Current Thread of function has been stopped and it is unexpected. """
	errno = 501
	pass
class NeedRestartException(LicornRuntimeException):
	""" Daemon needs to restart entirely, else bad things will occur. """
	errno = 502
	def __init__(self, *args, **kwargs):
		LicornRuntimeException.__init__(self, *args, **kwargs)
		self.pid = os.getpid()
class LicornRuntimeError(LicornError):
	""" [UNSTABLE] Something very bad has happened during program run.
		This is not clear exactly when this exception must be used. beware.  """
	errno = 6
	pass
class LicornWebException(LicornRuntimeException):
	errno = 601
	pass
class LicornWebError(LicornRuntimeError):
	errno = 602
	pass
class LicornWebCommandException(LicornWebException):
	errno = 603
	pass
class LicornWebCommandError(LicornWebError):
	errno = 604
	pass

class LicornHarvestException(LicornRuntimeException):
	errno = 510
	pass
class LicornHarvestError(LicornRuntimeError):
	errno = 511
	pass

class LicornCheckError(LicornError):
	""" Something bad happened during a check (licorn-check).  """
	errno = 7
	pass

class LicornSecurityError(LicornRuntimeError):
	""" Something very bad has happened which endangers the program or the system security.  """
	errno = 8
	pass
class LicornSecurityRaceConditionError(LicornSecurityError):
	""" (what could be a) race condition has been detected. It must be manually checked before anything is done.  """
	errno = 9
	pass

class LicornIOException(LicornException):
	""" [UNSTABLE] Something not expected has happened during an I/O.
		This is not clear exactly when this exception must be used. beware.  """
	errno = 10
	pass
class LicornIOError(LicornError):
	""" [UNSTABLE] Something very bad has happened during an I/O.
		This is not clear exactly when this exception must be used. beware.  """
	errno = 11
	pass

class BadArgumentError(LicornRuntimeError):
	""" Raised during command line parsing, when an unknown argument is encountered.  """
	errno = 12
	pass
class BadRequestError(BadArgumentError):
	""" Raised during command line parsing, when an unknown argument is encountered.  """
	errno = 121
	pass
class BadConfigurationError(LicornRuntimeError):
	""" Raised when a configuration directive is missing or when 2 configuration files are not synchronized.  """
	errno = 13
	pass
class InsufficientPermissionsError(LicornRuntimeError):
	""" Raised when someone is not authorized to do something.  """
	errno = 14
	pass

class LicornHookException(LicornException):
	""" a global problem in the hook* code.  """
	errno = 50
	pass
class LicornHookEventException(LicornHookException):
	""" Problem in the hook code, related to events """
	errno = 51
	pass
class LicornHookError(LicornError):
	""" an uncorrectable problem in the hook* code.  """
	errno = 52
	pass
class LicornHookEventError(LicornHookError):
	""" Uncorrectable problem, ie: an event was not found.  """
	errno = 53
	pass

class SystemCommandError(LicornRuntimeError):
	""" A system command has exited with an error."""
	def __init__(self, cmd, errno):
		self.cmd   = cmd
		self.errno = errno
	def __str__(self):
		return "The command `%s` failed (error code %d)." % (self.cmd, self.errno)
class SystemCommandSignalError(LicornRuntimeError):
	""" A system command has exited because it received a signal."""
	def __init__(self, cmd, errno):
		self.cmd   = cmd
		self.errno = errno
	def __str__(self):
		return "Command `%s` terminated by signal %d." % (self.cmd, self.errno)

class CorruptFileError(LicornIOError):
	""" A configuration is corrupt, or is empty and it was attended not to be.  """
	errno = 60
	__filename = ""
	__msg = "" # Error message
	__reason = ""
	def __init__(self, filename="", reason=""):
		self.__filename = filename
		self.__reason = reason
	def SetFilename(self, filename):
		self.__filename = filename
	def __str__(self):
		out = "The file " + self.__filename + " is corrupted"
		if self.__reason != "":
			out += "\nReason: " + self.__reason
		return out
class SGCorruptFileError(CorruptFileError):
	""" [UNSTABLE] squidGuard configuration file is corrupt.
		This error could change when webfilters code is merged in."""
	errno = 61
	pass
class AbsolutePathError(LicornIOError):
	""" [UNSTABLE] really needed ? please comment.  """
	errno = 62
	__path = ""
	__msg = "" # Error message
	def __init__(self, path=""):
		self.__path = path
	def __str__(self):
		return "The path `" + self.__path + "` is not correct. It must be a valid absolute path"
class IndexNotFoundError(LicornIOError):
	""" [UNSTABLE] really needed ? isn't there an existing python class which does the same ? please comment.  """
	errno = 63
	pass

class AlreadyExistsException(LicornRuntimeException):
	""" Raised when an object (user, group, profile) [strictly] already exists.
		The already existing object must be exactly the same (same name, same
		type, same attributes…).
		When this happens, the program can continue and assume the object has
		been created correctly.
	"""
	errno = 100
	pass
class AlreadyExistsError(LicornRuntimeError):
	""" Raised when an object already exists but is not exactly of the same
		type. The creation thus cannot happen, the program must exit, something
		must be done manually to correct the problem.  """
	errno = 101
	pass
class DoesntExistException(LicornRuntimeException):
	""" Raised when an object (user, group, profile) [strictly] doesn't exist,
		but the situation can be recovered at some extend.
	"""
	errno = 102
	pass
class DoesntExistError(LicornRuntimeError):
	""" Raised when an object doesn't exists and the situation is know to be
		completely unrecoverable. """
	errno = 103
	pass
class TimeoutExceededException(LicornRuntimeException):
	""" Raised when a timeout is reached, but the situation can be recovered at
		some extend. """
	errno = 104
	pass
class TimeoutExceededError(LicornRuntimeError):
	""" Raised when a timeout is reached, and the situation is know to be
		completely unrecoverable. """
	errno = 105
	pass

class PathDoesntExistException(DoesntExistException):
	""" Raised when a path doesn't exist,
		but the situation can be recovered or ignored at some extend.
	"""
	errno = 1021
	pass
class NetworkError(LicornError):
	"""Raised when a generic network error is encountered."""
	errno = 201
	pass
class Unreachable(NetworkError):
	"""Raised when a distant machine is unreachable."""
	errno = 202
	pass


class UpstreamBugException(LicornException):
	errno = 127
	""" Raised when your code makes a workaround to circumvent a bug in an external program.
		This Exception is likely to disappear in your code when upstream bug are solved.
	"""
	pass

class NoAvaibleIdentifierError(LicornRuntimeError):
	errno = 300
	""" Raised when there is no gid or uid avaible.
	"""
	pass


class NeedHelpException(LicornRuntimeException):
	""" Raised when user don't specify any argument, in CLI,
		and he/she should have. This exception permits to rerun the argparser
		with help appended, after the first run. """
	errno = 999
	pass
