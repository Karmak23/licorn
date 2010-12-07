# -*- coding: utf-8 -*-
"""
Licorn core.backends autoload facility.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os

from licorn.foundations        import logging
from licorn.foundations.styles import *
from licorn.foundations.ltrace import ltrace
from licorn.foundations.base   import Singleton, MixedDictObject

from licorn.core         import LMC
from licorn.core.classes import GiantLockProtectedObject

class BackendController(Singleton, GiantLockProtectedObject):
	_licorn_protected_attrs = (
			GiantLockProtectedObject._licorn_protected_attrs
			+ ['_available_backends']
		)
	def __init__(self):
		GiantLockProtectedObject.__init__(self, 'backends')
		self._available_backends = MixedDictObject(
			'BackendController._available_backends')
	#def _valuable(self, attr_name, attr_value=None):
	#	if attr_value is None:
	#		attr_value = getattr(self, attr_name)
	#
	#	return isinstance(attr_value, CoreBackend)
	def load(self):
		for entry in os.listdir(__path__[0]):
			if entry[0] == '_':
				continue
			if entry[-11:] == '_backend.py':
				modname      = entry[:-3]	# minus '.py'
				backend_name = entry[:-11]	# minus '_backend.py'
				assert ltrace('backends', 'importing backend %s' %
					stylize(ST_NAME, backend_name))

				pymod = __import__(modname, globals(), locals(),
					backend_name)
				backend = getattr(pymod, backend_name)

				assert ltrace('backends', 'loading backend %s' %
					stylize(ST_NAME, backend_name))
				# instanciate the controller into a backend object.
				#exec('backends.append(%s)' % backend_name)

				backend.load()

				if backend.available:
					if backend.enabled:
						self[backend.name] = backend
						assert ltrace('backends', 'loaded backend %s' %
							stylize(ST_NAME, backend.dump_status(True)))
					else:
						self._available_backends[backend.name] = backend
						assert ltrace('backends',
							'backend %s is only available' %
								stylize(ST_NAME, backend.name))
				else:
					assert ltrace('backends',
						'backend %s NOT available' %
							stylize(ST_NAME, backend.name))
					pass
	def enable_backend(self, backend):
		""" try to enable a given backend. what to do exactly is left to the
		backend itself."""

		assert ltrace('backends', '| enable_backend(%s, %s, %s)' % (backend,
			str([x for x in self.keys()]), self._available_backends.keys()))

		if backend in self.keys():
			logging.notice('%s backend already enabled.' % backend)
			return

		if self._available_backends[backend].enable():
			self[backend] = self._available_backends[backend]
			del self._available_backends[backend]
			self[backend].initialize()

			logging.notice('''successfully enabled %s backend.'''% backend)

		LMC.reload_controllers_backends()
	def disable_backend(self, backend):
		""" try to disable a given backend. what to do exactly is left to the
		backend itself."""

		assert ltrace('backends', '| disable_backend(%s, %s, %s)' % (backend,
			self.keys(), self._available_backends.keys()))

		if backend in self._available_backends.keys():
			logging.notice('%s backend already disabled.' % backend)
			return

		if self[backend].disable():
			self._available_backends[backend] = self[backend]
			del self[backend]
			logging.notice('''successfully disabled %s backend. ''' % backend)

		LMC.reload_controllers_backends()
	def check(self, batch=False, auto_answer=None):
		""" check all enabled backends, except the 'prefered', which is one of
		the enabled anyway.

		Checking them will make them configure themselves, and configure the
		underlying system daemons and tools.
		"""

		assert ltrace('backends', '> check()')

		for backend in self:
			assert ltrace('backends', '  check(%s)' % backend)
			backend.check(batch, auto_answer)

		# check the available_backends too. It's the only way to make sure they
		# can be fully usable before enabling them.
		for backend in self._available_backends:
			assert ltrace('backends', '  check(%s)' % backend)
			backend.check(batch, auto_answer)

		assert ltrace('backends', '< check()')
