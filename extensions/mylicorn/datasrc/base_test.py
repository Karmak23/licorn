# -*- coding: utf-8 -*-
"""
Licorn® MyLicorn data sources

:copyright: (C) 2012 Olivier Cortès <olive@licorn.org>
:license: GNU GPL version 2

"""
import os, py.test

from licorn.foundations import exceptions

import base

class AnonTest(object): pass
class AnonTest2(object): pass
class AnonTest3(object): pass

k1 = None

def test_anondatamap():

	m = base.AnonymDataMapping(AnonTest)

	# used in other test function.
	global k1

	k1 = m['test1']
	k2 = m['test2']

	assert k1 != k2

	k3 = m['test1']

	assert k1 == k3

	# NOTE: we don't clear the "m", to test it correctly
	# reloads in next function.
	assert os.path.exists(m.path)
def test_anondatamap_back():
	m2 = base.AnonymDataMapping(AnonTest)

	k12 = m2['test1']

	assert k1 == k12

	# Don't clear, we need to raise the error in next function.
	#m2.clear()
	#assert not os.path.exists(m2.path)
	return
def test_anondatamap_sha1():

	# this should raise because we use the same origin
	# class with pre-existing data, with a different
	# key generator.
	with py.test.raises(exceptions.LicornRuntimeError):
		m = base.AnonymDataMapping(AnonTest, genfunc=base.sha1)

	# OK, it raised; now clear and clean.
	m2 = base.AnonymDataMapping(AnonTest)
	m2.clear()
	assert not os.path.exists(m2.path)

	m = base.AnonymDataMapping(AnonTest2, genfunc=base.sha1)

	k1 = m['test1']
	k2 = m['test2']

	assert k1 != k2

	k3 = m['test1']

	assert k1 == k3

	m.clear()
	assert not os.path.exists(m.path)
def test_anondatamap_uuid():
	m = base.AnonymDataMapping(AnonTest3, genfunc=base.uuid4)

	k1 = m['test5']
	k2 = m['test6']

	assert k1 != k2

	k3 = m['test5']

	assert k1 == k3

	m.clear()
	assert not os.path.exists(m.path)
