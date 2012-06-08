# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

`pyutils` - Pure Python [low-level] utilities functions, which are not present in python 2.x

:copyright:
	* 2007-2012 Olivier Cortès <olive@deep-ocean.net>
	* 2012 META IT http://meta-it.fr/
:license:
	* GNU GPL version 2
"""

import re, math, functools
from traceback import print_exc

# WARNING: don't import anything from the core here.

# ============================================================= Licorn® imports
import exceptions, logging, styles
from _options  import options
from styles    import *
from ltrace    import *
from ltraces   import *
from constants import verbose

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

max_string_size = 128

def catch_exception(func):
	@functools.wraps(func)
	def wrap(*a, **kw):

		try:
			assert ltrace(TRACE_PYUTILS, 'RUN {0}({1}, {2})', func.__name__, str(a), str(kw))

			res = func(*a, **kw)

			assert ltrace(TRACE_PYUTILS, 'RETURN {0}', res)

			return res

		except Exception, e:
			# We need to truncate the output in case of a very long one. As
			# __str__() and __repr__() methods of the core often list all
			# elements, this is wanted.
			#s
			# http://stackoverflow.com/questions/2872512/python-truncate-a-long-string
			logging.exception(_('Exception {0} while running {1}({2}{3}{4})'),
					type(e).__name__, func.__name__,
					', '.join(str(i)[:max_string_size] + (
							str(i)[max_string_size:] and stylize(ST_COMMENT, '… (truncated)')) for i in a),
					', ' if a and kw else '',
					', '.join('{0}={1}'.format(str(k), str(v)[:max_string_size]
							+ (str(v)[max_string_size:] and stylize(ST_COMMENT, '… (truncated)')))
						for k, v in kw.iteritems()))
	return wrap
def resolve_attr(multi_attr_str, globals_):
	""" Given an argument string "object.attr1.attr2", return `attr2`
		as a usable python object.  """

	attrs        = multi_attr_str.split('.')
	current_attr = globals_[attrs[0]]

	for attr_name in attrs[1:]:
		current_attr = getattr(current_attr, attr_name)

	return current_attr
def print_exception_if_verbose():
	if options.verbose >= verbose.INFO:
		print_exc()
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
		out_set.append(elem)
	return out_set
def keep_false(x, y):
	""" function used in reduce(), keepping only False values in lists. """

	if x is False: return x
	else:          return y
def keep_true(x, y):
	""" function used in reduce(), keepping only True values in lists. """

	if x is True: return x
	else:         return y
def bytes_to_human(bytes, as_string=True, binary=True):
	""" From http://fr.wikipedia.org/wiki/Octet (in french in the text). """

	bytes = float(bytes)

	if binary:
		if bytes >= 1180591620717411303424L:
			# yobibytes
			size_val = bytes / 1180591620717411303424L
			size_str = _(u'{0:.2f}Yib')
		elif bytes >= 1152921504606846976L:
			# zebibytes
			size_val = bytes / 1152921504606846976L
			size_str = _(u'{0:.2f}Zib')
		elif bytes >= 1125899906842624L:
			# exbibytes
			size_val = bytes / 1125899906842624L
			size_str = _(u'{0:.2f}Eib')
		elif bytes >= 1125899906842620:
			# pebibytes
			size_val = bytes / 1125899906842620
			size_str = _(u'{0:.2f}Pib')
		elif bytes >= 1099511627776:
			# tebibytes
			size_val = bytes / 1099511627776
			size_str = _(u'{0:.2f}Tib')
		elif bytes >= 1073741824:
			# gibibytes
			size_val = bytes / 1073741824
			size_str = _(u'{0:.2f}Gib')
		elif bytes >= 1048576:
			# mebibytes
			size_val = bytes / 1048576
			size_str = _(u'{0:.2f}Mib')
		elif bytes >= 1024:
			#kibibytes
			size_val = bytes / 1024
			size_str = _(u'{0:.2f}Kib')
		else:
			size_val = bytes
			size_str = (u'{0:.2f}b')
	else:
		if bytes >= 1000000000000000000000000L:
			#yottabytes
			size_val = bytes / 1000000000000000000000000L
			size_str = _(u'{0:.2f}Yib')
		elif bytes >= 1000000000000000000000L:
			# zettabytes
			size_val = bytes / 1000000000000000000000L
			size_str = _(u'{0:.2f}Zib')
		elif bytes >= 1000000000000000000L:
			# exabytes
			size_val = bytes / 1000000000000000000L
			size_str = _(u'{0:.2f}Eib')
		elif bytes >= 1000000000000000L:
			# petabytes
			size_val = bytes / 1000000000000000L
			size_str = _(u'{0:.2f}Pib')
		elif bytes >= 1000000000000:
			# terabytes
			size_val = bytes / 1000000000000
			size_str = _(u'{0:.2f}Tib')
		elif bytes >= 1000000000:
			# gigabytes
			size_val = bytes / 1000000000
			size_str = _(u'{0:.2f}Gib')
		elif bytes >= 1000000:
			# megabytes
			size_val = bytes / 1000000
			size_str = _(u'{0:.2f}Mib')
		elif bytes >= 1000:
			# kilobytes
			size_val = bytes / 1000
			size_str = _(u'{0:.2f}Kib')
		else:
			size_val = bytes
			size_str = (u'{0:.2f}b')

	if as_string:
		return size_str.format(size_val)
	else:
		return size_val
