# -*- coding: utf-8 -*-
"""
Licorn extensions: Power management - http://docs.licorn.org/extensions/powermanagement.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, sys, time
from licorn.foundations.threads import RLock, Event

from licorn.foundations           import logging, exceptions, process, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, MixedDictObject, LicornConfigObject
from licorn.foundations.constants import priorities

from licorn.core               import LMC
from licorn.daemon.threads     import LicornJobThread
from licorn.extensions         import LicornExtension

class PowermanagementException(exceptions.LicornRuntimeException):
	""" A type of exception to deal with rdiff-backup specific problems.

		.. versionadded:: 1.2.4
	"""
	pass
class PowermanagementExtension(ObjectSingleton, LicornExtension):
	""" Handle energy and power-saving features on the local host, via multiple
		methods.

		.. versionadded:: 1.3
	"""
	#: the environment variable used to override rdiff-backup configuration
	#: during tests or real-life l33Tz runs.
	module_depends = [ 'gloop' ]

	def __init__(self):
		assert ltrace(TRACE_POWERMGMT, '| PowerManagementExtension.__init__()')
		LicornExtension.__init__(self, name='powermgmt')

		self.controllers_compat = [ 'system' ]
	def initialize(self):
		""" Return True if :command:`rdiff-backup` is installed on the local
			system.
		"""

		assert ltrace(globals()['TRACE_' + self.name.upper()], '> initialize()')

		if False:
			self.available = True

		else:
			logging.warning2(_(u'%s: extension not available because yet to be written.') % stylize(ST_NAME, self.name))

		assert ltrace(globals()['TRACE_' + self.name.upper()], '< initialize(%s)' % self.available)
		return self.available
	def is_enabled(self):
		""" the :class:`RdiffbackupExtension` is enabled when the
			:mod:`~licorn.extensions.volumes` extension is available (we need
			volumes to backup onto).

			If we are enabled, create a :class:`RdiffbackupThread` instance
			to be later collected and started by the daemon.
		"""
		if 'gloop' in LMC.extensions:
			return True

		return False
	def system_load(self):
		""" TODO. """

		#TODO: refresh statistics.

		return True
