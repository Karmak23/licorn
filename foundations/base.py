# -*- coding: utf-8 -*-
"""
	Licorn foundations
	~~~~~~~~~~~~~~~~~~

	base - ultra basic objects, used as base classes.

	:copyright: (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	:license: GNU GPL version 2
"""

# external imports
import types, copy, functools, new

# ============================================================= Licorn® imports
import exceptions, styles
from styles  import *
from ltrace  import *
from ltraces import *

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

#: just a list of Pyro objects attributes, to be able to protect them, when
#: switching internal attributes and dict items in MixedDictObject and derivatives.
pyro_protected_attrs = ['objectGUID', 'lastUsed', 'delegate', 'daemon']

class method_decorator(object):
	""" This method decorator gets the real method by using a descriptor.
		Original information: http://wiki.python.org/moin/PythonDecoratorLibrary

		And other [non-best-working] tries:
		http://stackoverflow.com/questions/1672064/decorating-instance-methods-in-python

	"""
	def __init__(self, func, **kwargs):
		self.func     = func
		self.kwargs   = kwargs
		self.__name__ = func.__name__
	def __get__(self, instance, klass):
		if instance is None:
			# Class method was requested
			return self.make_unbound(klass)
		return self.make_bound(instance)

	def make_unbound(self, klass):
		@functools.wraps(self.func)
		def wrapper(*args, **kwargs):
			raise TypeError(_(u'Unbound method {0}() must be called with {1} '
				u'instance as first argument (got nothing instead)').format(
					self.func.__name__, klass.__name__))
		return wrapper

	def make_bound(self, instance):
		@functools.wraps(self.func)
		def wrapper(*args, **kwargs):
			return self.func(instance, *args, **kwargs)

		for key, value in self.kwargs.iteritems():
			setattr(wrapper, key, value)

		# This instance does not need the descriptor anymore,
		# let it find the wrapper directly next time.
		#
		# Create a new instance method on the fly, to avoid
		# this special one beiing seen as a simple 'function'
		# instead of 'instancemethod'.
		setattr(instance, self.func.__name__, new.instancemethod(
						wrapper, instance, instance.__class__))

		return wrapper

class BasicCounter(object):
	def __init__(self, init=0):
		object.__init__(self)
		self.value = init
	def __str__(self):
		return str(self.value)
	def __call__(self):
		return self.value

	def set(self, val):
		assert int(val)
		self.value = val

	def __add__(self, val):
		self.value += val
	def __iadd__(self, val):
		self.value += val
		return self

	def __sub__(self, val):
		self.value -= val
	def __isub__(self, val):
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

		# WARNING: using 'cls' instead of 'cls.__name__' for instances dict
		# keys can lead to not having singletons in the reality, because
		# <class 'wmi.app.WmiEventApplication'> is not the same thing as
		# <class 'licorn.interfaces.wmi.app.WmiEventApplication'> when
		# importing classes from packages with a different base path.
		name = cls.__name__

		if ObjectSingleton.__instances.get(name) is None:

			# don't use str() here, it will fail in the backends.
			assert ltrace_func(TRACE_BASE)

			ObjectSingleton.__instances[name] = object.__new__(cls)

		assert ltrace_var(TRACE_BASE, ObjectSingleton.__instances[name])
		return ObjectSingleton.__instances[name]
