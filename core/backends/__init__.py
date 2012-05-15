# -*- coding: utf-8 -*-
"""
Licorn core: backends - http://docs.licorn.org/core/backends.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2

a backend should implement the following methods:
	initialize()
	enable()
	disable()
	check()
	load_<Object>() where Object is the name of the object used in the
		controller, eg 'User', 'Group', 'Machine'
	save_<Object>()
	save_<Object>s()
	compute_password() for users

.. versionadded:: 1.2
	the backend management facility appeared during the 1.1 ⇢ 1.2 development
	cycle.
"""

import os

from licorn.foundations           import logging, settings
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import DictSingleton
from licorn.foundations.constants import priorities
from licorn.core                  import LMC
from licorn.core.classes          import ModulesManager, CoreModule
from licorn.foundations.events import LicornEvent

class BackendsManager(DictSingleton, ModulesManager):
	""" Handles backend management. """

	#: BackendsManager has no special protected attrs, it uses the ones
	#: from its parent, the :class:`ModulesManager`.
	_licorn_protected_attrs = ModulesManager._licorn_protected_attrs

	def __init__(self):
		assert ltrace(TRACE_BACKENDS, '__init__()')
		ModulesManager.__init__(self, name='backends', module_type='backend',
			module_path=__path__[0], module_sym_path='licorn.core.backends')
	def enable_backend(self, backend_name):
		""" Enable a given backend, then call
			:meth:`~licorn.core.LicornMasterController.reload_controllers_backends`.
			Enabling the backend
			will probably modify system files or services, but whatever is done
			is different from a backend to another."""

		assert ltrace_func(TRACE_BACKENDS)

		if ModulesManager.enable_module(self, backend_name):
			LicornEvent('backend_enabled', backend=self[backend_name]).emit(priorities.HIGH)
			return True

		return False
	enable_func = enable_backend
	def disable_backend(self, backend_name):
		""" Disable a given backend,  then call
			:meth:`~licorn.core.LicornMasterController.reload_controllers_backends`.
			What is effectively
			done by the backend disabling itself is different from a
			backend to another."""

		assert ltrace_func(TRACE_BACKENDS)

		if ModulesManager.disable_module(self, backend_name):
			LicornEvent('backend_disabled', backend=self[backend_name]).emit(priorities.HIGH)
			return True

		return False
	disable_func = disable_backend
class CoreBackend(CoreModule):
	def __init__(self, name='core_backend', controllers_compat=[]):
		CoreModule.__init__(self, name=name,
			controllers_compat=controllers_compat, manager=LMC.backends)
		assert ltrace(TRACE_BACKENDS, '| CoreBackend.__init__(%s)' %
			controllers_compat)
	#~ def __str__(self):
		#~ return 'backend %s' % stylize(ST_NAME, self.name)
	def load(self, server_modules, batch=False, auto_answer=None):
		""" TODO. """
		if self.initialize():
			self.enabled = self.is_enabled()
class NSSBackend(CoreBackend):
	def __init__(self, name='nss', nss_compat=(), priority=0):
		CoreBackend.__init__(self, name=name,
			controllers_compat=['users', 'groups'])
		assert ltrace(TRACE_BACKENDS, '| NSSBackend.__init__(%s, %s)' % (nss_compat,
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
	""" Abstract user backend class allowing access to users data.

		A user backend should implement those methods:

		* `load_User(uid)`
		* `save_User(user, mode)`
		* `delete_User(user)`
		* `load_Users()`
		* `save_Users(users)`

	"""
	pass
class GroupsBackend(NSSBackend):
	"""	Abstract groups backend class allowing access to groups data.

		A group backend should implement those methods:

		* `load_Group(gid)`
		* `save_Group(group, mode)`
		* `delete_Group(group)`
		* `load_Groups()`
		* `save_Groups(groups)`

	"""
	pass
class MachinesBackend(CoreBackend):
	""" Abstract machines backend class allowing access to machines data.

		.. versionadded:: 1.3
	"""
	def __init__(self, name='machines'):
		CoreBackend.__init__(self, name=name, controllers_compat=['machines'])
		assert ltrace(TRACE_OBJECTS, '| MachinesBackends.__init__()')
	def load_Machine(self, mid):
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		assert ltrace_func(TRACE_BACKENDS)

		return self.load_Machines()
	def save_Machine(self, mid, mode):
		""" Write the groups data in appropriate system files."""

		assert ltrace_func(TRACE_BACKENDS)

		return self.save_Machine()
	def delete_Machine(self, mid):
		assert ltrace_func(TRACE_BACKENDS)
		pass

class TasksBackend(CoreBackend):
	def __init__(self, name='tasks'):
		CoreBackend.__init__(self, name=name, controllers_compat=['tasks'])
		assert ltrace(TRACE_OBJECTS, '| TasksBackends.__init__()')
		