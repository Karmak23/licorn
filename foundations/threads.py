# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

objects - ultra basic objects, used as base classes.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""
# http://stackoverflow.com/questions/2231427/error-when-calling-the-metaclass-bases-function-argument-1-must-be-code-not
from threading import current_thread, active_count, enumerate, _RLock as _TRLock, _Event as _TEvent, Lock

from styles  import *
from ltrace  import *
from ltraces import *

def _threads():
	return ', '.join([ '%s%s' % (x.name,
		stylize(ST_NOTICE, '&') if x.daemon else '') \
			for x in enumerate() ])

def _thcount():
	return stylize(ST_UGID, active_count())


if __debug__ and ltrace_level & TRACE_LOCKS:
	# Lock is a function in python dist classes, we cannot subclass
	# it. Bummer!

	class RLock(_TRLock):
		instances = []
		def __init__(self, *args, **kwargs):
			super(RLock, self).__init__(*args, **kwargs)
			self.__class__.instances.append(self)
		def locked(self):
			if self.acquire(0):
				self.release()
				return False
			return True
		def acquire(self, blocking=1):
			assert ltrace_locks(self)
			lprint(current_thread())
			return super(RLock, self).acquire(blocking)
		def release(self):
			super(RLock, self).release()
			#assert ltrace_locks(self)

		@classmethod
		def dump(cls):
			return [ x for x in cls.instances if x.locked() ]

	class Event(_TEvent):
		instances = []
		def __init__(self, *args, **kwargs):
			super(Event, self).__init__(*args, **kwargs)
			self.__class__.instances.append(self)
		@classmethod
		def dump(cls):
			return [ x for x in cls.instances if x.is_set() ]

else:
	RLock = _TRLock
	Event = _TEvent
