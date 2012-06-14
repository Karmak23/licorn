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
from licorn.foundations.constants   import filters
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
# for more explanations, see http://dev.licorn.org/wiki/LicornPermissions
def check_users(meta_action, *args, **kwargs):
	def decorator(view_func):
		def decorated(request, *args, **kwargs):

			from licorn.interfaces.wmi.app import wmi_event_app

			q = wmi_event_app.queue(request)

			victim      = LMC.users.by_uid(kwargs.get('uid'))
			wmi_user    = LMC.users.by_login(request.user.username)
			admin_group = LMC.groups.by_name(licorn_settings.defaults.admin_group)
			wmi_group   = LMC.groups.by_name(licorn_settings.licornd.wmi.group)

			if victim in LMC.users.select(filters.SYSTEM_RESTRICTED) \
											and not request.user.is_superuser:
				# Even a staff user can't touch restricted account.
				q.put(utils.notify(_('No operation allowed on restricted '
										'system accounts.')))
				return HttpResponse('ABORTED.')

			if victim == wmi_user:
				if meta_action == 'delete':
					# I cannot remove my own account
					q.put(utils.notify(_('I cannot let you delete your own '
														'account captain!')))
					return HttpResponse('ABORTED.')

				elif meta_action == 'mod':

					# I can do anything except removing my own power
					if kwargs.get('action') == 'groups':
						group_id, rel_id = (int(x) for x in kwargs.get('value').split('/'))
						group            = LMC.groups.by_gid(group_id)

						if request.user.is_superuser:

							# If I'm a superuser, I cannot become a standard user
							# FIXME: WHERE TO FIND DOCUMENTATION ABOUT REL_ID ??
							if rel_id == 0 and group == admin_group:
								q.put(utils.notify(_('You tried to remove '
													'your own account from the '
													'<em>{0}</em> group. '
													'<strong>Operation '
													'aborted</strong>.').format(
														admin_group.name)))
								return HttpResponse('ABORTED.')

						elif request.user.is_staff:
							if rel_id == 0 and group.is_privilege:
								q.put(utils.notify(_('You tried to remove '
										'your own account from a privileged '
										'group. <strong>Operation '
										'aborted</strong>.')))
								return HttpResponse('ABORTED.')

					elif kwargs.get('action') == 'lock':
						q.put(utils.notify(_('You tried to lock your own '
											'account.<strong>Operation '
											'aborted</strong>.')))
						return HttpResponse('ABORTED.')
			else:
				admins_members = set(admin_group.members + wmi_group.members)

				if request.user.is_superuser:
					if victim in admin_group.members:
						q.put(utils.notify(_('You tried to alter an account '
							'as powerful as yours. <strong>Operation '
							'aborted</strong>.<br />If you really want to do '
							'it, run this operation from a CLI command.')))
						return HttpResponse('ABORTED.')

				# if he is  >=  myself, I cannot do anything
				elif request.user.is_staff:
					if victim in admins_members:
						q.put(utils.notify(_('You tried to do something on '
							'an account as powerful (or even more) than '
							'you are. <strong>Operation aborted</strong>.')))
						return HttpResponse('ABORTED.')

			return view_func(request, *args, **kwargs)
		return decorated
	return decorator
def check_groups(meta_action, *args, **kwargs):
	def decorator(view_func):
		def decorated(request, *args, **kwargs):

			from licorn.interfaces.wmi.app import wmi_event_app

			q = wmi_event_app.queue(request)

			victim      = utils.select('groups', [ kwargs.get('gid') ])[0]
			wmi_user    = utils.select('users', [request.user.username])[0]
			admin_group = utils.select('groups', [ licorn_settings.defaults.admin_group ])[0]

			#FIXME: don't hardcode 'licorn-wmi' here.
			admins_members = (set(u.login for u in admin_group.members)
							| set(u.login for u in utils.select('groups', ['licorn-wmi'])[0].members))

			# FIXME: restricted system groups from old_decorators.

			if victim.name == admin_group.name:
				if request.user.is_staff:
					# I cannot do anythiong on admins group
					q.put(utils.notify(_('I cannot let you do anything on {0} group !').format(admin_group.name)))
					return HttpResponse()
				elif request.user.is_super_admin:
					if meta_action == 'delete':
						# I cannot remove admins group
						q.put(utils.notify(_('I cannot let you delete {0} group !').format(admin_group.name)))
						return HttpResponse()

			elif victim.is_privilege:
				if meta_action == 'delete':
					# I cannot remove a privileged group
					q.put(utils.notify(_('You cannot delete privileged group {0} !').format(victim.name)))
					return HttpResponse()

			# check if we are not adding/removing admins user from group
			if meta_action == 'mod':
				if kwargs.get('action') == 'users':
					# syntax value = "1000/1" => user_id/relation_id (see groups.views.mod)
					uid = kwargs.get('value').split("/")[0]
					if utils.select('users', [ uid ])[0].login in admins_members:
						q.put(utils.notify(_('You tried to do something on an account more or as powerfull than you are. I cannot let you do that !')))
						return HttpResponse()


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


