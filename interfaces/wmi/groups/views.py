# -*- coding: utf-8 -*-
"""
Licorn® WMI - groups views

:copyright:
	* 2008-2011 Olivier Cortès <olive@deep-ocean.net>
	* 2010-2011 META IT - Olivier Cortès <oc@meta-it.fr>
	* 2011 Robin Lucbernet <robinlucbernet@gmail.com>
	* 2012 Olivier Cortès <olive@licorn.org>
:license: GNU GPL version 2
"""

import os, time, tempfile, json, csv

from django.contrib.auth.decorators import login_required
from django.shortcuts               import *
from django.template.loader         import render_to_string
from django.utils.translation       import ugettext_lazy as _

from licorn.foundations           import exceptions, logging, settings
from licorn.foundations           import hlstr
from licorn.foundations.constants import filters, relation
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core import LMC

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi.libs                import old_utils as w
from licorn.interfaces.wmi.libs.old_decorators import check_groups

from licorn.interfaces.wmi.app             import wmi_event_app
from licorn.interfaces.wmi.libs            import utils, perms_decorators
from licorn.interfaces.wmi.libs.decorators import *

from forms                              import GroupForm

@staff_only
def message(request, part, gid=None, *args, **kwargs):

	if gid != None:
		group = utils.select('groups', [ gid ])[0]

	if part == 'delete':
		html = render_to_string('groups/delete_message.html', {
			'group_name'  : group.name,
			'archive_dir' : settings.home_archive_dir,
			'admin_group' : settings.defaults.admin_group,
			})

	elif part == 'skel':
		html = render_to_string('groups/skel_message.html', {
				'group_name'        : group.name,
				'skel_name'         : group.groupSkel
			})

	return HttpResponse(html)

#@perms_decorators.check_groups('delete')
@staff_only
def delete(request, gid, no_archive='', *args, **kwargs):
	try:
		# remote:
		#LMC.rwi.generic_controller_method_call('groups', 'del_Group',
		#					group=int(gid), no_archive=bool(no_archive))

		# local:
		LMC.groups.del_Group(group=int(gid), no_archive=bool(no_archive))

	except Exception, e:
		wmi_event_app.queue(request).put(utils.notify(
			_('Error while deleting group {0}: {1}.').format(group.name, e)))

	return HttpResponse('DONE.')
@staff_only
def toogle_permissiveness(request, gid, *args, **kwargs):
	group = utils.select('groups', [ gid ])[0]
	try:
		group.is_permissive = not group.is_permissive
	except Exception, e:
		wmi_event_app.queue(request).put(utils.notify(
			_('Error while changing group permissiveness {0}: {1}.').format(
			group.name, e)))

	return HttpResponse('DONE.')
@staff_only
def massive(request, gids, action, value='', *args, **kwargs):
	if action == 'delete':
		for gid in gids.split(','):
			delete(request, gid=int(gid), no_archive=bool(value))
	elif action == 'permissiveness':
		for gid in gids.split(','):
			toogle_permissiveness(request, gid=int(gid))
	elif action == 'export':
		_type = value

		export_handler, export_filename = tempfile.mkstemp()

		if _type.lower() == 'csv':
			export = LMC.groups.get_CSV_data(selected=[ int(g) for g in gids.split(',')])

			out = csv.writer(open(export_filename,"w"), delimiter=';',quoting=csv.QUOTE_MINIMAL)
			for row in export:
				out.writerow(row)

		else:
			export = LMC.groups.to_XML(selected=[ LMC.groups.by_gid(int(g)) for g in gids.split(',')])

			
			destination = open(export_filename, 'wb+')
			for chunk in export:
				destination.write(chunk)
			destination.close()
		
		return HttpResponse(json.dumps({ "file_name" : export_filename }))

	return HttpResponse('MASSIVE DONE.')

#@perms_decorators.check_groups('mod')
@staff_only
def mod(request, gid, action, value, *args, **kwargs):
	""" edit the gecos of the user """
	assert ltrace_func(TRACE_WMI)

	group = utils.select('groups', [ gid ])[0]

	def mod_users(user_id, rel_id):

		if group.is_standard:
			g_group = group.guest_group
			r_group = group.responsible_group

		if rel_id == relation.MEMBER:
			group.add_Users(users_to_add=[user_id], force=True)

		elif rel_id == relation.GUEST:
			g_group.add_Users(users_to_add=[user_id], force=True)

		elif rel_id == relation.RESPONSIBLE:
			r_group.add_Users(users_to_add=[user_id], force=True)

		else:
			# the user has to be deleted, but from standard group or from helpers ?
			if group.get_relationship(user_id) == relation.GUEST:
				g_group.del_Users(users_to_del=[user_id])

			elif group.get_relationship(user_id) == relation.RESPONSIBLE:
				r_group.del_Users(users_to_del=[user_id])

			elif group.get_relationship(user_id) == relation.MEMBER:
				group.del_Users(users_to_del=[user_id])

	try:
		if action == 'users':
			mod_users(*[ int(x) for x in value.split('/')])

		elif action == 'description':
			if value != group.description:
				group.description = value or ''

		elif action == 'permissive':
			group.permissive = bool(value)

		elif action == 'skel':
			if value != group.groupSkel:
				group.groupSkel = value

		elif action == 'apply_skel':
			for user in group.members:
				user.apply_skel(group.groupSkel)

	except Exception, e:
		wmi_event_app.queue(request).put(utils.notify(
			_('Error while modifying group {0}: {1}.').format(
				group.name, e)))

	# updating the web page is done in the event handler, via the push stream.
	return HttpResponse('DONE.')

