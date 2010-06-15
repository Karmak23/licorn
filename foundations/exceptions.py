# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""
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
class LicornConfigurationException (LicornException):
	""" Raised when a fatal configuration error is encountered.

		This exception is used when parsing a configuration file can't be done,
		or if a configuration directive needed by Licorn is missing.
	"""
	errno = 3
	pass
class LicornConfigurationError (LicornError):
	""" Raised when a correctable configuration problem is encountered.

		This exception is used when parsing a configuration file can't be done,
		or if a configuration directive needed by Licorn is missing.
	"""
	errno = 4
	pass
class LicornManualConfigurationException (LicornConfigurationException):
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

class AlreadyExistsException(LicornException):
	""" Raised when an object (user, group, profile) [strictly] already exists.
		The already existing object must be exactly the same (same name, same type, same attributes...).
		When this happens, the program can continue and assume the object has been created correctly.
	"""
	errno = 100
	pass
class AlreadyExistsError(LicornError):
	""" Raised when an object already exists but is not exactly of the same type.
		The creation thus cannot happen, the program must exit, something must be done manually
		to correct the problem.  """
	errno = 101
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
