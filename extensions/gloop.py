# -*- coding: utf-8 -*-
"""
Licorn extensions: Dbus - http://docs.licorn.org/extensions/dbus.html

* the first purpose of this extension is to provide a dbus/gobject mainloop
  outside of the licorn daemon, for enhanced flexibility.

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

from licorn.foundations           import exceptions, logging
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces import *
from licorn.foundations.base      import Singleton
from licorn.foundations.constants import services, svccmds
from licorn.extensions            import ServiceExtension

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
class GloopExtension(Singleton, ServiceExtension):
	""" Handle [our interesting subset of] Dbus configuration and options.
		Provide a dbus/gobject loop.

		.. versionadded:: 1.2.5
	"""
	def __init__(self):
		assert ltrace(TRACE_OPENSSH, '| OpensshExtension.__init__()')

		ServiceExtension.__init__(self,
			name='gloop',
			service_name='dbus',
			service_type=services.UPSTART
		)

		# TODO: parameter service_* from the distro
		# 		if LMC.configuration.distro in (
		#	distros.LICORN,
		#	distros.UBUNTU,
		#	distros.DEBIAN,
		#	distros.REDHAT,
		#	distros.GENTOO,
		#	distros.MANDRIVA,
		#	distros.NOVELL
		#	):

		self.paths.dbus_config = '/etc/dbus-1/system.conf'
		self.paths.dbus_binary = '/bin/dbus-daemon'

		# TODO: get this from the config file.
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

		logging.info(_(u'{0}: started extension and gobject mainloop '
			'thread.').format(stylize(ST_NAME, self.name)))

		assert ltrace(globals()['TRACE_' + self.name.upper()], '| is_enabled() → True')
		return True
