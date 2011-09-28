# -*- coding: utf-8 -*-
"""
Licorn core - http://docs.licorn.org/core.html

The Core API of a Licorn system.

([=\[(,\s])((users|groups|system|configuration|backends|privileges|profiles|machines)\.)

:copyright: 2005-2010 Olivier Cortès <oc@meta-it.fr>
:license: GNU GPL version 2
"""

from licorn.version import version

import os, sys, time, signal, Pyro.core, Pyro.configuration
from threading import RLock

from licorn.foundations           import logging, exceptions, options
from licorn.foundations           import process, network
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import MixedDictObject
from licorn.daemon                import roles

def connect_error(dummy1, dummy2):
	""" Method called on SIGALARM when the LMC fails to launch a daemon, or
		fails receiving the USR1 signal from it because it is too slow to boot.
		Exit with an error.
	"""

	logging.error('''daemon didn't wake us in 10 seconds, there is probably '''
		'''a problem with it. Please check %s for errors or contact your '''
		''' system administrator (if it's not you, else you're in trouble).''',
		200)

class LicornMasterController(MixedDictObject):
	""" The master container of all Licorn® system objects. It handles
		initialization of all of them. Can be considered as a master global
		object, permitting easy access to all others (which are thread-safe).

		The LMC is not thread-safe per-se, because it doesn't need to. Its
		methods are only used at daemon boot, when no other object and no
		thread exist.
	"""

	# these class attributes are used internally to be sure the initialization
	# is done in a good order. Don't touch them.
	_init_conf_minimal = False
	_init_conf_full    = False
	_init_first_pass   = False
	_init_common       = False
	_init_client       = False
	_init_server       = False

	#: names of attributes not stored in the :class:`dict` part of the
	#: :class:`MixedDictObject`, but as *real* attributes of the current
	#: :class:`LicornMasterController` instance.
	_licorn_protected_attrs = (
			MixedDictObject._licorn_protected_attrs
			+ [ 'locks', 'licornd' ]
		)
	@property
	def licornd(self):
		return self.__licornd
	@licornd.setter
	def licornd(self, licornd):

		#if not isinstance(licornd, LicornDaemon):
		#	raise exceptions.LicornRuntimeError(_(u'Cannot anything other than '
		#		'the daemon here!'))
		self.__licornd = licornd
	def __init__(self, licornd=None, master=True):
		""" Default name of :class:`LicornMasterController` is "LMC" because it
			is meant to be only one LMC.

			:param master: set to ``True`` when creating the first LMC instance,
				else ``False``. This will permit reusing already loaded
				controllers in helper LMCs (only used in CLIENT mode as of now).
		"""
		if master:
			MixedDictObject.__init__(self, 'LMC')
			self.__licornd = licornd
		else:
			MixedDictObject.__init__(self, 'HelperLMC')

		assert ltrace(TRACE_CORE, '| %s.__init__(%s)' % (str(self.__class__),
																	self.name))

		self._master = master

		# FIXME: get rid of these locks, they are useless now that everything
		# is on the daemon.
		self.locks = MixedDictObject('locks')

		self._ServerLMC = None
	def init_conf(self, minimal=False, batch=False):
		""" Init only the configuration object (prior to full LMC
			initialization). 3 scenarii are possible:
			- init in one pass (default, calling with ``minimal=False``).
			- init in 2 passes (will do the same as one pass init), like this::

				LMC.init_conf(minimal=True)
				...
				LMC.init_conf()

			- only init in minimal mode (used in the CLIENT daemon). This
			  permits to get a small configuration object, containing the
			  bare minimum to connect to a SERVER daemon.

			:param minimal: a boolean indicating if we want to initialize the
			                configuration object as small as possible.
			:param batch: a boolean to indicate that every problem encountered
			              during configuration initialization should be
			              corrected automatically (or not).
		"""
		if LicornMasterController._init_conf_full or (
			minimal and LicornMasterController._init_conf_minimal):
			return

		if self._master:

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
		else:
			self.configuration = LMC.configuration
	def init_server(self, batch=False):
		""" Meant to be called at the beginning of SERVER-daemon
			initialization. It is a one pass method. After having
			called it, the SERVER-daemon's `LMC` is ready to operate.
		"""

		assert LicornMasterController._init_conf_full

		self.__init_first_pass()
		self.__init_common()
		self.__init_server_final()
	def init_client_first_pass(self):
		""" Loads backends, users and groups only. There is a small difference
			between 2 calls of this method, on the client:

			* at the very first launch of the CLIENT-daemon (eg. after package
			  installation, it will load a **minimal** set of backends, and
			  load the according users and groups (presumably there will be
			  less than on the server).
			* at subsequent launches of the CLIENT-daemon, all backends are
			  the same as on the server (this has been taken care in
			  :meth:`init_client_second_pass`), and thus users and groups
			  contains the data from the server, merged with local (server's
			  data has precedence). """
		self.__init_first_pass()
	def init_client_second_pass(self, ServerLMC):
		""" Reload the backends, users and groups, to correspond to server data.

			* at very first launch of CLIENT daemon, this method will load all
			  missing backends (those not loaded by
			  :meth:`init_client_first_pass`), configuring them to point to the
			  server designed by :obj:`ServerLMC`, and restart the local daemon
			  if needed.
			* at subsequent launches, this method will do exactly nothing more
			  than the :meth:`init_client_first_pass`, because optional
			  backends are already configured since end of CLIENT-daemon first
			  launch.

			Even if doing nothing new, This two-pass init mechanism is necessary
			for the CLIENT daemon first-launch-auto-configuration-magic to work.

			:param ServerLMC: a reference to the SERVER-daemon LMC to inspect,
								in order to synchronize loaded backends and
								extensions. Stored as `self._ServerLMC`.
		"""

		assert not LicornMasterController._init_client
		assert LicornMasterController._init_first_pass

		self._ServerLMC = ServerLMC

		#print '>> server backends:', ServerLMC.system.get_backends(
		#													client_only=True)

		if self.backends.load(
				server_side_modules=ServerLMC.system.get_backends(
															client_only=True)):
			self.users.reload()
			self.groups.reload()

		self.__init_common()
		LicornMasterController._init_client = True
	def __init_first_pass(self):
		""" Load backends, users and groups.

			* on SERVER side, will load all enabled backends.
			* on CLIENT side:

				* at first launch, will do the same: load only the minimal
				  backend set (because others are not yet enabled)
				* on any other (re)launch, load the same backends as the
				  server, configured to link to it (because the second pass will
				  have done the dirty auto-configuration job).

		"""

		assert LicornMasterController._init_conf_full

		# NOTE: this couldn't have been done before, because EventsManager was
		# not up and ready. Now this will succeed, and we are still *before* all
		# other controllers load, so no event will be missed.
		L_event_collect(self.configuration)

		if self._master:

			# Initialize backends prior to controllers, because
			# controllers need backends to populate themselves.
			from backends import BackendsManager
			self.backends = BackendsManager()

			self.backends.load()

			# users and groups must be OK before everything. For this, backends
			# must be ready and configured, so we need to check them to be sure
			# their config is loaded and complete (eg. schemas in LDAP and that
			# sort of things).
			self.backends.check(batch=True)

			if self.configuration.licornd.role == roles.SERVER:
				# load common core objects.
				from users  import UsersController
				from groups import GroupsController

				self.users  = UsersController()
				self.groups = GroupsController()

				# groups will load users as a dependancy.
				self.groups.load()

			# We create it in first pass, because :class:`CommandListener` needs it.
			from licorn.foundations.messaging import MessageProcessor

			self.msgproc = MessageProcessor(
				ip_address=network.find_first_local_ip_address() \
					if self.configuration.licornd.role == roles.CLIENT \
					else None)

			# NOTE: we DO NOT collect events on message processor, because it
			# is not meant to listen for them.

			# NOTE: the msgproc must be connected to foundations.options,
			# in order for callbacks between pyro clients and server to work.
			# With this, the CLI knows how to call the MessageProcessor of
			# the daemon (which is how things work: the CLI always sends the
			# first message to the daemon, via an RPC).
			options.msgproc = LMC.msgproc

			from system import SystemController
			self.system = SystemController()
			self.system.load()

		else:
			self.backends = LMC.backends
			self.msgproc  = LMC.msgproc
			self.system   = LMC.system

			if self.configuration.licornd.role == roles.SERVER:
				self.users    = LMC.users
				self.groups   = LMC.groups

		LicornMasterController._init_first_pass = True
	def __init_common(self):
		""" Common phase of LMC.init between CLIENT and SERVER. Init the
			extensions after the controllers, and add extensions data to
			already existing objects.
		"""

		from licorn.extensions import ExtensionsManager
		self.extensions = ExtensionsManager()
		self.extensions.load(
			self._ServerLMC.system.get_extensions(client_only=True) \
				if self._ServerLMC else None)

		# extensions must have a clean configuration before continuing.
		self.extensions.check(batch=True)

		# we've got to reload users, groups and system, else they can't see
		# their own extensions (chicken and egg problem).
		if self.configuration.licornd.role == roles.SERVER:
			self.users.reload_extensions()
			self.groups.reload_extensions()

		self.system.reload_extensions()
	def __init_server_final(self):
		""" Final phase of SERVER initialization. Load system controllers
			and objects that doesn't need anything but are required to work.
		"""

		from privileges import PrivilegesWhiteList

		self.privileges = PrivilegesWhiteList()

		self.privileges.load()

		# The daemon (in server mode) holds every core object. We *MUST* check
		# the configuration prior to everything else, to ensure the system is
		# in a good state before using or modifying it. minimal=False to be
		# sure every needed system group gets created.
		self.configuration.check(minimal=False, batch=True)

		from profiles import ProfilesController
		from keywords import KeywordsController
		from machines import MachinesController

		self.profiles = ProfilesController()
		self.profiles.load()
		self.machines = MachinesController()
		self.machines.load()
		self.keywords = KeywordsController()
		self.keywords.load()
	def terminate(self):

		if self._ServerLMC:
			del LMC._ServerLMC
	def reload_controllers_backends(self):
		""" Walk through all controllers and make them reload their backends. If
			one of them finds a new prefered backend, we must restart the
			daemon: raise the appropriate exception to be catched in
			:term:`MainThread` and handle the stop/start operations.
		"""
		assert ltrace(TRACE_CORE, '| reload_controllers_backends()')

		for controller in self:
			if hasattr(controller, 'find_prefered_backend'):

				# first, reload the list of compatible backends. If this method
				# is called, there is at least one more or one less.
				controller.backends = self.backends.find_compatibles(controller)

				# then, tell the controller to find its new prefered in its
				# refreshed backends list.
				if controller.find_prefered_backend():
					raise exceptions.NeedRestartException(_(u'backends changed.'))

					# TODO: restart all the CLIENT-daemons too, to (un-) load
					# the new backend(s), synchronized with the server.
	def connect(self):
		""" Create remote connections to all Licorn® core objects. This method
			excludes calling all other `init*()` methods, because LMC can't be
			used both locally and remotely.

			Returns the Pyro proxy for the RWI (this is just a shortcut, because
			the RWI proxy is always accessible via :obj:`LMC.rwi`; but this
			makes easier to write the following code in CLI tools::

				LMC = LicornMasterController()
				RWI = LMC.connect()
				...

		"""

		assert ltrace(TRACE_CORE, '> connect()')

		from licorn.core.configuration import LicornConfiguration
		self._localconfig = LicornConfiguration(minimal=True)

		if self._localconfig.licornd.role == roles.SERVER:
			pyroloc = 'PYROLOC://127.0.0.1:%s' % (
				self._localconfig.licornd.pyro.port)
		else:
			logging.progress(_(u'trying to connect to server %s.') %
									 self._localconfig.server_main_address)
			pyroloc = 'PYROLOC://%s:%s' % (
				self._localconfig.server_main_address,
				self._localconfig.licornd.pyro.port)

			if not self._master:
				# remove current values of controllers, they are pointing to LMC.
				self.configuration = None
				self.backends = None
				self.extension = None
				self.users = None
				self.groups = None
				self.system = None
				self.msgproc = None

		# the opposite is already used to define licornd.pyro.port
		#Pyro.config.PYRO_PORT=_localconfig.licornd.pyro.port

		start_time = time.time()

		second_try=False
		while True:
			# This while seems infinite but is not.
			#   - on first succeeding connection, it will break.
			#   - on pyro exception (can't connect), the daemon will be forked
			#	  and signals will be setup, to wait for the daemon to come up:
			#     if the daemon comes up, the loop restarts and should break
			#	  because connection succeeds.
			try:
				self.configuration = Pyro.core.getAttrProxyForURI(
					"%s/configuration" % pyroloc)
				self.configuration._setTimeout(5)
				self.configuration.noop()
				assert ltrace(TRACE_CORE,
					'  connect(): main configuration object connected (Remote is SERVER).')

				# connection is OK, let's get all other objects connected, and pull
				# them back to the calling process.
				#self.machines = Pyro.core.getAttrProxyForURI("%s/machines" % pyroloc)
				self.rwi = Pyro.core.getAttrProxyForURI("%s/rwi" % pyroloc)
				self.system = Pyro.core.getAttrProxyForURI("%s/system" % pyroloc)
				break

			except AttributeError:
				self.system = Pyro.core.getAttrProxyForURI(
					"%s/system" % pyroloc)
				self.system._setTimeout(5)
				self.system.noop()
				assert ltrace(TRACE_CORE,
					'  connect(): main system object connected (Remote is CLIENT).')
				break

			except Pyro.errors.ProtocolError, e:

				if e.args[0] == 'security reasons':
					logging.error(_(u'Your user account is not allowed to '
									u'connect to the Licorn® daemon.'))
					sys.exit(911)

				if second_try:
					if self._localconfig.licornd.role == roles.SERVER:
						logging.error('''Can't connect to the daemon, but it '''
							'''has been successfully launched. I suspect '''
							'''you're in trouble (was: %s)''' % e, 199)
					else:
						logging.warning(_(u'Cannot reach our daemon at %s, '
							u'retrying in 5 seconds. Check your network '
							u'connection, cable, DNS and firewall. Perhaps the '
							u'Licorn® server is simply down.') %
								stylize(ST_ADDRESS, u'pyro://%s:%s' % (
									self._localconfig.server_main_address,
									self._localconfig.licornd.pyro.port)))
						time.sleep(5.0)
						continue

				if self._localconfig.licornd.role == roles.SERVER:
					# the daemon will fork in the background and the call will
					# return nearly immediately.
					process.fork_licorn_daemon(pid_to_wake=os.getpid())

					# wait to receive SIGUSR1 from the daemon when it's ready.
					# On loaded system with lots of groups, this can take a
					# while, but it will never take more than 10 seconds because
					# of the daemon's multithreaded nature, so we setup a signal
					# to wake us inconditionnaly in 10 seconds and report an
					# error if the daemon hasn't waked us in this time.
					signal.signal(signal.SIGALRM, connect_error)
					signal.alarm(10)

					# cancel the alarm if USR1 received.
					signal.signal(signal.SIGUSR1, lambda x,y: signal.alarm(0))

					logging.notice(_(u'waiting for daemon to come up…'))

					# ALARM or USR1 will break the pause()
					signal.pause()
				second_try=True


		assert ltrace(TRACE_TIMINGS, '@LMC.connect(): %.4fs' % (
			time.time() - start_time))
		del start_time

		assert ltrace(TRACE_CORE, '< connect()')

		try:
			return self.rwi

		except AttributeError:
			# the remote daemon has only the `system` attribute, it's a CLIENT.
			return self.system
	def release(self):
		""" Release all Pyro proxys. """
		assert ltrace(TRACE_CORE, '| release()')
		for controller in self.items():
			if hasattr(controller, '_release'):
				controller._release()

LMC = LicornMasterController()

if sys.getdefaultencoding() == "ascii":
	reload(sys)
	sys.setdefaultencoding("utf-8")
