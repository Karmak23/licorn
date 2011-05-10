# -*- coding: utf-8 -*-
"""
	Licorn foundations
	~~~~~~~~~~~~~~~~~~

	base - ultra basic objects, used as base classes.

	:copyright: (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	:license: GNU GPL version 2

"""
import copy

import exceptions
from styles import *
from ltrace import ltrace

#: just a list of Pyro objects attributes, to be able to protect them, when
#: switching internal attributes and dict items in MixedDictObject and derivatives.
pyro_protected_attrs = ['objectGUID', 'lastUsed', 'delegate', 'daemon']

class BasicCounter(object):
	def __init__(self, init=0):
		object.__init__(self)
		self.value = init
	def __str__(self):
		return str(self.value)
	def __repr__(self):
		return 'BasicCounter(%d)' % self.value
	def __call__(self):
		return self.value

	def set(self, val):
		assert int(val)
		self.value = val

	def __add__(self, val):
		self.value += val
	def __iadd__(self, val):
		#print '>> iadd', val
		self.value += val
		return self

	def __sub__(self, val):
		self.value -= val
	def __isub__(self, val):
		#print '>> isub', val
		self.value -= val
		return self

	def __le__(self, val):
		return self.value <= val
	def __nonzero__(self):
		return self.value != 0

class ObjectSingleton(object):
	""" Create a single instance of an object-derived class. """
	__instances = {}
	def __new__(cls, *args, **kargs):
		if ObjectSingleton.__instances.get(cls) is None:
			ObjectSingleton.__instances[cls] = object.__new__(cls)

		# don't use str() here, it will fail in the backends.
		assert ltrace('base', '| Singleton.__new__(%s)' % cls)
		return ObjectSingleton.__instances[cls]
class DictSingleton(dict):
	""" Create a single instance of a dict-derived class. """
	__instances = {}
	def __new__(cls, *args, **kargs):
		if DictSingleton.__instances.get(cls) is None:
			DictSingleton.__instances[cls] = dict.__new__(cls)

		# don't use str() here, it will fail in the backends.
		assert ltrace('base', '| Singleton.__new__(%s)' % cls)
		return DictSingleton.__instances[cls]

Singleton = DictSingleton

#new-style classes.
class NamedObject(object):
	""" A simple object-derived class with a :attr:`name` attribute, protected
		against aggressive :meth:`__setattr__` by the class attribute
		:attr:`_licorn_protected_attrs`. This protector is not used in the
		current class, but derivative classes rely on it to exist, in order
		to be able to protect the base :attr:`name` attribute will all or their
		other protected attributes.
	"""
	_licorn_protected_attrs = [ 'name' ]

	@property
	def name(self):
		return self.__name
	@name.setter
	def name(self, name):
		self.__name = name

	def __init__(self, name='<unset>', source=None):
		assert ltrace('base', '| NamedObject.__init__(%s)' % name)

		self.__name = name
		if source:
			self.copy_from(source)
	def __str__(self):
		data = ''
		for i in sorted(self.__dict__):
			if i[0] == '_' or i == 'parent': continue
			if type(getattr(self, i)) == type(self):
				data += '%s↳ %s:\n%s' % ('\t', i, str(getattr(self, i)))
			else:
				data += '%s↳ %s = %s\n' % ('\t', str(i), str(getattr(self, i)))
		return data
	def __repr__(self):
		data = ''
		for i in sorted(self.__dict__):
			if i[0] == '_' or i == 'parent': continue
			if type(getattr(self, i)) == type(self):
				data += '%s↳ %s:\n%s' % ('\t', i, str(getattr(self, i)))
			else:
				data += '%s↳ %s = %s\n' % ('\t', str(i), str(getattr(self, i)))
		return data
	def copy(self):
		""" Implements the copy method like any other base object. """
		assert ltrace('base', '| NamedObject.copy(%s)' % self.name)
		temp = self.__class__()
		temp.copy_from(self)
		return temp
	def copy_from(self, source):
		""" Copy attributes from another object of the same class. """
		assert ltrace('base', '| NamedObject.copy_from(%s, %s)' % (
			self.name, source.name))
		self.__name = source.name
	def dump_status(self, long_output=False, precision=None):
		""" method called by :meth:`ltrace.dump` and :meth:`ltrace.fulldump`
			to dig into complex derivated object at runtime (in the licornd
			interactive shell).
		"""
		assert ltrace('base', '| %s.dump_status(%s, %s)' % (self.name,
			long_output, precision))

		if long_output:
			return '%s %s:\n%s' % (
				str(self.__class__),
				stylize(ST_NAME, self.name),
				'\n'.join('%s(%s): %s' % (
					stylize(ST_ATTR, key), type(value), value)
						for key, value in self.__dict__.iteritems() \
							if key[:2] != '__' and not callable(value) \
							and key not in self.__class__._licorn_protected_attrs))
		else:
			return '%s %s: %s' % (
				str(self.__class__),
				stylize(ST_NAME, self.name),
				[ key for key, value \
					in self.__dict__.iteritems() if key[:2] != '__' \
						and not callable(value) \
						and key not in self.__class__._licorn_protected_attrs])
