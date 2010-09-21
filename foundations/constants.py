# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

constants - all enums for the rest of the world.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2
"""

from objects import LicornConfigObject

#filters for users/groups/profiles and al.
filters = LicornConfigObject()
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
host_status = LicornConfigObject()
host_status.OFFLINE = -2
host_status.IN_USE  = -1
# STATUS_IDLE is anything >=0
