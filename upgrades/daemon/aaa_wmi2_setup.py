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
import sys, os, glob, stat

from apt_pkg   import version_compare
from threading import current_thread

from licorn.foundations           import logging, settings, process, packaging, fsapi, events, network
from licorn.foundations.styles    import *
from licorn.foundations.constants import distros

from licorn.core import LMC

pip_packages = dict.fromkeys((distros.UBUNTU, distros.DEBIAN), ['python-pip'])
# This one is for explanation purposes only, when on an unknown distro.
pip_packages.setdefault(distros.UNKNOWN, 'PIP')

jinja2_packages = dict.fromkeys((distros.UBUNTU, distros.DEBIAN), ['python-jinja2'])
# distros.UNKNOWN value serves for explanation purposes and PIP installation.
# Do not modify it unless PIP package name changes.
jinja2_packages.setdefault(distros.UNKNOWN, 'Jinja2')

twisted_packages = dict.fromkeys((distros.UBUNTU, distros.DEBIAN), ['python-twisted-web'])
# distros.UNKNOWN value serves for explanation purposes and PIP installation.
# Do not modify it unless PIP package name changes.
twisted_packages.setdefault(distros.UNKNOWN, 'Twisted Web')

django_packages = dict.fromkeys((distros.UBUNTU, distros.DEBIAN), ['python-django'])
# distros.UNKNOWN value serves for explanation purposes and PIP installation.
# Do not modify it unless PIP package name changes.
django_packages.setdefault(distros.UNKNOWN, 'Django')

def check_and_install_pip():
	if not os.path.exists('/usr/bin/pip'):
		packaging.install_packages(pip_packages)
def check_and_install_twisted():

	if LMC.configuration.distro in (distros.UBUNTU, distros.DEBIAN):

		twist = glob.glob('/usr/share/pyshared/twisted/web')

		if twist == []:
			packaging.install_packages(twisted_packages)

	else:
		packaging.raise_not_installable(twisted_packages[distros.UNKNOWN])
def check_and_install_django():
	""" We need Django 1.3 for shortcuts and some other features. Version 1.3
		is packaged on Ubuntu Oneiric and Debian Wheezy. It's also available
		in ``squeeze-backports``, but testing if this source is active is a bit
		overhaul for the current `ùpgrades` mechanism. Perhaps in a future
		version if `foundations.apt` or `foundations.packaging` gets some
		dedicated function. """

	if (LMC.configuration.distro == distros.UBUNTU
			and version_compare(LMC.configuration.distro_version, '11.10') >= 0
		) or (LMC.configuration.distro == distros.DEBIAN
			and version_compare(LMC.configuration.distro_version, '7.0') >= 0):

		dj = glob.glob('/usr/share/pyshared/django')

		if dj == []:
			packaging.install_packages(django_packages)

	elif LMC.configuration.distro in (distros.UBUNTU, distros.DEBIAN):

		# We need at least Django 1.3
		dj = glob.glob('/usr/local/lib/python*/dist-packages/Django-1.[3456]*')

		if dj == []:
			packaging.pip_install_packages([ django_packages[distros.UNKNOWN] ])

	else:
		packaging.raise_not_installable(django_packages[distros.UNKNOWN])
def check_and_install_jinja2():
	""" We need Jinja 2.6+ for some `sort*()` functions and other
		enhancements. Version 2.6 is available as a package only on
		Ubuntu Precise and Debian Wheezy as of 20120227. Older DEBIAN
		distros will get it installed via PIP. """

	if (LMC.configuration.distro == distros.UBUNTU
			and version_compare(LMC.configuration.distro_version, '12.04') >= 0
		) or (LMC.configuration.distro == distros.DEBIAN
			and version_compare(LMC.configuration.distro_version, '7.0') >= 0):

		j2 = glob.glob('/usr/share/pyshared/jinja2')

		if j2 == []:
			packaging.install_packages(jinja2_packages)

	elif LMC.configuration.distro in (distros.UBUNTU, distros.DEBIAN):

		# Check the Jinja2 version installed to eventually trigger an
		# upgrade via PIP if an older version is installed. Glob Python
		# too, to be gentle with 2.5/2.6/2.7 distros.
		j2 = glob.glob('/usr/local/lib/python*/dist-packages/Jinja2-2.6*')

		if j2 == []:
			packaging.pip_install_packages([ jinja2_packages[distros.UNKNOWN] ])

	else:
		packaging.raise_not_installable(jinja2_packages[distros.UNKNOWN])
