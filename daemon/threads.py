# -*- coding: utf-8 -*-
"""
Licorn Daemon small threads.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import time

import gobject
import dbus.mainloop.glib

from threading   import Thread, Event, RLock, current_thread
from Queue       import Queue

from licorn.foundations           import logging, exceptions, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace

from licorn.daemon import dthreads, dname

class DbusThread(Thread):
	""" Run the d-bus main loop (from gobject) in a separate thread, because
		we've got many other things to do besides it ;-)

		Please don't forget to read:

		* http://dbus.freedesktop.org/doc/dbus-python/api/dbus.mainloop.glib-module.html
		* http://jameswestby.net/weblog/tech/14-caution-python-multiprocessing-and-glib-dont-mix.html
		* http://zachgoldberg.com/2009/10/17/porting-glib-applications-to-python/

	"""
	def __init__(self, pname='<unknown>', tname=None):
		# Setup the DBus main loop
		Thread.__init__(self)

		self.name  = "%s/%s" % (
			pname, tname if tname else
				str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		gobject.threads_init()
		dbus.mainloop.glib.threads_init()
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		self.mainloop = gobject.MainLoop()
	def run(self):
		self.mainloop.run()
	def stop(self):
		self.mainloop.quit()
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
class LicornBasicThread(Thread):
	""" A simple thread with an Event() used to stop it properly. """

	def __init__(self, pname=dname, tname=None):
		Thread.__init__(self)

		self.name = "%s/%s" % (pname, tname if (pname and tname) else
				str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self._stop_event  = Event()
		assert ltrace('thread', '%s initialized.' % self.name)
	def dump_status(self, long_output=False, precision=None):
		return '%s%s (stop=%s)' % (
				stylize(ST_RUNNING
					if self.is_alive() else ST_STOPPED, self.name),
				'&' if self.daemon else '',
				self._stop_event.is_set()
			)
	def run(self):
		""" default run method, which calls:

			* pre_run_method one time without arguments, if it exists.
			* run_action_method multiple times during a while loop until stopped.
			* post_run_method one time without arguments, if it exists.

			.. versionadded:: 1.2.4
				In previous versions, this run method didn't exist at all
				(this call was purely abstract).
		"""

		# don't call Thread.run(self), just override it.
		assert ltrace('thread', '%s running' % self.name)

		assert hasattr(self, 'run_action_method')

		if hasattr(self, 'pre_run_method'):
			getattr(self, 'pre_run_method')()

		while not self._stop_event.is_set():
			self.run_action_method()

		if hasattr(self, 'post_run_method'):
			getattr(self, 'post_run_method')()

		self.finish()
	def finish(self):
		assert ltrace('thread', '%s ended' % self.name)
	def stop(self):
		""" Stop current Thread. """
		assert ltrace('thread', '%s stopping' % self.name)
		self._stop_event.set()
class QueueWorkerThread(Thread):
	""" Finer implementation of old LicornPoolJobThread (removed).


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
		self.job_start_time = None

		assert ltrace('thread', '%s initialized.' % self.name)
		self.__class__.number += 1
		self.__class__.count += 1
	def __del__(self):
		self.__class__.count -= 1
	def dump_status(self, long_output=False, precision=None):
		""" get detailled thread status. """

		return '%s%s [%s]' % (
				stylize(ST_RUNNING
					if self.is_alive() else ST_STOPPED, self.name),
				'&' if self.daemon else '',
				'on %s for %s' % (stylize(ST_ON, self.current_target),
					pyutils.format_time_delta(
							time.time() - self.job_start_time,
							big_precision=True))
					if self.current_target else 'idle'
			)
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
				self.job_start_time = time.time()
				assert ltrace('thread', 'executing self.process(%s, %s, %s)' % (
					self.current_target, self.args, self.kwargs))

				self.process(self.current_target, *self.args, **self.kwargs)
				self.current_target = None
				self.job_start_time = None
				self.input_queue.task_done()

		assert ltrace('thread', '%s ended' % self.name)
	def stop(self):
		assert ltrace('thread', '%s stopping' % self.name)
		self.input_queue.put_nowait(None)
