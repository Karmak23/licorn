# -*- coding: utf-8 -*-
"""
Licorn DNSmasq plugin for machines handling.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import os

from licorn.foundations           import exceptions, readers, process
from licorn.foundations.objects   import Singleton
from licorn.foundations.constants import host_status
from licorn.foundations.ltrace    import ltrace

class dnsmasq_controller(Singleton):
	""" A plugin to cope with dnsmasq files."""

	name           = "dnsmasq"
	enabled        = False
	configuration  = None
	backend        = None
	warnings       = None
	purpose        = 'machines'
	backend_compat = ('unix')

	def __str__(self):
		return self.name
	def __repr__(self):
		return self.name
	def __init__(self, configuration, backend=None, warnings=True):
		ltrace('dnsmasq', '| __init__()')
		self.configuration = configuration
		self.warinings = warnings

		if backend:
			self.backend = backend

	def initialize(self):

		ltrace('dnsmasq', '> initialize()')

		self.dnsmasq_conf_file   = '/etc/dnsmasq.conf'
		self.dnsmasq_leases_file = '/var/lib/misc/dnsmasq.leases'

		if os.path.exists(self.dnsmasq_conf_file):
			# if the configuration file is not in place, assume dnsmasq is not
			# installed. we don't currently care if it is enabled or not in
			# etc/default/dnsmasq.
			self.enabled = True

		ltrace('dnsmasq', '< initialize(%s)' % self.enabled)
		return self.enabled
	def set_backend(self, backend):
		if backend is not None:
			self.backend = backend
	def load_machines(self):
		""" get the machines from static conf and leases, and create the pivot
		data for our internal data structures. """

		ltrace('dnsmasq', '> load_machines()')

		dnsmasq_conf = readers.dnsmasq_read_conf(self.dnsmasq_conf_file)

		if os.path.exists(self.dnsmasq_leases_file):
			leases = readers.dnsmasq_read_leases(self.dnsmasq_leases_file)
		else:
			leases = {}

		machines       = {}
		hostname_cache = {}
		ips_to_scan    = []

		from licorn.foundations.pyutils import add_or_dupe
		from licorn.foundations.hlstr import cregex

		if dnsmasq_conf.has_key('dhcp-host'):
			for host_record in dnsmasq_conf['dhcp-host']:
				# see dnsmasq(8) -> "dhcp-host" for details

				temp_host = {}

				ltrace('dnsmasq', '  load_machines(host_record=%s)'
					% host_record)

				for value in host_record:
					if value == 'ignore' or value.startswith('id:') \
						or value.startswith('set:'):
						continue
					if cregex['ether_addr'].match(value):
						# got a MAC address -> can have more than one for a
						# given machine (e.g. wifi & ethernet)
						add_or_dupe(temp_host, 'ether', value)

						if leases.has_key(value):
							temp_host['expiry'] = leases[value]['expiry']
							# after using it, delete the lease entry, in order
							# to not process it twice.
							del leases[value]

					elif cregex['ipv4'].match(value):
						# got an IPv4 -> only one for a given machine
						temp_host['ip'] = value
						ips_to_scan.append(value)
					elif cregex['duration'].match(value):
						temp_host['lease_time'] = value
					else:
						# got a hostname -> only one for a given machine
						temp_host['hostname'] = value

				if not temp_host.has_key('ip'):
					# presumably got a general configuration directive,
					# not speaking about any particular host. SKIP.
					continue

				if machines.has_key(temp_host['ip']):
					raise exceptions.AlreadyExistsException('''a machine '''
						'''with the ip address %s already exists in the '''
						'''database. Please check %s against duplicate '''
						'''entries.''' % (temp_host['ip'],
							self.dnsmasq_conf_file))

				# be sure we have a unique hostname, else many things could
				# fail.
				if not temp_host.has_key('hostname'):
					 temp_host['hostname'] = \
						'UNKNOWN-%s' % temp_host['ip'].replace('.', '-')

				machines[temp_host['ip']] = {
					'ip': temp_host['ip'],
					'hostname': temp_host['hostname'] ,
					'ether': temp_host['ether'] if temp_host.has_key('ether') \
						else None,
					'lease_time': temp_host['lease_time'] \
						if temp_host.has_key('lease_time') else None,
					'expiry': temp_host['expiry'] \
						if temp_host.has_key('expiry') else None,
					'status': host_status.OFFLINE,
					'managed': True
					}

				hostname_cache[temp_host['hostname']] = temp_host['ip']

				# TODO: check if the lease IP is the same as in the conf
				# (why not ?). idem for the hostname.

		for ether in leases:
			machines[leases[ether]['ip']] = {
				'ip': leases[ether]['ip'],
				'hostname': 'UNKNOWN-%s' % \
					leases[ether]['ip'].replace('.', '-') \
					if not leases[ether].has_key('hostname') \
					or leases[ether]['hostname'] == '*' \
					else leases[ether]['hostname'],
				'ether': ether,
				'lease_time': None,
				'expiry': leases[ether]['expiry'] \
					if leases[ether].has_key('expiry') else None,
				'status': host_status.OFFLINE,
				'managed': False
				}

			hostname_cache[machines[leases[ether]['ip']]['hostname']] = \
				leases[ether]['ip']

			ips_to_scan.append(leases[ether]['ip'])

		nmap_cmd = [ 'nmap', '-n', '-T5', '-sP', '-oG',	'-' ]
		nmap_cmd.extend(ips_to_scan)

		for status_line in process.execute(nmap_cmd)[0].splitlines():
			splitted = status_line.split()
			if splitted[0] == '#':
				continue
			if splitted[4] == 'Up':
					machines[splitted[1]]['status'] = status.IN_USE

		ltrace('dnsmasq', '< load_machines()')

		return machines, hostname_cache
	def save_machines(self):
		""" save the list of machines. """
		pass

	def save_machine(self, mid):
		""" Just a wrapper. Saving one machine in Unix backend is not
		significantly faster than saving all of them. """
		self.save_machines()
	def delete_machine(self, mid):
		""" Just a wrapper. Deleting one group in Unix backend is not
		significantly faster than saving all of them. """
		self.save_machines()

