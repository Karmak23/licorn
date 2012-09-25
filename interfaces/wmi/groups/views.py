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

import os, time, tempfile, json, csv, types
from operator import attrgetter
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers       import reverse
from django.shortcuts               import *
from django.template.loader         import render_to_string
from django.utils.translation       import ugettext_lazy as _
from django.http					import HttpResponse, \
											HttpResponseForbidden, \
											HttpResponseNotFound, \
											HttpResponseRedirect

from licorn.foundations           import exceptions, logging, settings
from licorn.foundations           import hlstr
from licorn.foundations.constants import filters, relation
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core import LMC

from collections import OrderedDict

# FIXME: OLD!! MOVE FUNCTIONS to new interfaces.wmi.libs.utils.
# WARNING: this import will fail if nobody has previously called `wmi.init()`.
# This should have been done in the WMIThread.run() method. Anyway, this must
# disappear soon!!
from licorn.interfaces.wmi.libs            import old_utils as w

from licorn.interfaces.wmi.app             import wmi_event_app
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import staff_only, check_groups

from forms import GroupForm, get_group_form_blocks

@staff_only
@check_groups('delete')
def delete(request, gid, no_archive='', *args, **kwargs):
	try:
		# remote:
		#LMC.rwi.generic_controller_method_call('groups', 'del_Group',
		#					group=int(gid), no_archive=bool(no_archive))

		# local:
		LMC.groups.del_Group(group=int(gid), no_archive=bool(no_archive))

	except Exception, e:
		utils.wmi_exception(request, e, _(u'Error while deleting group {0}'),
												LMC.groups.by_gid(gid).name)
	else:
		return HttpResponse('DELETED.')

@staff_only
def toggle_permissiveness(request, gid, *args, **kwargs):

	group = LMC.groups.by_gid(gid)

	try:
		group.is_permissive = not group.is_permissive

	except Exception, e:
		utils.wmi_exception(request, e, _(u'Error while changing group '
			u'<strong>{0}</strong> permissiveness'), group.name)

	return HttpResponse('DONE.')

@staff_only
def massive(request, gids, action, value='', *args, **kwargs):

	if action == 'delete':
		for gid in gids.split(','):
			delete(request, gid=int(gid), no_archive=bool(value))

	elif action == 'permissivness':
		for gid in gids.split(','):
			toggle_permissiveness(request, gid=int(gid))

	elif action == 'export':
		_type = value

		export_handler, export_filename = tempfile.mkstemp()

		if _type.lower() == 'csv':
			export = LMC.groups.get_CSV_data(selected=[int(g)
													for g in gids.split(',')])

			out = csv.writer(open(export_filename, 'w'),
								delimiter=';', quoting=csv.QUOTE_MINIMAL)
			for row in export:
				out.writerow(row)

		else:
			export = LMC.groups.to_XML(selected=[LMC.groups.by_gid(int(g))
													for g in gids.split(',')])

			destination = open(export_filename, 'wb+')
			for chunk in export:
				destination.write(chunk)
			destination.close()

		return HttpResponse(json.dumps({ "file_name" : export_filename }))
	
	elif action == 'skel':
		# massively mod shell
		for gid in gids.split(','):
			mod(request, gid=gid, action='skel', value=value)
	elif action == 'apply_skel':
		# massively apply shell
		for gid in gids.split(','):
			mod(request, gid=gid, action='apply_skel', value=None)
	elif action == 'users':
		print "mod users ",gids, value
		for gid in gids.split(','):
			mod(request, gid=gid, action='users', value=value)
			# group is : group_id/rel_id
	elif action == 'edit':
		groups = []
		for gid in gids.split(','):
			groups.append(LMC.groups.guess_one(gid))

		return get_group_template(request, "massiv", groups)

	return HttpResponse('MASSIVE')

@staff_only
@check_groups('mod')
def mod(request, gid, action, value, *args, **kwargs):
	""" edit the gecos of the user """
	assert ltrace_func(TRACE_WMI)

	group = LMC.groups.by_gid(gid)

	def mod_users(group, user_id, rel_id):

		# Allow direct modifications of helper groups via URLs by
		# swapping the helper group and its standard one, and
		# swapping the desired membership accordingly.
		if group.is_helper:
			if rel_id == relation.MEMBER:
				rel_id = relation.RESPONSIBLE \
							if group.is_responsible \
							else relation.GUEST
			group = group.standard_group

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
			mod_users(group, *(int(x) for x in value.split('/')))

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
		utils.wmi_exception(request, e, _(u'Error while modifying group '
										u'<strong>{0}</strong>'), group.name)

	# updating the web page is done in the event handler, via the push stream.
	return HttpResponse('MOD DONE.')

@staff_only
def create(request, **kwargs):
	if request.method == 'POST':

		name        = request.POST.get('name')
		permissive  = False if request.POST.get('permissive') == 'on' else True
		description = request.POST.get('description')
		groupSkel   = request.POST.get('skel')

		try:
			# remote:
			#LMC.rwi.generic_controller_method_call('groups','add_Group',
			#	name=name, description=description,	groupSkel=groupSkel,
			#	permissive=permissive, members_to_add=std_users,
			#	guests_to_add=guest_users, responsibles_to_add=resp_users)

			# local:
			group = LMC.groups.add_Group(
				name=name, description=description,	groupSkel=groupSkel,
				permissive=permissive,
				# We don't use these directly, to avoid #771.
				#members_to_add=std_users,
				#guests_to_add=guest_users,
				#responsibles_to_add=resp_users
				)

			for post_name, rel in (('guest_users', relation.GUEST),
								('member_users', relation.MEMBER),
								('resp_users', relation.RESPONSIBLE)):
				for u in request.POST.getlist(post_name):
					if u != '':
						mod(request, gid=group.gid, action='users',
											value='%s/%s' % (u, rel))
		except Exception, e:
			utils.wmi_exception(request, e, _(u'Error while adding group '
											u'<strong>{0}</strong>'), name)

	return HttpResponse("CREATED.")

