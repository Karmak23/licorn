# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

objects - ultra basic objects, used as base classes.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import sys, os, time
import Pyro.core, Pyro.util

from Queue              import Queue
from threading          import Thread, Event

# PLEASE do not import "logging" here.
import exceptions, styles
from ltrace    import ltrace
from constants import message_type, verbose, interactions

class LicornConfigObject():
	""" a base class just to be able to add/remove custom attributes
		to other custom attributes (build a tree simply).
	"""
	def __init__(self, fromdict={}, level=1):
		for key in fromdict.keys():
			setattr(self, key, fromdict[key])
		self._level = level
	def __str__(self):
		data = ""
		for i in self.__dict__:
			if i[0] == '_': continue
			if type(getattr(self, i)) == type(self):
				data += u'%s\u21b3 %s:\n%s' % ('\t'*self._level, i, str(getattr(self, i)))
			else:
				data += u"%s\u21b3 %s = %s\n" % ('\t'*self._level, str(i), str(getattr(self, i)))
		return data
	def __iter__(self):
		""" make this object sequence-compatible, for use in
			LicornConfiguration(). """
		for attribute_name in dir(self):
			if attribute_name[0] != '_':
				yield getattr(self, attribute_name)
class Singleton(object):
	__instances = {}
	def __new__(cls, *args, **kargs):
		if Singleton.__instances.get(cls) is None:
			Singleton.__instances[cls] = object.__new__(cls)
		#ltrace('objects', 'Singleton 2.6+: %s:%s.' % (cls, Singleton.__instances[cls]))
		return Singleton.__instances[cls]
