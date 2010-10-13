# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

core - The Core API of a Licorn system.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Licensed under the terms of the GNU GPL version 2
"""

# this @@VERSION@@ will be replaced by package maintainers, don't alter it here.
version = '@@VERSION@@'

import os, time, signal, Pyro.core
from licorn.foundations import logging, process
from licorn.foundations.ltrace import ltrace

def alarm_received(dummy1, dummy2):
	logging.error('''daemon didn't wake us in 10 seconds, there is probably '''
		'''a problem with it. Please check %s for errors or contact your '''
		''' system administrator (if it's not you, else you're in trouble).''',
		200)

def connect():
	""" Return remote connexions to all Licorn® core objects. """

	assert ltrace('core', '> connect()')

	from configuration import LicornConfiguration
	localconfig = LicornConfiguration(minimal=True)

	if localconfig.licornd.role == 'server':
		pyroloc = 'PYROLOC://localhost:7766'
	else:
		raise NotImplementedError(
			'Pyro connection in client mode not supported yet.')

	start_time = time.time()

	second_try=False
	while True:
		# this while seems infinite but is not.
		#   - on first succeeding connection, it will break.
		#   - on pyro exception (can't connect), the daemon will be forked and
		#     signals will be setup, to wait for the daemon to come up.
		#     - if daemons comes up, the loop restarts and should break because
		try:
			configuration = Pyro.core.getAttrProxyForURI(
				"%s/configuration" % pyroloc)
			configuration.noop()
			assert ltrace('core', '  connect(): main configuration object connected.')
			break
		except Pyro.errors.ProtocolError, e:
			if second_try:
				logging.error('''Can't connect to the daemon, but it has been'''
					''' successfully launched. I suspect you're in trouble '''
					'''(was: %s)''' % e, 199)

			logging.warning2('''can't connect to Licorn® daemon, trying to '''
				'''launch it…''')

			# the daemon will fork in the background and the call will return
			# nearly immediately.
			process.fork_licorn_daemon(pid_to_wake=os.getpid())

			# wait to receive SIGUSR1 from the daemon when it's ready. On loaded
			# system with lots of groups, this can take a while, but it will
			# never take more than 10 seconds because of the daemon's
			# multithreaded nature, so we setup a signal to wake us
			# inconditionnaly in 10 seconds and report an error if the daemon
			# hasn't waked us in this time.
			signal.signal(signal.SIGALRM, alarm_received)
			signal.alarm(10)

			# cancel the alarm if USR1 received.
			signal.signal(signal.SIGUSR1, lambda x,y: signal.alarm(0))

			logging.notice('waiting for daemon to come up…')

			# ALARM or USR1 will break the pause()
			signal.pause()
			second_try=True
	assert ltrace('core',
		'  connect(): connecting the rest of remote objects.')

	# connection is OK, let's get all other objects connected, and pull
	# them back to the calling process.
	users      = Pyro.core.getAttrProxyForURI("%s/users" % pyroloc)
	groups     = Pyro.core.getAttrProxyForURI("%s/groups" % pyroloc)
	profiles   = Pyro.core.getAttrProxyForURI("%s/profiles" % pyroloc)
	privileges = Pyro.core.getAttrProxyForURI("%s/privileges" % pyroloc)
	keywords   = Pyro.core.getAttrProxyForURI("%s/keywords" % pyroloc)
	machines   = Pyro.core.getAttrProxyForURI("%s/machines" % pyroloc)

	assert ltrace('timings', '@core.connect(): %.4fs' % (time.time()-start_time))
	del start_time

	assert ltrace('core', '< connect()')

	return (configuration, users, groups, profiles, privileges,
		keywords, machines)
