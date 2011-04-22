# -*- coding: utf-8 -*-
"""
Licorn Daemon WMI internals.
WMI = Web Management Interface.

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, mimetypes, urlparse, posixpath
import urllib, socket, time, signal, gettext

from threading      import current_thread
from traceback      import print_exc
from SocketServer   import TCPServer, ThreadingTCPServer
from BaseHTTPServer	import BaseHTTPRequestHandler

TCPServer.allow_reuse_address = True

from licorn.foundations           import options, logging, exceptions, process
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import verbose
from licorn.daemon.threads        import LicornBasicThread

from licorn.core import LMC

class WMIThread(LicornBasicThread):
	def __init__(self, licornd):
		assert ltrace('http', '| WMIThread.__init__()')

		LicornBasicThread.__init__(self, tname='WMIHTTPServer', licornd=licornd)
	def run(self):

		assert ltrace('http', 'WMIThread.run()')
		#logging.progress('''%s(%d): started, waiting for master to become '''
		#	'''ready.''' % (pname, os.getpid()))

		import licorn.interfaces.wmi as wmi
		WMIHTTPRequestHandler.wmi = wmi
		WMIHTTPRequestHandler.wmi.init()
		WMIHTTPRequestHandler.ip_addresses = (['127.0.0.1']
				+ LMC.configuration.network.local_ip_addresses())

		WMIHTTPRequestHandler.langs = self.licornd.langs

		if options.wmi_listen_address:
			# the daemon CLI argument has priority over the configuration
			# directive, for testing purposes.
			listen_address = options.wmi_listen_address

		elif LMC.configuration.licornd.wmi.listen_address:
			listen_address = LMC.configuration.licornd.wmi.listen_address

		else:
			# the fallback is * (listen on all interfaces)
			listen_address = ''

		if listen_address.startswith('if:') \
			or listen_address.startswith('iface:') \
			or listen_address.startswith('interface:'):

			raise NotImplementedError(
				'getting interface address is not yet implemented.')

		count = 0
		while not self._stop_event.is_set():
			# try creating an http server.
			# if it fails because of socket already in use, just retry
			# forever, displaying a message every second.
			#
			# when creation succeeds, break the loop and serve requets.
			try:
				self.httpd = ThreadingTCPServer((listen_address,
								LMC.configuration.licornd.wmi.port),
								WMIHTTPRequestHandler)
				break
			except socket.error, e:
				if e[0] == 98:
					logging.warning(_(u'{0}: socket already in use. '
						'waiting (total: %ds).').format(
							stylize(ST_NAME, self.name), count))
					count += 1
					time.sleep(1)
				else:
					logging.error(_(u'{0}: socket error %s.').format(
						stylize(ST_NAME, self.name), e))
					self.httpd = None
					self.stop()
					return

		logging.notice(_(u'{0}: {1} to answer requests at address {2}.').format(
			stylize(ST_NAME, self.name), stylize(ST_OK, _(u'ready')),
			stylize(ST_ADDRESS, 'http://%s:%s/' % (
				listen_address if listen_address else '*',
					LMC.configuration.licornd.wmi.port))))

		host, port = self.httpd.socket.getsockname()[:2]
		WMIHTTPRequestHandler.server_name = socket.getfqdn(host)
		WMIHTTPRequestHandler.server_port = port

		self.httpd.serve_forever(5.0)
	def stop(self):
		assert ltrace('http', 'WMIThread.stop()')
		LicornBasicThread.stop(self)
		if self.httpd:
			self.httpd.shutdown()

class WMIHTTPRequestHandler(BaseHTTPRequestHandler):
	""" TODO. """
	#: this is a reference to the licorn.interfaces.wmi module.
	#: it will be filled on thread load, to avoid us re-charging it at
	#: each HTTP request.
	wmi   = None
	langs = None

	ip_addresses = []

	server_name = None
	server_port = None
	def do_HEAD(self):
		try:
			f = self.send_head()
			if f:
				f.close()
		except socket.error, e:
			logging.warning('%s: harmless exception in do_HEAD(): %s. '
				'Full traceback follows:' % (
				current_thread().name, str(e).splitlines()[0]))
	def do_GET(self):
		try:
			f = self.send_head()
			if f:
				if type(f) in (type(''), type(u'')):
					self.wfile.write(f)
				else:
					buf = f.read(LMC.configuration.licornd.buffer_size)
					while buf:
						self.wfile.write(buf)
						buf = f.read(LMC.configuration.licornd.buffer_size)
					f.close()
		except socket.error, e:
			logging.warning('%s: harmless exception in do_GET(): %s. '
				'Full traceback follows:' % (
				current_thread().name, str(e).splitlines()[0]))
	def do_POST(self):
		""" Handle POST data and create a dict to be used later."""

		# TODO: protect ourselves against POST flood: if (too_much_data):
		# send_header('BAD BAD') and stop()

		post_data = self.rfile.read(
			int(self.headers.getheader('content-length')))

		post_data = post_data.split('&')
		self.post_args = {}
		for var in post_data:
			if var not in ('', '='):
				try:
					key, value = var.split('=')
				except ValueError:
					key = var
					value = ''

				if value != '':
					value = urllib.unquote_plus(value)

				if self.post_args.has_key(key):
					if type(self.post_args[key]) == type(''):
						self.post_args[key] = [ self.post_args[key], value ]
					else:
						self.post_args[key].append(value)
				else:
					self.post_args[key] = value

		#logging.info('%s' % self.post_args)

		self.do_GET()
	def send_head(self):
		"""Common code for HEAD/GET/POST commands.

		This sends the response code and MIME headers.

		Return value is either a file object (which has to be copied
		to the outputfile by the caller unless the command was HEAD,
		and must be closed by the caller under all circumstances), or
		None, in which case the caller has nothing further to do.
		"""

		#logging.progress('serving HTTP Request: %s.' % self.path)

		retdata = None

		if self.user_authorized():
			try:
				self.switch_lang()

				retdata = self.serve_virtual_uri()
			except exceptions.LicornWebException:
				retdata = self.serve_local_file()
		else:
			# return the 401 HTTP error code
			self.send_response(401, 'Unauthorized.')
			self.send_header('WWW-authenticate',
				'Basic realm="Licorn Web Management Interface"')
			retdata = ''

		self.end_headers()
		return retdata
	def switch_lang(self):
		""" Try to find a gettext translation suitable to the current visitor. """

		# this will get 'fr-FR,fr;q=0.8,en-US;q=0.6,en;q=0.4' for example
		langblocks = self.headers.getheader("accept-language").split(';')

		for langblock in langblocks:
			for lang in langblock.split(','):
				if lang in WMIHTTPRequestHandler.langs:
					# install the '_' only into the current thread. The builtin
					# one will redirect to it as needed, to make only the
					# current thread work in the language.
					current_thread()._ = WMIHTTPRequestHandler.langs[lang].ugettext

					logging.progress(_('{0}: switched to language {1} '
						'for http_user {2}.').format(
							stylize(ST_NAME, current_thread().name),
							stylize(ST_COMMENT, lang),
							stylize(ST_LOGIN, self.http_user)))
					break

	def user_authorized(self):

		""" Return True if authorization exists AND user is authorized."""

		authorization = self.headers.getheader("authorization")
		if authorization:
			authorization = authorization.split()
			if len(authorization) == 2:
				if authorization[0].lower() == "basic":
					import base64, binascii
					try:
						authorization = base64.decodestring(authorization[1])
					except binascii.Error:
						pass

					authorization = authorization.split(':')
					if len(authorization) == 2:
						#
						# TODO: make this a beautiful PAM authentication ?
						#
						try :

							user = LMC.users.by_login(authorization[0])

							if user.check_password(authorization[1]):

								try:
									group = LMC.groups.by_name(
											LMC.configuration.licornd.wmi.group)
								except exceptions.DoesntExistException:
									self.http_user = authorization[0]
									return True

								if group in user.groups:
									self.http_user = authorization[0]
									return True

						except exceptions.BadArgumentError:
							logging.warning(_(u'%s: empty username or '
								'password sent as authentification string.') %
									stylize(ST_NAME, self.name))
							return False
		return False
	def format_post_args(self):
		""" Prepare POST data for exec statement."""

		# TODO: verify there is no other injection problem than the '"' !!

		postargs = []
		for key, val in self.post_args.items():
			if type(val) == type(''):
				if val in ('True', 'False'):
					postargs.append('%s=%s' % (key, val))
				else:
					postargs.append('%s="%s"' % (key, val.replace('"', '\"')))
			else:
				postargs.append('%s=%s' % (key, val))

		return postargs
	def serve_virtual_uri(self):
		""" Serve dynamic URIs with our own code,
		and create pages on the fly. """

		retdata = None
		rettype = None

		# from http://www.java2s.com/Open-Source/Python/Web-Server/Snakelets/Snakelets-1.50/snakeserver/server.py.htm
		self.referer = self.headers.getheader('referer') or None

		if self.referer:
			# get the host and the port from where the client first
			# connected to us. This is the easiest way.
			self.hostaddr, self.hostport = self.referer.split('/', 3)[2].split(':')

		else:
			# try to guess everything, this will lead to errors in
			# many cases (ssh tunnels, NAT, port forwarding, etc).
			# we default to `server_name` (which will probably be
			# 0.0.0.0...) and then try to find something more precise.
			self.hostaddr = WMIHTTPRequestHandler.server_name
			self.hostport = LMC.configuration.licornd.wmi.port

			client_address_base = self.client_address[0].rsplit('.', 1)[0]

			# if we can find something more precise, use it.
			for ip in WMIHTTPRequestHandler.ip_addresses:
				if ip.startswith(client_address_base):
					try:
						# try to return the "short" hostname
						self.hostaddr = LMC.machines[ip].hostname
					except KeyError:
						# if it doesn't resolve,  return the IP address
						self.hostaddr = ip
					break

			del client_address_base

		# GET / has special treatment :-)
		if self.path == '/':
			rettype, retdata = self.wmi.base.index(
				self.path, self.http_user, referer=self.referer)

		else:
			# remove the last '/' (which is totally useless for us, even if it
			# is considered semantic for a dir/)
			if self.path[-1] == '/':
				self.path = self.path[:-1]
			# remove the first '/' before splitting (it is senseless here).
			args = self.path[1:].split('/')

			if len(args) == 1:
				args.append('main')
			elif args[1] == 'list':
				args[1] = 'main'

			if args[0] in dir(self.wmi):

				if hasattr(self, 'post_args'):
					py_code = ('rettype, retdata = self.wmi.%s.%s('
						'"%s", "%s" %s %s, referer=%s, '
						'wmi_hostname="%s", wmi_port=%s)') % (
						args[0], args[1], self.path, self.http_user,
						', "%s",' % '","'.join(args[2:]) \
							if len(args)>2 else ', ',
						', '.join(self.format_post_args()),
						'"%s"' % self.referer if self.referer else 'None',
						self.hostaddr, self.hostport)
				else:
					py_code = ('rettype, retdata = self.wmi.%s.%s('
						'"%s", "%s" %s referer=%s, '
						'wmi_hostname="%s", wmi_port=%s)') % (
						args[0], args[1], self.path, self.http_user,
						', "%s",' % '","'.join(args[2:])
							if len(args)>2 else ', ',
						'"%s"' % self.referer if self.referer else 'None',
						self.hostaddr, self.hostport)

				try:
					assert ltrace('http',
						'serve_virtual_uri:exec("%s")' % py_code)

					#TODO: #431
					#for i in postargs.iteritems() :
					#	kwargs[i] = i
					#getattr(getattr(wmi, niv1), niv2)(self.path, self.htt_user, **kwargs)
					exec py_code

				except (AttributeError, NameError), e:
					# this warning is needed as long as send_head() will produce
					# a 404 for ANY error. When it will able to distinguish
					# between bad requests and real 404, this warning will
					# disapear.
					logging.warning("exec(%s): %s." % (py_code, e))
					self.send_error(500,
						"Internal server error or bad request.\n\n%s" %
							self.wmi.utils.get_traceback(e))

				except TypeError, e:
					logging.warning('BadRequest/TypeError: %s.' % e)
					if options.verbose >= verbose.INFO:
						print_exc()

					rettype, retdata = 	self.wmi.utils.bad_arg_error(
											self.wmi.utils.get_traceback(e))

				except exceptions.LicornRuntimeException, e:
					logging.warning('Bad_Request/LicornRuntimeException: %s.'
						% e)
					rettype, retdata = self.wmi.utils.forgery_error()
			else:
				# not a self.wmi.* module
				raise exceptions.LicornWebException(
					'Bad base request (probably a regular file request).')

		#logging.info('>> %s: %s,\n %s: %s' % (type(rettype), rettype,
		#	type(retdata), retdata))

		if retdata:

			if rettype in ('img', self.wmi.utils.HTTP_TYPE_IMG):
				self.send_response(200)
				self.send_header("Content-type", 'image/png')

			elif rettype == self.wmi.utils.HTTP_TYPE_DOWNLOAD:
				# fix #104
				self.send_response(200)
				self.send_header('Content-type',
					'application/force-download; charset=utf-8')
				self.send_header('Content-Disposition',
					'attachment; filename=export.%s' % retdata[0])
				self.send_header('Pragma', 'no-cache')
				self.send_header('Expires', '0')

				# retdata was a tuple in this particular case.
				# forget the first argument (the content type) and
				# make retdata suitable for next operation.
				retdata = retdata[1]

			elif rettype == self.wmi.utils.HTTP_TYPE_REDIRECT:
				# special entry, which should not return any data, else
				# the redirect won't work.

				self.send_response(302)
				self.send_header("Location", retdata
					if retdata.startswith('http://')
					else 'http://%s:%s%s' % (
					self.hostaddr, self.hostport, retdata))
				self.send_header("Connection", 'close')
				self.end_headers()

				return ''

			else: # self.wmi.utils.HTTP_TYPE_TEXT
				self.send_response(200)
				self.send_header("Content-type", 'text/html; charset=utf-8')
				self.send_header("Pragma", "no-cache")

			self.send_header("Content-Length", len(retdata))

		return retdata
	def serve_local_file(self):
		""" Serve a local file (image, css, js…) if it exists. """

		retdata = None

		path = self.translate_path(self.path)

		assert ltrace('http', 'serving file: %s.' % path)

		if os.path.exists(path):

			ctype = self.guess_type(path)

			if ctype.startswith('text/'):
				mode = 'r'
			else:
				mode = 'rb'

			try:
				retdata = open(path, mode)

			except (IOError, OSError), e:
				if e.errno == 13:
					self.send_error(403, "Forbidden.")
				else:
					self.send_error(500, "Internal server error")

		else:
			self.send_error(404, "Not found.")

		if retdata:
			# use cache-control (HTTP/1.1)
			# TODO: use Expires (HTTP/1.0) if asked for.
			# http://performance.survol.fr/2008/10/expires-et-cache-control-une-date-limite-de-consommation-pour-vos-contenus/
			self.send_response(200)
			self.send_header("Content-type", ctype)

			# NOTE: i felt th need to define a developer mode, which would
			# have completely disabled the cache control. But I think any good
			# modern browser has a way to reload everything, bypassing the
			# cache-control directive, so i won't put anything fancy here.
			#
			# default cache expiration: One Year, as recommended by chromium
			# web audit helper.
			self.send_header('Cache-Control', 'public;max-age=31536000')

			fs = os.fstat(retdata.fileno())
			self.send_header("Content-Length", str(fs[6]))
			self.send_header("Last-Modified",
										self.date_time_string(fs.st_mtime))
		return retdata
	def guess_type(self, path):
		"""Guess the type of a file.

		Argument is a PATH (a filename).

		Return value is a string of the form type/subtype,
		usable for a MIME Content-type header.

		The default implementation looks the file's extension
		up in the table self.extensions_map, using application/octet-stream
		as a default; however it would be permissible (if
		slow) to look inside the data to make a better guess.
		"""
		base, ext = posixpath.splitext(path)
		if ext in self.extensions_map:
			return self.extensions_map[ext]
		ext = ext.lower()
		if ext in self.extensions_map:
			return self.extensions_map[ext]
		else:
			return self.extensions_map['']
	def translate_path(self, path):
		"""Translate a /-separated PATH to the local filename syntax.

		Components that mean special things to the local file system
		(e.g. drive or directory names) are ignored.
		XXX They should probably be diagnosed.

		"""
		# abandon query parameters
		path = urlparse.urlparse(path)[2]
		path = posixpath.normpath(urllib.unquote(path))
		words = path.split('/')
		words = filter(None, words)
		# FIXME: get rid of this variable.
		if os.getenv('LICORN_DEVEL'):
			path = os.getcwd()
		else:
			# FIXME: put this in LMC.configuration.licornd.wmi
			path = '/usr/share/licorn/wmi'
		for word in words:
			drive, word = os.path.splitdrive(word)
			head, word = os.path.split(word)
			if word in (os.curdir, os.pardir): continue
			if word == 'favicon.ico':
				word = 'images/favicon.ico'
			path = os.path.join(path, word)
		return path

	#
	# TODO: implement and override
	# BaseHTTPRequestHandler.log_{request,error,message}(), to
	# put logs into logfiles, like apache2 does ({access,error}.log). See
	# /usr/lib/python2.5/BaseHTTPServer.py for details.
	#

	#
	# Static code follows.
	#
	if not mimetypes.inited:
		mimetypes.init() # try to read system mime.types
	extensions_map = mimetypes.types_map.copy()
	extensions_map.update({
		'': 'application/octet-stream', # Default
        })
