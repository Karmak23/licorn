# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

constants - all enums for the rest of the world.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2
"""

from styles     import *
from base       import EnumDict

# verbose levels for options and logging.*
verbose = EnumDict('verbose')
verbose.QUIET    = 0
verbose.NOTICE   = 1
verbose.INFO     = 2
verbose.PROGRESS = 3
verbose.DEBUG    = 4
verbose.DEBUG2   = 5

#filters for users/groups/profiles and al.
filters = EnumDict('filters')
filters.NONE        = 0x00000000
filters.ALL         = 0xffffffff
filters.STANDARD    = 0x000000ff
filters.STD         = filters.STANDARD

filters.SYSTEM      = 0x0000ff00
filters.SYS         = filters.SYSTEM
filters.SYSTEM_RESTRICTED= 0x00001000
filters.SYSRSTR     = filters.SYSTEM_RESTRICTED
filters.SYSTEM_UNRESTRICTED= 0x00002000
filters.SYSUNRSTR     = filters.SYSTEM_UNRESTRICTED

filters.PRIVILEGED  = 0x00000100
filters.PRI         = filters.PRIVILEGED
filters.NOT_PRIVILEGED  = 0x00000101
filters.NOT_PRI         = filters.NOT_PRIVILEGED
filters.GUEST       = 0x00000200
filters.GST         = filters.GUEST
filters.NOT_GUEST       = 0x00000201
filters.NOT_GST         = filters.NOT_GUEST
filters.RESPONSIBLE = 0x00000400
filters.RSP         = filters.RESPONSIBLE
filters.NOT_RESPONSIBLE = 0x00000401
filters.NOT_RSP         = filters.NOT_RESPONSIBLE
filters.NOT_SYSTEM  = 0x00000301
filters.NOT_SYS     = filters.NOT_SYSTEM

filters.EMPTY       = 0x00ff0000

# enum machine stati, for core.machines
host_status = EnumDict('host_status')
host_status.UNKNOWN        = -0x0001
host_status.OFFLINE        =  0x00ff
host_status.GOING_TO_SLEEP =  0x0001
host_status.ASLEEP         =  0x0002
host_status.SHUTTING_DOWN  =  0x0004
host_status.ONLINE         =  0xff00
host_status.IDLE           =  0x0400
host_status.ACTIVE         =  0x0800

# FIXME: merge this with distros (don't duplicate)
host_types = EnumDict('host_types')
host_types.ALL        =  0xffffffffffffffff
host_types.NONE       =  0x0000000000000000
host_types.UNKNOWN    = -0x0000000000000001
host_types.LINUX      =  0x000000000000ffff
host_types.ALT_CLIENT =  0x0000000000000001
host_types.ALT        =  host_types.ALT_CLIENT
host_types.UBUNTU     =  0x0000000000000002
host_types.DEBIAN     =  0x0000000000000004
host_types.WINDOWS    =  0x00000000ffff0000
host_types.WIN_NT     =  0x0000000000010000
host_types.WIN_7      =  0x0000000000020000
host_types.WIN_OLD    =  0x0000000000040000
host_types.APPLE      =  0x0000ffff00000000
host_types.IMAC       =  0x0000000100000000
host_types.MACBOOK    =  0x0000000200000000
host_types.IPHONE     =  0x0000000400000000
host_types.IPAD       =  0x0000000800000000
host_types.DEVICES    =  0xffff000000000000
host_types.ROUTER     =  0x0001000000000000
host_types.FIREWALL   =  0x0002000000000000
host_types.SWITCH     =  0x0004000000000000
host_types.PRINTER    =  0x0008000000000000
host_types.SCANNER    =  0x0010000000000000
host_types.MULTIFUNC  =  0x0020000000000000
host_types.APPLIANCE  =  0x0040000000000000
host_types.NET_OTHER  =  0x0080000000000000

# messages between client and server (inside Pyro)
message_type = EnumDict('message_type')
message_type.EMIT        = 0x0001
message_type.TRANSMIT    = 0x0002
message_type.ANSWER      = 0x0004
message_type.PUSH_STATUS = 0x0008

interactions = EnumDict('interactions')
interactions.ASK_FOR_REPAIR = 0x01

licornd_roles = EnumDict('licornd_roles')
licornd_roles.UNSET  = 1
licornd_roles.SERVER = 2
licornd_roles.CLIENT = 3

# constants from core.configuration
distros = EnumDict('distros')
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

# this is a replica of python.gamin, to help displaying messages in a
# human-readable form.
gamin_events = {
	1: 'GAMChanged',
	2: 'GAMDeleted',
	3: 'GAMStartExecuting',
	4: 'GAMStopExecuting',
	5: 'GAMCreated',
	6: 'GAMMoved',
	7: 'GAMAcknowledge',
	8: 'GAMExists',
	9: 'GAMEndExist'
	}
