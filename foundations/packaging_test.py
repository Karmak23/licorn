# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

packaging test - testsuite for packaging

:copyright:
	* 2012 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

import py.test

import logging, exceptions
import process, packaging
from constants import distros

pkgs = dict.fromkeys((distros.UBUNTU, distros.DEBIAN), ['python-pip'])
pkgs.setdefault(distros.UNKNOWN, 'PIP')

def no_connection():
	class connobj():
		def __init__(self):
			out, err = process.execute(['sudo', 'ip', 'route', 'list', 'to', 'exact', '0/0'])
			self.route = out.strip()
		def __enter__(self):
			process.execute(['sudo', 'ip', 'route', 'del', 'default'])
		def __exit__(self, dum1, dum2, dum3):
			process.execute(['sudo', 'ip', 'route', 'add'] + self.route.split())

	return connobj()
def clean_apt(full=True):

	try:
		process.execute(['apt-get', 'remove', '--purge', pkgs[distros.DEBIAN]])

	except:
		logging.exception('Cannot clean test environment!')

	if full:
		try:
			process.execute(['apt-get', 'clean'])

		except:
			logging.exception('Cannot clean test environment!')
def pytest_configure(config):
	clean_apt()
def pytest_unconfigure(config):
	clean_apt()

# =================================================================== TESTS
# NOTE: they all fail because of LMC not connected when py.test runs
# outside of the daemon. We have to investigate a way to connect LMC
# and get LMC.configuration.something to return the wanted value.

def test_install_packages():
	""" Test the APT part. """

	assert packaging.install_packages(pkgs) == None
def test_reinstall_packages():
	""" Re-installing a package over and over should not fail. """
	assert packaging.install_packages(pkgs) == None
def test_install_without_connection_from_cache():
	""" trying to install something without an internet connection
		but from the cache should succeed. """

	clean_apt(full=False)

	with no_connection():
		assert packaging.install_packages(pkgs) == None
def test_install_without_connection():
	""" trying to install something without an internet connection
		should raise an error. """

	clean_apt()

	with no_connection():
		py.test.raises(exceptions.LicornRuntimeException, packaging.install_packages, pkgs)
