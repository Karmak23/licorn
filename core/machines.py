# -*- coding: utf-8 -*-
"""
Licorn core: machines - http://docs.licorn.org/core/machines.html

:copyright: 2010 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2
"""
import os, time
from traceback import print_exc

import netifaces, ipcalc, dumbnet, Pyro, socket

from threading  import current_thread
from time       import strftime, localtime
from subprocess import Popen, PIPE

from licorn.foundations           import logging, exceptions
from licorn.foundations           import process, hlstr, network, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Enumeration, Singleton
from licorn.foundations.constants import host_status, host_types, filters
from licorn.core                  import LMC
from licorn.core.classes          import CoreController, CoreStoredObject
from licorn.daemon                import priorities, roles
from licorn.interfaces.wmi        import WMIObject
from licorn.interfaces.wmi 		  import utils as w

class Machine(CoreStoredObject):

	by_hostname = {}
	by_ether    = {}
	arp_table   = None

	_nmap_cmd_base      = [ 'nmap', '-v', '-n', '-T5', '-sP', '-oG', '-' ]
	_nmap_cmd_gos_base  = [ 'nmap', '-n', '-O' ]
	_nmap_installed     = os.path.exists('/usr/bin/nmap')

	# translation table between nmap common values and our internal ones
	# examples:
	#
	#~ MAC Address: 60:FB:42:F5:80:40 (Apple)
	#~ Device type: general purpose
	#~ Running: Apple Mac OS X 10.5.X
	#~ OS details: Apple Mac OS X 10.5 - 10.6 (Leopard - Snow Leopard) (Darwin 9.0.0b5 - 10.0.0)
	#
	#~ MAC Address: 58:55:CA:FA:48:39 (Unknown)
	#~ Device type: general purpose
	#~ Running: Apple Mac OS X 10.5.X
	#~ OS details: Apple Mac OS X 10.5 - 10.6 (Leopard - Snow Leopard) (Darwin 9.0.0b5 - 10.0.0)
	#
	#~ MAC Address: 00:07:CB:D4:6D:83 (Freebox SA)
	#~ Warning: OSScan results may be unreliable because we could not find at least 1 open and 1 closed port
	#~ Device type: media device|general purpose
	#~ Running: Chumby embedded, Linux 2.6.X
	#~ OS details: Chumby Internet radio, Linux 2.6.13 - 2.6.28, Linux 2.6.18
	#
	# iPhone:
	#~ 22/tcp    open  ssh
	#~ 62078/tcp open  iphone-sync
	#~ MAC Address: F8:1E:DF:09:F8:0E (Apple)
	#~ Device type: general purpose
	#~ Running: Apple Mac OS X 10.5.X
	#~ OS details: Apple Mac OS X 10.5 - 10.6 (Leopard - Snow Leopard) (Darwin 9.0.0b5 - 10.0.0)
	#~ Network Distance: 1 hop
	#
	# Lucid VMWare:
	#~ PORT   STATE SERVICE
	#~ 22/tcp open  ssh
	#~ MAC Address: 00:0C:29:2A:23:7A (VMware)
	#~ Device type: general purpose
	#~ Running: Linux 2.6.X
	#~ OS details: Linux 2.6.17 - 2.6.31
	#
	#~ Starting Nmap 5.21 ( http://nmap.org ) at 2011-01-24 20:44 CET
	#~ Nmap scan report for 192.168.100.253
	#~ Host is up (0.0057s latency).
	#~ Not shown: 997 closed ports
	#~ PORT      STATE SERVICE
	#~ 5000/tcp  open  upnp
	#~ 5009/tcp  open  airport-admin
	#~ 10000/tcp open  snet-sensor-mgmt
	#~ MAC Address: 00:23:DF:F8:91:18 (Apple)
	#~ Device type: general purpose
	#~ Running: NetBSD 4.X
	#~ OS details: NetBSD 4.99.4
	#~ Network Distance: 1 hop


	_nmap_os_devices = {
		'printer':		host_types.PRINTER,

		# this just annoys me, don't do anything with it.
		'general purpose': 0x0
		}
	_nmap_os_running = {
		'Apple Mac OS X 10.5.X': host_types.APPLE,
		'Linux 2.6.X':           host_types.LNX_GEN,
		}
	_nmap_os_details = {
		'HP Photosmart printer': host_types.MULTIFUNC,
		}
	_nmap_os_ether = {
		'Freebox SA': host_types.FREEBOX,
		'VMware':     host_types.VMWARE,
		'Apple':      host_types.APPLE,
		}

	def __init__(self, mid, hostname=None, ether=None, expiry=None,
		lease_time=None, status=host_status.UNKNOWN, managed=False,
		system=None, system_type=host_types.UNKNOWN,
		linked_machines=None, linked_users=None, linked_groups=None,
		backend=None, myself=False, **kwargs):

		CoreStoredObject.__init__(self, LMC.machines, backend)

		assert ltrace('objects', '| Machine.__init__(%s, %s)' % (mid, hostname))

		# mid == IP address (unique on a given network)
		self.__mid = mid

		# hostname will be DNS-reversed from IP, or constructed.
		# it gets a __ because it is a property.
		self.__hostname  = hostname
		self.ether       = ether
		self.expiry      = expiry
		self.lease_time  = lease_time

		# will be updated as much as possible with the current host status.
		self.status = status

		# True if the machine is recorded in local configuration files.
		self.managed = managed

		# OS and OS level, arch, mixed in one integer.
		self.system_type = system_type

		# the Pyro proxy (if the machine has one) for contacting it across the
		# network.
		self.system = system

		self.linked_machines = linked_machines if linked_machines else []
		self.master_machine  = None

		# a shortcut to avoid testing everytime
		# if the current object is local or not.
		self.myself = myself

		for machine in self.linked_machines:
			machine.master_machine = self

		self.linked_users  = linked_users  if linked_users  else []
		self.linked_groups = linked_groups if linked_groups else []

	@property
	def mid(self):
		""" The IP address of the host. """
		return self.__mid

	# Comfort alias ("mid" is not a common name,
	# only for me and Licorn® internals)
	ip = mid

	@property
	def hostname(self):
		""" The host name (indexed in a reverse mapping dict). """
		return self.__hostname

	@hostname.setter
	def hostname(self, hostname):
		""" Update the reverse mapping dict. """
		try:
			del Machine.by_hostname[self.__hostname]
		except:
			pass

		self.__hostname = hostname
		LMC.machines.by_hostname[hostname] = self

	def add_link(self, licorn_object):
		""" TODO. """

		#print '>> add link from %s to %s' % (licorn_object.ip, self.ip)

		if isinstance(licorn_object, Machine):
			self.linked_machines.append(licorn_object)
			licorn_object.master_machine = self

			# avoid talking to myself via the network, if applicable.
			licorn_object.myself = self.myself
		else:
			raise NotImplementedError('no other link than machine yet')
	def guess_os(self):
		""" Use NMAP for OS fingerprinting and better service detection. """

		caller = current_thread().name

		if Machine._nmap_installed:
			for line in process.execute(
					Machine._nmap_cmd_gos_base + [self.mid])[0].splitlines():

				try:
					key, value = line.split(': ', 1)
				except ValueError:
					continue

				try:
					if key == 'Device type':
						self.system_type |= Machine._nmap_os_devices[value]

					elif key == 'Running':
						if not self.system_type & Machine._nmap_os_running[value]:
							self.system_type |= Machine._nmap_os_running[value]

					elif key == 'OS details':
						if not self.system_type & Machine._nmap_os_details[value]:
							self.system_type |= Machine._nmap_os_details[value]

					elif key == 'MAC Address':
						# See if we got something from the words in parentheses
						self.system_type |= Machine._nmap_os_ether[
												value.rsplit('(', 1)[1][:-1]]
					elif key in ('Not shown', 'Warning', 'Network Distance',
							'Nmap done', 'Note'):
						continue
					else:
						logging.warning2('%s: guess_os(%s) → unknown key "%s" '
							'with value "%s", please update database.' % (
								caller, self.mid, key, value))
						continue

				except KeyError:
					logging.warning2('%s: guess_os(%s) → unknown %s value "%s", '
						'please update database.' % (
							caller, self.mid, key, value))
					continue
		else:
			assert ltrace('machines', '| %s: guess_os(%s) → nmap '
				'not installed, can\'t guess OS.' % (caller, self.mid))
	def ping(self, and_more=False):
		""" PING. """
		caller = current_thread().name
		#assert ltrace('machines', '> %s: ping(%s)' % (caller, self.mid))

		with self.lock:

			if self.myself:
				self.status = host_status.ACTIVE
				if and_more:
					L_network_enqueue(priorities.NORMAL, self.pyroize)
					L_network_enqueue(priorities.LOW, self.arping)
					L_network_enqueue(priorities.LOW, self.resolve)
				assert ltrace('machines', '| %s: ping(%s) → %s' % (
									caller, self.mid, host_status[self.status]))
				return

			try:
				pinger = network.Pinger(self.mid)
				pinger.ping()

			except (exceptions.DoesntExistException,
					exceptions.TimeoutExceededException), e:

				self.status = host_status.OFFLINE

			except Exception, e:
				assert ltrace('machines', '  %s: cannot ping %s (was: %s).' % (
					caller, self.mid, e))
				pass

			else:
				self.status = host_status.ONLINE

				if and_more:
					L_network_enqueue(priorities.NORMAL, self.pyroize)
					L_network_enqueue(priorities.LOW, self.arping)
					L_network_enqueue(priorities.LOW, self.resolve)

			# close the socket (no more needed), else we could get
			# "too many open files" errors (254 open sockets for .
			pinger.reset(self)
			del pinger

		assert ltrace('machines', '| %s: ping(%s) → %s' % (
								caller, self.mid, host_status[self.status]))
	def resolve(self):
		""" Resolve IP to hostname, if possible. """
		caller = current_thread().name

		#assert ltrace('machines', '> %s: resolve(%s)' % (caller, self.mid))

		with self.lock:
			old_hostname = self.hostname
			try:
				self.hostname = socket.gethostbyaddr(self.mid)[0]
			except Exception, e:
				assert ltrace('machines', '  %s: cannot resolve %s (was: %s).'
					% (caller, self.mid, e))
				pass
			else:
				# update the hostname cache.
				# FIXME: don't update the cache manually,
				# delegate it to *something*.

				print '>> implement machines.Machine.resolve()'
				#del LMC.machines.by_hostname[old_hostname]
				#LMC.machines.by_hostname[self.hostname] = self

		assert ltrace('machines', '| %s: resolve(%s) → %s' % (
											caller, self.mid, self.hostname))
	def pyroize(self):
		""" find if the machine is Pyro enabled or not. """
		caller = current_thread().name

		#assert ltrace('machines', '> %s: pyroize(%s)' % (caller, self.mid))

		with self.lock:

			if self.myself:
				self.system=None
				self.update_informations()
				return

			if self.system is not None:
				logging.progress('%s: %s already pyroized, not redoing.' % (
					caller, self.mid))
				return

			try:
				# we don't assign directly the pyro proxy into
				# machines[mid]['system'] because it can be invalid
				# until the noop() call succeeds and guarantees the
				# remote system is really Pyro enabled.
				remotesys = Pyro.core.getAttrProxyForURI(
						"PYROLOC://%s:%s/system" % (self.mid,
							LMC.configuration.licornd.pyro.port))
				remotesys._setTimeout(3.0)
				remotesys.noop()

			except Pyro.errors.ProtocolError, e:
				L_network_enqueue(priorities.LOW, self.guess_os)
				assert ltrace('machines', '  %s: cannot pyroize %s '
								'(was: %s)' % (caller, self.mid, e))

			except Pyro.errors.PyroError, e:
				remotesys.release()
				del remotesys
				L_network_enqueue(priorities.LOW, self.guess_os)
				assert ltrace('machines', '%s: pyro error %s on %s.' % (
						caller, e, self.mid))

			else:
				self.system = remotesys
				self.pyro_deduplicate()
				self.update_informations()
		assert ltrace('machines', '| %s: pyroize(%s) → %s'
											% (caller, self.mid, self.system))
	def pyro_deduplicate(self):
		""" try to find if the remote system has multiple interfaces and
			if we have multiple record for it. Then, link them.
		"""

		caller = current_thread().name

		with self.lock:
			# merge remote hosts, particularly if they are connected
			# to me with more than one interface.
			remote_ifaces = self.system.local_ip_addresses()
			#print '>> dedupe'
			if len(remote_ifaces) > 1:
				#print '>> multiple iface detected', self.mid, remote_ifaces
				remote_ifaces.remove(self.mid)
				for iface in remote_ifaces:
					if iface in self.controller.keys():
						if not self.master_machine:
							logging.progress('%s: add link from %s to %s.' % (
								caller, iface, self.ip))
							self.add_link(self.controller[iface])
						#else:
						#	print '>>nothing done'

					else:
						#print '>> creating', iface, 'on next loop'
						#
						# when the second machine will have been created,
						# the pyroize() phase will reconcile master/slave
						# again. Next service loop.
						L_service_enqueue(priorities.HIGH,
									self.controller.add_machine, mid=iface)
	def pyro_shutdown(self):
		""" WIPE the system attribute and mark the machine as shutting down.
			DO the same for all linked machines if we are the master. Don't
			do anything if we are not.
		"""

		caller = current_thread().name

		if self.master_machine:
			assert ltrace('machines', '%s: not doing pyro_shutdown on self '
				'(%s), we are slave of %s.' (caller, self.ip,
					self.master_machine.ip))
			return

		logging.notice('%s: %s at %s.' % (caller,
			stylize(ST_BAD, 'Licorn® %s shutdown' % ('server'
				if self.system_type & host_types.META_SRV else 'client')),
			stylize(ST_ADDRESS, self.mid)))

		self.status = host_status.PYRO_SHUTDOWN
		self.system = None

		for machine in self.linked_machines:
			machine.status = host_status.PYRO_SHUTDOWN
			machine.system = None
	def _pyro_forward_goodbye_from(self, remote_ifaces):
		""" this is proxy method to call
			:meth:`~licorn.core.system.goodbye_from` on the remote side,
			because enqueuing a pyro proxy method in services queues
			doesn't work as expected. """

		#print '>> pyro_goodbye_from', remote_ifaces, 'to', self.ip

		if self.master_machine:
			return

		return self.system.goodbye_from(remote_ifaces)
	def arping(self):
		""" find the ether address. """

		if self.ether is not None:
			return

		if Machine.arp_table is None:
			Machine.arp_table = dumbnet.arp()

		caller = current_thread().name

		#assert ltrace('machines', '> %s: arping(%s)' % (caller, self.mid))

		with self.lock:
			try:
				# str() is needed to convert from dumbnet.addr() type.
				self.ether = str(Machine.arp_table.get(dumbnet.addr(self.mid)))

			except Exception, e:
				assert ltrace('machines', '  %s: cannot arping %s (was: %s).'
													% (caller, self.mid, e))
		assert ltrace('machines', '| %s: arping(%s) → %s'
											% (caller, self.mid, self.ether))
	def update_informations(self, system=None, merge=True):
		""" get detailled information about a remote host, via Pyro.
			This method will not check remote Pyro is OK, it's up to the
			caller to be sure it is.

			:param system: a remote Pyro Proxy for the SystemController.
				Passed when this method is called from cmdlistener during
				the client/server validation phase. At this moment, we
				overwrite the current value of system, because the new one
				is newer and probably comes from a daemon which rebooted,
				meaning the old is already no more valid, pointing to a
				dangling reference of an old Pyro daemon.
		"""

		caller = current_thread().name

		with self.lock:
			if self.myself:
				if merge:
					self.system_type |= LMC.system.get_host_type()
				else:
					self.system_type = LMC.system.get_host_type()
				self.status = LMC.system.get_status()
				return

			if system is not None:
				self.system = system

			# we don't update informations for slaves,
			# they get updated by masters.
			if self.master_machine:
				return


			if self.system is None:
				# if called too early from an hello_from(), we could
				# not have our pyro address yet. try to find it.
				self.pyroize()

			try:

				# We can merge the system types or not, depending if we already
				# have some valuable information (like the is_ALT status, guessed
				# from the ether, which the remote system doesn't implement yet
				# (as of 20110124).

				was_licorn = self.system_type & (host_types.LICORN
												| host_types.META_SRV)
				old_status = self.status

				self.system_type = self.system.get_host_type()

				is_licorn = self.system_type & host_types.LICORN
				is_server = self.system_type & host_types.META_SRV

				if not was_licorn and is_licorn:

					self.pyro_deduplicate()

					if self.master_machine:
						return

					logging.notice('%s: %s at %s.' % (caller,
						stylize(ST_OK, 'new Licorn® %s' % ('server'
							if is_server else 'client')),
						stylize(ST_ADDRESS, self.mid)))

					L_service_enqueue(priorities.HIGH, self.system.hello_from,
						LMC.system.local_ip_addresses())

			except Pyro.errors.PyroError, e:
				self.pyro_shutdown()
			else:
				self.status = self.system.get_status()

				if old_status & host_status.OFFLINE \
					and self.status & host_status.ONLINE:
					if is_licorn:
						logging.notice('%s: %s at %s.' % (caller,
							stylize(ST_OK, 'Licorn® %s back online' % ('server'
								if is_server else 'client')),
							stylize(ST_ADDRESS, self.mid)))
					else:
						logging.progress('%s: %s at %s.' % (caller,
							stylize(ST_ADDRESS, self.mid),
							stylize(ST_RUNNING, 'came back online')
							))

			for machine in self.linked_machines:
				machine.system_type = self.system_type
				machine.status      = self.status
	def shutdown(self, warn_users=True):
		""" Shutdown a machine, after having warned the connected user(s) if
			asked to."""

		if self.myself:
			logging.warning('Shutting myself down is a bad idea. '
				'Not doing this yet.')
			return

		if self.system:
			self.system.shutdown()
			self.status == host_status.SHUTTING_DOWN
			logging.info('Shut down machine %s.' % self.hostname)

		else:
			raise exceptions.LicornRuntimeException('''Can't shutdown a '''
				'''non remote-controlled machine!''')
	def update_status(self, status):
		""" update the current machine status, in a clever manner. """
		with self.lock:
			if status is None:
				# this part is not going to happen, because this method is
				# called (indirectly, via SystemController) from clients.
				logging.warning('machines.update_status() called with '
					'status=None for machine %s(%s)' % (self.hostname, self.mid))
			else:
				# don't do anything if the status is already the same or finer.
				# E.G. ACTIVE is finer than ONLINE, which doesn't known if the
				# machine is idle or not.
				if not self.status & status:
					self.status = status
					logging.progress("Updated machine %s's status to %s." % (
						stylize(ST_NAME, self.hostname),
						stylize(ST_COMMENT, host_status[status])
						))
	def __str__(self):
		return '%s(%s‣%s) = {\n\t%s\n\t}\n' % (
			self.__class__,
			stylize(ST_UGID, self.mid),
			stylize(ST_NAME, self.hostname),
			'\n\t'.join([ '%s: %s' % (attr_name, getattr(self, attr_name))
					for attr_name in dir(self) ])
			)
	def __repr__(self):
		return '%s(%s‣%s)' % (
			self.__class__,
			stylize(ST_UGID, self.mid),
			stylize(ST_NAME, self.hostname))
