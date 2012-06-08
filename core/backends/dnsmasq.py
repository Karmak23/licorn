# -*- coding: utf-8 -*-
"""
Licorn DNSmasq backend - http://docs.licorn.org/core/backends/dnsmasq.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

.. versionadded:: 1.3
	This backend was implemented during the 1.2 ⇢ 1.3 development cycle.

"""
import os

from licorn.foundations           import exceptions, logging
from licorn.foundations           import readers, network
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import Singleton, Enumeration
from licorn.foundations.pyutils   import add_or_dupe_obj
from licorn.foundations.hlstr     import cregex

from licorn.core                  import LMC
from licorn.core.machines         import Machine
from licorn.core.backends         import MachinesBackend

class DnsmasqBackend(Singleton, MachinesBackend):
	""" A plugin to cope with dnsmasq files."""

	def __init__(self):
		MachinesBackend.__init__(self, name='dnsmasq')
		assert ltrace(TRACE_DNSMASQ, '| __init__()')

		self.files = Enumeration()
		self.files.dnsmasq_conf   = '/etc/dnsmasq.conf'
		self.files.dnsmasq_leases = '/var/lib/misc/dnsmasq.leases'

		# no client counterparts for dnsmasq backend.
		self.server_only = True
	def initialize(self):
		assert ltrace(TRACE_DNSMASQ, '> initialize()')

		if os.path.exists(self.files.dnsmasq_conf):
			# if the configuration file is not in place, assume dnsmasq is not
			# installed. we don't currently care if it is enabled or not in
			# etc/default/dnsmasq.
			self.available = True

		assert ltrace(TRACE_DNSMASQ, '< initialize(%s)' % self.available)
		return self.available
	def load_dhcp_host(self, host_record):
		""" Called ONLY from self.load_machines().
			see dnsmasq(8) -> "dhcp-host" for details. """

		assert ltrace(TRACE_DNSMASQ, '> load_dhcp_host(host_record=%s)'
			% host_record)

		temp_host = Enumeration()

		for value in host_record:
			if value == 'ignore' or value.startswith('id:') \
				or value.startswith('set:'):
				assert ltrace(TRACE_MACHINES, '  entry skipped, not a regular host.')
				del temp_host
				return None

			# gather as many data as we can about this host.

			if cregex['ether_addr'].match(value):
				# got a MAC address -> can have more than one for a
				# given machine (e.g. wifi & ethernet)
				add_or_dupe_obj(temp_host, 'ether', value)

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

		if not hasattr(temp_host, 'ip'):
			# presumably got a general configuration directive,
			# not speaking about any particular host. SKIP.
			assert ltrace(TRACE_MACHINES, '  host skipped because no IPv4 address.')

			return None

		# be sure we have a unique hostname, else many things could
		# fail.
		if not hasattr(temp_host, 'hostname'):
			 temp_host.hostname = network.build_hostname_from_ip(temp_host.ip)

		# FIXME: re-order this ti be clean.
		final_host = Machine(mid=temp_host.ip, hostname=temp_host.hostname,
						managed=True, backend=self)

		for key in ('ether', 'lease_time', 'expiry'):
			if key in temp_host.keys():
				setattr(final_host, key, getattr(temp_host, key))

		return final_host
	def genex_AlreadyExistsException(self, ip, *args, **kwargs):
		""" Generate an appropriate exception about an already existing IP
			address. This is most probably a duplicate entry in our
			configuration file. """
		return exceptions.AlreadyExistsException('''a machine '''
			'''with the IP address %s already exists in the '''
			'''system. Please check %s against duplicate '''
			'''entries.''' % (ip, self.files.dnsmasq_conf))
	def load_Machines(self):
		""" get the machines from static conf and leases, and create the pivot
		data for our internal data structures. """

		assert ltrace(TRACE_DNSMASQ, '> load_machines()')

		dnsmasq_conf = readers.dnsmasq_read_conf(self.files.dnsmasq_conf)

		if os.path.exists(self.files.dnsmasq_leases):
			self.leases = readers.dnsmasq_read_leases(self.files.dnsmasq_leases)
		else:
			self.leases = {}

		if dnsmasq_conf.has_key('dhcp-host'):
			#print dnsmasq_conf['dhcp-host'][0]

			if hasattr(dnsmasq_conf['dhcp-host'][0], '__iter__'):
				# we got a list of hosts.

				for host_record in dnsmasq_conf['dhcp-host']:
					machine = self.load_dhcp_host(host_record)
					if machine:
						yield machine
					else:
						continue
			else:
				# we got a single host in the conf file.
				machine = self.load_dhcp_host(dnsmasq_conf['dhcp-host'])
				if machine:
					yield machine

				# TODO: check if the lease IP is the same as in the conf
				# (why not ?). idem for the hostname.

		for ether in self.leases:
			 yield Machine(
				mid=self.leases[ether]['ip'],
				hostname=network.build_hostname_from_ip(self.leases[ether]['ip']) \
					if not self.leases[ether].has_key('hostname') \
					or self.leases[ether]['hostname'] == '*' \
					else self.leases[ether]['hostname'],
				ether=ether,
				expiry=self.leases[ether]['expiry'] \
					if self.leases[ether].has_key('expiry') else None,
				backend=self
				)

		assert ltrace(TRACE_DNSMASQ, '< load_machines()')
	def save_Machines(self):
		""" save the list of machines. """
		pass
	def __reload_controller_machines(self, pathname):
		logging.notice(_(u'{0}: configuration file {1} changed, '
			'reloading {2} controller.').format(str(self),
				stylize(ST_PATH, pathname),
				stylize(ST_NAME, 'machines')))

		LMC.machines.reload_backend(self)
	def _inotifier_install_watches(self, inotifier):
		inotifier.watch_conf(self.files.dnsmasq_leases, LMC.machines, self.__reload_controller_machines)
