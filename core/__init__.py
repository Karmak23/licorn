# -*- coding: utf-8 -*-
"""
Licorn core - http://docs.licorn.org/core.html

The Core API of a Licorn system.

:copyright:
	* 2005-2012 Olivier Cortès <olive@licorn.org>
	* 2009-2012 META IT http://meta-it.fr/
:license: GNU GPL version 2
"""

from licorn.version import version

import os, sys, time, signal, Pyro.core, Pyro.configuration
from threading import current_thread, Timer

from licorn.foundations.threads   import RLock
from licorn.foundations           import logging, exceptions, options, settings
from licorn.foundations           import process, network, events
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import MixedDictObject
from licorn.foundations.constants import reasons, roles, priorities

from licorn.foundations.events import LicornEvent

timeout = settings.connect.timeout
msgth   = None

def connect_error(dummy1, dummy2):
	""" Method called on SIGALARM when the LMC fails to launch a daemon, or
		fails receiving the USR1 signal from it because it is too slow to boot.
		Exit with an error.
	"""

	logging.error(_(u'The daemon did not wake us in {0} seconds, there is '
		u'probably a problem with it. Please check the log for errors or '
		u'contact your system administrator if it is not you. Else you '
		u'already know you are in trouble ;-)').format(timeout), 911)
def start_message_thread():
	global msgth

	msgth = Timer(3, logging.notice, args=(_(u'Connection '
		u'established. Please be patient, the daemon seems '
		u'quite busy.'), ))

	msgth.start()

