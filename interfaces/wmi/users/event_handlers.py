# -*- coding: utf-8 -*-

from django.utils.translation     import ugettext as _
from django.template.loader       import render_to_string
from licorn.foundations.constants import filters
from licorn.interfaces.wmi.libs   import utils
from licorn.core                  import LMC

def users_import_started_handler(request, event):
	if request.user.is_staff:
		yield utils.format_RPC_JS('body_wait', True)
		yield utils.notify(_(u'Users import started, please wait while processing…'))

def users_import_finished_handler(request, event):
	if request.user.is_staff:
		yield utils.notify(_(u'Users import completed successfully.'))
		yield utils.format_RPC_JS('reload_div', "#sub_content",
							open(event.kwargs['result_filename'], 'r').read())
		yield utils.format_RPC_JS('body_unwait', True)

def users_import_failed_handler(request, event):
	if request.user.is_staff:
		yield utils.notify(_(u'Users import <em>failed</em>: {0} (check <code>/var/log/licorn.log</code> for details).').format(event.kwargs['error']), 10000)
		yield utils.format_RPC_JS('body_unwait', True)

def users_import_tested_handler(request, event):
	if request.user.is_staff:
		yield utils.notify(_(u'Users import test ran fine.'))
		yield utils.format_RPC_JS('reload_div', "#test_result", event.kwargs['import_preview'])
		yield utils.format_RPC_JS('body_unwait', True)

def update_users_number(request, event):
	if request.user.is_staff:
		yield utils.format_RPC_JS('reload_div', '#users_list_count',
								len(LMC.users.select(filters.STANDARD)))

	if request.user.is_superuser:
		yield utils.format_RPC_JS('reload_div', '#sys_users_list_count',
								len(LMC.users.select(filters.SYSTEM)))

def user_added_handler(request, event):
	if request.user.is_staff:

		user = event.kwargs['user']

		yield utils.notify(_(u'User account "{0}" added on '
							u'the system.').format(user.login))

		yield utils.format_RPC_JS('add_row',
									'users' if user.is_standard else 'sys_users',
									render_to_string('users/user_row.html', {
										'item': user,
										'name': '%s' % 'users'
											if user.is_standard else 'sys_users' }))
		yield utils.format_RPC_JS('init_users_events',
									'users' if user.is_standard else 'sys_users',
									user.uid, user.login, 'uidNumber')

		for i in update_users_number(request, event):
			yield i
def user_deleted_handler(request, event):

	if request.user.is_staff:
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

	user   = event.kwargs['user']
	update = False

	if request.user.username == user.login:
		yield utils.notify(_(u'You are now known as <em>{1}</em> on this '
				u'<a href="http://licorn.org/">Licorn®</a> network.').format(
					user.login, user.gecos), 5000)

		update = True
	elif request.user.is_staff:

		yield utils.notify(_(u'User account <strong>{0}</strong> full name '
			u'is now <em>{1}<em>.').format(user.login, user.gecos))

		update = True

	if update:
		yield utils.format_RPC_JS('update_row_value',
								'users' if user.is_standard
									else 'sys_users', user.uidNumber,
								"gecos", user.gecos or _('No name given'),
								[ '-grayed_out' ] if user.gecos else [ '+grayed_out' ])

def user_userPassword_changed_handler(request, event):

	user = event.kwargs['user']
	if request.user.username == user.login:
		yield utils.notify(_(u'Your password has been successfully modified!'), 5000)

	elif request.user.is_staff:

		yield utils.notify(_(u'Password changed for user account <strong>{0}</strong>.').format(user.login))
def user_skel_applyed_handler(request, event):

	if request.user.is_staff:
		user = event.kwargs['user']
		skel = event.kwargs['skel']

		yield utils.notify(_(u'Skel <em>{1}</em> reapplyed on user account '
							u'<strong>{0}</strong>.').format(user.login, skel))
def user_loginShell_changed_handler(request, event):
	user = event.kwargs['user']

	if request.user.username == user.login:
		yield utils.notify(_(u'Your shell is now powered by <em>{0}</em>.').format(user.loginShell))

	elif request.user.is_staff:
		yield utils.notify(_(u'Shell of user account <strong>{0}</strong> '
			u'changed to <em>{1}</em>.').format(user.login, user.loginShell))
def user_locked_changed_handler(request, event):

	if request.user.is_staff:
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
