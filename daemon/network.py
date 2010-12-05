# -*- coding: utf-8 -*-
"""
Licorn Daemon internals - network related .

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import Pyro

from threading                    import current_thread
from licorn.foundations           import logging
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import host_status

from licorn.core                  import LMC
from licorn.daemon.core           import dqueues

def queue_wait(queue, tprettyname, wait_message, caller, listener=None):
	logging.progress('%s: waiting for %d %s to %s (qsize=%d).' % (
			caller, LMC.configuration.licornd.threads.pool_members, tprettyname,
			wait_message, queue.qsize()), listener=listener)
	queue.join()
def queue_wait_for_pingers(caller, listener=None):
	queue_wait(dqueues.pings, 'pingers', 'ping network hosts',
		caller, listener=listener)
def queue_wait_for_arppingers(caller, listener=None):
	queue_wait(dqueues.arppings, 'arppingers', 'ARP ping network hosts',
		caller, listener=listener)
def queue_wait_for_pyroers(caller, listener=None):
	queue_wait(dqueues.pyrosys, 'pyroers',
		'discover Pyro on online hosts', caller, listener=listener)
def queue_wait_for_reversers(caller, listener=None):
	queue_wait(dqueues.reverse_dns, 'reversers',
		'PTR resolve IP addresses', caller, listener=listener)
def thread_network_links_builder():
	""" Ping all known machines. On online ones, try to connect to pyro and
	get current detailled status of host. Notify the host that we are its
	controlling server, and it should report future status change to us.

	LOCKED to avoid corruption if a reload() occurs during operations.
	"""

	caller    = current_thread().name
	pingqueue = dqueues.pings
	pyroqueue = dqueues.pyrosys
	machines  = LMC.machines

	assert ltrace('machines', '> thread_network_links_builder()')

	logging.info('%s: starting initial network scan.' % caller)

	with machines.lock():
		mids = machines.keys()

	for mid in mids:
		pingqueue.put(mid)

	queue_wait_for_pingers(caller)

	for mid in mids:
		with LMC.machines[mid].lock():
			if machines[mid].status & host_status.ONLINE:
				pyroqueue.put(mid)

	queue_wait_for_pyroers(caller)

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
def pool_job_reverser(mid, listener=None, *args, **kwargs):
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
def pool_job_pinger(mid, listener=None, *args, **kwargs):
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
def pool_job_arppinger(mid, listener=None, *args, **kwargs):
	"""  Ping an IP (PoolJobThread target method). """

	caller = current_thread().name
	machines = LMC.machines

	if machines.nmap_not_installed:
		# the status should already be unknown (from class constructor).
		#machines[mid]status = host_status.UNKNOWN
		return

	assert ltrace('machines', '> %s: pool_job_pinger(%s)' % (caller, mid))

	with LMC.locks.machines[mid]:
		machines[mid].ether = machines.run_arping(mid)

	assert ltrace('machines', '< %s: pool_job_pinger(%s)' % (caller, retval))
def pool_job_pyrofinder(mid, listener=None, *args, **kwargs):
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
			print e
			machines.guess_host_type(mid)
		else:
			machines[mid].system_type = remotesys.get_host_type()
			machines[mid].status      = remotesys.get_status()
			machines[mid].system      = remotesys
