# -*- coding: utf-8 -*-
"""
Licorn WMI2 decorators

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>
	* partial 2011 Robin Lucbernet <robinlucbernet@gmail.com>

:license: GNU GPL version 2
"""

import functools, Pyro, time
from threading import current_thread

from django.utils.translation       import ugettext as _
from django.contrib.auth.decorators import login_required
from django.http                    import HttpResponse, HttpResponseForbidden
from django.utils                   import simplejson

from licorn.foundations             import logging, pyutils
from licorn.foundations             import settings as lsettings
from licorn.foundations.ltrace      import *
from licorn.foundations.constants   import filters, relation
from licorn.core                    import LMC


# local imports
import utils

def superuser_only(func):
	""" Send an HTTP error 403 if the current logged in user is not superuser.
	"""

	@login_required
	@functools.wraps(func)
	def decorated(request, *args, **kwargs):

		if not request.user.is_superuser:
			return HttpResponseForbidden()

		return func(request, *args, **kwargs)

	return decorated
def staff_only(func):
	""" Send an HTTP error 403 if the current logged in user is not a staff member.
	"""

	@login_required
	@functools.wraps(func)
	def decorated(request, *args, **kwargs):

		if not request.user.is_staff:
			return HttpResponseForbidden()

		return func(request, *args, **kwargs)

	return decorated

#===================================================== fine grained permissions
def check_mod_users_groups(request, target_user, target_group, rel_id,
							admin_group, wmi_group, wmi_user,
							restricted_users, restricted_groups):
	""" Internal function which contains common checks to users and groups
		modifications.

		Returns either an `HttpResponseForbidden`, or ``None``
		(by not returning anything) if there is no problem in the
		checked operation.
	"""

	def forbidden(message):
		""" helper function for check_* decorators. """
		utils.notification(request, message)
		return HttpResponseForbidden(message)

	# Cannot remove any `admins` account from the `admins`
	# group, even if we are `admins` ourselves.
	if request.user.is_superuser:
		if target_user in admin_group.members \
						 and target_group == admin_group \
						 and rel_id == relation.NO_MEMBERSHIP:
			return forbidden(_(u'Insufficient permissions to '
						u'remove <strong>{0}</strong> from '
						u'the <em>{1}</em> group. If you '
						u'really want to, use the CLI.').format(
							_(u'you own account')
								if target_user == wmi_user
								else _(u'administrator account <strong>{0}</strong>'
											).format(target_user.login),
							admin_group.name))

	# `staff` (eg. `licorn-wmi`) accounts cannot
	# operate on restricted system groups nor
	# promote / demote `admins`.
	elif request.user.is_staff:
		if target_user in admin_group.members:
			# if he is >=  myself, I cannot do anything
			return forbidden(_(u'Insufficient permissions to alter '
							u'administrator account <strong>{0}</strong>.'
								).format(target_user.login))

		elif target_user in wmi_group.members \
							and target_group == wmi_group \
							and rel_id == relation.NO_MEMBERSHIP:
			return forbidden(_(u'Insufficient permissions to remove '
								u'<strong>{0}</strong> from the '
								u' <em>{1}</em> group.').format(
									_(u'you own account')
										if target_user == wmi_user
										else _(u'manager account '
											u'{0}').format(
												target_user.login),
									wmi_group.name))

		else:
			if target_group == admin_group or (
									target_group in restricted_groups
									and not target_group.is_privilege):

				return forbidden(_(u'Insufficient permissions to '
					u'alter the {0} group <em>{1}</em>.').format(
						_('administrator')
							if target_group == admin_group
							else _('restricted system'),
						target_group.name))

