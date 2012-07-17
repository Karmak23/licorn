# -*- coding: utf-8 -*-
"""
Licorn extensions: Power management - http://docs.licorn.org/extensions/powermanagement.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, sys, time, dbus, errno

from licorn.foundations.threads import RLock, Event

from licorn.foundations           import logging, exceptions
from licorn.foundations           import process, pyutils, events

from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, \
											MixedDictObject, \
											LicornConfigObject, \
											Enumeration, EnumDict
from licorn.foundations.constants import priorities

from licorn.core               import LMC
from licorn.daemon.threads     import LicornJobThread
from licorn.extensions         import LicornExtension

LicornEvent = events.LicornEvent

dbus_pretty_name = stylize(ST_NAME, 'dbus')

power_types = EnumDict('power_types', from_dict={
	# from http://upower.freedesktop.org/docs/Device.html#Device:Type
	# as of 2012-07-12.
	'UNKNOWN'    : 0,
	'LINE_POWER' : 1,
	'BATTERY'    : 2,
	'UPS'        : 3,
	'MONITOR'    : 4,
	'MOUSE'      : 5,
	'KEYBOARD'   : 6,
	'PDA'        : 7,
	'PHONE'      : 8,
})

class PowermanagementException(exceptions.LicornRuntimeException):
	""" A type of exception to deal with rdiff-backup specific problems.

		.. versionadded:: 1.2.4
	"""
	pass
class PowermanagementExtension(ObjectSingleton, LicornExtension):
	""" Handle energy and power-saving features on the local host, via multiple
		methods.

		.. versionadded:: 1.4.5+ This extension was present but not implemented
			at all before. In 1.4.5, the first implementation listens to
			`upower` dbus signals and forwards them inside Licorn® by turning
			them into :class:`~licorn.foundations.events.LicornEvent`.
	"""

	module_depends = [ 'gloop' ]

	def __init__(self):
		assert ltrace_func(TRACE_POWERMGMT)

		LicornExtension.__init__(self, name='powermgmt')

		self.controllers_compat = [ 'system' ]
	def initialize(self):
		""" Return True if :command:`rdiff-backup` is installed on the local
			system.
		"""

		assert ltrace_func(TRACE_POWERMGMT)

		if 'gloop' in LMC.extensions and LMC.extensions.gloop.dbus.system_bus:
			self.bus = LMC.extensions.gloop.dbus.system_bus

			self.available = True

			self.__setup_messages_handlers()
			self.__setup_upower()
		else:
			self.available = False

		return self.available
	def is_enabled(self):
		""" the :class:`RdiffbackupExtension` is enabled when the
			:mod:`~licorn.extensions.volumes` extension is available (we need
			volumes to backup onto).

			If we are enabled, create a :class:`RdiffbackupThread` instance
			to be later collected and started by the daemon.
		"""

		if self.available:

			version        = self.upower.props('DaemonVersion')
			self.__has_lid = self.upower.props('LidIsPresent')

			#self.udisks.cookie = self.udisks.interface.Inhibit()

			logging.info(_(u'{0}: extension enabled{1}, on top of '
							u'{2} v{3}.').format(self.pretty_name,
								stylize(ST_COMMENT, _(' with laptop mode'))
									if self.__has_lid else u'',
								stylize(ST_NAME, 'UPower'),
								stylize(ST_UGID, version)))

			return True

		logging.info(_(u'{0}: extension disabled because either {1} disabled '
						u'or {2} not connected.').format(self.pretty_name,
							LMC.extensions.gloop.pretty_name, dbus_pretty_name))
		return False
	@property
	def is_laptop(self):
		return self.__has_lid
	@property
	def on_battery(self):
		return self.upower.props('OnBattery')
	@property
	def on_low_battery(self):
		return self.upower.props('OnLowBattery')
	@property
	def battery_level(self):
		if self.__has_lid and self.battery.property('IsPresent'):
			return self.battery.property('Percentage')
		return -1
	def upower_catchall_signal_handler(self, device=None, dbus_message=None):
		""" Receive all UPower related messages, and eventually use them
			to update the extension properties. """
		# NOTE: device will be None when the 'Changed' debus message concerns
		# the UPower interface globally.
		#
		# When power is plugged in/out, there are 2 messages:
		#	- None 		> Changed
		#	- …ADAPT0 	> Changed

		member = dbus_message.get_member()

		logging.progress(_(u'{0}: UPower message{1}: {2}').format(
								self.pretty_name,
								_(' for device {0}').format(
										stylize(ST_NAME, device)
									) if device else u'',
								stylize(ST_ATTR, member)))

		if device is None and member != 'Changed':
			sleeping = member == 'Sleeping'
			logging.info(_(u'{0}: system is {1}, broadcasting information.').format(
							self.pretty_name,
							stylize(ST_BAD, _('going to sleep'))
								if sleeping
								else stylize(ST_OK, _(u'resuming from suspend'))))
			LicornEvent('system_%s' % member.lower()).emit(priorities.HIGH)

	def __setup_upower(self):

		self.upower = Enumeration(name='upower')

		try:
			self.upower.obj = self.bus.get_object(
									"org.freedesktop.UPower",
									"/org/freedesktop/UPower")
		except:
			self.upower.obj = None

		else:
			self.upower.interface = dbus.Interface(self.upower.obj,
										'org.freedesktop.UPower')
			self.upower.properties = dbus.Interface(self.upower.obj,
												dbus.PROPERTIES_IFACE)
			self.upower.props = lambda x: self.upower.properties.Get(
										'org.freedesktop.UPower', x)

		self.__setup_power_sources()
	def __setup_power_sources(self):

		self.battery       = None
		self.adapter       = None
		self.power_sources = []

		def create_source(device):
			""" For a very special reason, we cannot do the contents of
				this function inside the for loop: we get a variable collision
				on the `_props` attribute in the `lamdba`. Either I missed
				something in the Python documentation about variable scope,
				either there is a bug somewhere. And it could be in my head.
			"""
			source           = Enumeration(name=device.rsplit('/', 1)[1])
			source.device    = device
			source.dev_name  = device.replace('/', '.')[1:]
			source.obj       = self.bus.get_object('org.freedesktop.UPower', device)
			source.interface = dbus.Interface(source.obj, source.dev_name)
			source._props    = dbus.Interface(source.obj, dbus.PROPERTIES_IFACE)
			source.property  = lambda x: source._props.Get(source.dev_name, x)

			return source

		for device in self.upower.interface.EnumerateDevices():
			source = create_source(device)
			self.power_sources.append(source)
			source_type = source.property('Type')

			if source_type == power_types.LINE_POWER and not self.adapter:
				self.adapter = source

			elif source_type == power_types.BATTERY and not self.battery:
				self.battery = source
	def __setup_messages_handlers(self):

		self.bus.add_signal_receiver(self.upower_catchall_signal_handler,
							dbus_interface="org.freedesktop.UPower",
							message_keyword='dbus_message')

__all__ = ('PowermanagementExtension', 'PowermanagementException', 'power_types', )
