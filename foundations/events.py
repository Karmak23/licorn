# -*- coding: utf-8 -*-
"""
Licorn® foundations - events

:copyright:
	* 2010-2012 Olivier Cortès <olive@deep-ocean.net>
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
:license: GNU GPL version 2
"""

from threading import current_thread, Timer

from Queue     import PriorityQueue

# other foundations imports
import logging, exceptions, pyutils, styles
from threads   import RLock
from styles    import *
from ltrace    import *
from ltraces   import *
from base      import Singleton, NamedObject, method_decorator
from constants import priorities
from workers   import workers

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

# FIXME: this should go elsewhere someday.
from licorn.daemon.threads import LicornBasicThread

events_queue      = PriorityQueue()
events_handlers   = {}
events_callbacks  = {}
events_collectors = []
looper_thread     = None
loop_lock         = RLock()

class RoundRobinEventLooper(LicornBasicThread):
	""" Process internal events and run callbacks associated to them,
		synchronously or not. See :meth:`run_action_method` for
		implementation details.

		Generally speaking, N events can be processed parallel, until
		all service threads are busy. Every service thread is assigned
		one event to process.

		For a given Event beiing processed by a service thread,
		callbacks and handlers are run in turn, not in parallel.

		Thus, only the events are considered parallel.

		.. warning:: an event with the ``synchronous`` attribute set will
			completely block other incoming events processing. This is normal
			and meant to be. Please use ``synchronous`` events only if
			appropriate.

		.. versionadded:: 1.3
	"""

	def push_event_to_collectors_thread(self, event):
		""" Meant to be used in a ServiceThread, because it can take a long time. """

		assert ltrace_func(TRACE_EVENTS)

		for collector in events_collectors[:]:
			try:
				logging.monitor(TRACE_EVENTS, TRACELEVEL_2, _('Event push to collector: {0} > {1}'), event.name, collector)
				collector.process_event(event)

			except:
				# The collector probably disconnected without warning us first.
				# Even without that, it produced an error; drop it.
				logging.exception(_('Exception while when pushing event {0} to collector {1}.'), event, collector)
				unregister_collector(collector)
	def run_action_method(self):
		""" Try to get the next event from our event-queue (else block on it).

			If `event` is `None`, return.

			If we have event-collectors connected — like the WMI or a
			`get events` CLI tool, ask a :class:`~licorn.daemon.threads.ServiceWorkerThread`
			to forward the event to all of them.

			If the event must be run synchronously, do it. This will kind of
			briefly halt the event-loop, but this is meant to be with a
			synchronous event, isn't it?

			If the event is not synchronous, put all its callbacks into the
			service queue, with the same priority. One or more :class:`~licorn.daemon.threads.ServiceWorkerThread`
			will take care of running the registered callback methods.

			The current method will be run ad-vitam-eternam (until stopped) by the
			:meth:`licorn.daemon.threads.LicornBasicThread.run` method, in its while loop. """

		priority, event = events_queue.get()

		if event is None:
			return

		if events_collectors != []:
			workers.service_enqueue(priorities.HIGH,
								self.push_event_to_collectors_thread, event)

		if event.synchronous:
			# stop the current processing by running the event methods here and now.
			self.run_event(event)

		else:
			# process the event asynchronously in a service thread.
			workers.service_enqueue(priority, self.run_event, event)
	def run_methods(self, event, method_type_container, method_type):
		try:
			methods = method_type_container[event.name]

		except KeyError, e:
			assert ltrace(TRACE_EVENTS, _(u'{0}: no {1} for event {2}.').format(
								stylize(ST_NAME, self.name), method_type,
								stylize(ST_NAME, event.name)))
			method_type_container[event.name] = []
			return

		for method in methods:
			try:
				method(event, *event.args, **event.kwargs)

			except SystemExit:
				pass

			except:
				logging.exception(_(u'{0}: exception encountered while '
					u'running {1} {2} for event {3}, skipping to next method.'),
						(ST_NAME, self.name), method_type,
						(ST_NAME, method), (ST_NAME, event.name))
	def run_event(self, event):
		""" Will "run" or execute an event:

				* all handlers associated with a given ``event`` are executed in turn
					and are passed the event `args` and `kwargs`. Any encountered
					exception is dumped, but the processing continues.
				* the event callback is run when all handlers have been executed,
					with the event `args` and `kwargs`.

			.. note:: Caveheat: as of version 1.3, the event handlers are not run in paralled.

			.. versionadded:: 1.3
		"""

		assert ltrace_func(TRACE_EVENTS)

		logging.monitor(TRACE_EVENTS, TRACELEVEL_1, _('Processing event {0}'), (ST_NAME, event.name))

		self.run_methods(event, events_handlers, _('event handler'))
		self.run_methods(event, events_callbacks, _('event callback'))
