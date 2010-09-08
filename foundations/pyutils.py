# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

pyutils - Pure Python utilities functions, which are not present in python 2.4

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import re
from licorn.foundations import exceptions, logging, styles

def next_free(used_list, start, end):
	""" Find a new ID (which is not used).
		Return the smallest unused identifier in [start_id,end_id] of used_id_list.
		Note: don't sort the list before ! This function does it.
	"""
	used_list.sort()

	if start in used_list:
		cur = start + 1
		while cur in used_list:
			cur += 1
		if cur <= end:
			return cur
	else:
		return start

	raise exceptions.NoAvaibleIdentifierError()
def list2set(in_list):
	""" Transform a list to a set (ie remove duplicates). """
	out_set = []
	for elem in in_list:
		if elem in out_set: continue
		out_set.append(e)
	return out_set
def keep_false(x, y):
	""" function used in reduce(), keepping only False values in lists. """

	if x is False: return x
	else:          return y
def check_file_against_dict(conf_file, defaults, configuration,
	batch=False, auto_answer=None):
	''' Check if a file has some configuration directives,
	and check against values if given.
	If the value is None, only the directive existence is tested. '''

	from licorn.foundations import readers

	conf_file_alter = False
	conf_file_data  = open(conf_file, 'r').read()
	conf_file_dict  = readers.simple_conf_load_dict(data=conf_file_data)

	for (directive, value) in defaults:
		if not conf_file_dict.has_key(directive):

			logging.warning(
				'''%s should include directive %s, but it doesn't.''' % (
				styles.stylize(styles.ST_PATH, conf_file), directive))

			conf_file_alter           = True
			conf_file_dict[directive] = value
			conf_file_data            = '%s %s\n%s' % (
				directive, value, conf_file_data)

		if value != None and conf_file_dict[directive] != value:

			logging.warning('''%s should have directive %s be equal to %s, '''
				'''but it is %s.'''	% (
				styles.stylize(styles.ST_PATH, conf_file),
				styles.stylize(styles.ST_REGEX, directive),
				styles.stylize(styles.ST_OK, value),
				styles.stylize(styles.ST_BAD, conf_file_dict[directive])))

			conf_file_alter           = True
			conf_file_dict[directive] = value
			conf_file_data            = re.sub(r'%s.*' % directive,
				r'%s	%s' % (directive, value), conf_file_data)

		# else:
		# everything is OK, just pass.

	if conf_file_alter:
		if batch or logging.ask_for_repair(
			'''%s lacks mandatory configuration directive(s).''' % \
				styles.stylize(styles.ST_PATH, conf_file), auto_answer):
			try:
				open(conf_file, 'w').write(conf_file_data)
				logging.notice(
					'''Altered %s to match %s pre-requisites.'''
					% (styles.stylize(styles.ST_PATH, conf_file),
					configuration.app_name))
			except (IOError, OSError), e:
				if e.errno == 13:
					raise exceptions.LicornRuntimeError(
						'''Insufficient permissions. '''
						'''Are you root?\n\t%s''' % e)
				else:
					raise e
		else:
			raise exceptions.LicornRuntimeError(
			'''Modifications in %s are mandatory for %s to work '''
			'''properly. Can't continue without this, sorry!''' % (
			conf_file, configuration.app_name))

	return True
class masq_list(list):
	def __init__(self, name, data=[], separator='/'):
		list.__init__(self, data)
		self.name      = name
		self.separator = separator
	def __str__(self):
		if self.separator == '/':
			return '%s=/%s' % (self.name, '/'.join(self[:]))
		if self.separator == ',':
			return '%s=%s' % (self.name, ','.join(self[:]))
def add_or_dupe(confdict, name, value):
	""" when adding a new entry into a dict, verify if an already existing entry
	doesn't exist. If it is already present, make the current value become the
	first velue of a list, and append the new value. if value is already a list,
	just append at the end."""
	if confdict.has_key(name):
		if type(confdict[name]) == type([]):
			if type(confdict[name][0]) in (type([]), type(masq_list('dummy'))):
				confdict[name].append(value)
			else:
				confdict[name] = [ confdict[name], value ]
		else:
			confdict[name] = [ confdict[name], value ]
	else:
		confdict[name] = value
