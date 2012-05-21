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

# local backup data.
import wmi_data

def extension_enabled_handler(request, event):
	if event.kwargs['extension'].name == 'rdiffbackup':
		yield utils.format_RPC_JS('add_row', 'mainnav',
								render_to_string('backup/parts/sidebar.html',
									{ 'ext': utils.WmiProxy(event.kwargs['extension']) }),
								'')
		#yield utils.format_RPC_JS('add_row', 'mainnav',
		#						render_to_string('system/parts/shutdown_all_menuitem.html'),
		#						'#shutdown_menuitem')

		#yield utils.format_RPC_JS('setup_ajaxized_links', "div.shutdown_notification > a.ajax-link")

		#yield utils.format_RPC_JS('setup_ajaxized_confirms', "div.shutdown_notification > a.ajax-link-confirm")

def extension_disabled_handler(request, event):
	# FIXME: implement some kind of 'if request.session.push == backup:' test
	# before running head_over_to() (which is also not implemented yet).
	if event.kwargs['extension'].name == 'rdiffbackup':
		yield utils.notify(_('Backup extension disabled by someone else, quitting page.'))
		yield utils.format_RPC_JS('head_over_to', '/')

def reload_main_content():
	return utils.format_RPC_JS('reload_div', "#main_content",
		render_to_string('backup/index_main.html',
			wmi_data.base_data_dict()))

def volume_enabled_handler(request, event):
	yield utils.notify(_('Volume {0} reserved for Licorn® usage.').format(event.kwargs['volume'].label))
	yield reload_main_content()

def volume_disabled_handler(request, event):
	yield utils.notify(_('Volume {0} un-reserved for Licorn® usage.').format(event.kwargs['volume'].label))
	yield reload_main_content()

def volume_added_handler(request, event):
	yield utils.notify(_('Volume {0} added on the system.').format(event.kwargs['volume'].label))
	# 'volume_mounted' should do this after this event.
	#yield reload_main_content()

def volume_removed_handler(request, event):
	yield utils.notify(_('Volume {0} removed from the system.').format(event.kwargs['volume'].label))
	yield reload_main_content()

def volume_mounted_handler(request, event):
	yield utils.notify(_('Volume {0} mounted.').format(event.kwargs['volume'].label))
	yield reload_main_content()

def volume_unmounted_handler(request, event):
	yield utils.notify(_('Volume {0} unmounted.').format(event.kwargs['volume'].label))
	yield reload_main_content()

def backup_started_handler(request, event):
	yield utils.notify(_('Backup started on volume {0}.').format(event.kwargs['volume'].label))
	yield reload_main_content()

def backup_ended_handler(request, event):
	yield utils.notify(_('Backup ended on volume {0}.').format(event.kwargs['volume'].label))
	yield reload_main_content()

def backup_statistics_started_handler(request, event):
	yield utils.notify(_('Backup statistics computation started on volume {0}.').format(event.kwargs['volume'].label))
	yield reload_main_content()

def backup_statistics_ended_handler(request, event):
	yield utils.notify(_('Backup statistics computation ended on volume {0}.').format(event.kwargs['volume'].label))
	yield reload_main_content()
