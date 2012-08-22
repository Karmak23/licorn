# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

constants - all enums for the rest of the world.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2
"""

import stat

# ============================================================== licorn imports
import styles
from styles     import *
from base       import EnumDict

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

roles = EnumDict('roles', from_dict={
		'UNSET' : 1,
		'SERVER': 2,
		'CLIENT': 3,
	})

priorities = EnumDict('service_priorities', from_dict={
		'LOW'    : 20,
		'NORMAL' : 10,
		'HIGH'   : 0,
	})

# relationships between users and groups
relation = EnumDict('relation')
relation.NO_MEMBERSHIP = 0
relation.GUEST         = 1
relation.MEMBER        = 2
relation.RESPONSIBLE   = 3
relation.PRIVILEGE     = 4
relation.SYSMEMBER     = 5

# verbose levels for options and logging.*
verbose = EnumDict('verbose')
verbose.QUIET    = 0
verbose.NOTICE   = 1
verbose.INFO     = 2
verbose.PROGRESS = 3
verbose.DEBUG    = 4
verbose.DEBUG2   = 5

# filters for users/groups/profiles and al.
filters = EnumDict('filters')
filters.NONE                = 0x00000000
filters.ALL                 = 0xffffffff
filters.STANDARD            = 0x000000ff
filters.STD                 = filters.STANDARD

filters.SYSTEM              = 0x0000ff00
filters.SYS                 = filters.SYSTEM
filters.SYSTEM_RESTRICTED   = 0x00001000
filters.SYSRSTR             = filters.SYSTEM_RESTRICTED
filters.SYSTEM_UNRESTRICTED = 0x00002000
filters.SYSUNRSTR           = filters.SYSTEM_UNRESTRICTED

filters.PRIVILEGED          = 0x00000100
filters.PRI                 = filters.PRIVILEGED
filters.NOT_PRIVILEGED      = filters.SYSTEM - filters.PRIVILEGED
filters.NOT_PRI             = filters.NOT_PRIVILEGED
filters.GUEST               = 0x00000200
filters.GST                 = filters.GUEST
filters.NOT_GUEST           = filters.SYSTEM - filters.GUEST
filters.NOT_GST             = filters.NOT_GUEST
filters.RESPONSIBLE         = 0x00000400
filters.RSP                 = filters.RESPONSIBLE
filters.NOT_RESPONSIBLE     = filters.SYSTEM - filters.RESPONSIBLE
filters.NOT_RSP             = filters.NOT_RESPONSIBLE
filters.NOT_SYSTEM          = filters.ALL - filters.SYSTEM
filters.NOT_SYS             = filters.NOT_SYSTEM

filters.WATCHED             = 0x00000800
filters.INOTIFIED           = filters.WATCHED

filters.NOT_WATCHED         = filters.STANDARD - filters.WATCHED
filters.NOT_INOTIFIED       = filters.NOT_WATCHED

filters.EXTINCTION_TASK     = 0x00010000

filters.EMPTY               = 0x00ff0000

# enum machine stati, for core.machines
host_status = EnumDict('host_status')
host_status.UNKNOWN        = -0x00000001
host_status.NONE           =  0x00000000
host_status.ALL            =  0xffffffff
host_status.OFFLINE        =  0x000000ff
# The following 2 are the same
host_status.GOING_TO_SLEEP =  0x00000001
host_status.SLEEPING       =  0x00000001

host_status.ASLEEP         =  0x00000002
host_status.SHUTTING_DOWN  =  0x00000004
host_status.PYRO_SHUTDOWN  =  0x00000008
host_status.ONLINE         =  0x0000ff00
host_status.PINGS          =  0x00000100
host_status.BOOTING        =  0x00000200
host_status.IDLE           =  0x00000400
host_status.ACTIVE         =  0x00000800
host_status.LOADED         =  0x00001000
host_status.OP_IN_PROGRESS =  0xffff0000
host_status.UPGRADING      =  0x00010000

# FIXME: merge this with distros (don't duplicate)
host_types = EnumDict('host_types')
host_types.ALL        =  0xffffffffffffffff
host_types.NONE       =  0x0000000000000000
host_types.UNKNOWN    =  host_types.NONE
host_types.LINUX      =  0x000000000000ffff
host_types.LICORN     =  0x0000000000000001
host_types.ALT_CLIENT =  0x0000000000000002
host_types.ALT        =  host_types.ALT_CLIENT
host_types.META_SRV   =  0x0000000000000004
host_types.UBUNTU     =  0x0000000000000010
host_types.DEBIAN     =  0x0000000000000020
host_types.LNX_GEN    =  0x0000000000000040
host_types.WINDOWS    =  0x00000000ffff0000
host_types.WIN_NT     =  0x0000000000010000
host_types.WIN_7      =  0x0000000000020000
host_types.WIN_OLD    =  0x0000000000040000
host_types.APPLE      =  0x0000ffff00000000
host_types.IMAC       =  0x0000000100000000
host_types.MACBOOK    =  0x0000000200000000
host_types.IPHONE     =  0x0000000400000000
host_types.IPOD       =  0x0000000800000000
host_types.IPAD       =  0x0000001000000000
host_types.MACPRO     =  0x0000002000000000
host_types.XSERVE     =  0x0000004000000000
host_types.MACMINI    =  0x0000008000000000
host_types.TIMECAPS   =  0x0000010000000000
host_types.AIRPORT    =  0x0000020000000000
host_types.DEVICES    =  0xffff000000000000
host_types.ROUTER     =  0x0001000000000000
host_types.FIREWALL   =  0x0002000000000000
host_types.SWITCH     =  0x0004000000000000
host_types.PRINTER    =  0x0008000000000000
host_types.SCANNER    =  0x0010000000000000
host_types.MULTIFUNC  =  0x0020000000000000
host_types.APPLIANCE  =  0x0040000000000000
host_types.NAS        =  0x0080000000000000
host_types.APPLIANCE  =  0x0100000000000000
host_types.FREEBOX    =  0x0200000000000000
# room for new ones, here
host_types.VMWARE     =  0x4000000000000000
host_types.NET_OTHER  =  0x8000000000000000

# messages between client and server (inside Pyro)
message_type = EnumDict('message_type')
message_type.EMIT        = 0x0001
message_type.TRANSMIT    = 0x0002
message_type.ANSWER      = 0x0004
message_type.PUSH_STATUS = 0x0008

interactions = EnumDict('interactions')
interactions.ASK_FOR_REPAIR = 0x01
interactions.GET_PASSWORD   = 0x02

# constants from core.configuration
distros = EnumDict('distros')
distros.UNKNOWN  = 0
distros.UBUNTU   = 1
distros.LICORN   = distros.UBUNTU
distros.DEBIAN   = 2
distros.GENTOO   = 3
distros.NOVELL   = 4
distros.REDHAT   = 5
distros.MANDRIVA = 6

mailboxes = EnumDict('mailboxes')
mailboxes.NONE         = 0
mailboxes.VAR_MBOX     = 1
mailboxes.VAR_MAILDIR  = 2
mailboxes.HOME_MBOX    = 3
mailboxes.HOME_MAILDIR = 4
mailboxes.HOME_MH      = 5

servers = EnumDict('servers')
servers.MTA_UNKNOWN    = 0
servers.MTA_POSTFIX    = 1
servers.MTA_NULLMAILER = 2
servers.MTA_EXIM4      = 3
servers.MTA_QMAIL      = 4
servers.MTA_SENDMAIL   = 5
servers.IMAP_COURIER = 10
servers.IMAP_CYRUS   = 11
servers.IMAP_UW      = 12
servers.POP3_COURIER = 13
servers.POP3_QPOPPER = 14

backend_actions = EnumDict('backend_actions')
backend_actions.CREATE = 1
backend_actions.UPDATE = 2
backend_actions.DELETE = 3
backend_actions.RENAME = 4

reasons = EnumDict('reasons')
reasons.UNKNOWN             = 0
reasons.BACKENDS_CHANGED    = 1
reasons.REMOTE_SYSTEM_ASKED = 2
reasons.INTERNAL_LEAK       = 99


conditions = EnumDict('conditions')
conditions.WAIT_FOR_ME_BACK_ONLINE = 1

services = EnumDict('services')
services.UNKNOWN = 0
services.UPSTART = 1
services.SYSV    = 2
services.BSD     = 3

svccmds = EnumDict('svccmds')
# a special case to specify where the service name should be inserted in the
# command list. Not ideally placed here, but acceptable anyway IMHO.
svccmds.POSITION = -1
# standard service command types. UNKNOWN is reserved for detections purposes,
# please use it only if you know what you are doing.
svccmds.UNKNOWN = 0
svccmds.START   = 1
svccmds.STOP    = 2
svccmds.RESTART = 3
svccmds.RELOAD  = 4