@staff_only
def group(request, gid=None, name=None, action='edit', *args, **kwargs):
	""" group view : used to render the GroupForm in 'edit' or 'new' mode """

	try:
		group = LMC.groups.by_gid(gid)

	except:
		try:
			group = LMC.groups.by_name(name)

		except Exception, e:
			if action == 'edit':
				utils.wmi_exception(request, e, _(u'No group by that {0} '
									u'“<strong>{1}</strong>”.'),
									_('name') if name else _('GID'),
									name or gid)
				return HttpResponseRedirect(reverse('groups.views.main'))

			else:
				# creation mode.
				group = None

	# inform the user that the UI will take time to build,
	# to avoid re-clicks and (perfectly justified) grants.
	nusers = len(LMC.users.keys())
	if nusers > 50:
		# TODO: make the notification sticky and remove it just
		# before returning the rendered template result.
		utils.notification(request, _('Building group {0} form, please wait…').format(
			_('edit') if action == 'edit' else _('creation')), 3000 + 5 * nusers, 'wait_for_rendering')

	return get_group_template(request, action, group)

	"""
	if request.is_ajax():

		# TODO: use utils.format_RPC_JS('remove_notification', "wait_for_rendering")
		return render(request, 'groups/group.html', _dict)

	else:

		if request.user.is_superuser:
			sys_groups = [ g for g in utils.select('groups',
							default_selection=filters.SYSTEM)
								if not g.is_helper ]
		else:
			sys_groups = utils.select('groups', default_selection=filters.PRIVILEGED)

		_dict.update({
				'groups_list'            : utils.select('groups',
											default_selection=filters.STANDARD),
				'system_groups_list'     : sys_groups})

		# TODO: use utils.format_RPC_JS('remove_notification', "wait_for_rendering")
		return render(request, 'groups/group_template.html', _dict)"""

@staff_only
def main(request, sort="login", order="asc", select=None, *args, **kwargs):
	""" the main group page, list all groups.
		If resquesting user is staff, display standard and privileged groups.
		If it an "admins", display all groups.
	"""
	groups = LMC.groups.select(filters.STANDARD)
	
	if request.user.is_superuser:
		for g in LMC.groups.select(filters.SYSTEM):
			if not g.is_helper:
				groups.append(g)
	else:
		for g in LMC.groups.select(filters.PRIVILEGED):
			groups.append(g)

	return render(request, 'groups/index.html', {
			'request' : request,
			'groups' : sorted(groups, key= lambda x: attrgetter('name')(x).lower()
			)
		})

def massive_select_template(request, action_name, gids, *args, **kwargs):
	groups = [ LMC.groups.guess_one(g) for g in gids.split(',') ]
	template = None

	_dict = { 'groups' : groups }

	if action_name == 'delete':
		_dict.update({
			"archive_dir" : settings.home_archive_dir, 
			'admin_group' : settings.defaults.admin_group })
	if action_name == 'edit':
		return get_group_template(request, "massiv", groups)

	return HttpResponse(
		render_to_string('groups/parts/massive_{0}.html'.format(action_name),
			_dict))



def get_group_template(request, mode, groups):
	print "get_group_template", mode, groups

	if type(groups) != types.ListType:
		groups = [ groups ]
	
	_dict = {}


	users_lists = [
		{
			'list_name'    : 'standard',
			'list_content' : ''.join([render_to_string('/groups/parts/user_membership.html', {
				'groups' : groups,
				'user'  : u
				}) for u in LMC.users.select(filters.STANDARD)])
		}
	]

	# if super user append the system users list
	if request.user.is_superuser:
		users_lists.append(
			{
				'list_name'    : 'system',
				'list_content' : ''.join([render_to_string('/groups/parts/user_membership.html', {
					'groups' : groups,
					'user'  : u
					}) for u in LMC.users.select(filters.SYSTEM)])
			}
		)
		"""users_list.append( ( _('System users') ,  {
			'groups' : groups,
			'name'  : 'system',
			'users' : utils.select('users', default_selection=filters.SYSTEM)
		}))"""

	# we need to sort the form_blocks dict to display headers in order
	sorted_blocks = OrderedDict({})
	form_blocks = get_group_form_blocks(request)
	for k in sorted(form_blocks.iterkeys()):
		sorted_blocks.update({ k: form_blocks[k]})

	_dict.update({
				'mode'    	  : mode,
				'title'       : _("Massive edit"),
				'form'        : GroupForm(mode, groups[0]),
				'users_lists' : users_lists,
				'form_blocks' : sorted_blocks
			})
	if mode == 'edit':
		_dict.update({"group" : groups[0] })

	#print "rendering group.html", _dict

	if request.is_ajax():

		return render(request, 'groups/group.html', _dict)

	else:
		# render the full page
		groups = LMC.groups.select(filters.STANDARD)
	
		if request.user.is_superuser:
			for g in LMC.groups.select(filters.SYSTEM):
				if not g.is_helper:
					groups.append(g)
		else:
			for g in LMC.groups.select(filters.PRIVILEGED):
				groups.append(g)

		return render(request, 'groups/index.html', {
				'request' : request,
				'groups' : sorted(groups, key= lambda x: attrgetter('name')(x).lower()), 
				'modal_html' : render(request, 'groups/group.html', _dict) \
						if mode == 'new' else render_to_string('groups/group.html', _dict)
			})

def hotkeys_help(request):
	return render(request, '/groups/parts/hotkeys_help.html')