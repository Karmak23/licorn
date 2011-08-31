# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

hlstr - High-Level String functions and common regexs.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import re
from licorn.foundations        import exceptions
from licorn.foundations.styles import *

# please, just in case: never forget to read http://sed.sourceforge.net/sed1line.txt

# common regexs used in various places of licorn.core.*
regex = {}
regex['uri']          = r'''^(?P<protocol>\w+s?)://(?P<host>\S+)(?P<port>(:\d+)?).*$'''
regex['profile_name'] = ur'''^[\w]([-_\w ]*[\w])?$'''
# REGEX discussion: shouldn't we disallow #$*!~& in description regexes ?
# these characters could lead to potential crash/vulnerabilities. But refering
# to passwd(5), there are no restrictions concerning the description field.
# Thus we just disallow “:” to avoid a new field to be accidentally created.
regex['description']  = u'''^[-@#~*!¡&_…{}—–™®©/'"\w«»“”() ,;.¿?‘’€⋅]*$'''
regex['group_name']   = '''^[a-z]([-_.a-z0-9]*[a-z0-9][$]?)?$'''
regex['login']        = '''^[a-z][-_.a-z0-9]*[a-z0-9]$'''
regex['keyword']      = u'''^[a-z][- _./\w]*[a-z0-9]$'''
# IP regexxes come from http://stackoverflow.com/questions/319279/how-to-validate-ip-address-in-python/319293#319293
regex['ipv4']         = r'''^(?:(?:[3-9]\d?|2(?:5[0-5]|[0-4]?\d)?|1\d{0,2}|0x0*[0-9a-f]{1,2}|0+[1-3]?[0-7]{0,2})(?:\.(?:[3-9]\d?|2(?:5[0-5]|[0-4]?\d)?|1\d{0,2}|0x0*[0-9a-f]{1,2}|0+[1-3]?[0-7]{0,2})){3})$'''
# stripped out from the IPv4: short (hexa-)decimal forms, not commonly seen and error-prone to match standard integers: |0x0*[0-9a-f]{1,8}|0+[0-3]?[0-7]{0,10}|429496729[0-5]|42949672[0-8]\d|4294967[01]\d\d|429496[0-6]\d{3}|42949[0-5]\d{4}|4294[0-8]\d{5}|429[0-3]\d{6}|42[0-8]\d{7}|4[01]\d{8}|[1-3]\d{0,9}|[4-9]\d{0,8}
regex['conf_comment'] = u'''^(#.*|\s*)$'''
regex['ipv6']         = r'''^(?!.*::.*::)(?:(?!:)|:(?=:))(?:[0-9a-f]{0,4}(?:(?<=::)|(?<!::):)){6}(?:[0-9a-f]{0,4}(?:(?<=::)|(?<!::):)[0-9a-f]{0,4}(?:(?<=::)|(?<!:)|(?<=:)(?<!::):)|(?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)){3})$'''
regex['ether_addr']   = '''^([\da-f]+:){5}[\da-f]+$'''
regex['duration']     = '''^(infinite|\d+[dhms])$'''
regex['ip_address']   = r'(?:' + regex['ipv4'] + r'|' + regex['ipv6'] + r')'

# precompile all these to gain some time in the licorn daemon.
cregex = {}
cregex['uri']          = re.compile(regex['uri'],          re.IGNORECASE)
cregex['profile_name'] = re.compile(regex['profile_name'], re.IGNORECASE | re.UNICODE)
cregex['description']  = re.compile(regex['description'],  re.IGNORECASE | re.UNICODE)
cregex['group_name']   = re.compile(regex['group_name'],   re.IGNORECASE)
cregex['login']        = re.compile(regex['login'],        re.IGNORECASE)
cregex['keyword']      = re.compile(regex['keyword'],      re.IGNORECASE | re.UNICODE)
cregex['conf_comment'] = re.compile(regex['conf_comment'], re.IGNORECASE | re.UNICODE)
cregex['ipv4']         = re.compile(regex['ipv4'],         re.IGNORECASE)
cregex['ipv6']         = re.compile(regex['ipv6'],         re.IGNORECASE)
cregex['ip_address']   = re.compile(regex['ip_address'],   re.IGNORECASE)
cregex['ether_addr']   = re.compile(regex['ether_addr'],   re.IGNORECASE)
cregex['duration']     = re.compile(regex['duration'],     re.IGNORECASE)

def validate_name(s, aggressive=False, maxlenght=128, custom_keep='-.'):
	""" make a valid login or group name from a random string.
		Replace accentuated letters with non-accentuated ones, replace spaces, lower the name, etc.
	"""
	s = s.lower()

	# TODO: see if there are not any special characters to replace…
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

	# delete any strange (or forgotten by translation map…) char left
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
def word_fuzzy_match(part, word):
	""" This is a basic but kind of exact fuzzy match. ``part`` matches ``word``
		if every char of part is present in word, and in the same order.

		For more information on real fuzzy matching (which was not what I was
		looking for, thus I wrote this function), see:

		* http://stackoverflow.com/questions/682367/good-python-modules-for-fuzzy-string-comparison (best)
		* http://code.activestate.com/recipes/475148-fuzzy-matching-dictionary/ (a derivative real example)
		* http://stackoverflow.com/questions/2923420/fuzzy-string-matching-algorithm-in-python
		* http://ginstrom.com/scribbles/2007/12/01/fuzzy-substring-matching-with-levenshtein-distance-in-python/

		"""
	last = 0

	for char in part:
		current = word[last:].find(char)

		if current == -1:
			return None

		last = current

	# if we got out of the for loop without returning None, the part
	# matched, this is a success. Announce it.
	return word
def word_match(word, valid_words):
	""" try to find what the user specified on command line. """

	#print '>> match', word, 'in', valid_words, '(', remove, ' removed).'

	for a_try in valid_words:
		if word == a_try:
			# we won't get anything better than this
			return a_try

	first_match = None

	for a_try in valid_words:
		if a_try.startswith(word):
			if first_match is None:
				#print '>> partial match', a_try, 'continuing for disambiguity.'
				first_match = a_try

			else:
				raise exceptions.BadArgumentError(_('Ambiguous mode {0} '
					'(matches at least {1} and {2}).').format(
						stylize(ST_BAD, word),
						stylize(ST_COMMENT, first_match),
						stylize(ST_COMMENT, a_try)))

	# return an intermediate partial best_result, if it exists, else
	# continue for partial matches.
	if first_match:
		return first_match

	for a_try in valid_words:
		if word_fuzzy_match(word, a_try):
			if first_match is None:
				#print '>> fuzzy match', a_try, 'continuing for disambiguity.'
				first_match = a_try

			else:
				raise exceptions.BadArgumentError(_('Ambiguous mode {0} '
					'(matches at least {1} and {2}).').format(
						stylize(ST_BAD, word),
						stylize(ST_COMMENT, first_match),
						stylize(ST_COMMENT, a_try)))

	return first_match
def multi_word_match(word, valid_words):
	""" try to find what the user specified on command line. """

	matched = set()

	for a_try in valid_words:
		if word in a_try or word_fuzzy_match(word, a_try):
			matched.add(a_try)

	return list(matched)
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
