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
from licorn.core.classes       import CoreModule

class CoreBackend(CoreModule):
	def __init__(self, name='core_backend', controllers_compat=[]):
		CoreModule.__init__(self, name=name,
			controllers_compat=controllers_compat, manager=LMC.backends)
		assert ltrace('backends', '| CoreBackend.__init__(%s)' %
			controllers_compat)
class NSSBackend(CoreBackend):
	def __init__(self, name='nss', nss_compat=(), priority=0):
		CoreBackend.__init__(self, name=name,
			controllers_compat=['users', 'groups'])
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
	def __init__(self, name='machines'):
		CoreBackend.__init__(self, name=name, controllers_compat=['machines'])
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

