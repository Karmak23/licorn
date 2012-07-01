# -*- coding: utf-8 -*-
"""
  Copyright (c) 2007 Jan-Klaas Kollhof

  This file is part of jsonrpc.

  jsonrpc is free software; you can redistribute it and/or modify
  it under the terms of the GNU Lesser General Public License as published by
  the Free Software Foundation; either version 2.1 of the License, or
  (at your option) any later version.

  This software is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public License
  along with this software; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

import sys, os, urllib2, base64, cookielib

from json               import dumps, loads
from licorn.foundations import settings

class JSONRPCException(Exception):
	def __init__(self, rpcError):
		Exception.__init__(self)
		self.error = rpcError

class ServiceProxy(object):

	cookie_jars = {}
	url_openers = {}
	headers     = {}

	def __init__(self, serviceURL, serviceName=None, username=None, password=None):

		self.__serviceURL  = serviceURL
		self.__serviceName = serviceName

		if serviceName == None:
			# Setup all "things" for the base URL. This will be done only once:
			# when calling methods, `serviceName` is always not ``None``.

			# Setup the local cookies, used to keep the JSON-RPC session open.
			ServiceProxy.cookie_jars[serviceURL] = urllib2.HTTPCookieProcessor(
										cookielib.FileCookieJar(os.path.join(
											settings.cache_dir, 'cookies.txt')))

			#
			# NOTE: if `http_proxy` variable exists in environment, urllib2
			# 		will use the proxy automatically. No need for additionnal
			#		setup / opener.
			#

			ServiceProxy.url_openers[serviceURL] = urllib2.build_opener(
									ServiceProxy.cookie_jars[serviceURL])

			if username:
				if password is None:
					password = ''

				ServiceProxy.headers[serviceURL] = { "Authorization":
										'Basic %s' % base64.b64encode(
										username + ":" + password).strip() }
			else:
				ServiceProxy.headers[serviceURL] = {}

	def __getattr__(self, name):

		if self.__serviceName != None:
			name = "%s.%s" % (self.__serviceName, name)

		return ServiceProxy(self.__serviceURL, name)

	def __call__(self, *args):
		postdata = dumps({	'method' : self.__serviceName,
							'params' : args,
							'id'     : 'jsonrpc'})

		req = urllib2.Request(self.__serviceURL, postdata,
								ServiceProxy.headers[self.__serviceURL])

		resp = loads(ServiceProxy.url_openers[self.__serviceURL].open(req).read())

		if resp['error'] != None:
			raise JSONRPCException(resp['error'])

		else:
			return resp['result']
