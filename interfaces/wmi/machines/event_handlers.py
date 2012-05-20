# -*- coding: utf-8 -*-

from django.template.loader       import render_to_string
from django.utils.translation     import ugettext as _
from licorn.foundations.constants import host_status, host_types
from licorn.interfaces.wmi.libs   import utils

import wmi_data

def host_online_handler(request, event, reinit=False):

	# `render_to_string()` needs the host_types and host_status
	machine = event.kwargs['host']

	#print '>> host_online ', machine.mid

	yield utils.notify(_(u'New machine "{0}" found online.').format(machine.mid))

	yield utils.format_RPC_JS('add_row',
								'machines',
								render_to_string('machines/machine_row.html', {
									'item': machine,
									'name': 'machines',
									'get_host_status_html' : wmi_data.get_host_status_html,
									'get_host_os_html'     : wmi_data.get_host_os_html,
									'get_host_type_html'   : wmi_data.get_host_type_html}))

def host_back_online_handler(request, event, reinit=False):

	# `render_to_string()` needs the host_types and host_status
	machine = event.kwargs['host']

	yield utils.notify(_(u'Machine "{0}" is back online.').format(machine.hostname))

	yield utils.format_RPC_JS('update_row_value',
								'machines', machine.mid.replace('.','_'),
								"state", '<img src="/media/images/16x16/{0}" ' \
								'alt="{1}"	width="16" height="16" />'.format(
									wmi_data.get_host_status_html[machine.status][0],
									wmi_data.get_host_status_html[machine.status][1]))

def host_offline_handler(request, event, reinit=False):

	# `render_to_string()` needs the host_types and host_status
	machine = event.kwargs['host']

	#print '>> host_offline ', machine.mid

	yield utils.notify(_(u'Machine "{0}" is now offline.').format(machine.hostname))

	yield utils.format_RPC_JS('update_row_value',
								'machines', machine.mid.replace('.','_'),
								"state", '<img src="/media/images/16x16/{0}" ' \
								'alt="{1}"	width="16" height="16" />'.format(
									wmi_data.get_host_status_html[machine.status][0],
									wmi_data.get_host_status_html[machine.status][1]))

def licorn_host_online_handler(request, event, reinit=False):
	# render to string need to give host_types and host_status
	machine = event.kwargs['host']
	#print 'licorn_host_online'
	#print machine.mid

	yield utils.notify(_(u'New Licorn® machine {0} discovered.').format(machine.mid))

def licorn_host_shutdown_handler(request, event, reinit=False):
	raise NotImplementedError('TODO.')
