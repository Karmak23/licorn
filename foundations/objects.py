# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

objects - ultra basic objects, used as base classes.

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2

"""
from Queue              import Queue
from threading          import Thread, Event
from licorn.foundations import exceptions, logging

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

		Every subclass must implement a process_message() method, which will be called
		by the main loop until the thread stops.
	"""

	def __init__(self, pname = '<unknown>') :
		self.name  = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))


		self._stop_event  = Event()
		self._input_queue = Queue()
		#logging.progress('%s: thread initialized.' % self.name)
	def dispatch_message(self, msg) :
		""" get an incoming message in a generic way. """
		self._input_queue.put(msg)
	def run(self) :
		""" Process incoming messages until stop Event() is set. """

		logging.progress('%s: thread started.' % self.name)

		while not self._stop_event.isSet() :
			data = self._input_queue.get()
			if data is None : break
			self.process_message(data)

		logging.progress('%s: thread ended.' % self.name)
	def stop(self) :
		""" Stop current Thread
		and put a special None entry in the queue, to be
		sure that self.run() method exits properly. """
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


