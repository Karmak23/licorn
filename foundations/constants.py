# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

constants - all enums for the rest of the world.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2
"""

class Enumeration():
	pass

# verbose levels for options and logging.*
verbose = Enumeration()
verbose.QUIET    = 0
verbose.NOTICE   = 1
verbose.INFO     = 2
verbose.PROGRESS = 3
verbose.DEBUG    = 4
verbose.DEBUG2   = 5

#filters for users/groups/profiles and al.
filters = Enumeration()
filters.NONE        = 0x00000000
filters.ALL         = 0xffffffff
filters.STANDARD    = 0x000000ff
filters.STD         = filters.STANDARD

filters.SYSTEM      = 0x0000ff00
filters.SYS         = filters.SYSTEM

filters.PRIVILEGED  = 0x00000100
filters.PRI         = filters.PRIVILEGED
filters.GUEST       = 0x00000200
filters.GST         = filters.GUEST
filters.RESPONSIBLE = 0x00000400
filters.RSP         = filters.RESPONSIBLE

filters.EMPTY       = 0x00ff0000

# enum machine stati, for core.machines
host_status = Enumeration()
host_status.UNKNOWN  = -0x0001
host_status.OFFLINE  = 0x0000
host_status.ONLINE   = 0x00ff
host_status.ASLEEP   = 0x0001
host_status.IDLE     = 0x0002
host_status.ACTIVE   = 0x0004

# messages between client and server (inside Pyro)
message_type = Enumeration()
message_type.EMIT     = 0x01
message_type.TRANSMIT = 0x02
message_type.ANSWER   = 0x04

interactions = Enumeration()
interactions.ASK_FOR_REPAIR = 0x01


# constants from core.configuration
distros = Enumeration()
distros.UBUNTU   = 1
distros.LICORN   = distros.UBUNTU
distros.DEBIAN   = 2
distros.GENTOO   = 3
distros.NOVELL   = 4
distros.REDHAT   = 5
distros.MANDRIVA = 6

mailboxes = Enumeration()
mailboxes.VAR_MBOX     = 1
mailboxes.VAR_MAILDIR  = 2
mailboxes.HOME_MBOX    = 3
mailboxes.HOME_MAILDIR = 4
mailboxes.HOME_MH      = 5

servers = Enumeration()
servers.MTA_UNKNOWN    = 0
servers.MTA_POSTFIX    = 1
servers.MTA_NULLMAILER = 2
servers.MTA_EXIM4      = 3
servers.MTA_QMAIL      = 4
servers.MTA_SENDMAIL   = 5
servers.IMAP_COURIER = 1
servers.IMAP_CYRUS   = 2
servers.IMAP_UW      = 3
servers.POP3_COURIER = 1
servers.POP3_QPOPPER = 2

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
