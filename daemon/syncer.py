# -*- coding: utf-8 -*-
"""
Licorn Daemon Syncer internals.
Syncer is responsible of messaging and synchronization between 2 licorn machines.
It Handles a journal (as in "journaling") and ensure all peers get and execute
every part of it (else it handles rollback, etc).

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

from licorn.foundations.objects import LicornThread

"""
 TODO: publish our role with MDNS / Bonjour / Avahi

	if we are client, wait forever for a server.

	if we are a server, advertise us on the network.


PUBLISHING A SERVICE
--------------------

import Zeroconf
import socket

server = Zeroconf.Zeroconf()

# Get local IP address
local_ip = socket.gethostbyname(socket.gethostname())
local_ip = socket.inet_aton(local_ip)

svc1 = Zeroconf.ServiceInfo('_durus._tcp.local.',
                              'Database 1._durus._tcp.local.',
                              address = local_ip,
                              port = 2972,
                              weight = 0, priority=0,
                              properties = {'description':
                                            'Departmental server'}
                             )
server.registerService(svc1)


DISCOVERING SERVICES
--------------------

import Zeroconf

class MyListener(object):
    def removeService(self, server, type, name):
        print "Service", repr(name), "removed"

    def addService(self, server, type, name):
        print "Service", repr(name), "added"
        # Request more information about the service
        info = server.getServiceInfo(type, name)
        print 'Additional info:', info

if __name__ == '__main__':
    server = Zeroconf.Zeroconf()
    listener = MyListener()
    browser = Zeroconf.ServiceBrowser(server, "_durus._tcp.local.", listener)

"""

class ClientSyncer(LicornThread):
	pass

class ServerSyncer(LicornThread):
	pass