class MixedDictObject(NamedObject, dict):
	""" Object which attributes are usable in 2 forms:
			obj.attr = ...
			obj['attr'] = ...

		Also, iterating this object iterates its values instead of keys (which
		differs from the standard python dict implementation). We need values
		much more often than keys, and when iterating values - which are likely
		to be licorn base objects - their names are still accessible via the
		value.name attribute.

	"""
	_licorn_protected_attrs = NamedObject._licorn_protected_attrs
	def __init__(self, name=None, source=None):

		NamedObject.__init__(self, name=name)
		assert ltrace('base', '| MixedDictObject.__init__(%s)' % name)

		if source:
			self.copy_from(source)
	def copy(self):
		""" we must implement this one, else python will not be able to choose
			between the one from NamedObject and from dict. NamedObject will call
			our self.copy_from() which does the good job. """
		assert ltrace('base', '| MixedDictObject.copy()')
		return NamedObject.copy(self)
	def copy_from(self, source):
		assert ltrace('base', '| MixedDictObject.copy_from(%s)' %
			source.name)
		NamedObject.copy_from(self, source)
		dict.update(self, dict.copy(source))
	def iter(self):
		#print '>> iter', self.name
		assert ltrace('base', '| MixedDictObject.iter(%s)' % self.name)
		return dict.itervalues(self)
	def __iter__(self):
		#print '>> __iter__', self.name
		assert ltrace('base', '| MixedDictObject.__iter__(%s)' % self.name)
		return dict.itervalues(self)
	def __getattr__(self, attribute):
		""" Called only when a normal call to "self.attribute" fails. """
		assert ltrace('base', '| MixedDictObject.__getattr__(%s)' % attribute)
		try:
			return dict.__getitem__(self, attribute)
		except KeyError:
			raise AttributeError("'%s' %s%s" % (stylize(ST_BAD, attribute),
					'' if attribute in self.__class__._licorn_protected_attrs
						else ('\n\t- it is currently missing from %s '
							'(currently=%s)' % ('%s.%s' % (
								stylize(ST_NAME, self.name),
								stylize(ST_ATTR,'_licorn_protected_attrs')),
						', '.join(stylize(ST_COMMENT, value)
							for value in self.__class__._licorn_protected_attrs))),
					'\n\t- perhaps you tried to %s a %s?' % (
						stylize(ST_ATTR, 'getattr()'),
						stylize(ST_COMMENT, 'property()'))))
	def append(self, thing):
		dict.__setitem__(self, thing.name, thing)
	def remove(self, thing):
		for key, value in dict.iteritems(self):
			if value == thing:
				dict.__delitem__(self, key)
				break
	def __setattr__(self, attribute, value):
		""" any attribute other than {semi-hidden, protected or callable}
			attributes will go into the dict part, to be able to retrieve
			them in either way (x.attr or x[attr]).
		"""
		assert ltrace('base', '| MixedDictObject.__setattr__(%s, %s)' % (
			attribute, value))
		if attribute[0] == '_' or callable(value) \
			or attribute in self.__class__._licorn_protected_attrs:
			dict.__setattr__(self, attribute, value)
		else:
			dict.__setitem__(self, attribute, value)
	def __delattr__(self, key):
		assert ltrace('base', '| MixedDictObject.__delattr__(%s)' % key)
		if key[0] == '_' or key in self.__class__._licorn_protected_attrs:
			dict.__delattr__(self, key)
		else:
			dict.__delitem__(self, key)
	def dump_status(self, long_output=False, precision=None):
		assert ltrace('base', '| %s.dump_status(%s, %s)' % (self.name,
			long_output, precision))

		if long_output:
			return '%s %s:\n%s' % (
				str(self.__class__),
				stylize(ST_NAME, self.name),
				'\n'.join('%s(%s): %s' % (
					stylize(ST_ATTR, key), type(value), value)
						for key, value \
						in self.__dict__.items() + self.items() \
							if key[:2] != '__' and not callable(value) \
							and key not in self.__class__._licorn_protected_attrs))
		else:
			return '%s %s: %s' % (
				str(self.__class__),
				stylize(ST_NAME, self.name),
				[ key for key, value \
					in self.__dict__.items() + dict.items(self) \
						if key[:2] != '__' \
						and not callable(value) \
						and key not in self.__class__._licorn_protected_attrs])
