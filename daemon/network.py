# -*- coding: utf-8 -*-
"""
Licorn Daemon internals - network related .

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import Pyro, dumbnet, socket, time

from threading                    import current_thread
from licorn.foundations           import logging, network, exceptions, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import host_status

from licorn.core                  import LMC
from licorn.daemon.core           import dqueues
from licorn.daemon.threads        import QueueWorkerThread

def queue_wait(queue, tprettyname, wait_message, caller):
	logging.progress('%s: waiting for %d %s to %s (qsize=%d).' % (
			caller, LMC.configuration.licornd.threads.pool_members, tprettyname,
			wait_message, queue.qsize()))
	queue.join()
def queue_wait_for_ipscanners(caller):
	queue_wait(dqueues.ipscans, 'ipscanners', 'scan network hosts',
		caller)
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

	start_time = time.time()

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

	machines.scan_network2(wait_until_finished=True)

	logging.info('%s: initial network scan finished (took %s).' % (caller,
		pyutils.format_time_delta(time.time() - start_time)))

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
class DNSReverserThread(QueueWorkerThread):
	""" A thread who tries to find the DNS name of a given IP address, and keeps
		it in the host record for later use.

		Any socket.gethostbyaddr() can block or timeout on DNS call; this thread
		is daemonic to not block master daemon when it stops.
