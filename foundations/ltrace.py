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

trc['foundations']   = 0x0000000f
trc['logging']       = 0x00000001
trc['foundations']   = 0x00000002
trc['objects']       = 0x00000004
trc['options']       = 0x00000008

trc['core']          = 0x000000f0
trc['users']         = 0x00000010
trc['groups']        = 0x00000020
trc['configuration'] = 0x00000040
trc['machines']      = 0x00000080

trc['backends']      = 0x00000f00
trc['ldap']          = 0x00000100
trc['unix']          = 0x00000200

from os import getenv
from time import time, localtime, strftime

def mytime(braces=True):
	""" close http://dev.licorn.org/ticket/46 """
	t = time()
	if braces:
		return '[%s%s]' % (
			strftime('%Y/%d/%m %H:%M:%S', localtime(t)), ('%.4f' % (t%1))[1:])
	else:
		return '%s%s' % (
			strftime('%Y/%d/%m %H:%M:%S', localtime(t)), ('%.4f' % (t%1))[1:])

if getenv('LICORN_TRACE', None) != None:

	import sys

	def ltrace(module, message):
		if  trc[getenv('LICORN_TRACE')] & trc[module] :
			sys.stderr.write('TRACE[%s|%s]: %s\n' % (
				module, mytime(False), message))
else:
	def ltrace(module, message): pass