class TreeNode(NamedObject):
	def __init__(self, name=None, parent=None, prev=None, next=None,
		first=None, last=None, children=[], copy_from=None):

		NamedObject.__init__(self)
		assert ltrace('base', 'Enumeration_v2.__init__(%s)' % name)

		# graph attributes
		self._parent   = parent
		self._next     = next
		self._prev     = prev
		self._first    = first
		self._last     = last
		self._children = children

		if copy_from:
			self.copy_from(copy_from)
	def copy_from(self, source):
		""" Duplicate or reference source attributes to become a valid copy. """
		NamedObject.copy_from(self, copy_from)

		self._parent   = copy_from.parent
		self._next     = copy_from.next
		self._prev     = copy_from.prev
		self._first    = copy_from.first
		self._last     = copy_from.last
		self._children = copy_from.children

	def copy(self):
		""" make a complete and dereferenced copy of ouselves. """
		temp = self.__class__()
		temp.copy_from(self)
		return temp
	def __lsattrs__(self):
		return [ attr for attr, value in self.__dict__.iteritems() \
			if attr[:2] != '__' and not callable(value) ]
	def dump_status(self, long_output=False, precision=None):
		assert ltrace('base', '| %s.dump_status(%s,%s)' % (
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
	def _release(self):
		""" used to avoid crashing at the end of programs. """
		assert ltrace('base', '| Enumeration_v2._release(~FAKE~)')
		pass

# old-style classes, or classes to be removed at next refactor run.
class Enumeration(object):
	def __init__(self, name='<unset>', copy_from=None, **kwargs):
		assert ltrace('base', '| Enumeration.__init__()')
		object.__init__(self)
		self.name = name

		if copy_from:
			self.name = copy_from.name[:]
			for attrname, attrvalue in copy_from.iteritems():
				self.__setattr__(attrname, copy.copy(attrvalue))

		if kwargs != {}:
			for key, value in kwargs.iteritems():
				self.__setattr__(key, value)
	def copy(self):
		""" make a complete and dereferenced copy of ouselves. """
		temp = Enumeration()
		temp.name = self.name[:]
		for attrname, attrvalue in self.iteritems():
			setattr(temp, attrname, copy.copy(attrvalue))
		return temp
	# make Enumeration pseudo-list compatible
	def append(self, value):
		self.__setattr__(value.name, value)
	def remove(self, value):
		try:
			delattr(self, value.name)
		except AttributeError:
			delattr(self, value)
	# make enumeration
	def dump_status(self, long_output=False, precision=None):
		assert ltrace('base', '| %s.dump_status(%s,%s)' % (
			str(self.name), long_output, precision))
		if long_output:
			return 'object %s(%s):\n%s' % (stylize(ST_NAME, self.name),
				str(self.__class__),
				'\n'.join('%s(%s): %s' % (stylize(ST_ATTR, attrName),
					type(getattr(self, attrName)),
				getattr(self, attrName)) for attrName in dir(self)
					if attrName[:2] != '__' and not callable(getattr(self, attrName))))
		else:
			return '%s: %s attributes %s' % (stylize(ST_NAME, self.name),
				len(self), self.keys())
	def _valuable(self, attr_name, attr_value=None):
		""" avoid hidden attributes, methods and Pyro attributes. """

		#assert ltrace ('base', 'returning valuable=%s for attr %s' % (
		#	attr_name[0] != '_' \
		#		and not callable(getattr(self, attr_name)) \
		#		and not attr_name in ('name', 'delegate', 'daemon', 'lastUsed',
		#			'objectGUID'), attr_name))

		if attr_value is None:
			attr_value = getattr(self, attr_name)
		#print "bla:%s:%s" % (attr_name, len(attr_name))

		return attr_name[0] != '_' and not attr_name == 'name' \
			and not callable(attr_value)
		# \
		#	and not getattr(self, attr_name) in (True, False) \
		#	and not isinstance(getattr(self, attr_name), Enumeration)
	def __len__(self):
		return len([ x for x in dir(self) if self._valuable(x) ])
	def __setitem__(self, key, value):
		setattr(self, key, value)
	def __delitem__(self, key):
		delattr(self, key)
	def __getitem__(self, key):
		assert ltrace('base', '%s trying to get attr %s' % (self.name, key))
		try:
			return getattr(self, key)
		except TypeError:
			return 'NONE Object'
	def update(self, upddict):
		""" like a standard dict object, implement ``update()``. """
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
				yield getattr(self, attribute_name)
	def keys(self):
		for attribute_name in dir(self):
			if self._valuable(attribute_name):
					yield attribute_name
	def iteritems(self):
		""" behave like a dictionnary. """
		for attribute_name in dir(self):
			if self._valuable(attribute_name):
				yield (attribute_name, getattr(self, attribute_name))
	def _release(self):
		""" used to avoid crashing at the end of programs. """
		assert ltrace('base', '| Enumeration._release(FAKE!!)')
		pass
class EnumDict(Enumeration, dict):
	def __init__(self, name='<unset>', from_dict=None):
		assert ltrace('base', '| EnumDict.__init__(%s)' % name)
		dict.__init__(self)
		Enumeration.__init__(self, name)
		if from_dict:
			for key, value in from_dict.iteritems():
				self.__setattr__(key, value)
	def __setattr__(self, key, value):
		assert ltrace('base', '| EnumDict.__setattr__(%s → %s)' % (key, value))
		Enumeration.__setattr__(self, key, value)
		if dict.has_key(self, value):
			assert ltrace('base', '%s: duplicate key %s in our dict.' % (
				self.name, value))
			pass
		elif self._valuable(key):
			dict.__setitem__(self, value, key)
	def __getitem__(self, key):
		assert ltrace('base', '| EnumDict.__getitem__(%s) in %s, %s' % (
			key, dict.keys(self), Enumeration.keys(self)))
		try:
			return dict.__getitem__(self, key)
		except KeyError:
			return Enumeration.__getitem__(self, key)
	def __setitem__(self, key, value):
		assert ltrace('base', '| EnumDict.__setitem__(%s → %s)' % (key, value))
		if dict.has_key(self, key):
			raise exceptions.AlreadyExistsError('%s already present in %s!' % (
				key, self))
		else:
			dict.__setitem__(self, key, value)
		Enumeration.__setattr__(self, value, key)
class LicornConfigObject():
	""" a base class just to be able to add/remove custom attributes
		to other custom attributes (build a tree simply). """
	def __init__(self, fromdict={}, level=1):
		assert ltrace('base', '| LicornConfigObject.__init__(%s, %s)' % (
			fromdict, level))
		for key in fromdict.keys():
			setattr(self, key, fromdict[key])
		self._level = level
	def __str__(self):
		data = ""
		for i in sorted(self.__dict__):
			if i[0] == '_': continue
			if type(getattr(self, i)) == type(self):
				data += '%s↳ %s:\n%s' % ('\t'*self._level, i, str(getattr(self, i)))
			else:
				data += '%s↳ %s = %s\n' % ('\t'*self._level, str(i), str(getattr(self, i)))
		return data
	def iteritems(self):
		for key, value in sorted(self.__dict__.iteritems()):
			if key[0] != '_':
				yield key, value
	def __iter__(self):
		""" make this object sequence-compatible, for use in
			LicornConfiguration(). """
		for key, value in sorted(self.__dict__.iteritems()):
			if key[0] != '_' and not callable(value):
				yield value
class FsapiObject(Enumeration):
	""" TODO. """
	def __init__(self, name=None, path=None, uid=-1, gid=-1,
		root_dir_perm=None, dirs_perm=None, files_perm=None, exclude=None,
		rule=None, system=False, content_acl=False, root_dir_acl=False,
		home=None, user_uid=-1, user_gid=-1,
		copy_from=None):

		Enumeration.__init__(self, name, copy_from)

		# This one is used only in core.classes.CoreFSController methods
		if home:
			self.home     = home
			self.user_uid = user_uid
			self.user_gid = user_gid
		# else:
		# do not define self.{home,user_uid,user_gid}

		# These other are used in fsapi.check*
		self.path           = path
		self.uid            = uid
		self.root_gid       = gid
		self.content_gid    = None
		self.root_dir_perm  = root_dir_perm
		self.dirs_perm      = dirs_perm
		self.files_perm     = files_perm
		self.rule           = rule
		self.system         = system
		self.content_acl    = content_acl
		self.root_dir_acl   = root_dir_acl
		self.already_loaded = False

		if exclude is None:
			self.exclude    = []
		else:
			self.exclude    = exclude