class LicornEvent(NamedObject):
	""" Licorn® event object class.

		:param synchronous: a boolean indicating that the event should be run
			synchronously (defaults to `False`). Use with caution, running an
			event synchronously halts the event-loop during execution.

		:param callbacks: an optional iterable of python function or method
			which will be called after the event handlers have been processed.

		:param *args: any nameless argument will be stored in the event, to be
			forwarded to the callbacks: the one registered for the event, and
			the eventual one that will be called when the event is processed.

		:param **kwargs: same principle, with named arguments.

		.. note:: You should explicitely prefer named-kwargs over nameless-args.
			Licorn® extensions callbacks will rely on named-kwarguments.

		.versionadded:: 1.3
			During the 1.2 - 1.3 development cycle, the daemon's EventManager
			has been converted to a more generic and more feature full
			`licorn.foundations.events` module.
	"""
	def __init__(self, _event_name, *args, **kwargs):

		self.synchronous = kwargs.pop('synchronous', False)
		self.callbacks   = kwargs.pop('callbacks', None)

		super(LicornEvent, self).__init__(name=_event_name)

		self.args        = args
		self.kwargs      = kwargs

	def emit(self, priority=None, delay=None):

		if delay:
			t = Timer(delay, events_queue.put, args=((priority or priorities.NORMAL, self), ))
			t.start()

		else:
			events_queue.put((priority or priorities.NORMAL, self))
LicornEventType = type(LicornEvent('dummy_event'))

def callback_function(func):
	""" Event callback decorator. The decorated function will
		be called when all events handlers have been processed for a
		given event.

		Each callback will be passed the ``event`` as first argument,
		with `*event.args` and `**event.kwargs` too.

		.. warning:: don't use this decorator on a class/instance method.
	"""

	# make it easy to collect / uncollect callbacks afterwards.
	func.is_callback = True

	register_callback(func.__name__, func)

	return func
def handler_function(func):
	""" Event handler decorator. The decorated function will
		be run when a given event is emitted.

		All handlers are run in turn, in the order of registration,
		when an event is emitted.

		The decorated function/method name must be exactly the event
		name, to be registered correctly.

		Each handler will be passed the ``event`` as first argument,
		with `*event.args` and `**event.kwargs` too.

		.. warning:: don't use this decorator on a class/instance method.
	"""

	# make it easy to collect / uncollect handlers afterwards.
	func.is_handler = True

	register_handler(func.__name__, func)

	return func
def callback_method(meth):
	""" Event callback decorator. The decorated method will
		be called when all events handlers have been processed for a
		given event.

		Each callback will be passed the ``event`` as first argument,
		with `*event.args` and `**event.kwargs` too.

		.. warning:: don't use this decorator on a function.
	"""

	# make it easy to collect / uncollect callbacks afterwards.
	new_meth = method_decorator(meth, is_callback=True)

	# This won't work, because we would try to scan the descriptor object,
	# not the bound method it will return when the instance method is accessed.
	# The instance MUST call events.collect(self) at the end of its __init__().
	#
	#register_callback(meth.__name__, new_meth)

	return new_meth
def handler_method(meth):
	""" Event handler decorator. The decorated method will
		be run when a given event is emitted.

		All handlers are run in turn, in the order of registration,
		when an event is emitted.

		The decorated function/method name must be exactly the event
		name, to be registered correctly.

		Each handler will be passed the ``event`` as first argument,
		with `*event.args` and `**event.kwargs` too.

		.. warning:: don't use this decorator on a function.
	"""

	# make it easy to collect / uncollect handlers afterwards.
	new_meth = method_decorator(meth, is_handler=True)

	# This won't work, because we would try to scan the descriptor object,
	# not the bound method it will return when the instance method is accessed.
	# The instance MUST call events.collect(self) at the end of its __init__().
	#
	#register_handler(meth.__name__, new_meth)

	return new_meth
