# -*- coding: utf-8 -*-
"""
Licorn WMI2 utils

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

import time, types, json, uuid, functools

from Queue import Queue

from licorn.foundations.ltrace  import *
from licorn.foundations.ltraces import *
from licorn.foundations         import logging, pyutils, settings

from licorn.core        import LMC, version
from decorators         import *

# NO MORE a remote app:
#from licorn.core.remote import select, select_one, CoreObjectProxy as WmiProxy

# NOW a local app:
# see in select() function.

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
	""" TODO. """

	assert ltrace_func(TRACE_DJANGO)

	return format_RPC_JS('show_message_through_notification', message, timeout or u'', css_class or u'')
def format_RPC_JS(JS_method_name, *js_arguments):

	assert ltrace_func(TRACE_DJANGO)

	return { 'method'    : JS_method_name,
						'arguments' : [ json.dumps(unicode(a)
											if type(a) == types.StringType
											else a) for a in js_arguments ] }

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
		if module_name == '':
			continue

		try:
			if rendered_data[index] is not None:
				data[index] += rendered_data[index]
		except:
			logging.exception(_(u'No rendered data in dyndata_merge() for '
								u'index {0} but data is {1}'), index, data)

def version_html():
	return u'<p class="licorn_version">{0}</p>'.format(
				_(u'Licorn® version {0}.').format(version))

