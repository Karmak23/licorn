# -*- coding: utf-8 -*-
"""
Licorn WMI2 system wmi_data

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

from licorn.foundations.ltrace             import *
from licorn.foundations.constants          import host_types, host_status
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import *
from licorn.core                           import LMC

licorn_hosts_online = None

def count_licorn_hosts_online():
	try:
		return LMC.machines.licorn_machines_count()

	except:
		return 0

# this should occur only the first time the module is loaded.
if licorn_hosts_online is None:
	licorn_hosts_online = count_licorn_hosts_online()
