# -*- coding: utf-8 -*-
"""
Licorn Daemon internals - network related .

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import Pyro
import dumbnet

from threading                    import current_thread
from licorn.foundations           import logging
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import host_status

from licorn.core                  import LMC
from licorn.daemon.core           import dqueues

def queue_wait(queue, tprettyname, wait_message, caller):
	logging.progress('%s: waiting for %d %s to %s (qsize=%d).' % (
			caller, LMC.configuration.licornd.threads.pool_members, tprettyname,
			wait_message, queue.qsize()))
	queue.join()
def queue_wait_for_pingers(caller):
	queue_wait(dqueues.pings, 'pingers', 'ping network hosts',
		caller)
def queue_wait_for_arpingers(caller):
	queue_wait(dqueues.arpings, 'arpingers', 'ARP ping network hosts',
		caller)
def queue_wait_for_pyroers(caller):
	queue_wait(dqueues.pyrosys, 'pyroers',
		'discover Pyro on online hosts', caller)
def queue_wait_for_reversers(caller):
	queue_wait(dqueues.reverse_dns, 'reversers',
		'PTR resolve IP addresses', caller)
def thread_network_links_builder():
	""" Scan our known machines, then launch a discover operation on local
	network(s). The scan & discover operations consist in pinging hosts, and
	looking for Pyro enabled ones, while reversing IPs to find eventual DNS
	names and Ethernet addresses if they are unknown.
	"""

	caller    = current_thread().name
	machines  = LMC.machines

	assert ltrace('machines', '> thread_network_links_builder()')

	logging.info('%s: starting initial network scan.' % caller)

	with machines.lock():
		mids = machines.keys()

	# scan our know machines, if any.
	for mid in mids:
		dqueues.pings.put(mid)
		dqueues.reverse_dns.put(mid)

		if machines[mid].ether in (None, []):
			dqueues.arpings.put(mid)
			pass

	queue_wait_for_pingers(caller)

	for mid in mids:
		with LMC.machines[mid].lock():
			if machines[mid].status & host_status.ONLINE:
				dqueues.pyrosys.put(mid)

	queue_wait_for_pyroers(caller)

	queue_wait_for_reversers(caller)
	queue_wait_for_arpingers(caller)

	# then discover everything around us...
	machines.scan_network()

	logging.info('%s: initial network scan finished.' % caller)

	assert ltrace('machines', '< thread_network_links_builder()')
def thread_periodic_scanner():
	""" Scan all machines to be sure they are still alive, or still down.

		LOCKED to avoid corruption if a reload() occurs during scan.
	"""

	caller = current_thread().name
	pingqueue = dqueues.pings

	machines = LMC.machines

	with machines.lock():
		logging.progress('%s: periodic scan of non-managed network hosts.' %
			caller)

		for mid in machines.machines.keys():
			if machines[mid].system:
				# machine will report its status in real time, don't bother.
				logging.progress('%s: skipping machine %s, push enabled.'%
					caller)
				continue

			# machine is not META IT / Licorn® controlled and doesn't push
			# status information, we need to find by ourselves.
			pingqueue.put(mid)

	queue_wait_for_pingers(caller)
def pool_job_reverser(mid, *args, **kwargs):
	"""  Find the hostname for an IP, or build it (PoolJobThread target method). """

	caller = current_thread().name
	machines = LMC.machines

	assert ltrace('machines', '> %s: pool_job_reverser(%s)' % (caller, mid))

	with LMC.machines[mid].lock():
		old_hostname = machines[mid].hostname
		try:
			# get the first hostname from the list.
			machines[mid].hostname = socket.gethostbyaddr(mid)[0]
		except:
			logging.warning2("%s: couldn't reverse IP %s." % (caller, mid))
		else:
			# update the hostname cache.
			del machines.hostname_cache[old_hostname]
			machines.hostname_cache[machines[mid].hostname] = mid

	assert ltrace('machines', '< %s: pool_job_reverser(%s)' % (
		caller, machines[mid].hostname))
def pool_job_pinger(mid, *args, **kwargs):
	"""  Ping an IP (PoolJobThread target method). """

	caller = current_thread().name
	machines = LMC.machines

	if machines.nmap_not_installed:
		# the status should already be unknown (from class constructor).
		#machines[mid]status = host_status.UNKNOWN
		return

	assert ltrace('machines', '> %s: pool_job_pinger(%s)' % (caller, mid))

	with LMC.machines[mid].lock():
		up_hosts, down_hosts = machines.run_nmap([ mid ])

		if up_hosts != []:
			machines[mid].status = host_status.ONLINE
			retval = True
		elif down_hosts != []:
			machines[mid].status = host_status.OFFLINE
			retval = False
		else:
			retval = None

	assert ltrace('machines', '< %s: pool_job_pinger(%s)' % (caller, retval))
	return retval
def pool_job_arpinger(mid, *args, **kwargs):
	"""  Ping an IP (PoolJobThread target method). """

	caller = current_thread().name
	machines = LMC.machines
	arp_table = dumbnet.arp()

	assert ltrace('machines', '> %s: pool_job_arpinger(%s)' % (caller, mid))

	with LMC.locks.machines[mid]:
		try:
			machines[mid].ether = arp_table.get(dumbnet.addr(mid))

		except Exception, e:
			logging.warning2('%s: exception %s for host %s.' % (caller, e, mid))

	assert ltrace('machines', '< %s: pool_job_arpinger(%s)' % (caller, retval))
def pool_job_pyrofinder(mid, *args, **kwargs):
	""" scan a network host and try to find if it is Pyro enabled.
		This method is meant to be run from a LicornPoolJobThread. """

	caller = current_thread().name
	machines = LMC.machines

	assert ltrace('machines', '| %s: pool_job_pyrofinder(%s)' % (caller, mid))

	with LMC.machines[mid].lock():
		try:
			# we don't assign directly the pyro proxy into
			# machines[mid]['system'] because it can be invalid
			# until the noop() call succeeds and guarantees the
			# remote system is really Pyro enabled.
			remotesys = Pyro.core.getAttrProxyForURI(
					"PYROLOC://%s:%s/system" % (mid,
						LMC.configuration.licornd.pyro.port))
			remotesys._setTimeout(2)
			remotesys.noop()
		except Exception, e:
			assert ltrace('machines',
				'  %s: find_pyrosys(): %s is not pyro enabled.' %(caller,
				mid))
			logging.warning2('%s: exception %s for host %s.' % (
				caller, e, mid))
			machines.guess_host_type(mid)
		else:
			machines[mid].system_type = remotesys.get_host_type()
			machines[mid].status      = remotesys.get_status()
			machines[mid].system      = remotesys
