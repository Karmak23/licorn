# -*- coding: utf-8 -*-
"""
Licorn extensions: mylicorn - http://docs.licorn.org/extensions/mylicorn

:copyright: 2012 Olivier Cortès <olive@licorn.org>

:license: GNU GPL version 2

"""

import os, time, urllib2
from threading import Thread

from licorn.foundations           import exceptions, logging, settings, events, json
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.threads   import Event

from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.constants import services, svccmds, distros

from licorn.daemon.threads        import LicornJobThread

from licorn.core                  import LMC
from licorn.extensions            import LicornExtension

# local imports; get the constants in here for easy typing/using.
from constants import *

LicornEvent = events.LicornEvent

# We communicate with MyLicorn® via the JSON-RPC protocol.
from licorn.contrib import jsonrpc

def print_web_exception(e):

	try:
		error = json.loads(e.read())['error']

	except:
		# if 'error' is not present, the remote server is not in debug mode.
		# Do not try to display anything detailled, there won't be.
		logging.warning('Remote web exception: %s\n\tRequest:\n\t\t%s\n\t%s' % (e,
			str(e.info()).replace('\n', '\n\t\t'),
			str(json.loads(e.read())).replace('\n', '\n\t\t')))

	else:
		logging.warning('Remote web exception: %s\n\tRequest:\n\t\t%s\n\t%s' % (e,
			str(e.info()).replace('\n', '\n\t\t'), error['stack'].replace('\n', '\n\t\t')))

class MylicornExtension(ObjectSingleton, LicornExtension):
	""" Provide connexion and remote calls to `my.licorn.org`.

		.. versionadded:: 1.4
	"""
	def __init__(self):
		assert ltrace_func(TRACE_MYLICORN)
		LicornExtension.__init__(self, name='mylicorn')

		# advertise if we are connected via a standard event.
		self.events.connected = Event()

	def initialize(self):
		""" The MyLicorn® extension is always available. At worst is it
			disabled when there is no internet connexion, but even that
			is not yet sure.
		"""

		assert ltrace_func(TRACE_MYLICORN)
		self.available = True

		return self.available
	def is_enabled(self):

		logging.info(_(u'{0}: extension always enabled unless manually '
							u'ignored in {1}.').format(self.pretty_name,
								stylize(ST_PATH, settings.main_config_file)))

		return True
	@events.handler_method
	def extension_mylicorn_check_finished(self, *args, **kwargs):

		# Just trigger an authentication.
		LicornEvent('extension_mylicorn_authenticate').emit()

	@events.handler_method
	def extension_mylicorn_authenticate(self, *args, **kwargs):
		""" Authenticate ourselves on the central server.

			.. note:: this callback is lanched after LMC.configuration is
				loaded, because we need the system UUID to be found. It is
				used as the local server unique identifier, added to the
				API key (if any).
		"""

		assert ltrace_func(TRACE_MYLICORN)

		if LMC.configuration.system_uuid is None:
			logging.warning(_(u'{0}: system UUID not found, aborting. There '
									u'may be a serious problem '
									u'somewhere.').format(self.pretty_name))
			return

		# Allow environment override for testing / development.
		if 'MY_LICORN_URI' in os.environ:
			MY_LICORN_URI = os.environ.get('MY_LICORN_URI')
			logging.notice(_(u'{0}: using environment variable {1} pointing '
				u'to {2}.').format(self.pretty_name,
					stylize(ST_NAME, 'MY_LICORN_URI'),
					stylize(ST_URL, MY_LICORN_URI)))
		else:
			# default value, pointing to official My Licorn® webapp.
			MY_LICORN_URI = 'http://my.licorn.org/json/'

		self.service = jsonrpc.ServiceProxy(MY_LICORN_URI)

		try:
			api_key = settings.mylicorn.api_key

		except:
			api_key = None

		try:
			res = self.service.authenticate(LMC.configuration.system_uuid, api_key)

		except Exception, e:

			if isinstance(e, urllib2.HTTPError):
				print_web_exception(e)

			else:
				logging.exception(_(u'{0}: error while authenticating; will retry '
											u'in one hour.'), self.pretty_name)

			LicornEvent('extension_mylicorn_authenticate').emit(delay=3600.0)
			return

		if res['result'] < 0:
			# if authentication goes wrong, we won't even try to do anything
			# more. Every RPC call needs authentication.
			logging.warning(_(u'{0}: failed to authenticate, retrying in one '
							u'hour (code: authenticate.{1}, message: {2})').format(
								self.pretty_name, authenticate[res['result']],
								res['message']))

			LicornEvent('extension_mylicorn_authenticate').emit(delay=3600.0)
			return

		logging.info(_(u'{0}: sucessfully authenticated ourselves '
						u'(code: authenticate.{1}, message: {2})').format(
							self.pretty_name, authenticate[res['result']],
							res['message']))

		# Now that we are authenticated, we can report ourselves to our central
		# server at a regular interval.
		self.__start_updater_thread()
	def __start_updater_thread(self):

		if not self.events.connected.is_set():
			self.events.connected.set()

			self.threads.updater = LicornJobThread(
								target=self.update_remote_informations,
								# informations are updated every hour by default.
								delay=3600,
								tname='extensions.mylicorn.updater',
								# first noop() is in 5 seconds.
								time=(time.time()+5.0),
								)

			self.threads.updater.start()

			self.licornd.collect_and_start_threads(collect_only=True)

	def __stop_updater_thread(self):

		if self.events.connected.is_set():
			try:
				self.threads.updater.stop()
				del self.threads.updater

			except:
				logging.exception(_(u'{0}: exception while stopping updater thread'),
																self.pretty_name)
			self.events.connected.clear()
	def update_remote_informations(self):
		""" Method meant to be run from a Job Thread. It will run `noop()`
			remotely, to trigger a remote informations update from the HTTP
			request contents. From our point of view, this is just a kind of
			"ping()".
		"""
		try:
			self.service.noop()

		except Exception, e:
			if isinstance(e, urllib2.HTTPError):
				print_web_exception(e)

			else:
				logging.exception(_(u'{0}: error while noop()\'ing; retrying '
											u'in one hour.'), self.pretty_name)

			# any [remote] exception will halt the current thread, and
			# re-trigger a full pass of "authentication-then-regularly-update"
			# after having waited one hour to make things settle.
			self.__stop_updater_thread()

			LicornEvent('extension_mylicorn_authenticate').emit(delay=3600.0)

