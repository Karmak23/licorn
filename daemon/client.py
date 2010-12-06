# -*- coding: utf-8 -*-
"""
Licorn Daemon client part.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""
import os, sys, time
import Pyro.core

from licorn.foundations           import logging, exceptions
from licorn.foundations           import process, network
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace, dump, fulldump
from licorn.foundations.constants import host_status
from licorn.foundations.thread    import _threads, _thcount

from licorn.core   import LicornMasterController, LMC
from licorn.daemon import dthreads

ServerLMC = LicornMasterController('ServerLMC')

def thread_greeter():

	ServerLMC.connect()

	import licorn.daemon.cmdlistener
	licorn.daemon.cmdlistener.LicornPyroValidator.server_addresses = \
		ServerLMC.configuration.network.local_ip_addresses()

	logging.info('Successfully announced ourselves to our server %s.' %
		stylize(ST_ADDRESS, '%s:%s' % (
			LMC.configuration.server_main_address,
			LMC.configuration.licornd.pyro.port)))

	# NO NEED to do this, the server updates automatically the status if the
	# previous connection succeeds.
	#ServerLMC.machines.update_status(network.local_ip_addresses(),
	#	host_status.ONLINE)
