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
from threading   import Thread, current_thread
from Queue       import Queue

from licorn.foundations           import logging, exceptions, options
from licorn.foundations           import process, pyutils
from licorn.foundations.threads   import RLock, Event
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.constants import verbose, priorities

class BaseLicornThread(Thread):
	""" A simple class of thread which records its own instances, and whose
		start() method returns the current instance. This allows to instanciate
		and start the thread in one line.
	"""
	def __init__(self, *a, **kw):

		try:
			# using self.__class__ will fill subclasses._instances,
			# instead of BaseLicornThread._instances.
			self.__class__._instances.append(self)

		except AttributeError:
			self.__class__._instances = [ self ]

		Thread.__init__(self, *a, **kw)
	def start(self):
		""" Just a handy method that allows us to do::

			>>> th = BaseLicornThread(...).start()
		"""
		Thread.start(self)
		return self
	def stop(self):
		try:
			self.__class__._instances.remove(self)

		except ValueError:
			pass
class LicornThread(Thread):
	"""
		A simple thread with an Event() used to stop it properly, and a Queue() to
		get events from other threads asynchronically.

		Every subclass must implement a process_message() method, which will be called
		by the main loop until the thread stops.
	"""

	def __init__(self, tname=None):
		Thread.__init__(self)

		self.name  = tname or self.__class__.__name__

		# trap the original gettext translator, to avoid the builtin '_'
		# trigerring an exception everytime we need to translate a string.
		try:
			self._ = __builtin__.__dict__['_orig__']

		except KeyError:
			# In case our threaded gettext is not set up. Eg in WMI, we
			# don't set it up: Django does it, but much later that when
			# we initialize. Thus, we take the original gettext as fallback.
			self._ = __builtin__.__dict__['_']

		self._stop_event  = Event()
		self._input_queue = Queue()
		assert ltrace(TRACE_THREAD, '%s initialized' % self.name)
	def start(self):
		""" Just a handy method that allows us to do::

			>>> th = LicornThread(...).start()
		"""
		Thread.start(self)
		return self
	def dispatch_message(self, msg):
		""" get an incoming message in a generic way. """
		self._input_queue.put(msg)
	def run(self):
		""" Process incoming messages until stop Event() is set. """
		# don't call Thread.run(self), just override it.
		assert ltrace(TRACE_THREAD, '%s running' % self.name)

		while not self._stop_event.isSet():
			data = self._input_queue.get()
			if data is None:
				break
			self.process_data(data)
			self._input_queue.task_done()

		assert ltrace(TRACE_THREAD, '%s ended' % self.name)
	def stop(self):
		""" Stop current Thread
		and put a special None entry in the queue, to be
		sure that self.run() method exits properly. """
		assert ltrace(TRACE_THREAD, '%s stopping' % self.name)
		self._stop_event.set()
		self._input_queue.put(None)
