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

import os, pwd, Pyro.core

from threading import current_thread
from licorn.foundations.threads import RLock

from licorn.foundations           import logging, settings
from licorn.foundations           import process, apt, events, hlstr
from licorn.foundations.events    import LicornEvent
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, NamedObject
from licorn.foundations.messaging import ListenerObject
from licorn.foundations.constants import host_status, host_types, distros, \
											reasons, conditions, roles, priorities

from licorn.core                import LMC
from licorn.daemon              import client

class SystemController(ObjectSingleton, NamedObject, ListenerObject, Pyro.core.ObjBase):
	""" This class implement a local system controller. It is meant to be used
		remotely, via Pyro calls, to act on the local machine, or transmit
		informations (status, uptime, load, etc) to the caller.

		.. note:: all extensions attached to this controller must implement
			a :meth:`system_load` method, which will be called by the :meth:`reload`
			method. This is to make extensions load their
			**data**, which is different than loading their *configuration*,
			which must have been done at :meth:`~licorn.core.classes.CoreModule.initialize`
			time.
		"""
	init_ok = False
	@property
	def licornd(self):
		return LMC.licornd
	def __init__(self):
		""" INIT the local system object. It is meant
			to pilot other objects and the local machine. """

		if SystemController.init_ok:
			return

		Pyro.core.ObjBase.__init__(self)

		super(SystemController, self).__init__(name='system')

		self.lock = RLock()
		self.__status = host_status.ACTIVE

		SystemController.init_ok = True
	def load(self):
		pass
	def reload(self):
		""" load all our extensions. """
		if hasattr(self, 'extensions'):
			self.load_system_extensions()
		else:
			if hasattr(LMC, 'extensions'):
				self.extensions = LMC.extensions.find_compatibles(self)
				self.load_system_extensions()
			else:
				self.extensions = None
	def load_system_extensions(self):
		""" special case for SystemController. """
		assert ltrace(TRACE_SYSTEM, '| load_system_extension()')
		for ext in self.extensions:
			ext.system_load()
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

		if settings.role == roles.SERVER:
			LMC.machines.announce_shutdown()
		else:
			client.client_goodbye()
	def goodbye_from(self, remote_interfaces):
		""" a remote Licorn® server is shutting down: receive the shutdown
			announce and forward it to the
			:class:`~licorn.core.machines.MachinesController`, it knows what
			to do with it. """

		assert ltrace(TRACE_SYSTEM, '| goodbye_from(%s)' % ', '.join(remote_interfaces))

		if settings.role == roles.SERVER:
			LMC.machines.goodbye_from(remote_interfaces)
		else:
			workers.service_enqueue(priorities.HIGH, client.server_shutdown, remote_interfaces)
	def hello_from(self, remote_interfaces):
		""" a remote Licorn® server is warming up: receive the hello
			announce and forward it to the
			:class:`~licorn.core.machines.MachinesController`, it knows what
			to do with it. """

		assert ltrace(TRACE_SYSTEM, '| hello_from(%s)' % ', '.join(remote_interfaces))

		if settings.role == roles.SERVER:
			LMC.machines.hello_from(remote_interfaces)
		else:
			workers.service_enqueue(priorities.HIGH, client.server_reconnect, remote_interfaces)
	def get_host_type(self):
		""" Return local host type. """

		# this one is obliged, we are running Licorn® via this code.
		systype = host_types.LICORN

		if settings.role == roles.SERVER:
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
	def updates_available(self, full=False, *args, **kwargs):
		up, sec = apt.apt_do_check()
		if full:
			return up, sec
		return (up or sec)
	def security_updates(self, *args, **kwargs):
		return apt.apt_do_check()[1]
	def software_updates(self, *args, **kwargs):
		return apt.apt_do_check()[0]
	@workers.background_service(priorities.NORMAL)
	def do_upgrade(self, machine=None, *args, **kwargs):
		""" This method will launch the upgrade procedure in a background
			service thread. """

		if not self.updates_available():
			return

		with self.lock:
			self.__status |= host_status.UPGRADING

			machine.status = host_status.UPGRADING

			LicornEvent('software_upgrades_started', host=machine).emit()

		# no need to try/except, apt_do_upgrade() does it already.
		apt.apt_do_upgrade()

		with self.lock:
			self.__status -= host_status.UPGRADING

			machine.status = self.__status

			LicornEvent('software_upgrades_finished', host=machine).emit()

		# reset the status, anyway
		apt.apt_do_check(cache_force_expire=True)
	def uptime_and_load(self):
		assert ltrace(TRACE_SYSTEM, '| uptime_and_load()')
		return open('/proc/loadavg').read().split(' ')
	def explain_connecting_from(self, client_socket):
		""" Called from remote `licornd` to validate incoming Pyro connections. """

		uid, pid = process.find_network_client_infos(
			settings.pyro.port, client_socket, local=False)

		try:
			login = pwd.getpwuid(uid).pw_name

		except KeyError:
			login = None

		assert ltrace(TRACE_SYSTEM, '| uid_connecting_from(%s) -> %s (local=%s)' % (
													client_socket, uid, login))
		return (uid, login)
	def check_shutdown(self):
		""" someone could have cancelled the shutdown outside of Licorn®. """
		with self.lock:
			if self.__status == host_status.SHUTTING_DOWN:
				if process.already_running('/var/run/shutdown.pid'):
					return True

				else:
					self.__status = host_status.ACTIVE

			return False
	def shutdown(self, delay=1, warn_users=True, reboot=False, *args, **kwargs):
		""" Shutdown the local machine.

			Internally we use screen to detach the programs, because the
			fork/exec couple has become very hard to do without crashing
			some parts of licornd (due to Pyro and Twisted beiing buried
			down in our daemon).

			.. todo:: implement a correct shutdown_daemon_things() method
				to clean things and be able to daemonize() without using
				this os.system()/screen hack.
		"""
		assert ltrace(TRACE_SYSTEM, '| shutdown(warn=%s)' % warn_users)

		with self.lock:
			if self.check_shutdown():
				logging.warning(_(u'Already shutting down!'))
				return True

			self.__status = host_status.SHUTTING_DOWN

			LicornEvent('shutdown_started', reboot=reboot).emit(priorities.HIGH)

			if warn_users:
				import tempfile
				quote = hlstr.shell_quote

				# NOTE: pipes.quote() didn't really help in quoting these
				# complicated strings and shell commands. We were alone
				# here, and I chose to do it via a shell script.
				#
				# TODO: implement this via a contrib python script, making
				# the whole thing more elegant, and allowing the cancellation
				# by a licorn internal command, which will propagate the
				# event for the WMI side, too (not just a bare 'shutdown -c').
				command = (
					"export DISPLAY=':0'\n"
					"user=`w | grep -E 'tty.\s+:0' | awk '{{print $1}}'`\n"
					# In case no user detected, we must exit.
					# on Oneiric: https://bugs.launchpad.net/ubuntu/oneiric/+source/lightdm/+bug/870297
					"[ -z \"$user\" ] && exit 0 \n"
					"sudo su -l $user -c 'zenity \\\n"
					"	 --title=\"{0}\" --question \\\n"
					"	--ok-label=\"{1}\" --cancel-label=\"{2}\" \\\n"
					"	--text=\"{3}\" ' \n"
					"[ $? -eq 1 ] && (sleep 1; shutdown -c || true) \n").format(
						quote(_(u'Warning: automatic system shutdown')),
						quote(_(u'Accept fate')),
						quote(_(u'Cancel shutdown')),
						quote(_(u'The system will automatically shutdown '
							u'in one minute. Please save all your work '
							u'and close your session.\\n\\n'
							u'You can choose to cancel this operation, '
							u'but i imagine that your sysadmin will not '
							u'be happy \'bout that!'))
						)

				(fhandle, fname) = tempfile.mkstemp()

				os.write(fhandle, command)
				os.write(fhandle, 'rm -f "%s" \n' % fname)
				os.close(fhandle)

				# We'll warn the user in another process, else the current
				# one will be blocked until the user confirms the dialog, and
				# this could block the shutdown process from happening forever.
				os.system('screen -d -m bash %s' % fname)

			# run "shutdown" in another process, else it will stay "hooked" and
			# will block the current process.
			os.system('screen -d -m shutdown %s +1' % ('-r' if reboot else '-h'))

			return True
	def shutdown_cancel(self):
		""" shutdown the local machine. """

		assert ltrace_func(TRACE_SYSTEM)

		with self.lock:
			if not self.check_shutdown():
				logging.warning(_(u'Already NOT currently shutting down.'))
				return True

		if os.fork() == 0 :
			process.daemonize(close_all=True)

			command = [ 'shutdown', '-c' ]
			os.execvp('shutdown', command)

		else:
			LicornEvent('shutdown_cancelled').emit(priorities.HIGH)
			return True
	@events.handler_method
	def shutdown_cancelled(self, *args, **kwargs):
		with self.lock:
			self.__status = host_status.ACTIVE
	def restart(self, condition=None, delay=None):
		""" Called from remote `licornd`, to restart a licornd (not the whole system). """
		if delay is None:
			delay = 0.0

		logging.notice(_(u'{0:s}: machine {1:s} wants us to restart '
			u'(condition={2:s}, delay={3:s})').format(self,
				current_thread()._licorn_remote_address,
				conditions[condition], delay))

		if condition is None:
			time.sleep(delay)
			LicornEvent('need_restart',
				reason=reasons.REMOTE_SYSTEM_ASKED).emit(priorities.HIGH)

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
