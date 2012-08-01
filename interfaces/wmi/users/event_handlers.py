# -*- coding: utf-8 -*-

from django.utils.translation     import ugettext as _
from django.template.loader       import render_to_string
from licorn.foundations.constants import filters
from licorn.interfaces.wmi.libs   import utils

def users_import_started_handler(request, event):
	yield utils.notify(_(u'Users import started, please wait while processing…'))

def users_import_finished_handler(request, event):
	yield utils.notify(_(u'Users import completed successfully.'))
	yield utils.format_RPC_JS('reload_div', "#sub_content",
						open(event.kwargs['result_filename'], 'r').read())

def users_import_failed_handler(request, event):
	yield utils.notify(_(u'Users import <em>failed</em> : {0}.').format(event.kwargs['error']), 10000)

def users_import_tested_handler(request, event):
	yield utils.notify(_(u'Users import test ran fine.'))
	yield utils.format_RPC_JS('reload_div', "#test_result", event.kwargs['import_preview'])

def update_users_number(request, event):
	yield utils.format_RPC_JS('reload_div', '#users_list_count',
								len(LMC.users.select(filters.STANDARD)))
	if request.user.is_staff:
		yield utils.format_RPC_JS('reload_div', '#sys_users_list_count',
								len(LMC.users.select(filters.SYSTEM)))

def user_added_handler(request, event):

	user = event.kwargs['user']

	yield utils.notify(_(u'User account "{0}" added on '
						u'the system.').format(user.login))

	yield utils.format_RPC_JS('add_row',
								'users' if user.is_standard else 'sys_users',
								render_to_string('users/user_row.html', {
									'item': user,
									'name': '%s' % 'users'
										if user.is_standard else 'sys_users' }))

	for i in update_users_number(request, event):
		yield i
def user_deleted_handler(request, event):

	login  = event.kwargs['login']
	uid    = event.kwargs['uid']
	system = event.kwargs['system']

	yield utils.notify(_(u'User account "{0}" deleted from '
						u'the system.').format(login))

	yield utils.format_RPC_JS('del_row', 'sys_users'
							if system else 'users', uid)

	for i in update_users_number(request, event):
		yield i
def user_gecos_changed_handler(request, event):

	user = event.kwargs['user']

	yield utils.notify(_(u'User account "{0}" full name has been '
						'changed to "{1}".').format(user.login, user.gecos))

	yield utils.format_RPC_JS('update_row_value',
								'users' if user.is_standard
									else 'sys_users', user.uidNumber,
								"gecos", user.gecos or _('No name given'),
								[ '-grayed_out' ] if user.gecos else [ '+grayed_out' ])
def user_userPassword_changed_handler(request, event):

	user = event.kwargs['user']

	yield utils.notify(_(u'Password changed for user account "{0}".').format(user.login))

def user_skel_applyed_handler(request, event):

	user = event.kwargs['user']

	yield utils.notify(_(u'Skel reapplyed for for user account "{0}".').format(user.login))

def user_loginShell_changed_handler(request, event):

	user = event.kwargs['user']

	yield utils.notify(_(u'Shell of user account "{0}" was changed to "{1}".').format(
							user.login, user.loginShell))
def user_locked_changed_handler(request, event):

	user = event.kwargs['user']

	if user.locked:
		yield utils.notify(_(u'User account "{0}" has '
							u'been locked.').format(user.login))

	else:
		yield utils.notify(_(u'User account "{0}" has '
							u'been unlocked.').format(user.login))

	yield utils.format_RPC_JS('change_locked_state',
								'users' if user.is_standard else 'sys_users',
								user.uidNumber,
								user.locked)
