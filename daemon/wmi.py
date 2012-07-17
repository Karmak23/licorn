#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn WMI2: a WSGI dedicated web-server.
WMI means "Web Management Interface".

:copyright: 2007-2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

import sys, socket

try:
	# http://twistedmatrix.com/documents/current/web/howto/web-in-60/wsgi.html
	from twisted.web import version; del version

except ImportError:
	sys.stderr.write(u'Please install the Twisted Web Python package before starting the WMI.')
	raise SystemExit(911)

from socket    import error
from threading import current_thread

from django.core.handlers.wsgi    import WSGIHandler

from licorn.foundations           import options, settings, logging
from licorn.foundations           import styles
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.threads   import Event

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

from licorn.daemon.threads      import BaseLicornThread
from licorn.interfaces.wmi      import django_setup, wmi_event_app

class WebManagementInterface(BaseLicornThread):
	"""
		Usefull readings:
		 * http://stackoverflow.com/questions/2583350/is-epoll-the-essential-reason-that-tornadowebor-nginx-is-so-fast
	"""
	def __init__(self, *args, **kwargs):
		super(WebManagementInterface, self).__init__(*args, **kwargs)

		assert ltrace_func(TRACE_HTTP)

		self.name   = self.__class__.__name__
		self.daemon = True
	def run(self, *args, **kwargs):

		assert ltrace_func(TRACE_HTTP)

		self._stop_event = Event()

		# The django setup is needed for the wmi_event_app, which needs the
		# environment to load.
		#
		# The wmi_event_app must be loaded here in MainThread, because it will
		# setup a signal handler (to reconnect to master `licornd`).
		#
		# And all this can't be done before because we need to be root to
		# access logs and other restricted resources. To be root, we need to
		# be sure to operate after an eventual "refork" operation which occurs
		# in `self.main_post_parse_arguments()`.
		django_setup()
		wmi_event_app.start()

		self.run_http_server()
	def run_http_server(self):

		assert ltrace_func(TRACE_HTTP)

		if options.wmi_listen_address:
			# the daemon CLI argument has priority over the configuration
			# directive, for testing purposes.
			listen_address = options.wmi_listen_address

		elif settings.licornd.wmi.listen_address:
			listen_address = settings.licornd.wmi.listen_address

		else:
			# the fallback is * (listen on all interfaces)
			listen_address = ''

		if listen_address.startswith('if:') \
			or listen_address.startswith('iface:') \
			or listen_address.startswith('interface:'):

			raise NotImplementedError(
				'getting interface address is not yet implemented.')

		# Import twisted things here, *after the daemonization*. Else they
		# will fail with obscure "Bad File descriptors" errors (see
		# http://www.robgolding.com/blog/2011/02/05/django-on-twistd-web-wsgi-issue-workaround/
		# for details). NOTE: everything goes like a breeze if we don't
		# daemonize the WMI.
		from twisted.web      import server
		from twisted.web.wsgi import WSGIResource
		from twisted.internet import reactor, ssl

		# get a reference handy for the shutdown sequence
		self.reactor = reactor

		# Not yet ready
		# http://twistedmatrix.com/trac/export/29073/branches/websocket-4173-2/doc/web/howto/websocket.xhtml
		#from twisted.web.websocket import WebSocketSite

		count = 0
		while not self._stop_event.is_set():
			# try creating an http server.
			# if it fails because of socket already in use, just retry
			# forever, displaying a message every second.
			#
			# when creation succeeds, break the loop and start serving requets.
			try:
				reactor.listenSSL(3356,
									server.Site(WSGIResource(reactor,
												reactor.getThreadPool(),
												WSGIHandler())
										),
									contextFactory = ssl.DefaultOpenSSLContextFactory(
													settings.licornd.wmi.ssl_key,
													settings.licornd.wmi.ssl_cert
										)
									)

				break
			except (error, socket.error), e:
				if e[0] == 98:
					logging.warning(_(u'{0}: socket already in use. '
						'waiting (total: %ds).').format(
							stylize(ST_NAME, self.name), count))
					count += 1
					time.sleep(1)
				else:
					logging.error(_(u'{0}: socket error {1}.').format(
						stylize(ST_NAME, self.name), e))
					self.stop()
					return

		logging.notice(_(u'{0}: {1} to answer requests at address {2}.').format(
			stylize(ST_NAME, self.name), stylize(ST_OK, _(u'ready')),
			stylize(ST_ADDRESS, 'https://%s:%s/' % (
				listen_address if listen_address else '*',
					settings.licornd.wmi.port))))

		# don't install signal handlers, they are handled by the main daemon
		# and propagated to twisted via the stop() method.
		# for details, see http://twistedmatrix.com/trac/wiki/FrequentlyAskedQuestions#Igetexceptions.ValueError:signalonlyworksinmainthreadwhenItrytorunmyTwistedprogramWhatswrong
		self.reactor.run(installSignalHandlers=0)
	def stop(self):

		assert ltrace_func(TRACE_HTTP)

		# http://stackoverflow.com/questions/6526923/stop-twisted-reactor-on-a-condition
		if current_thread().name == 'MainThread':
			self.reactor.callFromThread(self.reactor.stop)

		else:
			self.reactor.stop()

		wmi_event_app.stop()
__all__ = ('WebManagementInterface', )
