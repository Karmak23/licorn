# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

objects - ultra basic objects, used as base classes.

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2

"""
from Queue              import Queue
from threading          import Thread, Event
from licorn.foundations import exceptions

class Singleton(object) :
	__instances = {}
	def __new__(cls, *args, **kargs): 
		if Singleton.__instances.get(cls) is None:
			Singleton.__instances[cls] = object.__new__(cls, *args, **kargs)
		return Singleton.__instances[cls]

class LicornThread(Thread) :
	"""
		A simple thread with an Event() used to stop it properly, and a Queue() to
		get events from other threads asynchronically.
	"""

	def __init__(self, pname = '<unknown>') :
		self.name  = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		self._stop_event  = Event()
		self._input_queue = Queue()
	def dispatch_message(msg) :
		self._input_queue.put(msg)
	def run(self) :

		if callable(getattr(self, 'process_message')) :
			raise exceptions.LicornRuntimeError("%s: no process_message() method !!" % self.name)
		
		logging.progress('%s: started.' % self.name)
		while not self._stop_event().isSet() :
			data = self._input_queue.get()
			if data is None :
				continue
			self.process_message(data)
		logging.progress('%s: stopped.' % self.name)
	def stop(self) :
		logging.progress('%s: stopping thread.' % self.name)
		self._stop_event.set()
		self._input_queue.put(None)

class StateMachine :
	"""
		A Finite state machine design pattern.
		Found at http://www.ibm.com/developerworks/library/l-python-state.html , thanks to David Mertz.
	"""

	def __init__(self) :
		self.handlers = {}
		self.startState = None
		self.endStates = []

	def add_state(self, name, handler, end_state = False) :
		self.handlers[name] = handler
		if end_state :
			 self.endStates.append(name)

	def set_start(self, name) :
		self.startState = name

	def run(self, data) :
		try :
			 handler = self.handlers[self.startState]
		except :
			 raise exceptions.LicornRuntimeError("LSM: must call .set_start() before .run()")

		if not self.endStates :
				 raise exceptions.LicornRuntimeError("LSM: at least one state must be an end_state.")

		while True :
			(newState, data) = handler(data)
			if newState in self.endStates :
				break 
			else :
				handler = self.handlers[newState]


