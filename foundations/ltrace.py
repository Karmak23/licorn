# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ltrace - light procedural trace (debug only)

	set environment variable LICORN_TRACE={all,configuration,core,…} and
	watch your terminal	flooded with information. You can combine values with
	pipes:
		export LICORN_TRACE=all
		export LICORN_TRACE=configuration
		export LICORN_TRACE="configuration|ldap"
		export LICORN_TRACE="users|backends|plugins"
		export LICORN_TRACE="groups|ldap"
		export LICORN_TRACE="machines|dnsmasq"
		(and so on…)

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

from os   import getenv
from time import time, localtime, strftime

# WARNING: please do not import anything from licorn here, except styles.
from styles import *

trc={}
trc['all']           = 0xffffffffffffffffffff
trc['none']          = 0x00000000000000000000
trc['special']       = 0xf0000000000000000000
trc['timings']       = 0x10000000000000000000

trc['foundations']   = 0x0000000000000000ffff
trc['logging']       = 0x00000000000000000001
trc['base']          = 0x00000000000000000002
trc['options']       = 0x00000000000000000004
trc['objects']       = 0x00000000000000000008
trc['readers']       = 0x00000000000000000010
trc['process']       = 0x00000000000000000020
trc['fsapi']         = 0x00000000000000000040
trc['network']       = 0x00000000000000000080
trc['dbus']          = 0x00000000000000000100

trc['core']          = 0x000000000000ffff0000
trc['configuration'] = 0x00000000000000010000
trc['users']         = 0x00000000000000020000
trc['groups']        = 0x00000000000000040000
trc['profiles']      = 0x00000000000000080000
trc['machines']      = 0x00000000000000100000
trc['internet']      = 0x00000000000000200000
trc['privileges']    = 0x00000000000000400000
trc['keywords']      = 0x00000000000000800000
trc['system']        = 0x00000000000001000000
trc['messaging']     = 0x00000000000002000000

trc['backends']      = 0x00000000ffff00000000
trc['ldap']          = 0x00000000000100000000
trc['unix']          = 0x00000000000200000000
trc['dnsmasq']       = 0x00000000000400000000

trc['daemon']        = 0x0000ffff000000000000
trc['master']        = 0x00000001000000000000
trc['inotifier']     = 0x00000002000000000000
trc['aclchecker']    = 0x00000004000000000000
trc['cache']         = 0x00000008000000000000
trc['crawler']       = 0x00000010000000000000
trc['cmdlistener']   = 0x00000020000000000000
# the next 2 are identical, this is meant to be, for syntaxic eases
trc['thread']        = 0x00000040000000000000
trc['threads']       = 0x00000040000000000000
trc['wmi']           = 0x00000080000000000000
trc['rwi']           = 0x00000100000000000000

# no 0xffff here, the first 'f' is for timings and special cases
trc['interfaces']    = 0x0fff0000000000000000
trc['cli']           = 0x00ff0000000000000000
trc['add']           = 0x00010000000000000000
trc['mod']           = 0x00020000000000000000
trc['del']           = 0x00040000000000000000
trc['chk']           = 0x00080000000000000000
trc['get']           = 0x00100000000000000000

def dump_one(obj_to_dump, long_output=False):
	try:
		print obj_to_dump.dump_status(long_output=long_output)
	except AttributeError:
		if long_output:
			print '%s %s:\n%s' % (
				str(obj_to_dump.__class__),
				stylize(ST_NAME, obj_to_dump.__name__),
				'\n'.join(['%s(%s): %s' % (
					stylize(ST_ATTR, key),
					type(getattr(obj_to_dump, key)),
					getattr(obj_to_dump, key))
						for key in dir(obj_to_dump)]))
		else:
			print '%s %s: %s' % (
				str(obj_to_dump.__class__),
				stylize(ST_NAME, obj_to_dump.__name__),
				[ key for key \
					in dir(obj_to_dump)])
def dump(*args, **kwargs):
	for arg in args:
		dump_one(arg)
	for key, value in kwargs:
		dump_one(value)
def fulldump(*args, **kwargs):
	for arg in args:
		dump_one(arg, True)
	for key, value in kwargs:
		dump_one(value, True)
def mytime():
	""" close http://dev.licorn.org/ticket/46 """
	t = time()
	return '[%s%s]' % (
		strftime('%Y/%d/%m %H:%M:%S', localtime(t)), ('%.4f' % (t%1))[1:])

if getenv('LICORN_TRACE', None) != None:

	import sys
	ltrace_level = 0
	for env_mod in getenv('LICORN_TRACE').split('|'):
		substracts = env_mod.split('^')
		ltrace_level |= trc[substracts[0]]
		for sub_env_mod in substracts[1:]:
			ltrace_level ^= trc[sub_env_mod]

	def ltrace(module, message):
		if  ltrace_level & trc[module]:
			sys.stderr.write('%s %s: %s\n' % (
				stylize(ST_COMMENT, 'TRACE%s' % mytime()),
				module, message))
		return True
else:
	def ltrace(a, b):
		return True
