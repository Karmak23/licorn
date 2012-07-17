# -*- coding: utf-8 -*-
"""
Licorn WMI2 Test Suite utils

cf. http://stackoverflow.com/questions/5917587/django-unit-tests-without-a-db

:copyright:
	* 2012 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>
	* 2012 META IT http://meta-it.fr/

:license: GNU GPL version 2
"""

import unittest
from django.test.simple import DjangoTestSuiteRunner
from licorn.foundations import logging

class WmiOutputStream(object):
	""" Emulate the unittest output stream behavior, but send things to
		licorn.foundations.logging facility instead.

		We don't bother providing writeLn(), unit-test will wrap the
		current class already.
	"""

	def write(self, arg):
		logging.raw_message(arg, to_local=False)

	def flush(self):
		pass

class WmiTextTestRunner(unittest.TextTestRunner):
	"""A test runner class that displays results in textual form, modified
		for Licorn® usage where tests are run remotely in the daemon.

		This is barely the original unittest.TextTestRunner class, modified
		to use the Licorn® facilities instead of self.stream.
	"""

	def __init__(self, stream=None, descriptions=True, verbosity=1,
					failfast=False, buffer=False, resultclass=None):

		unittest.TextTestRunner.__init__(self, stream=WmiOutputStream(),
					descriptions=descriptions, verbosity=verbosity,
					failfast=failfast, buffer=buffer, resultclass=resultclass)

class NoDbTestRunner(DjangoTestSuiteRunner):
	""" A test runner to test without database creation """

	def setup_databases(self, **kwargs):
		""" Override the database creation defined in parent class """
		pass

	def teardown_databases(self, old_config, **kwargs):
		""" Override the database teardown defined in parent class """
		pass

	def run_suite(self, suite, **kwargs):
		""" As Django hardcodes the test runner class, we have to provide
			our own run_suite() method, to use our WmiTestRunner class. """

		return WmiTextTestRunner(verbosity=self.verbosity, failfast=self.failfast).run(suite)
