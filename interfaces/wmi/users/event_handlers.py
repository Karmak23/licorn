# -*- coding: utf-8 -*-

from django.utils.translation     import ugettext as _
from django.template.loader       import render_to_string
from licorn.foundations.constants import filters
from licorn.interfaces.wmi.libs   import utils
from licorn.core                  import LMC

def update_user_row(user, remove=False, uid=None):
	if remove:
		return utils.format_RPC_JS('remove_instance',
								'users',
								uid
								)
	else:
		return utils.format_RPC_JS('update_instance',
								'users',
								user.uidNumber,
								render_to_string('users/user_row.html', {
									'user': user,
								}),
								"setup_row"
								)


def users_import_started_handler(request, event):
	yield utils.format_RPC_JS('body_wait', True)
	yield utils.notify(_(u'Users import started, please wait while processing…'))

def users_import_finished_handler(request, event):
	yield utils.notify(_(u'Users import completed successfully.'))
	yield utils.format_RPC_JS('reload_div', "#sub_content",
						open(event.kwargs['result_filename'], 'r').read())
	yield utils.format_RPC_JS('body_unwait', True)

def users_import_failed_handler(request, event):
	yield utils.notify(_(u'Users import <em>failed</em>: {0} (check <code>/var/log/licorn.log</code> for details).').format(event.kwargs['error']), 10000)
	yield utils.format_RPC_JS('body_unwait', True)

def users_import_tested_handler(request, event):
	yield utils.notify(_(u'Users import test ran fine.'))
	yield utils.format_RPC_JS('reload_div', "#test_result", event.kwargs['import_preview'])
	yield utils.format_RPC_JS('body_unwait', True)

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

	yield update_user_row(user)

	yield utils.format_RPC_JS('update_total_items', 'users', "/"+str(len(LMC.users)))

def user_deleted_handler(request, event):

	login  = event.kwargs['login']
	uid    = event.kwargs['uid']
	system = event.kwargs['system']

	yield utils.notify(_(u'User account "{0}" deleted from '
						u'the system.').format(login))

	yield update_user_row(None, remove=True, uid=uid)

	yield utils.format_RPC_JS('update_total_items', 'users', "/"+str(len(LMC.users)))


def user_gecos_changed_handler(request, event):

	user = event.kwargs['user']

	yield utils.notify(_(u'User account "{0}" full name has been '
						'changed to "{1}".').format(user.login, user.gecos))

	yield update_user_row(user)
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

	yield update_user_row(user)
