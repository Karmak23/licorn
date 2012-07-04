# -*- coding: utf-8 -*-
"""
Licorn extensions: mylicorn - http://docs.licorn.org/extensions/mylicorn

:copyright: 2012 Olivier Cortès <olive@licorn.org>

:license: GNU GPL version 2

"""

import os, time, urllib2, random

from threading import Thread

from licorn.foundations           import exceptions, logging, settings
from licorn.foundations           import events, json
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.threads   import Event

from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.constants import services, svccmds, distros, priorities

from licorn.daemon.threads        import LicornJobThread

from licorn.core                  import LMC
from licorn.extensions            import LicornExtension

# local imports; get the constants in here for easy typing/using.
from constants import *

LicornEvent = events.LicornEvent

# We communicate with MyLicorn® via the JSON-RPC protocol.
from licorn.contrib import jsonrpc

def random_delay(delay_max=5400):
	return float(random.randint(1800, delay_max))
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
		try:
			logging.warning('Remote web exception: %s\n\tRequest:\n\t\t%s\n\t%s' % (e,
				str(e.info()).replace('\n', '\n\t\t'), error['stack'].replace('\n', '\n\t\t')))
		except:
			logging.warning('Remote web exception: %s\n\tRequest:\n\t\t%s\n\t%s' % (e,
				str(e.info()).replace('\n', '\n\t\t'), str(error).replace('\n', '\n\t\t')))

