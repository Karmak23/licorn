# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

packaging - High-level API to manipulate packages accross distros.

:copyright:
	* 2012 Olivier Cortès <olive@deep-ocean.net>
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
:license: GNU GPL version 2
"""

import sys, os
from threading import current_thread

# licorn.foundations imports
import exceptions, process, logging
from base      import LicornConfigObject
from styles    import *
from ltrace    import *
from ltraces   import *
from constants import distros

def install_packages(packages_for_distros, warn_only=False):
	""" Installs a package, the standard way (= recommended by the underlying
		distro). Will use `apt-get` (or `python-apt`) on debian and
		derivatives, `emerge` on gentoo, etc.

		:param packages_for_distros: a `dict`, whose *keys* are constants from
			`licorn.foundations.constants.distros`, and *values* are lists of
			strings representing packages names. Packages names can be
			different on the various distros, they just have to be valid. For
			real-life examples, see in the `upgrades` modules (notably daemon).

			.. note:: the special *key/value* pair ``distros.UNKNOWN`` is used
				for user messages only. Put the « human-readable » form of the
				package name here.

		:param warn_only: a boolean indicating that any error/exception should
			be considered harmless and should not halt the current operations.
			When installing a bunch of packages, this could eventually be useful.
			Defaults to ``False`` (=raise exceptions and stop).

		.. note:: all implementations are not yet done. As of 20120227, Only
			Debian/Ubuntu works via `apt-get`.

		.. warning:: Currently, this function does the job **automatically**,
			eg. it won't ask for any confirmation before trying to install
			the asked packages.

		.. versionadded:: 1.3
	"""

	# this is not cool to do this here. We have a circular loop.
	from licorn.core import LMC

	if not LMC.configuration.distro in packages_for_distros:
		logging.warn_or_raise(_(u'Your distro is not yet supported to automatically install '
								u'package {0}, skipping it.').format(stylize(ST_NAME,
								packages_for_distros[distros.UNKNOWN])), warn_only=warn_only)

	if LMC.configuration.distro in (distros.LICORN, distros.UBUNTU, distros.DEBIAN):
		try:
			packages = packages_for_distros[LMC.configuration.distro]

		except KeyError:
			# fall back to debian package name as last resort. This should still
			# work in the vast majority of cases.
			packages = packages_for_distros[distros.DEBIAN]

		tname  = stylize(ST_NAME, current_thread().name)
		pnames = u', '.join(stylize(ST_NAME, x) for x in packages)

		# TODO: re-implement this with internal `python-apt` instead of forking
		# a non-interactive :program:`apt-get` process.
		os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

		logging.notice(_(u'{0}: Installing needed packages {1} before continuing. Please wait…').format(tname, pnames))

		out, err = process.execute([ 'apt-get', 'install', '--quiet', '--yes',
									'--force-yes', '--verbose-versions' ] + packages)

		if err:
			logging.warn_or_raise(_(u'{0}: An error occured while installing package(s) '
				u'{1}! Apt-Get Log follows:').format(tname, pnames) + u'\n' + err, warn_only=warn_only)

		else:
			logging.notice(_(u'{0}: Successfully installed package(s) {1} via {2}.').format(
							tname, pnames, stylize(ST_NAME, 'apt-get')))

	else:
		# TODO: implement emerge/RPM/YUM whatever here.
		logging.warn_or_raise(_(u'Installing packages on your distro is not yet '
				u'supported, sorry. You should install {0} yourself before '
				u'continuing.').format(pnames), warn_only=warn_only)
def pip_install_packages(packages_list, warn_only=False):
	""" Install one or more packages, via PIP. The function just spawns :program:`pip`
		with argument ``install``.

		:param packages_list: a list of strings representing PIP packages names. For
			real-life examples, see the `upgrades` modules (notably `daemon`).

		:param warn_only: see :func:`install_packages`.

		.. versionadded:: 1.3
			Before the WMI2, the package management foundations didn't exist.
	"""

	tname  = stylize(ST_NAME, current_thread().name)
	pnames = u', '.join(stylize(ST_NAME, x) for x in packages_list)

	logging.notice(_(u'{0}: Installing needed packages {1} from source before '
					u'continuing. Please wait…').format(tname, pnames))

	out, err = process.execute([ 'pip', 'install' ] + packages_list)

	if err:
		logging.warn_or_raise(_(u'An error occured while installing package(s) '
			u'{0}! PIP install Log follows:').format(pnames) + u'\n' + err, warn_only=warn_only)

	else:
		logging.notice(_(u'{0}: Successfully installed package(s) {1} via {2}.').format(
				tname, pnames, stylize(ST_NAME, 'PIP')))
def raise_not_installable(package_name):
	raise exceptions.LicornRuntimeException(_(u'Sorry, automatic install of '
			u'{0} is not yet supported on your distro. Please install it '
			u'manually before continuing.').format(
				stylize(ST_NAME, package_name)))

# export only the bare minimum.
__all__ = ( 'install_packages', 'pip_install_packages', 'raise_not_installable', )