def format_time_delta(delta_in_seconds, use_neg=False, long_output=True,
														big_precision=False):
	""" Build a time-related human readable string from a time given in seconds.
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
		year_text       = _('{0} year{1}')
		month_text      = _('{0}m{1}')
		day_text        = _('{0} day{1}')
		hour_text       = _('{0} hour{1}')
		min_text        = _('{0} min{1}')
		second_text     = _('{0} sec{1}')
		big_second_text = _('{0:.4f} sec{1}')

	else:
		sep1            = ''
		sep2            = ''
		year_text       = _('{0}y{1}')
		month_text      = _('{0}m{1}')
		day_text        = _('{0}d{1}')
		hour_text       ='{0}{1}h'
		min_text        ='{0}{1}m'
		second_text     ='{0}{1}s'
		big_second_text ='{0:.4f}s{1}'

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
						time_delta_string += year_text.format(
							int(time_delta_year), s_year)
				if time_delta_day > 1 and long_output:
					s_day = 's'
				if time_delta_day > 0:
					time_delta_string += '%s%s' % (
						sep1 if time_delta_string else '',
						day_text.format(int(time_delta_day), s_day)
						)
			if time_delta_hour > 1 and long_output:
				s_hour = 's'
			if time_delta_hour > 0:
				time_delta_string += '%s%s' % (
					sep2 if time_delta_string else '',
					hour_text.format(int(time_delta_hour), s_hour)
					)
		if time_delta_min > 1 and long_output:
			s_min = 's'
		if time_delta_min > 0:
			time_delta_string += '%s%s' % (
					sep2 if time_delta_string else '',
					min_text.format(int(time_delta_min), s_min)
					)
	if time_delta_sec > 1 and long_output:
		s_sec = 's'
	if time_delta_sec > 0:
		if big_precision:
			time_delta_string += '%s%s' % (
				sep2 if time_delta_string else '',
				big_second_text.format(time_delta_sec, s_sec)
			)
		else:
			time_delta_string += '%s%s' % (
				sep2 if time_delta_string else '',
				second_text.format(int(time_delta_sec), s_sec)
				)

	return time_delta_string_wrapper % time_delta_string
def check_file_against_dict(conf_file, defaults, configuration,
										batch=False, auto_answer=None):
	''' Check if a file has some configuration directives,
	and check against values if given.
	If the value is None, only the directive existence is tested. '''

	# FIXME: move out configuration and use LMC.configuration
	# FIXME 2: move this method out of here (if it needs LMC,
	# it must not be in foundations)!!

	from licorn.foundations import readers

	conf_file_alter = False
	conf_file_data  = open(conf_file, 'r').read()
	conf_file_dict  = readers.simple_conf_load_dict(data=conf_file_data)

	for (directive, value) in defaults:
		if not conf_file_dict.has_key(directive):

			logging.warning(_(u'Inserted missing directive {1} in {0}.').format(
					stylize(ST_PATH, conf_file),
					stylize(ST_COMMENT, directive)))

			conf_file_alter           = True
			conf_file_dict[directive] = value
			conf_file_data            = '%s %s\n%s' % (
				directive, value, conf_file_data)

		if value != None and conf_file_dict[directive] != value:

			logging.warning(_(u'modified {0} directive {1} to be equal to {2} '
				u'(was originaly {3}).').format(
					stylize(ST_PATH, conf_file),
					stylize(ST_REGEX, directive),
					stylize(ST_OK, value),
					stylize(ST_BAD, conf_file_dict[directive])))

			conf_file_alter           = True
			conf_file_dict[directive] = value
			conf_file_data            = re.sub(r'%s.*' % directive,
				r'%s	%s' % (directive, value), conf_file_data)

		# else:
		# everything is OK, just pass.

	if conf_file_alter:
		if batch or logging.ask_for_repair(_(u'Modify {0} on disk to '
				u'reflect current in-memory changes?').format(
					stylize(ST_PATH, conf_file)), auto_answer):
			try:
				open(conf_file, 'w').write(conf_file_data)

				logging.notice(_(u'Altered {0} to match {1} '
					u'pre-requisites.').format(
					stylize(ST_PATH, conf_file),
						stylize(ST_NAME, configuration.app_name)))
			except (IOError, OSError), e:
				if e.errno == 13:
					raise exceptions.LicornRuntimeError(_(u'Insufficient '
						u'permissions. Are you root?\n\t{0}').format(e))
				else:
					raise e
		else:
			raise exceptions.LicornRuntimeError(_(u'Modifications in {0} are '
				u'mandatory for {1} to work properly. Cannot continue without '
				u'this, sorry!').format(stylize(ST_PATH, conf_file),
						stylize(ST_NAME, configuration.app_name)))

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
	if name in confdict.keys():
		if hasattr(confdict[name], '__iter__'):
			if hasattr(confdict[name][0], '__iter__'):
				confdict[name].append(value)
			else:
				confdict[name] = [ confdict[name], value ]
		else:
			confdict[name] = [ confdict[name], value ]
	else:
		confdict[name] = value
def add_or_dupe_enumeration(enumeration, name, value):
	""" when adding a new entry into an enumeration, verify if an already
	existing entry doesn't exist. If it is already present, make the current
	value become the first value of a list, and append the new value. if value
	is already a list, just append at the end."""
	if name in enumeration.keys():
		if hasattr(enumeration[name], '__iter__'):
			enumeration[name].append(value)
		else:
			enumeration[name] = [ enumeration[name], value ]
	else:
		enumeration[name] = value
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
def expand_vars_and_tilde(text, uid=None):

	from licorn.core         import LMC
	user_home = LMC.users[uid]['homeDirectory'] if uid else ''

	return text.replace(
			'~', user_home).replace(
			'$HOME', user_home).replace(
			user_home, '')
def warn_exception(message, *args):
	logging.warning(message.format(*args))
	print_exception_if_verbose()
def warn2_exception(message, *args):
	logging.warning2(message.format(*args))
	print_exception_if_verbose()
def resolve_dependancies_from_dict_strings(arg):
	""" Gently taken from http://code.activestate.com/recipes/576570/ (r4)
		Dependency resolver

	"arg" is a dependency dictionary in which
	the values are the dependencies of their respective keys.

	Example:
		d=dict(
			a=('b','c'),
			b=('c','d'),
			e=(),
			f=('c','e'),
			g=('h','f'),
			i=('f',)
		)
		print dep(d)
	"""

	d = dict((k, set(arg[k])) for k in arg)
	r = []

	while d:
		# values not in keys (items without dep)
		t = set(i for v in d.values() for i in v) - set(d.keys())

		# and keys without value (items without dep)
		t.update(k for k, v in d.items() if not v)

		# can be done right away

		# the original code stated "r.append(t)". We "flaten" the list here
		# because we just need a list of things to load/check sequencially.
		r.extend(list(t))

		# and cleaned up
		d = dict( ((k, v - t) for k, v in d.items() if v) )

	return r
def merge_dicts_of_lists(*args, **kwargs):
	""" From *dicts, return a new (copy). Eg::

			{ 1: [2, 3] } + { 1: [4, 5] } => { 1: [2, 3, 4, 5] }

		If values doesn't understand '.extend()', the right-outer has always
		precedence, eg::

			{1: True}  + {1: False} => {1: False}
			{1: False} + {1: True}  => {1: True}

		Tips from http://stackoverflow.com/questions/38987/how-can-i-merge-two-python-dictionaries-as-a-single-expression

		worth a read: http://stackoverflow.com/questions/2365921/merging-python-dictionaries
	"""
	new_dict = args[0].copy()

	unique = kwargs.pop('unique', False)

	for other_dict in args[1:]:
		for key, value in other_dict.iteritems():
			try:
				if unique:
					new_dict[key] = list(set(new_dict[key]) | set(value[:]))
				else:
					new_dict[key].extend(value[:])

			except (KeyError, AttributeError, TypeError):
				if unique:
					new_dict[key] = value
				else:
					new_dict[key] = list(set(value))
	return new_dict


def MixIn(TargetClass, MixInClass, name=None):
    if name is None:
        name = "mixed_%s_with_%s" % (TargetClass.__name__, MixInClass.__name__)

    class CombinedClass(TargetClass, MixInClass):
        pass

    CombinedClass.__name__ = name
    return CombinedClass
