# -*- coding: utf-8 -*-
"""
Licorn WMI2 machines data

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

from django.utils.translation              import ugettext_lazy as _
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import *

from licorn.foundations.constants import host_status, host_types, host_os


get_host_status_html = {
	host_status.ONLINE        : [ 'online.png', _('This machine is online') ],
	host_status.PINGS         : [ 'online.png', _('This machine responds to network probes, but detailled status is not available') ],
	host_status.UNKNOWN       : [ 'unknown.png', _('The state of the machine is unknown') ],
	host_status.OFFLINE       : [ 'offline.png', _('This machine is offline') ],
	host_status.BOOTING       : [ 'progress_09.gif', _('This machine is rebooting, it is no more accessible until back online') ],
	host_status.IDLE          : [ 'idle.png', _('This machine is idle: powered on but no user logged in') ],
	host_status.ACTIVE        : [ 'active.png', _('This machine is online and can be managed') ],
	host_status.UPGRADING     : [ 'progress_03.gif', _('This machine is upgrading some of its software') ],
	host_status.PYRO_SHUTDOWN : [ 'online.png', _('Pyro shutdown')],
	host_status.ONLINE
		|host_status.UPGRADING: [ 'progress_03.gif', _('This machine is upgrading some of its software') ],
	host_status.ACTIVE
		|host_status.UPGRADING: [ 'progress_03.gif', _('This machine is upgrading some of its software') ],
}

def get_host_os_html(mtype):
	if mtype & host_os.LINUX:
		return [ 'linux.png', _('This machine runs an undetermined version of Linux®.') ]
	elif mtype & host_os.WINDOWS:
		return [ 'windows.png', _('This machine is running a Windows system.') ]
	elif mtype & host_os.APPLE:
		return [ 'apple.png', _('This machine is manufactured by Apple® Computer Inc.') ]
	else:
		return [ 'unknown.png', _('The OS of the machine is unknown') ]

def get_host_type_html(mtype):



	if mtype & host_types.LICORN:
		return [ 'licorn.png', _('This machine has Licorn® installed.') ]
	elif mtype & host_types.META_SRV:
		return [ 'server.png', _('This machine is a META IT/Licorn® server.') ]
	elif mtype & host_types.ALT:
		return [ 'alt.png', _('This machine is an ALT® client.') ]
	elif mtype & host_types.FREEBOX:
		return [ 'free.png', _('This machine is a Freebox appliance.') ]
	elif mtype & host_types.LIVEBOX:
		return [ 'orange.png', _('This machine is a Orange Livebox.') ]
	elif mtype & host_types.PRINTER:
		return [ 'printer.png', _('This machine is a network printer.') ]
	elif mtype & host_types.MULTIFUNC:
		return [ 'scanner.png', _('This machine is a network scanner.') ]
	elif mtype & host_types.ROUTER:
		return [ 'router.png', _('This machine is a network router.') ]
	elif mtype & host_types.VIRTUALBOX:
		return [ 'vbox.png', _('This is a Virtualbox virtual machine.') ]
	else:
		return [ 'unknown.png', _('The type of the machine is unknown') ]
