# -*- coding: utf-8 -*-
"""
Licorn extensions - http://docs.licorn.org/extensions.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os

from licorn.foundations        import logging
from licorn.foundations.styles import *
from licorn.foundations.ltrace import ltrace
from licorn.foundations.base   import Singleton, MixedDictObject

from licorn.core               import LMC
from licorn.core.classes       import ModulesManager, CoreModule

class ExtensionsManager(Singleton, ModulesManager):
	""" Handle licorn extensions. Extensions can "extend" :ref:`CoreController`s
		(ex. configuration) or :ref:`CoreObject`s (ex. :class:`User` or
		:class:`Group`). """
	def __init__(self):
		assert ltrace('extensions', '| __init__()')
		ModulesManager.__init__(self, name='extensions', module_type='extension',
			module_path=__path__[0], module_sym_path='licorn.extensions')
class LicornExtension(CoreModule):
	def __init__(self, name='extension', controllers_compat=[]):
		CoreModule.__init__(self, name=name, manager=LMC.extensions,
			controllers_compat=controllers_compat)
		assert ltrace('extensions', '| LicornExtension.__init__(%s)' % compat)