class LicornBasicThread(BaseLicornThread):
	""" A simple Thread with an Event(), used to stop it properly. Threaded
		gettext is setup in the :meth:`__init__` method.

		You must implement a method named `run_action_method` which does
		**one** processing at a time. This method will be automatically run
		in a `while` loop. It will be Exception-immune: any encountered
		exception is printed with a full stack trace, and next run goes on.

		..warning:: Don't put any infinite loop in your `run_action_method`,
			else the thread will never stop().

		Optional:

		- if a method named `pre_run_method` exists, it is run before entering
			the main while loop.
		- if a method named `post_run_method` exists, it is run after exiting
			the main while loop.
		- you should  probably overload :method:`dump_status()` to provide
			more informations about the current thread.


		.. versionadded:: a long while ago, I can't even remember when. Before
			version 1.2, this is sure.
	"""
	@property
	def pretty_name(self):
		return stylize(ST_NAME, self.name)
	def __init__(self, *args, **kwargs):

		# Pop our args to not bother upper classes.
		tname   = kwargs.pop('tname', None)
		licornd = kwargs.pop('licornd', None)

		BaseLicornThread.__init__(self, *args, **kwargs)

		self.name = tname or self.__class__.__name__

		self.__licornd = licornd

		# trap the original gettext translator, to avoid the builtin '_'
		# trigerring an exception everytime we need to translate a string.
		try:
			self._ = __builtin__.__dict__['_orig__']

		except KeyError:
			# In case our threaded gettext is not set up. Eg in WMI, we
			# don't set it up: Django does it, but much later that when
			# we initialize. Thus, we take the original gettext as fallback.
			self._ = __builtin__.__dict__['_']

		self._stop_event  = Event()

		assert ltrace(TRACE_THREAD, '%s initialized.' % self.name)
	@property
	def licornd(self):
		return self.__licornd
	def dump_status(self, long_output=False, precision=None, as_string=False):
		if as_string:
			return '%s%s (stop=%s)' % (
				stylize(ST_RUNNING
					if self.is_alive() else ST_STOPPED, self.name),
				'&' if self.daemon else '',
				self._stop_event.is_set()
			)
		else:
			# TODO: more details
			return process.thread_basic_info(self)
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
		assert ltrace(TRACE_THREAD, '%s running' % self.name)

		assert hasattr(self, 'run_action_method')

		if hasattr(self, 'pre_run_method'):
			try:
				getattr(self, 'pre_run_method')()

			except:
				logging.exception(_(u'{0}: Exception in self.pre_run_method(), aborting.'),
									(ST_NAME, self.name))
				self.finish()
				return

		while not self._stop_event.is_set():
			try:
				self.run_action_method()

			except:
				logging.exception(_(u'{0}: Exception in self.run_action_method(), '
						u'continuing.'), (ST_NAME, self.name))

		if hasattr(self, 'post_run_method'):
			try:
				getattr(self, 'post_run_method')()

			except:
				logging.exception(_(u'{0}: Exception in self.post_run_method()'),
									(ST_NAME, self.name))

		self.finish()
	def finish(self):
		assert ltrace(TRACE_THREAD, '%s ended' % self.name)
	def stop(self):
		""" Stop current Thread. """
		assert ltrace(TRACE_THREAD, '%s stopping' % self.name)
		self._stop_event.set()
		BaseLicornThread.stop(self)
