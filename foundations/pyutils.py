# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

pyutils - Pure Python utilities functions, which are not present in python 2.4

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import re, math
from gettext import gettext as _

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
def keep_true(x, y):
	""" function used in reduce(), keepping only True values in lists. """

	if x is True: return x
	else:         return y
def format_time_delta(delta_in_seconds, use_neg=False, long_output=True,
	big_precision=False):
	""" build a time-related human readable string from a time given in seconds.
		How the delta is used is function of the arguments (it can be a time in
		the past or in the future). """

	if use_neg:
		if delta_in_seconds < 0:
			time_delta_string_wrapper = _('%s ago')
			delta_in_seconds = abs(delta_in_seconds)
		else:
			time_delta_string_wrapper = _('in %s')
	else:
		time_delta_string_wrapper = '%s'

	time_delta_string = ''

	if long_output:
		sep1            = ', '
		sep2            = ' '
		year_text       = _('%d year%s')
		month_text      = _('%dm%s')
		day_text        = _('%d day%s')
		hour_text       = _('%d hour%s')
		min_text        = _('%d min%s')
		second_text     = _('%d sec%s')
		big_second_text = _('%.4f sec%s')

	else:
		sep1            = ''
		sep2            = ''
		year_text       = _('%dy%s')
		month_text      = _('%dm%s')
		day_text        = _('%dd%s')
		hour_text       ='%d%sh'
		min_text        ='%d%sm'
		second_text     ='%d%ss'
		big_second_text ='%.4fs%s'

	time_delta_sec  = delta_in_seconds
	time_delta_min  = 0
	time_delta_hour = 0
	time_delta_day  = 0
	time_delta_year = 0
	s_year = ''
	s_day  = ''
	s_hour = ''
	s_sec  = ''
	s_min  = ''
	if time_delta_sec > 60:
		time_delta_min = math.floor(time_delta_sec / 60)
		time_delta_sec -= (time_delta_min * 60)
		if time_delta_min > 60:
			time_delta_hour = math.floor(time_delta_min / 60)
			time_delta_min -= (time_delta_hour * 60)
			if time_delta_hour > 24:
				time_delta_day = math.floor(time_delta_hour / 24)
				time_delta_hour -= (time_delta_day * 24)
				if time_delta_day > 365:
					time_delta_year = math.floor(time_delta_day / 365)
					time_delta_day -= (time_delta_year * 365)
					if time_delta_year > 1 and long_output:
						s_year = 's'
					if time_delta_year > 0:
						time_delta_string += year_text % (
							time_delta_year, s_year)
				if time_delta_day > 1 and long_output:
					s_day = 's'
				if time_delta_day > 0:
					time_delta_string += '%s%s' % (
						sep1 if time_delta_string else '',
						day_text % (time_delta_day, s_day)
						)
			if time_delta_hour > 1 and long_output:
				s_hour = 's'
			if time_delta_hour > 0:
				time_delta_string += '%s%s' % (
					sep2 if time_delta_string else '',
					hour_text % (time_delta_hour, s_hour)
					)
		if time_delta_min > 1 and long_output:
			s_min = 's'
		if time_delta_min > 0:
			time_delta_string += '%s%s' % (
					sep2 if time_delta_string else '',
					min_text % (time_delta_min, s_min)
					)
	if time_delta_sec > 1 and long_output:
		s_sec = 's'
	if time_delta_sec > 0:
		if big_precision:
			time_delta_string += '%s%s' % (
				sep2 if time_delta_string else '',
				big_second_text % (time_delta_sec, s_sec)
			)
		else:
			time_delta_string += '%s%s' % (
				sep2 if time_delta_string else '',
				second_text % (int(time_delta_sec), s_sec)
				)

	return time_delta_string_wrapper % time_delta_string
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
		if hasattr(confdict[name], '__iter__'):
			if hasattr(confdict[name][0], '__iter__'):
				confdict[name].append(value)
			else:
				confdict[name] = [ confdict[name], value ]
		else:
			confdict[name] = [ confdict[name], value ]
	else:
		confdict[name] = value
def add_or_dupe_obj(target, name, value):
	""" add a new attribute to an object with a given value. If the attr already
		exists, make it a list and append the new value."""
	if hasattr(target, name):
		if hasattr(getattr(target, name), '__iter__'):
			if hasattr(getattr(target, name)[0], '__iter__'):
				getattr(target, name).append(value)
			else:
				setattr(target, name, [ getattr(target, name), value ])
		else:
			setattr(target, name, [ getattr(target, name), value ])
	else:
		setattr(target, name, [ value ])
def add_or_dupe_attr(target, value):
	""" add a new attribute to an object with a given value. If the attr already
		exists, make it a list and append the new value."""
	if target is None:
		target = [ value ]
	else:
		if hasattr(target, '__iter__'):
			if hasattr(target[0], '__iter__'):
				target.append(value)
			else:
				target = [ target, value ]
		else:
			target = [ target, value ]