def stop_message_thread():
	global msgth
	try:
		# don't display the waiting message if not already done.
		msgth.cancel()

	except:
		logging.notice(_(u'OK. We\'re running now!'))

	del msgth

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
	def __init__(self, *args, **kwargs):
		""" Default name of :class:`LicornMasterController` is "LMC" because it
			is meant to be only one LMC.

			:param master: set to ``True`` when creating the first LMC instance,
				else ``False``. This will permit reusing already loaded
				controllers in helper LMCs (only used in CLIENT mode as of now).
		"""

		licornd = kwargs.pop('licornd', None)
		master  = kwargs.pop('master', True)

		if master:
			super(LicornMasterController, self).__init__(name='LMC')

		else:
			super(LicornMasterController, self).__init__(name='HelperLMC')

		self.__licornd = licornd

		assert ltrace_func(TRACE_CORE)

		self._master = master

		self._connect_lock = RLock()
		self._connections  = 0

		self._ServerLMC = None

		events.collect(self)
	def __init_configuration(self, batch=False):
		""" Init the configuration object, prior to full LMC initialization.

			:param batch: a boolean indicating that every problem encountered
			              during configuration initialization should be
			              corrected automatically (default: ``False``).
		"""
		if LicornMasterController._init_conf_full:
			return

		if self._master:

			try:
				from configuration import LicornConfiguration

				self.configuration = LicornConfiguration(minimal=True, batch=batch)

			except exceptions.BadConfigurationError, e:
				logging.error(e)

			self.configuration.load(batch=batch)

			LicornMasterController._init_conf_full = True

		else:
			self.configuration = LMC.configuration
	def init_server(self, batch=False):
		""" Meant to be called at the beginning of SERVER-daemon
			initialization. It is a one pass method. After having
			called it, the SERVER-daemon's `LMC` is ready to operate.

			:param batch: a boolean specifying the configuration should
				be loaded in ``batch`` mode, which means it will correct
				every needed part of the system to work.
		"""

		self.__init_configuration(batch=batch)
		self.__init_first_pass()
		self.__init_common()
		self.__init_server_final()
	def init_client_first_pass(self, batch=False):
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
		self.__init_configuration(batch=batch)
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

		logging.info(_(u'Server backends: {0}').format(
						ServerLMC.system.get_backends(client_only=True)))

		self.backends.load(
				server_side_modules=ServerLMC.system.get_backends(
															client_only=True))

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

			if settings.role == roles.SERVER:
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
					if settings.role == roles.CLIENT \
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

			if settings.role == roles.SERVER:
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
		if settings.role == roles.SERVER:
			self.users.reload_extensions()
			self.groups.reload_extensions()

		# no more needed. system will eventually be integrated into RWI
		# but should at least become no more a real controller.
		#self.system.reload_extensions()
	def __init_server_final(self):
		""" Final phase of SERVER initialization. Load system controllers
			and objects that doesn't need anything but are required to work.
		"""

		from privileges import PrivilegesWhiteList

		self.privileges = PrivilegesWhiteList()

		self.privileges.load()

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
					LicornEvent('need_restart',
						reason=reasons.BACKENDS_CHANGED).emit(priorities.HIGH)

					# TODO: restart all the CLIENT-daemons too, to (un-) load
					# the new backend(s), synchronized with the server.
	def connect(self, delayed_daemon_start=False):
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
		assert ltrace_func(TRACE_CORE, level=99)

		# we need to protect the whole method, in case 2 threads try to
		# connect in // (this happens at WMI start).
		with self._connect_lock:
			self._connections += 1

			if self._connections > 1:
				# someone already connected us, just return the current
				# connected master object.
				return self.rwi

			if settings.role == roles.SERVER:
				pyroloc = 'PYROLOC://127.0.0.1:%s' % (settings.pyro.port)
			else:
				logging.progress(_(u'trying to connect to server %s.') %
													settings.server_main_address)
				pyroloc = 'PYROLOC://%s:%s' % (settings.server_main_address,
												settings.pyro.port)

				if not self._master:
					# remove current values of controllers, they are pointing to LMC.
					self.configuration = None
					self.backends = None
					self.extension = None
					self.users = None
					self.groups = None
					self.system = None
					self.msgproc = None

			# the opposite is already used to define pyro.port
			#Pyro.config.PYRO_PORT=settings.pyro.port

			start_time      = time.time()
			second_try      = False
			already_delayed = False

			while True:
				# This while seems infinite but is not.
				#   - on first succeeding connection, it will break.
				#   - on pyro exception (can't connect), the daemon will be forked
				#	  and signals will be setup, to wait for the daemon to come up:
				#     if the daemon comes up, the loop restarts and should break
				#	  because connection succeeds.
				try:
					start_message_thread()

					# a server daemon offers 'LMC.rwi' + `LMC.system`
					self.rwi = Pyro.core.getAttrProxyForURI("%s/rwi" % pyroloc)

					# Set a timeout for establishing the connection.
					# On a loaded daemon which is in the process of setting up
					# inotifier watches, this can be long.
					self.rwi._setTimeout(timeout)

					# be sure the connection can be established; without this
					# call, Pyro is lazy and doens't check someone really
					# listens at the other end.
					self.rwi.noop()

					# Cancel the status display as soon as `noop()` returns.
					stop_message_thread()

					# re-set an infinite timeout for normal operations, because
					# CLI methods can last a very long time (thinking about
					# `CHK`), while nothing is transmitted via the Pyro tunnel
					# all output goes via another thread / tunnel, and the
					# operation caller has just to wait that the called method
					# returns.
					self.rwi._setTimeout(0)

					assert ltrace(TRACE_CORE,
						'  connect(): RWI object connected (Remote is SERVER).')
					break

				except AttributeError:
					# a client daemon only offers "LMC.system", for remote-control.
					# This is used from `get {inside,events,status}` commands
					# with `export LICORN_SERVER=...` to inspect client daemons.

					self.system = Pyro.core.getAttrProxyForURI(
															"%s/system" % pyroloc)
					self.system._setTimeout(timeout)
					self.system.noop()

					stop_message_thread()

					assert ltrace(TRACE_CORE,
						'  connect(): system object connected (Remote is CLIENT).')
					break

				except Pyro.errors.ProtocolError, e:

					# We won't connect, whatever the reason. Don't display
					# the status waiting message.
					stop_message_thread()

					if e.args[0] == 'security reasons':
						logging.error(_(u'Your user account is not allowed to '
										u'connect to the Licorn® daemon.'))
						sys.exit(911)

					if second_try:
						if settings.role == roles.SERVER:
							logging.error(_(u'Cannot connect to the daemon, '
								u'but it has been successfully launched. I '
								u' suspect you are in trouble (was: %s)') %
									e, 199)
						else:
							logging.warning(_(u'Cannot reach our daemon at %s, '
								u'retrying in 5 seconds. Check your network '
								u'connection, cable, DNS and firewall. Perhaps '
								u' the Licorn® server is simply down.') %
									stylize(ST_ADDRESS, u'pyro://%s:%s' % (
										settings.server_main_address,
										settings.pyro.port)))
							time.sleep(5.0)
							continue

					if settings.role == roles.SERVER:

						if delayed_daemon_start and not already_delayed:
							already_delayed = True
							time.sleep(5.0)
							continue

						# The daemon will fork in the background and the call
						# will return nearly immediately.
						process.fork_licorn_daemon(pid_to_wake=os.getpid())

						# Wait to receive SIGUSR1 from the daemon when it's
						# ready. On loaded system with lots of groups, this
						# can take a while (I observed ~12min for 45K watches
						# on my Core i3 2,6Ghz + 8Gb + 4Tb RAID0 system), but
						# it will never take more than `first_connect_timeout`
						# seconds because of the daemon's multithreaded
						# nature. Thus we setup a signal to wake us
						# inconditionnaly after the timeout and report an
						# error if the daemon hasn't waked us in this time.
						signal.signal(signal.SIGALRM, connect_error)
						signal.alarm(timeout)

						# Cancel the alarm if USR1 received.
						signal.signal(signal.SIGUSR1, lambda x,y: signal.alarm(0))

						logging.notice(_(u'Waiting up to {0} seconds for '
										u'daemon to come up… Please hold '
										u'on.').format(timeout))

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

	def release(self, force=False):
		""" Release all Pyro proxys. """

		# we need to protect the whole method in case 2 threads try to
		# disconnect at the same time (this can happen in the WMI, with the
		# @lmc_connected decorator).
		with self._connect_lock:
			if force:
				self._connections = 0

			else:
				self._connections -= 1

			if self._connections != 0:
				# there are still some parts of the current interpreter
				# connected or using the connection, or the connection has already
				# been closed with force=True by someone else.
				# Don't try to `release()` anything.
				return

			assert ltrace_func(TRACE_CORE)

			for controller in self.items():
				if hasattr(controller, '_release'):
					controller._release()
					controller.close()
	@events.handler_method
	def backend_enabled(self, *args, **kwargs):
		self.reload_controllers_backends()
	@events.handler_method
	def backend_disabled(self, *args, **kwargs):
		self.reload_controllers_backends()

LMC = LicornMasterController()

__all__ = ('LMC', )
