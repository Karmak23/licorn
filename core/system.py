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
from licorn.foundations.constants import host_status, host_types, distros

from licorn.core         import LMC
from licorn.core.classes import CoreController
from licorn.daemon       import roles, client, priorities

class SystemController(Singleton, CoreController):
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

		CoreController.__init__(self, 'system')

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
	def local_ip_addresses(self):
		return LMC.configuration.network.local_ip_addresses()
	def get_status(self):
		""" Get local host current status. """
		with self.lock:
			assert ltrace('system', '| get_status(%s)' % self.status)
			return self.status
	def announce_shutdown(self):
		""" mark us as shutting down and announce this to everyone connected."""
		self.status = host_status.PYRO_SHUTDOWN

		if LMC.configuration.licornd.role == roles.SERVER:
			LMC.machines.announce_shutdown()
		else:
			client.client_goodbye()
	def goodbye_from(self, remote_interfaces):
		""" a remote Licorn® server is shutting down: receive the shutdown
			announce and forward it to the
			:class:`~licorn.core.machines.MachinesController`, it knows what
			to do with it. """

		assert ltrace('system', '| goodbye_from(%s)' % ', '.join(remote_interfaces))

		if LMC.configuration.licornd.role == roles.SERVER:
			LMC.machines.goodbye_from(remote_interfaces)
		else:
			self.licornd.service_enqueue(priorities.HIGH, client.server_shutdown, remote_interfaces)
	def hello_from(self, remote_interfaces):
		""" a remote Licorn® server is warming up: receive the hello
			announce and forward it to the
			:class:`~licorn.core.machines.MachinesController`, it knows what
			to do with it. """

		assert ltrace('system', '| hello_from(%s)' % ', '.join(remote_interfaces))

		if LMC.configuration.licornd.role == roles.SERVER:
			LMC.machines.hello_from(remote_interfaces)
		else:
			self.licornd.service_enqueue(priorities.HIGH, client.server_reconnect, remote_interfaces)
	def get_host_type(self):
		""" Return local host type. """

		# this one is obliged, we are running Licorn® via this code.
		systype = host_types.LICORN

		if LMC.configuration.licornd.role == roles.SERVER:
			systype |= host_types.META_SRV

		if LMC.configuration.distro == distros.UBUNTU:
			systype |= host_types.UBUNTU
			systype -= host_types.LNX_GEN

		elif LMC.configuration.distro == distros.DEBIAN:
			systype |= host_types.DEBIAN
			systype -= host_types.LNX_GEN

		elif LMC.configuration.distro == distros.GENTOO:
			systype |= host_types.GENTOO
			systype -= host_types.LNX_GEN

		elif LMC.configuration.distro == distros.REDHAT:
			systype |= host_types.REDHAT
			systype -= host_types.LNX_GEN

		elif LMC.configuration.distro == distros.MANDRIVA:
			systype |= host_types.MANDRIVA
			systype -= host_types.LNX_GEN

		assert ltrace('system', '| get_host_type(%s)' % systype)

		return systype
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

		with self.lock:
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
			with self.lock:
				self.status = host_status.SHUTTING_DOWN
				return True
	def get_extensions(self, client_only=False):
		if client_only:
			return [ key for key in LMC.extensions.keys()
						if not LMC.extensions[key].server_only ]
		else:
			return LMC.extensions.keys()
	def get_backends(self, client_only=False):
		if client_only:
			return [ key for key in LMC.backends.keys()
						if not LMC.backends[key].server_only ]
		else:
			return LMC.backends.keys()
