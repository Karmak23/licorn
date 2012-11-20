# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

apt - apt high-level API for Licorn®

:copyright: 2012 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

import os, apt_pkg

# licorn.foundations imports
import cache, process, logging
from _settings import settings
from base      import LicornConfigObject
from styles    import *
from ltrace    import *
from ltraces   import *

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

class debian_frontend(object):
	""" A simple context manager to set / restore environment variable
		``DEBIAN_FRONTEND`` to`anything when running a particular command. """

	def __init__(self, wanted_frontend):
		self.previous_frontend = os.environ.get('DEBIAN_FRONTEND', None)
		self.wanted_frontend = wanted_frontend
	def __enter__(self, *a, **kw):
		os.environ['DEBIAN_FRONTEND'] = self.wanted_frontend
	def __exit__(self, *a, **kw):
			if self.previous_frontend:
				os.environ['DEBIAN_FRONTEND'] = self.previous_frontend

			else:
				del os.environ['DEBIAN_FRONTEND']

def apt_do_upgrade(software_upgrades=False):
	""" This function will either run :program:`unattended-upgrades`
		or :program:`apt-get dist-upgrade --yes` if :param:`software_upgrades`
		is ``False`` or ``True``, respectively.

		.. note:: the current implement is barely a hack in its current form.
			In the future, it should deal with ``apt_pkg.config`` correctly
			and use the internal python methods of :program:`unattended-upgrades`.
			This will provide all the benefits to both security and non-security
			upgrades, eg. a better structure and context management (logging,
			mailing, reboot-needed, etc).

	"""

	if software_upgrades:
		apt_upgrade_command = ['apt-get', 'dist-upgrade', '--yes' ]

		# NOTE: we need force-yes until Licorn® packages are correctly
		# signed. I know this is insecure, but as we know and manage
		# every single Licorn® server on the planet, the venom is
		# limited. Any external sysadmin not wanting this could just
		# set the Licorn® setting to "False".
		#
		# Once Licorn® package are signed, the default should be changed to
		# "False" here.
		if settings.get('foundations.apt.force_yes', True):
			apt_upgrade_command.append('--force-yes')

		try:
			with debian_frontend('noninteractive'):
					return process.execute(apt_upgrade_command)

		except:
			logging.exception(_(u'Error while running « software-upgrades »!'))

	else:
		try:
			return process.execute(['unattended-upgrades'])

			# NOTE: we do not send an event / notification here. It's up
			# to the [much higher] calling function to do it.

		except:
			logging.exception(_(u'Error while running « unattended-upgrades »!'))

__all__ = ('version_compare', 'apt_do_check', 'apt_do_upgrade', )