class MachinesController(Singleton, CoreController, WMIObject):
	""" Holds all machines objects (indexed on IP addresses, reverse mapped on
		hostnames and ether addresses which should be unique). """
	init_ok         = False
	load_ok         = False

	_licorn_protected_attrs = (
			CoreController._licorn_protected_attrs
			+ WMIObject._licorn_protected_attrs
		)

	#: used in RWI.
	def object_type_str(self):
		return _(u'machine')
	def object_id_str(self):
		return _(u'MID')
	@property
	def sort_key(self):
		return 'name'

	def __init__(self):
		""" Create the machine accounts list from the underlying system.
			The arguments are None only for get (ie Export and ExportXml) """

		if MachinesController.init_ok:
			return

		assert ltrace('machines', 'MachinesController.__init__()')

		CoreController.__init__(self, 'machines')

		MachinesController.init_ok = True
	def add_machine(self, mid, hostname=None, ether=None, backend=None,
		system_type=host_types.UNKNOWN, system=None, status=host_status.UNKNOWN,
		myself=False):
		""" Create a machine in the current controller. Parameters are
			essentially the same as in the
			:class:`Machine constructor <Machine>`.
		"""
		caller = current_thread().name

		assert ltrace('machines', '| %s: add_machine(%s, %s, %s, %s, %s, %s, '
			'%s, %s)' % (caller, mid, hostname, ether, backend,
				system_type, system, status, myself))

		self[mid] = Machine(mid=mid,
						ether=ether,
						hostname=hostname
							if hostname
							else network.build_hostname_from_ip(mid),
						system_type=system_type,
						system=system,
						backend=backend
							if backend else Enumeration('null_backend'),
						status=status,
						myself=myself
					)

		L_network_enqueue(priorities.LOW, self[mid].ping, and_more=True)

		return self[mid]
	@property
	def hostnames(self):
		return (h for h in Machine.by_hostname)
	@property
	def ethers(self):
		return (e for e in Machine.by_ether)
	def word_match(self, word):
		return hlstr.multi_word_match(e, itertools.chain(self.hostnames, self.ethers))
	def load(self):
		if MachinesController.load_ok:
			return

		assert ltrace('machines', '| load()')
		self.reload()


		if LMC.configuration.experimental.enabled:
			self.create_wmi_object('/machines')

		MachinesController.load_ok = True
	def reload(self):
		""" Load (or reload) the data structures from the system files. """

		assert ltrace('machines', '> reload()')

		CoreController.reload(self)

		with self.lock:
			self.clear()

			for backend in self.backends:
				assert ltrace('machines', '  reload(%s)' % backend.name)
				for machine in backend.load_Machines():
					if machine.ip in self.keys():
						raise backend.generate_exception(
							'AlreadyExistsException', machine.ip)

					self.__setitem__(machine.ip, machine)

		assert ltrace('machines', '< reload()')
	def reload_backend(self, backend):
		assert ltrace('users', '| reload_backend(%s)' % backend.name)

		loaded = []

		assert ltrace('locks', '| machines.reload_backend enter %s' % self.lock)

		with self.lock:
			for mid, machine in backend.load_Machines():
				if mid in self:
					logging.warning2(_(u'Overwritten mid %s') % mid)
				self[mid] = machine
				loaded.append(mid)

			#for mid, machines in self.items():
			#	if user.backend.name == backend.name:
			#		if uid in loaded:
			#			loaded.remove(uid)

			#		else:
			#			logging.progress(_(u'{0}: removing disapeared user '
			#				'{1}.').format(stylize(ST_NAME, self.name),
			#					stylize(ST_LOGIN, user.login)))
			#
			#			self.del_User(user, batch=True, force=True)

		assert ltrace('locks', '| users.reload_backend exit %s' % self.lock)
	def build_myself(self):
		""" create internal instance(s) for the current Licorn® daemon. """
		with self.lock:
			first_machine_found = None

			for iface in network.interfaces():
				iface_infos = netifaces.ifaddresses(iface)
				if 2 in iface_infos:
					ipaddr = iface_infos[2][0]['addr']
					ether  = iface_infos[17][0]['addr']

					if first_machine_found:
						first_machine_found.add_link(
							self.add_machine(mid=ipaddr,
								ether=ether,
								status=host_status.ACTIVE,
								system_type=first_machine_found.system_type
							)
						)

					else:
						systype = host_types.UNKNOWN

						if self.is_alt(ether=ether):
							systype |= host_types.ALT

						first_machine_found = self.add_machine(
								mid=ipaddr,
								ether=ether,
								status=host_status.ACTIVE,
								system_type=systype,
								myself=True
							)
	def initial_scan(self):
		""" Called on daemon start, this method create objects for all LAN
			hosts, if not disabled by configuration directive
			:ref:`licornd.network.lan_scan.en`.
		"""
		caller = current_thread().name

		assert ltrace('machines', '> %s: initial_scan()' % caller)

		logging.info(_(u'{0}: {1} initial network discovery.').format(caller,
									stylize(ST_RUNNING, _(u'started'))))

		with self.lock:

			# FIRST, add myself to known machines, and link all my IP
			# addresses to the same machine, to avoid displaying more than one
			# on our interfaces (CLI / WMI).
			self.build_myself()

			# SECOND update our know machines statuses, if any.
			for machine in self:
				if machine.status & host_status.UNKNOWN:
					L_network_enqueue(priorities.LOW, machine.ping, and_more=True)

				if machine.hostname.startswith('UNKNOWN'):
					L_network_enqueue(priorities.LOW, machine.resolve)

			# THEN scan the whole LAN to discover more machines.
			if LMC.configuration.licornd.network.lan_scan:
				L_network_enqueue(priorities.LOW, self.scan_network)
			else:
				logging.notice(_('{0}: network auto-discovery disabled by '
					'configuration rule {1}, not going further.').format(
						caller, stylize(ST_ATTR, 'licornd.network.lan_scan')))

		assert ltrace('machines', '< %s: initial_scan()' % caller)
	def scan_network(self, network_to_scan=None):
		""" Scan a whole network and add all discovered machines to
		the local configuration. If arg"""

		caller = current_thread().name

		assert ltrace('machines', '> %s: scan_network()' % caller)

		known_ips   = self.keys()
		ips_to_scan = []

		if network_to_scan is None:
			for iface in network.interfaces():
				iface_infos = netifaces.ifaddresses(iface)

				if 2 in iface_infos:
					logging.info('%s: programming scan of LAN %s.0/%s.'
						% (caller, iface_infos[2][0]['addr'].rsplit('.', 1)[0],
							network.netmask2prefix(
												iface_infos[2][0]['netmask'])))

					for ipaddr in ipcalc.Network('%s.0/%s' % (
							iface_infos[2][0]['addr'].rsplit('.', 1)[0],
							network.netmask2prefix(
								iface_infos[2][0]['netmask']))):
						# need to convert because ipcalc returns IP() objects.
						ips_to_scan.append(str(ipaddr))
		else:
			for netw in network_to_scan.split(','):
				for ipaddr in ipcalc.Network(netw):
					ips_to_scan.append(str(ipaddr))

		for ipaddr in ips_to_scan:
			if ipaddr[-2:] != '.0' and ipaddr[-4:] != '.255':
				if ipaddr in known_ips:
					L_network_enqueue(priorities.LOW,
											self[str(ipaddr)].ping)
				else:
					self.add_machine(mid=str(ipaddr))

		assert ltrace('machines', '< %s: scan_network()' % caller)
	def goodbye_from(self, remote_ips):
		""" this method is called on the remote side, when the local side calls
			:meth:`announce_shutdown`.
		"""
		current_ips = self.keys()

		for ip in remote_ips:
			if ip in current_ips:
				L_service_enqueue(priorities.HIGH, self[ip].pyro_shutdown)
	def hello_from(self, remote_ips):
		""" this method is called on the remote side, when the local side calls
			:meth:`announce_shutdown`.
		"""
		current_ips = self.keys()

		for ip in remote_ips:
			if ip in current_ips:
				L_service_enqueue(priorities.HIGH, self[ip].update_informations)
			else:
				self.add_machine(mid=ip)
				L_service_enqueue(priorities.HIGH, self[ip].update_informations)
	def announce_shutdown(self):
		""" announce our shutdown to all connected machines. """

		caller       = current_thread().name
		local_ifaces = LMC.configuration.network.local_ip_addresses()

		for machine in self:
			if machine.system and not (
							machine.master_machine or machine.myself):
				assert ltrace('machines',
									'| annouce_shutdown() to %s' % machine.ip)
				try:
					#print '>> announce shutdown to', machine.ip
					L_service_enqueue(priorities.HIGH,
									machine._pyro_forward_goodbye_from,
										local_ifaces)
				except Pyro.errors.PyroError, e:
					logging.warning2('%s: announce_shutdown(): harmless '
						'error %s from %s.' % (caller, e, machine.ip))

		#
		# WARNING: don't service_wait() here, the thread would join its own
		# queue and this would deadblock (not lock ;-) ).
		#
	def WriteConf(self, mid=None):
		""" Write the machine data in appropriate system files."""

		assert ltrace('machines', 'saving data structures to disk.')

		with self.lock:
			if mid:
				LMC.backends[
					self[mid]['backend']
					].save_Machine(mid)
			else:
				for backend in self.backends:
					backend.save_Machines()
	def select(self, filter_string, filter_type=host_status, return_ids=False):
		""" Filter machine accounts on different criteria. """

		filtered_machines = []

		assert ltrace('machines', '> select(%s)' % filter_string)

		with self.lock:
			if filter_type == host_status:

				def keep_status(machine, status=None):
					if machine.status == status \
							and machine.master_machine is None:
						filtered_machines.append(machine)

				if None == filter_string:
					filtered_machines = []

				else:

					if host_status.OFFLINE & filter_string:

						map(lambda x: keep_status(x, host_status.OFFLINE),
								self.itervalues())

						if host_status.ASLEEP & filter_string:
							map(lambda x: keep_status(x, host_status.ASLEEP),
								self.itervalues())

						if host_status.PYRO_SHUTDOWN & filter_string:
							map(lambda x: keep_status(x, host_status.PYRO_SHUTDOWN),
								self.itervalues())

					if host_status.ONLINE & filter_string:

						map(lambda x: keep_status(x, host_status.ONLINE),
								self.itervalues())

						if host_status.ACTIVE & filter_string:
							map(lambda x: keep_status(x, host_status.ACTIVE),
								self.itervalues())

						if host_status.IDLE & filter_string:
							map(lambda x: keep_status(x, host_status.IDLE),
								self.itervalues())

						if host_status.LOADED & filter_string:
							map(lambda x: keep_status(x, host_status.LOADED),
								self.itervalues())

						if host_status.BOOTING & filter_string:
							map(lambda x: keep_status(x, host_status.BOOTING),
								self.itervalues())

			else:
				import re
				mid_re = re.compile("^mid=(?P<mid>\d+)")
				mid = mid_re.match(filter_string)
				if mid is not None:
					mid = int(mid.group('mid'))
					filtered_machines.append(self[mid])

			assert ltrace('machines', '< select(%s)' % filtered_machines)
			if return_ids:
				return [ m.mid for m in filtered_machines ]
			else:
				return filtered_machines
	def ExportCLI(self, selected=None, long_output=False):
		""" Export the machine accounts list to human readable («passwd») form.
		"""
		if selected is None:
			mids = self.keys()
		else:
			mids = selected
		mids.sort()

		assert ltrace('machines', '| ExportCLI(%s)' % mids)

		justw=10

		def build_cli_output_machine_data(mid):

			m = self[mid]

			account = [	stylize(ST_NAME \
							if m.managed else ST_SPECIAL,
							m.hostname) + (_(u' (this machine)')
								if m.myself else ''),
						'%s: %s%s' % (
								'status'.rjust(justw),
								stylize(ST_ON
										if m.status & host_status.ONLINE
											else ST_OFF,
										host_status[m.status].title()),
								'' if m.system is None
										else ' (remote control enabled)'
							),
						'%s: %s (%s%s)' % (
								'address'.rjust(justw),
								str(mid),
								'expires: %s, ' % stylize(ST_ATTR,
									strftime('%Y-%d-%m %H:%M:%S',
									localtime(float(m.expiry))))
										if m.expiry else '',
									'managed' if m.managed
													else 'floating',
							),
						'%s: %s' % (
								'ethernet'.rjust(justw),
								str(m.ether)
							)
						]
			return '\n'.join(account)

		data = '\n'.join(map(build_cli_output_machine_data, mids)) + '\n'

		return data
	def ExportXML(self, selected=None, long_output=False):
		""" Export the machine accounts list to XML. """

		if selected is None:
			mids = self.keys()
		else:
			mids = selected
		mids.sort()

		assert ltrace('machines', '| ExportXML(%s)' % mids)

		m = self

		def build_xml_output_machine_data(mid):
			data = '''	<machine>
		<hostname>%s</hostname>
		<mid>%s</mid>
		<managed>%s</managed>
		<ether>%s</ether>
		<expiry>%s</expiry>\n''' % (
					m[mid].g,
					mid,
					m[mid].managed,
					m[mid].ether,
					m[mid].expiry if m[mid].expiry else ''
				)

			return data + "	</machine>"

		data = "<?xml version='1.0' encoding=\"UTF-8\"?>\n<machines-list>\n" \
			+ '\n'.join(map(build_xml_output_machine_data, mids)) \
			+ "\n</machines-list>\n"

		return data
	def shutdown(self, mid, warn_users=True):
		""" Shutdown a machine, after having warned the connected user(s) if
			asked to."""

		self[mid].shutdown(warn_users=warn_users)
	def is_alt(self, mid=None, ether=None):
		""" Return True if the machine is an ALT client, else False.
			TODO: move this to Machine class.
		"""

		try:
			if ether:
				is_ALT = ether.startswith('00:e0:f4:')
			else:
				is_ALT = self[mid].ether.lower().startswith('00:e0:f4:')
		except (AttributeError, KeyError):
			is_ALT = False

		assert ltrace('machines', '| is_alt(mid=%s) → %s' % (mid, is_ALT))

		return is_ALT
	def confirm_mid(self, mid):
		""" verify a MID or raise DoesntExist. """
		try:
			return self[mid].ip
		except KeyError:
			raise exceptions.DoesntExistException(
				"MID %s doesn't exist" % mid)
	def make_hostname(self, inputhostname=None):
		""" Make a valid hostname from what we're given. """

		if inputhostname is None:
			raise exceptions.BadArgumentError(
				_('''You must pass a hostname to verify!'''))

		# use provided hostname and verify it.
		hostname = hlstr.validate_name(str(inputhostname),
			maxlenght = LMC.configuration.machines.hostname_maxlenght)

		if not hlstr.cregex['hostname'].match(hostname):
			raise exceptions.LicornRuntimeError(
				_(u'Cannot build a valid hostname (got {0}, which does not '
				'verify {1}).').format(
					inputhostname, hlstr.regex['hostname']))

		return hostname

	# these 3 will be mapped into R/O properties by the WMIObject creation
	# process method. They will be deleted from here after the mapping is done.
	def _wmi_name(self):
		return _('Machines')
	def _wmi_alt_string(self):
		return _('Manage network clients (computers, printers, '
					'etc) and energy preferences')
	def _wmi_context_menu(self):
		"""
			NOT YET:
				_("Add a machine"),
				_("Create a configuration record for a machine which is not yet on "
					"the network."),
				_("Export current machines list to a CSV or XML file."),
				_("Export this list")
			"""

		return (
			(
				_('Shutdown machines'),
				'/machines/massshutdown',
				_('Shutdown machines on the network.'),
				'ctxt-icon',
				'icon-massshutdown',
				lambda: len(self) > 0
			),
			(
				_('Energy policies'),
				'/machines/preferences',
				_('Manage network-wide Energy &amp; '
					'power saving policies.'),
				'ctxt-icon',
				'icon-energyprefs',
				None
			)
		)
	def _wmi_shutdown(self, uri, http_user, hostname=None, sure=False,
		warn_users=True, **kwargs):
		""" Shutdown a machine. """

		w = self.utils

		title = _("Shutdown machine %s") % hostname
		data  = w.page_body_start(uri, http_user, self._ctxtnav, title)

		if not sure:
			description = _('''Are you sure you want to remotely shutdown '''
				'''machine %s?''') % hostname

			form_options = w.checkbox("warn_users", "True",
					'<strong>' + _("Warn connected user(s) before shuting "
						"system down.") + '</strong>', True)

			data += w.question(_("Please confirm operation"),
				description,
				yes_values   = [ _("Shutdown") + ' >>',
							"/machines/shutdown/%s/sure" % hostname, "S" ],
				no_values    = [ '<< ' + _("Cancel"),  "/machines/list",   "N" ],
				form_options = form_options)

			data += '</div><!-- end main -->'

			return (w.HTTP_TYPE_TEXT, w.page(title, data))

		else:

			# TODO: find a way to callback the result to the WMI...

			L_service_enqueue(priorities.LOW,
				self.by_hostname(hostname).shutdown, warn_users=warn_users)

			return (self.utils.HTTP_TYPE_REDIRECT,
							self.wmi.successfull_redirect)
	def _wmi_massshutdown(self, uri, http_user, sure=False, asleep=None, idle=None,
		active=None, warn_users=None, admin=None, **kwargs):
		""" Shutdown a bunch of machines et once,
			based on their current status (active, idle, etc). """

		w = self.utils

		title = _("Massive shutdown")
		data  = w.page_body_start(uri, http_user, self._ctxtnav, title)

		if not sure:
			description = _('You can shutdown all currently running and/or idle'
				' machines. This is a quite dangerous operation, because users'
				' will be disconnected, and there is a potential to loose '
				'unsaved work on idle machines (users are not in front of'
				' them, they will not notice the system is shuting down.<br />'
				'<br />Systems will be shut down <strong>ONE minute</strong> '
				'after validation.')

			form_options = '%s<br />%s<br />%s<br />%s<br /><br />%s' % (
				w.checkbox('active', 'True',
					_('Shutdown <strong>active</strong> machines'), True),
				w.checkbox('idle', 'True',
					_('Shutdown <strong>idle</strong> machines'), True),
				w.checkbox('asleep', 'True',
					_('Shutdown <strong>asleep</strong> machines'), True),
				w.checkbox('admin', 'True',
					_('Shutdown the <strong>administrator</strong> '
						'machine too<br/>(the one currently connected '
						'to the WMI).'), False),
				w.checkbox('warn_users', 'True',
					'<strong>' + _('Warn connected users before shuting '
						'systems down.') + '</strong>', True)
				)

			data += w.question(_('Choose machines to shutdown'),
				description,
				yes_values   = [ _('Shutdown') + ' >>',
										'/machines/massshutdown/sure', 'S' ],
				no_values    = [ '<< ' + _('Cancel'),  '/machines/list',   'N' ],
				form_options = form_options)

			data += '</div><!-- end main -->'

			return (w.HTTP_TYPE_TEXT, w.page(title, data))

		else:
			# TODO: reimplement the ALL variant
			if False:
				selection = host_status.IDLE | host_status.ASLEEP | host_status.ACTIVE
			else:
				selection = filters.NONE

			if idle:
				selection |= host_status.IDLE

			if asleep:
				selection |= host_status.ASLEEP

			if active:
				selection |= host_status.ACTIVE

			for machine in self.select(filter_string=selection):
				L_service_enqueue(priorities.LOW,	machine.shutdown, warn_users=warn_users)

			return (self.utils.HTTP_TYPE_REDIRECT,
							self.wmi.successfull_redirect)
	def _wmi_preferences(self, uri, http_user, **kwargs):
		""" Export machine list."""

		w = self.utils

		title = _("Energy saving policies")

		if type == "":
			description = _('''CSV file-format is used by spreadsheets and most '''
			'''systems which offer import functionnalities. XML file-format is a '''
			'''modern exchange format, used in soma applications which respect '''
			'''interoperability constraints.<br /><br />When you submit this '''
			'''form, your web browser will automatically offer you to download '''
			'''and save the export-file (it won't be displayed). When you're '''
			'''done, please click the “back” button of your browser.''')

			form_options = \
				_("Which file format do you want the machines list to be exported to? %s") \
					% w.select("type", [ "CSV", "XML"])

			data += w.question(_("Please choose file format for export list"),
				description,
				yes_values   = [ _("Export >>"), "/machines/export", "E" ],
				no_values    = [ _("<< Cancel"),  "/machines/list",   "N" ],
				form_options = form_options)

			data += '</div><!-- end main -->'

			return (w.HTTP_TYPE_TEXT, w.page(title, data))

		else:
			LMC.machines.select(filters.STANDARD)

			if type == "CSV":
				data = LMC.machines.ExportCSV()
			else:
				data = LMC.machines.ExportXML()

			return w.HTTP_TYPE_DOWNLOAD, (type, data)
	def _wmi_export(self, uri, http_user, type = "", yes=None, configuration=None,
		machines=None, **kwargs):
		""" Export machine list."""

		w = self.utils

		return (w.HTTP_TYPE_TEXT, "not implemented yet.")

		title = _("Export machines list")
		data  = w.page_body_start(uri, http_user, self._ctxtnav, title)

		if type == "":
			description = _('''CSV file-format is used by spreadsheets and most '''
			'''systems which offer import functionnalities. XML file-format is a '''
			'''modern exchange format, used in soma applications which respect '''
			'''interoperability constraints.<br /><br />When you submit this '''
			'''form, your web browser will automatically offer you to download '''
			'''and save the export-file (it won't be displayed). When you're '''
			'''done, please click the “back” button of your browser.''')

			form_options = \
				_("Which file format do you want the machines list to be exported to? %s") \
					% w.select("type", [ "CSV", "XML"])

			data += w.question(_("Please choose file format for export list"),
				description,
				yes_values   = [ _("Export >>"), "/machines/export", "E" ],
				no_values    = [ _("<< Cancel"),  "/machines/list",   "N" ],
				form_options = form_options)

			data += '</div><!-- end main -->'

			return (w.HTTP_TYPE_TEXT, w.page(title, data))

		else:
			LMC.machines.select(filters.STANDARD)

			if type == "CSV":
				data = LMC.machines.ExportCSV()
			else:
				data = LMC.machines.ExportXML()

			return w.HTTP_TYPE_DOWNLOAD, (type, data)
	def _wmi_main(self, uri, http_user, sort="hostname", order="asc", **kwargs):
		""" display all machines in a nice HTML page. """

		w = self.utils

		start = time.time()

		m = self

		accounts = {}
		ordered  = {}
		totals   = {
			_('managed'): 0,
			_('floating'): 0
			}

		title = _("Machines")
		data  = w.page_body_start(uri, http_user, self._ctxtnav, title)

		if order == "asc": reverseorder = "desc"
		else:              reverseorder = "asc"

		data += '<table id="machines_list">\n		<tr class="machines_list_header">'

		for (sortcolumn, sortname) in (
				("status", _("Status")),
				("hostname", _("Host name")),
				("ip", _("IP address")),
				("ether", _("Hardware address")),
				("expiry", _("Expiry")),
				("managed", _("Managed"))
			):
			if sortcolumn == sort:
				data += '''
				<th><img src="/images/sort_%s.png"
					alt="%s order image" />&#160;
					<a href="/machines/list/%s/%s" title="%s">%s</a>
				</th>\n''' % (order, order, sortcolumn, reverseorder,
						_("Click to sort in reverse order."), sortname)
			else:
				data += '''
				<th>
					<a href="/machines/list/%s/asc"	title="%s">%s</a>
				</th>\n''' % (sortcolumn,
					_("Click to sort on this column."), sortname)
		data += '		</tr>\n'

		def html_build_compact(machine):
			hostname = machine.hostname
			edit     = 'machine %s (IP %s)' % (hostname, machine.ip)
			if machine.managed:
				totals[_('managed')] += 1
			else:
				totals[_('floating')] += 1

			power_statuses = {
				host_status.UNKNOWN: (None, 'unknown',
					_('''Host %s is in an unknown state. Nothing is possible. '''
						'''Please wait for a reconnection.''')),
				host_status.OFFLINE: (None, 'offline',
					_('''Host %s is offline, and cannot be powered on from here,'''
						'''Only from the machine itself.''')),
				host_status.GOING_TO_SLEEP: (None, 'going_to_sleep',
					_('Host %s is going to sleep, it will be unavailable in a small period of time.')),
				host_status.ASLEEP: ('shutdown', 'asleep',
					_('Shutdown the machine %s')),
				host_status.SHUTTING_DOWN: (None, 'shutting_down',
					_('Host %s is shutting down, it will be unavailable in a small period of time.')),
				host_status.ONLINE: (None, 'online',
					_('Machine %s is online but unmanageable (not Licorn® enabled).')),
				host_status.IDLE: ('shutdown', 'idle',
					_('Shutdown the machine %s')),
				host_status.ACTIVE: ('shutdown', 'active',
					_('Shutdown the machine %s')),
				}

			status = machine.status
			if power_statuses[status][0]:

				html_data = '''
		<tr class="userdata">
			<!-- STATUS -->
			<td class="user_action_center">
				<a href="/machines/%s/%s" title="%s" class="%s">
				<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span></a>
			</td>''' % (
				power_statuses[status][0],
				hostname,
				power_statuses[status][2] % hostname,
				power_statuses[status][1]
				)

			else:
				html_data = '''
		<tr class="userdata">
			<!-- STATUS -->
			<td class="user_action_center">
				<span class="%s" title="%s">&nbsp;&nbsp;&nbsp;&nbsp;</span>
			</td>''' % (
				power_statuses[status][1],
				power_statuses[status][2] % hostname)

			#print '>>', machine.linked_machines

			html_data += '''

			<!-- HOSTNAME -->
			<td class="paddedright">
				<a href="/machines/edit/%s" title="%s" class="edit-entry">%s%s</a>
			</td>
			<!-- IP -->
			<td class="paddedright">
				<a href="/machines/edit/%s" title="%s" class="edit-entry">%s</a>
			</td>
			<!-- ETHER -->
			<td class="paddedright">
				<a href="/machines/edit/%s" title="%s" class="edit-entry">%s</a>
			</td>
			<!-- EXPIRY -->
			<td class="paddedright">
				<a href="/machines/edit/%s" title="%s" class="edit-entry">%s</a>
			</td>
				''' % (
					hostname, edit, hostname,
						((
						'&nbsp;<img src="/images/16x16/linked.png" alt="%s" width="16" height="16" />'
							% _('This machine has multiple network interfaces.')
								if machine.linked_machines else ''
						) + (
						'&nbsp;<img src="/images/16x16/vmware.png" alt="%s" width="16" height="16" />'
							% _('This machine is a virtual computer.')
								if machine.system_type & host_types.VMWARE else ''
						) + (
						'&nbsp;<img src="/images/16x16/linux.png" alt="%s" width="16" height="16" />'
							% _('This machine runs an undetermined version '
								'of Linux®.')
								if machine.system_type & host_types.LNX_GEN else ''
						) + (
						'&nbsp;<img src="/images/16x16/server.png" alt="%s" width="16" height="16" />'
							% _('This machine is a META IT/Licorn® server.')
								if (machine.system_type & host_types.META_SRV) else ''
						) + (
						'&nbsp;<img src="/images/16x16/licorn.png" alt="%s" width="16" height="16" />'
							% _('This machine has Licorn® installed.')
								if (machine.system_type & host_types.LICORN) else ''
						) + (
						'&nbsp;<img src="/images/16x16/alt.png" alt="%s" width="16" height="16" />'
							% _('This machine is an ALT® client.')
								if (machine.system_type & host_types.ALT) else ''
						) + (
						'&nbsp;<img src="/images/16x16/debian.png" alt="%s" width="16" height="16" />'
							% _('This machine Debian installed.')
								if (machine.system_type & host_types.DEBIAN) else ''
						) + (
						'&nbsp;<img src="/images/16x16/ubuntu.png" alt="%s" width="16" height="16" />'
							% _('This machine is Ubuntu installed.')
								if (machine.system_type & host_types.UBUNTU) else ''
						) + (
						'&nbsp;<img src="/images/16x16/apple.png" alt="%s" width="16" height="16" />'
							% _('This machine is manufactured by Apple® Computer Inc.')
								if (machine.system_type & host_types.APPLE) else ''
						) + (
						'&nbsp;<img src="/images/16x16/free.png" alt="%s" width="16" height="16" />'
							% _('This machine is a Freebox appliance.')
								if (machine.system_type & host_types.FREEBOX) else ''
						) + (
						'&nbsp;<img src="/images/16x16/printer.png" alt="%s" width="16" height="16" />'
							% _('This machine is a network printer.')
								if (machine.system_type & host_types.PRINTER) else ''
						) + (
						'&nbsp;<img src="/images/16x16/scanner.png" alt="%s" width="16" height="16" />'
							% _('This machine is a network scanner.')
								if (machine.system_type & host_types.MULTIFUNC) else ''
						)),
					hostname, edit, machine.ip,
					hostname, edit, machine.ether,
					hostname, edit, pyutils.format_time_delta(
						float(machine.expiry) - time.time(), use_neg=True) \
								if machine.expiry else '-'
					)

			if machine.managed:
				html_data += '''

			<!-- MANAGED -->
			<td class="user_action_center">
				<a href="/machines/unmanage/%s" title="%s" class="managed">
				<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span></a>
			</td>
				''' % (hostname, _("""Unmanage machine (remove it from """
					"""configuration, in order to allow it to be managed by """
					"""another server."""))
			else:
				html_data += '''

			<!-- UNMANAGED -->
			<td class="user_action_center">
				<a href="/machines/manage/%s" title="%s" class="floating">
				<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span></a>
			</td>
				''' % (hostname, _("""Manage machine (fix its IP address and """
					"""configure various aspects of the client)."""))

			return html_data

		for machine in self:
			# don't display offline machines
			if machine.status & host_status.OFFLINE \
					or machine.master_machine:
				continue

			#machine  = m[mid]
			hostname = machine.hostname

			# we add the hostname to gecosValue and lockedValue to be sure to obtain
			# unique values. This prevents problems with empty or non-unique GECOS
			# and when sorting on locked status (accounts would be overwritten and
			# lost because sorting must be done on unique values).
			accounts[machine.ip] = {
				'status'  : str(machine.status) + hostname,
				'hostname': hostname,
				'ip'      : machine.ip,
				'ether'   : machine.ether if machine.ether else _('<unknown>') + hostname,
				'expiry'  : machine.expiry,
				'managed' : str(machine.managed) + hostname
			}

			# index on the column choosen for sorting, and keep trace of the mid
			# to find account data back after ordering.
			ordered[hlstr.validate_name(accounts[machine.ip][sort])] = machine

		sorted_data = ordered.keys()
		sorted_data.sort()
		if order == "desc": sorted_data.reverse()

		for order_key in sorted_data:
			data += html_build_compact(ordered[order_key])

		def print_totals(totals):
			output = ""
			for total in totals:
				if totals[total] != 0:
					output += '''
		<tr class="list_total">
			<td colspan="5" class="total_left">%s</td>
			<td class="total_right">%d</td>
		</tr>
			''' % (_("number of <strong>%s</strong> machines:") % total, totals[total])
			return output

		data += '''
		<tr>
			<td colspan="5">&#160;</td></tr>
		%s
		<tr class="list_total">
			<td colspan="5" class="total_left">%s</td>
			<td class="total_right">%d</td>
		</tr>
	</table>
		''' % (print_totals(totals),
			_("<strong>Total number of machines:</strong>"),
			reduce(lambda x, y: x+y, totals.values()))

		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.page_body_end(w.total_time(start, time.time()))))
