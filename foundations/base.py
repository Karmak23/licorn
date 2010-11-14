# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

objects - ultra basic objects, used as base classes.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""
import exceptions, logging
from styles import *
from ltrace import ltrace

class Singleton(object):
	__instances = {}
	def __new__(cls, *args, **kargs):
		if Singleton.__instances.get(cls) is None:
			Singleton.__instances[cls] = object.__new__(cls)

		# don't use str() here, it will fail in the backends.
		assert ltrace('objects', 'Singleton (py2.6+) created for %s' % cls)
		return Singleton.__instances[cls]
class Enumeration(object):
	def __init__(self, name='<unset>'):
		assert ltrace('objects', 'Enumeration.__init__()')
		object.__init__(self)
		self.name = name
	def dump_status(self, long_output=False, precision=None):
		assert ltrace('objects', '| %s.dump_status(%s,%s)' % (
			str(self.name), long_output, precision))
		if long_output:
			return 'object %s(%s):\n%s' % (stylize(ST_NAME, self.name),
				str(self.__class__),
				'\n'.join('%s(%s): %s' % (stylize(ST_ATTR, attrName),
					type(getattr(self, attrName)),
				getattr(self, attrName)) for attrName in dir(self)))
		else:
			return '%s: %s attributes %s' % (stylize(ST_NAME, self.name),
				len(self), self.keys())
	def _valuable(self, attr_name, attr_value=None):
		""" avoid hidden attributes, methods and Pyro attributes. """

		#assert ltrace ('objects', 'returning valuable=%s for attr %s' % (
		#	attr_name[0] != '_' \
		#		and not callable(getattr(self, attr_name)) \
		#		and not attr_name in ('name', 'delegate', 'daemon', 'lastUsed',
		#			'objectGUID'), attr_name))

		if attr_value is None:
			attr_value = getattr(self, attr_name)

		try:
			return attr_name[0] != '_' and not attr_name == 'name' \
				and not callable(attr_value)
			# \
			#	and not getattr(self, attr_name) in (True, False) \
			#	and not isinstance(getattr(self, attr_name), Enumeration)
		except Exception, e:
			logging.warning("%s: can't get attr %s (was: %s)" % (
				self.name, attr_name, e))

	def __len__(self):
		return len([ x for x in dir(self) if self._valuable(x) ])
	def __setitem__(self, key, value):
		setattr(self, key, value)
	def __delitem__(self, key):
		delattr(self, key)
	def __getitem__(self, key):
		assert ltrace('objects', '%s trying to get attr %s' % (self.name, key))
		try:
			return getattr(self, key)
		except TypeError:
			return 'NONE Object'
	def update(self, upddict):
		for (key, value) in upddict.iteritems():
			setattr(self, key, value)
	def remove(self, attr):
		delattr(self, attr)
	def __iter__(self):
		""" make this object sequence-compatible, for use in loops. Main
		diffence with other iterables like dict is that we yield values, not
		keys. I found it more useful. vast majority of yielded objects has
		self.name available anyway. """
		for attribute_name in dir(self):
			if self._valuable(attribute_name):
				try:
					yield getattr(self, attribute_name)
				except Exception, e:
					logging.warning("%s: can't get attr %s (was: %s)" % (
						self.name, attribute_name, e))
	def keys(self):
		for attribute_name in dir(self):
			if self._valuable(attribute_name):
					yield attribute_name
	def iteritems(self):
		""" behave like a dictionnary. """
		for attribute_name in dir(self):
			if self._valuable(attribute_name):
				try:
					yield (attribute_name, getattr(self, attribute_name))
				except Exception, e:
					logging.warning("%s: can't get attr %s (was: %s)" % (
						self.name, attribute_name, e))

	def _release(self):
		""" used to avoid crashing at the end of programs. """
		assert ltrace('objects', '| Enumeration._release(FAKE!!)')
		pass
class EnumDict(Enumeration, dict):
	def __init__(self, name='<unset>'):
		assert ltrace('objects', 'EnumDict.__init__()')
		dict.__init__(self)
		Enumeration.__init__(self, name)
	def __setattr__(self, key, value):
		assert ltrace('objects', 'EnumDict.__setattr__(%s->%s)' % (key, value))
		Enumeration.__setattr__(self, key, value)
		if dict.has_key(self, value):
			assert ltrace('objects', '%s: duplicate key %s in our dict.' % (
				self.name, value))
			pass
		elif self._valuable(key):
			dict.__setitem__(self, value, key)
	def __getitem__(self, key):
		assert ltrace('objects', 'EnumDict.__getitem__(%s) in %s, %s' % (
			key, dict.keys(self), Enumeration.keys(self)))
		try:
			return dict.__getitem__(self, key)
		except KeyError:
			return Enumeration.__getitem__(self, key)
	def __setitem__(self, key, value):
		assert ltrace('objects', 'EnumDict.__setitem__(%s->%s)' % (key, value))
		if dict.has_key(self, key):
			raise exceptions.AlreadyExistsError('%s already present in %s!' % (
				key, self))
		else:
			dict.__setitem__(self, key, value)
		Enumeration.__setattr__(self, value, key)

class LicornConfigObject():
	""" a base class just to be able to add/remove custom attributes
		to other custom attributes (build a tree simply).
	"""
	def __init__(self, fromdict={}, level=1):
		for key in fromdict.keys():
			setattr(self, key, fromdict[key])
		self._level = level
	def __str__(self):
		data = ""
		for i in self.__dict__:
			if i[0] == '_': continue
			if type(getattr(self, i)) == type(self):
				data += u'%s\u21b3 %s:\n%s' % ('\t'*self._level, i, str(getattr(self, i)))
			else:
				data += u"%s\u21b3 %s = %s\n" % ('\t'*self._level, str(i), str(getattr(self, i)))
		return data
	def __iter__(self):
		""" make this object sequence-compatible, for use in
			LicornConfiguration(). """
		for attribute_name in dir(self):
			if attribute_name[0] != '_':
				yield getattr(self, attribute_name)
