# -*- coding: utf-8 -*-
"""
Licorn core - http://dev.licorn.org/documentation/core

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>,
Licensed under the terms of the GNU GPL version 2
"""

import os, sys, socket, Pyro.core

from threading import RLock, current_thread
from time      import time, strftime, gmtime, localtime

from licorn.foundations           import logging, exceptions
from licorn.foundations           import process, hlstr, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.network   import build_hostname_from_ip, \
										find_local_ip_addresses
from licorn.foundations.base      import Enumeration, Singleton
from licorn.foundations.constants import host_status, filters, host_types

from licorn.core           import LMC
from licorn.core.objects   import LicornCoreController, Machine
from licorn.daemon         import dqueues
from licorn.daemon.network import queue_wait_for_pingers, \
									queue_wait_for_pyroers, \
									queue_wait_for_reversers

class MachinesController(Singleton, LicornCoreController):

	init_ok         = False
	load_ok         = False

	def __init__(self):
		""" Create the machine accounts list from the underlying system.
			The arguments are None only for get (ie Export and ExportXml) """

		if MachinesController.init_ok:
			return

		LicornCoreController.__init__(self, 'machines')

		self.nmap_cmd_base = [ 'nmap', '-v', '-n', '-T5', '-sP', '-oG',	'-' ]
		self.nmap_not_installed = False

		MachinesController.init_ok = True
	def load(self):
		if MachinesController.load_ok:
			return
		else:
			assert ltrace('machines', '| load()')
			self.reload()
			MachinesController.load_ok = True
	def __getitem__(self, item):
		return self.machines[item]
	def __setitem__(self, item, value):
		self.machines[item]=value
	def keys(self):
		return self.machines.keys()
	def has_key(self, key):
		return self.machines.has_key(key)
	def reload(self):
		""" Load (or reload) the data structures from the system files. """

		assert ltrace('machines', '> reload()')

		with self.lock():
			self.machines = {}
			self.hostname_cache = {}

			for backend in self.backends():
				assert ltrace('machines', '  reload(%s)' % backend.name)
				m, l, c = backend.load_Machines()

				self.machines.update(m)
				LMC.locks.machines.update(l)
				self.hostname_cache.update(c)
		assert ltrace('machines', '< reload()')
	def scan_network(self, network_to_scan, wait_until_finish=False,
		listener=None, *args, **kwargs):
		""" use nmap to scan a whole network and add all discovered machines to
		the local configuration. """

		caller   = current_thread().name
		pyroq    = dqueues.pyrosys
		reverseq = dqueues.reverse_dns

		assert ltrace('machines', '> %s: scan_network(%s)' % (
			caller, network_to_scan))

		up_hosts, down_hosts = self.run_nmap([ network_to_scan ])

		with self.lock():
			current_mids = self.machines.keys()

		# we have to skip our own addresses, else pyro will die after having
		# exhausted the max number of threads (trying connecting to ourself in
		# loop...).
		#current_mids.extend(find_local_ip_addresses())

		for hostip in up_hosts:
			if hostip in current_mids:
				continue

			with self.lock():
				logging.info('found online machine with IP address %s' % hostip,
					listener=listener)
				machine = Machine(mid=hostip,
					hostname=build_hostname_from_ip(hostip))
				self.machines[hostip] = machine
				# lock should be already built by constructor
				self.hostname_cache[machine.hostname] = machine.ip

			reverseq.put(hostip)
			pyroq.put(hostip)

		# don't wait, search will be handled by the daemon. Give back hand to
		# the calling CLI process.
		if wait_until_finish:
			queue_wait_for_reversers(caller, listener=listener)
			queue_wait_for_pyroers(caller, listener=listener)
	def run_arping(self, to_ping):
		""" run nmap on to_ping and return 2 lists of up and down hosts.

			On Windows:
			http://groups.google.com/group/comp.lang.python/msg/fd2e7437d72c1c21

			sudo arping -f -c 5 -w 2 192.168.119.254 -I eth2
			ARPING 192.168.119.254 from 192.168.119.200 eth2
			Unicast reply from 192.168.119.254 [00:25:86:E3:AE:92]  0.646ms
			Sent 1 probes (1 broadcast(s))
			Received 1 response(s)

		"""

		caller = current_thread().name
		arping_cmd = self.arping_cmd_base[:]
		nmap_cmd.append(to_ping)

		assert ltrace('machines', '> %s: run_arping(%s)' % (
			caller, ' '.join(arping_cmd)))

		assert ltrace('machines', '< run_nmap(up=%s, down=%s)' % (
			up_hosts, down_hosts))

	def run_nmap(self, to_ping):
		""" run nmap on to_ping and return 2 lists of up and down hosts. """

		caller = current_thread().name
		nmap_cmd = self.nmap_cmd_base[:]
		nmap_cmd.extend(to_ping)

		assert ltrace('machines', '> %s: run_nmap(%s)' % (
			caller, ' '.join(nmap_cmd)))

		try:
			nmap_status = process.execute(nmap_cmd)[0]
		except (IOError, OSError), e:
			if e.errno == 2:
				self.nmap_not_installed = True
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
	def ping_all_machines(self, listener=None, *args, **kwargs):
		""" run across all IPs and find which machines are up or down. """

		if self.nmap_not_installed:
			# don't do anything, this is useless. UNKNOWN status has already
			# been set on all machines by the backend load.
			return

		raise NotImplementedError('to be rewritten.')

		nmap_cmd = self.nmap_cmd_base[:]
		nmap_cmd.extend(self.machines.keys())

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
						self.machines[splitted[1]]['status'] = host_status.ACTIVE
				elif splitted[4] == 'Down':
						self.machines[splitted[1]]['status'] = host_status.OFFLINE
		assert ltrace('machines', '< update_statuses()')
	def guess_host_type(self, mid):
		""" On a network machine which don't have pyro installed, try to
			determine type of machine (router, PC, Mac, Printer, etc) and OS
			(for computers), to help admin know on which machines he/she can
			install Licorn® client software. """

		logging.notice('machines.guess_host_type() not implemented.')

		return
	def update_status(self, mid=None, hostname=None, status=None, listener=None,
		*args, **kwargs):

		mid, hostname = self.resolve_mid_or_hostname(mid, hostname)

		assert ltrace('machines', '| update_status(%s)' % status)

		with LMC.locks.machines[mid]:
			if status is None:
				# this part is not going to happen, because this method is called
				# (indirectly, via SystemController) from clients.
				logging.warning('machines.update_status() called with status=None '
					'for machine %s(%s)' % (hostname, mid), listener=listener)
			else:
				self.machines[mid].status = status
	def WriteConf(self, mid=None):
		""" Write the machine data in appropriate system files."""

		assert ltrace('machines', 'saving data structures to disk.')

		with self.lock():
			if mid:
				LMC.backends[
					self.machines[mid]['backend']
					].save_Machine(mid)
			else:
				for backend in self.backends():
					backend.save_Machines()
	def Select(self, filter_string):
		""" Filter machine accounts on different criteria. """

		filtered_machines = []

		assert ltrace('machines', '> Select(%s)' % filter_string)

		with self.lock():
			mids = self.machines.keys()
			mids.sort()

			def keep_mid_if_status(mid, status=None):
				#print('mid: %s, status: %s, keep if %s' % (
				#	mid, self.machines[mid]['status'], status))
				if self.machines[mid].status == status:
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
	def dump(self):
		""" Dump the internal data structures (debug and development use). """

		with self.lock():
			assert ltrace('machines', '| dump()')

			mids = self.machines.keys()
			mids.sort()

			hostnames = self.hostname_cache.keys()
			hostnames.sort()

			data = '%s:\n%s\n%s:\n%s\n' % (
				stylize(ST_IMPORTANT, 'core.machines'),
				'\n'.join(map(str, self.machines.itervalues())),
				stylize(ST_IMPORTANT, 'core.hostname_cache'),
				'\n'.join(['\t%s: %s' % (key, self.hostname_cache[key]) \
					for key in hostnames ])
				)

			return data
	def ExportCLI(self, selected=None, long_output=False):
		""" Export the machine accounts list to human readable («passwd») form.
		"""
		if selected is None:
			mids = self.machines.keys()
		else:
			mids = selected
		mids.sort()

		assert ltrace('machines', '| ExportCLI(%s)' % mids)

		m = self.machines

		def build_cli_output_machine_data(mid):

			account = [	stylize(ST_NAME \
							if m[mid].managed else ST_SPECIAL,
							m[mid].hostname),
						stylize(ST_OK, 'Online') \
								if m[mid].status == host_status.ACTIVE \
								else stylize(ST_BAD, 'Offline'),
						'managed' if m[mid].managed \
								else 'floating',
						str(mid),
						str(m[mid].ether),
						stylize(ST_ATTR,
							strftime('%Y-%d-%m %H:%M:%S',
							localtime(float(m[mid].expiry)))) \
							if m[mid].expiry else '',
						]
			return '/'.join(account)

		data = '\n'.join(map(build_cli_output_machine_data, mids)) + '\n'

		return data
	def ExportXML(self, selected=None, long_output=False):
		""" Export the machine accounts list to XML. """

		if selected is None:
			mids = self.machines.keys()
		else:
			mids = selected
		mids.sort()

		assert ltrace('machines', '| ExportXML(%s)' % mids)

		m = self.machines

		def build_xml_output_machine_data(mid):
			data = '''	<machine>
		<hostname>%s</hostname>
		<mid>%s</mid>
		<managed>%s</managed>
		<ether>%s</ether>
		<expiry>%s</expiry>\n''' % (
					m[mid].hostname,
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
	def shutdown(self, mid=None, hostname=None, warn_users=True, listener=None):
		""" Shutdown a machine, after having warned the connected user(s) if
			asked to."""

		mid, hostname = self.resolve_mid_or_hostname(mid, hostname)

		if self.machines[mid].system:
			self.machines[mid].system.shutdown()
			self.machines[mid].status == host_status.SHUTTING_DOWN
			logging.info('Shut down machine %s.' % hostname, listener=listener)

		else:
			raise exceptions.LicornRuntimeException('''Can't shutdown a '''
				'''non remote-controlled machine!''')
	def is_alt(self, mid=None, hostname=None):
		""" Return True if the machine is an ALT client, else False. """

		mid, hostname = self.resolve_mid_or_hostname(mid,hostname)

		try:
			is_ALT = self.machines[mid].ether.lower().startswith(
				'00:e0:f4:')
		except (AttributeError, KeyError):
			is_ALT = False

		assert ltrace('machines', '| is_alt(mid=%s, hostname=%s) -> %s' % (
			mid, hostname, is_ALT))

		return is_ALT
	def confirm_mid(self, mid):
		""" verify a MID or raise DoesntExists. """
		try:
			return self.machines[mid].ip
		except KeyError:
			raise exceptions.DoesntExistsException(
				"MID %s doesn't exist" % mid)
	def resolve_mid_or_hostname(self, mid=None, hostname=None):
		""" method used every where to get mid / hostname of a group object to
			do something onto. a non existing mid / hostname will raise an
			exception from the other methods methods."""

		if hostname is None and mid is None:
			raise exceptions.BadArgumentError(
				"You must specify a hotname or a MID to resolve from.")

		assert ltrace('machines', '| resolve_mid_or_hostname(mid=%s, hostname=%s)' % (
			mid, hostname))

		# we cannot just test "if gid:" because with root(0) this doesn't work.
		if mid is not None:
			hostname = self.mid_to_hostname(mid)
		else:
			mid = self.hostname_to_mid(hostname)
		return (mid, hostname)
	def exists(self, mid=None, hostname=None):
		if mid:
			return self.machines.has_key(mid)
		if hostname:
			return self.hostname_cache.has_key(hostname)

		raise exceptions.BadArgumentError(
			"You must specify a MID or a hostname to test existence of.")
	def hostname_to_mid(self, hostname):
		""" Return the mid of the machine 'hostname'. """
		try:
			# use the cache, Luke !
			return self.hostname_cache[hostname]
		except KeyError:
			try:
				int(hostname)
				logging.warning("You passed an mid to hostname_to_mid():"
					" %d (guess its hostname is « %s » )." % (
						hostname, self.machines[hostname].hostname))
			except ValueError:
				pass

			raise exceptions.LicornRuntimeException(
				_('''machine %s doesn't exist.''') % hostname)
	def mid_to_hostname(self, mid):
		""" Return the hostname for a given IP."""
		try:
			return self.machines[mid].hostname
		except KeyError:
			raise exceptions.DoesntExistsException(
				"MID %s doesn't exist" % mid)
	def guess_identifier(self, value):
		""" Try to guess everything of a machine from a
			single and unknown-typed info. """
		try:
			self.mid_to_hostname(value)
			mid = value
		except exceptions.DoesntExistsException, e:
			mid = self.mid_to_hostname(value)
		return mid
	def guess_identifiers(self, value_list):

		valid_ids=set()
		for value in value_list:
			try:
				valid_ids.add(self.guess_identifier(value))
			except exceptions.DoesntExistsException:
				logging.notice("Skipped non-existing hostname or MID '%s'." %
					stylize(ST_NAME, value))
		return valid_ids
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

