# -*- coding: utf-8 -*-
"""
squid extension testing

:copyright: 2011 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2

"""
import sys, os, py.test, copy

from licorn.foundations         import exceptions
from licorn.foundations.config  import ConfigurationToken, ConfigurationBlock, \
										ConfigurationDirective, ConfigurationFile
from licorn.extensions.squid    import *

ts_data_path = os.path.dirname(__file__) + '/../tests/data'

s1 = ConfigurationFile(filename=ts_data_path + '/squid3/squid.conf.orig.short',
						lexer=LicornSquidConfLexer(), caller='squid')
s2 = ConfigurationFile(filename=ts_data_path + '/squid3/squid.conf.orig.short.same',
						lexer=LicornSquidConfLexer(), caller='squid')
s3 = ConfigurationFile(filename=ts_data_path + '/squid3/squid.conf.orig.short.different',
						lexer=LicornSquidConfLexer(), caller='squid')
s4 = ConfigurationFile(filename=ts_data_path + '/squid3/squid.conf.orig',
						lexer=LicornSquidConfLexer(), caller='squid')

def bad_config_syntax(filename):
	ConfigurationFile(filename=ts_data_path + filename,
							lexer=LicornSquidConfLexer(), caller='squid')

def bad_config_syntax_func(filename):
	""" just a wrapper, to avoid strange and unrelated long messages in
		py.test outputs. """
	py.test.raises(exceptions.BadConfigurationError, bad_config_syntax, filename)

def test_parser():
	""" assumes the lexer does an acceptable job, to be able to output the
		file exactly the same way it was before.

		this doesn't verify the tokens are built correctly, though. Improperly
		splitted tokens can still produce a valid final output.
	"""

	assert open(ts_data_path + '/squid3/squid.conf.orig.short', 'rb').read() == s1.to_string()
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
	py.test.raises(ConfigurationDirective, s1.find, directive, raise_partial=True)

	assert s1.find(directive, match_value=False) == s1.directives[0]
	assert s1.find(directive, match_value=False) != s1.directives[1]

	try:
		s1.find(directive, raise_partial=True)

	except ConfigurationDirective, e:
		assert e == s1.directives[0]
		assert e != s1.directives[1]
def test_equality():
	assert s1 == s2
	assert s1 != s3
	assert s2 != s3

	#def print_file(f):
	#	print '>>', f, '\n'.join('%s, %s' % (x.name, x.lineno) for x in f.directives)

	print_file(s1)
	print_file(s4)

	assert s1 == s4
	assert s2 == s4
def test_bad_config_syntax():
		for filename in ('/squid3/squid.conf.orig.short.baddly_written_01',
						'/squid3/squid.conf.orig.short.baddly_written_02'):
			yield bad_config_syntax_func, filename
