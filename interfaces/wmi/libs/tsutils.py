# -*- coding: utf-8 -*-
"""
Licorn WMI2 Test Suite utils

cf. http://stackoverflow.com/questions/5917587/django-unit-tests-without-a-db

:copyright:
	* 2012 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>
	* 2012 META IT http://meta-it.fr/

:license: GNU GPL version 2
"""

from django.test.simple import DjangoTestSuiteRunner

class NoDbTestRunner(DjangoTestSuiteRunner):
  """ A test runner to test without database creation """

  def setup_databases(self, **kwargs):
    """ Override the database creation defined in parent class """
    pass

  def teardown_databases(self, old_config, **kwargs):
    """ Override the database teardown defined in parent class """
    pass
