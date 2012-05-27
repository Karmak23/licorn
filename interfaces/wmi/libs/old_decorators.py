# -*- coding: utf-8 -*-


from django.utils.translation       import ugettext_lazy as _

from licorn.core import LMC

#FIXME: old, convert this to new:
from licorn.interfaces.wmi.libs import old_utils as w

from licorn.foundations.constants import filters
"""
USER PERMISSIONS:
		ø if members of licorn-wmi
			can do anything on him, BUT NOT:
				- strong action like delete his account,
				- remove himself from a privileged group
			can do anything on standards user
			can do nothing on admins user
		ø if members of admins:
			can do anythings, BUT NOT:
				- remove his account
				- remove himself from admins group

GROUPS PERMISSIONS:
	ø if http_user member of licorn-wmi:
		can do anything on standard group (delete/mod/add)
		can mod/add priv group but canNOT delete privileged group
		can do nothing on admins group

	ø if http_user member of admins:
		can do anything BUT cannot delete admins group
"""
def check_users(action):
	def decorator(function):

		def decorated(request, uid, *args, **kwargs):
			admin_group = LMC.groups.by_name(settings.defaults.admin_group)

			user_wmi = LMC.users.by_login(login=http_user)
			user = LMC.users.by_uid(uid)
			msg = ''

			restricted_users = LMC.users.select(filters.SYSTEM_RESTRICTED)

			if user in restricted_users:
				return (w.HTTP_TYPE_JSON_NOTIF, _(u"Impossible to do actions "
							u"on restricted users for the moment, sorry."))

			if user_wmi == user:
				#if it is my own account, check how much I'm powerfull
				if user_wmi in LMC.groups.by_name(
					settings.defaults.admin_group).members:
					# I'm member of admins
					if action == 'delete' or action == 'lock':
						msg = _(u"User {0}: Impossible to {1} your "
									u"own account!").format(user.login, action)
					elif action == 'edit_groups':
						if admin_group.is_privilege and settings.defaults.admin_group \
							not in args[0].split(','):
							msg = _(u"User {0}: Impossible to remove your "
										u"own account from group {1}!").format(
										user.login,
										settings.defaults.admin_group)

				elif user_wmi in LMC.groups.by_name(
					settings.licornd.wmi.group).members:
					# I'm member of licorn-wmi
					if action == 'delete' or action == 'lock':
						msg = _(u"User {0}: Impossible to {1} your "
							u"own account!").format(user.login, action)
					elif action == 'edit_groups':
						"""if settings.licornd.wmi.group \
							not in args[0].split(','):
								msg = _("User %s: Impossible to remove your "
									"own account from group %s!" %
									(user.login, settings.licornd.wmi.group))"""
						if settings.defaults.admin_group in \
							args[0].split(',') if len(args) != 0 else []:

							msg = _(u'You cannot modify group %s') % settings.defaults.admin_group
						for group in user.groups :
							if group.is_privilege and group.name not in args[0].split(','):
								msg = _('Impossible action, you cannot '
							'remove yourself from the privileged group %s.' % group.name)
				else:
					# I'm standard user, what am I doing here ??
					pass
			else:
				# current user is not user we are dealing with.
				# if we are members of admins we can do everything.
				if user_wmi in LMC.groups.by_name(
					settings.defaults.admin_group).members:
					pass
				elif user_wmi in LMC.groups.by_name(
					settings.licornd.wmi.group).members:

					if user in LMC.groups.by_name(
						settings.defaults.admin_group).members:
							msg = _(u'User %s: Impossible action,you cannot '
									u'do anything on member more powerfull '
									u'than you are.' % user.login)
					if action == 'edit_groups':
						if user not in LMC.groups.by_name(
							settings.defaults.admin_group).members \
							and settings.defaults.admin_group in \
							args[0].split(',') if len(args) != 0 else []:

							msg = _(u'You cannot modify group %s' %
									settings.defaults.admin_group)
					# TODO : can he do something on members of licorn-wmi

			if msg != '':
				return (w.HTTP_TYPE_JSON_NOTIF, msg)

			return function(uri, http_user, uid, *args, **kwargs)
		return decorated
	return decorator

def check_groups(action):
	def decorator(function):

		def decorated(uri, http_user, gid, *args, **kwargs):
			user_wmi = LMC.users.by_login(login=http_user)
			group = LMC.groups.by_gid(gid)
			admins_group = LMC.groups.by_name(
				settings.defaults.admin_group)
			wmi_group = LMC.groups.by_name(
				settings.licornd.wmi.group)

			restricted_groups = LMC.groups.select(filters.SYSTEM_RESTRICTED)

			if group in restricted_groups:
				return (w.HTTP_TYPE_JSON_NOTIF, _(u"Impossible to do actions "
					u"on restricted groups for the moment, sorry."))

			msg = ''

			if user_wmi in admins_group.members:
				if action == 'delete' and group == admins_group:
					msg = _(u"Group %s: Impossible to remove the admins "
							u"group!" % group.name)
			elif user_wmi in wmi_group.members:
				if group == admins_group:

					raise _(u"Group %s: You have not enought rights to do "
						u" actions on the admins group!" % group.name)
				if action == 'delete' and group.is_privilege:
					msg = _(u"Group %s: Impossible to remove a "
						u"privileged group!" % group.name)

			if msg != '':
				return (w.HTTP_TYPE_JSON_NOTIF, None)

			return function(uri, http_user, gid, *args, **kwargs)
		return decorated
	return decorator