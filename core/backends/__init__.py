# -*- coding: utf-8 -*-
"""
Licorn core.backends autoload facility.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os

from licorn.foundations        import logging
from licorn.foundations.styles import *
from licorn.foundations.ltrace import ltrace
from licorn.foundations.base   import Singleton, MixedDictObject

from licorn.core         import LMC
from licorn.core.classes import ModuleManager

class BackendsManager(Singleton, ModuleManager):
	_licorn_protected_attrs = ModuleManager._licorn_protected_attrs
	def __init__(self):
		assert ltrace('backends', '__init__()')
		ModuleManager.__init__(self, name='backends', module_type='backend',
			module_path=__path__[0], module_sym_path='licorn.core.backends')
	def enable_backend(self, backend_name):
		""" try to enable a given backend. what to do exactly is left to the
		backend itself."""

		assert ltrace(self.name, '| enable_backend(%s)' % backend_name)
		ModuleManager.enable_module(self, backend_name)
		LMC.reload_controllers_backends()
	def disable_backend(self, backend_name):
		""" try to disable a given backend. what to do exactly is left to the
		backend itself."""

		assert ltrace(self.name, '| disable_backend(%s)' % backend_name)
		ModuleManager.disable_module(self, backend_name)
		LMC.reload_controllers_backends()
