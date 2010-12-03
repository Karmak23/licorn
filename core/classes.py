# -*- coding: utf-8 -*-
"""
Licorn core objects

Basic objects used in all core controllers, backends, plugins.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Licensed under the terms of the GNU GPL version 2
"""

import Pyro.core
from threading import RLock, current_thread

from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import NamedObject, MixedDictObject, pyro_protected_attrs
from licorn.foundations.constants import host_status, host_types

from licorn.core import LMC

class GiantLockProtectedObject(MixedDictObject, Pyro.core.ObjBase):
	_licorn_protected_attrs = (
			MixedDictObject._licorn_protected_attrs
			+ pyro_protected_attrs
			+ ['warnings']
		)
	def __init__(self, name, warnings=True):
		MixedDictObject.__init__(self, name)
		Pyro.core.ObjBase.__init__(self)
		assert ltrace('objects', '| GiantLockProtectedObject.__init__(%s, %s)' % (
			name, warnings))

		self.warnings = warnings

		# Create lock holder objects for the current GiantLockProtectedObject
		# and all CoreUnitObjects stored inside us. The giant_lock is hidden,
		# in case we iter*() the master lock object, for it to return only the
		# UnitObject locks.
		lock_manager = MixedDictObject(name + '_lock')
		lock_manager._giant_lock = RLock()
		setattr(LMC.locks, self.name, lock_manager)
	def __getitem__(self, key):
		""" return the value, but protect us against concurrent accesses. """
		with self.lock():
			return MixedDictObject.__getitem__(self, key)
	def __setitem__(self, key, value):
		""" Add a new element inside us protected with our lock. """
		with self.lock():
			MixedDictObject.__setitem__(self, key, value)
	def __delitem__(self, key):
		""" Delete data inside us, protected with our lock. """
		with self.lock():
			MixedDictObject.__delitem__(self, key)
	def acquire(self):
		assert ltrace('thread', '%s: acquiring %s %s.' % (
			current_thread().name, self.name, self.lock()))
		self.lock().acquire()
	def lock(self):
		return getattr(getattr(LMC.locks, self.name), '_giant_lock')
	def release(self):
		assert ltrace('thread', '%s: releasing %s %s.' % (
			current_thread().name, self.name, self.lock()))
		self.lock().release()
	def is_locked(self):
		""" WARNING: calling this method costs. """
		if self.lock().acquire(blocking=False):
			self.lock().release()
			return False
		return True
