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
from licorn.foundations.styles      import *
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
							admin_group, wmi_group, wmi_user):
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
		if target_user.is_system:
			return forbidden(_(u'No operation allowed on {0} system '
				u'accounts.').format(_('restricted')
					if target_user.is_system_restricted else u''))

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
									target_group.is_system
									and not (target_group.is_privilege
											or target_group.is_helper)):
				return forbidden(_(u'Insufficient permissions to '
					u'alter the {0} group <em>{1}</em>.').format(
						_('administrator')
							if target_group == admin_group
							else _('{0} system').format(
								_('restricted')
									if target_group.is_system_restricted
									else u''),
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

				if not request.user.is_staff:
					# Standard users can't do anything except some rare
					# modifications on their own account. But they can
					# reach the current decorator because they have access
					# to 'users.views.mod()' in that case. If they are
					# trying to do something prohibited, someone should be
					# told, because they can't do it without forging URLs,
					# thus the action is voluntary and possibly evil.

					logging.warning(_(u'{0}: user {1} tried to alter '
							u'account {2} with WMI action {3}!').format(
								stylize(ST_BAD, _('POSSIBLE BREAKIN ATTEMPT')),
								stylize(ST_LOGIN, wmi_user.login),
								stylize(ST_LOGIN, victim_user.login),
								stylize(ST_BAD, '%s(args=%s, kwargs=%s)'
									% (meta_action, args, kwargs))
							)
						)

				utils.notification(request, message)
				return HttpResponseForbidden(message)

			victim_user       = LMC.users.by_uid(kwargs.get('uid'))
			admin_group       = LMC.groups.by_name(lsettings.defaults.admin_group)
			wmi_group         = LMC.groups.by_name(lsettings.licornd.wmi.group)
			wmi_user          = LMC.users.by_login(request.user.username)

			# NOTE: when selecting SYSTEM users simply like this, the
			#		result contains SYSTEM_RESTRICTED users too. Thus,
			#		the RESTRICTED must be tested / enforced *before*
			#		the SYSTEM, else the forbidden reason will not be
			#		forcibly good.

			if victim_user.is_system_restricted and not request.user.is_superuser:
				# Even a staff user can't touch restricted account.
				return forbidden(_(u'No operation allowed on '
										u'restricted system accounts.'))

			# Testing 'is_staff' is not good, because superusers are staff too,
			# and this would disallow them to modify system accounts.
			if victim_user.is_system and not request.user.is_superuser:
				# And staff cannot touch any [non-restricted] system accounts.
				return forbidden(_(u'No operation allowed on system accounts.'))

			if victim_user == wmi_user:
				# I'm trying to modify my own account

				if meta_action == 'delete':
					# I cannot remove my own account
					return forbidden(_(u'Impossible to delete your own '
														u'account, captain!'))

				elif meta_action == 'mod':
					local_action = kwargs.get('action')
					# I can do anything except removing my own power, but even
					# only if I'm not a standard user
					if local_action == 'groups':
						group_id, rel_id = (int(x) for x in
											kwargs.get('value').split('/'))

						if not request.user.is_superuser:
							if LMC.groups.by_gid(group_id) == wmi_group \
										and rel_id == relation.NO_MEMBERSHIP:
								return forbidden(_(u'Impossible to demote your '
												u'own account to standard user '
												u', captain!'))

						if not request.user.is_staff:
							# standard users can use 'mod()' to alter their
							# attributes, but not all of them. A standard user
							# can't change any of his groups.
							return forbidden(_(u'Insufficient permissions to '
												u'alter your own account.'))

					elif local_action == 'lock':
						return forbidden(_(u'Impossible to lock your own '
														u'account, captain!'))

					elif local_action == 'unlock':
						# in theory, the user shouldn't be able to come here
						# if his account is already locked, but we never know.
						if not request.user.is_superuser:
							return forbidden(_(u'Insufficient permissions to '
											u'unlock your own account.'))

					elif local_action not in ('gecos', 'skel', 'shell', 'password'):
						# standard users
						return forbidden(_(u'Insufficient permissions to '
											u'alter your own account.'))

					# implicit: else:
					# all other actions are permitted on my own account.
			else:
				# The victim is not myself but another account. Managers and
				# Administrators can't do harmfull operations on them, nor
				# change their password or gecos (anything, in fact ?).
				# Only group modifications are permitted, and handled later
				# with a common checker for users and groups.

				if not request.user.is_staff:
					# First and very important: standard users have nothing
					# to do here. forbidden() will add a warning() in the log.
					return forbidden(_(u'Insufficient permissions.'))

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
										admin_group, wmi_group, wmi_user)
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
			system_users      = LMC.users.select(filters.SYSTEM)
			system_groups     = LMC.groups.select(filters.SYSTEM)
			needed_groups     = (LMC.groups.by_name(x)
									for x in (LMC.configuration.users.group,
											LMC.configuration.acls.group))

			if (victim_group.is_system_restricted
				and not victim_group.is_privilege) \
											and not request.user.is_superuser:
				# Even a staff user can't touch restricted groups.
				return forbidden(_(u'No operation allowed on restricted '
									u'system groups.'))

			# Testing 'is_staff' is not good, because superusers are staff too,
			# and this would disallow them to modify system accounts.
			if victim_group.is_system \
									and not request.user.is_superuser \
									and not (victim_group.is_helper
											or victim_group.is_privilege):
				# and staff can only touch helper groups, not any system group.
				return forbidden(_(u'No operation allowed on non-helpers '
									u'system groups.'))

			if victim_group == admin_group or \
									victim_group.is_system:

				group_name_string = _('the administrators groups') \
								if victim_group == admin_group \
								else _('the <strong>{0}</strong> {1}'
									).format(victim_group.name, _('privilege')
										if victim_group.is_privilege
										else _('{0} system group').format(
											_('restricted')
												if victim_group.is_system_restricted
												else u'helper'))

				if meta_action == 'delete':
					# no-one can remove these special group (at least from
					# the WMI). For helper groups, 'delete' is already covered
					# by the `core` code, but wrapping them here makes the user
					# experience much better than an Http500 triggered by a
					# daemon-side exception.
					if not request.user.is_superuser or (
										victim_group == admin_group
										or victim_group == wmi_group
										or victim_group.is_helper
										or victim_group.is_system_restricted
										or victim_group in needed_groups):
						return forbidden(_(u'Removing {0} is strongly '
											u'not recommended.{1}').format(
												group_name_string,
												_(u' If you really want to '
													u'shoot yourself in the '
													u'foot, use the CLI.')
												if request.user.is_superuser
												else u''))

				elif meta_action == 'mod' \
										and kwargs.get('action') != 'users':

					if not request.user.is_superuser:
						# `licorn-wmi` cannot do anything on `admins` group.
						return forbidden(_(u'Insufficient permissions to alter '
											u'{0}.').format(group_name_string))

			# check if we are not adding/removing admins user from any group
			if meta_action == 'mod' and kwargs.get('action') == 'users':
					user_id, rel_id = (int(x) for x in
										kwargs.get('value').split("/"))

					is_forbidden = check_mod_users_groups(request,
											LMC.users.by_uid(user_id),
											victim_group, rel_id,
											admin_group, wmi_group, wmi_user)
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