class DictSingleton(dict):
	""" Create a single instance of a dict-derived class. """
	__instances = {}
	def __new__(cls, *args, **kargs):
		if DictSingleton.__instances.get(cls) is None:
			assert ltrace_func(TRACE_BASE)
			DictSingleton.__instances[cls] = dict.__new__(cls)

		# don't use str() here, it will fail in the backends.
		assert ltrace_var(TRACE_BASE, DictSingleton.__instances[cls])
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
	name = '<unset_yet>'

	def __init__(self, *args, **kwargs):

		source = kwargs.pop('source', None)

		# object.__init__ is not super() compatible...
		#super(NamedObject, self).__init__(*args, **kwargs)

		assert ltrace_func(TRACE_BASE)

		# this instance variable should override the class one.
		# the class variable is used to avoid crash when ltrace tries
		# to str() objects during their initialisation.
		self.name = kwargs.pop('name', NamedObject.name)

		if source:
			self.copy_from(source)
	def __hash__(self):
		return id(self)
	@property
	def pretty_name(self):
		try:
			return self.__pretty_name

		except:
			self.__pretty_name = stylize(ST_NAME, self.name)
			return self.__pretty_name
	def __str__(self):
		#data = ''
		#for i in sorted(self.__dict__):
		#	if i[0] == '_' or i == 'parent': continue
		#	if type(getattr(self, i)) == type(self):
		#		data += '%s↳ %s:\n%s' % ('\t', i, str(getattr(self, i)))
		#	else:
		#		data += '%s↳ %s = %s\n' % ('\t', str(i), str(getattr(self, i)))
		return "<%s: '%s' at 0x%x>" % (
			stylize(ST_ATTR, self.__class__.__name__),
			stylize(ST_NAME, self.name),
			id(self))
	def __unicode__(self):
		return unicode(str(self))
	def copy(self):
		""" Implements the copy method like any other base object. """
		assert ltrace_func(TRACE_BASE)
		temp = self.__class__()
		temp.copy_from(self)
		return temp
	def copy_from(self, source):
		""" Copy attributes from another object of the same class. """
		assert ltrace_func(TRACE_BASE)
		self.name = source.name
	def dump_status(self, long_output=False, precision=None, as_string=False):
		""" method called by :meth:`ltrace.dump` and :meth:`ltrace.fulldump`
			to dig into complex derivated object at runtime (in the licornd
			interactive shell).
		"""
		assert ltrace_func(TRACE_BASE)

		if long_output:
			return u'%s %s:\n%s' % (
				unicode(self.__class__),
				stylize(ST_NAME, self.name),
				u'\n'.join(u'%s(%s): %s' % (
							stylize(ST_ATTR, key),
							type(value),
							# some non-licorn objects (notably the Pyro daemon)
							# don't provide __unicode__() and trigger a crash.
							value if hasattr(value, '__unicode__')
								else unicode(str(value))
						) for key, value in self.__dict__.iteritems() \
							if key[:2] != u'__' and not callable(value) \
							and key not in self.__class__._licorn_protected_attrs))
		else:
			return u'%s %s: %s' % (
				unicode(self.__class__),
				stylize(ST_NAME, self.name),
				[ unicode(key) for key, value \
					in self.__dict__.iteritems() if key[:2] != u'__' \
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

	def __init__(self, *args, **kwargs):

		source = kwargs.pop('source', None)

		assert ltrace_func(TRACE_BASE)

		super(MixedDictObject, self).__init__(*args, **kwargs)

		if source:
			self.copy_from(kwargs.pop('source'))
	def copy(self):
		""" we must implement this one, else python will not be able to choose
			between the one from NamedObject and from dict. NamedObject will call
			our self.copy_from() which does the good job. """
		assert ltrace_func(TRACE_BASE)
		return NamedObject.copy(self)
	def copy_from(self, source):
		assert ltrace_func(TRACE_BASE)
		NamedObject.copy_from(self, source)
		dict.update(self, dict.copy(source))
	def iter(self):
		assert ltrace_func(TRACE_BASE)
		return self.__iter__()
	def __iter__(self):
		assert ltrace_func(TRACE_BASE)
		for v in dict.itervalues(self):
			yield v
	def __getattr__(self, attribute):
		""" Called only when a normal call to "self.attribute" fails. """
		assert ltrace_func(TRACE_BASE)

		try:
			return dict.__getitem__(self, attribute)

		except KeyError:
			try:
				return dict.__getattr__(self, attribute)

			except AttributeError:
				try:
					return NamedObject.__getattr__(self, attribute)

				except AttributeError:
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
		assert ltrace_func(TRACE_BASE)
		dict.__setitem__(self, thing.name, thing)
	def remove(self, thing):
		assert ltrace_func(TRACE_BASE)
		for key, value in dict.iteritems(self):
			if value == thing:
				dict.__delitem__(self, key)
				break
	def __setattr__(self, attribute, value):
		""" any attribute other than {semi-hidden, protected or callable}
			attributes will go into the dict part, to be able to retrieve
			them in either way (x.attr or x[attr]).
		"""
		assert ltrace_func(TRACE_BASE)

		if attribute[0] == '_' or callable(value) \
						or attribute in self.__class__._licorn_protected_attrs:
			dict.__setattr__(self, attribute, value)

		else:
			dict.__setitem__(self, attribute, value)
	def __delattr__(self, key):
		assert ltrace_func(TRACE_BASE)

		if key[0] == '_' or key in self.__class__._licorn_protected_attrs:
			dict.__delattr__(self, key)

		else:
			dict.__delitem__(self, key)
	def dump_status(self, long_output=False, precision=None, as_string=False):
		assert ltrace_func(TRACE_BASE)

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
		assert ltrace(TRACE_BASE, 'Enumeration_v2.__init__(%s)' % name)

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
	def dump_status(self, long_output=False, precision=None, as_string=True):
		assert ltrace(TRACE_BASE, '| %s.dump_status(%s,%s)' % (
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
		assert ltrace(TRACE_BASE, '| Enumeration_v2._release(~FAKE~)')
		pass

# old-style classes, or classes to be removed at next refactor run.
class Enumeration(object):

	def __init__(self, *args, **kwargs):
		assert ltrace(TRACE_BASE, '| Enumeration.__init__()')
		object.__init__(self)
		self.name = kwargs.pop('name', '<unset>')

		copy_from = kwargs.pop('copy_from', None)
		if copy_from:
			self.name = copy_from.name[:]
			for attrname, attrvalue in copy_from.iteritems():
				self.__setattr__(attrname, copy.copy(attrvalue))

		if kwargs != {}:
			for key, value in kwargs.iteritems():
				self.__setattr__(key, value)
	def __str__(self):
		return "<%s: '%s' at 0x%x>" % (stylize(ST_ATTR, self.__class__.__name__),
						stylize(ST_NAME, self.name), id(self))
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
	def dump_status(self, long_output=False, precision=None, as_string=True):
		assert ltrace(TRACE_BASE, '| %s.dump_status(%s,%s)' % (
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
		assert ltrace(TRACE_BASE, '%s trying to get attr %s' % (self.name, key))
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
		assert ltrace(TRACE_BASE, '| Enumeration._release(FAKE!!)')
		pass
class EnumDict(Enumeration, dict):
	def __init__(self, name='<unset>', from_dict=None):
		assert ltrace(TRACE_BASE, '| EnumDict.__init__(%s)' % name)
		dict.__init__(self)
		Enumeration.__init__(self, name)
		if from_dict:
			for key, value in from_dict.iteritems():
				self.__setattr__(key, value)
	def __setattr__(self, key, value):
		assert ltrace(TRACE_BASE, '| EnumDict.__setattr__(%s → %s)' % (key, value))
		Enumeration.__setattr__(self, key, value)
		if dict.has_key(self, value):
			assert ltrace(TRACE_BASE, '%s: duplicate key %s in our dict.' % (
				self.name, value))
			pass
		elif self._valuable(key):
			dict.__setitem__(self, value, key)
	def __getitem__(self, key):
		assert ltrace(TRACE_BASE, '| EnumDict.__getitem__(%s) in %s, %s' % (
			key, dict.keys(self), Enumeration.keys(self)))
		try:
			return dict.__getitem__(self, key)
		except KeyError:
			return Enumeration.__getitem__(self, key)
	def __setitem__(self, key, value):
		assert ltrace(TRACE_BASE, '| EnumDict.__setitem__(%s → %s)' % (key, value))
		if dict.has_key(self, key):
			raise exceptions.AlreadyExistsError('%s already present in %s!' % (
				key, self))
		else:
			dict.__setitem__(self, key, value)
		Enumeration.__setattr__(self, value, key)
class LicornConfigObject:
	""" a base class just to be able to add/remove custom attributes
		to other custom attributes (build a tree simply). """
	def __init__(self, fromdict={}, _name=None, parent=None, level=0):

		assert ltrace_func(TRACE_BASE)

		self._name = _name

		if parent:
			self._level = parent._level + 1

		else:
			self._level = level

		for key, value in fromdict.iteritems():
			setattr(self, key,
					LicornConfigObject(fromdict=value, parent=self)
						if isinstance(value, types.DictType)
						else value)
	def __str__(self):
		data   = ''
		sep    = '  '
		sublev = self._level + 1

		for key, value in self.__dict__.iteritems():

			if key[0] == '_':
				continue

			data += '%s%s: %s,\n' % (sep * sublev, key, value)

		return '{\n%s%s}' % (data, sep * self._level)
	def iteritems(self):
		for key, value in sorted(self.__dict__.iteritems()):
			if key[0] != '_':
				yield key, value
	def __iter__(self):
		""" make this object sequence-compatible, for use in
			LicornConfiguration(). """
		for key, value in self.__dict__.iteritems():
			if key[0] != '_':
				yield value
