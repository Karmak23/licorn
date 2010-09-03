# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

hlstr - High-Level String functions and common regexs.

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2

"""

import re
from licorn.foundations import exceptions

# common regexs used in various places of licorn.core.*
regex = {}
regex['uri']          = u'''^(?P<protocol>\w+s?)://(?P<host>\S+)(?P<port>(:\d+)?).*$'''
regex['profile_name'] = u'''^[\w]([-_\w ]*[\w])?$'''
# REGEX discussion: shouldn't we disallow #$*!~& in description regexes ?
# these characters could lead to potential crash/vulnerabilities. But refering
# to passwd(5), there are no restrictions concerning the description field.
# Thus we just disallow “:” to avoid a new field to be accidentally created.
regex['description']  = u'''^[-@#~*!¡&_…{}—–™®©/'"\w«»“”() ,;.¿?‘’€⋅]*$'''
regex['group_name']   = u'''^[a-z]([-_.a-z0-9]*[a-z0-9][$]?)?$'''
regex['login']        = u'''^[a-z][-_.a-z0-9]*[a-z0-9]$'''
regex['keyword']      = u'''^[a-z][- _./\w]*[a-z0-9]$'''
regex['conf_comment'] = u'''^(#.*|\s*)$'''
regex['ipv4']         = u'''^\d+\.\d+\.\d+\.\d+$'''
regex['ether_addr']   = u'''^([\da-f]+:){5}[\da-f]+$'''
regex['duration']     = u'''^(infinite|\d+[dhms])$'''


# precompile all these to gain some time (in the licorn daemon).
cregex = {}
cregex['uri']          = re.compile(regex['uri'],          re.IGNORECASE)
cregex['profile_name'] = re.compile(regex['profile_name'], re.IGNORECASE | re.UNICODE)
cregex['description']  = re.compile(regex['description'],  re.IGNORECASE | re.UNICODE)
cregex['group_name']   = re.compile(regex['group_name'],   re.IGNORECASE | re.UNICODE)
cregex['login']        = re.compile(regex['login'],                        re.UNICODE)
cregex['keyword']      = re.compile(regex['keyword'],      re.IGNORECASE | re.UNICODE)
cregex['conf_comment'] = re.compile(regex['conf_comment'], re.IGNORECASE | re.UNICODE)
cregex['ipv4']         = re.compile(regex['ipv4'],         re.IGNORECASE | re.UNICODE)
cregex['ether_addr']   = re.compile(regex['ether_addr'],   re.IGNORECASE | re.UNICODE)
cregex['duration']     = re.compile(regex['duration'],     re.IGNORECASE | re.UNICODE)


def validate_name(s, aggressive = False, maxlenght = 128, custom_keep = '-.'):
	""" make a valid login or group name from a random string.
		Replace accentuated letters with non-accentuated ones, replace spaces, lower the name, etc.
	"""
	s = s.lower()

	# TODO: see if there are not any special characters to replace...
	translation_map = {
						u'à': u'a',
						u'â': u'a',
						u'ä': u'a',
						u'ã': u'a',
						u'æ': u'ae',
						u'ç': u'c',
						u'é': u'e',
						u'è': u'e',
						u'ê': u'e',
						u'ë': u'e',
						u'î': u'i',
						u'ï': u'i',
						u'ì': u'i',
						u'í': u'i',
						u'ñ': u'n',
						u'ô': u'o',
						u'ö': u'o',
						u'ò': u'o',
						u'õ': u'o',
						u'œ': u'oe',
						u'ú': u'u',
						u'ù': u'u',
						u'û': u'u',
						u'ü': u'u',
						u'ŷ': u'y',
						u'ÿ': u'y',
						u'ý': u'y',
						u'ß': u'ss',
						u"'": u'',
						u'"': u'',
						u' ': u'_'
						}

	for elem in translation_map:
		s = s.replace(elem, translation_map[elem])

	import re

	# delete any strange (or forgotten by translation map...) char left
	if aggressive:
		s = re.sub('[^.a-z0-9]', '', s)
	else:
		# keep dashes (or custom characters)
		s = re.sub('[^%sa-z0-9]' % custom_keep, '', s)

	# strip remaining doubles punctuations signs
	s = re.sub( r'([-._])[-._]*', r'\1', s)

	# strip left and rights punct signs
	s = re.sub( r'(^[-._]*|[-._*]*$)', '', s)

	if len(s) > maxlenght:
		raise exceptions.LicornRuntimeError("String %s too long (%d characters, but must be shorter or equal than %d)." % (s, len(s), maxlenght))

	# return a standard string (not unicode), because a login/group_name don't include
	# accentuated letters or such strange things.
	return str(s)
def generate_salt(maxlen = 12):
	"""Generate a random password."""

	import random

	# ascii table: 48+ = numbers, 65+ = upper letter, 97+ = lower letters
	special_chars = [ '.', '/' ]

	special_chars_count = len(special_chars) -1

	salt = ""

	for i in range(0, maxlen):
		char_type = random.randint(1, 4)

		if char_type < 3:
			number = random.randint(0, 25)

			if char_type == 1:
				# an uppercase letter
				salt += chr(65 + number)
			else:
				# a lowercase letter
				salt += chr(97 + number)
		else:
			if char_type == 3:
				# a number
				salt += str(random.randint(0, 9))
			else:
				# a special char
				number = random.randint(0, special_chars_count)
				salt += special_chars[number]

	return salt
def generate_password(maxlen = 12, use_all_chars = False):
	"""Generate a random password."""

	import random

	# ascii table: 48+ = numbers, 65+ = upper letter, 97+ = lower letters
	special_chars = [ '.', '/',  '_', '*', '+', '-', '=', '@' ]

	if use_all_chars:
		special_chars.extend([ '$', '%', '&', '!', '?', '(', ')', ',',
			':', ';', '<', '>', '[', ']', '{', '}' ])

	special_chars_count = len(special_chars) -1

	password = ""

	for i in range(0, maxlen):
		char_type = random.randint(1, 4)

		if char_type < 3:
			number = random.randint(0, 25)

			if char_type == 1:
				# an uppercase letter
				password += chr(65 + number)
			else:
				# a lowercase letter
				password += chr(97 + number)
		else:
			if char_type == 3:
				# a number
				password += str(random.randint(0, 9))
			else:
				# a special char
				number = random.randint(0, special_chars_count)
				password += special_chars[number]

	return password
def statsize2human(size):
	""" Convert an integer size (coming from a stat object) to a Human readable string.

		TODO: NLS this !
		TODO: I heard of a python package already doing this. remove this functions when found.
	"""
	size *= 1.0
	unit = 'byte(s)'

	if size > 1024:
		size /= 1024.0
		unit = 'Kib'
	if size > 1024:
		size /= 1024.0
		unit = 'Mib'
	if size > 1024:
		size /= 1024.0
		unit = 'Gib'
	if size > 1024:
		size /= 1024.0
		unit = 'Tib'
	if size > 1024:
		size /= 1024.0
		unit = 'Pib'
	return '%d %s' % (round(size), unit)
