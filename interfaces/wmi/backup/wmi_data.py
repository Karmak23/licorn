# -*- coding: utf-8 -*-
"""
Licorn WMI2 system views

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

from licorn.core                           import LMC
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import *

def base_data_dict():

	volext   = LMC.extensions.volumes
	rdiffext = LMC.extensions.rdiffbackup

	volumes = [ v for v in volext ]
	mounted = [ v for v in volumes if v.enabled and v.mount_point ]
	enabled = [ v for v in volumes if v.enabled ]

	return {
			'extension'             : rdiffext,
			'volext'                : volext,
			'volumes'               : volumes,
			'enabled_volumes'       : enabled,
			'mounted_volumes'       : mounted,
			# curvol can be None, but it will be tested before use, with various extension events.
			'curvol'                : rdiffext.current_operated_volume,
			#'main_content_template' : 'backup/index_main.html',
			#'sub_content_template'  : 'backup/index_sub.html',
		}
