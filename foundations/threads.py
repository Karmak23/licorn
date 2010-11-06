# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

objects - ultra basic objects, used as base classes.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""
import time

from Queue              import Queue
from threading          import Thread, Event

import exceptions, styles, logging
from ltrace    import ltrace
from constants import message_type, verbose, interactions

class LicornBasicThread(Thread):
	""" A simple thread with an Event() used to stop it properly. """

	def __init__(self, pname='<unknown>', tname=None):
		Thread.__init__(self)

		self.name  = "%s/%s" % (
			pname, tname if tname else
				str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self._stop_event  = Event()
		logging.progress('%s: thread initialized.' % self.name)
	def stop(self):
		""" Stop current Thread. """
		logging.progress('%s: stopping thread.' % self.name)
		self._stop_event.set()
class LicornThread(Thread):
	"""
		A simple thread with an Event() used to stop it properly, and a Queue() to
		get events from other threads asynchronically.

		Every subclass must implement a process_message() method, which will be called
		by the main loop until the thread stops.
	"""

	def __init__(self, pname='<unknown>', tname=None):
		Thread.__init__(self)

		self.name  = "%s/%s" % (
			pname, tname if tname else
				str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self._stop_event  = Event()
		self._input_queue = Queue()
		logging.progress('%s: thread initialized.' % self.name)
	def dispatch_message(self, msg):
		""" get an incoming message in a generic way. """
		self._input_queue.put(msg)
	def run(self):
		""" Process incoming messages until stop Event() is set. """
		Thread.run(self)
		logging.progress('%s: thread started.' % self.name)

		while not self._stop_event.isSet():
			data = self._input_queue.get()
			if data is None:
				break
			self.process_message(data)
			self._input_queue.task_done()

		logging.progress('%s: thread ended.' % self.name)
	def stop(self):
		""" Stop current Thread
		and put a special None entry in the queue, to be
		sure that self.run() method exits properly. """
		logging.progress('%s: stopping thread.' % self.name)
		self._stop_event.set()
		self._input_queue.put(None)
class LicornJobThread(LicornBasicThread):
	def __init__(self, name, target, time=None, count=None, delay=0.0,
		tname=None,	target_args=(), target_kwargs={}):
		""" Create a scheduled job thread.
			time: is a time.time() object before first execution, or for
				one-shot jobs ("AT" like)
			count: eventually the number of time you want the job to repeat (>0)
				default: None => infinite loop
			delay: a float in seconds to wait between each call when looping.
				Only used in loop.

			If looping (infinite or not), delay must be set.

			args and kwargs are for target, which will be executed at least once.

			tname is an optionnal thread name, to differentiate each, if you
			launch more than one JobThread.
		"""

		LicornBasicThread.__init__(self, name, tname)

		self.target = target
		self.time = time
		self.delay = delay
		self.count = count
		self.args = target_args
		self.kwargs = target_kwargs

		#print 'caller %s for target %s' % (self.kwargs, self.target)

		if self.count is None:
			self.loop = True
		else:
			if self.count <= 0:
				raise exceptions.BadArgumentError('count can only be > 0')
			elif self.count >= 1:
				self.loop = False

		assert ltrace('thread', '''| LicornJobThread.__init__(target=%s, time=%s, '''
			'''count=%s, delay=%s, loop=%s)''' % (self.target, self.time,
				self.count, self.delay, self.loop))

		if (self.loop or self.count) and self.delay is None:
			raise exceptions.BadArgumentError(
				'must provide a delay for looping.')
	def sleep(self, delay=None):
		""" sleep at most self.delay, but with smaller intervals, to allow
			interruption without waiting to the end of self.delay, which can
			be very long.
		"""

		if delay is None:
			delay = self.delay

		current_delay = 0.0
		while current_delay < delay and not self._stop_event.isSet():
			#print "waiting %.1f < %.1f" % (current_delay, self.delay)
			time.sleep(0.1)
			current_delay += 0.1
	def run(self):
		LicornBasicThread.run(self)
		logging.progress('%s: thread started.' % self.name)

		self.current_loop = 0

		# first occurence: we need to wait until time if it is set.
		if self.time:
			# only sleep 'til initial time if not already passed. Else just run
			# the loop, to have the job done as soon as possible.
			first_delay = self.time - time.time()
			if first_delay > 0:
				self.sleep(first_delay)
		elif self.delay:
			# we just have to wait a delay before starting (this is a
			# simple timer thread).
			self.sleep()

		while not self._stop_event.isSet() and \
			(self.loop or self.current_loop < self.count):

			#logging.progress('%s: calling %s(%s)' % (self.name, self.target, self.kwargs)
			self.target(*self.args, **self.kwargs)

			self.current_loop += 1
			self.sleep()
		logging.progress('%s: thread ended.' % self.name)