def check_users(meta_action, *args, **kwargs):
	""" Make various checks against "shooting myself or my friends in the foot"
		classic human errors, which can arise in the WMI because everything
		is so much easy than in the CLI.

		For detailled informations about what this decorator checks, see
		the specification: http://dev.licorn.org/wiki/LicornPermissions

		.. note:: the ``rel_id`` (relationships) only exists in the WMI. For
			more informations, see the
			:func:`~licorn.interfaces.wmi.users.views.mod` function. Basic
			syntax for relationships is "<object_id>/<relationship_id>".

		.. versionadded:: 1.3.1. Permissions decorators existed before, but
			they have been deactivated between the 1.2 and 1.3 development
			cycles because we had no time to port them.
"""
	def decorator(view_func):
		def decorated(request, *args, **kwargs):

			def forbidden(message):
				""" helper function for check_* decorators. """
				utils.notification(request, message)
				return HttpResponseForbidden(message)

			victim_user       = LMC.users.by_uid(kwargs.get('uid'))
			admin_group       = LMC.groups.by_name(lsettings.defaults.admin_group)
			wmi_group         = LMC.groups.by_name(lsettings.licornd.wmi.group)
			wmi_user          = LMC.users.by_login(request.user.username)
			restricted_users  = LMC.users.select(filters.SYSTEM_RESTRICTED)
			restricted_groups = LMC.groups.select(filters.SYSTEM_RESTRICTED)

			if victim_user in restricted_users and not request.user.is_superuser:
				# Even a staff user can't touch restricted account.
				return forbidden(_(u'No operation allowed on '
										u'restricted system accounts.'))

			if victim_user == wmi_user:
				# I'm trying to modify my own account

				if meta_action == 'delete':
					# I cannot remove my own account
					return forbidden(_(u'Impossible to delete your own '
														u'account, captain!'))

				elif meta_action == 'mod':
					# I can do anything except removing my own power
					if kwargs.get('action') == 'groups':
						group_id, rel_id = (int(x) for x in
											kwargs.get('value').split('/'))

						if request.user.is_staff:
							if LMC.groups.by_gid(group_id).is_privilege \
										and rel_id == relation.NO_MEMBERSHIP:
								return forbidden(_(u'Impossible to remove your '
												u'own account from a privileged '
												u'group, captain!'))

					elif kwargs.get('action') == 'lock':
						return forbidden(_(u'Impossible to lock your own '
														u'account, captain!'))

			else:
				# The victim is not myself but another account. We can't delete
				# or lock them, nor change their password or gecos (anything,
				# in fact). Only group modifications are handled later.

				if meta_action == 'delete' or (meta_action == 'mod'
										and kwargs.get('action') != 'groups'):

					# Check if the victim is some kind of admin account.
					# If then, the user cannot do anything on sibling accounts,
					# only on lower: eg `admins` can alter `licorn-wmi` but not
					# other `admins`, and `licorn-wmi` can alter only standard
					# user accounts.

					if request.user.is_superuser:
						# `admins` users can do anything, but we prefer them to
						# battle in CLI. WMI is a peaceful place.
						if victim_user in admin_group.members:
							return forbidden(_(u'Insufficient permissions '
									u'to alter <em>administrator</em> account '
									u'<strong>{0}</strong>. If you really '
									u'want to, use the CLI.').format(
										victim_user.login))

					elif request.user.is_staff:
						err = False
						# if he is  >=  myself, I cannot do anything
						if victim_user in admin_group.members:
							typ = _('administrator')
							err = True

						elif victim_user in wmi_group.members:
							typ = _('manager')
							err = True

						if err:
							return forbidden(_(u'Insufficient permissions to '
											u'alter <em>{0}</em> account '
											u' <strong>{1}</strong>.').format(
												typ, victim_user.login))

			# Whatever the victim is (me or another user), we check if we
			# are not adding/removing him from unwanted groups.
			if meta_action == 'mod' and kwargs.get('action') == 'groups':
				group_id, rel_id = (int(x) for x in
									kwargs.get('value').split("/"))

				is_forbidden = check_mod_users_groups(request, victim_user,
										LMC.groups.by_gid(group_id), rel_id,
										admin_group, wmi_group, wmi_user,
										restricted_users, restricted_groups)

				if is_forbidden:
					return is_forbidden

			return view_func(request, *args, **kwargs)
		return decorated
	return decorator
