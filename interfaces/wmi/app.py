# -*- coding: utf-8 -*-
"""
Licorn WMI2 base app and views.

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

import sys, os, time, re, itertools, urlparse
import json, types

from threading    import Event, RLock, current_thread
from Queue        import Queue, Empty

from django.contrib.auth.decorators import login_required
from django.contrib.auth			import logout as django_logout
from django.http					import HttpResponse, \
											HttpResponseForbidden, \
											HttpResponseNotFound, \
											HttpResponseRedirect
from django.template.loader         import render_to_string
from django.utils.translation       import ugettext_lazy as _

# WARNING: we can't import them here, because then `upgrades` would fail.
# 			anyway we don't use them in this file, but I keep them here
#			just to illustrate the warning.
#from django.contrib.sessions.models import Session
#from django.contrib.auth.models     import User

# ============================================================= Licorn® imports
from licorn.foundations           import logging, options, styles
from licorn.foundations           import events, pyutils
from licorn.foundations.events    import LicornEvent, LicornEventType
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.styles    import *
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.constants import priorities
from licorn.foundations.messaging import MessageProcessor

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

from licorn.core				  import LMC
from licorn.daemon.threads        import BaseLicornThread, LicornThread
from licorn.interfaces.wmi.libs   import utils

# =============================================================== Local classes

class WmiEventCollectorThread(LicornThread, MessageProcessor):
	def __init__(self, *a, **kw):
		LicornThread.__init__(self, *a, **kw)
		MessageProcessor.__init__(self, *a, **kw)

		assert ltrace_func(TRACE_THREADS)

		self.daemon = True
		self.name   = 'WmiEventsCollector'

		events.register_collector(self)
	def __str__(self):
		return stylize(ST_NAME, self.name)

	# ================================================ MessageProcessor methods
	def process_event(self, event, *a, **kw):
		""" This method just forward the message to the :meth:`dispatch_message`
		method of the :class:`~licorn.daemon.threads.LicornThread` class. """
		assert ltrace_func(TRACE_WMI)

		self.dispatch_message(event)
	# ========================================= WmiEventCollectorThread Methods
	def resync(self, signum=None, frameno=None):
		""" Put a special item in the queue, forcing the thread to reconnect
			to licornd. We must not do the reconnect operation from here, this
			would produce an error.

			.. note:: this method overrides the one from the
				:class:`~interfaces.LicornInterfaceBaseApplication`. """

		pass
	def process_data(self, licornd_event):
		""" TO TEST the event collection and propagation::

				licornd -rvWD

				# not necessary, but cool:
				get events -f all -v

				licornd-wmi -rvD

			Open the WMI / in a browser.

			And then, in a CLI shell::

				add user toto; add group test; mod user toto -l; mod group test -p
				mod user toto -L; mod group test -P; del user toto; del group test

		"""

		assert ltrace_func(TRACE_WMI)

		if licornd_event is None:
			return

		for session_key, user_queue in wmi_event_app.queues.iteritems():
			#assert ltrace(TRACE_EVENTS,
			#	_(u'WMI Event Collector: pushed {0} to WMI user {1}.'),
			#	(ST_NAME, licornd_event.name), (ST_NAME, User.objects.get(
			#		pk=Session.objects.get(
			#			pk=session_key).get_decoded()['user_id']).username))
			assert ltrace(TRACE_WMI, 'push {0} to HTTP session {1}.', (ST_NAME, licornd_event.name), session_key)
			user_queue.put(licornd_event)

	def stop(self, ignore_errors=True):

		if self._stop_event.is_set():
			logging.warning2(_(u'{0}: {1} tryied to stop us more '
						u'than once!').format(self, current_thread().name))
			return

		self._stop_event.set()

		assert ltrace_func(TRACE_THREADS)

		logging.monitor(TRACE_EVENTS, TRACELEVEL_1,
									_(u'Stopping WMI event collector thread.'))
		try:
			logging.progress(_(u'{0}: unregistering ourselves from '
								u'licornd collectors.').format(self))
			#LMC.release(force=True)
			events.unregister_collector(self)

		except Exception, e:
			if not ignore_errors:
				logging.exception(_(u'{0}: exception while unregistering '
										u'ourselves from licornd.'), self)

		try:
			# be sure we exits by unblocking
			# our queue but not processing anything.
			logging.progress(_(u'{0}: emptying our event queue.').format(self))
			self.incoming_events.put(None)

		except Exception, e:
			if not ignore_errors:
				logging.exception(_(u'{0}: exception while emptying our queue.'), self)
	def check_collector(self, collector):
		return collector == self
class DataCollectorThread(BaseLicornThread):
	""" Periodically collects data inside `licornd`, and dispatch the collected
		data to *listeners*.

		A listener is just a queue, one for each web user.

		Listeners are (un-)registered via methods of this class, which is meant
		to be instanciated only once per data collected (the collection is
		mutualized for all web-connected users).

		Singleton pattern is not enforced because the "only once" condition is
		on the collect-data-method side, not the class side.
	"""
	def __init__(self, method, *a, **kw):
		BaseLicornThread.__init__(self, *a, **kw)

		assert ltrace_func(TRACE_THREADS)

		self.daemon        = True
		self.interval      = method.interval
		self.run_method    = method
		self.has_listeners = Event()
		self.listeners     = []
	def stop(self):
		""" nothing yet to do to stop. """
		assert ltrace_func(TRACE_THREADS)
		pass
	def add_listener(self, listener_queue):

		assert ltrace_func(TRACE_WMI)

		self.listeners.append(listener_queue)

		# unblock the `while` in `self.run()`.
		self.has_listeners.set()
	def del_listener(self, listener_queue):

		assert ltrace_func(TRACE_WMI)

		if len(self.listeners) == 1:
			# re-block the `while` in `self.run()`.
			self.has_listeners.clear()

		try:
			self.listeners.remove(listener_queue)

		except ValueError:
			# already not present
			pass
	def run(self):

		assert ltrace_func(TRACE_WMI)

		if hasattr(self.run_method, 'js_method'):
			meth = self.run_method.js_method

		else:
			meth = 'update_' + self.run_method.__name__

		if hasattr(self.run_method, 'js_arguments'):
			# get a copy with [:], so that we don't append arguments
			# to the original list in the while loop.
			start_args, end_args = self.run_method.js_arguments[:]

		else:
			start_args = end_args = []

		while 1:
			self.has_listeners.wait()

			args = start_args[:]
			try:
				if hasattr(self.run_method, 'render_template'):
					args.append(
						json.dumps(
							render_to_string(
								self.run_method.render_template, {
									self.run_method.__name__:
										self.run_method()
									}
								)
							)
						)
				else:
					args.append(json.dumps(self.run_method()))

				args += end_args

				data = { 'method': meth, 'arguments': args }

				for listener in self.listeners:
					#assert ltrace(TRACE_WMI, 'push {0} to listener {1}.', (ST_COMMENT, data), (ST_NAME, listener))
					listener.put(data)

			except Exception, e:
				logging.exception(_(u'{0:s}: Exception while collecting {1}.'),
									self, self.run_method.__name__)

			time.sleep(self.interval)
class WmiOperatorThread(LicornThread):
	""" This thread (there should be only one) gets background operations in
		its queue from Django views, and runs these operations in the
		background, to avoid view seeming unresponsive when the resquested
		operation is long.
	"""
	def process_data(self, message):

		assert ltrace_func(TRACE_WMI)

		request, method, args, kwargs = message

		if type(method) == types.StringType:
			# FIXME: Comment/explanation needed. Is `list()` really needed?
			# Isn't `args` already a list? or is it a tuple?
			args = [ method ] + list(args)
			method = LMC.rwi.generic_resolved_call

		try:
			method(*args, **kwargs)

		except:
			logging.exception(_(u'{0}: cannot exec {0}({1}, {2})!'), self, method, args, kwargs)

			wmi_event_app.queues[request.session.session_key] = utils.notify(str(e))
class WmiEventApplication(ObjectSingleton):
	""" The "thing" that centralizes all background operations in the WMI. It
		is manupulated by licorn threads and via Django views. It holds "slave"
		(wmi-only) threads too, and is the central place to start and stop them.

		* via its event-collector, it receives all `Events` going via the daemon.
		* the thread push them to web-connected users.
		* manage push queues for client-server live communications.

	"""
	def __init__(self):

		# user push queues (one per user session)
		self.queues	= {}

		# protect self.queues against multi-threaded access
		self.qlock = RLock()

		# various internal helper threads
		self.threads  = {}

		# event handlers, which process events coming from `licornd` for
		# connected users.
		self.handlers = {}

		# the list of dynamically found apps. Can be different from the one
		# in Django settings.
		self.django_apps = []

		# `start()` will be done a little later, in the WMI daemon. Starting later
		# permits to import the `wmi_event_app` object without launching
		# automatically all its threads and internals. This is softer and allow
		# positionning the `import` statement higher in the `daemon/wmi.py` file.
		#self.start()
	def __str__(self):
		return stylize(ST_NAME, 'wmi_event_app')
	def queue(self, request):
		with self.qlock:
			return self.queues.setdefault(request.session.session_key, Queue())
	def push(self, request):
		""" This is really a long-polling request, not an HTTP push stream. We
			had problems setting up a stream, some events were missed from the
			client side (but all were well pushed by the server side).
		"""

		assert ltrace_func(TRACE_DJANGO)

		start_time = time.time()
		q = self.queue(request)

		# the first call is blocking, to make the request become long-polling.
		# we wait for at least one data to appear in the queue.
		data = q.get()

		if data is None:
			# return an empty response, to make the client restart the push stream
			logging.info(_(u'PUSH-stream force-close for user {0} (session {1})').format(
				stylize(ST_NAME, request.user.username), request.session.session_key))

			return HttpResponse(json.dumps({'data': [] }), mimetype='application/json')

		else:
			content = [ data ]

		# once we unblock, try to read as many items as possible, to avoid
		# many consequent small request from the client.
		while 1:
			try:
				content.append(q.get(False))

			except Empty:
				break

		tojson = []

		for data in content:

			if type(data) == LicornEventType:
				if data.name in self.handlers:
					try:
						for handler in self.handlers[data.name]:
							assert ltrace(TRACE_WMI, 'yield to user {0}@{1} {2}',
												request.user.username,
												request.META['REMOTE_ADDR'],
												stylize(ST_NAME, handler.__name__))

							for json_output in handler(request, data):
								tojson.append(json_output)

					except:
						logging.exception(_(u'Unexpected exception in Event '
											u'handler {0}; continuing.'),
											stylize(ST_NAME, handler.__name__))
				else:
					logging.warning2(_(u'No WMI handler yet for event '
								u'"{0}".').format(stylize(ST_NAME, data.name)))
					#yield utils.notify(_(u'No event handler <strong>yet</strong> '
					#	u'for event « <strong><code>{0}</code></strong> ».').format(data.name))

			else:
				# Transmit the result without modifying it. As any other
				# special method (not event handler) should already have
				# prepared the result, this should be safe.
				assert ltrace(TRACE_DJANGO, 'yield to user {1} from {2} data "{0}"',
													data, request.user.username,
													request.META['REMOTE_ADDR'])

				tojson.append(data)

		result = json.dumps({ 'data': tojson })

		return HttpResponse(result, mimetype='application/json')
	def start(self):

		assert ltrace_func(TRACE_DJANGO)

		logging.progress(_(u'{0}: starting threads and collecting '
								u'dynamic handlers.').format(self))

		for attr_name, thread_class in (('collector', WmiEventCollectorThread),
										('operator', WmiOperatorThread), ):
			setattr(self, attr_name, thread_class().start())

		# hints coming from http://stackoverflow.com/questions/301134/dynamic-module-import-in-python

		dirname = os.path.dirname(__file__)

		self.push_permissions = {}
		self.dynamic_sidebars = {}
		self.dynamic_statuses = {}
		self.dynamic_infos    = {}

		for entry in os.listdir(dirname):
			# If is has 'views' and 'urls', we consider it a django app;
			# it SHOULD have a `push_permissions` dict defined in __init__.py
			if os.path.exists(os.path.join(dirname, entry, 'views.py')) \
					and os.path.exists(os.path.join(dirname, entry, 'urls.py')):
				try:
					module = __import__('licorn.interfaces.wmi.%s' % entry,
									fromlist=["licorn.interfaces.wmi.%s" % entry])

					self.push_permissions.update(module.push_permissions)

					self.django_apps.append(entry)

				except AttributeError:
					logging.warning(_(u'module {0} does not include a {1} dict '
						u'in its {2} file!').format(stylize(ST_NAME, entry),
							stylize(ST_ATTR, 'push_permissions'),
							stylize(ST_PATH, '__init__.py')))

			if os.path.exists(os.path.join(dirname, entry, 'dynamics.py')):
				try:
					module = __import__('licorn.interfaces.wmi.%s.dynamics' % entry,
							fromlist=["licorn.interfaces.wmi.%s" % entry])

				except:
					logging.exception(_(u'Dynamic parts of module {0} cannot be '
									u'loaded!').format(stylize(ST_NAME, entry)))

				else:
					if hasattr(module, 'dynamic_sidebar'):
						self.dynamic_sidebars[entry] = module.dynamic_sidebar

					if hasattr(module, 'dynamic_status'):
						self.dynamic_statuses[entry] = module.dynamic_status

					if hasattr(module, 'dynamic_infos'):
						self.dynamic_infos[entry] = module.dynamic_infos

			if os.path.exists(os.path.join(dirname, entry, 'event_handlers.py')):

				module = __import__('licorn.interfaces.wmi.%s.event_handlers' % entry,
								fromlist=["licorn.interfaces.wmi.%s" % entry])

				for key, value in module.__dict__.iteritems():
					if key.endswith('_handler'):
						event_name = key[0:-8]
						if event_name in self.handlers:
							self.handlers[event_name].append(value)
						else:
							self.handlers[event_name] = [ value ]

		assert ltrace_var(TRACE_DJANGO, self.push_permissions)

		# this is meant to go in an external module / process in the near future.
		self.__setup_data_collectors()

		logging.info(_(u'{0}: all threads started, ready to dispatch events.').format(self))

		ltrace_func(TRACE_DJANGO, True)
	def push_setup(self, request):

		assert ltrace_func(TRACE_DJANGO)

		# remove '/setup' from current path to get the real location.
		path = request.get_full_path()[6:]

		# a sane, conservative and securitary default
		collected = None

		# we try to match from the longest first.
		for key in reversed(sorted(self.push_permissions)):
			if path.startswith(key):
				assert ltrace(TRACE_DJANGO, 'matched push perm {0} for path {1}.', key, path)

				if self.push_permissions[key][0](request):
					collected = self.push_permissions[key][1]

				else:
					collected = self.push_permissions[key][2]

				# we don't go farther than first match.
				break

		if collected is None:
			return HttpResponseForbidden('You do not have enough privileges '
										'to setup a PUSH stream for this URL.')

		self.push_setup_queue_and_collectors(request, collected)

		return HttpResponse('DONE.')
	def push_setup_queue_and_collectors(self, request, collectors_list):

		assert ltrace_func(TRACE_DJANGO)

		q = self.queue(request)
		threads = self.threads

		# the user is requesting setup, he connects to a new page.
		# 2 cases:
		# 	- the user was already connected to another page, he already has
		#		a push running (probably blocking); we need to unblock it
		#		and terminate the current push.
		#	- this is the first connection; nothing particular to do.

		if q.qsize() > 0:
			# consume all current events to /dev/null, they are most probably
			# out of date. Don't block on `q.get()`, this would be a bad idea.
			logging.warning2(_(u'Manual PUSH-stream queue-flush for user '
									u'{0} (session {1})').format(
									stylize(ST_NAME, request.user.username),
									request.session.session_key))
			try:
				while 1: q.get(False)

			except Empty:
				pass

		if request.session.get('previously_connected', False):
			q.put(None)

		else:
			request.session['previously_connected'] = True

		# clear all current collector listeners (from other pages).
		for thread in threads.itervalues():
			thread.del_listener(q)

		# setup collectors for current page only.
		for collector_name in collectors_list:
			try:
				threads[collector_name].add_listener(q)

			except KeyError:
				logging.warning(_(u'Cannot setup collector {0}.').format(collector_name))

		if request.session.get('not_yet_welcomed', True):
			# a kind of welcome message
			wmi_event_app.queue(request).put(
				utils.notify(_(u'Welcome to Licorn® WMI, {0}.').format(
										request.user.username)), 3500)
			request.session['not_yet_welcomed'] = False

		assert ltrace_func(TRACE_DJANGO, True)
	def resync(self):
		assert ltrace_func(TRACE_DJANGO)
		#self.collector.resync()
		pass
	def stop(self):
		assert ltrace_func(TRACE_DJANGO)

		logging.progress(_(u'{0}: stopping operator threads.').format(self))
		self.operator.stop()
		self.collector.stop()

		logging.progress(_(u'{0}: stopping helper threads.').format(self))
		for th in self.threads.itervalues():
			th.stop()

		logging.info(_(u'{0}: all thread stopped.').format(self))
	def __setup_data_collectors(self):
		""" this content is meant to go away when the data collector is done. """

		assert ltrace_func(TRACE_DJANGO)

		import collectors

		def init_data_collectors(module_):

			for attr_name in dir(module_):
				attr = getattr(module_, attr_name)

				if callable(attr) and hasattr(attr, 'interval'):
					yield DataCollectorThread(attr).start()

		for module_ in (collectors, ):
			if module_.not_started:
				self.threads.update((t.run_method.__name__, t) for t in init_data_collectors(module_))
				module_.not_started = False
	def enqueue_notification(self, request, message, *args, **kwargs):
		assert ltrace_func(TRACE_DJANGO)
		self.queue(request).put(utils.notify(message, *args, **kwargs))
	def enqueue_operation(self, request, method, *args, **kwargs):
		assert ltrace_func(TRACE_DJANGO)
		self.operator.dispatch_message((request, method, args, kwargs))
	def notify_not_implemented(self, request, func_name=None):
		assert ltrace_func(TRACE_DJANGO)
		self.queue(request).put(utils.notify(_(u'Sorry, the {0} functionnality '
					u'is not yet implemented.').format(func_name or 'clicked')))
	def django_apps_list(self):
		""" Get a list of WMI installed apps short names, if they have been
			detected during the start() method of this App.

			E.g, even if django settings have:

			INSTALLED_APPS = (
				'django.contrib.auth',
				'django.contrib.contenttypes',
				'django.contrib.sessions',
				'django.contrib.sites',
				'django.contrib.messages',
				'wmi.system',
				'wmi.users',
				'wmi.groups',
			)

			This method could return:

			[ 'system', 'users', 'groups', 'machines', 'backup' ]

			If 'backup' and 'machines' apps were successfully imported.
		"""

		return self.django_apps
#============================================================= Exported objects

wmi_event_app = WmiEventApplication()

@login_required
def push(request):
	""" This is the Django view which sends the PUSH stream to the connected
		web user. """
	return wmi_event_app.push(request)

@login_required
def setup(request):
	""" Setup the PUSH stream for the connected user.

		This is a Django view.
	"""
	return wmi_event_app.push_setup(request)

@login_required
def logout(request):
	""" Django view for loging out the connected user. It will stop the push
		stream and call the standard `django_logout()` function. After that,
		it redirects to '/'.

		.. todo:: send a good-bye notification.
	"""

	# disconnect all listeners, shutdown the push stream.
	wmi_event_app.push_setup(request)

	django_logout(request)

	from django.shortcuts import redirect

	return redirect('/', permanent=False)

__all__ = ('wmi_event_app', 'push', 'setup', 'logout')
