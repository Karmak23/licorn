# -*- coding: utf-8 -*-

import utils
from django.shortcuts          import *
from django.utils.translation  import ugettext as _

from licorn.foundations        import settings as licorn_settings
from licorn.foundations.ltrace import *
from licorn.interfaces.wmi.app import wmi_event_app
"""
USER PERMISSIONS:
	if user is me :
		I CANNOT remove my account
		if i'm superuser:
			I CANNOT remove myself from admins group
		else:
			I CANNOT remove myself from a privileged group
	else:
		if user is more powerfull than I am:
			CANNOT do anything


GROUPS PERMISSIONS:
	if group == admins
		if I'm staff members:
			I can't do anything
		if I'm superuser:
			I can't DELETE it


	if group is privileged I cannot DELETE it
"""

def check_users(meta_action, *args, **kwargs):
	def decorator(view_func):
		def decorated(request, *args, **kwargs):

			q = wmi_event_app.queue(request)

			victim      = utils.select('users', [ kwargs.get('uid') ])[0]
			wmi_user    = utils.select('users', [request.user.username])[0]
			admin_group = utils.select('groups', [ licorn_settings.defaults.admin_group ])[0]

			if victim.login == wmi_user.login:
				#lprint("myself")
				#MYSELF
				if meta_action == 'delete':
					# I cannot remove my own account
					q.put(utils.notify(_('I cannot let you delete your own account captain !')))
					return HttpResponse()
				elif meta_action == 'mod':
					#print 'mod'
					# I can fo anything except on my power
					if kwargs.get('action') == 'groups':
						#print 'groups'
						group_id, rel_id = kwargs.get('value').split('/')
						group=utils.select('groups', [group_id])[0]
						if request.user.is_staff:
							if int(rel_id) == 0 and group.is_privilege:
								q.put(utils.notify(_('You tried to remove your own account from a privileged group. I cannot let you do that !')))
								return HttpResponse()
						elif request.user.is_superuser:

							# even if I'm a superuser, I cannot become a standard user
							if int(rel_id) == 0 and group.name == admin_group.name:
								q.put(utils.notify(_('You tried to remove your own account from {0} group. I cannot let you do that !').format(admin_group.name)))
								return HttpResponse()

					elif kwargs.get('action') == 'lock':
						# I cannot remove my own account
						q.put(utils.notify(_('I cannot let you lock your own account !')))
						return HttpResponse()
			else:
				#FIXME: don't hardcode 'licorn-wmi' here.
				admins_members = (set(u.login for u in admin_group.members)
								| set(u.login for u in utils.select('groups', ['licorn-wmi'])[0].members))


				# if I am member of admins, I can do everything !
				if request.user.is_superuser:
					pass

				# if he is more powerful or equal to myself, I cannot do anything on him
				elif request.user.is_staff:
					if victim.login in admins_members:
						q.put(utils.notify(_('You tried to do something on an account more or as powerfull than you are. I cannot let you do that !')))
						return HttpResponse()

			return view_func(request, *args, **kwargs)
		return decorated
	return decorator

def check_groups(meta_action, *args, **kwargs):
	def decorator(view_func):
		def decorated(request, *args, **kwargs):
			q = wmi_event_app.queue(request)

			victim      = utils.select('groups', [ kwargs.get('gid') ])[0]
			wmi_user    = utils.select('users', [request.user.username])[0]
			admin_group = utils.select('groups', [ licorn_settings.defaults.admin_group ])[0]

			#FIXME: don't hardcode 'licorn-wmi' here.
			admins_members = (set(u.login for u in admin_group.members)
							| set(u.login for u in utils.select('groups', ['licorn-wmi'])[0].members))


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
