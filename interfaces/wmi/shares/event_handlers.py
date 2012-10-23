# -*- coding: utf-8 -*-

import sys, json, time

from threading import Thread, Event, current_thread
from Queue     import Queue, Empty

from django.template.loader       import render_to_string
from django.utils.translation     import ugettext as _
from licorn.foundations           import logging, options, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.messaging import MessageProcessor

from licorn.core                import LMC
from licorn.interfaces.wmi.libs import utils

import wmi_data

def reload_main_content(request):
	""" Reload only if extension is present and enabled, else this will produce
		exceptions (harmless but polluting). """

	return utils.format_RPC_JS('reload_div', "#main_content",
									render_to_string('shares/index_main.html',
										wmi_data.base_data_dict(request)))

def share_added_handler(request, event):
	# WARNING: not yet ready for production, to be refreshed.

	if request.user.username == event.kwargs.pop('share').coreobj.name:
		yield reload_main_content(request)

share_deleted_handler  = share_added_handler
share_modified_handler = share_added_handler

def share_status_changed_handler(request, event):
	# WARNING: not yet ready for production, to be refreshed.
	if request.user.username == event.kwargs.pop('user').name:
		yield reload_main_content(request)

def share_short_url_set_handler(request, event):

	share = event.kwargs.pop('share')

	if request.user.username == share.coreobj.name:
		yield utils.notify(_(u'Share “{0}” got its short URL assigned to <a '
			u'href="{1}">{2}<a>. Please reload the page to have up-to-date '
			u'informations displayed.').format(share.name, share.public_url,
				share.uri), 5000)

