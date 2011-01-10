# -*- coding: utf-8 -*-
"""
Licorn core: machines - http://docs.licorn.org/core/machines.html

:copyright: 2010 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2
"""

import netifaces, ipcalc

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
from licorn.daemon         import dqueues
from licorn.daemon.network import queue_wait_for_pingers, \
									queue_wait_for_pyroers, \
									queue_wait_for_reversers, \
									queue_wait_for_arpingers, \
									queue_wait_for_ipscanners

class Machine(CoreStoredObject):
	counter = 0
	def __init__(self, mid=None, hostname=None, ether=None, expiry=None,
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
					'status=None for machine %s(%s)' % (hostname, mid))
			else:
				# don't do anything if the status is already the same or finer.
				# E.G. ACTIVE is finer than ONLINE, which doesn't known if the
				# machine is idle or not.
				if not self.status & status:
					logging.progress("Updated machine %s's status to %s." % (
						stylize(ST_NAME, self.hostname),
						stylize(ST_COMMENT, host_status[status])
						))
					self.status = status
	def __str__(self):
		return '%s(%s‣%s) = {\n\t%s\n\t}\n' % (
			self.__class__,
			stylize(ST_UGID, self.mid),
			stylize(ST_NAME, self.hostname),
			'\n\t'.join([ '%s: %s' % (attr_name, getattr(self, attr_name))
					for attr_name in dir(self) ])
			)
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

		with self[mid].lock():
			dqueues.arpings.put(mid)
			dqueues.reverse_dns.put(mid)
			dqueues.pyrosys.put(mid)
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
	def scan_network2(self, wait_until_finish=False,
		*args, **kwargs):
		""" use nmap to scan a whole network and add all discovered machines to
		the local configuration. """

		caller   = current_thread().name
		pyroq    = dqueues.pyrosys
		arpingq  = dqueues.arpings
		reverseq = dqueues.reverse_dns

		assert ltrace('machines', '> %s: scan_network2()' % caller)

		ips_to_scan = []
		for iface in network.interfaces():
			iface_infos = netifaces.ifaddresses(iface)
			if 2 in iface_infos:
				logging.info('%s: Planning scan of local area network %s.0/%s.'
					% (caller, iface_infos[2][0]['addr'].rsplit('.', 1)[0],
						network.netmask2prefix(iface_infos[2][0]['netmask'])))

				for ipaddr in ipcalc.Network('%s.0/%s' % (
						iface_infos[2][0]['addr'].rsplit('.', 1)[0],
						network.netmask2prefix(
							iface_infos[2][0]['netmask']))):
					# need to convert because ipcalc returns IP() objects.
					ipaddr = str(ipaddr)
					if ipaddr[-2:] != '.0' and ipaddr[-4:] != '.255':
						dqueues.ipscans.put(str(ipaddr))

		if wait_until_finish:
			queue_wait_for_ipscanners(caller)
			queue_wait_for_arpingers(caller)
			queue_wait_for_reversers(caller)
			queue_wait_for_pyroers(caller)

		assert ltrace('machines', '< %s: scan_network2()' % caller)
	def scan_network(self, network_to_scan=None, wait_until_finish=False,
		*args, **kwargs):
		""" use nmap to scan a whole network and add all discovered machines to
		the local configuration. """

		caller   = current_thread().name
		pyroq    = dqueues.pyrosys
		arpingq  = dqueues.arpings
		reverseq = dqueues.reverse_dns

		assert ltrace('machines', '> %s: scan_network(%s)' % (
			caller, network_to_scan))

		if network_to_scan is None:
			network_to_scan = []
			for iface in network.interfaces():
				iface_infos = netifaces.ifaddresses(iface)
				if 2 in iface_infos:
					logging.info('Programming scan of local area network %s/%s.'
						% (iface_infos[2][0]['addr'],
							iface_infos[2][0]['netmask']))
					# FIXME: don't hard-code /24, but nmap doesn't understand
					# 255.255.255.0 and al...
					network_to_scan.append('%s/24' % iface_infos[2][0]['addr'])
				# else: interface as no IPv4 address assigned, skip it.

		with self.lock():
			current_mids = self.keys()

		# we have to skip our own addresses, else pyro will die after having
		# exhausted the max number of threads (trying connecting to ourself in
		# loop...).
		for iface in network.local_ip_addresses():
			try:
				up_hosts.remove(iface)
			except:
				pass

		for hostip in self.find_up_hosts(network_to_scan):
			if hostip in current_mids:
				continue

			with self.lock():
				logging.info('found online machine with IP address %s' % hostip)

				# create a fake hostname for now, the IP will be reversed a
				# little later to get the eventual real DNS name of host.
				#
				# Use null_backend because the discovered hostname is stored
				# nowhere for now. Don't yet know how to handle it, the discover
				# function is just a pure bonus for demos.
				machine = Machine(mid=hostip,
					hostname=network.build_hostname_from_ip(hostip),
					backend=Enumeration('null_backend'),
					status=host_status.ONLINE)
				self[hostip] = machine

			arpingq.put(hostip)
			reverseq.put(hostip)
			pyroq.put(hostip)

		# don't wait, search will be handled by the daemon. Give back hand to
		# the calling CLI process.
		if wait_until_finish:
			queue_wait_for_reversers(caller)
			queue_wait_for_pyroers(caller)
	def find_up_hosts(self, to_ping):
		""" run nmap on to_ping and return 2 lists of up and down hosts. """

		caller = current_thread().name
		nmap_cmd = self._nmap_cmd_base[:]
		nmap_cmd.extend(to_ping)

		assert ltrace('machines', '> %s: find_up_hosts(%s)' % (
			caller, ' '.join(nmap_cmd)))

		try:
			nmap_pipe = Popen(nmap_cmd, shell=False, stdout=PIPE, stderr=PIPE,
			close_fds=True).stdout
		except (IOError, OSError), e:
			if e.errno == 2:
				self._nmap_not_installed = True
				raise exceptions.LicornRuntimeException('''nmap is not '''
					'''installed on this system, can't use it!''', once=True)
			else:
				raise e

		for status_line in nmap_pipe.readlines():
			splitted = status_line.split()

			if splitted[0] == '#':
				continue
			if splitted[4] == 'Up':
					yield splitted[1]

		assert ltrace('machines', '< find_up_hosts()')
	def run_nmap(self, to_ping):
		""" run nmap on to_ping and return 2 lists of up and down hosts. """

		caller = current_thread().name
		nmap_cmd = self._nmap_cmd_base[:]
		nmap_cmd.extend(to_ping)

		assert ltrace('machines', '> %s: run_nmap(%s)' % (
			caller, ' '.join(nmap_cmd)))

		try:
			nmap_status = process.execute(nmap_cmd)[0]
		except (IOError, OSError), e:
			if e.errno == 2:
				self._nmap_not_installed = True
				raise exceptions.LicornRuntimeException('''nmap is not '''
					'''installed on this system, can't use it!''', once=True)
			else:
				raise e
		up_hosts   = []
		down_hosts = []

		for status_line in nmap_status.splitlines():
			splitted = status_line.split()
			#print splitted
			if splitted[0] == '#':
				continue
			if splitted[4] == 'Up':
					up_hosts.append(splitted[1])
			elif splitted[4] == 'Down':
					down_hosts.append(splitted[1])

		assert ltrace('machines', '< run_nmap(up=%s, down=%s)' % (
			up_hosts, down_hosts))
		return up_hosts, down_hosts
	def ping_all_machines(self, *args, **kwargs):
		""" run across all IPs and find which machines are up or down. """

		if self._nmap_not_installed:
			# don't do anything, this is useless. UNKNOWN status has already
			# been set on all machines by the backend load.
			return

		raise NotImplementedError('to be rewritten.')

		nmap_cmd = self._nmap_cmd_base[:]
		nmap_cmd.extend(self.keys())

		assert ltrace('machines', '> update_statuses(%s)' % ' '.join(nmap_cmd))

		try:
			nmap_status = process.execute(nmap_cmd)[0]
		except (IOError, OSError), e:
			if e.errno == 2:
				logging.warning2('''nmap is not installed on this system, '''
					'''can't ping machines''', once=True)
			else:
				raise e
		else:
			for status_line in nmap_status.splitlines():
				splitted = status_line.split()
				if splitted[0] == '#':
					continue
				assert ltrace('machines', '  update_statuses(%s) -> ' % (
					mid, splitted[4]))
				if splitted[4] == 'Up':
						self[splitted[1]]['status'] = host_status.ACTIVE
				elif splitted[4] == 'Down':
						self[splitted[1]]['status'] = host_status.OFFLINE
		assert ltrace('machines', '< update_statuses()')
	def guess_host_type(self, mid):
		""" On a network machine which don't have pyro installed, try to
			determine type of machine (router, PC, Mac, Printer, etc) and OS
			(for computers), to help admin know on which machines he/she can
			install Licorn® client software. """

		logging.progress('machines.guess_host_type() not implemented.')

		return
	def update_status(self, mid, status=None, system=None,
		*args, **kwargs):

		assert ltrace('machines', '| update_status(%s, %s)' % (mid, status))

		if mid in self.keys():
			self[mid].update_status(status)

		elif system:
			# this is a self-declaring pyro-enabled host. create it.
			self[mid] = Machine(mid=mid,
				hostname=network.build_hostname_from_ip(mid),
				backend=Enumeration('null_backend'),
				system=system,
				status=status)

			# try to reverse the hostname, but don't wait
			dqueues.reverse_dns.put(mid)
		else:
			logging.warning('update_status() called with invalid MID %s!' % mid)
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
	def Select(self, filter_string):
		""" Filter machine accounts on different criteria. """

		filtered_machines = []

		assert ltrace('machines', '> Select(%s)' % filter_string)

		with self.lock():
			mids = self.keys()
			mids.sort()

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
