# -*- coding: utf-8 -*-
"""
squid extension testing

:copyright: 2011 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2

"""
import sys, os, py.test, copy

from licorn.foundations         import exceptions
from licorn.foundations.config  import *
from licorn.extensions.squid    import *

LSCF = LicornSquidConfigurationFile

ts_data_path = os.path.dirname(__file__) + '/../../tests/data/squid3/'

s1 = LSCF(filename=ts_data_path	+ 'squid.conf.orig.short')
s2 = LSCF(filename=ts_data_path + 'squid.conf.orig.short.same')
s3 = LSCF(filename=ts_data_path + 'squid.conf.orig.short.different')
s4 = LSCF(filename=ts_data_path + 'squid.conf.orig')

def bad_config_syntax(filename):
	""" Just instanciate from the filename. The given file should have a
		syntax or ordering error in it, and the constructor will raise an
		exception, which is what is intended. """

	LSCF(filename=ts_data_path + filename)
def bad_config_syntax_func(filename):
	""" just a wrapper, to avoid strange and unrelated long messages in
		py.test outputs. """

	py.test.raises(exceptions.BadConfigurationError, bad_config_syntax, filename)
def print_file(f):
	""" Small helper used to debug the testsuite and file contents, to be sure
		results are the ones that we want to acheive. """
	print '>>', f, '\n'.join('%s, %s' % (x.name, x.lineno) for x in f.directives)

def test_parse_and_rewrite():
	""" assumes the lexer does an acceptable job, to be able to output the
		file exactly the same way it was before.

		this doesn't verify the tokens are built correctly, though. Improperly
		splitted tokens can still produce a valid final output.
	"""

	assert open(ts_data_path + 'squid.conf.orig.short', 'rb').read() == s1.to_string()
def test_search():

	py.test.raises(ValueError, s1.find)

	assert s1.has(directive_name='prout') == False

	directive = copy.deepcopy(s1.directives[1])

	assert s1.has(directive) == True
	assert s1.has(directive, match_value=False) == True
	assert s1.has(directive_name=directive.name) == True

	assert s1.find(directive) == directive

	assert s1.find(directive, match_value=False) == s1.directives[0]
	assert s1.find(directive, match_value=False) != s1.directives[1]

	assert s1.find(directive_name=directive.name) == s1.directives[0]
	assert s1.find(directive_name=directive.name) != s1.directives[1]

	# create a non-existing directive (same name, different value)

	directive.value[-1].value = 'other_value'

	assert s1.has(directive) == False
	assert s1.has(directive, match_value=False) == True
	assert s1.has(directive_name=directive.name) == True

	py.test.raises(ValueError, s1.find, directive)
	py.test.raises(PartialMatch, s1.find, directive, partial_match=True)

	assert s1.find(directive, match_value=False) == s1.directives[0]
	assert s1.find(directive, match_value=False) != s1.directives[1]

	try:
		s1.find(directive, partial_match=True)

	except PartialMatch, e:
		assert e.match == s1.directives[0]
		assert e.match != s1.directives[1]
def test_equality():
	assert s1 == s2
	assert s1 != s3
	assert s2 != s3

	#print_file(s1)
	#print_file(s4)

	assert s1 == s4
	assert s2 == s4
def test_bad_config_syntax_or_ordering():
	"""
		.. todo:: create a test for the "manager" part of  ``*_access``
			directives when the check-related code is implemented.
	"""

	for filename in ('squid.conf.orig.short.baddly_written_01',
					'squid.conf.orig.short.baddly_written_02',
					'squid.conf.orig.short.bad_ordering_01',
					'squid.conf.orig.short.bad_ordering_02'):
		yield bad_config_syntax_func, filename
def test_merge_basic():
	m1 = LSCF(filename=ts_data_path + 'squid.conf.test_merge.1.start')
	m2 = LSCF(filename=ts_data_path + 'squid.conf.test_merge.2.part_to_merge', snipplet=True)
	m3 = LSCF(filename=ts_data_path + 'squid.conf.test_merge.3.final')

	m1.merge(m2)

	assert m1.changed

	# The 2 instances should be equal. This is the important test.
	assert m1 == m3

	# As there are many ways to write the same file, these stringified
	# versions will be different (the .final file was voluntarily made to be).
	assert m1.to_string() != m3.to_string()
def test_merge_standard_from_existing():
	""" This test should be activated when the feature is ready.

		As of 20121008, merging anything into an empty ConfigurationFile
		doesn't work as expected.
	"""

	os.chdir('/usr/share/licorn/extensions/squid/data')

	# start with an empty file.
	m1 = LSCF(filename='squid.minimal.test.conf')

	m1.merge(LSCF(filename='squid.replacements.conf', snipplet=True), partial_match=True, on_conflict='replace')
	#print '>> +replacements', m1.to_string()
	assert m1.changed

	m1.merge(LSCF(filename='squid.licorn_lan_1.conf', snipplet=True), partial_match=True, on_conflict='replace')
	#print '>> +lan_1', m1.to_string()
	assert m1.changed

	m1.merge(LSCF(filename='squid.licorn_lan_2.conf', snipplet=True))
	#print '>> +lan_2\n', m1.to_string()
	assert m1.changed

	mcheck = LSCF(filename='squid.merged.for_check.conf')
	#print '>> +check\n', mcheck.to_string()
	assert m1 == mcheck
def test_merge_standard_from_empty():
	""" Same test as previous, but starting from an empty file. Should bring
		up the same result. """

	os.chdir('/usr/share/licorn/extensions/squid/data')

	# start with an empty file.
	m1 = LSCF(text='')

	m1.merge(LSCF(filename='squid.minimal.test.conf'))

	m1.merge(LSCF(filename='squid.replacements.conf', snipplet=True), partial_match=True, on_conflict='replace')
	#print '>> +replacements', m1.to_string()
	assert m1.changed

	m1.merge(LSCF(filename='squid.licorn_lan_1.conf', snipplet=True), partial_match=True, on_conflict='replace')
	#print '>> +lan_1', m1.to_string()
	assert m1.changed

	m1.merge(LSCF(filename='squid.licorn_lan_2.conf', snipplet=True))
	#print '>> +lan_2\n', m1.to_string()
	assert m1.changed

	mcheck = LSCF(filename='squid.merged.for_check.conf')
	#print '>> +check\n', mcheck.to_string()
	assert m1 == mcheck
def test_wipe():
	m1 = LSCF(filename=ts_data_path + 'squid.conf.test_merge.1.start')
	m2 = LSCF(filename=ts_data_path + 'squid.conf.test_merge.2.part_to_merge', snipplet=True)
	m3 = LSCF(filename=ts_data_path + 'squid.conf.test_merge.3.final')

	m3.wipe(m2)

	assert m3.changed

	# The 2 instances should be equal. This is the important test.
	assert m1 == m3

	# This time, due to the simple nature of the wipe operation,
	# the stringified files should be equal.
	assert m1.to_string() == m3.to_string()
