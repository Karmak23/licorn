# -*- coding: utf-8 -*-

from django.template.loader       import render_to_string
from django.utils.translation     import ugettext as _

from licorn.foundations.ltrace    import *
from licorn.foundations.constants import relation, filters
from licorn.interfaces.wmi.libs   import utils

def memberships(rel):
	return {
		# this one should not be needed, else there is something
		# wrong in `core.groups.*`.
		#relation.NO_MEMBERSHIP : _(u'stranger'),
		relation.MEMBER        : _(u'member'),
		relation.GUEST         : _(u'guest'),
		relation.RESPONSIBLE   : _(u'responsible'),
	}[rel]
def update_groups_number(request, event):
	yield utils.format_RPC_JS('reload_div', '#groups_list_count',
								len(utils.select('groups', default_selection=filters.STANDARD)))
	if request.user.is_staff:
		yield utils.format_RPC_JS('reload_div', '#sys_groups_list_count',
								len(utils.select('groups', default_selection=filters.SYSTEM)))
def group_added_handler(request, event):

	group = event.kwargs['group']

	yield utils.notify(_(u'Group "{0}" added on the system.').format(group.name))
	yield utils.format_RPC_JS('add_row',
								'groups' if group.is_standard else 'sys_groups',
								render_to_string('groups/group_row.html', {
									'item': group,
									'name': '%s' % 'groups'
										if group.is_standard else 'sys_groups' }))

	yield utils.format_RPC_JS('init_groups_events',
								'groups' if group.is_standard else 'sys_groups',
								group.gid, group.name, 'gidNumber')

	for i in update_groups_number(request, event):
		yield i
def group_deleted_handler(request, event):

	system = event.kwargs['system']
	gid    = event.kwargs['gid']
	name   = event.kwargs['name']

	yield utils.notify(_(u'Group "{0}" deleted from the system.').format(name))
	yield utils.format_RPC_JS('del_row', 'sys_groups' if system else 'groups', gid)
	for i in update_groups_number(request, event):
		yield i
def group_member_deleted_handler(request, event):

	user  = event.kwargs['user']
	group = event.kwargs['group']

	yield utils.format_RPC_JS('update_relationship', 'user',
		user.uidNumber, group.standard_group.gidNumber
						if group.is_helper else group.gidNumber, 0)

	yield utils.notify(_(u'User "{0}" has no more relationship with '
		u'group "{1}".').format(user.login,
				group.standard_group.name
					if group.is_helper else group.name))
def group_member_added_handler(request, event):

	user  = event.kwargs['user']
	group = event.kwargs['group']

	rel = group.get_relationship(user.uidNumber)

	yield utils.format_RPC_JS('update_relationship', 'user',
		user.uidNumber,
		group.standard_group.gidNumber if group.is_helper else group.gidNumber,
		rel)

	yield utils.notify(_(u'User "{0}" is now a {1} of group "{2}".').format(
		user.login, memberships(rel), group.standard_group.name
							if group.is_helper else group.name))
def group_permissive_state_changed_handler(request, event):

	group = event.kwargs['group']

	yield utils.format_RPC_JS('change_permissive_state',
								group.gidNumber,
								group.is_permissive)

	yield utils.notify(_(u'Group "{0}" is now {1}.').format(group.name,
			_(u'permissive') if group.is_permissive else _(u'not permissive')))
def group_description_changed_handler(request, event):

	group = event.kwargs['group']

	yield utils.notify(_(u'Group "{0}" description has changed '
						u'to {1}.').format(group.name, group.description))

	yield utils.format_RPC_JS('update_row_value',
								'groups' if group.is_standard
									else 'sys_groups', group.gidNumber,
								"description", _('No description')
									if group.description in ('', None) else group.description,
								[ '-grayed_out' ] if group.description else [ '+grayed_out' ])