class MylicornExtension(ObjectSingleton, LicornExtension):
	""" Provide connexion and remote calls to `my.licorn.org`.

		.. versionadded:: 1.4
	"""
	def __init__(self):
		assert ltrace_func(TRACE_MYLICORN)
		LicornExtension.__init__(self, name='mylicorn')

		# advertise if we are connected via a standard event.
		self.events.connected = Event()

		self.paths.config_file = os.path.join(settings.config_dir, 'mylicorn.conf')

		# unknown reachable status
		self.__is_reachable = None
	@property
	def reachable(self):
		return self.__is_reachable
	@property
	def connected(self):
		return self.events.connected.is_set()
	@property
	def api_key(self):
		return self.__api_key
	@api_key.setter
	def api_key(self, api_key):
		if not hlstr.cregex['api_key'].match(api_key):
			raise exceptions.BadArgumentError(_(u'Bad API key "{0}", must '
						u'match "{1}/i"').format(api_key, hlstr.regex['api_key']))

		# TODO: if connected: check the API key is valid.

		self.__save_configuration(api_key=self.__api_key)
	def initialize(self):
		""" The MyLicorn® extension is always available. At worst is it
			disabled when there is no internet connexion, but even that
			is not yet sure.
		"""

		assert ltrace_func(TRACE_MYLICORN)
		self.available = True

		# Allow environment override for testing / development.
		if 'MY_LICORN_URI' in os.environ:
			MY_LICORN_URI = os.environ.get('MY_LICORN_URI')
			logging.notice(_(u'{0}: using environment variable {1} pointing '
				u'to {2}.').format(self.pretty_name,
					stylize(ST_NAME, 'MY_LICORN_URI'),
					stylize(ST_URL, MY_LICORN_URI)))
		else:
			# default value, pointing to official My Licorn® webapp.
			MY_LICORN_URI = 'http://my.licorn.org/'

		if MY_LICORN_URI.endswith('/'):
			MY_LICORN_URI = MY_LICORN_URI[:-1]

		if not MY_LICORN_URI.endswith('/json'):
			# The ending '/' is important, else POST returns 301,
			# GET returns 400, and everything fails in turn…
			MY_LICORN_URI += '/json/'

		self.my_licorn_uri = MY_LICORN_URI

		defaults = { 'api_key': None }
		data     = defaults.copy()

		try:
			with open(self.paths.config_file) as f:
				data.update(json.load(f))

		except (OSError, IOError), e:
			if e.errno != errno.ENOPERM:
				raise e

		except:
			logging.warning(_(u'{0}: configuration file {1} seems '
								u'corrupt; not using it.').format(self,
							stylize(ST_PATH, self.paths.config_file)))

		klass = self.__class__.__name__

		# only take in data the parameters we know, avoiding collisions.
		for key in defaults:
			setattr(self, '_%s__%s' % (klass, key), data[key])

		return self.available
	def is_enabled(self):

		logging.info(_(u'{0}: extension always enabled unless manually '
							u'ignored in {1}.').format(self.pretty_name,
								stylize(ST_PATH, settings.main_config_file)))

		return True
	def __save_configuration(self, **kwargs):

		basedict = {}

		if os.path.exists(self.paths.config_file):
			basedict.update(json.load(open(self.paths.config_file, 'r')))

		basedict.update(kwargs)

		json.dump(basedict, open(self.paths.config_file, 'w'))

		LicornEvent('extension_mylicorn_configuration_changed', **kwargs).emit()

	@events.handler_method
	def licornd_cruising(self, *args, **kwargs):
		""" When Licornd is OK, we can start requesting the central server. """

		if self.enabled:
			self.authenticate()

	@events.handler_method
	def extension_mylicorn_authenticated(self, *args, **kwargs):
		""" Now that we are authenticated, we can report ourselves
			to our central server at a regular interval. """

		self.__start_updater_thread()

	@events.handler_method
	def extension_mylicorn_configuration_changed(self, *args, **kwargs):
		if 'api_key' in kwargs:
			self.disconnect()
			self.authenticate()

	@events.handler_method
	def daemon_shutdown(self, *args, **kwargs):
		""" Try to disconnected when the daemon shuts down. """
		if self.enabled:
			try:
				self.disconnect()
			except:
				pass

	def __start_updater_thread(self):

		if not self.events.connected.is_set():
			self.events.connected.set()

			self.threads.updater = LicornJobThread(
								target=self.update_remote_informations,
								# informations are updated every hour by default.
								delay=3600,
								tname='extensions.mylicorn.updater',
								# first noop() is in 1 seconds.
								time=(time.time()+1.0),
								)

			self.threads.updater.start()

			self.licornd.collect_and_start_threads(collect_only=True)
	def __stop_updater_thread(self):

		if self.events.connected.is_set():
			try:
				self.threads.updater.stop()
				del self.threads.updater

			except:
				logging.exception(_(u'{0}: exception while stopping '
										u'updater thread'),	self.pretty_name)

			# Back to "unknown" reachable state
			self.__is_reachable = None

			# and not connected, because not emitting to central.
			self.events.connected.clear()
	def __remote_call(self, rpc_func, *args, **kwargs):

		try:
			result = rpc_func(*args, **kwargs)

		except Exception, e:
			if isinstance(e, urllib2.HTTPError):
				print_web_exception(e)

			else:
				logging.exception(_(u'{0}: error while executing {1}'),
											self.pretty_name, rpc_func.__name__)

			return {'result' : common.FAILED,
					'message': _('RPC %s failed') % rpc_func.__name__}

		else:
			return result

	def disconnect(self):
		assert ltrace_func(TRACE_MYLICORN)

		if self.connected:

			LicornEvent('extension_mylicorn_disconnects', synchronous=True).emit()

			res = self.__remote_call(self.service.disconnect)

			code = res['result']

			if code < 0:
				# if authentication goes wrong, we won't even try to do anything
				# more. Every RPC call needs authentication.
				logging.warning(_(u'{0}: failed to disconnect (code: {1}, '
									u'message: {2})').format(
										self.pretty_name,
										stylize(ST_UGID, disconnect[code]),
										stylize(ST_COMMENT, res['message'])))

			else:
				logging.info(_(u'{0}: sucessfully disconnected (code: {1}, '
								u'message: {2})').format(
									self.pretty_name,
									stylize(ST_UGID, authenticate[code]),
									stylize(ST_COMMENT, res['message'])))

				LicornEvent('extension_mylicorn_disconnected').emit()

		else:
			logging.warning(_(u'{0}: already disconnected, not trying '
									u'again.').format(self.pretty_name))

	def authenticate(self):
		""" Authenticate ourselves on the central server. """

		assert ltrace_func(TRACE_MYLICORN)

		if self.connected:
			logging.warning(_(u'{0}: already connected, not doing '
									u'it again.').format(self.pretty_name))
			return

		if LMC.configuration.system_uuid in (None, ''):
			logging.warning(_(u'{0}: system UUID not found, aborting. There '
									u'may be a serious problem '
									u'somewhere.').format(self.pretty_name))
			return

		self.service = jsonrpc.ServiceProxy(self.my_licorn_uri)

		res = self.__remote_call(self.service.authenticate,
									LMC.configuration.system_uuid, self.api_key)

		code = res['result']

		if code < 0:
			# if authentication goes wrong, we won't even try to do anything
			# more. Every RPC call needs authentication.
			logging.warning(_(u'{0}: failed to authenticate, will retry later '
								u'(code: {1}, message: {2})').format(
									self.pretty_name,
									stylize(ST_UGID, authenticate[code]),
									stylize(ST_COMMENT, res['message'])))

			workers.network_enqueue(priorities.NORMAL, self.authenticate,
													job_delay=random_delay())
		else:
			logging.info(_(u'{0}: sucessfully authenticated '
							u'(code: {1}, message: {2})').format(
								self.pretty_name,
								stylize(ST_UGID, authenticate[code]),
								stylize(ST_COMMENT, res['message'])))

			LicornEvent('extension_mylicorn_authenticated').emit()
	def update_reachability(self):
		""" Ask the central server if we are reachable from the Internet or not. """

		# Unknown status by default
		self.__is_reachable = None

		res = self.__remote_call(self.service.is_reachable)

		code = res['result']

		if code == is_reachable.SUCCESS:
			self.__is_reachable = True

		elif code == is_reachable.UNREACHABLE:
			self.__is_reachable = False

		logging.info(_(u'{0}: our reachability state is now {1}.').format(
					self.pretty_name, stylize(ST_ATTR, 'UNKNOWN'
												if code == is_reachable.FAILED
												else is_reachable[code])))
	def update_remote_informations(self):
		""" Method meant to be run from a Job Thread. It will run `noop()`
			remotely, to trigger a remote informations update from the HTTP
			request contents. From our point of view, this is just a kind of
			"ping()".
		"""
		res = self.__remote_call(self.service.noop)

		code = res['result']

		if code < 0:
			# any [remote] exception will halt the current thread, and
			# re-trigger a full pass of "authentication-then-regularly-update"
			# after having waited one hour to make things settle.
			self.__stop_updater_thread()

			workers.network_enqueue(priorities.NORMAL, self.authenticate,
													job_delay=random_delay())

		else:
			logging.info(_('{0}: successfully noop()\'ed {1}.').format(
						self.pretty_name, stylize(ST_URL, self.my_licorn_uri)))

			# wait a little for the central server to have tested our
			# reachability before asking for it back.
			workers.network_enqueue(priorities.NORMAL, self.update_reachability,
																job_delay=20.0)

__all__ = ('MylicornExtension', )
