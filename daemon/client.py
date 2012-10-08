# -*- coding: utf-8 -*-
"""
Licorn Daemon client part.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import Pyro
from threading import current_thread

from licorn.foundations           import settings, logging
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core import LicornMasterController, LMC

ServerLMC = LicornMasterController(master=False)

def client_hello():

	assert ltrace(TRACE_CLIENT, '| thread_greeter()')

	# done in daemon main
	#ServerLMC.connect()

	#print '>> client_hello LMC.system', LMC.system
	#print ('>> client_hello ServerLMC.system', ServerLMC.system,
	#	'addresses', ServerLMC.system.local_ip_addresses())

	from licorn.daemon.cmdlistener import LicornPyroValidator

	LicornPyroValidator.server_addresses = ServerLMC.system.local_ip_addresses()

	ServerLMC.system.hello_from(LMC.system.local_ip_addresses())

	logging.notice('%s: %s to Licorn® server %s.' % (
						current_thread().name,
						stylize(ST_OK, 'Successfully connected'),
						stylize(ST_ADDRESS, 'pyro://%s:%s' % (
							settings.server_main_address,
							settings.pyro.port))))

	# NO NEED to do this, the server updates automatically the status if the
	# previous connection succeeds.
	#ServerLMC.machines.update_status(network.local_ip_addresses(),
	#	host_status.ONLINE)
def client_goodbye():
	try:
		ServerLMC.system.goodbye_from(LMC.system.local_ip_addresses())
		ServerLMC.release()

	except Pyro.errors.PyroError, e:
		logging.warning('%s: exception %s encountered while shutting down.' % (
			current_thread().name, e))

def server_shutdown(remote_interfaces):
	from licorn.daemon.cmdlistener import LicornPyroValidator

	if remote_interfaces == LicornPyroValidator.server_addresses:
		ServerLMC.release()
		logging.notice('%s: %s to Licorn® server %s.' % (
			current_thread().name,
			stylize(ST_BAD, 'Closed connection'),
			stylize(ST_ADDRESS, 'pyro://%s:%s' % (settings.server_main_address,
													settings.pyro.port))))
	else:
		#lprint('>> other server shutdown')
		pass
def server_reconnect(remote_interfaces):
	from licorn.daemon.cmdlistener import LicornPyroValidator

	if remote_interfaces == LicornPyroValidator.server_addresses:
		ServerLMC = LicornMasterController(master=False)
		logging.notice('%s: %s to Licorn® server %s.' % (
			current_thread().name,
			stylize(ST_OK, 'Successfully reconnected'),
			stylize(ST_ADDRESS, 'pyro://%s:%s' % (settings.server_main_address,
													settings.pyro.port))))

__all__ = ('ServerLMC',
			'client_hello', 'client_goodbye',
			'server_shutdown', 'server_reconnect' )
