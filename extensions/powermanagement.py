# -*- coding: utf-8 -*-
"""
Licorn extensions: Power management - http://docs.licorn.org/extensions/powermanagement.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, sys, time
from threading import RLock, Event

from licorn.foundations        import logging, exceptions, process, pyutils
from licorn.foundations.styles import *
from licorn.foundations.ltrace import ltrace
from licorn.foundations.base   import Singleton, MixedDictObject, LicornConfigObject

from licorn.core               import LMC
from licorn.daemon.threads     import LicornJobThread
from licorn.extensions         import LicornExtension
from licorn.extensions.volumes import VolumeException
from licorn.interfaces.wmi     import WMIObject

from licorn.daemon             import priorities, service_enqueue

class PowermanagementException(exceptions.LicornRuntimeException):
	""" A type of exception to deal with rdiff-backup specific problems.

		.. versionadded:: 1.2.4
	"""
	pass
class PowermanagementExtension(Singleton, LicornExtension, WMIObject):
	""" Handle energy and power-saving features on the local host, via multiple
		methods.

		.. versionadded:: 1.3
	"""
	#: the environment variable used to override rdiff-backup configuration
	#: during tests or real-life l33Tz runs.
	module_depends = [ 'gloop' ]

	def __init__(self):
		assert ltrace('powermgmt', '| PowerManagementExtension.__init__()')
		LicornExtension.__init__(self, name='powermgmt')

		self.controllers_compat = [ 'system' ]
	def initialize(self):
		""" Return True if :command:`rdiff-backup` is installed on the local
			system.
		"""

		assert ltrace(self.name, '> initialize()')

		if False:
			self.available = True

		else:
			logging.warning2('%s: not available because yet to be written.' % self.name)

		assert ltrace(self.name, '< initialize(%s)' % self.available)
		return self.available
	def is_enabled(self):
		""" the :class:`RdiffbackupExtension` is enabled when the
			:mod:`~licorn.extensions.volumes` extension is available (we need
			volumes to backup onto).

			If we are enabled, create a :class:`RdiffbackupThread` instance
			to be later collected and started by the daemon.
		"""
		if 'gloop' in LMC.extensions:

			"""
			self.create_wmi_object(uri='/energy', name=_('Energy'),
				alt_string=_('Manage Energy and network-wide power-saving preferences'),
				context_menu_data=(
					(_('Run backup'), '/backups/run',
						_('Run a system incremental backup now'),
						'ctxt-icon', 'icon-add',
						lambda: self._enabled_volumes() != []
							and not self.running()),
					(_('Rescan volumes'), '/backups/rescan',
						_('Force the system to rescan and remount connected '
						'volumes'),
						'ctxt-icon', 'icon-energyprefs',
						lambda: self._backup_enabled_volumes() == [])
				)
			)
			"""
			return True

		return False
	def system_load(self):
		""" TODO. """

		#TODO: refresh statistics.

		return True
	def _wmi__status(self):
		""" Method called from wmi:/, to integrate backup informations on the
			status page. """

		return '<strong>NOTHING YET</strong>'
