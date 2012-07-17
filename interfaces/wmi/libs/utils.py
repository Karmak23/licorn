# -*- coding: utf-8 -*-
"""
Licorn WMI2 utils

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

import os, time, types, json, mimetypes, uuid, socket

#
# WARNING: please don't import nothing from Django here.
# If needed, do it in functions. But generally speaking,
# avoid it: we are in libs, this is a low-level module.
#

from licorn.foundations             import logging, pyutils, settings, cache
from licorn.foundations.ltrace      import *
from licorn.foundations.ltraces     import *
from licorn.foundations.styles      import *
from licorn.foundations.base        import ObjectSingleton
from licorn.core                    import LMC, version

# local imports
from decorators                     import *

def select(*a, **kw):
	""" Mimics the daemon.rwi.select() method, but wraps the results into
		CoreObjectProxies for easier and transparent operations on the WMI side. """

	from licorn.daemon.main import daemon

	#print '>> selecting', str(a), str(kw), 'in', LMC, LMC.rwi, LMC._connections, LMC.system.noop()
	#remote_selection = daemon.rwi.select(*a, **kw)
	#lprint(remote_selection)
	return daemon.rwi.select(*a, **kw)
def select_one(*a, **kw):
	from licorn.daemon.main import daemon

	#print '>> selecting ONE', str(a), str(kw), 'in', LMC, LMC.rwi, LMC._connections, LMC.system.noop()
	try:
		return daemon.rwi.select(*a, **kw)[0]
	except IndexError:
		return None

# ================================================================== WMI2 utils

def unique_hash(replacement=None):
	""" Jinja2 globals which just returns `uuid.uuid4().hex`. """

	return str(uuid.uuid4().hex).replace('-', replacement or '-')

# JS and RPC-JS related functions
def notify(message, timeout=None, css_class=None):
	""" OLD notification system (WMI2 version < 1.3.1). Please use
		`notification()` instead (via the auto-instanciated
		:class:`_notification` class), it is much simpler and feature
		complete. """

	assert ltrace_func(TRACE_DJANGO)
	return format_RPC_JS('show_message_through_notification', message,
							timeout or u'', css_class or u'')

class _notification(ObjectSingleton):
	""" This class avoids importing the WMI event App everywhere, when a
		client-side notification is needed.

		.. versionadded:: 1.3.1, during the #762 re-implementation.
	"""

	def __import(self):
		from licorn.interfaces.wmi.app import wmi_event_app
		self.wmi_event_app = wmi_event_app

	def __call__(self, request, message, timeout=None, css_class=None):

		assert ltrace_func(TRACE_DJANGO)

		try:
			self.wmi_event_app.queue(request).put(format_RPC_JS(
					'show_message_through_notification',
					message, timeout or u'', css_class or u'')
				)
		except:
			self.__import()
			self.wmi_event_app.queue(request).put(format_RPC_JS(
					'show_message_through_notification',
					message, timeout or u'', css_class or u'')
				)
notification = _notification()
def wmi_exception(request, exc, *args):
	""" Provide the exception on the daemon side (log or console), and notify
		the client via the push mechanism, all in one call. """

	logging.exception(*args)
	notification(request, args[0].format(*args[1:])
							+ _(' (was: {0})').format(exc))
def format_RPC_JS(JS_method_name, *js_arguments):

	assert ltrace_func(TRACE_DJANGO)
	return { 'method'    : JS_method_name,
						'arguments' : [ json.dumps(unicode(a)
											if type(a) == types.StringType
											else a) for a in js_arguments ] }
def dynamic_urlpatterns(dirname):
	""" Scan the local directory, looking for Django apps that define
		dependancies and URL base bases in their `__init__.py` and
		yield them if the dependancies are met.

		* ``dependancies`` must be a list/tuple of strings or unicode
			expressions that must evaluate to ``True`` for the dependancy
			to be considered satisfied
			(eg. 'LMC.extensions.rdiffbackup.enabled'). For this to work,
			the local environment always contains Licorn® ``LMC`` (from the
			``core`` and ``settings`` from the ``foundations``.
		* ``url_base`` must be a string containing the base URL for the
			module.

		.. versionadded:: 1.3.1
 		"""

	# These dependancies are re-imported here to be sure they are always
	# available when we test Django app dependancies.
	from licorn.core import LMC

	for entry in os.listdir(dirname):

		if entry[0] == '.':
			continue

		if os.path.exists(os.path.join(dirname, entry, '__init__.py')):

			modname = 'licorn.interfaces.wmi.%s' % entry

			try:
				module = __import__(modname, fromlist=[ modname ])

			except ImportError:
				logging.exception(_('Could not import module {0}'),
														(ST_NAME, modname))
				continue

			try:
				dependancies = module.dependancies
				base_url     = module.base_url

			except:
				# module has no dependancies, continue
				continue

			load_urls = True

			for dependancy in dependancies:
				if type(dependancy) not in (type(''), type(unicode)):
					load_urls = False
					logging.warning(_(u'Dependancy {0} of Django app {1} is '
						u'unsafe (not a str() nor an unicode() object), '
						u' ignoring the app completely.'))
					break

				try:
					result = eval(dependancy)

				except:
					load_urls = False
					logging.warning2(_(u'Urls of Django app {0} are not '
								u'loaded because dependancy {1} is not '
								u'satisfied.').format(stylize(ST_NAME, entry),
									stylize(ST_BAD, dependancy)))
					break

				else:
					if not result:
						load_urls = False
						logging.warning2(_(u'Urls of Django app {0} are not '
									u'loaded because dependancy {1} is not '
									u'satisfied.').format(
										stylize(ST_NAME, entry),
										stylize(ST_BAD, dependancy)))
						break


			if load_urls:
				logging.progress(_(u'Dynamically loading URL patterns for '
								u'Django app {0}, all dependancies '
								u'satisfied.').format(stylize(ST_NAME, entry)))
				yield base_url, entry

# This must be done at least once.
mimetypes.init()
@cache.cached(cache.one_hour)
def server_address(request):

	name = request.META['SERVER_NAME']

	ip = socket.gethostbyname(name)

	if ip == name:
		return name
	else:
		return '%s (%s)' % (name, ip)

def download_response(filename):
	""" Gets a filename from a string, returns an `HttpResponse` for the
		download. This is kind of a "view helper". It should probably go
		elsewhere to avoid the Django imports, but as it's the only of this
		kind of thing we have, we didn't mind creating a dedicated file yet.

		When reaching here, no check is made on the filename, path, etc.
		It's up to the caller view to verify the filename and the file
		content is secure to transmit.
	"""

	from django.core.servers.basehttp   import FileWrapper
	from django.http					import HttpResponse

	wrapper  = FileWrapper(file(filename))
	mtype    = mimetypes.guess_type(filename)[0]
	response = HttpResponse(wrapper,
							content_type=mtype or 'application/octet-stream')

	response['Content-Length']      = os.path.getsize(filename)
	response['Content-Disposition'] = 'attachment; filename="{0}"'.format(
								# Double quote are translated to simple ones.
								# this is ugly, but simple, and avoid crashing
								# the client with "double headers" error.
								os.path.basename(filename).replace('"',"'"))

	return response

# =============================================================== Jinja2 globals


def config(key_name):

	# remote:
	#return LMC.rwi.configuration_get(key_name)

	# local:
	result = pyutils.resolve_attr("LMC.configuration.%s" % key_name, { "LMC": LMC })
	return result() if callable(result) else result
def licorn_setting(key_name):
	#remote:
	#return LMC.rwi.setting_get(key_name)

	# local:
	return pyutils.resolve_attr("settings.%s" % key_name, {'settings': settings})
def get_lmc():
	return LMC
def now():
	""" Jinja2 global, just returns `time.time()`. """
	return time.time()
def djsettings():
	""" Access Django `settings` from templates. A pity this can't be done
		without this function. And Jinja2 wants 'GLOBALS' to be callable, thus
		this function just return Django `settings`.

		This function is a Jinja2 global.
	"""

	from django.conf import settings as django_settings
	return django_settings
def dynsidebars():
	""" This is a Jinja2 global function. """

	from licorn.interfaces.wmi.app import wmi_event_app

	return wmi_event_app.dynamic_sidebars
def dynstatuses():
	""" This is a Jinja2 global function. """

	from licorn.interfaces.wmi.app import wmi_event_app

	return wmi_event_app.dynamic_statuses
def dyninfos():
	""" This is a Jinja2 global function. """

	from licorn.interfaces.wmi.app import wmi_event_app

	return wmi_event_app.dynamic_infos
def dyndata_merge(data, rendered_data):
	""" A real-example: take `statuses` from `system/index_main.html` and
		merge rendered strings from dynamic_status() functions coming from
		our specific Django apps.

		The *dynamic informations* and *dynamic statuses* mechanisms work
		exactly the same. In the templates they are just used in different
		places.

		This function is a Jinja2 global.

		See `system/index_main.html` for exact use.
	"""

	for index, module_name in enumerate(data):
		try:
			if rendered_data[index] is not None:
				data[index] += rendered_data[index]

		except:
			logging.exception(_(u'No rendered data in dyndata_merge() for '
								u'index {0} but data is {1}'), index, data)

def version_html():
	return u'<p class="licorn_version">{0}</p>'.format(
				_(u'Licorn® version {0}.').format(version))

