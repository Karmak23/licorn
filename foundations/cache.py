# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

cache - small in-memory cache for Licorn®.
	because memcached is overkill on thin clients, and beaker is too much for what I need.

:copyright:
	* 2012 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

import time
from functools import wraps


# ============================================================== licorn imports
import styles
from base    import ObjectSingleton
from styles  import *
from ltrace  import *
from ltraces import *

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

half_a_minute     = 30.0
one_minute        = 60.0
two_minutes       = 120.0
five_minutes      = 300.0
ten_minutes       = 600.0
half_an_hour      = 1800.0
thirty_minutes    = half_an_hour
one_hour          = 3600.0
two_hours         = 7200.0
six_hours         = 7200.0 * 3.0
twelve_hours      = 3600.0 * 12.0
half_a_day        = twelve_hours
twenty_four_hours = 3600.0 * 24.0
one_day           = twenty_four_hours
one_week          = one_day * 7.0
one_month         = one_day * 30.0
six_months        = one_month * 6.0
half_a_year       = six_months
one_year          = one_day * 365.0
twelve_months     = one_year

default_expire_time = ten_minutes

class LicornCache(ObjectSingleton):

	def __init__(self):
		self.data = {}

	def get(self, key):
		value, expire_time = self.data[key]

		if time.time() > expire_time:
			raise KeyError(_('Key %s expired!') % key)

		return value
	def set(self, key, value, expire_time=None):

		if expire_time is None:
			expire_time = time.time() + default_expire_time

		else:
			expire_time += time.time()

		self.data[key] = (value, expire_time)
	def delete(self, key):
		try:
			del self.data[key]

		except KeyError:
			pass

cache  = LicornCache()
get    = cache.get
set    = cache.set
delete = cache.delete
expire = delete

def cached(expire_time=None):
	""" This decorator will only work on standard functions (not instance methods).

		For the instance method implementation hint, see http://code.activestate.com/recipes/577452-a-memoize-decorator-for-instance-methods/
	"""
	def wrap1(func):
		@wraps(func)
		def wrap2(*args, **kwargs):

			force_expire = kwargs.pop('cache_force_expire', False)

			key = '_%s%s%s' % (func.__name__, ''.join(str(x) for x in args),
								''.join(str(v) for v in kwargs.itervalues()))

			if force_expire:
				res = func(*args, **kwargs)
				cache.set(key, res, expire_time)
				return res

			try:
				return cache.get(key)

			except KeyError:

				res = func(*args, **kwargs)
				cache.set(key, res, expire_time)
				return res

		return wrap2
	return wrap1

__all__ = ('get', 'set', 'delete', 'expire', 'cached')
