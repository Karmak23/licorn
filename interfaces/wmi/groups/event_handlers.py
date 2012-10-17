# -*- coding: utf-8 -*-

from django.template.loader       import render_to_string
from django.utils.translation     import ugettext as _

from licorn.foundations.ltrace    import *
from licorn.foundations.constants import relation, filters
from licorn.interfaces.wmi.libs   import utils
from licorn.core                  import LMC
def memberships(rel):
	return {
		# this one should not be needed, else there is something
		# wrong in `core.groups.*`.
		#relation.NO_MEMBERSHIP : _(u'stranger'),
		relation.MEMBER        : _(u'member'),
		relation.GUEST         : _(u'guest'),
		relation.RESPONSIBLE   : _(u'responsible'),
	}[rel]
def update_group_row(group, remove=False, gid=None):
	if remove:
		return utils.format_RPC_JS('remove_instance',
								'groups',
								gid
								)
	else:
		return utils.format_RPC_JS('update_instance',
								'groups',
								group.gid,
								render_to_string('groups/group_row.html', {
									'group': group,
								}),
								"setup_row"
								)


def update_groups_number(request, event):
	yield utils.format_RPC_JS('reload_div', '#groups_list_count',
								len(LMC.groups.select(filters.STANDARD)))
	if request.user.is_staff:
		yield utils.format_RPC_JS('reload_div', '#sys_groups_list_count',
								len(LMC.groups.select(filters.SYSTEM)))
def group_added_handler(request, event):

	group = event.kwargs['group']

	yield utils.notify(_(u'Group "{0}" added on the system.').format(group.name))

	yield update_group_row(group)

	yield utils.format_RPC_JS('update_total_items', 'groups', "/"+str(len(LMC.groups)))
def group_deleted_handler(request, event):

	system = event.kwargs['system']
	gid    = event.kwargs['gid']
	name   = event.kwargs['name']

	yield utils.notify(_(u'Group "{0}" deleted from the system.').format(name))

	yield update_group_row(None, remove=True, gid=gid)

	yield utils.format_RPC_JS('update_total_items', 'groups', "/"+str(len(LMC.groups)))

def group_member_deleted_handler(request, event):

	user  = event.kwargs['user']
	group = event.kwargs['group']

	gid = group.gidNumber if not group.is_helper else group.standard_group.gidNumber

	yield utils.format_RPC_JS(
		'update_relationship',
		user.uidNumber, gid, 0)

	yield utils.notify(_(u'User "{0}" has no more relationship with '
		u'group "{1}".').format(user.login,
				group.standard_group.name
					if group.is_helper else group.name))
def group_member_added_handler(request, event):

	user  = event.kwargs['user']
	group = event.kwargs['group']

	rel = group.get_relationship(user.uidNumber)
	gid = group.gidNumber if not group.is_helper else group.standard_group.gidNumber

	yield utils.format_RPC_JS('update_relationship',
		user.uidNumber, gid,
		rel)

	yield utils.notify(_(u'User "{0}" is now a {1} of group "{2}".').format(
		user.login, memberships(rel), group.standard_group.name
							if group.is_helper else group.name))
def group_permissive_state_changed_handler(request, event):

	group = event.kwargs['group']

	yield update_group_row(group)

	yield utils.notify(_(u'Group "{0}" is now {1}.').format(group.name,
			_(u'permissive') if group.is_permissive else _(u'not permissive')))
def group_groupSkel_changed_handler(request, event):

	group = event.kwargs['group']
	skel = event.kwargs['skel']

	yield utils.notify(_(u'Group "{0}" now depends on skeleton {1}.').format(group.name,
			skel))
	yield update_group_row(group)
def group_description_changed_handler(request, event):

	group = event.kwargs['group']

	yield utils.notify(_(u'Group "{0}" description has changed '
						u'to {1}.').format(group.name, group.description))

	yield update_group_row(group)
