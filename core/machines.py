# -*- coding: utf-8 -*-
"""
Licorn core: machines - http://docs.licorn.org/core/machines.html

:copyright: 2010 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2
"""
from traceback import print_exc

import netifaces, ipcalc, dumbnet, Pyro, socket

from threading  import current_thread
from time       import strftime, localtime
from subprocess import Popen, PIPE

from licorn.foundations           import logging, exceptions
from licorn.foundations           import process, hlstr, network
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace

from licorn.foundations.base      import Enumeration, Singleton
from licorn.foundations.constants import host_status, host_types

from licorn.core           import LMC
from licorn.core.classes   import CoreController, CoreStoredObject
from licorn.daemon         import network_service, priorities

class Machine(CoreStoredObject):
	counter = 0
	arp_table = None
	def __init__(self, mid, hostname=None, ether=None, expiry=None,
		lease_time=None, status=host_status.UNKNOWN, managed=False,
		system=None, system_type=host_types.UNKNOWN, backend=None, **kwargs):

		CoreStoredObject.__init__(self, oid=mid, name=hostname,
			controller=LMC.machines, backend=backend)

		assert ltrace('objects', '| Machine.__init__(%s, %s)' % (mid, hostname))

		# mid == IP address (unique on a given network)
		self.mid         = self._oid
		self.ip          = self.mid

		# hostname will be DNS-reversed from IP, or constructed.
		self.hostname    = self.name

		self.ether       = ether
		self.expiry      = expiry
		self.lease_time  = lease_time

		# will be updated as much as possible with the current host status.
		self.status      = status

		# True if the machine is recorded in local configuration files.
		self.managed     = managed

		# OS and OS level, arch, mixed in one integer.
		self.system_type = system_type

		# the Pyro proxy (if the machine has one) for contacting it across the
		# network.
		self.system      = system
	def ping(self, and_more=False):
		""" PING. """
		caller = current_thread().name
		#assert ltrace('machines', '> %s: ping(%s)' % (caller, self.mid))

		with self.lock():
			try:
				pinger = network.Pinger(self.mid)
				pinger.ping()

			except (exceptions.DoesntExistsException,
					exceptions.TimeoutExceededException), e:

				self.status = host_status.OFFLINE

			except Exception, e:
				assert ltrace('machines', '  %s: cannot ping %s (was: %s).' % (
					caller, self.mid, e))
				pass

			else:
				self.status = host_status.ONLINE

				if and_more:
					network_service(priorities.NORMAL, self.pyroize)
					network_service(priorities.LOW, self.arping)

			# close the socket (no more needed), else we could get
			# "too many open files" errors (254 open sockets for .
			pinger.reset(self)
			del pinger

		assert ltrace('machines', '< %s: ping(%s) → %s' % (caller, self.mid,
												host_status[self.status]))
	def resolve(self):
		""" Resolve IP to hostname, if possible. """
		caller = current_thread().name

		assert ltrace('machines', '> %s: resolve(%s)' % (caller, self.mid))

		with self.lock():
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
				del LMC.machines.by_hostname[old_hostname]
				LMC.machines.by_hostname[self.hostname] = self

		assert ltrace('machines', '< %s resolve(%s)' % (caller, self.hostname))
	def arping(self):
		""" find the ether address. """

		if Machine.arp_table is None:
			Machine.arp_table = dumbnet.arp()

		caller    = current_thread().name

		assert ltrace('machines', '> %s: arping(%s)' % (caller, self.mid))

		with self.lock():
			try:
				# str() is needed to convert from dumbnet.addr() type.
				self.ether = str(Machine.arp_table.get(dumbnet.addr(self.mid)))

			except Exception, e:
				assert ltrace('machines', '  %s: cannot arping %s (was: %s).'
						% (caller, self.mid, e))
		assert ltrace('machines', '< %s: arping(%s) → %s'
						% (caller, self.mid, self.ether))
	def pyroize(self):
		""" find if the machine is Pyro enabled or not. """
		caller = current_thread().name

		assert ltrace('machines', '> %s: pyroize(%s)' % (caller, self.mid))

		with self.lock():
			try:
				# we don't assign directly the pyro proxy into
				# machines[mid]['system'] because it can be invalid
				# until the noop() call succeeds and guarantees the
				# remote system is really Pyro enabled.
				remotesys = Pyro.core.getAttrProxyForURI(
						"PYROLOC://%s:%s/system" % (self.mid,
							LMC.configuration.licornd.pyro.port))
				remotesys._setTimeout(5.0)
				remotesys.noop()
			except Exception, e:
				if __debug__:
					if str(e) == 'connection failed':
						assert ltrace('machines', '  %s: no pyro on %s.' % (
								caller, self.mid))
						pass
					else:
						remotesys.release()
						del remotesys
						assert ltrace('machines', '  %s: cannot pyroize %s '
							'(was: %s)' % (caller, self.mid, e))
						pass
				self.guess_host_type()
			else:
				self.system_type = remotesys.get_host_type()
				self.status      = remotesys.get_status()
				self.system      = remotesys
		assert ltrace('machines', '< %s: pyroize(%s) → %s'
				% (caller, self.mid, self.system))
	def guess_host_type(self):
		""" On a network machine which don't have pyro installed, try to
			determine type of machine (router, PC, Mac, Printer, etc) and OS
			(for computers), to help admin know on which machines he/she can
			install Licorn® client software. """

		logging.progress('machines.guess_host_type() not implemented.')
		return
	def shutdown(self, warn_users=True):
		""" Shutdown a machine, after having warned the connected user(s) if
			asked to."""

		if self.system:
			self.system.shutdown()
			self.status == host_status.SHUTTING_DOWN
			logging.info('Shut down machine %s.' % self.hostname)

		else:
			raise exceptions.LicornRuntimeException('''Can't shutdown a '''
				'''non remote-controlled machine!''')
	def update_status(self, status):
		""" update the current machine status, in a clever manner. """
		with self.lock():
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
class MachinesController(Singleton, CoreController):
	""" Holds all machines objects (indexed on IP addresses, reverse mapped on
		hostnames and ether addresses which should be unique). """
	init_ok         = False
	load_ok         = False
	_licorn_protected_attrs = CoreController._licorn_protected_attrs

	def __init__(self):
		""" Create the machine accounts list from the underlying system.
			The arguments are None only for get (ie Export and ExportXml) """

		if MachinesController.init_ok:
			return

		assert ltrace('machines', 'MachinesController.__init__()')

		CoreController.__init__(self, name='machines',
			reverse_mappings=['hostname', 'ether'])

		self._nmap_cmd_base = [ 'nmap', '-v', '-n', '-T5', '-sP', '-oG',	'-' ]
		self._nmap_not_installed = False

		MachinesController.init_ok = True
	def add_machine(self, mid, hostname=None, ether=None, backend=None,
		status=host_status.UNKNOWN):
		assert ltrace('machines', '| add_machine(%s, %s, %s, %s)' % (mid,
			hostname, backend, status))
		self[mid] = Machine(mid=mid,
			ether=ether,
			hostname=hostname if hostname else
				network.build_hostname_from_ip(mid),
			backend=backend if backend else Enumeration('null_backend'),
			status=status)

		network_service(priorities.LOW, self[mid].ping, and_more=True)
		network_service(priorities.LOW, self[mid].resolve)
	def load(self):
		if MachinesController.load_ok:
			return
		else:
			assert ltrace('machines', '| load()')
			self.reload()
			MachinesController.load_ok = True
	def reload(self):
		""" Load (or reload) the data structures from the system files. """

		assert ltrace('machines', '> reload()')

		CoreController.reload(self)

		with self.lock():
			self.clear()

			for backend in self.backends:
				assert ltrace('machines', '  reload(%s)' % backend.name)
				for machine in backend.load_Machines():
					if machine.ip in self.keys():
						raise backend.generate_exception(
							'AlreadyExistsException', machine.ip)

					self.__setitem__(machine.ip, machine)

		assert ltrace('machines', '< reload()')
	def initial_scan(self):
		caller    = current_thread().name

		assert ltrace('machines', '> %s: initial_scan()' % caller)

		logging.info('%s: %s initial network scan.' % (caller,
			stylize(ST_RUNNING, 'started')))

		with self.lock():

			# FIRST, scan our know machines, if any.
			for machine in self:
				network_service(priorities.LOW, machine.ping, and_more=True)
				network_service(priorities.LOW, machine.resolve)

				if machines[mid].ether in (None, []):
					network_service(priorities.LOW, machine.arping)

		# THEN, scan the whole LAN to add more.
		network_service(priorities.LOW, self.scan_network)

		assert ltrace('machines', '< %s: initial_scan()' % caller)
	def scan_network(self):
		""" Scan a whole network and add all discovered machines to
		the local configuration. """

		caller   = current_thread().name

		#logging.info('%s: %s LAN scan.' % (caller,
		#									stylize(ST_RUNNING, 'started')))

		assert ltrace('machines', '> %s: scan_network()' % caller)

		known_ips   = self.keys()
		ips_to_scan = []
		for iface in network.interfaces():
			iface_infos = netifaces.ifaddresses(iface)
			if 2 in iface_infos:
				logging.info('%s: programming scan of LAN %s.0/%s.'
					% (caller, iface_infos[2][0]['addr'].rsplit('.', 1)[0],
						network.netmask2prefix(iface_infos[2][0]['netmask'])))

				for ipaddr in ipcalc.Network('%s.0/%s' % (
						iface_infos[2][0]['addr'].rsplit('.', 1)[0],
						network.netmask2prefix(
							iface_infos[2][0]['netmask']))):
					# need to convert because ipcalc returns IP() objects.
					ipaddr = str(ipaddr)
					if ipaddr[-2:] != '.0' and ipaddr[-4:] != '.255':
						if ipaddr in known_ips:
							network_service(priorities.LOW, self[str(ipaddr)].ping)
						else:
							self.add_machine(str(ipaddr))

		assert ltrace('machines', '< %s: scan_network()' % caller)
	def WriteConf(self, mid=None):
		""" Write the machine data in appropriate system files."""

		assert ltrace('machines', 'saving data structures to disk.')

		with self.lock():
			if mid:
				LMC.backends[
					self[mid]['backend']
					].save_Machine(mid)
			else:
				for backend in self.backends:
					backend.save_Machines()
	def Select(self, filter_string, filter_type=host_status):
		""" Filter machine accounts on different criteria. """

		filtered_machines = []

		assert ltrace('machines', '> Select(%s)' % filter_string)

		with self.lock():
			mids = self.keys()
			mids.sort()

			if filter_type == host_status:

				def keep_mid_if_status(mid, status=None):
					#print('mid: %s, status: %s, keep if %s' % (
					#	mid, self[mid]['status'], status))
					if self[mid].status == status:
						filtered_machines.append(mid)

				if None == filter_string:
					filtered_machines = []

				elif host_status.ONLINE & filter_string:

					if host_status.ACTIVE & filter_string:
						def keep_mid_if_active(mid):
							return keep_mid_if_status(mid, status=host_status.ACTIVE)
						map(keep_mid_if_active, mids)

					if host_status.IDLE & filter_string:
						def keep_mid_if_idle(mid):
							return keep_mid_if_status(mid, status=host_status.IDLE)
						map(keep_mid_if_idle, mids)

					if host_status.ASLEEP & filter_string:
						def keep_mid_if_asleep(mid):
							return keep_mid_if_status(mid, status=host_status.ASLEEP)
						map(keep_mid_if_asleep, mids)

			else:
				import re
				mid_re = re.compile("^mid=(?P<mid>\d+)")
				mid = mid_re.match(filter_string)
				if mid is not None:
					mid = int(mid.group('mid'))
					filtered_machines.append(mid)

			assert ltrace('machines', '< Select(%s)' % filtered_machines)
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

		m = self
		justw=10

		def build_cli_output_machine_data(mid):

			account = [	stylize(ST_NAME \
							if m[mid].managed else ST_SPECIAL,
							m[mid].hostname),
						'%s: %s%s' % (
								'status'.rjust(justw),
								stylize(ST_ON
										if m[mid].status & host_status.ONLINE
											else ST_OFF,
										host_status[m[mid].status].title()),
								'' if m[mid].system is None
										else ' (remote control enabled)'
							),
						'%s: %s (%s%s)' % (
								'address'.rjust(justw),
								str(mid),
								'expires: %s, ' % stylize(ST_ATTR,
									strftime('%Y-%d-%m %H:%M:%S',
									localtime(float(m[mid].expiry))))
										if m[mid].expiry else '',
									'managed' if m[mid].managed
													else 'floating',
							),
						'%s: %s' % (
								'ethernet'.rjust(justw),
								str(m[mid].ether)
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
	def is_alt(self, mid):
		""" Return True if the machine is an ALT client, else False. """

		hostname = self[mid].hostname

		try:
			is_ALT = self[mid].ether.lower().startswith(
				'00:e0:f4:')
		except (AttributeError, KeyError):
			is_ALT = False

		assert ltrace('machines', '| is_alt(mid=%s, hostname=%s) -> %s' % (
			mid, hostname, is_ALT))

		return is_ALT
	def confirm_mid(self, mid):
		""" verify a MID or raise DoesntExists. """
		try:
			return self[mid].ip
		except KeyError:
			raise exceptions.DoesntExistsException(
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
				_('''Can't build a valid hostname (got %s, which doesn't'''
				''' verify %s)''') % (
					inputhostname, hlstr.regex['hostname']))

		return hostname
