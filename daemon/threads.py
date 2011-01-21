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

class DbusThread(Thread):
	""" Run the d-bus main loop (from gobject) in a separate thread, because
		we've got many other things to do besides it ;-)

		Please don't forget to read:

		* http://dbus.freedesktop.org/doc/dbus-python/api/dbus.mainloop.glib-module.html
		* http://jameswestby.net/weblog/tech/14-caution-python-multiprocessing-and-glib-dont-mix.html
		* http://zachgoldberg.com/2009/10/17/porting-glib-applications-to-python/

	"""
	def __init__(self, daemon):
		# Setup the DBus main loop
		assert ltrace('dbus', '| DbusThread.__init__()')
		Thread.__init__(self)
		self.name  = "%s/%s" % (daemon.dname, dbus)

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

	def __init__(self, pname='<UNSET>', tname=None):
		Thread.__init__(self)

		self.name = "%s/%s" % (pname, tname if tname else
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
class ServiceWorkerThread(Thread):
	""" A thread which get random things to do from a priority queue, and
		auto-sizes a bounded peer-threads pool to help get work done.

		.. note:: This class isn't meant to be derived in any way.

		.. versionadded:: 1.2.5

	"""
	#: just a friendly name
	base_name = 'ServiceWorker'

	#: :attr:`number` is used to create the unique thread name. It is always
	#: incremented, and thus helps keeping some sort of history.
	number = 0

	#: :attr:`count` is the current number of instances. It is incremented at
	#: :meth:`__init__` and decremented at :meth:`__del__`.
	instances = 0

	class_lock = RLock()
	def __init__(self, in_queue, licornd, daemon=True):
		assert ltrace('thread', '| ServiceWorkerThread.__init__(%s)' % ServiceWorkerThread.number)
		Thread.__init__(self)

		#: the threading.Thread attribute.
		self.name = '%s-%d' % (ServiceWorkerThread.base_name, ServiceWorkerThread.number)

		#: a reference to the Licorn, daemon to get the configuration,
		#: pass to peer threads, and manage threads list.
		self.licornd = licornd

		self.threads_max = self.licornd.configuration.threads.service_max
		self.threads_min = self.licornd.configuration.threads.service_min

		#: our master queue, from which we get job to do (objects to process).
		self.input_queue = in_queue

		#: the :attr:`daemon` coming from threading.Thread.
		self.daemon = daemon

		#: used in dump_status (as a display info only), to know which
		#: object our target function is running onto.
		self.job = None
		self.job_start_time = None

		with self.class_lock:
			ServiceWorkerThread.number += 1
			ServiceWorkerThread.instances += 1
	def dump_status(self, long_output=False, precision=None):
		""" get detailled thread status. """

		return '%s%s [%s]' % (
				stylize(ST_RUNNING
					if self.is_alive() else ST_STOPPED, self.name),
				'&' if self.daemon else '',
				'on %s for %s' % (stylize(ST_ON, self.job),
					pyutils.format_time_delta(
							time.time() - self.job_start_time,
							big_precision=True))
					if self.job else 'idle'
			)
	def run(self):
		assert ltrace('thread', '> %s.run()' % self.name)

		#print '>> instances', self.instances

		self.throttle()

		while True:
			priority, self.job = self.input_queue.get()

			if self.job is None:
				# None is a fake message to unblock the q.get(), when the
				# main process terminates the current thread with stop(). We
				# emit task_done(), else the main process will block forever
				# on q.join().
				self.input_queue.task_done()
				break

			else:
				self.job_start_time = time.time()
				assert ltrace('thread', '%s: running job %s' % (
														self.name, self.job))
				self.job()
				self.job = None
				self.job_start_time = None
				self.input_queue.task_done()

			self.throttle()

		with self.class_lock:
			ServiceWorkerThread.instances -= 1

		assert ltrace('thread', '< %s.run()' % self.name)
	def throttle(self):
		# FIRST, see if peers are in need of help: if there are
		# still a lot of job to do, spawn another peer to get the
		# job done, until the configured thread limit is reached.

		if ServiceWorkerThread.instances < self.threads_min or (
				self.input_queue.qsize() > 2 * ServiceWorkerThread.instances
				and ServiceWorkerThread.instances < self.threads_max
			):
			#~ assert ltrace('thread', '  %s: spawing a new peer to help (%d < %d or %d > %d and %d < %d).'
																#~ % (self.name,
																#~ ServiceWorkerThread.instances, self.threads_min,
																#~ self.input_queue.qsize(), 2 * ServiceWorkerThread.instances,
																#~ ServiceWorkerThread.instances, self.threads_max))
			peer = self.__class__(self.input_queue, self.licornd, self.daemon)
			self.licornd.threads.append(peer)
			peer.start()

		# SECOND: see if jobs have been worked out during the time
		# we spent joing our job. If things have settled, signify to
		# one of the peers to terminate (this could be me, or not),
		# but only if there are still more peers than the configured
		# lower limit.

		elif self.input_queue.qsize() <= ServiceWorkerThread.instances/2 \
						and ServiceWorkerThread.instances > self.threads_min:
			assert ltrace('thread', '  %s: terminating because running out '
				'of jobs (%d <= %d and %d > %d).' % (self.name, self.input_queue.qsize(),
				ServiceWorkerThread.instances/2, ServiceWorkerThread.instances, self.threads_min))
			self.stop()

	def stop(self):
		assert ltrace('thread', '| %s.stop()' % self.name)
		self.input_queue.put_nowait((-1, None))

		# if we are in the process of settling down, tell the
		# master thread cleaner to search for terminated threads to wipe.
		try:
			self.licornd.threads.cleaner.trigger(0.1)
		except AttributeError:
			# if daemon is stopping, cleaner could be already wiped out.
			pass
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
	def __init__(self, pname='<UNSET>', tname=None, time=None, count=None,
		delay=0.0, daemon=False):

		LicornBasicThread.__init__(self, pname=pname, tname=tname)

		self.time   = time
		self.delay  = delay
		self.count  = count
		self.daemon = daemon

		# lock used when accessing self.time_elapsed and self.sleep_delay
		self._time_lock = RLock()

		# these 2 variable are internal to the sleep() method, but can be used
		# R/O in remaining_time().
		self.__time_elapsed = 0.0
		self.__sleep_delay  = None

		#: used when we want to reset the timer, without running our action.
		self._reset_event = Event()

		#: used when we force running our action without waiting the full
		#: delay. This event is triggered from the outside using methods.
		self._trigger_event = Event()
		self.__trigger_delay = None

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

		with self._time_lock:
			self.__time_elapsed = 0.0

		while self.__time_elapsed < self.__sleep_delay and not self._stop_event.is_set():
			#print "waiting %.1f < %.1f" % (current_delay, self.delay)
			time.sleep(0.01)
			with self._time_lock:
				self.__time_elapsed += 0.01
			if self._reset_event.is_set():
				logging.progress('%s: timer reset after %s elapsed.' % (self.name,
						pyutils.format_time_delta(self.__time_elapsed)))
				with self._time_lock:
					self.__time_elapsed = 0.0
				self._reset_event.clear()
			if self._trigger_event.is_set():
				with self._time_lock:
					if self.__trigger_delay is None:
						self.__time_elapsed = self.__sleep_delay
					else:
						self.__time_elapsed = self.__sleep_delay - self.__trigger_delay
				self._trigger_event.clear()
	def trigger_event(self, delay=None):
		self.__trigger_delay = delay
		self._trigger_event.set()
	trigger = trigger_event
	def reset_timer(self):
		self._reset_event.set()
	#: :meth:`reset` is an alias to :meth:`reset_timer`
	reset = reset_timer
	def remaining_time(self):
		""" Returns the remaining time until next target execution, in seconds.
		"""
		with self._time_lock:
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
	def __init__(self, trigger_event, pname='<UNSET>', tname=None, time=None, count=None,
		delay=0.0, daemon=False):
		AbstractTimerThread.__init__(self, time=time, count=count, delay=delay,
			daemon=daemon, pname=pname, tname=tname)

		self._trigger_event = trigger_event
	def run_action_method(self):
		return self._trigger_event.set()
class TriggerWorkerThread(LicornBasicThread):
	def __init__(self, target, trigger_event, args=(), kwargs={},
												pname='<UNSET>', tname=None):
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
class LicornJobThread(AbstractTimerThread):
	def __init__(self, target, pname='<UNSET>', tname=None, time=None, count=None,
		delay=0.0, target_args=(), target_kwargs={}, daemon=False):
		""" TODO: this class is meant to be removed in version 1.3+, replaced
			by the couple
			:class:`TriggerWorkerThread` / :class:`TriggerTimerThread`.
		"""

		AbstractTimerThread.__init__(self, time=time, count=count, delay=delay,
			daemon=daemon, pname=pname, tname=tname)

		self.target        = target
		self.target_args   = target_args
		self.target_kwargs = target_kwargs

		# a parallel thread that will run the real job, to be able to continue
		# to countdown the delay while job is running.
		self.job_runner = None
	def dump_status(self, long_output=False, precision=None):
		return '%s%s [%s]' % (
				stylize(ST_RUNNING
					if self.job_runner else ST_STOPPED, self.name),
				'&' if self.daemon else '',
				'%s(%s%s%s)' % (self.target,
					self.target_args if self.target_args else '',
					', ' if (self.target_args and self.target_kwargs) else '',
					self.target_kwargs if self.target_kwargs else '')
				if self.job_runner else 'sleeping'
			)
	def run_action_method(self):
		""" A method that will wrap self.target into a JobRunner simple
			:class:`~threading.Thread`. """

		if (not self.job_runner) or (not self.job_runner.is_alive()):
			self.job_runner = Thread(
					target=self.target,
					name=self.name + '.JobRunner',
					args=self.target_args,
					kwargs=self.target_kwargs
				)
			self.job_runner.daemon = True
			self.job_runner.start()