class GQWSchedulerThread(BaseLicornThread):
	""" Try to dynamically adapt the number of workers for a given qsize.

		.. warning:: this scheduler is very basic, and in loaded conditions,
			the priorities will not be respected: if all workers are currently
			handling jobs, any incoming one (even with a higher priority) will
			have to wait before beiing processed.
			This can eventually be avoided by the use of greenlets everywhere
			in licorn code, but this will need a deeper level of code rewrite.
	"""
	def __init__(self, klass, *a, **kw):
		BaseLicornThread.__init__(self, *a, **kw)

		self.scheduled_class = klass
		self._stop_event     = Event()
		self.sleep_lock      = RLock()

		self.name   = '%s(%s)' % (self.__class__.__name__, klass.__name__)

		# trap the original gettext translator, to avoid the builtin '_'
		# trigerring an exception everytime we need to translate a string.
		# the try/except block is for the testsuite, which uses this thread
		# as base class, but doesn't handle on-the-fly multilingual switch.
		try:
			self._ = __builtin__.__dict__['_orig__']

		except KeyError:
			self._ = __builtin__.__dict__['_']
	def dump_status(self, long_output=False, precision=None, as_string=False):

		if as_string:
			return _('{0}{1} for {2} [{3} workers; wake up in {4}]\n{5}').format(
				stylize(ST_RUNNING if self.is_alive() else ST_STOPPED,
						self.__class__.__name__),
				'&' if self.daemon else '',
				self.scheduled_class.__name__,
				# `.instances` is the number of instances
				self.scheduled_class.instances,
				pyutils.format_time_delta(self.sleep_start_time + self.sleep_time - time.time()),
				'\n'.join(('\t%s' % t.dump_status(long_output, precision, as_string))
									# `._instances` is the list of threads.
									for t in self.scheduled_class._instances)
			)

		else:
			return dict(workers=[ t.dump_status(long_output, precision, as_string)
									for t in self.scheduled_class._instances ],
						wake_up=self.sleep_start_time + self.sleep_time,
					**process.thread_basic_info(self))
	def run(self):
		assert ltrace_func(TRACE_THREAD)

		def throttle_up():
			""" See if there are too many or missing peers to handle queued jobs,
				and spawn a friend if needed, or terminate myself if no more useful.
			"""
			# we acquire the class lock to "freeze" starts/ends while we count
			# everyone and throttle workers. This can make all workers wait, but
			# doesn't happen that frequently.
			with cls.lock:
				# FIRST, see if peers are in need of help: if there are
				# still a lot of job to do, spawn another peer to get the
				# job done, until the configured thread limit is reached.

				n_instances = cls.instances

				if qsize > 0 and n_instances == cls.busy:
					if n_instances < cls.peers_max:
						# sleep a lot, because we start a lot of workers,
						# but no more that 10 seconds.
						return min(10.0, float(self.spawn_worker(min(qsize,
											cls.peers_max - n_instances))))

					else:
						if time.time() - cls.last_warning > 5.0:
							cls.last_warning = time.time()
							logging.progress(_(u'{0}: maximum workers already '
								u' running, but qsize={1}.').format(
									self.name, qsize))

						# all workers are currently busy, we can wait a lot
						# before things settle. Keep CPU cycles for our workers.
						return 10.0
				else:
					# things have not changed. Wait a little, but not that
					# much in case things go up again fast.
					return 2.0
		def throttle_down():
			""" See if there are too many peers to handle queued jobs, and then
				send terminate signal (put a ``None`` job in the queue), so that
				one of the peers will terminate.
			"""

			# we need to get the class lock, else peers could stop() while we are
			# stopping too, and the daemon could be left without any thread for a
			# given class of them.

			with cls.lock:
				# See if jobs have been worked out during the time
				# we spent joing our job. If things have settled, signify to
				# one of the peers to terminate (this could be me, or not),
				# but only if there are still more peers than the configured
				# lower limit.

				n_instances = cls.instances

				if qsize <= n_instances and n_instances > cls.busy:
					# sleep a lot if we terminate a lot of workers, but
					# no more than 10 seconds to avoid beiing flooded
					# by next "queue attack".
					return min(10.0, float(self.stop_worker(
									n_instances - qsize - cls.peers_min)))

				# things have not changed. Wait a little, but not that
				# much in case things go up again fast.
				return 2.0

		cls        = self.scheduled_class
		q          = cls.input_queue
		prev_qsize = 0

		from licorn.core import LMC

		while not self._stop_event.is_set():

			with cls.lock:
				qsize = q.qsize()

			with self.sleep_lock:
				if qsize >= prev_qsize:
					self.sleep_time = throttle_up()

				else:
					self.sleep_time = throttle_down()

			# from time to time, or if we are in the process of settling down,
			# ask the thread-cleaner to search for dead-threads to wipe from memory.
			try:
				if len(cls._instances) != cls.instances:
					try:
						LMC.licornd.clean_objects(delay=1.0)

					except AttributeError:
						# if daemon is currently stopping, the thread-cleaner
						# could be already wiped out. Harmless.
						pass

			except AttributeError:
				# the first time, cls._instances is not yet set. harmless.
				pass

			prev_qsize = qsize
			self.sleep_start_time = time.time()

			with self.sleep_lock:
				# don't hold the lock while we sleep, this would cause
				# dump_status() to hang.
				sleep_time = self.sleep_time

			time.sleep(sleep_time)
		assert ltrace_func(TRACE_THREAD, True)
	def stop(self):
		assert ltrace_func(TRACE_THREAD)

		# Stop blocked workers
		self.stop_worker(self.scheduled_class.instances)

		# Stop sleeping workers
		for inst in self.scheduled_class._instances:
			inst.stop()

		self._stop_event.set()

		assert ltrace_func(TRACE_THREAD, True)
	def spawn_worker(self, number=None):
		for i in range(number or 1):
			self.scheduled_class().start()
		return number or 1.0
	def stop_worker(self, number=None):
		for i in range(number or 1):
			self.scheduled_class.input_queue.put_nowait(
											self.scheduled_class.stop_packet)
		return number or 1.0
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
	def __init__(self, *args, **kwargs):

		# Pop our args to not bother upper classes.
		time   = kwargs.pop('time', None)
		count  = kwargs.pop('count', None)
		delay  = kwargs.pop('delay', None)
		daemon = kwargs.pop('daemon', False)

		LicornBasicThread.__init__(self, *args, **kwargs)

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

		assert ltrace(TRACE_THREAD, '| AbstractTimerThread.__init__(time=%s, '
			'count=%s, delay=%s, loop=%s)' % (self.time,
										self.count, self.delay, self.loop))

		if (self.loop or self.count > 1) and self.delay is None:
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

		assert ltrace(TRACE_THREAD, '| %s.sleep(%s)' % (self.name, delay))

		with self._time_lock:
			self.__time_elapsed = 0.0

		while self.__time_elapsed < self.__sleep_delay:
			#print "waiting %.1f < %.1f" % (current_delay, self.delay)

			if self._stop_event.is_set():
				break

			if self._reset_event.is_set():
				logging.progress(_(u'{0}: timer reset after {1} elapsed.').format(
						stylize(ST_NAME, self.name),
						pyutils.format_time_delta(self.__time_elapsed,
													big_precision=True)))

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

		assert ltrace(TRACE_THREAD, '| %s.sleep(EXIT)' % self.name)
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
class GenericQueueWorkerThread(AbstractTimerThread):
	""" Inherits from :class:`AbstractTimerThread` to be able to be interrupted
		in the middle of a :meth:`sleep` triggered by a ``job_delay``. The
		:meth:`run` method of the :class:`AbstractTimerThread` is totally
		overriden though, and is never called, this is intended. We just need
		the :meth:`sleep` one. The :meth:`stop` method comes from
		:class:`LicornBasicThread`.

		.. versionadded::
			- created for the 1.2.5
			- enhanced for the 1.5: add the ability to stop the thread in the
			  middle of a sleep, not only when the thread is idle.
	"""

	_setup_done  = False
	lock         = RLock()
	counter      = 0
	instances    = 0
	busy         = 0
	last_warning = 0

	#: what we need to put in the queue for a worker to stop.
	stop_packet  = (-1, None, None, None)
	scheduler    = None

	@classmethod
	def setup(cls, licornd, input_queue, peers_min, peers_max, daemon=False):
		""" Setup The Worker class. Starts the Scheduler thread, and return it.

			You have to store the scheduler reference somewhere!

			To stop the workers, invoke the scheduler `stop()` method.
		"""

		if cls._setup_done:
			return

		cls._instance = []

		#cls.high_bypass = high_bypass
		cls.peers_min   = peers_min
		cls.peers_max   = peers_max

		#: a reference to the licorn daemon
		cls.licornd = licornd

		#: should the worker instances be daemon threads?
		cls.daemon = daemon

		# the very first instance of the class has to setup everything
		# for its future peers.
		cls.input_queue  = input_queue

		# start the class scheduler, which will manage worker threads
		cls.scheduler = GQWSchedulerThread(cls).start()

		cls._setup_done = True

		# start the first worker, which needs `_setup_done` to be True.
		cls().start()

		return cls.scheduler
	def __init__(self, *a, **kw):

		cls = self.__class__

		if not cls._setup_done:
			raise RuntimeError(_(u'Class method {0}.setup() has not been '
									u'called!').format(cls.__name__))

		kw.update({
			#: the :class:`threading.Thread` attributes.
			'tname'   : '%s-%03d' % (cls.__name__, cls.counter),
			'daemon'  : cls.daemon,
			'licornd' : cls.licornd,

			# FAKE: we pass 1 for the AbstractTimerThread.__init__() not to
			# bother us with 'must provide a delay for looping' check error.
			# Anyway, as we override completely its run() method, this has
			# no importance at all for the runtime, *we* loop like we want.
			'count'   : 1,
		})

		AbstractTimerThread.__init__(self, *a, **kw)

		# trap the original gettext translator, to avoid the builtin '_'
		# trigerring an exception everytime we need to translate a string.
		# the try/except block is for the testsuite, which uses this thread
		# as base class, but doesn't handle on-the-fly multilingual switch.
		try:
			self._ = __builtin__.__dict__['_orig__']

		except KeyError:
			self._ = __builtin__.__dict__['_']

		#: used in dump_status (as a display info only), to know which
		#: object our target function is running onto.
		self.job            = None
		self.priority       = None
		self.job_args       = None
		self.job_kwargs     = None
		self.job_start_time = None

		#: used to sync and not crash between run() and dump_status().
		self.lock    = RLock()
		self.jobbing = Event()

		#assert ltrace_locks(cls.lock)

		with cls.lock:
			cls.counter   += 1
			cls.instances += 1
	def dump_status(self, long_output=False, precision=None, as_string=True):
		""" get detailled thread status. """
		with self.lock:
			if as_string:
				return '%s%s [%s]' % (
					stylize(ST_RUNNING
						if self.is_alive() else ST_STOPPED, self.name),
					'&' if self.daemon else '',
					'on %s since %s' % (self.__format_job(),
						pyutils.format_time_delta(
								time.time() - self.job_start_time,
								big_precision=True))
						if self.jobbing.is_set() else 'idle'
				)
			else:
				return dict(job=self.job,
							job_args=self.job_args,
							job_kwargs=self.job_kwargs,
							start_time=self.job_start_time,
							jobbing=self.jobbing.is_set(),
							**process.thread_basic_info(self))
	def __format_job(self):
		return stylize(ST_ON, '%s(%s%s%s)' % (
							self.job.__name__,
							', '.join([str(j) for j in self.job_args])
								if self.job_args else '',
							', ' if self.job_args and self.job_kwargs else '',
							', '.join(['%s=%s' % (key, value) for key, value
										in self.jobs_kwargs])
								if self.job_kwargs else ''))
	def run(self):
		""" A queue worker can be interrupted in two ways:

			- calling its :meth:`stop` method
			- putting ``(None, …)`` in its queue.
		"""

		assert ltrace_func(TRACE_THREAD)

		cls = self.__class__
		q   = cls.input_queue

		while not self._stop_event.is_set():

			# We need to store the item in a separate variable in case it is
			# badly formed (see #898). Without this, we won't be able to
			# display it in the message in case of an exception.
			temp_data = q.get()

			try:
				self.priority, self.job, self.job_args, self.jobs_kwargs = temp_data

			except ValueError:
				logging.warning(_(u'{0}: invalid queue item "{1}", '
								u'terminating.').format(self.name, temp_data))

				# Even with a bad-built item, we successfully poped it from the
				# queue. Notify any waiters before quitting.
				q.task_done()
				break

			else:
				del temp_data

			if self.job is None:
				# None is a fake message to unblock the q.get(), when the
				# main process terminates the current thread with stop(). We
				# emit task_done(), else the main process will block forever
				# on q.join().
				q.task_done()

				# Don't set self._stop_event(), just break: when we encounter
				# the 'stop job' item, the QueueWorkerScheduler is in the
				# process of calling our stop() method too. Setting the event
				# from here is thus not necessary; the loop will already break.
				break

			with cls.lock:
				cls.busy += 1

			with self.lock:
				self.jobbing.set()
				self.job_start_time = time.time()

			# this will at most eventually sleep a little if called requested
			# if, or at best (with 0.0s) switch to another thread needing the
			# CPU in the Python interpreter before starting to process the job.
			self.sleep(self.jobs_kwargs.pop('job_delay', 0.0))

			# In case the sleep() was interrupted by a stop(), we need to
			# check, to avoid running the job in a stopping daemon.
			if self._stop_event.is_set():

				with cls.lock:
					cls.busy -= 1

				with self.lock:
					self.jobbing.clear()

				q.task_done()

				logging.warning(_(u'{0}: stopped during sleep, job {1} will '
					u'not be run at all.').format(self.name, self.__format_job()))
				break

			#assert ltrace(TRACE_THREAD, '%s: running job %s' % (
			#										self.name, self.job))

			try:
				self.job(*self.job_args, **self.jobs_kwargs)

			except Exception:
				logging.exception(_(u'{0}: Exception encountered while running '
									u'{1}'), self.name, self.__format_job())

			q.task_done()

			with self.lock:
				self.jobbing.clear()

			with cls.lock:
				cls.busy -= 1

			self.job            = None
			self.priority       = None
			self.job_args       = None
			self.job_kwargs     = None
			self.job_start_time = None

			if q.qsize() == 0:
				logging.progress(_(u'%s: queue is now empty, going '
								u'asleep waiting for jobs.') % self.name)

		# when ending, be sure to notice everyone interested.
		with cls.lock:
			cls.instances -= 1
