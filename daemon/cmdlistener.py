# -*- coding: utf-8 -*-
"""
Licorn Daemon CommandListener, implemented with Pyro (Python Remote Objects)

:copyright: 2007-2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2.
"""

import signal, os, time, new, pwd
import Pyro.core, Pyro.protocol, Pyro.configuration, Pyro.constants

from threading import Thread, Timer, current_thread
from licorn.foundations.threads import RLock

from licorn.foundations           import logging, settings, exceptions
from licorn.foundations           import process, network, pyutils, events
from licorn.foundations.events    import LicornEvent
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.constants import host_status, host_types, priorities, roles

from licorn.core                  import LMC
from licorn.daemon.threads        import LicornBasicThread

def _pyro_thread_dump_status(self, long_output=False, precision=None, as_string=True):
	if as_string:
		return u'\t%s%s: RWI calls for %s(%s) @%s:%s %s\n' % (
			stylize(ST_RUNNING if self.is_alive() else ST_STOPPED, self.name),
			stylize(ST_OK, u'&') if self.daemon else '',
			stylize(ST_LOGIN, self._licorn_remote_user),
			stylize(ST_UGID, self._licorn_remote_uid),
			self._licorn_remote_address,
			self._licorn_remote_port,
			('(started %s)' % pyutils.format_time_delta(
						self._licorn_thread_start_time - time.time(),
						use_neg=True, long_output=False)))
	else:
		return dict(
			alive=self.is_alive(),
			name=self.name,
			daemon=self.daemon,
			remote_user=self._licorn_remote_user,
			remote_uid=self._licorn_remote_uid,
			remote_address=self._licorn_remote_address,
			remote_port=self._licorn_remote_port,
			started=self._licorn_thread_start_time - time.time()
		)
