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
from licorn.foundations             import settings as licorn_settings
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

			from licorn.interfaces.wmi.app import wmi_event_app

			q = wmi_event_app.queue(request)

			victim            = LMC.users.by_uid(kwargs.get('uid'))
			wmi_user          = LMC.users.by_login(request.user.username)
			admin_group       = LMC.groups.by_name(licorn_settings.defaults.admin_group)
			wmi_group         = LMC.groups.by_name(licorn_settings.licornd.wmi.group)
			restricted_users  = LMC.users.select(filters.SYSTEM_RESTRICTED)
			restricted_groups = LMC.groups.select(filters.SYSTEM_RESTRICTED)

			if victim in restricted_users and not request.user.is_superuser:
				# Even a staff user can't touch restricted account.
				q.put(utils.notify(_('No operation allowed on restricted '
										'system accounts.')))
				return HttpResponseForbidden('ABORTED.')

			if victim == wmi_user:
				# I'm trying to modify my own account

				if meta_action == 'delete':
					# I cannot remove my own account
					q.put(utils.notify(_('I cannot let you delete your own '
														'account captain!')))
					return HttpResponseForbidden(_('Insecure operation.'))

				elif meta_action == 'mod':
					# I can do anything except removing my own power
					if kwargs.get('action') == 'groups':
						group_id, rel_id = (int(x) for x in
											kwargs.get('value').split('/'))

						if request.user.is_staff:
							if LMC.groups.by_gid(group_id).is_privilege \
										and rel_id == relation.NO_MEMBERSHIP:
								q.put(utils.notify(_(u'You tried to remove '
													u'your own account from a '
													u'privileged group. '
													u'<strong>Operation '
													u'aborted</strong>.')))
								return HttpResponseForbidden(
													_('Insecure operation.'))

					elif kwargs.get('action') == 'lock':
						q.put(utils.notify(_(u'You tried to lock your own '
											u'account. <strong>Operation '
											u'aborted</strong>.')))
						return HttpResponseForbidden(_('Insecure operation.'))

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
						if victim in admin_group.members:
							q.put(utils.notify(_(u'You tried to alter an '
								u'account as powerful as yours. '
								u'<strong>Operation aborted</strong>.<br />'
								u'If you really want to do this, run this '
								u'operation from a CLI command.')))
							return HttpResponseForbidden(_('Operation aborted.'))

					elif request.user.is_staff:
						# if he is  >=  myself, I cannot do anything
						if victim in admin_group.members \
												or victim in wmi_group.members:
							q.put(utils.notify(_(u'You tried to do something on '
								u'an account as powerful (or even more) than '
								u'you are. <strong>Operation aborted</strong>.')))
							return HttpResponseForbidden(_('Operation aborted.'))

			# Whatever the victim is (me or another user), we check if we
			# are not adding/removing him from unwanted groups.
			if meta_action == 'mod' and kwargs.get('action') == 'groups':
				group_id, rel_id = (int(x) for x in
									kwargs.get('value').split("/"))

				# Cannot remove any `admins` account from the `admins`
				# group, even if we are `admins` ourselves.
				if request.user.is_superuser:
					if group_id == admin_group.gidNumber and \
											rel_id == relation.NO_MEMBERSHIP:
						q.put(utils.notify(_(u'You tried to remove {0} '
									u'from the <em>{1}</em> group. '
									u'<strong>Operation aborted</strong>.'
									u'<br /> If you really want to do '
									u'this, run this operation from a '
									u'CLI command.').format(
								_(u'you own account') if victim == wmi_user
								else _(u'an account as powerful as you are'),
								admin_group.name)))
						return HttpResponseForbidden(_('Operation aborted.'))

				# `staff` (eg. `licorn-wmi`) accounts cannot
				# operate on restricted system groups nor
				# promote / demote `admins`.
				elif request.user.is_staff:

					# if he is >=  myself, I cannot do anything
					if victim in admin_group.members:
						q.put(utils.notify(_(u'You tried to do something on '
											u'an account more powerful than '
											u'you are. <strong>Operation '
											u'aborted</strong>.')))
						return HttpResponseForbidden(_('Not enough permissions.'))

					elif group_id == wmi_group.gidNumber and \
											rel_id == relation.NO_MEMBERSHIP:
						q.put(utils.notify(_(u'You tried to remove {0} '
											u'from the <em>{1}</em> group. '
											u'<strong>Operation '
											u'aborted</strong>.').format(
												_(u'you own account')
													if victim == wmi_user
													else _(u'an account as '
															u'powerful (or even '
															u'more) as you are'),
												wmi_group.name)))
						return HttpResponseForbidden(_('Not enough permissions.'))

					else:
						group = LMC.groups.by_gid(group_id)

						if group == admin_group	or (
												group in restricted_groups
												and not group.is_privilege):

							q.put(utils.notify(_(u'You tried to do something on '
											u'a <em>restricted group</em> or the '
											u'<em>{0}</em>. <strong>Operation '
											u'aborted</strong>.')))
							return HttpResponseForbidden(
												_('Not enough permissions.'))

			return view_func(request, *args, **kwargs)
		return decorated
	return decorator
def check_groups(meta_action, *args, **kwargs):
	""" For more informations, see
		:func:`~licorn.interfaces.wmi.libs.decorators.check_users`. """

	def decorator(view_func):
		def decorated(request, *args, **kwargs):

			from licorn.interfaces.wmi.app import wmi_event_app

			q = wmi_event_app.queue(request)

			victim      = LMC.groups.by_gid(kwargs.get('gid'))
			admin_group = LMC.groups.by_name(licorn_settings.defaults.admin_group)
			wmi_group   = LMC.groups.by_name(licorn_settings.licornd.wmi.group)
			admins_members = set(admin_group.members + wmi_group.members)

			if victim in LMC.groups.select(filters.SYSTEM_RESTRICTED) \
											and not request.user.is_superuser:
				# Even a staff user can't touch restricted account.
				q.put(utils.notify(_('No operation allowed on restricted '
										'system accounts.')))
				return HttpResponse('ABORTED.')

			if victim == admin_group:
				if request.user.is_staff:
					# I cannot do anythiong on admins group
					q.put(utils.notify(_('You tried to touch to <em>{0}</em> '
						'group account.  <strong>Operation aborted</strong>.'
						).format(admin_group.name)))
					return HttpResponse("ABORTED")
				elif request.user.is_super_admin:
					if meta_action == 'delete':
						# I cannot remove admins group
						q.put(utils.notify(_('You tried to delete <em>{0}</em> '
						'group. <strong>Operation aborted</strong>.').format(
							admin_group.name)))
						return HttpResponse("ABORTED")

			elif victim.is_privilege:
				if meta_action == 'delete':
					# I cannot remove a privileged group
					q.put(utils.notify(_('You tried to delete the <em>privileged'
						'</em> group {0}.  <strong>Operation aborted</strong>.'
						).format(victim.name)))
					return HttpResponse("ABORTED")

			# check if we are not adding/removing admins user from any group
			if meta_action == 'mod':
				if kwargs.get('action') == 'users':
					# syntax value = "1000/1" => user_id/relation_id
					#(see groups.views.mod)
					uid = kwargs.get('value').split("/")[0]
					if LMC.users.by_uid(uid) in admins_members:
						q.put(utils.notify(_('You tried to do something on '
							'an account as powerful (or even more) than '
							'you are. <strong>Operation aborted</strong>.')))
						return HttpResponse('ABORTED.')

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