class TriggerWorkerThread(LicornBasicThread):
	def __init__(self, target, trigger_event, args=(), kwargs={},
												pname=dname, tname=None):
		assert ltrace('thread', '| TriggerWorkerThread.__init__()')
		LicornBasicThread.__init__(self, pname, tname)
		self._disable_event     = Event()
		self._currently_running = Event()
		self._trigger_event     = trigger_event

		self.target = target
		self.args   = args
		self.kwargs = kwargs

		# used on manual triggering only.
		self.one_time_args   = None
		self.one_time_kwargs = None
	def dump_status(self, long_output=False, precision=None):
		return '%s%s (%s)' % (
			stylize(ST_RUNNING if self.is_alive() else ST_STOPPED, self.name),
			'&' if self.daemon else '',
			stylize(ST_OFF, 'disabled') if self._disable_event.is_set()
					else '%s, %s' % (
							stylize(ST_ON, 'enabled'),
							stylize(ST_ON, 'active') if
								self._currently_running.is_set() else 'idle'
						)
			)
	def active(self):
		""" Returns ``True`` if the internal worker is running, else ``False``
			(the thread can be considered idle). """

		return self._currently_running.is_set()
	#: an alias from :meth:`running` to :meth:`active`.
	running = active
	def idle(self):
		""" Exact inverse of :meth:`active` method. """
		return not self._currently_running.is_set()
	def enabled(self):
		""" Returns ``True`` if not currently disabled. """
		return not self._disable_event.is_set()
	def disabled(self):
		"""Exact inverse of :meth:`enabled` method. """
		return self._disable_event.is_set()
	def run(self):
		# don't call Thread.run(self), just override it.
		assert ltrace('thread', '%s running' % self.name)

		while True:
			self._trigger_event.wait()

			# be sure to wait at next loop.
			self._trigger_event.clear()

			if self._stop_event.is_set():
				assert ltrace('thread', '%s: breaking our loop now.' % self.name)
				break

			if self._disable_event.is_set():
				assert ltrace('thread', '%s: triggered, but currently '
					'disabled: not doing anything.' % self.name)
				continue

			# use one_time arguments if we have been manually trigerred.
			if self.one_time_args is not None:
				args = self.one_time_args
				self.one_time_args = None
			else:
				args = self.args

			if self.one_time_kwargs is not None:
				kwargs = self.one_time_kwargs
				self.one_time_kwargs = None
			else:
				kwargs = self.kwargs

			assert ltrace('thread', '%s: triggered, running target %s(%s, %s)'
				% (self.name, self.target, ', '.join(args), ', '.join(kwargs)))

			self._currently_running.set()
			self.target(*args, **kwargs)
			self._currently_running.clear()

		self.finish()
	def trigger(self, *args, **kwargs):
		""" Trigger a worker run if we are not currently stopping. """
		assert ltrace('thread', '| TriggerWorkerThread.trigger()')
		self.one_time_args = args
		self.one_time_kwargs = kwargs
		if not self._stop_event.is_set():
			return self._trigger_event.set()
	#: An alias from :meth:`manual_trigger` to :meth:`trigger` for purists.
	manual_trigger = trigger
	def disable(self):
		""" Disable next runs (until re-enabled), but only if we are not
			currently stopping. """
		assert ltrace('thread', '| TriggerWorkerThread.disable()')
		if not self._stop_event.is_set():
			return self._disable_event.set()
	def enable(self):
		assert ltrace('thread', '| TriggerWorkerThread.enable()')
		return self._disable_event.clear()
	def stop(self):
		""" Stop the thread properly (things must be done in a certain order,
			internally). """

		# Stop the base things. At this moment, the thread is either waiting
		# on the trigger, or running.
		LicornBasicThread.stop(self)

		# Then be sure to release the wait() on the trigger,
		# else we will never quit...
		self._trigger_event.set()
