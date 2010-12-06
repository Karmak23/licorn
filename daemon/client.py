# -*- coding: utf-8 -*-
"""
Licorn Daemon client part.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

from licorn.foundations           import logging
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace

from licorn.core   import LicornMasterController, LMC

ServerLMC = LicornMasterController('ServerLMC')

def thread_greeter():

	assert ltrace('client', '| thread_greeter()')

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
