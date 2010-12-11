# -*- coding: utf-8 -*-
"""
Licorn core - http://dev.licorn.org/documentation/core

The Core API of a Licorn system.

([=\[(,\s])((users|groups|system|configuration|backends|privileges|profiles|machines)\.)

Copyright (C) 2005-2010 Olivier Cortès <oc@meta-it.fr>,
Licensed under the terms of the GNU GPL version 2
"""

# this @DEVEL@ will be replaced by package maintainers, don't alter it here.
version = '@DEVEL@'

import os, sys, time, signal, Pyro.core, Pyro.configuration
from threading import RLock

from licorn.foundations           import logging, exceptions
from licorn.foundations           import process, network
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import MixedDictObject
from licorn.foundations.constants import licornd_roles

def connect_error(dummy1, dummy2):
	logging.error('''daemon didn't wake us in 10 seconds, there is probably '''
		'''a problem with it. Please check %s for errors or contact your '''
		''' system administrator (if it's not you, else you're in trouble).''',
		200)

class LicornMasterController(MixedDictObject):
	_init_conf_minimal = False
	_init_conf_full    = False
	_licorn_protected_attrs = (
			MixedDictObject._licorn_protected_attrs
			+ ['backends', 'extensions', 'locks']
		)
	def __init__(self, name='LMC'):
		""" Default name is LMC because in 99.9% cases we've got only one LMC."""
		MixedDictObject.__init__(self, name)
		assert ltrace('core', '| %s.__init__(%s)' % (str(self.__class__), name))

		#: Create the internal lock manager. GiantLockProtectedObject class relies on it.
		self.locks = MixedDictObject('locks')
	def init_conf(self, minimal=False, batch=False):
		""" Init the configuration object. 2 scenarii:

			- init in one pass from the outside (calling with ``minimal=False``):
				internally we call 2 passes, to avoid problems with backends.
			- init in 2 passes from the outside: the same as internally.

		"""
		if LicornMasterController._init_conf_full or (
			minimal and LicornMasterController._init_conf_minimal):
			return

		try:
			from configuration import LicornConfiguration

			self.configuration = LicornConfiguration(
				minimal=True, batch=batch)

		except exceptions.BadConfigurationError, e:
			logging.error(e)

		if minimal:
			LicornMasterController._init_conf_minimal = True
		else:
			self.configuration.load(batch=batch)
			LicornMasterController._init_conf_full = True
	def init(self, batch=False):

		if not LicornMasterController._init_conf_full:
			self.init_conf(minimal=False, batch=batch)

		init_method = {
			licornd_roles.SERVER: self.__init_server,
			licornd_roles.CLIENT: self.__init_client,
			}

		self.__init_common()

		init_method[self.configuration.licornd.role]()
	def __init_common(self):

		# init the backends prior to controllers, which will use them.
		from backends import BackendManager
		self.backends = BackendManager()
		self.backends.load()

		# init the backends prior to controllers, which will use them.
		from licorn.extensions import ExtensionsManager
		self.extensions = ExtensionsManager()
		self.extensions.load()

		# load common core objects.
		from users  import UsersController
		from groups import GroupsController

		self.users  = UsersController()
		self.groups = GroupsController()

		# will load users as a dependancy.
		self.groups.load()

		# The Message processor is used to communicate with clients, via Pyro.
		# this is a special case coming from foundations, because other objects
		# in foundations rely on it.
		from licorn.foundations.messaging import MessageProcessor

		self.msgproc = MessageProcessor(
			ip_address=network.find_first_local_ip_address() \
				if self.configuration.licornd.role == licornd_roles.CLIENT \
				else None)

		from system import SystemController

		self.system = SystemController()

		self.system.load()
	def __init_client(self):
		""" as of now, client has only common. """
		pass
	def __init_server(self):

		from privileges import PrivilegesWhiteList

		self.locks.privileges = MixedDictObject()
		self.locks.privileges.giant_lock = RLock()

		self.privileges = PrivilegesWhiteList()
		self.privileges.load()

		# users and groups must be OK before everything.
		# for this, backends must be ready and configured.
		# check them first.
		self.backends.check(batch=True)

		# The daemon (in server mode) holds every core object. We *MUST* check
		# the configuration prior to everything else, to ensure the system is
		# in a good state before using or modifying it. minimal=False to be
		# sure every needed system group gets created.
		self.configuration.check(minimal=False, batch=True)

		from profiles import ProfilesController
		from keywords import KeywordsController
		from machines import MachinesController

		self.locks.profiles = MixedDictObject()
		self.locks.profiles.giant_lock = RLock()

		self.locks.machines = MixedDictObject()
		self.locks.machines.giant_lock = RLock()

		self.locks.keywords = MixedDictObject()
		self.locks.keywords.giant_lock = RLock()

		self.profiles = ProfilesController()
		self.profiles.load()
		self.machines = MachinesController()
		self.machines.load()
		self.keywords = KeywordsController()
		self.keywords.load()
	def reload_controllers_backends(self):
		""" run through all controllers and make them reload their backends. If
			one of them finds a new prefered backend, we must reload. Raise the
			appropriate exception. """
		for controller in self:
			if hasattr(controller, 'find_prefered_backend'):
				if controller.find_prefered_backend():
					raise exceptions.NeedRestartException('backends changed.')
	def connect(self):
		""" Return remote connexions to all Licorn® core objects. """

		assert ltrace('core', '> connect()')

		from configuration import LicornConfiguration
		self._localconfig = LicornConfiguration(minimal=True)

		if self._localconfig.licornd.role == licornd_roles.SERVER:
			pyroloc = 'PYROLOC://127.0.0.1:%s' % (
				self._localconfig.licornd.pyro.port)
		else:
			pyroloc = 'PYROLOC://%s:%s' % (
				self._localconfig.server_main_address,
				self._localconfig.licornd.pyro.port)

		# the opposite is already used to define licornd.pyro.port
		#Pyro.config.PYRO_PORT=_localconfig.licornd.pyro.port

		start_time = time.time()

		second_try=False
		while True:
			# this while seems infinite but is not.
			#   - on first succeeding connection, it will break.
			#   - on pyro exception (can't connect), the daemon will be forked and
			#     signals will be setup, to wait for the daemon to come up.
			#     - if daemons comes up, the loop restarts and should break because
			try:
				self.configuration = Pyro.core.getAttrProxyForURI(
					"%s/configuration" % pyroloc)
				self.configuration.noop()
				assert ltrace('core',
					'  connect(): main configuration object connected.')
				break
			except Pyro.errors.ProtocolError, e:
				if second_try:
					if self._localconfig.licornd.role == licornd_roles.SERVER:
						logging.error('''Can't connect to the daemon, but it '''
							'''has been successfully launched. I suspect '''
							'''you're in trouble (was: %s)''' % e, 199)
					else:
						logging.error('''Can't reach our daemon at %s, '''
							'''aborting. Check your network connection, '''
							'''cable, DNS and firewall.''' % stylize(ST_ADDRESS,
								'%s:%s' % (
									self._localconfig.server_main_address,
									self._localconfig.licornd.pyro.port)))

				if self._localconfig.licornd.role == licornd_roles.SERVER:
					# the daemon will fork in the background and the call will return
					# nearly immediately.
					process.fork_licorn_daemon(pid_to_wake=os.getpid())

					# wait to receive SIGUSR1 from the daemon when it's ready. On loaded
					# system with lots of groups, this can take a while, but it will
					# never take more than 10 seconds because of the daemon's
					# multithreaded nature, so we setup a signal to wake us
					# inconditionnaly in 10 seconds and report an error if the daemon
					# hasn't waked us in this time.
					signal.signal(signal.SIGALRM, connect_error)
					signal.alarm(10)

					# cancel the alarm if USR1 received.
					signal.signal(signal.SIGUSR1, lambda x,y: signal.alarm(0))

					logging.notice('waiting for daemon to come up…')

					# ALARM or USR1 will break the pause()
					signal.pause()
				second_try=True
		assert ltrace('core',
			'  connect(): connecting the rest of remote objects.')

		# connection is OK, let's get all other objects connected, and pull
		# them back to the calling process.
		self.machines   = Pyro.core.getAttrProxyForURI("%s/machines" % pyroloc)
		self.system     = Pyro.core.getAttrProxyForURI("%s/system" % pyroloc)
		self.rwi        = Pyro.core.getAttrProxyForURI("%s/rwi" % pyroloc)

		assert ltrace('timings', '@LMC.connect(): %.4fs' % (
			time.time() - start_time))
		del start_time

		assert ltrace('core', '< connect()')
		return self.rwi
	def release(self):
		""" Release all Pyro proxys. """
		assert ltrace('core', '| release()')
		for controller in self.items():
			if hasattr(controller, '_release'):
				controller._release()

LMC = LicornMasterController()

if sys.getdefaultencoding() == "ascii":
	reload(sys)
	sys.setdefaultencoding("utf-8")
