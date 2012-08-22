# -*- coding: utf-8 -*-
"""
Licorn core: machines - http://docs.licorn.org/core/machines.html

:copyright: 2010 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2
"""
import os, time, types
from collections import deque

import netifaces, ipcalc, dumbnet, Pyro, socket, functools, itertools

from threading  import current_thread
from time       import strftime, localtime

from licorn.foundations           import logging, exceptions, settings
from licorn.foundations           import process, hlstr, network, pyutils, events
from licorn.foundations.workers   import workers
from licorn.foundations.ltrace    import *
from licorn.foundations.styles    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.constants import *
from licorn.foundations.base      import Enumeration, DictSingleton
from licorn.foundations.classes   import SharedResource
from licorn.foundations.events    import LicornEvent
from licorn.core                  import LMC
from licorn.core.classes          import CoreController, CoreStoredObject

def not_myself(func):
	@functools.wraps(func)
	def wrap(self, *a, **kw):
		if self.myself or self.master_machine:
			return
		else:
			return func(self, *a, **kw)
	return wrap
def system_connected(func):
	@functools.wraps(func)
	def wrap(self, *a, **kw):
		if self.system:
			try:
				return func(self, *a, **kw)

			except:
				logging.exception(_('Failed to call `{0}()` on machine {1}!').format(
					stylize(ST_NAME, func.__name__), stylize(ST_NAME, self.hostname)))
		else:
			logging.warning(_('Cannot call `{0}` on non-connected machine {1}!').format(
				stylize(ST_NAME, func.__name__), stylize(ST_NAME, self.hostname)))
	return wrap
def myself_or_system_forward(func):
	@functools.wraps(func)
	def wrap(self, *a, **kw):
		if self.myself:
			kw['machine'] = self
			return getattr(LMC.system, func.__name__)(*a, **kw)

		if self.system:
			try:
				return getattr(self.system, func.__name__)(*a, **kw)

			except:
				logging.exception(_('Failed to call `{0}()` on machine {1}!').format(
					stylize(ST_NAME, func.__name__), stylize(ST_NAME, self.hostname)))
		else:
			msg = _('Cannot call `{0}` on non-connected machine {1}!').format(
				stylize(ST_NAME, func.__name__), stylize(ST_NAME, self.hostname))
			logging.warning(msg)

			try:
				print kw
				print kw['raise_exception']
				if kw['raise_exception']:
					print "raising"
					raise exceptions.LicornWebCommandException(msg)
			except KeyError:
				print "KeyError"
				pass
				# raise_exception is not a valid kwarg
	return wrap

