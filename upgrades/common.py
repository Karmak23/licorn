# -*- coding: utf-8 -*-
"""
Licorn upgrades: - http://docs.licorn.org/upgrades/

Common checks to all upgrades modules.

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
:license: GNU GPL version 2
"""

import os, glob

from licorn.foundations           import logging, packaging, fsapi
from licorn.foundations.styles    import *
from licorn.foundations.constants import distros
from licorn.core                  import LMC

pip_packages = dict.fromkeys((distros.UBUNTU, distros.DEBIAN), ['python-pip'])
# This one is for explanation purposes only, when on an unknown distro.
pip_packages.setdefault(distros.UNKNOWN, 'PIP')

def check_and_install_pip():
	if not os.path.exists('/usr/bin/pip'):
		packaging.install_packages(pip_packages)
def check_pip_perms():
	""" Fix a PIP bug we don't notice if we are root. But normal developpers
		could face it.

		We've spotted this bug only on Ubuntu. But we didn't test other
		distros. If you see it, just add more conditions in this 'if'.

	"""

	if LMC.configuration.distro in (distros.UBUNTU, distros.DEBIAN):
		for python_path in glob.glob('/usr/local/lib/python*/dist-packages'):
			logging.progress(_(u'Fixing permissions in {0}, this may take '
							u'a while…').format(stylize(ST_PATH, python_path)))

			# This is the Licorn® way of running these shell commands,
			# but we do it in ONE pass without forking anything :-)
			#
			#	sudo find /usr/local/lib -print0 | sudo xargs -0 -n 1024 chown root:root
			#	sudo find /usr/local/lib -type d -print0 | sudo xargs -0 -n 1024 chmod 755
			#	sudo find /usr/local/lib -type f -print0 | sudo xargs -0 -n 1024 chmod 644
			for uyp in fsapi.check_dirs_and_contents_perms_and_acls_new([
								fsapi.FsapiObject(name='python_path',
									path=python_path, uid=0, gid=0,
									root_dir_perm=00755, dirs_perm=00755,
									files_perm=00644)
							], batch=True, full_display=False):
				# TODO: we could count modified entries and display a nice
				# information message. Left to contributors, we don't have
				# enough time.
				pass

__all__ = ('check_and_install_pip', 'check_pip_perms')