@staff_only
def create(request, **kwargs):
	if request.method == 'POST':

		name        = request.POST.get('name')
		permissive  = True if request.POST.get('permissive') == 'on' else False
		description = request.POST.get('description')
		groupSkel   = request.POST.get('skel')

		guest_users = [ int(u) for u in request.POST.getlist('guest_users') if u != '' ]
		std_users = [ int(u) for u in request.POST.getlist('member_users') if u != '' ]
		resp_users = [ int(u) for u in request.POST.getlist('resp_users') if u != '' ]

		try:
			# remote:
			#LMC.rwi.generic_controller_method_call('groups','add_Group',
			#	name=name, description=description,	groupSkel=groupSkel,
			#	permissive=permissive, members_to_add=std_users,
			#	guests_to_add=guest_users, responsibles_to_add=resp_users)

			# local:
			LMC.groups.add_Group(
				name=name, description=description,	groupSkel=groupSkel,
				permissive=permissive, members_to_add=std_users,
				guests_to_add=guest_users, responsibles_to_add=resp_users)

		except Exception, e:
			wmi_event_app.queue(request).put(utils.notify(_('Error while adding group {0}: {1}.').format(name, e)))

	return HttpResponse("DONE.")

@staff_only
def view(request, gid=None, name=None, *args, **kwargs):

	if gid != None:
		group = utils.select('groups', [gid])[0]

	elif name != None:
		group = utils.select('groups', [ name ])[0]

	if group.is_standard:
		lists = [{
					'title' : _('Responsibles'),
					'kind'  : _('responsible'),
					'users' : group.responsible_group.members
				},
				{
					'title' : _('Members'),
					'kind'  : _('standard'),
					'users' : group.members
				},
				{
					'title' : _('Guests'),
					'kind'  : _('guest'),
					'users' : group.guest_group.members
				}]
	else:
		lists = [{
					'title' : _('Members'),
					'kind'  : 'standard',
					'users' : group.members
				}]

	_dict = { 'group' : group, 'lists' : lists }

	if request.is_ajax():
		return render(request, 'groups/view.html', _dict)

	else:

		if request.user.is_superuser:
			_sys_groups = set(g.gidNumber for g in utils.select('groups',
								default_selection=filters.SYSTEM))
			not_resps   = set(g.gidNumber for g in utils.select('groups',
								default_selection=filters.NOT_RESPONSIBLE))
			not_guests  = set(g.gidNumber for g in utils.select('groups',
								default_selection=filters.NOT_GUEST))
			sys_groups  = utils.select('groups',
							_sys_groups.intersection(not_resps, not_guests))

		else:
			sys_groups = utils.select('groups', default_selection=filters.PRIVILEGED)

		_dict.update({
				'groups_list'            : utils.select('groups', default_selection=filters.STANDARD),
				'system_groups_list'     : sys_groups
			})

		return render(request, 'groups/view_template.html', _dict)

@staff_only
def group(request, gid=None, name= None, action='edit', *args, **kwargs):

	# resolve group
	try:
		group = utils.select('groups', [ gid ])[0]
	except IndexError:
		try:
			group = utils.select('groups', [ name ])[0]
		except IndexError:
			group = None


	if action=='edit':
		edit_mod = True
		title    = _('Edit group {0}').format(group.name)
		group_id  = group.gidNumber
	else:
		edit_mod = False
		title    = _('Add new group')
		group_id  = ''


	# get form
	f = GroupForm(edit_mod, group)

	users_list = [ (_('Standard users'),{
					'group': group,
					'name': 'standard',
					'users' : utils.select("users", default_selection=filters.STANDARD)
				}) ]

	# if super user append the system users list
	if request.user.is_superuser:
		users_list.append( ( _('System users') ,  {
			'group': group,
			'name': 'system',
			'users' : utils.select("users", default_selection=filters.SYSTEM)
		}))

	_dict = {
				'group_gid'             : group_id,
				'edit_mod'              : edit_mod,
				'title'                 : title,
				'form'                  : f,
				'users_lists'           : users_list

			}

	if request.is_ajax():
		return render(request, 'groups/group.html', _dict)

	else:

		if request.user.is_superuser:
			sys_groups = [ g for g in utils.select('groups',
							default_selection=filters.SYSTEM)
								if not g.is_helper ]
		else:
			sys_groups = utils.select('groups', default_selection=filters.PRIVILEGED)


		_dict.update({
				'groups_list'            : utils.select('groups', default_selection=filters.STANDARD),
				'system_groups_list'     : sys_groups})

		return render(request, 'groups/group_template.html', _dict)

@staff_only
def main(request, sort="login", order="asc", select=None, *args, **kwargs):

	groups = utils.select('groups', default_selection=filters.STANDARD)


	if request.user.is_superuser:
		sys_groups = [ g for g in utils.select('groups',
							default_selection=filters.SYSTEM)
								if not g.is_helper ]
	else:
		sys_groups = utils.select('groups', default_selection=filters.PRIVILEGED)

	return render(request, 'groups/index.html', {
			'groups_list' : groups,
			'system_groups_list' : sys_groups,
		})
