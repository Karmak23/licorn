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
from licorn.foundations         import logging, exceptions, styles

from licorn.core                import configuration

from licorn.daemon.core         import dname

"""
 TODO: publish our role with MDNS / Bonjour / Avahi

	if we are client, wait forever for a server.

	if we are a server, advertise us on the network.

"""

class ClientSyncer(LicornThread) :
	pass

class ServerSyncer(LicornThread) :
	pass

