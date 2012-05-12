# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

hlstr tests - testsuite for hlstr

:copyright:
	* 2012 Olivier Cortès <olive@deep-ocean.net>
	* 2012 META IT http://meta-it.fr/
	* 2012 Olivier Cortès <oc@meta-it.fr>
:license: GNU GPL version 2
"""

import os, stat, py.test

import logging, exceptions, process, hlstr

def test_word_match():

	wm = hlstr.word_match
	wlist = [ 'extensions', 'backends', 'configuration' ]

	assert wm('ext', wlist) == 'extensions'
	assert wm('nope', wlist) == None

	# could match 'extensions' and 'backends'
	py.test.raises(exceptions.BadArgumentError, wm, 'ns', wlist)

	# could match 'extensions' and 'configuration'
	py.test.raises(exceptions.BadArgumentError, wm, 'ni', wlist)
