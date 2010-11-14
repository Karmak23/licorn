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
from licorn.foundations.base      import Enumeration
from licorn.foundations.constants import host_status, host_types

from licorn.core import LMC

class LicornBaseObject(Enumeration):
	def __init__(self, name, warnings=True):
		Enumeration.__init__(self)
		assert ltrace('objects', '| LicornBaseObject.__init__()')
		self.name = name
		self.warnings = warnings
	def _valuable(self, attr_name, attr_value=None):
		if attr_value is None:
			attr_value = getattr(self, attr_name)
		return Enumeration._valuable(self, attr_name) \
			and not attr_value is False and not attr_value is True \
				and not attr_name in ('name', 'delegate', 'daemon', 'lastUsed',
					'objectGUID')

class LicornCoreObject(LicornBaseObject, Pyro.core.ObjBase):
	def __init__(self, name, warnings=True):
		Pyro.core.ObjBase.__init__(self)
		LicornBaseObject.__init__(self, name, warnings)
		assert ltrace('objects', '| LicornCoreObject.__init__()')
		# Create locks for the current CoreObject.
		lock_manager = Enumeration(name + '_lock')
		lock_manager.giant_lock = RLock()
		setattr(LMC.locks, self.name, lock_manager)
	def acquire(self):
		assert ltrace('thread', '%s: acquiring %s %s.' % (
			current_thread().name, self.name, self.lock()))
		self.lock().acquire()
	def acquire_lock(self):
		assert ltrace('thread', '%s: acquiring %s %s.' % (
			current_thread().name, self.name, self.lock()))
		self.lock().acquire()
	def lock(self):
		return getattr(getattr(LMC.locks, self.name), 'giant_lock')
	def release(self):
		assert ltrace('thread', '%s: releasing %s %s.' % (
			current_thread().name, self.name, self.lock()))
		self.lock().release()
	def release_lock(self):
		assert ltrace('thread', '%s: releasing %s %s.' % (
			current_thread().name, self.name, self.lock()))
		self.lock().release()
	def is_locked(self):
		""" WARNING: calling this method costs. """
		if self.lock().acquire(blocking=False):
			self.lock().release()
			return False
		return True
	def _release(self):
		""" fake method to not crash when daemon terminates. Yes, this is a hack."""
		pass

class LicornCoreController(LicornCoreObject):
	def __init__(self, name, warnings=True):
		LicornCoreObject.__init__(self, name, warnings)
		assert ltrace('objects', '| LicornCoreController.__init__()')
		self._prefered_backend_name = None
		self._prefered_backend_prio = None

		self.find_prefered_backend()
	def backends(self):
		assert ltrace(self.name, '| backends(%s -> %s)' % (
			str([ x.controllers_compat for x in LMC.backends ]),
			str([ backend for backend in LMC.backends if self.name in backend.controllers_compat ])))
		#print '--%s--' %
		return [ backend for backend in LMC.backends if self.name in backend.controllers_compat ]
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
class Machine(Enumeration):
	def __init__(self, mid=None, hostname=None, ether=None, expiry=None,
		lease_time=None, status=host_status.UNKNOWN, managed=False,
		system=None, system_type=host_types.UNKNOWN, **kwargs):

		#Enumeration has no __init__(self)

		# mid == IP address (unique on a given network)
		self.mid         = mid
		self.ip          = self.mid

		# hostname will be DNS-reversed from IP, or constructed.
		self.hostname    = hostname

		self.ether       = ether

		self.expiry      = expiry

		self.lease_time  = lease_time

		# will be updated as much as possible with the current host status.
		self.status      = status

		# True if the machine is recorded in local configuration files.
		self.managed     = managed

		# OS and OS level, arch, mixed in one integer.
		self.system_type = system_type

		# the Pyro proxy (if the machine has one) for contacting it across the
		# network.
		self.system      = system

		if self.mid is not None:
			LMC.locks.machines[self.mid] = RLock()

		for key, value in kwargs.iteritems():
			setattr(self, key, value)
	def __str__(self):
		return '%s(%s‣%s) = {\n\t%s\n\t}\n' % (
			self.__class__,
			stylize(ST_UGID, self.mid),
			stylize(ST_NAME, self.hostname),
			'\n\t'.join([ '%s: %s' % (attr_name, getattr(self, attr_name))
					for attr_name in dir(self) ])
			)