def register_callback(event_name, method):
	return register_(events_callbacks, _('event callback'), event_name, method)
def unregister_callback(event_name, method):
	return unregister_(events_callbacks, _('event callback'), event_name, method)
def register_handler(event_name, method):
	return register_(events_handlers, _('event handler'), event_name, method)
def unregister_handler(event_name, method):
	return unregister_(events_handlers, _('event handler'), event_name, method)
def register_(on_what, mtype, event_name, method):
	""" Register a function/method as handler or callback for a given event.
		This generic function is called by all other ``register_*`` functions.

		It is not exported out of this module because it exists just for
		factoring purposes.

		.. note:: you won't see the logging.* of this function when registering
			events and other low-level foundations objects, because the verbose
			level of the program is not yet set when the register operation
			occurs. This is a known issue.

	"""
	assert ltrace_func(TRACE_EVENTS)

	with loop_lock:
		try:
			if method in on_what[event_name]:
				logging.warning(_(u'{0}: {1} {2} already registered for '
								u'event {3}.').format(
								stylize(ST_NAME, current_thread().name),
								mtype, stylize(ST_NAME, method),
								stylize(ST_NAME, event_name)))
				return

			on_what[event_name].append(method)

		except KeyError:
			on_what[event_name] = [ method ]

	if __debug__:
		logging.debug(_(u'{0}: registered {1} as new {2} for event {3}.').format(
								stylize(ST_NAME, current_thread().name),
								stylize(ST_NAME, method), mtype,
								stylize(ST_NAME, event_name)))
def unregister_(on_what, mtype, event_name, method):

	assert ltrace_func(TRACE_EVENTS)

	with loop_lock:
		try:
			on_what[event_name].remove(method)

			if __debug__:
				logging.debug(_(u'{0}: unregistered {2} {1} for event {3}.').format(
									stylize(ST_NAME, current_thread().name),
									stylize(ST_NAME, method), mtype,
									stylize(ST_NAME, event_name)))

		except KeyError:
			logging.warning(_(u'{0}: event "{1}" not found when trying to '
				u'unregister {2} {3}.').format(stylize(ST_NAME, current_thread().name),
					stylize(ST_NAME, event_name), mtype,
					stylize(ST_NAME, method.__name__)))

		except ValueError:
			logging.warning(_(u'{0}: {1} {2} already not registered for '
				u'event {3}.').format(stylize(ST_NAME, current_thread().name),
					mtype, stylize(ST_NAME, method.__name__)),
					stylize(ST_NAME, event_name))
def register_collector(collector):
	assert ltrace_func(TRACE_EVENTS)

	with loop_lock:
		events_collectors.append(collector)

		try:
			collector._setTimeout(3.0)

		except:
			# in case the event collector is inside the daemon, it is not
			# a pyro proxy, but just a thread. _setTimeout() will fail.
			pass

	logging.progress( _('{0}: registered event collector {1}.').format(
						stylize(ST_NAME, current_thread().name), stylize(ST_NAME, collector)))

	# we wait 6 seconds to send this special event, because all web clients
	# will take at most 5 seconds to reconnect to the WMI when it comes back.
	# This signal will tell them to resynchronize internal structures.
	LicornEvent('collector_reinit', collector=collector).emit(priorities.HIGH, delay=6.0)
def unregister_collector(collector):

		assert ltrace_func(TRACE_EVENTS)

		with loop_lock:
			try:
				events_collectors.remove(collector)

				logging.progress(_('{0}: unregistered event collector {0}.').format(
						stylize(ST_NAME, current_thread().name), stylize(ST_NAME, collector)))

			except ValueError:
				logging.exception(_(u'Error while trying to unregister collector {0}.'), collector)
def scan_object(objekt, meth_handler, meth_callback):
	for attribute in (getattr(objekt, attr) for attr in dir(objekt)):
		if callable(attribute):
			if hasattr(attribute, 'is_callback'):
				meth_callback(attribute.__name__, attribute)

			elif hasattr(attribute, 'is_handler'):
				meth_handler(attribute.__name__, attribute)
def collect_object(objekt):
	return scan_object(objekt, register_handler, register_callback)
