# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

apt - apt high-level API for Licorn®

:copyright: 2012 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

import apt_pkg

# licorn.foundations imports
import cache, process, logging
from base    import LicornConfigObject
from styles  import *
from ltrace  import *
from ltraces import *

if not process.executable_exists_in_path('unattended-upgrades'):
	logging.warning(_(u'You must install the debian package {0} for the '
		u'upgrade mechanism to work fully. Currently you will only be able to '
		u'check if the system needs upgrading.').format(stylize(ST_NAME, 'unattended-upgrades')))

# version_compare() will refuse to work without this.
apt_pkg.init()

# import it here to have it handy inside Licorn®
version_compare = apt_pkg.version_compare

from licorn.contrib import apt_check

opts = LicornConfigObject()
opts.show_package_names          = False
opts.readable_output             = False
opts.security_updates_unattended = False

@cache.cached(cache.one_day)
def apt_do_check(**kwargs):
	""" Just cache the apt-check result. We need `**kwargs` to eventually be
		able to force the cache to expire after an upgrade. """

	# The init() has to be recomputed at every call, because it
	# works in-memory and won't notice real-life changes if not re-run.
	apt_check.init()
	return apt_check.run(opts)

def apt_do_upgrade(software_upgrades=False):
	if software_upgrades:
		try:
			raise NotImplementedError(_(u'software_upgrades not yet implemented'))
		except:
			logging.exception(_(u'Error while running « software-upgrades »!'))
			return None, None

	else:
		try:
			return process.execute(['unattended-upgrades'])

			# NOTE: we do not send an event / notification here. It's up
			# to the [much higher] calling function to do it.

		except:
			logging.exception(_(u'Error while running « unattended-upgrades »!'))
			return None, None

__all__ = ('version_compare', 'apt_do_check', 'apt_do_upgrade', )
