# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ltrace levels - in a dedicated file to be able to import *

Copyright (C) 2011 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

class _ltrace_level(long):
	""" See http://stackoverflow.com/questions/3238350/subclassing-int-in-python for details. """
	def __new__(cls, value, name):
		inst = super(_ltrace_level, cls).__new__(cls, value)
		inst.name = name
		return inst

TRACE_ALL           = _ltrace_level(0xfffffffffffffffffffffffff, 'all')
TRACE_NONE          = _ltrace_level(0x0000000000000000000000000, 'none')
TRACE_SPECIAL       = _ltrace_level(0xff00000000000000000000000, 'special')
TRACE_TIMINGS       = _ltrace_level(0x0100000000000000000000000, 'timings')
TRACE_GC            = _ltrace_level(0x0200000000000000000000000, 'gc')
# the next 2 are identical, this is meant to be, for syntaxic eases
TRACE_LOCK          = _ltrace_level(0x0400000000000000000000000, 'locks')
TRACE_LOCKS         = _ltrace_level(0x0400000000000000000000000, 'locks')
# the next 2 are identical, this is meant to be, for syntaxic eases
TRACE_EVENT         = _ltrace_level(0x0800000000000000000000000, 'events')
TRACE_EVENTS        = _ltrace_level(0x0800000000000000000000000, 'events')


TRACE_FOUNDATIONS   = _ltrace_level(0x000000000000000000000ffff, 'foundations')
TRACE_LOGGING       = _ltrace_level(0x0000000000000000000000001, 'logging')
TRACE_BASE          = _ltrace_level(0x0000000000000000000000002, 'base')
TRACE_OPTIONS       = _ltrace_level(0x0000000000000000000000004, 'options')
TRACE_OBJECTS       = _ltrace_level(0x0000000000000000000000008, 'objects')
TRACE_READERS       = _ltrace_level(0x0000000000000000000000010, 'readers')
TRACE_PROCESS       = _ltrace_level(0x0000000000000000000000020, 'process')
TRACE_FSAPI         = _ltrace_level(0x0000000000000000000000040, 'fsapi')
TRACE_NETWORK       = _ltrace_level(0x0000000000000000000000080, 'network')
TRACE_DBUS          = _ltrace_level(0x0000000000000000000000100, 'dbus')
TRACE_MESSAGING     = _ltrace_level(0x0000000000000000000000200, 'messaging')
# the following two are the same, for syntax comfort
TRACE_CHECK         = _ltrace_level(0x0000000000000000000000400, 'checks')
TRACE_CHECKS        = _ltrace_level(0x0000000000000000000000400, 'checks')


TRACE_CORE          = _ltrace_level(0x00000000000000000ffff0000, 'core')
TRACE_CONFIGURATION = _ltrace_level(0x0000000000000000000010000, 'configuration')
TRACE_USERS         = _ltrace_level(0x0000000000000000000020000, 'users')
TRACE_GROUPS        = _ltrace_level(0x0000000000000000000040000, 'groups')
TRACE_PROFILES      = _ltrace_level(0x0000000000000000000080000, 'profiles')
TRACE_MACHINES      = _ltrace_level(0x0000000000000000000100000, 'machines')
TRACE_INTERNET      = _ltrace_level(0x0000000000000000000200000, 'internet')
TRACE_PRIVILEGES    = _ltrace_level(0x0000000000000000000400000, 'privileges')
TRACE_KEYWORDS      = _ltrace_level(0x0000000000000000000800000, 'keywords')
TRACE_SYSTEM        = _ltrace_level(0x0000000000000000001000000, 'system')


TRACE_BACKENDS      = _ltrace_level(0x0000000000000ffff00000000, 'backends')
TRACE_OPENLDAP      = _ltrace_level(0x0000000000000000100000000, 'openldap')
TRACE_SHADOW        = _ltrace_level(0x0000000000000000200000000, 'shadow')
TRACE_DNSMASQ       = _ltrace_level(0x0000000000000000400000000, 'dnsmasq')


