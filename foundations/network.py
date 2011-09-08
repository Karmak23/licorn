# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2
"""

import os, fcntl, struct, socket, platform, re, netifaces
import icmp, ip, time, select

from ping      import PingSocket
from threading import current_thread, RLock

# other foundations imports.
import logging, process, exceptions
from styles    import *
from ltrace	   import ltrace
from ltraces   import *
from constants import distros

def netmask2prefix(netmask):
	return (reduce(lambda x,y: x+y,
		[ bin(int(x)) for x in netmask.split('.')])).count('1')
def interfaces(full=False):
	""" Eventually filter the netifaces.interfaces() result, which contains
		a bit too much results for our own use. """

	assert ltrace(TRACE_NETWORK, '| interfaces(%s)' % full)

	if full:
		return netifaces.interfaces()
	else:
		ifaces = []
		for iface in netifaces.interfaces():
			if iface.startswith('lo') or iface.startswith('gif') \
				or iface.startswith('fw'):
					#print 'skip interface %s' % iface
					continue
			ifaces.append(iface)
		return ifaces
def find_server_Linux(configuration):
	""" return the hostname / IP of our DHCP server. """

	env_server = os.getenv('LICORN_SERVER', None)

	if env_server:
		logging.notice('Using fixed value %s for server (please unset '
			'LICORN_SERVER if you prefer automatic detection via DHCP)' %
				stylize(ST_NAME, env_server))
		return env_server

	if configuration.distro in (distros.LICORN, distros.UBUNTU,
		distros.DEBIAN):
		for argument in process.get_process_cmdline('dhclient'):
			if argument.startswith('/var/lib/dhcp3/dhclient'):
				for try_host in [ x[0] if x[1] == '' else x[1] \
					for x in re.findall('''\s*(?:server-name ['"]([^'"]+)'''
						'''|option dhcp-server-identifier ([^;]*))''',
							open(argument).read()) ]:
					try:
						socket.gethostbyname(try_host)
						return try_host
					except socket.gaierror:
						logging.warning2('''can't resolve host or IP %s.'''
							% try_host)
		return None
	else:
		raise NotImplementedError('find_server() not implemented yet for your distro!')
def find_first_local_ip_address_Linux():
	""" try to find the main external IP address of the current machine (first
		found is THE one). Return None if we can't find any.

		Note: lo is not concerned. """

	interfaces = []
	for range_min, range_max in ((0, 3), (3, 10)):
		for iface_name in ('eth', 'wlan', 'ath', 'br'):
			interfaces.extend([ '%s%s' % (iface_name, x) for x in range(
				range_min, range_max) ])

	assert ltrace(TRACE_NETWORK, '|  find_first_local_ip_address(%s)' % interfaces)

	for interface in interfaces:
		try:
			return netifaces.ifaddresses(interface)[2][0]['addr']
		except:
			continue

	return None
def local_ip_addresses():
	""" try to find the main external IP address of the current machine (first
		found is THE one). Return None if we can't find any.

		Note: lo is not concerned. """

	ifaces = []
	for range_min, range_max in ((0, 3), (3, 10)):
		for iface_name in ('eth', 'wlan', 'ath', 'br'):
			ifaces.extend([ '%s%s' % (iface_name, x) for x in range(
				range_min, range_max) ])

	assert ltrace(TRACE_NETWORK, '|  local_ip_addresses(%s)' % interfaces)

	addresses = []

	for iface in interfaces():
		try:
			addresses.append(netifaces.ifaddresses(iface)[2][0]['addr'])
		except KeyError:
			# the interface has no valid IP assigned
			continue

	return addresses
def local_interfaces_Linux():
	""" Gather any possible information about local interfaces.
		Note: lo is not concerned. """

	interfaces = []
	for range_min, range_max in ((0, 3), (3, 10)):
		for iface_name in ('eth', 'wlan', 'ath', 'br'):
			interfaces.extend([ '%s%s' % (iface_name, x) for x in range(
				range_min, range_max) ])

	assert ltrace(TRACE_NETWORK, '|  find_local_ip_addresses(%s)' % interfaces)

	up_ifaces = []

	for interface in interfaces:
		try:
			up_ifaces.append(interface_infos(interface))
		except:
			continue

	return up_ifaces
def interface_address_Linux(iface_name, iface_address=None):
	""" Get an interface IPv4 adress and return it as a string.

		We dig in /usr/include/linux to find all the values !
			bits/socket.h
			sockios.h
			if.h
		and probably some other files i forgot to list here…

		some reference:
		http://mail.python.org/pipermail/python-list/1999-August/009100.html

		final python 2.6+ version :
		http://code.activestate.com/recipes/439094-get-the-ip-address-associated-with-a-network-inter/

	"""
	raise RuntimeError("please don't use this method aymore")


	assert ltrace(TRACE_NETWORK, '|  interface_address(%s)' % iface_name)

	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

	if iface_address is None:
		# 0x8915 should be IN.SIOCGIFADDR
		return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915,
			struct.pack('256s', iface_name[:15]))[20:24])
	else:
		raise NotImplementedError("iface address setting is not implemented yet.")
def interface_infos_Linux(iface_name):
	""" Get an interface IPv4 adsress and return it as a string.

		We dig in /usr/include/linux to find all the values !
			bits/socket.h
			sockios.h
			if.h
		and probably some other files i forgot to list here…

		some reference:
		http://mail.python.org/pipermail/python-list/1999-August/009100.html

		final python 2.6+ version :
		http://code.activestate.com/recipes/439094-get-the-ip-address-associated-with-a-network-inter/

	"""

	raise RuntimeError("please don't use this method aymore")

	assert ltrace(TRACE_NETWORK, '|  interface_infos_linux(%s)' % iface_name)

	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

	# 0x8915 should be IN.SIOCGIFADDR
	return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915,
		struct.pack('256s', iface_name[:15]))[20:24])
def interface_hostname_Linux(iface_name, iface_address=None):
	""" Get an interface IPv4 hostname and return it as a string.
		same doc as previous function.
	"""

	raise NotImplementedError("TODO !")

	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

	# mapping struct ifreq:
	#	16s: union ifr_ifrn
	#	16s: union ifr_irfu
	ifr = struct.pack('!16s16s', iface_name, '')

	if iface_address is not None:
		raise NotImplementedError("iface address setting is not implemented yet.")

	# 0x8915 should be IN.SIOCGIFADDR, but it is not defined in
	# /usr/lib/python2.4/plat-linux2/IN.py as of 20060823
	res = fcntl.ioctl(s.fileno(), 0x8915 , ifr)

	# 16s == ifrn_name
	#   i == __SOCKADDR_COMMON (sa_) == sa_family_t sa_family
	#  4s == the IP address
	#  8s == padding to complete the struct ifreq
	(ifr_name, sa_family, addr, padding) = struct.unpack('!16si4s8s', res)

	return socket.inet_ntop(socket.AF_INET, addr)
def nameservers_Linux():
	""" return system nameservers present in /etc/resolv.conf."""

	import re
	ns_re = re.compile("^\s*nameserver\s+([-\w\.]+)\s*$")

	for line in open("/etc/resolv.conf"):
		#assert logging.debug("line: " + line)
		ns_matches = ns_re.match(line)
		if  ns_matches:
			yield ns_matches.group(1)
def build_hostname_from_ip(ip):
	return 'UNKNOWN-%s' % ip.replace('.', '-')

platform_system = platform.system()
platform_len = len(platform_system)

# FIXME: this doesn't work as expected. find a way.
for key, value in locals().items():
	if callable(value) and key[-platform_len:] == platform_system:
		# remove _ from the name too.
		exec "%s = %s" % (key[-platform_len-1:], key)

find_server = find_server_Linux
find_first_local_ip_address = find_first_local_ip_address_Linux
def get_local_hostname_Linux():
	""" Try to find the hostname of the localmachine from the first IP
		interface, else return only the IP address if the hostname cannot be
		determined.
	"""
	try:
		ip_addr = find_first_local_ip_address_Linux()
		return socket.gethostbyaddr(ip_addr)[0]
	except socket.herror:
		return ip_addr
get_local_hostname = get_local_hostname_Linux
class Pinger:
	""" This is a rewrite of pyip.Pinger, to:
		- use smaller (and customizable) timeouts,
		- don't use gethostbyaddr() because this makes the whole thing a lot
		slower, and we don't use the hostname anyway in caller processes,
		- make the class thread-safe (using the PID as packet id is not safe
		at all in pool of pinger threads...
		- handle Unreachable hosts (at least), vastly used while scanning
		local networks.
	"""
	#: 0.4 sec is a sane maximum timeout for local network peers. If they don't
	#: respond in this time, a TimeoutException will be raised. Remember, we are
	#: on a LAN. Everything is speedy!
	time_out = 0.4

	#: automatically create a unique identifier for a new Pinger object. This
	#: has to be different from os.getpid() for thread-safe purposes.
	ident_counter = 0
	ident_lock = RLock()
	def __init__(self, addr=None, num=1):
		Pinger.ident_lock.acquire()
		self.ping_ident = Pinger.ident_counter
		Pinger.ident_counter +=1
		Pinger.ident_lock.release()

		if addr:
			self.switch_to(addr, num)
	def reset(self, num):
		""" reset all attributes to zero, to start a new ping session. """
		self.num    = num
		self.last   = 0
		self.sent   = 0
		self.times  = {}
		self.deltas = []
		self.sock   = None
	def switch_to(self, addr, num=1):
		""" reset the current instance attributes and prepare it to ping the new
			:param:`addr` (a hostname or an IPv4 address), :param:`num` times.
		"""
		self.reset(num)

		if self.sock:
			self.sock.socket.close()
			self.sock = None

		self.sock = PingSocket(addr)
		self.addr = addr
	def send_packet(self):
		pkt = icmp.Echo(id=self.ping_ident, seq=self.sent, data='licorn pinger')
		buf = icmp.assemble(pkt)
		self.times[self.sent] = time.time()
		self.sock.sendto(buf)
		self.plen = len(buf)
		self.sent = self.sent + 1
	def recv_packet(self, pkt, when):
		try:
			sent = self.times[pkt.get_seq()]
			del self.times[pkt.get_seq()]
		except KeyError:
			return
		# limit to ms precision
		delta = int((when - sent) * 1000.)
		self.deltas.append(delta)
		if pkt.get_seq() > self.last:
			self.last = pkt.get_seq()
	def ping(self):
		self.last_arrival = time.time()
		while 1:
			if self.sent < self.num:
				self.send_packet()
			elif not self.times and self.last == self.num - 1:
				break
			else:
				now = time.time()
				if self.deltas:
					# Wait no more than 10 times the longest delay so far
					if (now - self.last_arrival) > max(self.deltas) / 1000.:
						#break
						raise exceptions.TimeoutExceededException(
							'Max ping timeout exceeded for host %s' % self.addr)
				else:
					if (now - self.last_arrival) > Pinger.time_out:
						#break
						raise exceptions.TimeoutExceededException(
							'Ping timeout exceeded for host %s' % self.addr)
			self.wait()
	def wait(self):
		start = time.time()
		timeout = 0.05
		while 1:
			rd, wt, er = select.select([self.sock.socket], [], [], timeout)
			if rd:
				# okay to use time here, because select has told us
				# there is data and we don't care to measure the time
				# it takes the system to give us the packet.
				arrival = time.time()
				try:
					pkt, who = self.sock.recvfrom(4096)
				except socket.error:
					continue
				# could also use the ip module to get the payload
				repip = ip.disassemble(pkt)
				try:
					reply = icmp.disassemble(repip.data)
				except ValueError:
					continue
				try:
					if reply.get_id() == self.ping_ident:
						self.recv_packet(reply, arrival)
						self.last_arrival = arrival
				except AttributeError, e:
					if reply.get_embedded_ip().dst == self.addr:
						raise exceptions.DoesntExistException('host %s '
							'unreachable (%s)' % (self.addr, e))
					# else we are receiving a hostunreach for another host,
					# just ignore it and continue waiting.
			timeout = (start + 0.05) - time.time()
			if timeout < 0:
				break
	def get_summary(self):
		dmin = min(self.deltas)
		dmax = max(self.deltas)
		davg = reduce(lambda x, y: x + y, self.deltas) / len(self.deltas)
		sent = self.num
		recv = sent - len(self.times.values())
		loss = float(sent - recv) / float(sent)
		return dmin, davg, dmax, sent, recv, loss

# from http://stackoverflow.com/questions/819355/how-can-i-check-if-an-ip-is-in-a-network-in-python
"""

import socket,struct

def makeMask(n):
	"return a mask of n bits as a long integer"
	return (2L<<n-1) - 1

def dottedQuadToNum(ip):
	"convert decimal dotted quad string to long integer"
	return struct.unpack('L', socket.inet_aton(ip))[0]

def networkMask(ip, bits):
	"Convert a network address to a long integer"
	return dottedQuadToNum(ip) & makeMask(bits)

def addressInNetwork(ip, net):
	"Is an address in a network"
	return ip & net == net

"""