class LicornPyroValidator(Pyro.protocol.DefaultConnValidator):
	""" Validator class for Pyro connections, for both client and server
		licornd. Modes of operations:
		* the client only authorize connexions from localhost and its server.
		* the server authorize connexions from localhost and any local client,
		provided the client has a Pyro daemon running on a restricted port, and
		the originating socket comes from a process launched by an authorized
		user (member of group 'admins').
	"""
	#: A list of local (loopback) interfaces. 127.0.1.1 is here because included
	#: in Ubuntu (don't know why they don't just use the plain 127.0.0.1).
	local_interfaces = [ '127.0.0.1', '127.0.1.1' ]

	#: :attr:`pyro_port` will be filled by :term:`pyro.port` value
	#: before the thread starts. See :ref:`configuration` object for details
	#: about port numbers.
	pyro_port = None

	#: The main server IP address. Can be overidden by the environment variable
	#: :envvar:`LICORN_SERVER` to help debugging the daemon.
	server = None

	#: A list of other server IP addresses, gathered from the client thread
	#: :func:`thread_greeter`. The auxilliary IP addresses are needed when our
	#: server has more than one interface, because connection can initiate from
	#: any of them.
	server_addresses = []

	#: a list of address undergoing bi-directionnal checking (server-to-server),
	#: kept as references to avoid more-than-once checking (this can exhaust
	#: system resources and lead to issue #452.
	current_checks = []

	#: this RLock is needed because of pyro multi-threaded nature. We don't
	#: want to check a remote system twice because of a miss on
	#: self.current_check.
	check_lock = RLock()

	def __init__(self, role):
		Pyro.protocol.DefaultConnValidator.__init__(self)

		#: A local copy of :ref:`settings.role`, to avoid importing LMC here.
		self.role = role
	def acceptHost(self, daemon, connection):
		""" Basic check of the connection. See :class:`LicornPyroValidator` for
			details. """
		client_addr, client_socket = connection.addr

		assert ltrace(TRACE_CMDLISTENER, 'connection from %s:%s' % (
			client_addr, client_socket))

		if client_addr in LicornPyroValidator.local_interfaces:

			try:
				client_uid, client_pid = process.find_network_client_infos(
					LicornPyroValidator.pyro_port, client_socket,
					local=True if client_addr[:3] == '127' else False, pid=True)

			except Exception, e:
				logging.warning('error finding network connection from '
					'localhost:%s (was %s).' % (client_socket, e))

				return 0, Pyro.constants.DENIED_UNSPECIFIED

			else:
				accept, reason = self.acceptUid(daemon, client_uid, None,
												client_addr, client_socket)

				if accept and client_pid:
					# record the PID for SIGUSR2 eventual sending on restart.
					CommandListener.add_listener_pid(client_pid)

				return accept, reason
		else:
			if self.role == roles.SERVER:
				# connect to the client's Pyro daemon and make sure the request
				# originates from a valid user.
				#
				# FIXME: this is far from perfect and secure, but quite
				# sufficient for testing and deploying. Better security will
				# come when everything works.

				remote_system = Pyro.core.getAttrProxyForURI(
									"PYROLOC://%s:%s/system" % (client_addr,
										LicornPyroValidator.pyro_port))
				remote_system._setTimeout(3.0)

				with LicornPyroValidator.check_lock:
					if client_addr in LicornPyroValidator.current_checks:

						# ACCEPT the connection, don't start a check-loop.
						LicornPyroValidator.current_checks.remove(client_addr)

						t = self.setup_licorn_thread('root', 0,
												client_addr, client_socket)

						logging.monitor(TRACE_CMDLISTENER,
							'{0}/{1}: connection check validated for {2}:{3}.',
								t.name, self.__class__.__name__,
									client_addr, client_socket)
						return 1, 0

					else:
						LicornPyroValidator.current_checks.append(client_addr)
						logging.monitor(TRACE_CMDLISTENER,
							'{0}/{1}: connection check stored for {2}:{3}.',
								current_thread().name, self.__class__.__name__,
									client_addr, client_socket)

				try:
					client_uid, client_login = remote_system.explain_connecting_from(
																client_socket)

				except:
					logging.exception(_(u'Problem finding uid initiating '
							u'connection from {0}:{1}, denying request.'),
								client_addr, client_socket)

					return 0, Pyro.constants.DENIED_UNSPECIFIED

				else:
					return self.acceptUid(daemon, client_uid, client_login,
										client_addr, client_socket)
			else:
				# FIXME: we are on the client, just accept any connection
				# coming from our server, else deny. This must be refined to be
				# sure the connection is valid, but i've got no idea yet on how
				# to do it properly.
				if client_addr == LicornPyroValidator.server \
					or client_addr in LicornPyroValidator.server_addresses:

					logging.monitor(TRACE_CMDLISTENER,
						'{0}/{1}: server connection accepted from {2}:{3}.',
							current_thread().name, self.__class__.__name__,
								client_addr, client_socket)

					self.setup_licorn_thread('root', 0,
											client_addr, client_socket)

					# ACCEPT
					return 1, 0
				else:
					logging.warning(_(u'Denied connection tentative '
						u'from {0}:{1} (allowed are {2} and {3}).').format(
							client_addr, client_socket,
							LicornPyroValidator.server,
							', '.join(LicornPyroValidator.server_addresses)))

					return 0, Pyro.constants.DENIED_HOSTBLOCKED
	def acceptUid(self, daemon, client_uid, client_login, client_addr, client_socket):
		try:
			# NOTE: measured with LICORN_TRACE=timings, using pwd.getpwuid()
			# is **at best** as quick as users.uid_to_login(), but generally
			# slower. Thus we use our internals.
			#client_login = pwd.getpwuid(client_uid).pw_name

			if settings.role == roles.CLIENT:

				if client_addr.startswith('127.'):
					logging.warning(_(u'Please implement client.server.bounce '
						u'auth. Accepted for now (localhost, uid {0}).').format(
							stylize(ST_UGID, client_uid)))

					t = self.setup_licorn_thread('<unknown>', client_uid,
												client_addr, client_socket)

					return 1, 0
				else:
					logging.warning(_(u'Senseless connection tentative from {0}, '
						u'uid {2}.').format(
							stylize(ST_ADDRESS, '%s:%s' % (client_addr, client_socket)),
							stylize(ST_UGID, client_uid)))

					return 0, Pyro.constants.DENIED_SECURITY
			else:
				local_login = LMC.users.uid_to_login(client_uid)

		except (exceptions.DoesntExistException, KeyError), e:
			logging.warning(_(u'Connection tentative from {0}: '
							u'unknown local UID {1}!').format(
					stylize(ST_ADDRESS, '%s:%s' % (client_addr, client_socket)),
					stylize(ST_UGID, client_uid)))

			return 0, Pyro.constants.DENIED_SECURITY

		except Exception, e:
			logging.warning(_(u'Something went wrong from {0} '
				u'(was: {1}).').format(
					stylize(ST_ADDRESS, '%s:%s' % (client_addr, client_socket)),
					e))
			pyutils.print_exception_if_verbose()

			return 0, Pyro.constants.DENIED_UNSPECIFIED

		else:
			if client_login:
				if client_login != local_login:
					# TODO: send an alert ?
					logging.warning(_(u'Remote login {0} is different from '
						u'local {1} for UID {2}. Using {0}.').format(
						stylize(ST_LOGIN, client_login),
						stylize(ST_LOGIN, local_login),
						stylize(ST_UGID, client_uid)))

				# remote login takes precedence
				local_login = client_login

			assert ltrace(TRACE_CMDLISTENER, 'currently authorized users: %s.' %
					', '.join(stylize(ST_LOGIN, u.login)
						for u in LMC.groups.by_name(
									settings.defaults.admin_group
										).all_members))

			if client_uid == 0 \
				or client_uid in [x.uidNumber for x in LMC.groups.by_name(
									settings.defaults.admin_group
										).all_members]:

				t = self.setup_licorn_thread(local_login, client_uid,
										client_addr, client_socket)

				logging.progress(_(u'{0}/{1}: authorized client connection from '
						u'{2}:{3}, user {4}({5}).').format(
						t.name, self.__class__.__name__,
						client_addr, client_socket,
						stylize(ST_NAME, local_login),
						stylize(ST_UGID, client_uid)))

				# ACCEPT
				return 1, 0
			else:
				logging.warning(_(u'Connection tentative from {0}:{1}, '
					u'user {2}({3}).').format(client_addr, client_socket,
						client_login, client_uid))

				return 0, Pyro.constants.DENIED_SECURITY

	def setup_licorn_thread(self, client_login, client_uid,
								client_addr, client_socket):
		# When a Pyro connection is granted, the current thread (already
		# created by Pyro) will survive and possibly live a long
		# time. We attach our own attributes and methods to it, to
		# integrate it a little more in Licorn® (most notably
		# in the daemon status).
		t = current_thread()

		# Set a smarter name than 'Thread-28', easier to track in status.
		t.setName('Pyro' + t.name)

		t._licornd                  = LMC.licornd
		t._licorn_remote_user       = client_login
		t._licorn_remote_uid        = client_uid
		t._licorn_remote_address    = client_addr
		t._licorn_remote_port       = client_socket
		t._licorn_thread_start_time = time.time()
		t._pyro_thread_dump_status  = new.instancemethod(
						_pyro_thread_dump_status, t, t.__class__)
		return t
