# -*- coding: utf-8 -*-
"""
	Pre-install steps for the WMI2.

	- `Django`: at least version *1.3* (neded for some `shortcuts` and features).
	- `Jinja2`: at least version *2.6* (needed for sort(attribute='...') argument).
	- `Djinja`: at least version *0.7* (because version 0.6 doesn't display any valuable template debugging output).

:copyright:
	* Olivier Cortès <olive@licorn.org>
	* META IT - Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2
"""
import glob

from apt_pkg import version_compare

from licorn.foundations           import packaging, events
from licorn.foundations.styles    import *
from licorn.foundations.constants import distros
from licorn.core                  import LMC

pyudev_packages = dict.fromkeys((distros.UBUNTU, distros.DEBIAN), ['python-pyudev'])
# distros.UNKNOWN value serves for explanation purposes and PIP installation.
# Do not modify it unless PIP package name changes.
pyudev_packages.setdefault(distros.UNKNOWN, 'Pyudev')

def check_and_install_pyudev():
	""" We need Pyudev to talk to udev and handle volumes. """

	if (LMC.configuration.distro == distros.UBUNTU
			and version_compare(LMC.configuration.distro_version, '10.04') >= 0
		) or (LMC.configuration.distro == distros.DEBIAN
			and version_compare(LMC.configuration.distro_version, '7.0') >= 0):

		udev = glob.glob('/usr/share/pyshared/pyudev*')

		if udev == []:
			packaging.install_packages(pyudev_packages)

	elif (LMC.configuration.distro == distros.DEBIAN
			and version_compare(LMC.configuration.distro_version, '6.0') <= 0):

		udev = glob.glob('/usr/local/lib/python*/dist-packages/pyudev*')

		if udev == []:
			packaging.pip_install_packages([ pyudev_packages[distros.UNKNOWN] ])

	else:
		packaging.raise_not_installable(pyudev_packages[distros.UNKNOWN])

@events.handler_function
def extension_volumes_imports(*args, **kwargs):
	""" Install python-pyudev from APT, or from PIP on "old" Debian Squeeze.

		.. versionadded:: 1.4.2
	"""

	from licorn.upgrades import common

	common.check_and_install_pip()
	check_and_install_pyudev()
	common.check_pip_perms()

__all__ =  ('extension_volumes_imports', )
