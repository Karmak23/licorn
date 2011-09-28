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

import os, pwd, uuid
from threading import current_thread, RLock

from licorn.foundations           import logging, options
from licorn.foundations           import process
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import Singleton
from licorn.foundations.messaging import remote_output, ListenerObject
from licorn.foundations.constants import host_status, host_types, distros, \
											reasons, conditions

from licorn.core         import LMC
from licorn.core.classes import CoreController
from licorn.daemon       import roles, client, priorities

class SystemController(Singleton, CoreController, ListenerObject):
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

		self.__status = host_status.ACTIVE

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
		assert ltrace(TRACE_SYSTEM, '| load_system_extension()')
		for ext in self.extensions:
			ext.system_load()
	def noop(self):
		""" No-op function, called when remotely connecting pyro, to check if
			link is OK between the server and the client. """
		assert ltrace(TRACE_SYSTEM, '| noop(True)')
		return True
	def get_daemon_status(self, opts, args):
		""" This method is called from CLI tools. """
		self.setup_listener_gettext()

		remote_output(LMC.licornd.dump_status(opts.long_output, opts.precision),
								clear_terminal=opts.monitor_clear)
	def local_ip_addresses(self):
		""" Called from remote `licornd`. """
		return LMC.configuration.network.local_ip_addresses()
	def get_status(self):
		""" Get local host current status. """
		with self.lock:
			assert ltrace(TRACE_SYSTEM, '| get_status(%s)' % self.__status)
			return self.__status
	def announce_shutdown(self):
		""" mark us as shutting down and announce this to everyone connected."""
		self.__status = host_status.PYRO_SHUTDOWN

		if LMC.configuration.licornd.role == roles.SERVER:
			LMC.machines.announce_shutdown()
		else:
			client.client_goodbye()
	def goodbye_from(self, remote_interfaces):
		""" a remote Licorn® server is shutting down: receive the shutdown
			announce and forward it to the
			:class:`~licorn.core.machines.MachinesController`, it knows what
			to do with it. """

		assert ltrace(TRACE_SYSTEM, '| goodbye_from(%s)' % ', '.join(remote_interfaces))

		if LMC.configuration.licornd.role == roles.SERVER:
			LMC.machines.goodbye_from(remote_interfaces)
		else:
			L_service_enqueue(priorities.HIGH, client.server_shutdown, remote_interfaces)
	def hello_from(self, remote_interfaces):
		""" a remote Licorn® server is warming up: receive the hello
			announce and forward it to the
			:class:`~licorn.core.machines.MachinesController`, it knows what
			to do with it. """

		assert ltrace(TRACE_SYSTEM, '| hello_from(%s)' % ', '.join(remote_interfaces))

		if LMC.configuration.licornd.role == roles.SERVER:
			LMC.machines.hello_from(remote_interfaces)
		else:
			L_service_enqueue(priorities.HIGH, client.server_reconnect, remote_interfaces)
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

		assert ltrace(TRACE_SYSTEM, '| get_host_type(%s)' % systype)

		return systype
	def uptime_and_load(self):
		assert ltrace(TRACE_SYSTEM, '| uptime_and_load()')
		return open('/proc/loadavg').read().split(' ')
	def explain_connecting_from(self, client_socket):
		""" Called from remote `licornd` to validate incoming Pyro connections. """

		uid = process.find_network_client_uid(
			LMC.configuration.licornd.pyro.port, client_socket, local=False)

		try:
			login = pwd.getpwuid(uid).pw_name

		except KeyError:
			login = None

		assert ltrace(TRACE_SYSTEM, '| uid_connecting_from(%s) -> %s (local=%s)' % (
													client_socket, uid, login))
		return (uid, login)
	def shutdown(self, delay=1, warn_users=True):
		""" shutdown the local machine. """
		assert ltrace(TRACE_SYSTEM, '| shutdown(warn=%s)' % warn_users)

		with self.lock:
			if self.__status == host_status.SHUTTING_DOWN:
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
				self.__status = host_status.SHUTTING_DOWN
				return True
	def restart(self, condition=None, delay=None):
		""" Called from remove `licornd`. """
		if delay is None:
			delay = 0.0

		logging.notice(_(u'{0:s}: machine {1:s} wants us to restart '
			u'(condition={2:s}, delay={3:s})').format(self,
				current_thread()._licorn_remote_address,
				conditions[condition], delay))

		if condition is None:
			time.sleep(delay)
			L_event_dispatch(priorities.HIGH,
					InternalEvent('need_restart',
						reason=reasons.REMOTE_SYSTEM_ASKED))

		elif condition == conditions.WAIT_FOR_ME_BACK_ONLINE:
			# TODO: we need to setup :
			# 	- a new event in the Machines: 'server_came_back_online'
			# 	- a new event callback which:
			#		- compares the IP of the emitter
			#		- unregisters itselfs to avoid duplicate receives of the event
			# 		- waits the delay
			#		- and sends the 'need_restart' event.
			pass
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
	def register_monitor(self, facilities):

		self.setup_listener_gettext()

		t = current_thread()
		t.monitor_facilities = ltrace_str_to_int(facilities)

		t.monitor_uuid = uuid.uuid4()

		logging.notice(_(u'New trace session started with UUID {0}, '
			u'facilities {1}.').format(stylize(ST_UGID, t.monitor_uuid),
				stylize(ST_COMMENT, facilities)))

		# The monitor_lock avoids collisions on listener.verbose
		# modifications while a flood of messages are beiing sent
		# on the wire. Having a per-thread lock avoids locking
		# the master `options.monitor_lock` from the client side
		# when only one monitor changes its verbose level. This
		# is more fine grained.
		t.monitor_lock = RLock()

		with options.monitor_lock:
			options.monitor_listeners.append(t)

		# return the UUID of the thread, so that the remote side
		# can detach easily when it terminates.
		return t.monitor_uuid
	def unregister_monitor(self, muuid):

		self.setup_listener_gettext()

		found = None

		with options.monitor_lock:
			for t in options.monitor_listeners[:]:
				if t.monitor_uuid == muuid:
					found = t
					options.monitor_listeners.remove(t)
					break

		if found:
			del t.monitor_facilities
			del t.monitor_uuid
			del t.monitor_lock

		else:
			logging.warning(_(u'Monitor listener with UUID %s not found!') % muuid)

		logging.notice(_(u'Trace session UUID {0} ended.').format(
													stylize(ST_UGID, muuid)))
