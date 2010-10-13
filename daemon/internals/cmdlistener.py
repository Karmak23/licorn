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

from licorn.foundations           import logging, styles, process
from licorn.foundations.threads   import LicornBasicThread
from licorn.foundations.constants import filters

from licorn.daemon.core           import dname

class LicornPyroValidator(Pyro.protocol.DefaultConnValidator):
	valid_users = grp.getgrnam('admins').gr_mem
	@staticmethod
	def reload():
		LicornPyroValidator.valid_users = grp.getgrnam('admins').gr_mem
		logging.info('Reloaded list of users granted to connect to the daemon.')
	def __init__(self):
		Pyro.protocol.DefaultConnValidator.__init__(self)
	def acceptHost(self, daemon, connection):
		""" Very basic check for the connection. """
		client_addr, client_socket = connection.addr
		if client_addr in ('127.0.0.1', '127.0.1.1'):
			# TODO inspect the socket number, launch netstat -atnp, find the
			# process and get the user to see if member of group admins
			# or == root.
			try:
				client_uid = process.find_network_client_uid(7766,
					client_socket)
			except Exception, e:
				logging.warning('''error finding network connection from '''
					'''localhost:%s (was %s).''' % (client_socket, e))
				return 0, Pyro.constants.DENIED_UNSPECIFIED
			else:
				try:
					# measured with LICORN_TRACE=timings, using pwd.getpwuid()
					# is at best as quick as users.uid_to_login(), but generally
					# slower. Thus we use our internals.
					#client_login = pwd.getpwuid(client_uid).pw_name
					client_login = daemon.cmdlistener.users.uid_to_login(client_uid)

					if client_uid == 0 \
						or client_login in LicornPyroValidator.valid_users:
						logging.progress('''Authorized client connection from '''
							'''localhost:%s, user %s(%s).''' % ( client_socket,
							styles.stylize(styles.ST_NAME, client_login),
							styles.stylize(styles.ST_UGID, client_uid)))

						# connection is authorized.
						return 1,0
					else:
						return 0, Pyro.constants.DENIED_SECURITY
				except Exception, e:
					logging.warning(
						'something went wrong from localhost:%s (was %s).' % (
						client_socket, e))
					return 0, Pyro.constants.DENIED_UNSPECIFIED

		else:
			logging.warning('connection tentative from %s:%s' % (client_addr,
				client_socket))
			return 0, Pyro.constants.DENIED_HOSTBLOCKED
class CommandListener(LicornBasicThread):
	""" A Thread which collect INotify events and does what is appropriate with them. """

	def __init__(self, pname=dname, pids_to_wake=[], **kwargs):

		LicornBasicThread.__init__(self)

		self.name = "%s/%s" % (
			pname, str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self.pids_to_wake = pids_to_wake
		self.wake_threads = []

		for attr in kwargs:
			setattr(self, attr, kwargs[attr])

	def run(self):
		logging.progress("%s: thread running." % (self.name))

		Pyro.core.initServer()
		#Pyro.config.PYRO_TRACELEVEL=3
		#Pyro.config.PYRO_USER_TRACELEVEL=3
		#Pyro.config.PYRO_LOGFILE='pyro.log'
		#Pyro.config.PYRO_USER_LOGFILE='pyro.user.log'

		self.pyro_daemon=Pyro.core.Daemon()
		self.pyro_daemon.setNewConnectionValidator(LicornPyroValidator())
		self.pyro_daemon.cmdlistener = self
		self.uris = {}

		self.uris['configuration'] = self.pyro_daemon.connect(
			self.configuration,'configuration')
		self.uris['users'] = self.pyro_daemon.connect(
			self.users, 'users')
		self.uris['groups'] = self.pyro_daemon.connect(
			self.groups,'groups')
		self.uris['profiles'] = self.pyro_daemon.connect(
			self.profiles, 'profiles')
		self.uris['privileges'] = self.pyro_daemon.connect(
			self.privileges, 'privileges')
		self.uris['keywords'] = self.pyro_daemon.connect(
			self.keywords, 'keywords')
		self.uris['machines'] = self.pyro_daemon.connect(
			self.machines, 'machines')
		self.uris['msgproc'] = self.pyro_daemon.connect(
					self.msgproc, 'msgproc')

		logging.info("%s: %s Pyro daemon on port %s." % (
			self.name, styles.stylize(styles.ST_OK, "started"),
			self.pyro_daemon.port))
		logging.progress('%s: Pyro objects URI: %s' % (
			self.name, str(self.uris).replace('{', '\n{\n	').replace(
				', ', ',\n	').replace('}', '\n}')))

		for pid in self.pids_to_wake:
			t = Timer(0.25, lambda x: os.kill(x, signal.SIGUSR1), (pid,))
			self.wake_threads.append(t)
			t.start()

		while not self._stop_event.isSet():
			self.pyro_daemon.handleRequests(0.1)

		logging.info("%s: %s Pyro daemon." % (self.name,
			styles.stylize(styles.ST_BAD, "stopped")))
		self.pyro_daemon.shutdown(True)

		# don't forget to join these, to clean everything before exiting.
		for thread in self.wake_threads:
			thread.join()

		logging.progress("%s: thread ended." % (self.name))