class ServiceWorkerThread(GenericQueueWorkerThread):
	pass
class ACLCkeckerThread(GenericQueueWorkerThread):
	pass
class NetworkWorkerThread(GenericQueueWorkerThread):
	pass
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
	def __init__(self, *a, **kw):
		assert ltrace(TRACE_THREAD, '| TriggerWorkerThread.__init__()')

		try:
			target = a.pop()

		except:
			try:
				target = kw.pop('target')

			except:
				raise exceptions.BadArgumentError(_(u'{0}: the "target" first '
								u'(or named) argument is mandatory!').format(
									self.__class__.__name__))
		try:
			trigger_event = a.pop()

		except:
			try:
				trigger_event = kw.pop('trigger_event')

			except:
				raise exceptions.BadArgumentError(_(u'{0}: the "trigger_event" '
						u'second (or named) argument is mandatory!').format(
							self.__class__.__name__))

		try:
			args = a.pop()

		except:
			args = kw.pop('args', ())

		try:
			kwargs = a.pop()

		except:
			kwargs = kw.pop('kwargs', {})

		LicornBasicThread.__init__(self, *a, **kw)

		self._disable_event     = Event()
		self._currently_running = Event()
		self._trigger_event     = trigger_event

		self.target = target
		self.args   = args
		self.kwargs = kwargs

		# used on manual triggering only.
		self.one_time_args   = None
		self.one_time_kwargs = None
	def dump_status(self, long_output=False, precision=None, as_string=False):
		if as_string:
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
		else:
			return process.thread_basic_info(self)
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
		assert ltrace(TRACE_THREAD, '%s running' % self.name)

		while True:
			self._trigger_event.wait()

			# be sure to wait at next loop.
			self._trigger_event.clear()

			if self._stop_event.is_set():
				assert ltrace(TRACE_THREAD, '%s: breaking our loop now.' % self.name)
				break

			if self._disable_event.is_set():
				assert ltrace(TRACE_THREAD, '%s: triggered, but currently '
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

			assert ltrace(TRACE_THREAD, '%s: triggered, running target %s(%s, %s)'
				% (self.name, self.target, ', '.join(args), ', '.join(kwargs)))

			self._currently_running.set()
			self.target(*args, **kwargs)
			self._currently_running.clear()

		self.finish()
	def trigger(self, *args, **kwargs):
		""" Trigger a worker run if we are not currently stopping. """
		assert ltrace(TRACE_THREAD, '| TriggerWorkerThread.trigger()')
		self.one_time_args = args
		self.one_time_kwargs = kwargs
		if not self._stop_event.is_set():
			return self._trigger_event.set()
	#: An alias from :meth:`manual_trigger` to :meth:`trigger` for purists.
	manual_trigger = trigger
	def disable(self):
		""" Disable next runs (until re-enabled), but only if we are not
			currently stopping. """
		assert ltrace(TRACE_THREAD, '| TriggerWorkerThread.disable()')
		if not self._stop_event.is_set():
			return self._disable_event.set()
	def enable(self):
		assert ltrace(TRACE_THREAD, '| TriggerWorkerThread.enable()')
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
	def dump_status(self, long_output=False, precision=None, as_string=False):
		""" get detailled thread status. """
		if as_string:
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
		else:
			# TODO: more details
			return process.thread_basic_info(self)
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