def check_and_install_djinja():
	""" Djinja is only available as a PIP package as of 20120227, whatever the Debian
		derivative tested. """

	dj = glob.glob('/usr/local/lib/python*/dist-packages/Djinja-*')

	if dj == []:
		packaging.pip_install_packages(['Djinja'])
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
									path=python_path,
									uid=0, gid=0,
									root_dir_perm=00755,
									dirs_perm=00755,
									files_perm=00644)
							], batch=True, full_display=False):
				# TODO: we could count modified entries and display a nice
				# information message. Left to contributors, we don't have
				# enough time.
				pass
def check_django_wmi_database():
	""" Check the first installation of the Django session database for the
		WMI. If it doesn't exist, create it and sync it, for the WMI2 to work
		correctly immediately after installation. """

	# we rename the Django settings to `djsettings` not to
	# clash with `licorn.foundations.settings`.
	import licorn.interfaces.wmi.settings as djsettings

	defdb = djsettings.DATABASES.get('default')

	# Don't try to prepare anything more complicated than SQLite, this is beyond
	# the scope of the current script.
	if 'sqlite3' in defdb.get('ENGINE'):
		dbfile = defdb.get('NAME')

		if not os.path.exists(dbfile):

			# The directories should have been created by the Makefile or
			# package, but this doesn't cost much to check anyway.
			os.makedirs(os.path.dirname(dbfile))

			fsapi.touch(dbfile)

			logging.info(_(u'Creating the Django session database in {0}, '
					u'this may take a while…').format(stylize(ST_PATH, dbfile)))

			# execute_manager will fail without this.
			sys.path.extend(['licorn.interfaces', 'licorn.interfaces.wmi'])

			from licorn.interfaces.wmi  import django_setup
			from django.core.management import execute_manager

			# we must put 'manage.py' in the arguments for Django to lookup
			# correctly the commands set for this utility.
			django_setup()
			execute_manager(djsettings, [ 'manage.py', 'syncdb',
										'--noinput', '--verbosity=0' ])

			logging.info(_(u'Successfully created Django session database '
							u'in {0}.').format(stylize(ST_PATH, dbfile)))
def check_ssl_certificate():
	""" This procedure has been gently inspired by Debian/Ubuntu
		`dovecot-common` postinst script.

		References:
		- http://stackoverflow.com/questions/1087227/validate-ssl-certificates-with-python
	"""

	if not (os.path.exists(settings.licornd.wmi.ssl_cert)
		and os.path.exists(settings.licornd.wmi.ssl_key)):

		hostname = network.get_local_hostname()

		logging.progress(_(u'Creating an SSL certificate/key pair for the WMI…'))

		out, err = process.execute([ 'openssl', 'req', '-newkey', 'rsa:2048',
					'-x509', '-days', '3652.5', '-nodes', '-rand', '/dev/urandom',
					'-out', settings.licornd.wmi.ssl_cert,
					'-keyout', settings.licornd.wmi.ssl_key ],
					input_data='.\n.\n.\nLicorn® WMI\n{0}\n{0}\nroot@{0}\n'.format(hostname))

		# Python SSL needs the certificate appended to the key, else it displays
		# 'error:140DC009:SSL routines:SSL_CTX_use_certificate_chain_file:PEM lib'
		# errors and never accepts connections.
		# Cf. http://lists.geni.net/pipermail/gcf-dev/2011-April/000054.html
		open(settings.licornd.wmi.ssl_key, 'ab').write(
				open(settings.licornd.wmi.ssl_cert).read())

		# `openssl` CLI tools displays every question on `stderr`. Thanks for
		# not respecting stderr/stdout conventions, OpenSSL… We cannot rely on
		# 'err', and won't display anything. Any real error will be silently
		# ignored, which is not cool.
		#
		#if err:
		#	logging.warn_or_raise(_(u'An error occured while setting up SSL '
		#		u'certificate and key for the WMI! OpenSSL Log follows:\n') + err)

		os.chown(settings.licornd.wmi.ssl_cert, 0, 0)
		os.chmod(settings.licornd.wmi.ssl_cert, 0644)
		os.chown(settings.licornd.wmi.ssl_key, 0, 0)
		os.chmod(settings.licornd.wmi.ssl_key, 0600)

		logging.info(_(u'Successfully created WMI SSL certificate/key pair.'))

@events.handler_function
def wmi_starts(*args, **kwargs):
	""" Install everything needed for the WMI2, depending on the current configuration.

		In developper installations, `make uninstall` will correctly get rid of
		everything made by this function, except the PIP/apt-get installs.

		.. note:: this callback will be run *before* the WMI is really forked. If the
			WMI is disabled by any configuration directive or command-line argument,
			it will not be run.

		.. versionadded:: 1.3
	"""

	check_and_install_pip()
	check_and_install_twisted()
	check_and_install_django()
	check_and_install_jinja2()
	check_and_install_djinja()
	check_pip_perms()
	check_django_wmi_database()
	check_ssl_certificate()

__all__ =  ('wmi_starts', )
