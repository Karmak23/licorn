# -*- coding: utf-8 -*-
"""
Licorn core.backends - http://docs.licorn.org/core/backends.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2

.. versionadded:: 1.2
	the backend management facility appeared during the 1.1 ⇢ 1.2 development
	cycle.
"""

import os

from licorn.foundations        import logging
from licorn.foundations.styles import *
from licorn.foundations.ltrace import ltrace
from licorn.foundations.base   import Singleton, MixedDictObject

from licorn.core         import LMC
from licorn.core.classes import ModuleManager

class BackendsManager(Singleton, ModuleManager):
	""" Handles backend management. """

	#: BackendsManager has no special protected attrs, it uses the ones
	#: from its parent, the :class:`ModuleManager`.
	_licorn_protected_attrs = ModuleManager._licorn_protected_attrs

	def __init__(self):
		assert ltrace('backends', '__init__()')
		ModuleManager.__init__(self, name='backends', module_type='backend',
			module_path=__path__[0], module_sym_path='licorn.core.backends')
	def enable_backend(self, backend_name):
		""" Enable a given backend, then call
			:meth:`~LMC.reload_controllers_backends`. Enabling the backend
			will probably modify system files or services, but whatever is done
			is different from a backend to another."""

		assert ltrace(self.name, '| enable_backend(%s)' % backend_name)
		ModuleManager.enable_module(self, backend_name)
		LMC.reload_controllers_backends()
	def disable_backend(self, backend_name):
		""" Disable a given backend,  then call
			:meth:`~LMC.reload_controllers_backends`. What is effectively
			done by the backend disabling itself is different from a
			backend to another."""

		assert ltrace(self.name, '| disable_backend(%s)' % backend_name)
		ModuleManager.disable_module(self, backend_name)
		LMC.reload_controllers_backends()