class CoreController(GiantLockProtectedObject):
	""" The CoreController class implements multiple functionnalities:
		- storage for UnitObjects, via the dict part of MixedDictObject
		- backend resolution, with priorities if used by current
			controller's backends.
		- the reverse mapping via one or more protected dictionnary.
	"""
	class ReverseMappingDict(dict):
		""" Small class to make a dict callable() by returning getitem() when
			called. This avoids the need to create a function next to the dict
			to implement reverse mappings, the simple way. """
		def __call__(self, item):
			return self.__getitem__(item)
	def __init__(self, name, warnings=True, reverse_mappings=[]):
		GiantLockProtectedObject.__init__(self, name=name, warnings=warnings)
		assert ltrace('objects', '| CoreController.__init__(%s, %s)' % (
			name, warnings))

		# Keeping the reverse mapping dicts in a container permits having
		# more than one reverse mapping available for UnitObjects (kind of an
		# internal index) and update them fast when an object is altered.
		#
		# The mapping construct permits having different mapping names instead
		# of fixed ones (e.g. "login" for users, "name" for groups, "hostname"
		# for machines...).
		self._reverse_mappings = MixedDictObject(self.name + '_reverse_mappings')
		for mapping_name in reverse_mappings:
			mapping = CoreController.ReverseMappingDict()
			self.__setattr__('_by_' + mapping_name, mapping)
			setattr(self._reverse_mappings, mapping_name, mapping)

		# prefixed with '_', they are automatically protected and stored out
		# of the dict() part of self, thanks to MixedDictObject.
		self._prefered_backend_name = None
		self._prefered_backend_prio = None

		self.find_prefered_backend()
	def __setitem__(self, key, value):
		""" Add a new element inside us and update all reverse mappings. """
		with self.lock():
			GiantLockProtectedObject.__setitem__(self, key, value)
			for mapping_name, mapping_dict in self._reverse_mappings.items():
				mapping_dict[getattr(value, mapping_name)] = value
	def __delitem__(self, key):
		""" Delete data inside us, but remove reverse mappings first. """
		with self.lock():
			for mapping_name, mapping_dict in self._reverse_mappings.items():
				del mapping_dict[getattr(self[key], mapping_name)]
			GiantLockProtectedObject.__delitem__(self, key)
	def exists(self, oid=None, **kwargs):
		if oid:
			return oid in self
		if kwargs:
			for mapping_name, value in kwargs.items():
				if value in self._reverse_mappings[mapping_name]:
					return True
			return False
		raise exceptions.BadArgumentError(
			"You must specify an ID or a name to test existence of.")
	def guess_identifier(self, value):
		""" Try to guess the real ID of one of our internal objects from a
			single and unknown-typed info given as argument. """
		if value in self:
			return value
		for mapping in self._reverse_mappings:
			try:
				return mapping[value]._oid
			except KeyError:
				continue
		raise exceptions.DoesntExistsException
	def guess_identifiers(self, value_list):
		""" Try to guess the type of any identifier given, find it in our
			objects IDs or reverse mappings, and return the ID (numeric) of the
			object found. """
		valid_ids=set()
		for value in value_list:
			try:
				valid_ids.add(self.guess_identifier(value))
			except exceptions.DoesntExistsException:
				logging.notice("Skipped non-existing object / ID '%s'." %
					stylize(ST_NAME, value))
		return valid_ids
	def dump(self):
		""" Dump the internal data structures (debug and development use). """

		assert ltrace(self.name, '| dump()')

		with self.lock():

			dicts_to_dump = [ (self.name, self) ] + [
				(mapping_name, mapping)
					for mapping_name, mapping
						in self._reverse_mappings.items() ]

			return '\n'.join([
				'%s:\n%s' % (
					stylize(ST_IMPORTANT, mapping_name),
					'\n'.join([
							'\t%s: %s' % (key, value)
								for key, value in sorted(mapping_dict.items())
						])
					)
					for mapping_name, mapping_dict in dicts_to_dump
				])
	def backends(self):
		""" return a list of compatible backends for the current core object."""
		assert ltrace(self.name, 'LMC.backends=%s' % LMC.backends)
		assert ltrace(self.name, '| backends(%s -> %s)' % (
			str([ x.controllers_compat for x in LMC.backends ]),
			str([ backend for backend in LMC.backends \
				if self.name in backend.controllers_compat ])))
		return [ backend for backend in LMC.backends \
			if self.name in backend.controllers_compat ]
	def find_prefered_backend(self):
		""" iterate through active backends and find the prefered one.
			We use a copy, in case there is no prefered yet: LMC.backends
			will change and this would crash the for_loop. """

		assert ltrace(self.name, '> find_prefered_backend(%s)' % self.backends())

		changed = False

		# remove an old backend name if the corresponding just got disabled.
		# else we don't change if the old had a better priority than the
		# remaining ones.
		if self._prefered_backend_name not in LMC.backends.keys():
			self._prefered_backend_name = None
			self._prefered_backend_prio = None

		for backend in self.backends():
			if self._prefered_backend_name is None:
				assert ltrace(self.name, ' found first prefered_backend(%s)' %
					backend.name)
				self._prefered_backend_name = backend.name
				changed = True
				if hasattr(backend, 'priority'):
					self._prefered_backend_prio = backend.priority
				else:
					# my backends don't handle priory, I will deal with the first.
					break
			else:
				if hasattr(backend, 'priority'):
					if backend.priority > self._prefered_backend_prio:
						assert ltrace(self.name,
							' found better prefered_backend(%s)' % backend.name)
						self._prefered_backend_name = backend.name
						self._prefered_backend_prio = backend.priority
						changed = True
					else:
						assert ltrace(self.name,
							' discard lower prefered_backend(%s)' %
								backend.name)
						pass
				else:
					assert ltrace(self.name,
						' no priority mechanism, skipping backend %s' %
							backend.name)

		assert ltrace(self.name, '< find_prefered_backend(%s, %s)' % (
			self._prefered_backend_name, changed))
		return changed

class CoreUnitObject(NamedObject):
	""" Common attributes for unit objects  and backends in Licorn® core. """

	# no need to add our _* attributes, because we don't inherit from
	# MixedDictObject. This Class attribute won't be used unless using
	# MixedDictObject or one of its inherited classes.
	_licorn_protected_attrs = NamedObject._licorn_protected_attrs
	counter = 0
	def __init__(self, name=None, oid=None, controller=None):
		NamedObject.__init__(self, name)
		assert ltrace('objects',
			'| CoreUnitObject.__init__(%s, %s, %s)' % (
				name, oid, controller))

		assert oid is not None and controller is not None

		if oid:
			self._oid = oid
		else:
			self._oid = self.__class__.counter
			self.__class__.counter +=1

		# FIXME: find a way to store the reference to the controller, not only
		# its name. This will annoy Pyro which cannot pickle weakproxy objects,
		# but will be cleaner than lookup the object by its name...
		self._controller = controller.name

class CoreStoredObject(CoreUnitObject):
	""" Common attributes for stored objects (users, groups...). Add individual
		locking capability (better fine grained than global controller lock when
		possible), and the backend name of the current object storage. """

	# no need to add our _* attributes, because we don't inherit from
	# MixedDictObject. This Class attribute won't be used unless using
	# MixedDictObject or one of its inherited classes.
	_licorn_protected_attrs = CoreUnitObject._licorn_protected_attrs
	def __init__(self, name=None, oid=None, controller=None, backend=None):
		CoreUnitObject.__init__(self, name=name, oid=oid, controller=controller)
		assert ltrace('objects',
			'| CoreStoredObject.__init__(%s, %s, %s, %s)' % (
				name, oid, controller.name, backend.name))

		self._backend  = backend.name

		# store the lock outside of us, else Pyro can't pickle us.
		LMC.locks[self._controller][self._oid] = RLock()
	def lock(self):
		""" return our unit RLock(). """
		return LMC.locks[self._controller][self._oid]
