# -*- coding: utf-8 -*-
"""
Licorn DNSmasq plugin for machines handling.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import os
from threading import RLock

from licorn.foundations           import exceptions, logging
from licorn.foundations           import readers, process
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, Enumeration
from licorn.foundations.constants import host_status
from licorn.foundations.pyutils   import add_or_dupe_attr
from licorn.foundations.hlstr     import cregex
from licorn.foundations.network   import build_hostname_from_ip

from objects             import MachinesBackend
from licorn.core         import LMC
from licorn.core.objects import Machine

class dnsmasq_controller(Singleton, MachinesBackend):
	""" A plugin to cope with dnsmasq files."""

	def __init__(self, warnings=True):
		assert ltrace('dnsmasq', '| __init__()')
		MachinesBackend.__init__(self, name='dnsmasq', warnings=warnings)

		self.files = Enumeration()
		self.files.dnsmasq_conf   = '/etc/dnsmasq.conf'
		self.files.dnsmasq_leases = '/var/lib/misc/dnsmasq.leases'
	def initialize(self):
		assert ltrace('dnsmasq', '> initialize()')

		if os.path.exists(self.files.dnsmasq_conf):
			# if the configuration file is not in place, assume dnsmasq is not
			# installed. we don't currently care if it is enabled or not in
			# etc/default/dnsmasq.
			self.available = True

		assert ltrace('dnsmasq', '< initialize(%s)' % self.available)
		return self.available
	def load_dhcp_host(self, host_record):
		""" Called ONLY from self.load_machines().
			see dnsmasq(8) -> "dhcp-host" for details. """

		temp_host = Machine(managed=True)

		assert ltrace('dnsmasq', '> load_dhcp_host(host_record=%s)'
			% host_record)

		for value in host_record:
			if value == 'ignore' or value.startswith('id:') \
				or value.startswith('set:'):
				assert ltrace('machines', '  entry skipped, not a regular host.')
				del temp_host
				return

			# gather as many data as we can about this host.

			if cregex['ether_addr'].match(value):
				# got a MAC address -> can have more than one for a
				# given machine (e.g. wifi & ethernet)
				add_or_dupe_attr(temp_host.ether, value)

				if self.leases.has_key(value):
					temp_host.expiry = self.leases[value]['expiry']
					# after using it, delete the lease entry, in order
					# to not process it twice.
					del self.leases[value]

			elif cregex['ipv4'].match(value):
				# got an IPv4 -> only one for a given machine
				temp_host.ip = value

			elif cregex['duration'].match(value):
				temp_host.lease_time = value

			else:
				# got a hostname -> only one for a given machine
				temp_host.hostname = value

		# data is gathered, here come the checks. if one of them fail,
		# the temp_host is bad, forget it.

		if temp_host.ip is None:
			# presumably got a general configuration directive,
			# not speaking about any particular host. SKIP.
			assert ltrace('machines', '  host skipped because no IPv4 address.')
			del temp_host
			return

		if self.machines.has_key(temp_host.ip):
			raise exceptions.AlreadyExistsException('''a machine '''
				'''with the ip address %s already exists in the '''
				'''database. Please check %s against duplicate '''
				'''entries.''' % (temp_host.ip,
					self.files.dnsmasq_conf))

		# be sure we have a unique hostname, else many things could
		# fail.
		if temp_host.hostname is None:
			 temp_host.hostname = build_hostname_from_ip(temp_host.ip)

		self.machines[temp_host.ip] = temp_host
		self.locks[temp_host.ip] = RLock()
		self.hostname_cache[temp_host.hostname] = temp_host.ip
	def load_Machines(self):
		""" get the machines from static conf and leases, and create the pivot
		data for our internal data structures. """

		assert ltrace('dnsmasq', '> load_machines()')

		dnsmasq_conf = readers.dnsmasq_read_conf(self.files.dnsmasq_conf)

		if os.path.exists(self.files.dnsmasq_leases):
			self.leases = readers.dnsmasq_read_leases(self.files.dnsmasq_leases)
		else:
			self.leases = {}

		self.machines       = {}
		self.hostname_cache = {}
		self.locks          = {}

		if dnsmasq_conf.has_key('dhcp-host'):
			#print dnsmasq_conf['dhcp-host'][0]

			if hasattr(dnsmasq_conf['dhcp-host'][0], '__iter__'):
				# we got a list of hosts.

				for host_record in dnsmasq_conf['dhcp-host']:
					self.load_dhcp_host(host_record)
			else:
				# we got a single host in the conf file.
				self.load_dhcp_host(dnsmasq_conf['dhcp-host'])

				# TODO: check if the lease IP is the same as in the conf
				# (why not ?). idem for the hostname.

		for ether in self.leases:
			self.machines[self.leases[ether]['ip']] = Machine(
				ip=self.leases[ether]['ip'],
				hostname='UNKNOWN-%s' % \
					self.leases[ether]['ip'].replace('.', '-') \
					if not self.leases[ether].has_key('hostname') \
					or self.leases[ether]['hostname'] == '*' \
					else self.leases[ether]['hostname'],
				ether=ether,
				expiry=self.leases[ether]['expiry'] \
					if self.leases[ether].has_key('expiry') else None,
				)

			self.hostname_cache[
				self.machines[
					self.leases[ether]['ip']
					]['hostname']
				] = self.leases[ether]['ip']

		assert ltrace('dnsmasq', '< load_machines(%s)' % self.machines)

		return self.machines, self.locks, self.hostname_cache
	def save_Machines(self):
		""" save the list of machines. """
		pass

dnsmasq = dnsmasq_controller()
