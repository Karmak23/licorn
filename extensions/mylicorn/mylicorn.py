# -*- coding: utf-8 -*-
"""
Licorn extensions: mylicorn - http://docs.licorn.org/extensions/mylicorn

:copyright: 2012 Olivier Cortès <olive@licorn.org>

:license: GNU GPL version 2

"""

import os
from threading import Thread

from licorn.foundations           import exceptions, logging, settings, events
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.constants import services, svccmds, distros

from licorn.core                  import LMC
from licorn.extensions            import LicornExtension

# local imports; get the constants in here for easy typing/using.
from constants import *

LicornEvent = events.LicornEvent

# We communicate with MyLicorn® via the JSON-RPC protocol.
from licorn.contrib import jsonrpc

class MylicornExtension(ObjectSingleton, LicornExtension):
	""" Provide connexion and remote calls to `my.licorn.org`.

		.. versionadded:: 1.4
	"""
	def __init__(self):
		assert ltrace_func(TRACE_MYLICORN)
		LicornExtension.__init__(self, name='mylicorn')
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

		myl = jsonrpc.ServiceProxy(MY_LICORN_URI)

		try:
			api_key = settings.mylicorn.api_key
		except:
			api_key = None

		res = myl.authenticate(LMC.configuration.system_uuid, api_key)

		if res['result'] < 0:
			# if authentication goes wrong, we won't even try to do anything
			# more. Every RPC call needs authentication.
			logging.warning(_(u'{0}: failed to authenticate (code: '
							u'authenticate.{1}, message: {2})').format(
								self.pretty_name, authenticate[res['result']],
								res['message']))
			return

		logging.info(_(u'{0}: sucessfully authenticated ourselves '
						u'(code: authenticate.{1}, message: {2})').format(
							self.pretty_name, authenticate[res['result']],
							res['message']))

