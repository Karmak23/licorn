# -*- coding: utf-8 -*-
"""
Licorn Pickle backend - http://docs.licorn.org/core/backends/shadow.html

:copyright: 2011 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2.

.. versionadded:: 1.3
	This backend was previously known as **unix**, but has been
	renamed **shadow** during the 1.2 ⇢ 1.3 development cycle, to
	better match reality and avoid potential name conflicts.
"""

from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import Singleton
from licorn.core.backends         import UsersBackend, GroupsBackend, MachinesBackend

class PickleBackend(Singleton, UsersBackend, GroupsBackend, MachinesBackend):
	""" A backend to cope with /etc/* UNIX shadow traditionnal files.

	"""

	init_ok = False

	def __init__(self):

		assert ltrace_func(TRACE_PICKLE)

		if self.__class__.init_ok:
			return

		super(PickleBackend, self).__init__(name='pickle', priority=99)

		# this no-op backend is disabled for now
		self.available = False
		self.enabled   = False

		self.__class__.init_ok = True

		assert ltrace_func(TRACE_PICKLE, True)
