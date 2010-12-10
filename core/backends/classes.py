# -*- coding: utf-8 -*-
"""
Licorn Core backends classes.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>, <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.

a backend should implement the following methods:
	initialize()
	enable()
	disable()
	check()
	load_<Object>() where Object is the name of the object used in the
		controller, eg 'User', 'Group', 'Machine'
	save_<Object>()
	compute_password() for users

"""

from licorn.foundations.ltrace import ltrace
from licorn.core               import LMC
from licorn.core.classes       import CoreUnitObject

class CoreBackend(CoreUnitObject):
	def __init__(self, name='core_backend', compat=[], warnings=True):
		CoreUnitObject.__init__(self, name=name, controller=LMC.backends)
		assert ltrace('backends', '| CoreBackend.__init__(%s)' % compat)

		# abstract defaults
		self.available  = False
		self.enabled    = False
		self.controllers_compat = compat
	def __str__(self):
		return self.name
	def __repr__(self):
		return str(self.__class__)
	def load(self):
		assert ltrace(self.name, '| load()')
		if self.initialize():
			self.enabled = self.is_enabled()
	def generate_exception(extype, *args, **kwargs):
		""" generic mechanism for exception generation (every backend can
		implement only the exceptions he handles). """

		assert ltrace('backends', '| generate_exception(%s,%s,%s)' % (
			extype, args, kwargs))

		# it's up to the developper to implement the right methods, don't
		# enclose the getattr() call in try .. except.
		assert hasattr(self, 'genex_' % extype)

		getattr(self, 'genex_' % extype)(*args, **kwargs)
	def is_enabled(self):
		""" in standard operations, this method checks if the backend can be
			enabled (in particular conditions). but the abstract method of the
			base class just return self.enabled, for backends which don't make
			a difference between available and enabled. """
		assert ltrace(self.name, '| is_enabled(%s)' % self.available)
		return self.available
	def enable(self):
		assert ltrace(self.name, '| enable(False)')
		return False
	def disable(self):
		assert ltrace(self.name, '| disable(True)')
		return True
	def initialize(self):
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

		assert ltrace(self.name, '| initialize(%s)' % self.available)
		return self.available
	def check(self, batch=False, auto_answer=None):
		""" default check method. """
		assert ltrace(self.name, '| ckeck(%s)' % batch)
		pass
	def load_defaults(self):
		""" A real backend will setup its own needed attributes with values
		*strictly needed* to work. This is done in case these values are not
		present in configuration files.

		Any configuration file containing these values, will be loaded
		afterwards and will overwrite these attributes. """
		pass
class NSSBackend(CoreBackend):
	def __init__(self, name='nss', nss_compat=(), priority=0, warnings=True):
		CoreBackend.__init__(self, name, compat=['users', 'groups'],
			warnings=warnings)
		assert ltrace('backends', '| NSSBackend.__init__(%s, %s)' % (nss_compat,
			priority))

		self.nss_compat = nss_compat
		self.priority   = priority
	def is_enabled(self):
		for val in LMC.configuration.nsswitch['passwd']:
			if val in self.nss_compat:
				return True
		return False
# The following classes are used in controllers to dertermine if a given backend
# is compatible with the controller or not. It is up to the real backend to
# implement necessary methods, these abstract backends contain nothing.
class UsersBackend(NSSBackend):
	""" Abstract user backend class allowing access to users data. """
	def load_User(self, uid):
		""" Load user accounts from /etc/{passwd,shadow} """

		assert ltrace('backends', '| abstract load_User(%s)' % uid)

		# NOTE: which is totally ignored in this backend, we always load ALL
		# users, because we always read/write the entire files.

		return self.load_Users()
	def save_User(self, uid, mode):
		""" Write /etc/passwd and /etc/shadow """

		assert ltrace('backends', '| abstract save_User(%s)' % uid)
		return self.save_Users()
	def delete_User(self, uid):
		assert ltrace('backends', '| abstract delete_User(%s)' % uid)
		return self.save_Users()
class GroupsBackend(NSSBackend):
	"""	Abstract groups backend class allowing access to groups data. """
	def load_Group(self, gid):
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		assert ltrace('backends', '| abstract load_Group(%s)' % gid)

		return self.load_Groups()
	def save_Group(self, gid, mode):
		""" Write the groups data in appropriate system files."""

		assert ltrace('backends', '| abstract save_Group(%s)' % gid)

		return self.save_Groups()
	def delete_Group(self, gid):
		assert ltrace('backends', '| abstract delete_Group(%s)' % gid)
		return self.save_Groups()
class MachinesBackend(CoreBackend):
	""" Abstract machines backend class allowing access to machines data. """
	def __init__(self, name='machines', warnings=True):
		CoreBackend.__init__(self, name=name, compat=['machines'],
			warnings=warnings)
		assert ltrace('objects', '| MachinesBackends.__init__()')
	def load_Machine(self, mid):
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		assert ltrace('backends', '| abstract load_Machine(%s)' % mid)

		return self.load_Machines()
	def save_Machine(self, mid, mode):
		""" Write the groups data in appropriate system files."""

		assert ltrace('backends', '| abstract save_Machine(%s)' % mid)

		return self.save_Machine()
	def delete_Machine(self, mid):
		assert ltrace('backends', '| abstract delete_Machine(%s)' % mid)
		pass

