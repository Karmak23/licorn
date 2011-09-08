#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn® daemon Event manager / dispatcher

:copyright: 2011-2010 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2

"""

from threading import RLock, current_thread
from Queue     import PriorityQueue
from traceback import print_exc

from licorn.foundations           import logging, exceptions
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces import *
from licorn.core                  import LMC
from licorn.daemon.threads        import LicornBasicThread

class EventManager(LicornBasicThread):
	""" Process internal events and run callbacks associated to them,
		synchronously or not.

		.. versionadded:: 1.3
	"""
	def __init__(self, licornd):

		LicornBasicThread.__init__(self, 'EventManager', licornd)

		self._input_queue = PriorityQueue()

		# my dict of events, with a list of callback to call, for each.
		self.__events = {}

		self.__lock   = RLock()
	def dump_status(self, long_output=False, precision=None):

		with self.__lock:
			return _(u'{0}{1} ({2} events & {3} callbacks registered)').format(
				stylize(ST_RUNNING
					if self.is_alive() else ST_STOPPED, self.name),
				'&' if self.daemon else '',
				stylize(ST_RUNNING,   str(len(self.__events))),
				stylize(ST_RUNNING,   str(sum(len(l)
					for l in self.__events.values()))))
	def stop(self):
		self.uncollect()
		LicornBasicThread.stop(self)
		self._input_queue.put((-1, None))
	def run_action_method(self):
		""" this method will be run by the LicornBasicThread.run() method,
			in a while loop. """

		priority, event = self._input_queue.get()

		if event is None:
			return

		if event.synchronous:
			self.run_event(event)
		else:
			try:
				for method in self.__events[event.name]:
					L_service_enqueue(priority,
								self.__run_one_event_method, event, method)
			except KeyError:
				logging.warning2(_(u'{0}: no callbacks / methods for event {1}.').format(
					stylize(ST_NAME, self.name),
					stylize(ST_NAME, event.name)),
					to_listener=False)
				self.__events[event.name] = []

	def __run_one_event_method(self, event, method):
		""" Run a given method, for a given event. ``event`` is only used to
			know its name in case of an exception/error, and to call its
			callback if defined. """

		try:
			assert ltrace(TRACE_EVENTS, '| EventsManager.__run_one_event_method(%s, %s, %s, callback=%s, %s)' % (
				event.name, method, ', '.join(event.args), event.callback,
				', '.join('%s=%s' % (key, value) for key,value in event.kwargs.iteritems())))

			method(*event.args, callback=event.callback, **event.kwargs)

		except Exception, e:
			logging.warning(_(u'{0}: exception encountered while '
				'running event {1}: {2}').format(
					stylize(ST_NAME, self.name),
					stylize(ST_NAME, event.name), e))
			print_exc()
	def dispatch(self, priority, event):
		assert ltrace(TRACE_EVENTS, '| EventsManager.dispath(%s, %s)' % (priority, event.name))

		self._input_queue.put((priority, event))
	def run_event(self, event):
		""" Will "run" or execute an event synchronously: all callbacks
			associated with a given ``event`` are executed in turn, then this
			method returns.

			It will not crash if an exception is encoutered
			in any method, but will display a stack trace and continue with
			next method. """

		try:
			assert ltrace(TRACE_EVENTS, '| EventsManager.run_event(%s)' % event.name)

			methods = self.__events[event.name]

		except KeyError, e:
			assert ltrace(TRACE_EVENTS, _(u'{0}: no callbacks / methods for event {1}.').format(
								stylize(ST_NAME, self.name),
								stylize(ST_NAME, event.name)))
			self.__events[event.name] = []
			return

		for method in methods:
			self.__run_one_event_method(event, method)
	# comfort alias
	send_event = dispatch
	def event_register(self, event_name, reg_method):

		assert ltrace(TRACE_EVENTS, '  %s: register method %s of %s for event %s.' % (
							current_thread().name, reg_method.im_func,
							reg_method.im_self, stylize(ST_NAME, event_name)))
		with self.__lock:
			try:
				self.__events[event_name].append(reg_method)
			except KeyError:
				self.__events[event_name] = [ reg_method ]
	def event_unregister(self, event_name, unr_method):

		try:
			assert ltrace(TRACE_EVENTS, '  %s: unregister method %s of %s for event %s.' % (
							current_thread().name, unr_method.im_func,
							unr_method.im_self, stylize(ST_NAME, event_name)))

			with self.__lock:
				self.__events[event_name].remove(unr_method)

		except KeyError:
			logging.warning(_(u'{0}: event "{1}" not found when trying to '
				'unregister method {2}.').format(stylize(ST_NAME, self.name),
					stylize(ST_NAME, event_name), stylize(ST_NAME, str(unr_method))))

		except ValueError:
			logging.warning(_(u'{0}: method {1} already not registered for '
				'event {2}.').format(stylize(ST_NAME, self.name),
					stylize(ST_NAME, str(method)),
					stylize(ST_NAME, event_name)))
	def __collect(self, objekt):

		assert ltrace(TRACE_EVENTS, '| EventsManager.__collect(%s)' % objekt.name)

		for attr in dir(objekt):
			if attr.endswith('_callback'):
				self.event_register(attr[0:-9], getattr(objekt, attr), )
	def uncollect(self, on_object=None):

		assert ltrace(TRACE_EVENTS, '| EventsManager.uncollect(%s)' % (
							'None' if on_object is None else on_object.name))
		assert ltrace(TRACE_LOCKS, '> EventsManager.uncollect(): %s' % self.__lock)

		with self.__lock:
			if on_object is None:
				self.__events.clear()
			else:
				self.__uncollect(on_object)
	def __uncollect(self, objekt):

		assert ltrace(TRACE_EVENTS, '| EventsManager.__uncollect(%s)' % objekt.name)

		for attr in dir(objekt):
			if attr.endswith('_callback'):
				self.event_unregister(attr[0:-9], getattr(objekt, attr))
	def collect(self, on_object=None):
		""" collect controllers, extensions  and unit objects event callbacks.
		"""
		assert ltrace(TRACE_EVENTS, '> EventsManager.collect(%s)' % (
							'None' if on_object is None else on_object.name))
		assert ltrace(TRACE_LOCKS, '> EventsManager.collect(): %s' % self.__lock)

		with self.__lock:

			if on_object is None:
				for controller in LMC:
					self.__collect(controller)

					if hasattr(controller, '_look_deeper_for_callbacks') \
									and controller._look_deeper_for_callbacks:
						for objekt in controller:
							self.__collect(objekt)
			else:
				self.__collect(on_object)

		assert ltrace(TRACE_LOCKS, '< EventsManager.collect(): %s' % self.__lock)
