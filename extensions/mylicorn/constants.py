# -*- coding: utf-8 -*-
"""
My Licorn® JSON-API return codes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 1.4

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>

:license: GNU GPL version 3
"""

from licorn.foundations.base import EnumDict

common = EnumDict('common', from_dict={
	'NOTIMPLEMENTED' : -100,
	'FAILED'         : -1,
	'SUCCESS'        : 1,
	})

authenticate = EnumDict('authenticate', from_dict={
	''
	# -1 & 1 come from common
	'ALREADY'   : 2,
	'ANONYMOUS' : 3,
})
