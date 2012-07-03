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

__common_dict = {
	'NOTIMPLEMENTED' : -100,
	'OVERQUOTA'      : -10,
	'NOTFOUND'       : -9,
	'SUSPENDED'      : -3,
	'UNAUTHORIZED'   : -2,
	'FAILED'         : -1,
	# 0 is not used.
	'SUCCESS'        : 1,
	}

common = EnumDict('common', from_dict=__common_dict)

# we always merge the common dict to include common result codes,
# this makes it easier to use in logging messages.
authenticate = EnumDict('authenticate', from_dict=__common_dict)
authenticate.ALREADY   = 2
authenticate.ANONYMOUS = 3

# other JSON-RPC functions
set_attribute = EnumDict('set_attribute', from_dict=__common_dict)

shorten_url = EnumDict('shorten_url', from_dict=__common_dict)
shorten_url.ALREADY = 2

is_reachable = EnumDict('is_reachable', from_dict=__common_dict)
is_reachable.UNREACHABLE = -4
is_reachable.UNKNOWN     = 2
