# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ltrace - light procedural trace (debug only)

	set LICORN_TRACE={all,configuration,core,...} and watch your terminal
	flooded with information.


Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.

"""

#
# WARNING: please do not import anything from licorn here.
#

trc={}
trc['all']           = 0xffffffff
trc['none']          = 0x00000000

trc['foundations']   = 0x000000ff
trc['logging']       = 0x00000001
trc['foundations']   = 0x00000002
trc['objects']       = 0x00000004
trc['options']       = 0x00000008

trc['core']          = 0x0000ff00
trc['users']         = 0x00000100
trc['groups']        = 0x00000200
trc['configuration'] = 0x00000400
trc['machines']      = 0x00000800
trc['internet']      = 0x00000f00

trc['backends']      = 0x00ff0000
trc['ldap']          = 0x00010000
trc['unix']          = 0x00020000

trc['daemon']        = 0xff000000
trc['master']        = 0x01000000
trc['inotifier']     = 0x02000000
trc['aclchecker']    = 0x04000000
trc['cache']         = 0x08000000
trc['crawler']       = 0x0f000000

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
