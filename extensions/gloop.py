# -*- coding: utf-8 -*-
"""
Licorn extensions: GLoop - http://docs.licorn.org/extensions/gloop

* the first purpose of this extension is to provide a dbus/gobject mainloop
  outside of the licorn daemon `MainThread`, for enhanced flexibility.

.. note:: This extension is named after 'gloop' because naming it 'dbus'
	produces awful results and import cycles (conflict with standard dbus
	python module).

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os
from threading import Thread

import gobject
import dbus.mainloop.glib

from licorn.foundations           import exceptions, logging, styles
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, Enumeration
from licorn.foundations.constants import services, svccmds, distros

from licorn.core                  import LMC
from licorn.extensions            import ServiceExtension

stylize = styles.stylize

dbus_pretty_name = stylize(ST_NAME, 'dbus')

class DbusThread(Thread):
	""" Run the d-bus main loop (from gobject) in a separate thread, because
		we've got many other things to do besides it ;-)

		Please don't forget to read:

		* http://dbus.freedesktop.org/doc/dbus-python/api/dbus.mainloop.glib-module.html
		* http://jameswestby.net/weblog/tech/14-caution-python-multiprocessing-and-glib-dont-mix.html
		* http://zachgoldberg.com/2009/10/17/porting-glib-applications-to-python/

	"""
	def __init__(self, daemon=True):
		# Setup the DBus main loop
		assert ltrace(TRACE_DBUS, '| DbusThread.__init__()')
		Thread.__init__(self)
		self.name = 'extensions/Gloop.GobjectMainLooper'
		self.daemon = True

		gobject.threads_init()
		dbus.mainloop.glib.threads_init()
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		self.mainloop = gobject.MainLoop()
	def run(self):
		self.mainloop.run()
	def stop(self):
		self.mainloop.quit()
class GloopExtension(ObjectSingleton, ServiceExtension):
	""" Handle [our interesting subset of] Dbus configuration and options.
		Provide a dbus/gobject loop.

		.. versionadded:: 1.2.5
	"""

	_lpickle_ = { 'to_drop' : [ 'dbus' ] }

	def __init__(self):
		assert ltrace(TRACE_OPENSSH, '| OpensshExtension.__init__()')

		ServiceExtension.__init__(self,
			name='gloop',
			service_name='dbus',
			service_type=services.UPSTART
							if LMC.configuration.distro == distros.UBUNTU
							else services.SYSV
		)

		dbus_binary_paths = {
			distros.UBUNTU: '/bin/dbus-daemon',
			distros.DEBIAN: '/usr/bin/dbus-daemon',
		}

		# NOTE: same path on Ubuntu and Debian.
		self.paths.dbus_config = '/etc/dbus-1/system.conf'

		# NOTE: different path on Ubuntu and Debian. Don't know other distros.
		self.paths.dbus_binary = dbus_binary_paths.get(LMC.configuration.distro,
									'/distro_not_supported/for_gloop_extension/dbus-daemon')

		# TODO: get this from the config file.
		# NOTE: same path on Ubuntu and Debian.
		self.paths.pid_file    = '/var/run/dbus/pid'

	def initialize(self):
		""" Return True if :program:`dbus-daemon` is installed on the system
			and if the configuration file exists where it should be.
		"""

		assert ltrace(globals()['TRACE_' + self.name.upper()], '> initialize()')

		if os.path.exists(self.paths.dbus_binary) \
				and os.path.exists(self.paths.dbus_config):
			self.available = True

			# WE do not use the config file yet.
		else:
			logging.warning2(_(u'{0}: extension not available because '
				'{1} or {2} do not exist on the system.').format(
					stylize(ST_NAME, self.name),
					stylize(ST_PATH, self.paths.dbus_binary),
					stylize(ST_PATH, self.paths.dbus_config)))


		assert ltrace(globals()['TRACE_' + self.name.upper()], '< initialize(%s)' % self.available)
		return self.available
	def is_enabled(self):
		""" Dbus is always enabled if available. This method will **start**
			the dbus/gobject mainloop (not just instanciate it), in a
			separate thread (which will be collected later by the daemon).

			.. note:: Dbus is too important on a Linux system to be disabled
			if present. I've never seen a linux system where it is installed
			but not used (apart from maintenance mode, but Licorn® should not
			have been started in this case).
		"""

		if not self.running(self.paths.pid_file):
			self.service(svccmds.START)

		self.threads.dbus = DbusThread()
		self.threads.dbus.start()

		try:
			self.dbus            = Enumeration('dbus')
			self.dbus.system_bus = dbus.SystemBus()

		except:
			logging.exception(_(u'{0}: could not acquire {1} system bus, '
				u'disabling'), self.pretty_name, dbus_pretty_name)

		else:
			self.__setup_messages_handlers()

			logging.info(_(u'{0}: started extension and gobject mainloop '
					u'thread.').format(self.pretty_name))

		assert ltrace(globals()['TRACE_' + self.name.upper()], '| is_enabled() → True')
		return True
	def dbus_catchall_signal_handler(self, *args, **kwargs):
		logging.progress(_(u'{0}: DBUS message {1} {2}.').format(
				self.pretty_name,
				u', '.join(stylize(ST_NAME, a) for a in args),
				u', '.join('%s=%s' % (stylize(ST_ATTR, k),
										stylize(ST_ATTRVALUE, v))
					for k,v in kwargs.iteritems())))
	def __setup_messages_handlers(self):
		if __debug__:
			# The dbus catchall
			self.dbus.system_bus.add_signal_receiver(self.dbus_catchall_signal_handler,
							interface_keyword='dbus_interface',
							member_keyword='member')
		pass

__all__ = ('GloopExtension', )