class Machine(CoreStoredObject, SharedResource):

	# for SelectableController
	_id_field   = 'mid'

	by_hostname = {}
	by_name     = by_hostname
	by_ether    = {}
	arp_table   = None

	# just a cache, for informations given by nmap.
	# we manually add missing names from /etc/services.
	_service_names      = {
			settings.pyro.port:	'licornd',
			3356              :	'licornd-wmi',
			8069              :	'openerp-XML-RPC',
			8070              :	'openerp-NET-RPC'
		}

	_nmap_cmd_base      = [ 'nmap', '-v', '-n', '-T5', '-sP', '-oG', '-' ]
	_nmap_cmd_scan_base = [ 'nmap', '-v', '-n', '-T5', '-p0-65535', '-oG', '-' ]
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

	_lpickle_ = {
		'drop__' : False,
		}

	def __init__(self, mid, hostname=None, ether=None, expiry=None,
		lease_time=None, status=host_status.UNKNOWN, managed=False,
		system=None, system_type=host_types.UNKNOWN,
		linked_machines=None, linked_users=None, linked_groups=None,
		backend=None, myself=False, **kwargs):

		super(Machine, self).__init__(controller=LMC.machines, backend=backend)

		assert ltrace(TRACE_OBJECTS, '| Machine.__init__(%s, %s)' % (mid, hostname))

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

		# scanned by nmap if present, converted to various
		# features offered by the machine in our various interfaces.
		self.open_ports = deque()

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

		self.has_already_been_online = False

	@property
	def mid(self):
		""" The IP address of the host. """
		return self.__mid
	@property
	def wid(self):
		""" Used in the WMI, return the IP address replacing '.' by '_' """
		return self.__mid.replace('.', '_')

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

		Machine.by_hostname[hostname] = self

		LicornEvent('machine_hostname_changed', host=self).emit()

	name = hostname
	def add_link(self, licorn_object):
		""" TODO. """

		caller = current_thread().name

		if isinstance(licorn_object, Machine):

			self.linked_machines.append(licorn_object)
			licorn_object.master_machine = self

			# avoid talking to myself via the network, if applicable.
			licorn_object.myself = self.myself

		else:
			raise NotImplementedError(_(u'no other link than machine yet'))

		logging.info(_(u'{0}: Linked {1} to {2}.').format(
								caller, stylize(ST_UGID, licorn_object.ip),
								stylize(ST_UGID, self.ip)))
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
						logging.warning2(_(u'{0}: guess_os({1}) → unknown '
							u'key "{2}" with value "{2}", please update our '
							u'knowledge database if you what type of device '
							u'it is.').format(caller, self.mid, key, value))
						continue

				except KeyError:
					logging.warning2(_(u'{0}: guess_os({1}) → unknown {2} '
						u'value "{3}", please update our knowledge database '
						u'if you what type of device it is.').format(
							caller, self.mid, key, value))
					continue
		else:
			assert ltrace(TRACE_MACHINES, '| %s: guess_os(%s) → nmap '
				'not installed, can\'t guess OS.' % (caller, self.mid))
			pass
	def ping(self, and_more=False):
		""" PING. """
		caller = current_thread().name
		#assert ltrace(TRACE_MACHINES, '> %s: ping(%s)' % (caller, self.mid))

		old_status = self.status
		UP_status = [ host_status.ONLINE, host_status.PINGS, host_status.ACTIVE ]

		with self.lock:

			if self.myself:
				self.status = host_status.ACTIVE

				if and_more:
					workers.network_enqueue(priorities.NORMAL, self.scan_ports)
					workers.network_enqueue(priorities.LOW, self.arping)
					workers.network_enqueue(priorities.LOW, self.resolve)
				assert ltrace(TRACE_MACHINES, '| %s: ping(%s) → %s' % (
									caller, self.mid, host_status[self.status]))

				self.has_already_been_online = True
				return

			try:
				pinger = network.Pinger(self.mid)
				pinger.ping()

			except (exceptions.DoesntExistException,
					exceptions.TimeoutExceededException), e:

				self.status = host_status.OFFLINE
				if old_status in UP_status:
					LicornEvent('host_offline', host=self).emit()

			except Exception, e:
				assert ltrace(TRACE_MACHINES, '  %s: cannot ping %s (was: %s).' % (
					caller, self.mid, e))
				pass

			else:
				self.status = host_status.PINGS
				if old_status not in UP_status:
					LicornEvent('host_back_online'
									if self.has_already_been_online
									else 'host_online', host=self).emit()

				if and_more:
					workers.network_enqueue(priorities.NORMAL, self.scan_ports)
					workers.network_enqueue(priorities.LOW, self.arping)
					workers.network_enqueue(priorities.LOW, self.resolve)

				self.has_already_been_online = True
			# close the socket (no more needed), else we could get
			# "too many open files" errors (254 open sockets for .
			pinger.reset(self)
			del pinger

		assert ltrace(TRACE_MACHINES, '| %s: ping(%s) → %s' % (
								caller, self.mid, host_status[self.status]))
	def resolve(self):
		""" Resolve IP to hostname, if possible. """
		caller = current_thread().name

		#assert ltrace(TRACE_MACHINES, '> %s: resolve(%s)' % (caller, self.mid))

		with self.lock:
			#old_hostname = self.hostname

			try:
				self.hostname = socket.gethostbyaddr(self.mid)[0]
			except Exception:
				logging.exception(_(u'Could not resolve machine name for '
									u'address {0}'), self.mid)

		assert ltrace(TRACE_MACHINES, '| %s: resolve(%s) → %s' % (
											caller, self.mid, self.hostname))
	def scan_ports(self):
		""" find if the machine is Pyro enabled or not. """
		caller = current_thread().name

		assert ltrace(TRACE_MACHINES, '> %s: scan_ports(%s)' % (caller, self.mid))

		if not Machine._nmap_installed:
			# better-than-nothing fallback: we always try to find pyro manually.
			workers.network_enqueue(priorities.NORMAL, self.pyroize)
			return


		#  -PS/PA/PU/PY[portlist]: TCP SYN/ACK, UDP or SCTP discovery to given port
		#              -p <port ranges>: Only scan specified ports


		with self:
			# TODO: implement this with netstat locally, or just scan myself?
			if self.myself:
				workers.network_enqueue(priorities.NORMAL, self.update_informations)
				return

			for line in process.execute(
					Machine._nmap_cmd_scan_base + [ self.mid ])[0].splitlines():

				if line.startswith('#'):
					continue

				if 'Ports: ' in line:

				# example line = "Host: 192.168.0.10 ()	Ports: 22/open/tcp//ssh///, 25/open/tcp//smtp///	Ignored State: closed (985)"
					# split on TAB and take right part, then skip 'Ports: ' (7 chars)
					nmap_ports = [ x.split('/') for x in line.split('\t')[1][7:].split(', ') ]

					for port in nmap_ports:
						port[0] = int(port[0])
						self.open_ports.append(port[0])

						# fill the cache
						if port[0] not in Machine._service_names:
							Machine._service_names[port[0]] = port[4]

			if settings.pyro.port in self.open_ports:
				workers.network_enqueue(priorities.NORMAL, self.pyroize)
		assert ltrace(TRACE_MACHINES, '< %s: scan_ports(%s) → %s' % (caller, self.mid, self.open_ports))
	def pyroize(self):
		""" find if the machine is Pyro enabled or not. """
		caller = current_thread().name

		assert ltrace(TRACE_MACHINES, '> %s: pyroize(%s)' % (caller, self.mid))

		with self.lock:

			if self.myself:
				self.system = None
				self.update_informations()
				return

			if self.system is not None:
				logging.progress(_(u'{0}: {1} already pyroized, not doing '
								u'the work again.').format(caller, self.mid))
				return

			try:
				# we don't assign directly the pyro proxy into
				# machines[mid]['system'] because it can be invalid
				# until the noop() call succeeds and guarantees the
				# remote system is really Pyro enabled.
				remotesys = Pyro.core.getAttrProxyForURI(
						"PYROLOC://%s:%s/system" % (self.mid,
													settings.pyro.port))
				remotesys._setTimeout(3.0)
				remotesys.noop()

			except Pyro.errors.ProtocolError, e:
				workers.network_enqueue(priorities.LOW, self.guess_os)
				assert ltrace(TRACE_MACHINES, '  %s: cannot pyroize %s '
								'(was: %s)' % (caller, self.mid, e))

			except Pyro.errors.PyroError, e:
				remotesys.release()
				del remotesys
				workers.network_enqueue(priorities.LOW, self.guess_os)
				assert ltrace(TRACE_MACHINES, '%s: pyro error %s on %s.' % (
						caller, e, self.mid))

			else:
				self.system = remotesys
				self.pyro_deduplicate()
				self.update_informations()
		assert ltrace(TRACE_MACHINES, '| %s: pyroize(%s) → %s'
											% (caller, self.mid, self.system))
	def pyro_deduplicate(self):
		""" try to find if the remote system has multiple interfaces and
			if we have multiple record for it. Then, link them.
		"""

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
							self.add_link(self.controller[iface])
						#else:
						#	print '>>nothing done'

					else:
						#print '>> creating', iface, 'on next loop'
						#
						# when the second machine will have been created,
						# the pyroize() phase will reconcile master/slave
						# again. Next service loop.
						workers.service_enqueue(priorities.HIGH,
									self.controller.add_machine, mid=iface)
	def pyro_shutdown(self):
		""" WIPE the system attribute and mark the machine as shutting down.
			DO the same for all linked machines if we are the master. Don't
			do anything if we are not.
		"""

		caller = current_thread().name

		if self.master_machine:
			assert ltrace(TRACE_MACHINES, '%s: not doing pyro_shutdown on self '
				'(%s), we are slave of %s.' (caller, self.ip,
					self.master_machine.ip))
			return

		logging.notice(_(u'{0}: {1} at {2}.').format(caller,
			stylize(ST_BAD, _(u'Licorn® %s shutdown') % (_(u'server')
				if self.system_type & host_types.META_SRV else _(u'client'))),
			stylize(ST_ADDRESS, self.mid)))

		LicornEvent('licorn_host_shutdown', host=self).emit()

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
		caller = current_thread().name

		if self.master_machine:
			return

		try:
			self.system.goodbye_from(remote_ifaces)

		except Pyro.errors.PyroError, e:
			logging.exception(_(u'{0}: _pyro_forward_goodbye_from(): harmless '
								u'error {1} from {2}.'), caller, e, self.ip)
	def arping(self):
		""" find the ether address. """

		if self.ether is not None:
			return

		if Machine.arp_table is None:
			Machine.arp_table = dumbnet.arp()

		caller = current_thread().name

		#assert ltrace(TRACE_MACHINES, '> %s: arping(%s)' % (caller, self.mid))

		with self.lock:
			try:
				# str() is needed to convert from dumbnet.addr() type.
				self.ether = str(Machine.arp_table.get(dumbnet.addr(self.mid)))

			except Exception, e:
				assert ltrace(TRACE_MACHINES, '  %s: cannot arping %s (was: %s).'
													% (caller, self.mid, e))
		assert ltrace(TRACE_MACHINES, '| %s: arping(%s) → %s'
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

					logging.notice(_(u'{0}: {1} at {2}.').format(caller,
						stylize(ST_OK, _(u'new Licorn® %s') % (_(u'server')
							if is_server else _(u'client'))),
						stylize(ST_ADDRESS, self.mid)))

					# FIXME: merge the next LicornEvent with this one,
					# and add the 'back_online=True/False' argument?
					LicornEvent('licorn_host_online', host=self).emit()

					workers.service_enqueue(priorities.HIGH, self.system.hello_from,
						LMC.system.local_ip_addresses())

			except Pyro.errors.PyroError:
				self.pyro_shutdown()

			else:
				self.status = self.system.get_status()

				if old_status & host_status.OFFLINE \
					and self.status & host_status.ONLINE:
					if is_licorn:
						logging.notice(_(u'{0}: {1} at {2}.').format(caller,
							stylize(ST_OK, _(u'Licorn® %s back online') % (
								_(u'server') if is_server else _(u'client'))),
							stylize(ST_ADDRESS, self.mid)))

						LicornEvent('licorn_host_online', host=self).emit()

					else:
						logging.progress(_(u'{0}: {1} came back '
											u'online.').format(caller,
											stylize(ST_ADDRESS, self.mid)))

			for machine in self.linked_machines:
				machine.system_type = self.system_type
				machine.status      = self.status

		# call this immediately, this will feed the cache and will
		# avoid a potential massive waiting time for the unlucky first
		# 'get machines' or machines listing in the WMi.
		self.software_updates()
	@not_myself
	@system_connected
	def shutdown(self, warn_users=True):
		""" Shutdown a machine, after having warned the connected user(s) if
			asked to."""

		with self.lock:
			self.status = host_status.SHUTTING_DOWN

		self.system.shutdown()
		logging.info(_('Shut down machine {0}.').format(self.hostname))
	@not_myself
	@system_connected
	def restart(self, condition=None):
		""" Restart the remote machine. """

		with self.lock:
			self.status = host_status.REBOOTING

		self.system.restart(condition=condition)
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

	# ===================================================== CORE.system methods
	@myself_or_system_forward
	def updates_available(self, *a, **kw): pass
	@myself_or_system_forward
	def security_updates(self, *a, **kw): pass
	@myself_or_system_forward
	def software_updates(self, *a, **kw): pass
	@myself_or_system_forward
	def do_upgrade(self, *a, **kw): pass

class MachinesController(DictSingleton, CoreController):
	""" Holds all machines objects (indexed on IP addresses, reverse mapped on
		hostnames and ether addresses which should be unique). """
	init_ok         = False
	load_ok         = False

	_licorn_protected_attrs = (CoreController._licorn_protected_attrs)

	#: used in RWI.
	def object_type_str(self):
		return _(u'machine')
	def object_id_str(self):
		return _(u'MID')
	@property
	def sort_key(self):
		return 'hostname'

	# local and specific implementations of SelectableController methods.
	def by_mid(self, mid, strong=False):
		# we need to be sure we get an int(), because the 'uid' comes from RWI
		# and is often a string.
		return self[mid]
	def by_hostname(self, hostname, strong=False):
		# Call the thing before returning it, because it's a weakref.
		# return Machine.by_hostname[hostname]()
		return Machine.by_hostname[hostname]

	# the generic way (called by SelectableController)
	by_key  = by_mid
	by_id   = by_mid
	by_name = by_hostname
	# end SelectableController

	def __init__(self):
		""" Create the machine accounts list from the underlying system.
			The arguments are None only for get (ie Export and ExportXml) """

		if MachinesController.init_ok:
			return

		assert ltrace(TRACE_MACHINES, 'MachinesController.__init__()')

		super(MachinesController, self).__init__(name='machines')

		MachinesController.init_ok = True
		events.collect(self)
	def add_machine(self, mid, hostname=None, ether=None, backend=None,
		system_type=host_types.UNKNOWN, system=None, status=host_status.UNKNOWN,
		myself=False):
		""" Create a machine in the current controller. Parameters are
			essentially the same as in the
			:class:`Machine constructor <Machine>`.
		"""
		caller = current_thread().name

		assert ltrace(TRACE_MACHINES, '| %s: add_machine(%s, %s, %s, %s, %s, %s, '
			'%s, %s)' % (caller, mid, hostname, ether, backend,
				system_type, system, status, myself))

		self[mid] = Machine(mid=mid,
						ether=ether,
						hostname=hostname
							if hostname
							else mid,
						system_type=system_type,
						system=system,
						backend=backend
							if backend else Enumeration(name='null_backend'),
						status=status,
						myself=myself
					)

		workers.network_enqueue(priorities.LOW, self[mid].ping, and_more=True)

		return self[mid]
	@property
	def hostnames(self):
		return (h for h in Machine.by_hostname)
	@property
	def ethers(self):
		return (e for e in Machine.by_ether)
	def load(self):
		if MachinesController.load_ok:
			return

		assert ltrace(TRACE_MACHINES, '| load()')
		self.reload()

		#if LMC.configuration.experimental.enabled:
		#	self.create_wmi_object('/machines')

		MachinesController.load_ok = True
	def reload(self):
		""" Load (or reload) the data structures from the system files. """

		assert ltrace(TRACE_MACHINES, '> reload()')

		CoreController.reload(self)

		with self.lock:
			self.clear()

			for backend in self.backends:
				assert ltrace(TRACE_MACHINES, '  reload(%s)' % backend.name)
				for machine in backend.load_Machines():
					if machine.ip in self.keys():
						raise backend.generate_exception(
							'AlreadyExistsException', machine.ip)

					self.__setitem__(machine.ip, machine)

		assert ltrace(TRACE_MACHINES, '< reload()')
	def reload_backend(self, backend):
		assert ltrace(TRACE_USERS, '| reload_backend(%s)' % backend.name)

		loaded = []

		assert ltrace(TRACE_LOCKS, '| machines.reload_backend enter %s' % self.lock)

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

		assert ltrace(TRACE_LOCKS, '| users.reload_backend exit %s' % self.lock)
	@events.handler_method
	def daemon_will_restart(self, *args, **kwargs):
		""" We have some work to do in some cases when the local daemon restart. """

		reason = kwargs.pop('reason', reasons.UNKNOWN)

		if reason == reasons.BACKENDS_CHANGED:
			#TODO: restart peers ?
			# we need to restart our clients.
			for machine in self:
				try:
					machine.restart(condition=conditions.WAIT_FOR_ME_BACK_ONLINE)

				except Exception, e:
					pyutils.warn2_exception(_(u'{0:s}: cannot restart '
						u'machine {1:s} (was: {2:s})'), self, machine, e)
	def build_myself(self):
		""" create internal instance(s) for the current Licorn® daemon. """
		with self.lock:
			first_machine_found = None

			for iface in network.interfaces():
				iface_infos = netifaces.ifaddresses(iface)
				if 2 in iface_infos:
					ipaddr = iface_infos[2][0]['addr']

					try:
						ether = iface_infos[17][0]['addr']

					except:
						# some interfaces (aliases) don't have any MAC.
						ether = None

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

		assert ltrace_func(TRACE_MACHINES)

		with self.lock:
			# FIRST, add myself to known machines, and link all my IP
			# addresses to the same machine, to avoid displaying more than one
			# on our interfaces (CLI / WMI).
			self.build_myself()

			# SECOND update our know machines statuses, if any.
			for machine in self:
				if machine.status & host_status.UNKNOWN:
					workers.network_enqueue(priorities.LOW, machine.ping, and_more=True)

				if machine.hostname.split('.', 1)[0].isdigit():
					workers.network_enqueue(priorities.LOW, machine.resolve)

			# THEN scan the whole LAN to discover more machines.
			if settings.licornd.network.lan_scan:
				workers.network_enqueue(priorities.LOW, self.scan_network)

			else:
				logging.notice(_('{0}: network auto-discovery disabled by '
					'configuration rule {1}, not going further.').format(
						caller, stylize(ST_ATTR, 'licornd.network.lan_scan')))

		assert ltrace(TRACE_MACHINES, '< %s: initial_scan()' % caller)
	def scan_network(self, network_to_scan=None):
		""" Scan a whole network and add all discovered machines to
		the local configuration. If arg"""

		caller = current_thread().name

		assert ltrace(TRACE_MACHINES, '> %s: scan_network()' % caller)

		logging.progress(_(u'{0}: {1} initial network discovery.').format(caller,
									stylize(ST_RUNNING, _(u'starting'))))

		known_ips   = self.keys()
		ips_to_scan = []

		if network_to_scan is None:
			for iface in network.interfaces():
				iface_infos = netifaces.ifaddresses(iface)

				if 2 in iface_infos:

					if settings.licornd.network.lan_scan_public \
						or network.is_private(iface_infos[2][0]['addr'],
											iface_infos[2][0]['netmask']) :
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
						logging.info('%s: public LAN %s.0/%s excluded from scan.'
							% (caller, iface_infos[2][0]['addr'].rsplit('.', 1)[0],
								network.netmask2prefix(
													iface_infos[2][0]['netmask'])))

		else:
			for netw in network_to_scan.split(','):
				for ipaddr in ipcalc.Network(netw):
					ips_to_scan.append(str(ipaddr))

		for ipaddr in ips_to_scan:
			if ipaddr[-2:] != '.0' and ipaddr[-4:] != '.255':
				if ipaddr in known_ips:
					workers.network_enqueue(priorities.LOW,
											self[str(ipaddr)].ping)
				else:
					self.add_machine(mid=str(ipaddr))

		assert ltrace(TRACE_MACHINES, '< %s: scan_network()' % caller)
	def goodbye_from(self, remote_ips):
		""" Called from remote `licornd`, when it runs :meth:`announce_shutdown`. """

		current_ips = self.keys()

		for ip in remote_ips:
			if ip in current_ips:
				workers.service_enqueue(priorities.HIGH, self[ip].pyro_shutdown)
	def hello_from(self, remote_ips):
		""" this method is called on the remote side, when the local side calls
			:meth:`announce_shutdown`.
		"""
		current_ips = self.keys()

		for ip in remote_ips:
			if ip in current_ips:
				workers.service_enqueue(priorities.HIGH, self[ip].update_informations)
			else:
				self.add_machine(mid=ip)
				workers.service_enqueue(priorities.HIGH, self[ip].update_informations)
	def announce_shutdown(self):
		""" announce our shutdown to all connected machines. """

		local_ifaces = LMC.configuration.network.local_ip_addresses()

		for machine in self:
			if machine.system and not (
							machine.master_machine or machine.myself):
				assert ltrace(TRACE_MACHINES,
									'| annouce_shutdown() to %s' % machine.ip)
				workers.service_enqueue(priorities.HIGH,
								machine._pyro_forward_goodbye_from,
									local_ifaces)
	def licorn_machines_count(self):
		count = 0
		for machine in self:
			if machine.system_type & host_types.LICORN \
						and machine.status & host_status.ONLINE:
				count += 1

		return count

		#
		# WARNING: don't service_wait() here, the thread would join its own
		# queue and this would deadblock (not lock ;-) ).
		#
	def WriteConf(self, mid=None):
		""" Write the machine data in appropriate system files."""

		assert ltrace(TRACE_MACHINES, 'saving data structures to disk.')

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

		assert ltrace(TRACE_MACHINES, '> select(%s)' % filter_string)

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

						if host_status.PINGS & filter_string:
							map(lambda x: keep_status(x, host_status.PINGS),
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

			assert ltrace(TRACE_MACHINES, '< select(%s)' % filtered_machines)
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

		assert ltrace(TRACE_MACHINES, '| ExportCLI(%s)' % mids)

		justw=10

		def cli_status(m):
			if m.status & host_status.OP_IN_PROGRESS:
				color = ST_IMPORTANT

			elif m.status & host_status.ONLINE:
				color = ST_ON

			else:
				color = ST_OFF

			return u','.join(stylize(color, host_status[s].title())
								for s in host_status
									if m.status & s
										and s not in (host_status.UNKNOWN,
														host_status.ALL,
														host_status.ONLINE,))
		def test_upgrade_needed(m):
			if m.myself:
				system = LMC.system

			elif m.system:
				system = m.system

			else:
				return ''

			try:
				up, sec = system.updates_available(full=True)

			except:
				logging.exception(_(u'Package status unavailable on '
					u'machine {0}.'), (ST_NAME, m.hostname))

				return _(u', {0}').format(stylize(ST_DEBUG,
						_(u'packages status unavailable')))

			return _(u', {0} package(s) to upgrade {1}').format(up,
						stylize(ST_IMPORTANT if sec else ST_OK,
						_(u'({0} security update(s))').format(
						sec or _(u'no'))))

		def build_cli_output_machine_data(mid):

			m = self[mid]

			account = [	stylize(ST_NAME
							if m.managed else ST_SPECIAL,
							m.hostname) + (_(u' (this machine)')
								if m.myself else ''),
						_(u'{0}: {1}{2}{3}').format(
								_(u'status').rjust(justw),
								cli_status(m),
								_(u' (remote control enabled)') if m.system else u'',
								test_upgrade_needed(m)
							),
						_(u'{0}: {1} ({2}{3})').format(
								_(u'address').rjust(justw),
								str(mid),
								_(u'expires: %s, ') % stylize(ST_ATTR,
									# TODO: locale-formated time.
									strftime('%Y-%d-%m %H:%M:%S',
									localtime(float(m.expiry))))
										if m.expiry else u'',
									_(u'managed') if m.managed
													else _(u'floating'),
							),
						_(u'{0}: {1}').format(
								_(u'ethernet').rjust(justw),
								str(m.ether)
							)
						]
			return u'\n'.join(account)

		data = u'\n'.join(map(build_cli_output_machine_data, mids)) + u'\n'

		return data
	def ExportXML(self, selected=None, long_output=False):
		""" Export the machine accounts list to XML. """

		if selected is None:
			mids = self.keys()
		else:
			mids = selected
		mids.sort()

		assert ltrace(TRACE_MACHINES, '| ExportXML(%s)' % mids)

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

		if type(mid) in (types.StringType, types.UnicodeType):
			self[mid].shutdown(warn_users=warn_users)
		elif type(mid) == types.ListType:
			for m in mid:
				try:
					self[m].shutdown(warn_users=warn_users)
				except KeyError:
					logging.exception('{0} to shutdown machine {1}, not'
					' referenced in the machines controller'.format(
						stylize(ST_BAD, "Unable"), stylize(ST_PATH, m)))
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

		assert ltrace(TRACE_MACHINES, '| is_alt(mid=%s) → %s' % (mid, is_ALT))

		return is_ALT
	def confirm_mid(self, mid):
		""" verify a MID or raise DoesntExist. """
		try:
			return self[mid].ip
		except KeyError:
			raise exceptions.DoesntExistException(_(u'MID %s does not exist') % mid)
	def make_hostname(self, inputhostname=None):
		""" Make a valid hostname from what we're given. """

		if inputhostname is None:
			raise exceptions.BadArgumentError(
									_('You must pass a hostname to verify!'))

		# use provided hostname and verify it.
		hostname = hlstr.validate_name(str(inputhostname),
			maxlenght = LMC.configuration.machines.hostname_maxlenght)

		if not hlstr.cregex['hostname'].match(hostname):
			raise exceptions.LicornRuntimeError(_(u'Cannot build a valid '
					u'hostname (got {0}, which does not verify {1}).').format(
						inputhostname, hlstr.regex['hostname']))

		return hostname

	def word_match(self, word):
		return hlstr.word_match(word, set(itertools.chain(*[
			(m.name, m.mid) for m in self])))




