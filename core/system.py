# -*- coding: utf-8 -*-
"""
Licorn core: system - http://docs.licorn.org/core/system.html

:copyright:
	* 2010 Olivier Cortès <olive@deep-ocean.net>
	* partial 2010 Robin Lucbernet <robinlucbernet@gmail.com>

:license: GNU GPL version 2

.. versionadded:: 1.3
	This backend was implemented during the 1.2 ⇢ 1.3 development cycle.

"""

import os

from licorn.foundations           import logging
from licorn.foundations           import process
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton
from licorn.foundations.constants import host_status, host_types

from licorn.core         import LMC
from licorn.core.classes import LockedController

class SystemController(Singleton, LockedController):
	""" This class implement a local system controller. It is meant to be used
		remotely, via Pyro calls, to act on the local machine, or transmit
		informations (status, uptime, load, etc) to the caller.

		.. note:: all extensions attached to this controller must implement
			a :meth:`system_load` method, which will be called by the
			:meth:`reload` method. This is to make extensions load their
			**data**, which is different than loading their *configuration*,
			which must have been done at
			:meth:`~licorn.core.classes.CoreModule.initialize` time.
		"""
	init_ok = False

	def __init__(self):
		""" INIT the local system object. It is meant
			to pilot other objects and the local machine. """

		if SystemController.init_ok:
			return

		LockedController.__init__(self, 'system')

		self.status = host_status.ACTIVE

		SystemController.init_ok = True
	def load(self):
		pass
	def reload(self):
		""" load all our extensions. """
		#print '>> reload sys'
		if hasattr(self, 'extensions'):
			self.load_system_extensions()
		else:
			if hasattr(LMC, 'extensions'):
				#print '>> findcompat'
				self.extensions = LMC.extensions.find_compatibles(self)
				self.load_system_extensions()
			else:
				#print '>> sysextnone'
				self.extensions = None
	def load_system_extensions(self):
		""" special case for SystemController. """
		assert ltrace('system', '| load_system_extension()')
		for ext in self.extensions:
			ext.system_load()
	def noop(self):
		""" No-op function, called when remotely connecting pyro, to check if
			link is OK between the server and the client. """
		assert ltrace('system', '| noop(True)')
		return True
	def start_service(self, service_name):
		""" start a service at the system level (currently upstart
		compatible only). """
		# TODO: use SystemserviceExtension...
		ret = process.execute(['start', service_name])[1].strip()
		logging.info('Started service %s (%s).' % (
				stylize(ST_NAME, service_name), ret))
	def stop_service(self, service_name):
		""" stop a service at the system level (currently upstart
		compatible only). """
		# TODO: use SystemserviceExtension...
		ret = process.execute(['stop', service_name])[1].strip()
		logging.info('Stopped service %s (%s).' % (
				stylize(ST_NAME, service_name), ret))
	def reload_service(self, service_name):
		""" reload a service at the system level (currently upstart
		compatible only). """
		# TODO: use SystemserviceExtension...
		ret = process.execute(['reload', service_name])[1].strip()
		logging.info('Reloaded service %s (%s).' % (
				stylize(ST_NAME, service_name), ret))
	def restart_service(self, service_name):
		""" restart a service at the system level (currently upstart
		compatible only). """
		# TODO: use SystemserviceExtension...
		ret = process.execute(['restart', service_name])[1].strip()
		logging.info('Restarted service %s (%s).' % (
				stylize(ST_NAME, service_name), ret))
	def get_status(self):
		""" Get local host current status. """
		with self.lock():
			assert ltrace('system', '| get_status(%s)' % self.status)
			return self.status
	def get_daemon_status(self, long_output, precision):
		from licorn.daemon.core import get_daemon_status
		return get_daemon_status(long_output, precision)
	def get_host_type(self):
		""" Return local host type. """
		assert ltrace('system', '| get_host_type(%s)' % host_types.UBUNTU)
		return host_types.UBUNTU
	def uptime_and_load(self):
		assert ltrace('system', '| uptime_and_load()')
		return open('/proc/loadavg').read().split(' ')
	def uid_connecting_from(self, client_socket):
		""" TODO """
		uid = process.find_network_client_uid(
			LMC.configuration.licornd.pyro.port, client_socket, local=False)
		assert ltrace('system', '| uid_connecting_from(%s) -> %s(%s)' % (
			client_socket, LMC.users.uid_to_login(uid), uid))
		return uid
	def shutdown(self, delay=1, warn_users=True):
		""" shutdown the local machine. """
		assert ltrace('system', '| shutdown(warn=%s)' % warn_users)

		with self.lock():
			if self.status == host_status.SHUTTING_DOWN:
				logging.warning('already shutting down!')
				return True

		if os.fork() == 0 :
			process.daemonize()

			if warn_users:
				if os.fork() == 0:
					process.daemonize()

					command = (r'''export DISPLAY=":0"; '''
						r'''sudo su -l '''
						r'''`w | grep -E 'tty.\s+:0' | awk '{print $1}'` '''
						r'''-c 'zenity --warning --text='''
						r'''"le système va être arrêté dans '''
						r'''une minute exactement, merci de bien vouloir '''
						r'''enregistrer votre travail et de fermer votre '''
						r'''session."' ''')
					os.execvp('bash', [ 'bash', '-c', command ])

			command = [ 'shutdown', '-h', '+1' ]
			os.execvp('shutdown', command)
		else:
			with self.lock():
				self.status = host_status.SHUTTING_DOWN
				return True
	def get_extensions(self, client_only=False):
		if client_only:
			return [ key for key in LMC.extensions.keys()
						if not LMC.extensions[key].server_only ]
		else:
			return LMC.extensions.keys()
	def backends(self, client_only=False):
		if client_only:
			return [ key for key in LMC.backends.keys()
						if not LMC.backends[key].server_only ]
		else:
			return LMC.backends.keys()
