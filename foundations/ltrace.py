# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ltrace - light procedural trace (debug only)

	set environment variable LICORN_TRACE={all,configuration,core,...} and
	watch your terminal	flooded with information. You can combine values with
	pipes:
		export LICORN_TRACE=all
		export LICORN_TRACE=configuration
		export LICORN_TRACE="configuration|ldap"
		export LICORN_TRACE="users|backends|plugins"
		export LICORN_TRACE="groups|ldap"
		export LICORN_TRACE="machines|dnsmasq"
		(and so on...)

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

#
# WARNING: please do not import anything from licorn here.
#

trc={}
trc['all']           = 0xffffffffffffffff
trc['none']          = 0x0000000000000000

trc['foundations']   = 0x00000000000000ff
trc['logging']       = 0x0000000000000001
trc['foundations']   = 0x0000000000000002
trc['objects']       = 0x0000000000000004
trc['options']       = 0x0000000000000008
trc['readers']       = 0x0000000000000010
trc['process']       = 0x0000000000000020
trc['fsapi']         = 0x0000000000000040

trc['core']          = 0x000000000000ff00
trc['configuration'] = 0x0000000000000100
trc['users']         = 0x0000000000000200
trc['groups']        = 0x0000000000000400
trc['profiles']      = 0x0000000000000800
trc['machines']      = 0x0000000000001000
trc['internet']      = 0x0000000000002000

trc['backends']      = 0x0000000000ff0000
trc['ldap']          = 0x0000000000010000
trc['unix']          = 0x0000000000020000

trc['plugins']       = 0x00000000ff000000
trc['dnsmasq']       = 0x0000000001000000

trc['daemon']        = 0x000000ff00000000
trc['master']        = 0x0000000100000000
trc['inotifier']     = 0x0000000200000000
trc['aclchecker']    = 0x0000000400000000
trc['cache']         = 0x0000000800000000
trc['crawler']       = 0x0000001000000000
trc['thread']        = 0x0000002000000000
trc['wmi']           = 0x0000004000000000

trc['interfaces']    = 0x00ffff0000000000
trc['cli']           = 0x0000ff0000000000
trc['add']           = 0x0000010000000000
trc['mod']           = 0x0000020000000000
trc['del']           = 0x0000040000000000
trc['chk']           = 0x0000080000000000
trc['get']           = 0x0000100000000000


from os   import getenv
from time import time, localtime, strftime

import styles

def mytime():
	""" close http://dev.licorn.org/ticket/46 """
	t = time()
	return '[%s%s]' % (
		strftime('%Y/%d/%m %H:%M:%S', localtime(t)), ('%.4f' % (t%1))[1:])

if getenv('LICORN_TRACE', None) != None:

	import sys

	# TODO: make this clever, by understanding '^' (binary exclusions) too.
	ltrace_level = 0
	for env_mod in getenv('LICORN_TRACE').split('|'):
		ltrace_level |= trc[env_mod]

	def ltrace(module, message):
		if  ltrace_level & trc[module] :
			sys.stderr.write('%s %s: %s\n' % (
				styles.stylize(styles.ST_COMMENT, 'TRACE%s' % mytime()),
				module, message))
else:
	def ltrace(module, message): pass