def check_groups(meta_action, *args, **kwargs):
	""" For more informations, see
		:func:`~licorn.interfaces.wmi.libs.decorators.check_users`. """

	def decorator(view_func):
		def decorated(request, *args, **kwargs):

			def forbidden(message):
				""" helper function for check_* decorators. """
				utils.notification(request, message)
				return HttpResponseForbidden(message)

			victim_group      = LMC.groups.by_gid(kwargs.get('gid'))
			admin_group       = LMC.groups.by_name(lsettings.defaults.admin_group)
			wmi_group         = LMC.groups.by_name(lsettings.licornd.wmi.group)
			wmi_user          = LMC.users.by_login(request.user.username)
			restricted_users  = LMC.users.select(filters.SYSTEM_RESTRICTED)
			restricted_groups = LMC.groups.select(filters.SYSTEM_RESTRICTED)
			system_groups     = LMC.groups.select(filters.SYSTEM)

			if (victim_group in restricted_groups
				and not victim_group.is_privilege) \
											and not request.user.is_superuser:
				# Even a staff user can't touch restricted groups.
				return forbidden(_(u'No operation allowed on restricted '
									u'system groups.'))

			if victim_group in system_groups \
					and not (
					(victim_group.is_helper or victim_group.is_privilege)
					and request.user.is_staff):
				# and staff can only touch helper groups, not any system group.
				return forbidden(_(u'No operation allowed on non-helpers '
									u'system groups.'))

			if victim_group == admin_group or victim_group.is_privilege:

				group_name_string = _('the administrators groups') \
								if victim_group == admin_group \
								else _('the <strong>{0}</strong> privilege'
									).format(victim_group.name)

				if meta_action == 'delete':
					# no-one can remove admins group nor privileges
					return forbidden(_(u'Removing {0} is strongly '
										u'not recommended.{1}').format(
											group_name_string,
											_(u' If you really '
												u'want to, use the CLI.')
												if request.user.is_superuser
												else u''))

				elif meta_action == 'mod' \
										and kwargs.get('action') != 'users':

					if not request.user.is_superuser:
						# `licorn-wmi` cannot do anything on `admins` group.
						return forbidden(_(u'Insufficient permissions to alter '
											u'{0}.').format(group_name_string))

			elif victim_group.is_helper:
				# 'delete' is already covered by the CORE code, but covering it
				# here makes the whole client experience better than a crash.
				if meta_action == 'delete':
					# no-one can remove admins group nor privileges
					return forbidden(_(u'Removing helper group '
										u'<strong>{0}</strong> is '
										u'not possible.').format(
											victim_group.name))

				elif meta_action == 'mod' \
										and kwargs.get('action') != 'users':

					if not request.user.is_superuser:
						# `licorn-wmi` cannot do anything on `admins` group.
						return forbidden(_(u'Insufficient permissions to alter '
											u'helper group '
											u'<strong>{0}</strong>.').format(
												victim_group.name))

			# check if we are not adding/removing admins user from any group
			if meta_action == 'mod' and kwargs.get('action') == 'users':
					user_id, rel_id = (int(x) for x in
										kwargs.get('value').split("/"))

					is_forbidden = check_mod_users_groups(request,
											LMC.users.by_uid(user_id),
											victim_group, rel_id,
											admin_group, wmi_group, wmi_user,
											restricted_users, restricted_groups)

					if is_forbidden:
						return is_forbidden

			return view_func(request, *args, **kwargs)
		return decorated
	return decorator
def json_view(func):
	def wrap(*a, **kw):
		#try:
		response = func(*a, **kw)
		#assert isinstance(response, dict)
		#if 'result' not in response:
		#	response['result'] = 'ok'
		"""
		except KeyboardInterrupt:
			# Allow keyboard interrupts through for debugging.
			raise
		except Exception, e:
			# Mail the admins with the error
			exc_info = sys.exc_info()
			subject = 'JSON view error: %s' % request.path
			try:
				request_repr = repr(request)
			except:
				request_repr = 'Request repr() unavailable'
			import traceback
			message = 'Traceback:\n%s\n\nRequest:\n%s' % (
				'\n'.join(traceback.format_exception(*exc_info)),
				request_repr,
				)
			mail_admins(subject, message, fail_silently=True)

			# Come what may, we're returning JSON.
			if hasattr(e, 'message'):
				msg = e.message
			else:
				msg = _('Internal error')+': '+str(e)
			response = {'result': 'error',
						'text': msg}
		"""
		json = simplejson.dumps(response)
		return HttpResponse(json, mimetype='application/json')
	return wrap

__all__ = ('superuser_only', 'staff_only', 'check_users', 'check_groups',
			'json_view')