class FileLock:
	"""
		This FileLock class is a reimplementation of basic locks with files.
		This is needed to be compatible with adduser/login binaries, which
		use /etc/{passwd,group}.lock to signify that the system files are locked.

	"""

	def __init__(self, configuration, filename = None, waitmax = 10, verbose = True):

		# TODO: don't blow up if user_dir isn't set (which is the case for daemon user)

		self.pretty_name = str(self.__class__).rsplit('.', 1)[1]

		if filename is None :
			raise exceptions.LicornRuntimeError("please specify a file to lock")

		if filename[0] == '/':
			self.filename = filename + '.lock'
			self.lockname = filename.rsplit('/', 1)[1]
		else:
			self.filename = "%s/%s.lock" % (configuration.user_dir, filename)
			self.lockname = filename

		assert ltrace('objects', '%s: new instance with %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.filename)))

		self.waitmax = waitmax
		self.wait    = waitmax
		self.verbose = verbose

	#
	# Make FileLock be usable as a context manager.
	#
	def __enter__(self):
		self.Lock()
	def __exit__(self, type, value, tb):
		self.Unlock()

	def Lock(self):
		"""Acquire a lock, i.e. create $file.lock."""
		assert ltrace('objects', '%s: pseudo-locking %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.lockname)))

		try:
			self.wait = self.waitmax
			while os.path.exists(self.filename) and self.wait >= 0:
				if self.verbose:
					sys.stderr.write("\r %s waiting %d second(s) for %s lock to be released… " \
						% (styles.stylize(styles.ST_NOTICE, '*'), self.wait, self.lockname))
					sys.stderr.flush()
				self.wait = self.wait - 1
				time.sleep(1)

			if self.wait <= 0:
				sys.stderr.write("\n")
				raise IOError, "%s lockfile still present, can't acquire lock after timeout !" % self.lockname

			else:
				try:
					open(self.filename, "w")
				except (IOError, OSError):
					raise IOError, "Can't create lockfile %s." % self.filename

		except KeyboardInterrupt:
			sys.stderr.write("\n")
			raise

		assert ltrace('objects', '%s: successfully locked %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.filename)))

	def Unlock(self):
		"""Free the lock by removing the associated lockfile."""

		assert ltrace('objects', '%s: removing lock on %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.lockname)))

		if os.path.exists(self.filename):
			try:
				os.unlink(self.filename)
			except (OSError):
				raise OSError, "can't remove lockfile %s." % self.filename

		assert ltrace('objects', '%s: successfully unlocked %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.filename)))

	def IsLocked(self):
		"""Tell if a file is currently locked by looking if the associated lock
		is present."""
		return os.path.exists(self.filename)
class UGMBackend(Pyro.core.ObjBase):
	"""
		Abstract backend class allowing access to users and groups data. The
		UGMBackend presents an homogeneous API for operations on these
		objects at a system level.

		Please refer to http://dev.licorn.org/wiki/DynamicUGMBackendSystem for
		a more general documentation.
	"""

	def __str__(self):
		return self.name
	def __repr__(self):
		return self.name
	def __init__(self, configuration, users=None, groups=None, warnings=True):

		Pyro.core.ObjBase.__init__(self)

		self.name      = "UGMBackend"

		assert ltrace('objects', '| UGMBackend.__init__()')

		self.users         = None
		self.groups        = None
		self.machines      = None

		# abstract defaults
		self.warnings      = warnings
		self.available     = False
		self.enabled       = False
		self.compat        = ()
		self.priority      = 0
		self.plugins       = {}


		self.configuration = configuration

		if users:
			self.set_users_controller(users)

		if groups:
			self.set_groups_controller(groups)

		#
		# everything else __init__() should be done by a real implementation.
		#

		return False
	def enable(self):
		return False
	def disable(self):
		return False
	def initialize(self, active=True):
		"""
		For an abstract backend, initialize() always return False.

		"active" is filled by core.configuration and gives a hint about the
		system configuration:
			- active will be true if the underlying system is configured to
				use the backend. That doesn't imply the backend CAN be used,
				for exemple on a partially configured system.
			- active will be false if the backend is deactivated in the system
				configuration. The backend can be fully operationnal anyway. In
				this case "active" means that the backend will be used (or not)
				by Licorn.

		"""

		# return "self".enabled instead of UGMBackend.enabled, to get the
		# instance attribute, if modified.
		return self.enabled
	def check(self, batch=False, auto_answer=None):
		""" default check method. """
		pass
	def set_users_controller(self, users):
		""" save a reference of the UsersController for future use. """
		self.users = users
		if users.groups is not None:
			self.groups = users.groups
	def set_groups_controller(self, groups):
		""" save a reference of the GroupsController for future use. """
		self.groups = groups
		if groups.users is not None:
			self.users = groups.users
	def set_machines_controller(self, machines):
		self.machines = machines
	def connect_plugin(self, plugin):
		""" """
		assert ltrace('objects', '| UGMBackend.connect_plugin()')

		if self.name in plugin.backend_compat:
			assert ltrace('objects', '  UGMBackend.connect_plugin(%s <-> %s)' % (
				self.name, plugin.name))
			self.plugins[plugin.name] = plugin
			plugin.set_backend(self)
			return True
		return False
	def load_defaults(self):
		""" A real backend will setup its own needed attributes with values
		*strictly needed* to work. This is done in case these values are not
		present in configuration files.

		Any configuration file containing these values, will be loaded
		afterwards and will overwrite these attributes. """
		pass
	def load_machines(self):
		""" gather the list of all known machines on the system. """

		assert ltrace('objects', '| UGMBackend.load_machines(%s)' % self.plugins)

		for p in self.plugins:
			if self.plugins[p].purpose == 'machines':
				# the first plugin found is the good, don't try others.
				return self.plugins[p].load_machines()

		return {}, {}
	def save_users(self):
		""" Take all users from UGMBackend.users (typically in a for loop) and
		save them into the backend. """
		pass
	def save_groups(self):
		""" Take all groups from UGMBackend.groups (typically in a for loop) and
		save them into the backend. """
		pass
	def save_machines(self):
		""" Take all machines from UGMBackend.machines (typically in a for loop)
		and	save them into the backend. """
		pass
	def save_user(self, uid):
		""" save one user into the backend. Useful on system which have loads
		of users/groups, to avoid saving all of them when there is only a small
		update.	"""
		pass
	def save_group(self, gid):
		""" save one group into the backend. Useful on system which have loads
		of users/groups, to avoid saving all of them when there is only a small
		update.	"""
		pass
	def save_machine(self, mid):
		""" save one machine into the backend. Useful on system which have loads
		of machines, to avoid saving all of them when there is only a small
		update.	"""
		pass
	def save_all(self, users=None, groups=None, machines=None):
		""" Save all internal data to backend. This is just a wrapper. """
		self.save_users()
		self.save_groups()
		self.save_machines()
	def compute_password(self, password):
		""" Encode a password in a way the backend can understand.
		For example the unix backend will use crypt() function, whereas
		the LDAP backend will use the SHA1 hash only with a base64 encoding and
		a '{SHA}' text header. """
		pass
class StateMachine:
	"""
		A Finite state machine design pattern.
		Found at http://www.ibm.com/developerworks/library/l-python-state.html , thanks to David Mertz.
	"""
	def __init__(self):
		self.handlers = {}
		self.startState = None
		self.endStates = []

	def add_state(self, name, handler, end_state = False):
		self.handlers[name] = handler
		if end_state:
			 self.endStates.append(name)

	def set_start(self, name):
		self.startState = name

	def run(self, data):
		try:
			 handler = self.handlers[self.startState]
		except:
			 raise exceptions.LicornRuntimeError("LSM: must call .set_start() before .run()")

		if not self.endStates:
				 raise exceptions.LicornRuntimeError("LSM: at least one state must be an end_state.")

		while True:
			(newState, data) = handler(data)
			if newState in self.endStates:
				break
			else:
				handler = self.handlers[newState]
class MessageProcessor(Pyro.core.CallbackObjBase):
	channels = {
		1:	sys.stdout,
		2:	sys.stderr,
		}

	def __init__(self, verbose=verbose.NOTICE):
		Pyro.core.CallbackObjBase.__init__(self)
		self.verbose = verbose
		assert ltrace('objects', '| MessageProcessor(%s)' % self.verbose)
	def process(self, message, callback):
		""" process a message. """

		if message.type == message_type.EMIT:
			# We are in the server, the message has just been built.
			# Forward it nearly "as is". Only the message type is changed,
			# to make us know it has been processed one time since emission,
			# and thus the next hop will be the client, which has the task
			# to display it, and eventually get an interactive answer.

			assert ltrace('objects', '  MessageProcessor.process(EMIT)')

			if message.interaction:

				from ttyutils import interactive_ask_for_repair

				if message.interaction == interactions.ASK_FOR_REPAIR:

					message.answer = interactive_ask_for_repair(message.data,
						auto_answer=message.auto_answer)
				else:
					assert ltrace('objects',
						'unsupported interaction type in message %s.' % message)
					message.answer = None
			else:
				MessageProcessor.channels[message.channel].write(message.data)
				message.answer = None

			message.type   = message_type.ANSWER
			return callback.process(message, self.getAttrProxy())
		else: # message_type.ANSWER
			# We are on the server, this is the answer from the client to
			# ourquestion. Return it directly to the calling process. The
			# message loop ends here.

			assert ltrace('objects', '  MessageProcessor.process(ANSWER)')

			#message.channel.write(message.data)
			return message.answer
class LicornMessage(Pyro.core.CallbackObjBase):
	def __init__(self, my_type=message_type.EMIT, data='', interaction=None,
		answer=None, auto_answer=None, channel=2):

		Pyro.core.CallbackObjBase.__init__(self)

		assert ltrace('objects', '''| LicornMessage(data=%s,type=%s,interaction=%s,'''
			'''answer=%s,auto_answer=%s,channel=%s)''' % (data, my_type,
			interaction, answer, auto_answer, channel))

		self.data = data
		self.type = my_type
		self.interaction = interaction
		self.answer = answer
		self.auto_answer = auto_answer
		self.channel = channel
