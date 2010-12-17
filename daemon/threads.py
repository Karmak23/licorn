# -*- coding: utf-8 -*-
"""
Licorn Daemon small threads.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import time

from threading   import Thread, Event, current_thread
from Queue       import Queue

from licorn.foundations           import logging, exceptions
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace

from licorn.daemon import dthreads

class LicornBasicThread(Thread):
	""" A simple thread with an Event() used to stop it properly. """

	def __init__(self, pname='<unknown>', tname=None):
		Thread.__init__(self)

		self.name  = "%s/%s" % (
			pname, tname if tname else
				str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self._stop_event  = Event()
		assert ltrace('thread', '%s initialized.' % self.name)
	def dump_status(self, long_output=False, precision=None):
		return '%s(%s%s) %s.' % (
				stylize(ST_NAME, self.name),
				self.ident, stylize(ST_OK, '&') if self.daemon else '',
				stylize(ST_OK, 'alive') \
					if self.is_alive() else 'has terminated')
	def run(self):
		# don't call Thread.run(self), just override it.
		assert ltrace('thread', '%s running' % self.name)
	def finish(self):
		assert ltrace('thread', '%s ended' % self.name)
	def stop(self):
		""" Stop current Thread. """
		assert ltrace('thread', '%s stopping' % self.name)
		self._stop_event.set()
class LicornPoolJobThread(Thread):
	def __init__(self, in_queue, target, pname='<unknown>', tname='PoolJobber',
		target_args=(), target_kwargs={}, daemon=False):
		Thread.__init__(self)

		self.name  = "%s/%s" % (
			pname, tname if tname else
				str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self.input_queue = in_queue
		self.target = target
		self.args = target_args
		self.kwargs = target_kwargs
		self.daemon = daemon

		#: used in dump_status (as a display info only), to know which
		#: object our target function is running onto.
		self.current_target_object = None
		assert ltrace('thread', '%s initialized.' % self.name)
	def dump_status(self, long_output=False, precision=None):
		""" get detailled thread status. """

		if long_output:

			target = str(self.target).replace('function ', '').replace(' at ', '|')

			return '%s(%s%s) %s(%s) ‣ %s(%s, %s, %s)' % (
					stylize(ST_NAME, self.name),
					self.ident, stylize(ST_OK, '&') if self.daemon else '',
					str(self.input_queue).replace(' instance at ', '|'),
					stylize(ST_UGID, self.input_queue.qsize()),
					'%s…' % str(target)[:29] \
						if len(str(target)) >= 30 else str(target),
					self.current_target_object, self.args, self.kwargs
				)
		else:
			return '%s(%s%s) %s.' % (
					stylize(ST_NAME, self.name),
					self.ident, stylize(ST_OK, '&') if self.daemon else '',
					'%s, [on‣%s]' % (stylize(ST_OK, 'alive'),
						self.current_target_object) \
						if self.is_alive() else 'has terminated')
	def run(self):
		assert ltrace('thread', '%s running' % self.name)
		while True:
			msg = self.input_queue.get()
			if msg is None:
				# None is a fake message to unblock the q.get(), when the
				# main process terminates the current thread with stop(). We
				# emit task_done(), else the main process will block forever
				# on q.join().
				self.input_queue.task_done()
				break
			else:
				assert ltrace('thread', 'executing %s(%s, %s)' % (self.target,
					self.args, self.kwargs))
				self.current_target_object = msg
				self.target(msg, *self.args, **self.kwargs)
				self.current_target_object = None
				self.input_queue.task_done()

		assert ltrace('thread', '%s ended' % self.name)
	def stop(self):
		assert ltrace('thread', '%s stopping' % self.name)
		self.input_queue.put_nowait(None)
class QueueWorkerThread(Thread):
	""" Finer implementation of LicornPoolJobThread. Let


		new in version 1.2.3
	"""
	#: :attr:`number` is used to create the unique thread name. It is always
	#: incremented, and thus helps keeping some sort of history.
	number = 0

	#: :attr:`count` is the current number of instances. It is incremented at
	#: :meth:`__init__` and decremented at :meth:`__del__`.
	count = 0
	def __init__(self, in_queue, name='QueueWorkerThread',
		target_args=(), target_kwargs={}, daemon=False):
		Thread.__init__(self)

		assert self.__class__.number is not None
		assert self.__class__.count is not None

		#: the threading.Thread attribute.
		self.name  = '%s-%d' % (str(self.__class__.name), self.__class__.number)

		#: our master queue, from which we get job to do (objects to process).
		self.input_queue = in_queue

		#: optional args for our :meth:`self.process`.
		self.args = target_args

		#: optional kwargs for our :meth:`self.process`.
		self.kwargs = target_kwargs

		#: the :attr:`daemon` coming from threading.Thread.
		self.daemon = daemon

		#: used in dump_status (as a display info only), to know which
		#: object our target function is running onto.
		self.current_target = None

		assert ltrace('thread', '%s initialized.' % self.name)
		self.__class__.number += 1
		self.__class__.count += 1
	def __del__(self):
		self.__class__.count -= 1
	def dump_status(self, long_output=False, precision=None):
		""" get detailled thread status. """

		if long_output:

			target = str(self.target).replace('function ', '').replace(' at ', '|')

			return '%s(%s%s) %s(%s) ‣ %s(%s, %s, %s)' % (
					stylize(ST_NAME, self.name),
					self.ident, stylize(ST_OK, '&') if self.daemon else '',
					str(self.input_queue).replace(' instance at ', '|'),
					stylize(ST_UGID, self.input_queue.qsize()),
					'%s…' % str(target)[:29] \
						if len(str(target)) >= 30 else str(target),
					self.current_target, self.args, self.kwargs
				)
		else:
			return '%s(%s%s) %s.' % (
					stylize(ST_NAME, self.name),
					self.ident, stylize(ST_OK, '&') if self.daemon else '',
					'%s, [on‣%s]' % (stylize(ST_OK, 'alive'),
						self.current_target) \
						if self.is_alive() else 'has terminated')
	def run(self):
		assert ltrace('thread', '%s running' % self.name)
		assert hasattr(self, 'process') and callable(self.process)

		while True:
			self.current_target = self.input_queue.get()

			if self.current_target is None:
				# None is a fake message to unblock the q.get(), when the
				# main process terminates the current thread with stop(). We
				# emit task_done(), else the main process will block forever
				# on q.join().
				self.input_queue.task_done()
				break

			else:
				assert ltrace('thread', 'executing self.process(%s, %s, %s)' % (
					self.current_target, self.args, self.kwargs))

				self.process(self.current_target, *self.args, **self.kwargs)
				self.current_target = None
				self.input_queue.task_done()

		assert ltrace('thread', '%s ended' % self.name)
	def stop(self):
		assert ltrace('thread', '%s stopping' % self.name)
		self.input_queue.put_nowait(None)
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
		assert ltrace('thread', '%s initialized' % self.name)
	def dispatch_message(self, msg):
		""" get an incoming message in a generic way. """
		self._input_queue.put(msg)
	def run(self):
		""" Process incoming messages until stop Event() is set. """
		# don't call Thread.run(self), just override it.
		assert ltrace('thread', '%s running' % self.name)

		while not self._stop_event.isSet():
			data = self._input_queue.get()
			if data is None:
				break
			self.process_message(data)
			self._input_queue.task_done()

		assert ltrace('thread', '%s ended' % self.name)
	def stop(self):
		""" Stop current Thread
		and put a special None entry in the queue, to be
		sure that self.run() method exits properly. """
		assert ltrace('thread', '%s stopping' % self.name)
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

		assert ltrace('thread', '''| LicornJobThread.__init__(target=%s, '''
			'''time=%s, count=%s, delay=%s, loop=%s)''' % (self.target,
				self.time, self.count, self.delay, self.loop))

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

		current_delay = 0.005
		while current_delay < delay and not self._stop_event.isSet():
			#print "waiting %.1f < %.1f" % (current_delay, self.delay)
			time.sleep(0.005)
			current_delay += 0.005
	def run(self):
		LicornBasicThread.run(self)

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
		LicornBasicThread.finish(self)
class StatusUpdaterThread(LicornBasicThread):
	def __init__(self):
		pass
	def run(self):
		""" connect to local dbus system bus and forward every status change to
			our controlling server. """
		pass

def thread_periodic_cleaner():
	""" Ping all known machines. On online ones, try to connect to pyro and
	get current detailled status of host. Notify the host that we are its
	controlling server, and it should report future status change to us.

	LOCKED to avoid corruption if a reload() occurs during operations.
	"""

	caller = current_thread().name

	assert ltrace('system', '> %s:thread_cleaner()' % caller)

	for (tname, thread) in dthreads.items():
		if not thread.is_alive():
			del dthreads[tname]
			del thread
			logging.info('%s: wiped dead thread %s from memory.' % (
				caller, stylize(ST_NAME, tname)))

	assert ltrace('system', '< %s:thread_cleaner()' % caller)
