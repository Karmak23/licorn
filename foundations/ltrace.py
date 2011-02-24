# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ltrace - light procedural trace (debug only)

	set environment variable LICORN_TRACE={all,configuration,core,…} and
	watch your terminal	flooded with information. You can combine values with
	pipes:
		export LICORN_TRACE=all
		export LICORN_TRACE=configuration
		export LICORN_TRACE="configuration|openldap"
		export LICORN_TRACE="users|backends|plugins"
		export LICORN_TRACE="groups|openldap"
		export LICORN_TRACE="machines|dnsmasq"
		(and so on…)

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
from sys  import stderr
from os   import getenv
from time import time, localtime, strftime

# WARNING: please do not import anything from licorn here, except styles.
from styles import *

trc={}

trc['all']           = 0xffffffffffffffffffffffff
trc['none']          = 0x000000000000000000000000
trc['special']       = 0xf00000000000000000000000
trc['timings']       = 0x100000000000000000000000

trc['foundations']   = 0x00000000000000000000ffff
trc['logging']       = 0x000000000000000000000001
trc['base']          = 0x000000000000000000000002
trc['options']       = 0x000000000000000000000004
trc['objects']       = 0x000000000000000000000008
trc['readers']       = 0x000000000000000000000010
trc['process']       = 0x000000000000000000000020
trc['fsapi']         = 0x000000000000000000000040
trc['network']       = 0x000000000000000000000080
trc['dbus']          = 0x000000000000000000000100
trc['messaging']     = 0x000000000000000000000200
# the following two are the same, for syntax comfort
trc['check']         = 0x000000000000000000000400
trc['checks']        = 0x000000000000000000000400


trc['core']          = 0x0000000000000000ffff0000
trc['configuration'] = 0x000000000000000000010000
trc['users']         = 0x000000000000000000020000
trc['groups']        = 0x000000000000000000040000
trc['profiles']      = 0x000000000000000000080000
trc['machines']      = 0x000000000000000000100000
trc['internet']      = 0x000000000000000000200000
trc['privileges']    = 0x000000000000000000400000
trc['keywords']      = 0x000000000000000000800000
trc['system']        = 0x000000000000000001000000

trc['backends']      = 0x000000000000ffff00000000
trc['openldap']      = 0x000000000000000100000000
trc['shadow']        = 0x000000000000000200000000
trc['dnsmasq']       = 0x000000000000000400000000

trc['extensions']    = 0x00000000ffff000000000000
trc['postfix']       = 0x000000000001000000000000
trc['apache2']       = 0x000000000002000000000000
trc['caldavd']       = 0x000000000004000000000000
trc['samba']         = 0x000000000008000000000000
trc['courier']       = 0x000000000010000000000000
trc['openssh']       = 0x000000000020000000000000
trc['volumes']       = 0x000000000040000000000000
trc['rdiffbackup']   = 0x000000000080000000000000
trc['squid']         = 0x000000000100000000000000
trc['powermgmt']     = 0x000000000200000000000000
trc['gloop']         = 0x000000000400000000000000


trc['daemon']        = 0x0000ffff0000000000000000
trc['master']        = 0x000000010000000000000000
trc['inotifier']     = 0x000000020000000000000000
trc['aclchecker']    = 0x000000040000000000000000
trc['cache']         = 0x000000080000000000000000
trc['crawler']       = 0x000000100000000000000000
trc['cmdlistener']   = 0x000000200000000000000000
# the next 2 are identical, this is meant to be, for syntaxic eases
trc['thread']        = 0x000000400000000000000000
trc['threads']       = 0x000000400000000000000000
trc['http']          = 0x000000800000000000000000
trc['rwi']           = 0x000001000000000000000000
trc['client']        = 0x000002000000000000000000
trc['interactor']    = 0x000004000000000000000000

# no 0xffff here, the first 'f' is for timings and special cases
trc['interfaces']    = 0x0fff00000000000000000000
trc['cli']           = 0x00ff00000000000000000000
trc['add']           = 0x000100000000000000000000
trc['mod']           = 0x000200000000000000000000
trc['del']           = 0x000400000000000000000000
trc['chk']           = 0x000800000000000000000000
trc['get']           = 0x001000000000000000000000
trc['argparser']     = 0x002000000000000000000000
trc['wmi']           = 0x004000000000000000000000


trc['highlevel']     = (trc['all'] ^ trc['foundations']
						^ trc['thread'] ^ trc['machines'] ^ trc['inotifier'])
trc['high']          = trc['highlevel']
trc['standard']      = trc['highlevel']
trc['std']           = trc['highlevel']

def dump_one(obj_to_dump, long_output=False):
	try:
		print obj_to_dump.dump_status(long_output=long_output)
	except AttributeError:
		if long_output:
			print '%s %s:\n%s' % (
				str(obj_to_dump.__class__),
				stylize(ST_NAME, obj_to_dump.name),
				'\n'.join(['%s(%s): %s' % (
					stylize(ST_ATTR, key),
					type(getattr(obj_to_dump, key)),
					getattr(obj_to_dump, key))
						for key in dir(obj_to_dump)]))
		else:
			print '%s %s: %s' % (
				str(obj_to_dump.__class__),
				stylize(ST_NAME, obj_to_dump.name),
				[ key for key in dir(obj_to_dump)])
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

# the new LTRACE env variable takes precedence, then we try the old one
# LICORN_TRACE.
new_trace = getenv('LTRACE', None)
old_trace = getenv('LICORN_TRACE', None)

if new_trace != None or old_trace != None:

	if new_trace:
		env_trace = new_trace
	else:
		env_trace = old_trace

	import sys
	ltrace_level = 0
	maxwidth = 0

	for key in trc.keys():
		if len(key) > maxwidth:
			maxwidth = len(key)

	for env_mod in env_trace.split('|'):
		substracts = env_mod.split('^')
		ltrace_level |= trc[substracts[0]]
		for sub_env_mod in substracts[1:]:
			ltrace_level ^= trc[sub_env_mod]

	def ltrace(module, message):
		if  ltrace_level & trc[module]:
			stderr.write('%s %s: %s\n' % (
				stylize(ST_COMMENT, '   %s' % mytime()),
				stylize(ST_DEBUG, 'TRACE  ' + module.rjust(maxwidth)), message))
		return True

	def insert_ltrace():
		# in trace mode, use python interpreter directly to avoid the -OO
		# inserted in all our executables.
		# NOTE: don't use assert ltrace here, this will fail to display the
		# message on first launch, where -OO is active.
		stderr.write('Licorn®: %s for %s\n' % (
					stylize(ST_IMPORTANT, 'LTRACE enabled'),
					stylize(ST_COMMENT, env_trace)
				)
			)

		return ['python']
else:
	def ltrace(a, b):
		return True
	def insert_ltrace():
		return []