class AbstractTimerThread(LicornBasicThread):
	""" Base (abstract) class for any advanced timer thread:

		* the thread can loop any number of time (0 to infinite). 0 means it is
		  a one shot timer, 1 or more means it is like a scheduled job (but no
		  date handling yet).
		* it can wait a specific time before starting to loop.
		* the timer can be reset at any moment.

		:param time: is a time.time() object before first execution, or for
				one-shot jobs ("AT" like)
		:param count: eventually the number of time you want the job to repeat (>0)
				default: None => infinite loop
		:param delay: a float in seconds to wait between each call when looping.
				Only used in loop.

			If looping (infinite or not), delay must be set.

			args and kwargs are for target, which will be executed at least once.

			tname is an optionnal thread name, to differentiate each, if you
			launch more than one JobThread.

		.. versionadded:: 1.2.4

		.. warning:: This class is an abstract one, it does nothing besides
			sleeping. All inheriting classes must implement a
			``run_action_method``, else they will fail.

	"""
	def __init__(self, pname=dname, tname=None, time=None, count=None,
		delay=0.0, daemon=False):
		"""
		"""

		LicornBasicThread.__init__(self, pname=pname, tname=tname)

		self.time = time
		self.delay = delay
		self.count = count
		self.daemon = daemon

		# lock used when accessing self.time_elapsed and self.sleep_delay
		self.time_lock = RLock()

		# these 2 variable are internal to the sleep() method, but can be used
		# R/O in remaining_time().
		self.__time_elapsed = 0.0
		self.__sleep_delay  = None

		# used when we want to reset the timer.
		self._reset_event = Event()
		# a parallel thread that will run the real job, to be able to continue
		# to countdown the delay while job is running.

		if self.count is None:
			self.loop = True
		else:
			if self.count <= 0:
				raise exceptions.BadArgumentError('count can only be > 0')
			elif self.count >= 1:
				self.loop = False

		assert ltrace('thread', '| AbstractTimerThread.__init__(time=%s, '
			'count=%s, delay=%s, loop=%s)' % (self.time,
				self.count, self.delay, self.loop))

		if (self.loop or self.count) and self.delay is None:
			raise exceptions.BadArgumentError(
				'must provide a delay for looping.')
	def sleep(self, delay=None):
		""" sleep at most self.delay, but with smaller intervals, to allow
			interruption without waiting to the end of self.delay, which can
			be very long.
		"""

		if delay:
			self.__sleep_delay = delay
		else:
			self.__sleep_delay = self.delay


		assert ltrace('thread', '| %s.sleep(%s)' % (self.name, delay))

		with self.time_lock:
			self.__time_elapsed = 0.0

		while self.__time_elapsed < self.__sleep_delay and not self._stop_event.is_set():
			#print "waiting %.1f < %.1f" % (current_delay, self.delay)
			time.sleep(0.01)
			with self.time_lock:
				self.__time_elapsed += 0.01
			if self._reset_event.is_set():
				logging.progress('%s: timer reset after %s elapsed.' % (self.name,
						pyutils.format_time_delta(self.__time_elapsed)))
				with self.time_lock:
					self.__time_elapsed = 0.0
				self._reset_event.clear()
	def reset_timer(self):
		self._reset_event.set()
	#: :meth:`reset` is an alias to :meth:`reset_timer`
	reset = reset_timer
	def remaining_time(self):
		""" Returns the remaining time until next target execution, in seconds.
		"""
		with self.time_lock:
			if self.__sleep_delay is None:
				raise exceptions.LicornRuntimeException(
										'%s: not yet started.' % self.name)
			return self.__sleep_delay - self.__time_elapsed
	def run(self):
		""" TODO. """

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

		while not self._stop_event.is_set() and	(
				self.loop or self.current_loop < self.count):

			self.run_action_method()

			self.current_loop += 1
			self.sleep()
		LicornBasicThread.finish(self)
class TriggerTimerThread(AbstractTimerThread):
	""" A Timer Thread whose sole action is to trigger an
		:class:`~threading.Event`. It is used in conjunction of the
		:class:`TriggerWorkerThread` (which waits on the
		:class:`~threading.Event`).

		.. versionadded:: 1.2.4
	"""
	def __init__(self, trigger_event, pname=dname, tname=None, time=None, count=None,
		delay=0.0, daemon=False):
		AbstractTimerThread.__init__(self, time=time, count=count, delay=delay,
			daemon=daemon, pname=pname, tname=tname)

		self._trigger_event = trigger_event
	def run_action_method(self):
		return self._trigger_event.set()
class LicornJobThread(AbstractTimerThread):
	def __init__(self, target, pname=dname, tname=None, time=None, count=None,
		delay=0.0, target_args=(), target_kwargs={}, daemon=False):
		""" TODO: this class is meant to be removed in version 1.3+, replaced
			by the couple
			:class:`TriggerWorkerThread` / :class:`TriggerTimerThread`.
		"""

		AbstractTimerThread.__init__(self, time=time, count=count, delay=delay,
			daemon=daemon, pname=pname, tname=tname)

		self.target = target
		self.args = target_args
		self.kwargs = target_kwargs

		# a parallel thread that will run the real job, to be able to continue
		# to countdown the delay while job is running.
		self.job_runner = None
	def run_action_method(self):
		""" A method that will wrap self.target into a JobRunner simple
			:class:`~threading.Thread`. """

		if (not self.job_runner) or (not self.job_runner.is_alive()):
			self.job_runner = Thread(
					target=self.target,
					name=self.name + '.JobRunner',
					args=self.args,
					kwargs=self.kwargs
				)
			self.job_runner.daemon = True
			self.job_runner.start()
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
