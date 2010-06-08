# -*- coding: utf-8 -*-
"""
Licorn core - http://dev.licorn.org/documentation/core

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2

"""

from licorn import exceptions

def iface_address(iface_name, iface_address = None):
	""" Get an interface IPv4 adress and return it as a string. 
	
	We dig in /usr/include/linux to find all the values !
		bits/socket.h
		sockios.h
		if.h
	and probably some other files i forgot to list here...

	a similar way to do this (which i don't like), without struct:
	http://mail.python.org/pipermail/python-list/1999-August/009100.html
		
	
		struct if_settings
		{
		    unsigned int type;      /* Type of physical device or protocol */
		    unsigned int size;      /* Size of the data allocated by the caller */
		    union {
		        /* {atm/eth/dsl}_settings anyone ? */
		        raw_hdlc_proto          *raw_hdlc;
		        cisco_proto             *cisco;
		        fr_proto                *fr;
		        fr_proto_pvc            *fr_pvc;
		        fr_proto_pvc_info       *fr_pvc_info;

		        /* interface settings */
		        sync_serial_settings    *sync;
		        te1_settings            *te1;
		    } ifs_ifsu;
		};

		#define IFNAMSIZ        16

		struct ifmap
		{
		    unsigned long mem_start;
		    unsigned long mem_end;
		    unsigned short base_addr;
		    unsigned char irq;
		    unsigned char dma;
		    unsigned char port;
		    /* 3 bytes spare */
		};

		struct ifreq
		{
		#define IFHWADDRLEN     6
		    union
		    {
		        char    ifrn_name[IFNAMSIZ];            /* if name, e.g. "en0" */
		    } ifr_ifrn;

		    union {
		        struct  sockaddr ifru_addr;
		        struct  sockaddr ifru_dstaddr;
		        struct  sockaddr ifru_broadaddr;
		        struct  sockaddr ifru_netmask;
		        struct  sockaddr ifru_hwaddr;
		        short   ifru_flags;
		        int     ifru_ivalue;
		        int     ifru_mtu;
		        struct  ifmap ifru_map;
		        char    ifru_slave[IFNAMSIZ];   /* Just fits the size */
		        char    ifru_newname[IFNAMSIZ];
		        char *  ifru_data;
		        struct  if_settings ifru_settings;
		    } ifr_ifru;
		};

		typedef unsigned short int sa_family_t;

		#define __SOCKADDR_COMMON(sa_prefix) \
			sa_family_t sa_prefix##family

		struct sockaddr
		{
			__SOCKADDR_COMMON (sa_);    /* Common data: address family and length.  */
			char sa_data[14];           /* Address data.  */
		};
		
	"""

	import fcntl, struct, socket
	
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
def iface_hostname(iface_name, iface_address = None):
	""" Get an interface IPv4 hostname and return it as a string. 
		same doc as previous function.
	"""

	raise NotImplementedError("TODO !")

	import fcntl, struct, socket
	
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
def nameservers():
	""" return system nameservers present in /etc/resolv.conf."""
	
	import re
	ns_re = re.compile("^\s*nameserver\s+([-\w\.]+)\s*$")
	
	for line in open("/etc/resolv.conf"):
		#logging.debug("line: " + line)
		ns_matches = ns_re.match(line)
		if  ns_matches:
			yield ns_matches.group(1)
			
