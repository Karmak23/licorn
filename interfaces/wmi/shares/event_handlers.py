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

	if 'simplesharing' in LMC.extensions.keys() \
					and LMC.extensions.simplesharing.enabled:

		return utils.format_RPC_JS('reload_div', "#main_content",
									render_to_string('shares/index_main.html',
										wmi_data.base_data_dict(request)))

def share_added_handler(request, *args, **kwargs):

	if request.user.username == kwargs.pop('share').coreobj.name:
		yield reload_main_content(request)

share_deleted_handler  = share_added_handler
share_modified_handler = share_added_handler

def shares_status_changed_handler(request, *args, **kwargs):

	if request.user.username == kwargs.pop('user').name:
		yield reload_main_content(request)