"""
	#: see :class:`QueueWorkerThread` for details.
	name='DNSReverser'
	#: see :class:`QueueWorkerThread` for details.
	number = 0
	#: see :class:`QueueWorkerThread` for details.
	count = 0
	def __init__(self):
		QueueWorkerThread.__init__(self, in_queue=dqueues.reverse_dns,
			daemon=True)
	def process(self, mid, *args, **kwargs):
		"""  Find the hostname for an IP, or build it. """

		assert ltrace('machines', '> %s.process(%s)' % (self.name, mid))

		with LMC.machines[mid].lock():
			old_hostname = LMC.machines[mid].hostname
			try:
				start_time = time.time()
				# get the first hostname from the list.
				LMC.machines[mid].hostname = socket.gethostbyaddr(mid)[0]
			except:
				logging.warning2("%s: couldn't reverse IP %s (took %s)." % (
					self.name, mid,
					pyutils.format_time_delta(time.time() - start_time)))
			else:
				# update the hostname cache.
				# FIXME: don't update the cache manually,
				# delegate it to *something*.
				del LMC.machines.by_hostname[old_hostname]
				LMC.machines.by_hostname[
					LMC.machines[mid].hostname] = LMC.machines[mid]

		assert ltrace('machines', '< %s.process(%s)' % (
		self.name, LMC.machines[mid].hostname))
class PingerThread(QueueWorkerThread, network.Pinger):
	""" Just Ping a machine, and store its status (UP or DOWN), depending on
		the pong status.

		FIXME: make this thread not daemon when we understand why they don't
		shutdown correctly.
	"""
	#: see :class:`QueueWorkerThread` for details.
	name='Pinger'
	#: see :class:`QueueWorkerThread` for details.
	number = 0
	#: see :class:`QueueWorkerThread` for details.
	count = 0
	def __init__(self):
		QueueWorkerThread.__init__(self, in_queue=dqueues.pings, daemon=True)
		network.Pinger.__init__(self)
	def process(self, mid, *args, **kwargs):
		"""  Ping an IP (PoolJobThread target method) """

		assert ltrace('machines', '> %s.process(%s)' % (self.name, mid))

		with LMC.machines[mid].lock():
			try:
				self.switch_to(mid)
				self.ping()

			except (exceptions.DoesntExistsException,
					exceptions.TimeoutExceededException), e:

				LMC.machines[mid].status = host_status.OFFLINE

			except Exception, e:
				logging.warning2('%s: exception %s for host %s.' % (
					self.name, e, mid))

			else:
				LMC.machines[mid].status = host_status.ONLINE

		assert ltrace('machines', '< %s:process(%s)' % (
		self.name, LMC.machines[mid].status))
class ArpingerThread(QueueWorkerThread):
	""" A thread who tries to find the ethernet address of an already recorded
		host, and keeps this ethernet address in the host record for later use.

		FIXME: make this thread not daemon when we understand why they don't
		shutdown correctly.
	"""
	#: see :class:`QueueWorkerThread` for details.
	name='Arpinger'
	#: see :class:`QueueWorkerThread` for details.
	number = 0
	#: see :class:`QueueWorkerThread` for details.
	count = 0
	def __init__(self):
		QueueWorkerThread.__init__(self, in_queue=dqueues.arpings, daemon=True)
		self.arp_table = dumbnet.arp()
	def process(self, mid, *args, **kwargs):
		""" scan a network host and try to find if it is Pyro enabled.
			This method is meant to be run from a LicornPoolJobThread. """

		assert ltrace('machines', '| %s.process(%s)' % (self.name, mid))

		with LMC.machines[mid].lock():
			try:
				LMC.machines[mid].ether = self.arp_table.get(dumbnet.addr(mid))
			except Exception, e:
				logging.warning2('%s: exception %s for host %s.' % (
					self.name, e, mid))
class PyroFinderThread(QueueWorkerThread):
	""" A thread who tries to find if a given host is Pyro enabled or not. If it
		is, record the address of the Pyro daemon (as a ProxyAttr) into the
		scanned host attributes for later use.

		Pyrofinder threads are daemons, because they can block a very long
		time on a host (TCP timeout on routers which drop packets), and
		during the time they block, the daemon cannot terminate and seems
		to hang. Setting these threads to daemon will permit the main
		thread to exit, even if some are still left and running.
	"""
	#: see :class:`QueueWorkerThread` for details.
	name='PyroFinder'
	#: see :class:`QueueWorkerThread` for details.
	number = 0
	#: see :class:`QueueWorkerThread` for details.
	count = 0
	def __init__(self):
		QueueWorkerThread.__init__(self, in_queue=dqueues.pyrosys,
			name='pyrofinder-%d' % PyroFinderThread.number, daemon=True)
	def process(self, mid, *args, **kwargs):
		""" scan a network host and try to find if it is Pyro enabled.
			This method is meant to be run from a LicornPoolJobThread. """

		assert ltrace('machines', '| %s.process(%s)' % (self.name, mid))

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
					'  %s: find_pyrosys(): %s is not pyro enabled.' % (
						self.name, mid))
				if str(e) != 'connection failed':
					logging.warning2('%s: exception %s for host %s.' % (
						self.name, e, mid))
				LMC.machines.guess_host_type(mid)
			else:
				LMC.machines[mid].system_type = remotesys.get_host_type()
				LMC.machines[mid].status      = remotesys.get_status()
				LMC.machines[mid].system      = remotesys
class IPScannerThread(QueueWorkerThread, network.Pinger):
	""" Evolution of the PingerThread, used to scan hosts on a local network.
		Given an IP address, we will first ping it. If it pongs, we will create
		a corresponding Machine() entry in the MachinesController, then try to
		discover everything possible about the host, by feeding other helper
		threads. """
	#: see :class:`QueueWorkerThread` for details.
	name='IPScanner'
	#: see :class:`QueueWorkerThread` for details.
	number = 0
	#: see :class:`QueueWorkerThread` for details.
	count = 0
	def __init__(self):
		QueueWorkerThread.__init__(self, in_queue=dqueues.ipscans,
			name='ipscanner-%d' % IPScannerThread.number, daemon=True)
		network.Pinger.__init__(self)
	def process(self, mid, *args, **kwargs):
		"""  Ping() an IP and create a Machine() if the IP Pong()s. """

		assert ltrace('machines', '> %s: process(%s)' % (self.name, mid))

		with LMC.machines.lock():
			known_mids = LMC.machines.keys()

		if mid in known_mids or mid in network.local_ip_addresses():
			return

		try:
			self.switch_to(mid)
			self.ping()

		except (exceptions.DoesntExistsException,
				exceptions.TimeoutExceededException), e:

			assert ltrace('machines', '%s: %s.' % (self.name, e))
			pass

		else:
			logging.progress('%s: found online host %s.' % (self.name, mid))

			with LMC.machines.lock():
				LMC.machines.add_machine(mid=mid, status=host_status.ONLINE)

		assert ltrace('machines', '< %s: process(%s)' % (self.name, mid))
