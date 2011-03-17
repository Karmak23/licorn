# -*- coding: utf-8 -*-
"""
Licorn Daemon threads classes.

Worth reads (among many others):

* http://code.google.com/p/python-safethread/w/list
* http://www.python.org/dev/peps/pep-0020/

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import time, __builtin__
from traceback   import print_exc
from threading   import Thread, Event, RLock, current_thread
from Queue       import Queue

from licorn.foundations           import logging, exceptions, options, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import verbose
from licorn.daemon                import priorities

class LicornThread(Thread):
	"""
		A simple thread with an Event() used to stop it properly, and a Queue() to
		get events from other threads asynchronically.

		Every subclass must implement a process_message() method, which will be called
		by the main loop until the thread stops.
	"""

	def __init__(self, tname=None):
		Thread.__init__(self)

		self.name  = (tname if tname else
				str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		# trap the original gettext translator, to avoid the builtin '_'
		# trigerring an exception everytime we need to translate a string.
		self._ = __builtin__.__dict__['_orig__']

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

	def __init__(self, tname=None, licornd=None):
		Thread.__init__(self)

		self.name = (tname if tname else
				str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self.__licornd = licornd

		# trap the original gettext translator, to avoid the builtin '_'
		# trigerring an exception everytime we need to translate a string.
		self._ = __builtin__.__dict__['_orig__']

		self._stop_event  = Event()
		assert ltrace('thread', '%s initialized.' % self.name)
	@property
	def licornd(self):
		return self.__licornd
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
class GenericQueueWorkerThread(Thread):
	"""
		.. versionadded:: 1.2.5
	"""

	def __init__(self, licornd, in_queue=None,
				peers_min=None, peers_max=None, high_bypass=True, daemon=True):
		Thread.__init__(self)

		#: the :attr:`daemon` coming from threading.Thread.
		self.daemon        = daemon
		self.__high_bypass = high_bypass

		#: a reference to the Licorn daemon, to record myself in threads list.
		self.__licornd = licornd

		if in_queue:
			# the very first instance of the class has to setup everything
			# for its future peers.
			self.__class__.base_name   = str(self.__class__).rsplit(
																'.', 1)[1][:-8]
			self.__class__.counter      = 0
			self.__class__.instances    = 0
			self.__class__.busy         = 0
			self.__class__.input_queue  = in_queue
			self.__class__.lock         = RLock()
			self.__class__.peers_min    = peers_min
			self.__class__.peers_max    = peers_max
			self.__class__.last_warning = 0

		# trap the original gettext translator, to avoid the builtin '_'
		# trigerring an exception everytime we need to translate a string.
		# the try/except block is for the testsuite, which uses this thread
		# as base class, but doesn't handle on-the-fly multilingual switch.
		try:
			self._ = __builtin__.__dict__['_orig__']
		except KeyError:
			self._ = __builtin__.__dict__['_']

		#: the threading.Thread attribute.
		self.name = '%s-%03d' % (self.__class__.base_name, self.__class__.counter)

		#assert ltrace('thread', '| %s.__init__()' % self.name)

		#: our master queue, from which we get job to do (objects to process).
		self.input_queue = self.__class__.input_queue

		#: used in dump_status (as a display info only), to know which
		#: object our target function is running onto.
		self.job = None
		self.priority = None
		self.job_args = None
		self.job_kwargs = None
		self.job_start_time = None

		#: used to sync and not crash between run() and dump_status().
		self.lock = RLock()

		# necessary to get job status without crashing in corner cases.
		self.jobbing = Event()

		with self.__class__.lock:
			#print '>> lock %s +' % self.name, self.__class__.counter, self.__class__.instances
			self.__class__.counter   += 1
			self.__class__.instances += 1
	def dump_status(self, long_output=False, precision=None):
		""" get detailled thread status. """
		with self.lock:
			return '%s%s [%s]' % (
					stylize(ST_RUNNING
						if self.is_alive() else ST_STOPPED, self.name),
					'&' if self.daemon else '',
					'on %s since %s' % (stylize(ST_ON, '%s(%s%s%s)' % (
							self.job,
							', '.join([str(j) for j in self.job_args])
								if self.job_args else '',
							', ' if self.job_args and self.job_kwargs else '',
							', '.join(['%s=%s' % (key, value) for key, value
										in self.jobs_kwargs])
								if self.job_kwargs else '')),
						pyutils.format_time_delta(
								time.time() - self.job_start_time,
								big_precision=True))
						if self.jobbing.is_set() else 'idle'
				)
	def run(self):
		#assert ltrace('thread', '> %s.run()' % self.name)

		while True:

			self.priority, self.job, self.job_args, self.jobs_kwargs = \
														self.input_queue.get()
			if self.job is None:
				# None is a fake message to unblock the q.get(), when the
				# main process terminates the current thread with stop(). We
				# emit task_done(), else the main process will block forever
				# on q.join().
				self.input_queue.task_done()
				break

			with self.__class__.lock:
				self.__class__.busy += 1

			# Do the throttle_up() out of the lock to release it, for
			# peers to notice the newcomer. The method re-acquires it anyway.
			self.throttle_up()

			with self.lock:
				if self.__high_bypass and self.priority != priorities.HIGH \
					and self.__class__.busy == self.__class__.instances:
					# make some room for HIGH priority jobs. They could still
					# be queued if everyone is busy, but this is less likely
					# now, because HIGH priority jobs are advised to be very
					# short (else they should be converted to NORMAL or LOW,
					# or splitted in smaller tasks).
					#
					# If we can spawn aa new peer, it will wait for new
					# jobs while we run, else we must not handle the
					# current job

					if self.__class__.instances < self.__class__.peers_max:

						assert ltrace('thread', '  %s: spawing new peer '
							'to always handle HIGH jobs.' % self.name)
						self.spawn_peer()

					else:
						assert ltrace('thread', '  %s: delaying job to be '
							'able to always handle HIGH jobs' % self.name)

						# mark the job as done, because we already got() it.
						self.input_queue.task_done()

						# reput it at the end of the queue, as if a new job
						# had been created.
						self.input_queue.put((self.priority, self.job,
										self.job_args, self.jobs_kwargs))

						self.job = None
						self.priority = None
						self.job_args = None
						self.job_kwargs = None
						continue

			with self.lock:
				self.jobbing.set()
				self.job_start_time = time.time()

			if 'job_delay' in self.jobs_kwargs:
				time.sleep(self.jobs_kwargs['job_delay'])
				del self.jobs_kwargs['job_delay']

			#assert ltrace('thread', '%s: running job %s' % (
			#										self.name, self.job))

			try:
				self.job(*self.job_args, **self.jobs_kwargs)

			except exceptions.LicornError, e:
				logging.warning('%s: LicornError encountered: %s' % (
															self.name, e))
				print_exc()
			except (exceptions.LicornException, Exception), e:
				logging.warning('%s: Exception encountered: %s' % (
															self.name, e))
				if options.verbose >= verbose.INFO:
					print_exc()

			self.input_queue.task_done()

			with self.lock:
				self.jobbing.clear()

			with self.__class__.lock:
				self.__class__.busy -= 1

			self.job = None
			self.priority = None
			self.job_args = None
			self.job_kwargs = None
			self.job_start_time = None

			self.throttle_down()

			if self.input_queue.qsize() == 0:
				logging.progress('%s: queue is now empty, going '
					'asleep waiting for jobs.' % self.name)

		with self.__class__.lock:
			self.__class__.instances -= 1
			#print '>> lock -', self.__class__.instances

		#assert ltrace('thread', '< %s.run()' % self.name)
	def throttle_up(self):
		""" See if there are too many or missing peers to handle queued jobs,
			and spawn a friend if needed, or terminate myself if no more useful.
		"""

		# we need to get the class lock, else peers could stop() while we are
		# stopping too, and the daemon could be left without any thread for a
		# given class of them.

		with self.__class__.lock:
			# FIRST, see if peers are in need of help: if there are
			# still a lot of job to do, spawn another peer to get the
			# job done, until the configured thread limit is reached.

			if (self.input_queue.qsize() > self.__class__.instances
					and self.__class__.instances == self.__class__.busy) \
					or self.__class__.instances < self.__class__.peers_min:

				if self.__class__.instances < self.__class__.peers_max:

					assert ltrace('thread', '  %s: spawing a new peer because '
						'%d instances < %d peers_min or (%d jobs > %d instances '
						'and all instances busy); '
						'(BTW %d instances < %d peers_max).' % (self.name,
							self.__class__.instances, self.__class__.peers_min,
							self.input_queue.qsize(), self.__class__.instances,
							self.__class__.instances, self.__class__.peers_max))

					self.spawn_peer()
				else:
					# alert the user that we can't spawn a new thread because
					# upper limit it already reached, but not too much (one alert
					# per second seems not too much).
					if time.time() - self.__class__.last_warning > 1.0:
						self.__class__.last_warning = time.time()
						logging.progress('%s: maximum peers already running, '
							'queue size is %s.' % (self.name,
								self.input_queue.qsize()))
			else:
				assert ltrace('thread', '  %s: NOT spawing a new peer because '
					'NOT %d instances < %d peers_min or (%d jobs > %d instances '
					'and all instances busy); '
					'(BTW %d instances < %d peers_max).' % (self.name,
						self.__class__.instances, self.__class__.peers_min,
						self.input_queue.qsize(), self.__class__.instances,
						self.__class__.instances, self.__class__.peers_max))
	def throttle_down(self):
		""" See if there are too many peers to handle queued jobs, and then
			send terminate signal (put a ``None`` job in the queue), so that
			one of the peers will terminate.
		"""

		# we need to get the class lock, else peers could stop() while we are
		# stopping too, and the daemon could be left without any thread for a
		# given class of them.

		with self.__class__.lock:
			# See if jobs have been worked out during the time
			# we spent joing our job. If things have settled, signify to
			# one of the peers to terminate (this could be me, or not),
			# but only if there are still more peers than the configured
			# lower limit.

			if (self.input_queue.qsize() <= self.__class__.instances
					and self.__class__.instances > self.__class__.busy):

				if self.__class__.instances > self.__class__.peers_min:

					assert ltrace('thread', '  %s: terminating because running out '
						'of jobs (%d jobs <= %d instances '
						'and %d instances > %d peers_min).' % (
						self.name,
						self.input_queue.qsize(), self.__class__.instances,
						self.__class__.instances, self.__class__.peers_min))

					self.stop()
	def spawn_peer(self):
		self.__licornd.append_thread(
				self.__class__(licornd=self.__licornd, daemon=self.daemon))
	def stop(self):
		#assert ltrace('thread', '| %s.stop()' % self.name)
		self.input_queue.put_nowait((-1, None, None, None))

		# if we are in the process of settling down, tell the
		# master thread cleaner to search for terminated threads to wipe,
		# but not everytime.
		if self.__class__.instances % 10 == 0 or self.__class__.instances <= 2:
			try:
				self.__licornd.clean_objects(0.1)
			except AttributeError:
				# if daemon is stopping, cleaner could be already wiped out.
				pass
class ServiceWorkerThread(GenericQueueWorkerThread):
	pass
class ACLCkeckerThread(GenericQueueWorkerThread):
	pass
class NetworkWorkerThread(GenericQueueWorkerThread):
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
	def __init__(self, tname=None, time=None, count=None,
		delay=0.0, daemon=False):

		LicornBasicThread.__init__(self, tname=tname)

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

		while self.__time_elapsed < self.__sleep_delay:
			#print "waiting %.1f < %.1f" % (current_delay, self.delay)

			if self._stop_event.is_set():
				break

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

			time.sleep(0.01)
			with self._time_lock:
				self.__time_elapsed += 0.01
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

		while self.loop or self.current_loop < self.count:

			if self._stop_event.is_set():
				break

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
	def __init__(self, trigger_event, tname=None, time=None, count=None,
		delay=0.0, daemon=False):
		AbstractTimerThread.__init__(self, time=time, count=count, delay=delay,
			daemon=daemon, tname=tname)

		self._trigger_event = trigger_event
	def run_action_method(self):
		return self._trigger_event.set()
class TriggerWorkerThread(LicornBasicThread):
	def __init__(self, target, trigger_event, args=(), kwargs={}, tname=None):
		assert ltrace('thread', '| TriggerWorkerThread.__init__()')
		LicornBasicThread.__init__(self, tname)
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
	def __init__(self, target, tname=None, time=None, count=None,
		delay=0.0, target_args=(), target_kwargs={}, daemon=False):
		""" TODO: this class is meant to be removed in version 1.3+, replaced
			by the couple
			:class:`TriggerWorkerThread` / :class:`TriggerTimerThread`.
		"""

		AbstractTimerThread.__init__(self, time=time, count=count, delay=delay,
			daemon=daemon, tname=tname)

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
				if self.job_runner else 'sleeping, wake up in %s'
					% pyutils.format_time_delta(self.remaining_time())
			)
	def run_action_method(self):
		""" A method that will wrap self.target into a JobRunner simple
			:class:`~threading.Thread`. """

		'''
		if (not self.job_runner) or (not self.job_runner.is_alive()):
			self.job_runner = Thread(
					target=self.target,
					name=self.name + '.JobRunner',
					args=self.target_args,
					kwargs=self.target_kwargs
				)
			self.job_runner.daemon = True
			self.job_runner.start()
		'''
		self.target(*self.target_args, **self.target_kwargs)