class CommandListener(LicornBasicThread):
	""" A Thread which answer to Pyro remote commands. """

	listeners_pids = set()
	# we need to protect the set() from multi-thread access.
	lplock         = RLock()

	@classmethod
	def add_listener_pid(cls, pid_to_add):

		with cls.lplock:
			for pid in cls.listeners_pids.copy():
				if not os.path.exists('/proc/%s/cmdline' % pid):
					cls.listeners_pids.remove(pid)

			cls.listeners_pids.add(pid_to_add)
	def __init__(self, pids_to_wake1=None, pids_to_wake2=None, *args, **kwargs):
		assert ltrace(TRACE_CMDLISTENER, '| CommandListener.__init__()')

		daemon = kwargs.pop('daemon', False)
		kwargs['tname'] = 'CommandListener'

		LicornBasicThread.__init__(self, *args, **kwargs)

		# The :class:`Thread` attribute
		self.daemon = daemon

		# Wake them with USR1
		self.pids_to_wake1 = pids_to_wake1 or []

		# Wake them with USR2
		self.pids_to_wake2 = pids_to_wake2 or []

		self.wake_threads = []
	def dump_status(self, long_output=False, precision=None, as_string=True):
		""" get detailled thread status. """
		if long_output:
			uri_status= '\n\tObjects URI: %s' % str(self.uris).replace(
				'{', '\n\t\t').replace(', ', ',\n\t\t').replace('}', '')

		else:
			uri_status = ''

		if as_string:
			return '%s(%s%s) %s (%d loops, %d wakers)%s%s' % (
				stylize(ST_NAME, self.name),
				self.ident, stylize(ST_OK, '&') if self.daemon else '',
				stylize(ST_OK, 'alive') \
					if self.is_alive() else 'has terminated',
				self._pyro_loop, len(self.wake_threads), uri_status,
				self.dump_pyro_connections(long_output, precision)
			)
		else:
			return dict(
				name=self.name,
				ident=self.ident,
				daemon=self.daemon,
				alive=self.is_alive(),
				loops=self._pyro_loop,
				wakers=len(self.wake_threads),
				uri_status=uri_status,
				connections=self.dump_pyro_connections(long_output, precision, as_string)
			)
	def dump_pyro_connections(self, long_output=False, precision=None, as_string=True):
		""" """
		if as_string:
			data = '\n'
			for conn in self.pyro_daemon.connections:
				if isinstance(conn, Pyro.protocol.TCPConnection):
					#data += '\tTCPConn %s: %s:%s ‣ %s:%s\n'
					data += '%s\n' % str(conn)

				elif isinstance(conn, Thread):
					try:
						data += conn._pyro_thread_dump_status(long_output, precision, as_string)
					except AttributeError:
						data += (u'thread %s%s(%s) does not implement '
									u'dump_status().\n' % (
									stylize(ST_NAME, conn.name),
									stylize(ST_OK, u'&') if conn.daemon else '',
									conn.ident))
				else:
					data += 'unknown %s\n' % str(conn)

			# remove last trailing '\n'
			return data[:-1]

		else:
			conns = []
			for conn in self.pyro_daemon.connections:
				if isinstance(conn, Thread):
					try:
						conns.append(conn._pyro_thread_dump_status(
										long_output, precision, as_string))
					except AttributeError:
						conns.append(process.thread_basic_info(conn))
				else:
					conns.append(dict(name=str(conn)))
			return conns
	def run(self):
		assert ltrace(TRACE_THREAD, '%s running' % self.name)

		LicornEvent('command_listener_starts').emit()

		if self.licornd.opts.initial_check:
			logging.notice(_(u'{0}: not starting because initial '
							u'check in progress.').format(self.pretty_name))
			return

		Pyro.core.initServer()
		Pyro.config.PYRO_PORT=settings.pyro.port

		count = 0

		while not self._stop_event.isSet():
			try:
				# by default Pyro listens on all interfaces, no need to refine.
				self.pyro_daemon=Pyro.core.Daemon(norange=1,
												port=settings.pyro.port)
				break
			except Pyro.core.DaemonError, e:
				logging.warning('''%s: %s. '''
					'''waiting (total: %ds).''' % (self.name, e, count))
				count += 1
				time.sleep(1)

		if self._stop_event.is_set():
			# happens with a Control-C during the previous while and pyro daemon
			# didn't start (we are stopping and didn't acheive to really start).
			return

		# get the port number from current configuration.
		LicornPyroValidator.pyro_port = settings.pyro.port

		# dynamicly gather local interfaces IP addresses
		LicornPyroValidator.local_interfaces.extend(
			network.local_ip_addresses())

		if settings.role == roles.CLIENT:
			LicornPyroValidator.server = LMC.configuration.server_main_address

		self.pyro_daemon.setNewConnectionValidator(
			LicornPyroValidator(settings.role))
		self.pyro_daemon.cmdlistener = self
		self.uris = {}

		if settings.role == roles.SERVER:

			# for clients: centralized configuration.
			self.uris['configuration'] = self.pyro_daemon.connect(
											LMC.configuration, 'configuration')

			# Used by CLI.
			self.uris['rwi'] = self.pyro_daemon.connect(self.licornd.rwi, 'rwi')

			# TODO: for other daemons (cluster ?)
			#self.uris['machines'] = self.pyro_daemon.connect(
			#	LMC.machines, 'machines')

		# CLIENT and SERVER export their system and msgproc to communicate
		# with each other.
		#
		# FIXME: server exporting system is not very secure...
		self.uris['system'] = self.pyro_daemon.connect(
			LMC.system, 'system')

		self.uris['msgproc'] = self.pyro_daemon.connect(
					LMC.msgproc, 'msgproc')

		logging.info(_(u'{0}: {1} to answer requests at {2}.').format(
								self.name, stylize(ST_OK, _(u'ready')),
								stylize(ST_URL, u'pyro://*:%s'
									% self.pyro_daemon.port)))

		def wake_pid(pid, wake_signal):
			try:
				os.kill(pid, wake_signal)

			except OSError, e:
				# no such process, not a real problem.
				if e.errno != 3:
					raise e

		for pids_list, wake_signal in ((self.pids_to_wake1, signal.SIGUSR1),
										(self.pids_to_wake2, signal.SIGUSR2)):
			for pid in pids_list:
				th = Timer(0.25, wake_pid, (pid, wake_signal))
				self.wake_threads.append(th)
				assert ltrace(TRACE_THREAD, '%s starting wake up thread %s.' % (
															self.name, th.name))
				th.start()

		check_wakers = True
		self._pyro_loop = 0
		while not self._stop_event.isSet():
			try:
				# NOTE: 0.5s seems to be the lowest resources consuming value.
				# on an idle system with WMI::/system/daemon displayed,
				#	- 2.0s  leads to
				#	- 1.0s  leads to
				#	- 0.5s  leads to 37s SYS for 52min run, 150 loops/sec
				#	- 0.2s  leads to 10 loops/sec
				#	- 0.1s  leads to 59m SYS for 55min run, 20 loops/sec
				#	- 0.01s leads to
				self.pyro_daemon.handleRequests(0.2)
				#assert ltrace(TRACE_CMDLISTENER, "pyro daemon %d's loop: %s" % (
				#	self._pyro_loop, self.pyro_daemon.connections))
			except Exception, e:
				logging.warning(e)
			self._pyro_loop += 1

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
						assert ltrace(TRACE_THREAD,
							'%s: all wakers terminated at loop#%d.' % (
								self.name, self._pyro_loop))
						check_wakers = False

		self.pyro_daemon.shutdown(True)

		# be sure the pyro_daemon's __del__ method is called, it will
		# close the server socket properly.
		del self.pyro_daemon

		logging.progress('%s: %s Pyro daemon.' % (self.name,
			stylize(ST_BAD, 'stopped')))

		# NOTE: this is just in case we stop ourselves *before* waker_threads
		# finish. Happens if Control-C at the beginning of the daemon. Unlikely
		# to occur, but who knows.
		for th in self.wake_threads:
			assert ltrace(TRACE_THREAD, '%s  stopping wake up thread %s.' % (
				self.name, th.name))
			th.cancel()
			th.join()

		assert ltrace(TRACE_THREAD, '%s ended' % self.name)
