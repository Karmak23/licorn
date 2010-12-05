# -*- coding: utf-8 -*-
"""
Licorn Daemon CommandListener, implemented with Pyro (Python Remote Objects).

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import time, pwd, grp, signal, os

import Pyro.core, Pyro.protocol, Pyro.configuration, Pyro.constants

from threading   import Thread, Event, Semaphore, Timer
from collections import deque

from licorn.foundations           import logging, process, network
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import filters, licornd_roles

from licorn.core                  import LMC
from licorn.daemon.core           import dname, dthreads
from licorn.daemon.threads        import LicornBasicThread

class LicornPyroValidator(Pyro.protocol.DefaultConnValidator):
	valid_users = []
	local_interfaces = [ '127.0.0.1', '127.0.1.1' ]
	# the values will be overridden by daemon.configuration when thread starts.
	# see configuration objects for details about port numbers.
	pyro_port = None
	server = None
	def __init__(self):
		Pyro.protocol.DefaultConnValidator.__init__(self)
	def acceptHost(self, daemon, connection):
		""" Very basic check for the connection. """
		client_addr, client_socket = connection.addr

		assert ltrace('cmdlistener', 'connection from %s:%s' % (
			client_addr, client_socket))

		if client_addr in LicornPyroValidator.local_interfaces:
			# TODO inspect the socket number, launch netstat -atnp, find the
			# process and get the user to see if member of group admins
			# or == root.
			try:
				client_uid = process.find_network_client_uid(
					LicornPyroValidator.pyro_port, client_socket,
					local=True if client_addr[:3] == '127' else False)
			except Exception, e:
				logging.warning('''error finding network connection from '''
					'''localhost:%s (was %s).''' % (client_socket, e))
				return 0, Pyro.constants.DENIED_UNSPECIFIED
			else:
				return self.acceptUid(daemon, client_uid, client_addr,
					client_socket)
		else:
			if LMC.configuration.licornd.role == licornd_roles.SERVER:
				# connect to the client's Pyro daemon and make sure the request
				# originates from a valid user.
				# FIXME: this is far from perfect and secure, but quite
				# sufficient for testing and deploying. Better security will
				# come when everything works.

				remote_system = Pyro.core.getAttrProxyForURI(
					"PYROLOC://%s:%s/system" % (client_addr,
					LicornPyroValidator.pyro_port))
				try:
					client_uid = remote_system.uid_connecting_from(
						client_socket)
				except Exception, e:
					logging.warning('''error finding uid initiation '''
						'''connection from %s:%s (was %s).''' % (client_addr,
							client_socket, e))
					return 0, Pyro.constants.DENIED_UNSPECIFIED
				else:
					return self.acceptUid(daemon, client_uid, client_addr,
						client_socket)

				if client_socket <= 1024 \
					or client_socket == LicornPyroValidator.pyro_port:
					# restricted port, only root can do that.
					# connection is authorized.
					return 1, 0
				else:
					logging.warning('connection tentative from %s:%s' % (
						client_addr, client_socket))
					return 0, Pyro.constants.DENIED_HOSTBLOCKED
			else:
				# FIXME: we are on the client, just accept any connection
				# coming from our server, else deny. This must be refined to be
				# sure the connection is valid, but i've got no idea yet on how
				# to do it properly.
				if client_addr == LicornPyroValidator.server:
					return 1, 0
				else:
					logging.warning('connection tentative from %s:%s' % (
						client_addr, client_socket))
					return 0, Pyro.constants.DENIED_HOSTBLOCKED
	def acceptUid(self, daemon, client_uid, client_addr, client_socket):
		try:
			# measured with LICORN_TRACE=timings, using pwd.getpwuid()
			# is at best as quick as users.uid_to_login(), but generally
			# slower. Thus we use our internals.
			#client_login = pwd.getpwuid(client_uid).pw_name
			client_login = LMC.users.uid_to_login(
				client_uid)

			assert ltrace('cmdlistener',
				'currently auhorized users: %s' %
					LicornPyroValidator.valid_users)

			if client_uid == 0 \
				or client_login in LicornPyroValidator.valid_users:
				logging.progress('''Authorized client connection from'''
					''' %s:%s, user %s(%s).''' % (client_addr, client_socket,
					stylize(ST_NAME, client_login),
					stylize(ST_UGID, client_uid)))

				# connection is authorized.
				return 1, 0
			else:
				logging.warning('connection tentative from %s:%s, user %s(%s).'
					% (client_addr, client_socket, client_login, client_uid))
				return 0, Pyro.constants.DENIED_SECURITY
		except Exception, e:
			logging.warning(
				'something went wrong from %s (was %s).' % (
				(stylize(ST_ADDRESS, '%s:%s' % (client_addr,
					client_socket)), e)))
			return 0, Pyro.constants.DENIED_UNSPECIFIED
class CommandListener(LicornBasicThread):
	""" A Thread which collect INotify events and does what
		is appropriate with them. """

	def __init__(self, pname=dname, pids_to_wake=[], **kwargs):

		LicornBasicThread.__init__(self, pname)

		#self.name = "%s/%s" % (
		#	pname, str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self.pids_to_wake = pids_to_wake
		self.wake_threads = []

		#for (cname, controller) in LMC.iteritems():
		#	setattr(self, cname, controller)

		for attr_name in kwargs:
			setattr(self, attr_name, kwargs[attr_name])
	def dump_status(self, long_output=False, precision=None):
		""" get detailled thread status. """
		if long_output:
			uri_status= '\n\tObjects URI: %s' % str(self.uris).replace(
				'{', '\n\t\t').replace(', ', ',\n\t\t').replace('}', '')

		else:
			uri_status = ''

		return '%s(%s%s) %s (%d calls, %d wakers)%s%s' % (
				stylize(ST_NAME, self.name),
				self.ident, stylize(ST_OK, '&') if self.daemon else '',
				stylize(ST_OK, 'alive') \
					if self.is_alive() else 'has terminated',
				self._pyro_loop, len(self.wake_threads), uri_status,
				self.dump_pyro_connections()
			)
	def dump_pyro_connections(self):
		""" """
		data = '\n'
		for conn in self.pyro_daemon.connections:
			if isinstance(conn, Pyro.protocol.TCPConnection):
				#data += '\tTCPConn %s: %s:%s ‣ %s:%s\n'
				data += '%s\n' % str(conn)
			elif isinstance(conn, Thread):
				data += '\tThread %s\n' % str(conn)
			else:
				data += 'unknown %s\n' % str(conn)
		# remove last trailing '\n'
		return data[:-1]
	def run(self):
		assert ltrace('thread', '%s running' % self.name)

		Pyro.core.initServer()
		Pyro.config.PYRO_PORT=LMC.configuration.licornd.pyro.port
		#Pyro.config.PYRO_TRACELEVEL=3
		#Pyro.config.PYRO_USER_TRACELEVEL=3
		#Pyro.config.PYRO_LOGFILE='pyro.log'
		#Pyro.config.PYRO_USER_LOGFILE='pyro.user.log'

		# by default Pyro listens on all interfaces, no need to refine.
		self.pyro_daemon=Pyro.core.Daemon(norange=1,
			port=LMC.configuration.licornd.pyro.port)

		# not strictly needed.
		#self.pyro_daemon.setTimeout(5)
		#self.pyro_daemon.setTransientsCleanupAge(5)

		# get a direct reference to the members of group authorized to connect,
		# this avoids any needs to reload it after a change.
		LicornPyroValidator.valid_users = LMC.groups[
			LMC.groups.name_to_gid(
				LMC.configuration.defaults.admin_group
				)]['memberUid']
		LicornPyroValidator.pyro_port = LMC.configuration.licornd.pyro.port
		LicornPyroValidator.local_interfaces.extend(
			network.find_local_ip_addresses())

		if LMC.configuration.licornd.role == licornd_roles.CLIENT:
			LicornPyroValidator.server = LMC.configuration.server_address

		self.pyro_daemon.setNewConnectionValidator(LicornPyroValidator())
		self.pyro_daemon.cmdlistener = self
		self.uris = {}

		self.uris['configuration'] = self.pyro_daemon.connect(
			LMC.configuration, 'configuration')
		self.uris['msgproc'] = self.pyro_daemon.connect(
					LMC.msgproc, 'msgproc')

		if LMC.configuration.licornd.role == licornd_roles.SERVER:
			self.uris['users'] = self.pyro_daemon.connect(
				LMC.users, 'users')
			self.uris['groups'] = self.pyro_daemon.connect(
				LMC.groups, 'groups')
			self.uris['profiles'] = self.pyro_daemon.connect(
				LMC.profiles, 'profiles')
			self.uris['machines'] = self.pyro_daemon.connect(
				LMC.machines, 'machines')
			self.uris['privileges'] = self.pyro_daemon.connect(
				LMC.privileges, 'privileges')
			self.uris['keywords'] = self.pyro_daemon.connect(
				LMC.keywords, 'keywords')
			self.uris['backends'] = self.pyro_daemon.connect(
				LMC.backends, 'backends')

		# client and server get the SystemController
		self.uris['system'] = self.pyro_daemon.connect(
			LMC.system, 'system')

		logging.info("%s: %s Pyro daemon on interface %s." % (
			self.name, stylize(ST_OK, "started"),
			stylize(ST_URL, '*:%s' % self.pyro_daemon.port)))

		for pid in self.pids_to_wake:
			th = Timer(0.25, lambda x: os.kill(x, signal.SIGUSR1), (pid,))
			self.wake_threads.append(th)
			assert ltrace('thread', '%s starting wake up thread %s.' % (
				self.name, th.name))
			th.start()

		check_wakers = True
		self._pyro_loop = 0
		while not self._stop_event.isSet():
			try:
				self.pyro_daemon.handleRequests(0.1)
				assert ltrace('cmdlistener', "pyro daemon %d's loop: %s" % (
					self._pyro_loop, self.pyro_daemon.connections))
			except Exception, e:
				logging.warning(e)
			self._pyro_loop +=1

			if check_wakers:
				# we check wake threads only at the beginning of loop. After
				# that, they should be already stopped.
				for th in self.wake_threads:
					if th.is_alive():
						continue
					else:
						th.join()
						self.wake_threads.remove(th)
						del th

					if len(self.wake_threads) == 0:
						assert ltrace('thread',
							'%s: all wakers terminated at loop#%d.' % (
								self.name, self._pyro_loop))
						check_wakers = False

		logging.info('%s: %s Pyro daemon.' % (self.name,
			stylize(ST_BAD, 'stopped')))
		self.pyro_daemon.shutdown(True)

		# NOTE: this is just in case we stop ourselves *before* waker_threads
		# finish. Happens if Control-C at the beginning of the daemon. Unlikely
		# to occur, but who knows.
		for th in self.wake_threads:
			assert ltrace('thread', '%s  stopping wake up thread %s.' % (
				self.name, th.name))
			th.cancel()
			th.join()

		assert ltrace('thread', '%s ended' % self.name)