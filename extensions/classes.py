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

class CoreExtension(CoreUnitObject):
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