def uncollect_object(objekt):
	return scan_object(objekt, unregister_handler, unregister_callback)
def collect(on_object=None):
	""" Collect events handlers and callbacks on a given object.
		Used to dynamically collect them when we add / remove
		features in a running daemon.

		:param on_object: an instance of something you want to
			collect handlers / callbacks on. Defaults to ``None``,
			meaning we will walk across LMC.* and all sub-objects
			to re-collect everything.

		.. versionadded:: 1.3
	"""
	assert ltrace_func(TRACE_EVENTS)

	with loop_lock:
		if on_object is None:
			# Not that cool to import something from the core here
			# (in foundations), but very comfortable to be able to.
			from licorn.core import LMC

			for controller in LMC:
				collect(controller)

				if hasattr(controller, '_look_deeper_for_callbacks') \
								and controller._look_deeper_for_callbacks:
					for objekt in controller:
						collect_object(objekt)
		else:
			collect_object(on_object)
def uncollect(self, on_object=None):
	""" TODO. """

	assert ltrace_func(TRACE_EVENTS)

	with loop_lock:
		if on_object is None:
			events_callbacks.clear()
			events_handlers.clear()

		else:
			uncollect_object(on_object)
def run():
	global looper_thread
	looper_thread = RoundRobinEventLooper('EventLooper')
	looper_thread.start()

	logging.progress(_(u'{0}: Licorn® Event Loop started.').format(stylize(ST_NAME, current_thread().name)))
def stop():
	""" Completely stop the event queue. This is meant to be done only
		one time, when the daemon stops. """
	# be sure the EventManager thread will stop when we'll tell
	# him to do so.
	looper_thread.stop()

	# enqueue a super high priority job containing None, which will
	# unblock the EventManager run_action_method().
	events_queue.put((-1, None))

	logging.progress(_(u'{0}: Licorn® Event Loop stopped.').format(stylize(ST_NAME, current_thread().name)))
def dump_status(long_output=False, precision=None, as_string=True):

	t     = looper_thread
	evts  = events_handlers
	cbks  = events_callbacks
	colls = events_collectors
	queue = events_queue

	with loop_lock:
		if as_string:
			if long_output:
				return _(u'{0}{1}: {2} events, {3} handler(s) and {4} callback(s) registered,\n{5}\n{6}').format(
					stylize(ST_RUNNING if t.is_alive() else ST_STOPPED, t.name),
					u'&' if t.daemon else u'',
					stylize(ST_RUNNING, str(len(evts))),
					stylize(ST_RUNNING, str(sum(len(l)
						for l in evts.values()))),
					stylize(ST_RUNNING, str(sum(len(l)
						for l in cbks.values()))),
					u'\n'.join(u'%s\n\t%s' % (key, '\n\t'.join(str(x)
																for x in value))
						for key, value in evts.iteritems()),
					u'\n'.join(u'%s\n\t%s' % (key, '\n\t'.join(str(x)
																for x in value))
						for key, value in cbks.iteritems())
					)
			else:
				return _(u'{0}{1} ({2} events, {3} handler(s) and {4} callback(s) registered)').format(
					stylize(ST_RUNNING
						if t.is_alive() else ST_STOPPED, t.name),
					u'&' if t.daemon else u'',
					stylize(ST_RUNNING, str(len(evts))),
					stylize(ST_RUNNING, str(sum(len(l)
						for l in evts.values()))),
					stylize(ST_RUNNING, str(sum(len(l)
						for l in cbks.values())))
					)
		else:
			return dict(
					name=t.name,
					alive=t.is_alive(),
					daemon=t.daemon,
					ident=t.ident,
					qsize=queue.qsize(),
					handlers=dict((key, [ v.__name__ for v in value ])
							for key, value in evts.iteritems()),
					callbacks=dict((key, [ v.__name__ for v in value ])
							for key, value in cbks.iteritems()),
					collectors=[ repr(c) for c in colls ]
				)

__all__ = (
	'LicornEvent', 'LicornEventType',
	'run', 'stop', 'collect', 'uncollect',
	'handler', 'register_handler', 'unregister_handler',
	'callback', 'register_callback', 'unregister_callback',
	'register_collector', 'unregister_collector',
	'dump_status', )

