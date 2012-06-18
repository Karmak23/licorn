# -*- coding: utf-8 -*-
"""
Licorn WMI2 system event handlers

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

import time, itertools

from django.template.loader       import render_to_string
from django.utils.translation     import ugettext as _
from licorn.interfaces.wmi.libs   import utils
from licorn.interfaces.wmi.system import wmi_data

from views import view_groups
from licorn.foundations.constants     import relation

def daemon_is_restarting_handler(request, event, *args, **kwargs):
	yield utils.notify(_(u'Licorn® daemon is restarting in the background. '
						u'You will not be able to do anything in this '
						u'interface until it is back to normal.'),
						20000, 'daemon_is_restarting')

def shutdown_started_handler(request, event, *args, **kwargs):

	yield utils.notify(render_to_string('system/parts/shutdown_notification.html',
						{ 'reboot': event.kwargs['reboot'], 'uuid': utils.unique_hash('_') }),
						# display the notification for 55 seconds (default shutdown delay is 1 minute)
						55000,
						# put it a CSS class to be able to remove it easily
						# in case of a shutdown-cancelled operation.
						'shutdown_notification')

	yield utils.format_RPC_JS('setup_ajaxized_links', "div.shutdown_notification > a.ajax-link")

	yield utils.format_RPC_JS('setup_ajaxized_confirms', "div.shutdown_notification > a.ajax-link-confirm")

def shutdown_cancelled_handler(request, event, *args, **kwargs):

	yield utils.notify(_(u'System restart/shudown cancelled.'))

	# we need to sleep to avoid a race where shutdown notification
	# is not yet built on client side.
	time.sleep(0.01)

	yield utils.format_RPC_JS('remove_notification', "shutdown_notification")

def licorn_host_online_handler(request, event, *args, **kwargs):

	reinit = kwargs.pop('reinit', False)

	if not reinit:
		wmi_data.licorn_hosts_online += 1

	if request.user.is_staff and (
					(reinit and wmi_data.licorn_hosts_online >= 1)
					or wmi_data.licorn_hosts_online == 1):
		yield utils.format_RPC_JS('add_row', 'mainnav',
								render_to_string('system/parts/shutdown_all_menuitem.html'),
								'#shutdown_menuitem')
		yield utils.format_RPC_JS('add_row', 'mainnav',
								render_to_string('system/parts/restart_all_menuitem.html'),
								'#restart_menuitem')

		# make the new entries clickable like others, with confirm, ajax, etc
		# NOTE: without any arguments, these functions work on the sidebar menu,
		# which is exactely what we want.
		yield utils.format_RPC_JS('setup_ajaxized_links')
		yield utils.format_RPC_JS('setup_ajaxized_confirms')

def licorn_host_shutdown_handler(request, event, *args, **kwargs):

	reinit = kwargs.pop('reinit', False)

	if not reinit:
		wmi_data.licorn_hosts_online -= 1

	if request.user.is_staff and (reinit or wmi_data.licorn_hosts_online < 1):
		yield utils.format_RPC_JS('del_row', 'mainnav', 'shutdown_all_menuitem')
		yield utils.format_RPC_JS('del_row', 'mainnav', 'restart_all_menuitem')

def wmi_starts_handler(request, event):
	yield utils.notify(_(u'Licornd successfully started; Rock\'n Roll again ;-)'))
	# we need to sleep to avoid a race where restart notification
	# is not yet built on client side.
	time.sleep(0.01)

	yield utils.format_RPC_JS('remove_notification', 'daemon_is_restarting')



# NO STAFF 
def group_member_added_handler(request, event, *args, **kwargs):
	# if this is the currently user logged in the wmi
	user = event.kwargs['user']
	if str(request.user) == str(user.login):
		yield utils.format_RPC_JS('reload_div', '#table_my_groups', view_groups(request))

def group_member_deleted_handler(request, event):
	user = event.kwargs['user']
	if str(request.user) == str(user.login):
		yield utils.format_RPC_JS('reload_div', '#table_my_groups', view_groups(request))