TRACE_EXTENSIONS    = _ltrace_level(0x000000000ffff000000000000, 'extensions')
TRACE_POSTFIX       = _ltrace_level(0x0000000000001000000000000, 'postfix')
TRACE_APACHE2       = _ltrace_level(0x0000000000002000000000000, 'apache2')
TRACE_CALDAVD       = _ltrace_level(0x0000000000004000000000000, 'caldavd')
TRACE_SAMBA         = _ltrace_level(0x0000000000008000000000000, 'samba')
TRACE_COURIER       = _ltrace_level(0x0000000000010000000000000, 'courier')
TRACE_OPENSSH       = _ltrace_level(0x0000000000020000000000000, 'openssh')
TRACE_VOLUMES       = _ltrace_level(0x0000000000040000000000000, 'volumes')
TRACE_RDIFFBACKUP   = _ltrace_level(0x0000000000080000000000000, 'rdiffbackup')
TRACE_SQUID         = _ltrace_level(0x0000000000100000000000000, 'squid')
TRACE_POWERMGMT     = _ltrace_level(0x0000000000200000000000000, 'powermgmt')
TRACE_GLOOP         = _ltrace_level(0x0000000000400000000000000, 'gloop')


TRACE_DAEMON        = _ltrace_level(0x00000ffff0000000000000000, 'daemon')
TRACE_MASTER        = _ltrace_level(0x0000000010000000000000000, 'master')
TRACE_INOTIFIER     = _ltrace_level(0x0000000020000000000000000, 'inotifier')
TRACE_ACLCHECKER    = _ltrace_level(0x0000000040000000000000000, 'aclchecker')
TRACE_CACHE         = _ltrace_level(0x0000000080000000000000000, 'cache')
TRACE_CRAWLER       = _ltrace_level(0x0000000100000000000000000, 'crawler')
TRACE_CMDLISTENER   = _ltrace_level(0x0000000200000000000000000, 'cmdlistener')
# the next 2 are identical, this is meant to be, for syntaxic eases
TRACE_THREAD        = _ltrace_level(0x0000000400000000000000000, 'threads')
TRACE_THREADS       = _ltrace_level(0x0000000400000000000000000, 'threads')
TRACE_HTTP          = _ltrace_level(0x0000000800000000000000000, 'http')
TRACE_RWI           = _ltrace_level(0x0000001000000000000000000, 'rwi')
TRACE_CLIENT        = _ltrace_level(0x0000002000000000000000000, 'client')
TRACE_INTERACTOR    = _ltrace_level(0x0000004000000000000000000, 'interactor')


# no 0x0ffff here, the first 'f' is for timings and special cases
TRACE_INTERFACES    = _ltrace_level(0x00fff00000000000000000000, 'interfaces')
TRACE_CLI           = _ltrace_level(0x000ff00000000000000000000, 'cli')
TRACE_ADD           = _ltrace_level(0x0000100000000000000000000, 'add')
TRACE_MOD           = _ltrace_level(0x0000200000000000000000000, 'mod')
TRACE_DEL           = _ltrace_level(0x0000400000000000000000000, 'del')
TRACE_CHK           = _ltrace_level(0x0000800000000000000000000, 'chk')
TRACE_GET           = _ltrace_level(0x0001000000000000000000000, 'get')
TRACE_ARGPARSER     = _ltrace_level(0x0002000000000000000000000, 'argparser')
TRACE_WMI           = _ltrace_level(0x0004000000000000000000000, 'wmi')


TRACE_HIGHLEVEL     = _ltrace_level(TRACE_ALL
						- TRACE_FOUNDATIONS
						- TRACE_THREAD
						- TRACE_MACHINES
						- TRACE_INOTIFIER, 'highlevel')
TRACE_HIGH          = TRACE_HIGHLEVEL
TRACE_STANDARD      = TRACE_HIGHLEVEL
TRACE_STD           = TRACE_HIGHLEVEL

# NOTE: keep calling it traces with a 's', because we loop 'trace_'* variables
# names to find the max width.
TRACES_MAXWIDTH = 0

for key, value in locals().items():
	if key.startswith('trace_'):
		if len(value.name) > TRACES_MAXWIDTH:
			TRACES_MAXWIDTH = len(value.name)

def ltrace_str_to_int(string_trace):

	ltrace_level = 0

	for level in string_trace.split('|'):
		substracts = level.split('^')
		ltrace_level |= globals()['TRACE_' + substracts[0].upper()]
		for sub_env_mod in substracts[1:]:
			ltrace_level -= globals()['TRACE_' + sub_env_mod.upper()]

	return ltrace_level
