# -*- coding: utf-8 -*-

import os, time, operator

from licorn.foundations           import exceptions, hlstr
from licorn.foundations.constants import filters

from licorn.core import LMC

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi import utils as w

rewind = _("<br /><br />Go back with your browser, double-check data and validate the web-form.")
successfull_redirect = '/groups/list'

def ctxtnav(active=True):

	if active:
		disabled = '';
		onClick = '';
	else:
		disabled = 'un-clickable';
		onClick  = 'onClick="javascript: return(false);"'

	return '''
	<div id="ctxtnav" class="nav">
		<h2>Context Navigation</h2>
		<ul>
			<li><a href="/groups/new" title="%s" %s class="%s"><div class="ctxt-icon %s" id="icon-add">%s</div></a></li>
		</ul>
	</div>
	''' % (_('Add a new group on the system.'), onClick, disabled, disabled, _('Add a group'))

# locking and unlocking.
def unlock(uri, http_user, name, sure=False, **kwargs):
	""" Make a shared group dir permissive. """

	group = LMC.groups.by_name(name)
	title = _("Make group %s permissive") % name

	if group._wmi_protected():
		return w.forgery_error(title)

	if sure:
		try:
			group.permissive = True

		except Exception, e:
			print_exc()

		return w.HTTP_TYPE_REDIRECT, successfull_redirect
	else:
		description = _('This will permit global access to files and folders '
			'in the group shared dir, by allow <strong>any member</strong> of '
			'the group to modify / delete any document (even if he/she is not '
			'owner of the document). Enabling this option depends on how '
			'members are used to work together. Generally speaking, you will '
			'enable this feature on small-sized working groups. <br />Note: '
			'<strong> The system will propagate new permissions on share data '
			'in the background</strong>, after you toggle this feature, and '
			'this can take some time, depending of the volume of shared data '
			'(about 15 seconds per Gib).')

		data = (w.page_body_start(uri, http_user, ctxtnav, title, False) +
			w.question(_('Are you sure you want to enable '
			'permissiveness on group <strong>%s</strong>?') % name,
			description, yes_values = [ _("Enable") + ' >>',
			"/groups/unlock/%s/sure" % name, _("A") ],
			no_values = [ '<< ' + _("Cancel"), "/groups/list", _("N") ]))

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def lock(uri, http_user, name, sure=False, **kwargs):
	""" Make a group not permissive. """

	group = LMC.groups.by_name(name)
	title = _("Make group %s not permissive") % name

	if group._wmi_protected():
		return w.forgery_error(title)

	if sure:
		try:
			group.permissive = False

		except Exception, e:
			print_exc()

		return w.HTTP_TYPE_REDIRECT, successfull_redirect
	else:
		description = _('This will ensure finer write access to files and '
			'folders in the group shared dir. Only the owner / creator of a '
			'document will be able to modify it; other group members will only '
			'be able to read such a document (unless the owner manually assign '
			'other permissions, which will not be maintained by the system).'
			 '<br />Note: '
			'<strong> The system will propagate new permissions on share data '
			'in the background</strong>, after you toggle this feature, and '
			'this can take some time, depending of the volume of shared data '
			'(about 15 seconds per Gib).')

		data += (w.page_body_start(uri, http_user, ctxtnav, title, False)
			+ w.question(_('Are you sure you want to disable permissiveness '
			'on group <strong>%s</strong>?') % name,
			description, yes_values   = [ _("Disable") + ' >>',
				"/groups/lock/%s/sure" % name, _("D") ],
			no_values    = [ '<< ' + _("Cancel"), "/groups/list", _("N") ]))

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def delete(uri, http_user, name, sure=False, no_archive=False, **kwargs):
	""" Remove group and archive (or not) group shared dir. """

	group = LMC.groups.by_name(name)
	title = _("Remove group %s") % name

	if group._wmi_protected():
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	if not sure:
		data += w.question(_('Are you sure you want to delete group '
			'<strong>%s</strong>?') % name,
			_('Shared data will be archived in directory {0}, '
				'and accessible to members of group {1} for eventual '
				'recovery. However, you can decide to remove them '
				'permanently.').format(
					LMC.configuration.home_archive_dir,
					LMC.configuration.defaults.admin_group),
			yes_values   = [ _("Delete") + ' >>',
				"/groups/delete/%s/sure" % name, _("R") ],
			no_values    = [ '<< ' + _("Cancel"),
				"/groups/list", _("N") ],
			form_options = w.checkbox("no_archive", "True",
				_('Definitely remove group shared data.'),
				checked = False) )

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:
		# we are sure, do it !

		try:
			LMC.groups.del_Group(group, no_archive=True if no_archive else False)

		except Exception, e:
			print_exc()

		return w.HTTP_TYPE_REDIRECT, successfull_redirect
def new(uri, http_user, **kwargs):
	"""Generate a form to create a new group on the system."""

	title = _("Creating a new group")
	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	form_name = "group_create_form"

	data += '''<div id="edit_form">
<form name="%s" id="%s" action="/groups/create" method="post">
<table id="group_new">
	<tr>
		<td><strong>%s</strong></td><td>%s</td>
	</tr>
	<tr>
		<td><strong>%s</strong><br />%s</td><td>%s</td>
	</tr>
	<tr>
		<td><strong>%s</strong></td><td>%s</td>
	</tr>
	<tr>
		<td><strong>%s</strong></td><td>%s</td>
	</tr>
	<tr>
		<td></td>
	</tr>
	<tr>
		<td>%s</td>
		<td class="right">%s</td>
	</tr>
</table>
</form>
</div>
	''' % ( form_name, form_name,
		_('Group name'),
		w.input('name', "", size=30, maxlength=64, accesskey=_('A')),
		_('Group description'), _('(optional)'),
		w.input('description', "", size=30, maxlength=256, accesskey=_('D')),
		_('Skel of future group members'),
		w.select('skel',  LMC.configuration.users.skels,
		current = LMC.configuration.users.default_skel,
		func = os.path.basename),
		_('Permissive shared dir?'),
		w.checkbox('permissive', "True", _("Yes"), accesskey=_('P')),
		w.button(_('<< Cancel'), "/groups/list", accesskey=_('N')),
		w.submit('create', _('Create') + ' >>',
		onClick="selectAllMultiValues('%s');" % form_name, accesskey=_('T'))
		)
	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def create(uri, http_user, name, description=None, skel="", permissive=False,
	**kwargs):

	try:
		LMC.groups.add_Group(name,
					description=description or None,
					permissive=True if permissive else False,
					groupSkel=skel,
					async=False)

	except Exception, e:
		print_exc()

	return w.HTTP_TYPE_REDIRECT, successfull_redirect
def view(uri, http_user, name,**kwargs):
	"""Prepare a group view to be printed."""

	group = LMC.groups.by_name(name)
	title = _("Details of group %s") % name

	if group._wmi_protected(complete=False) and LMC.users.by_login(http_user) \
				not in LMC.groups.by_name(
					LMC.configuration.defaults.admin_group).all_members:
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	try:
		def user_line(user):
			return '''<tr>
				<td><a href="/users/view/{0}">{0}</a></td>
				<td><a href="/users/view/{0}">{1}</a></td>
				<td>{2}</td>
				</tr>'''.format(user.login, user.gecos, user.uidNumber)

		members = sorted(group.auxilliary_members)

		if members != []:

			members_html = '''
			<h2>{0}</h2>
			<div style="text-align:left;">{1}</div>
			<table class="group_members">
			<tr>
				<th><strong>{2}</strong></th>
				<th><strong>{3}</strong></th>
				<th><strong>{4}</strong></th>
			</tr>
			{5}
			</table>
			'''.format(_('Members'),
					_('(ordered by login)'),
					_('Full Name'),
					_('Identifier'),
					_('UID'),
					'\n'.join(user_line(m) for m in members))
		else:
			members_html = '<h2>%s</h2>' % _('No member in this group.')

		if group.is_standard:
			resps = sorted(group.responsible_group.auxilliary_members)

			if resps != []:
				resps_html = '''
				<h2>%s</h2>
				<div style="text-align:left;">%s</div>
				<table class="group_members">
				<tr>
					<th><strong>%s</strong></th>
					<th><strong>%s</strong></th>
					<th><strong>%s</strong></th>
				</tr>
				%s
				</table>
				''' % (
				_('Responsibles'),
				_('(ordered by login)'),
				_('Full Name'),
				_('Identifier'),
				_('UID'),
				"\n".join(user_line(r) for r in resps))

			else:
				resps_html = "<h2>%s</h2>" % _('No responsible for this group.')

			guests = sorted(group.guest_group.auxilliary_members)

			if guests != []:
				guests_html = '''
				<h2>%s</h2>
				<div style="text-align:left;">%s</div>
				<table class="group_members">
				<tr>
					<th><strong>%s</strong></th>
					<th><strong>%s</strong></th>
					<th><strong>%s</strong></th>
				</tr>
				%s
				</table>
				''' % (
				_('Guests'),
				_('(ordered by login)'),
				_('Full Name'),
				_('Identifier'),
				_('UID'),
				'\n'.join(user_line(g) for g in guests))

			else:
				guests_html = "<h2>%s</h2>" % _('No guest in this group.')

		else:
			resps_html = guests_html = ''

		form_name = "group_print_form"
		data += '''
		<div id="details">
		<form name="%s" id="%s" action="/groups/view/%s" method="post">
		<table id="user_account">
			<tr><td><strong>%s</strong><br />%s</td>
			<td class="not_modifiable">%d</td></tr>
			<tr><td><strong>%s</strong><br />%s</td>
			<td class="not_modifiable">%s</td></tr>
			<tr><td colspan="2" class="double_selector">%s</td></tr>
			<tr><td colspan="2" class="double_selector">%s</td></tr>
			<tr><td colspan="2" class="double_selector">%s</td></tr>
			<tr>
				<td>%s</td>
				<td class="right">%s</td>
			</tr>
		</table>
		</form>
		</div>
			''' % ( form_name, form_name, name,
				_('GID'), _('immutable'), group.gidNumber,
				_('Name'), _('immutable'), name,
				members_html,
				resps_html,
				guests_html,
				w.button(_('<< Go back'), "/groups/list", accesskey=_('B')),
				w.submit('print', _('Print') + ' >>',
					onClick="javascript:window.print(); return false;",
					accesskey=_('P'))
				)

	except exceptions.LicornException, e:
		data += w.error(_("Group %s doesn't exist (%s, %s)!") % (
			name, "group = g[LMC.groups.name_to_gid(name)]", e))

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def edit(uri, http_user, name, **kwargs):
	"""Edit a group."""

	group = LMC.groups.by_name(name)
	title = _("Editing group %s") %  name

	if group._wmi_protected(complete=False) and LMC.users.by_login(http_user) \
				not in LMC.groups.by_name(
					LMC.configuration.defaults.admin_group).all_members:
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	try:
		dbl_lists = {}

		if group.is_system:
			groups_filters_lists_ids = (
				(group, [ _('Manage members'), _('Users not yet members'),
				_('Current members') ], 'members' ),
				)

			#	,
			#	(LMC.configuration.groups.resp_prefix + name, None, '&#160;' ),
			#	(LMC.configuration.groups.guest_prefix + name, None, '&#160;' )
		else:
			groups_filters_lists_ids = (
				(group,
					[_('Manage members'),
					_('Users not yet members'),
					_('Current members')],
					'members'),
				(group.responsible_group,
					[_('Manage responsibles'),
					_('Users not yet responsibles'),
					_('Current responsibles')],
					'resps'),
				(group.guest_group,
					[_('Manage guests'),
					_('Users not yet guests'),
					_('Current guests')],
					'guests') )

		for (g, titles, tid) in groups_filters_lists_ids:
			if titles is None:
				dbl_lists[gname] = tid

			else:
				dest   = list(g.memberUid)
				source = [ u.login for u in LMC.users.select(filters.STANDARD)]

				# make a live copy, else RuntimeError because we modify the
				# original list.
				for a_user in dest[:]:
					try:
						source.remove(a_user)
					except ValueError:
						dest.remove(a_user)

				dbl_lists[g.name] = w.doubleListBox(titles, tid, sorted(source), sorted(dest))

		def descr(desc, system):
			return w.input('description', desc, size=30, maxlength=256,
				accesskey='D')
		def skel(cur_skel, system):
			return '' if system else \
				'''
				<tr>
					<td><strong>%s</strong></td>
					<td class="right">%s</td>
				</tr>
				''' % (_('Skeleton'),
					w.select('skel', LMC.configuration.users.skels,
					cur_skel, func = os.path.basename))
		def permissive(perm, system):
			return '' if system else \
				'''
				<tr>
					<td><strong>%s</strong></td>
					<td class="right">%s</td>
				</tr>
				''' % (_('Permissive shared dir?'),
					w.checkbox('permissive',
					"True", _(u"Yes"), checked = perm ))

		form_name = "group_edit_form"

		if group.is_system:
			data_rsp_gst =''
		else :
			data_rsp_gst = '''
<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>
				<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>

			''' % (
			_('Group responsibles') ,
			dbl_lists[group.responsible_group.name],
			_('Group guests'),
			dbl_lists[group.guest_group.name]
			)

		data += '''
		<script type="text/javascript" src="/js/jquery.js"></script>
		<script type="text/javascript" src="/js/accordeon.js"></script>

		<div id="edit_form">
<form name="%s" id="%s" action="/groups/record/%s" method="post">
	<table id="user_account">
		<tr>
			<td><strong>%s</strong><br />%s</td>
			<td class="not_modifiable right">%d</td>
		</tr>
		<tr>
			<td><strong>%s</strong><br />%s</td>
			<td class="not_modifiable right">%s</td>
		</tr>
		%s
		<tr>
			<td><strong>%s</strong></td>
			<td class="right">%s</td>
		</tr>
		%s
		<tr>
			<td colspan="2" id="my-accordion">
				<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>
				%s
			</td>
		<tr>
			<td>%s</td>
			<td class="right">%s</td>
		</tr>
	</table>
</form>
</div>
		''' % ( form_name, form_name, name,
			_('GID'), _('(immutable)'),
			group.gidNumber,
			_('Group name'), _('(immutable)'),
			group.name,
			permissive(group.permissive, group.is_system),
			_('Group description'),
			descr(group.description, group.is_system),
			skel(group.groupSkel, group.is_system),
			_('Group members'),
				dbl_lists[group.name],
			data_rsp_gst,
			w.button('<< ' + _('Cancel'), "/groups/list", accesskey=_('N')),
			w.submit('record', _('Record') + ' >>',
			onClick="selectAllMultiValues('%s');" % form_name,
			accesskey=_('R'))
			)

	except exceptions.LicornException, e:
		data += w.error(_("Group %s doesn't exist (%s, %s)!") % (name,
			"group = allgroups.groups[LMC.groups.name_to_gid(name)]", e))

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def record(uri, http_user, name, skel=None, permissive=False, description=None,
	members_source    = [], members_dest = [],
	resps_source      = [], resps_dest   = [],
	guests_source     = [], guests_dest  = [],
	**kwargs):
	""" Record group modification changes."""

	group = LMC.groups.by_name(name)
	title = _("Modifying group %s") % name

	not_super_admin = (not LMC.users.by_login(http_user)
			in LMC.groups.by_name(
				LMC.configuration.defaults.admin_group).all_members)

	if group._wmi_protected(complete=False) and not_super_admin:
		return w.forgery_error(title)

	# protect against URL forgery
	for user_list in (members_source, members_dest, resps_source, resps_dest,
			guests_source, guests_dest):
		if hasattr(user_list, '__iter__'):
			for user in user_list:
				if LMC.users.by_login(user)._wmi_protected() and not_super_admin:
					return w.forgery_error(title)
		else:
			if LMC.users.by_login(user_list)._wmi_protected() and not_super_admin:
				return w.forgery_error(title)

	if name in (LMC.configuration.licornd.wmi.group,
				LMC.configuration.defaults.admin_group) and (
		http_user in members_source
		or http_user in resps_source
		or http_user in guests_source):
		return w.fool_proof_protection_error(_("The system won't let you "
			"remove your own account from the {wmi_group} or {admin_group} "
			"groups, sorry.").format(
				wmi_group=LMC.configuration.licornd.wmi.group,
				admin_group=LMC.configuration.defaults.admin_group), title)

	data    = '%s<h1>%s</h1>' % (w.backto(), title)

	if description != group.description:
		group.description = unicode(description)

	if skel and skel != group.groupSkel:
		group.groupSkel = skel

	group.permissive = True if permissive else False

	add_members = sorted(w.merge_multi_select(members_dest))
	del_members = sorted(w.merge_multi_select(members_source))
	cur_members = list(group.memberUid)

	group_pack_del = [
				(del_members, cur_members, group.del_Users)
			]

	group_pack_add = [
				(add_members, cur_members, group.add_Users)
			]

	if group.is_standard:
		add_resps = sorted(w.merge_multi_select(resps_dest))
		del_resps = sorted(w.merge_multi_select(resps_source))
		cur_resps = list(group.responsible_group.memberUid)

		add_guests = sorted(w.merge_multi_select(guests_dest))
		del_guests = sorted(w.merge_multi_select(guests_source))
		cur_guests = list(group.guest_group.memberUid)

		group_pack_del.insert(0, (del_guests, cur_guests, group.guest_group.del_Users))
		group_pack_add.insert(0, (add_guests, cur_guests, group.guest_group.add_Users))

		group_pack_del.append((del_resps, cur_resps, group.responsible_group.del_Users))
		group_pack_add.append((add_resps, cur_resps, group.responsible_group.add_Users))

	# shortcut in loops
	byl = LMC.users.by_login

	def not_contains(a, b):
		return not operator.contains(a, b)

	# NOTE: the order is important: we delete, then add; we demote, then promote.
	# this avoids conflicts and symlinks overwrite/deletion.
	for pack, operator_ in ((group_pack_del, operator.contains),
							(group_pack_add, not_contains)):
		for var, cur, func in pack:
			to_operate = []

			for one in var:
				if operator_(cur, one):
					try:
						#print '>>> del/add', one, func
						to_operate.append(byl(one))
					except:
						print_exc()

			if to_operate != []:
				try:
					func(to_operate, batch=True)
				except:
					print_exc()

	return w.HTTP_TYPE_REDIRECT, successfull_redirect
def main(uri, http_user, sort="name", order="asc", **kwargs):
	"""List all groups and provileges on the system, displaying them
	in a nice HTML page. """

	start = time.time()

	groups = LMC.groups

	std_users = LMC.users.select(filters.STANDARD)

	tgroups  = {}
	totals   = {}

	title = _('Groups')
	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if order == "asc": reverseorder = "desc"
	else:              reverseorder = "asc"

	data += '<table id="groups_list">\n		<tr class="groups_list_header">\n'

	sortcols = (
		('', '', False),
		("name", _("Name"), True),
		("description", _("Description"), True),
		("skel", _("Skeleton"), True),
		("permissive", _("Perm."), True),
		('members', _("Members"), False),
		("resps", _("Responsibles"), False),
		("guests", _("Guests"), False) )

	for (column, name, can_sort) in sortcols:
		if can_sort:
			if column == sort:
					data += '''
		<th><img src="/images/sort_%s.png" alt="%s" />&#160;
			<a href="/groups/list/%s/%s" title="%s">%s</a>
		</th>\n''' % (order, _('%s order') % order, column, reverseorder,
			_('Click to sort in reverse order.'), name)
			else:
				data += '''		<th><a href="/groups/list/%s/asc"
					title="%s">%s</a></th>\n''' % (column,
					_('Click to sort on this column.'), name)
		else:
			data += '		<th>%s</th>\n' % name

	data += '		</tr>\n'

	for (filter, filter_name) in (
		(filters.STANDARD, _('Groups')),
		(filters.PRIVILEGED, _("Privileges")) ):

		tgroups  = {}
		ordered  = {}
		totals[filter_name] = 0

		for group in LMC.groups.select(filter):
			gid = group.gidNumber
			name  = group.name

			tgroups[gid] = {
				'name'        : name,
				'description' : group.description + name,
				'skel'        : (_(u'none') if group.groupSkel
											else group.groupSkel) + name,
				'permissive'  : str(group.permissive) + name
				}
			totals[filter_name] += 1

			# index on the column choosen for sorting, and keep trace of the uid
			# to find account data back after ordering.

			ordered[hlstr.validate_name(tgroups[gid][sort])] = group

			tgroups[gid]['members'] = []
			for member in group.members:
				if not member.is_system:
					tgroups[gid]['members'].append(member)

			if not group.is_system:
				for g2 in group.responsible_group, group.guest_group:
					tgroups[gid][g2.name + 'members'] = []
					for member in g2.members:
						if not member.is_system:
							tgroups[gid][g2.name + 'members'].append(member)

		gkeys = sorted(ordered.iterkeys())
		if order == "desc": gkeys.reverse()

		def html_build_group(group):
			gid   = group.gidNumber
			name  = group.name
			html_data = '''
		<tr class="userdata">
			<td class="nopadding">
				<a href="/groups/view/%s" title="%s" class="view-entry">
				<span class="view-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span>
				</a>
			</td>
			<td class="group_name">
				<a href="/groups/edit/%s" title="%s" class="edit-entry">%s</a>
			</td>
			<td class="group_name">
				<a href="/groups/edit/%s" title="%s" class="edit-entry">%s</a>
			</td>
			<td class="right">
				<a href="/groups/edit/%s">%s</a>
			</td>
				''' % (
				name, _('''View the group details, its parameters,
					members, responsibles and guests.
					From there you can print all group-related informations.'''),
				name, group.description, name,
				name, group.description, group.description,
				name, group.groupSkel or _(u'none'))

			if group.is_system:
				html_data += '<td>&#160;</td>'
			else:
				if group.permissive:
					html_data += '''
				<td class="user_action_center">
					<a href="/groups/lock/%s" title="%s">
					<img src="/images/16x16/unlocked.png" alt="%s"/></a>
				</td>
					''' % (name, _('''Shared group directory is currently '''
					'''<strong>permissive</strong>. Click to deactivate '''
					'''permissiveness.'''), _('Group is currently permissive.'))
				else:
					html_data += '''
				<td class="user_action_center">
					<a href="/groups/unlock/%s" title="%s">
					<img src="/images/16x16/locked.png" alt="%s"/></a>
				</td>
					''' % (name, _('''Shared group directory is currently
					<strong>NOT</strong> permissive. Click ti activate
					permissiveness.'''), _('Group is NOT permissive.'))

			if group.is_system:
				group_pack = (('members', _('Current members')), )
			else:
				group_pack = (
				('members', _('Current members')),
				(group.responsible_group.name + 'members', _('Current responsibles')),
				(group.guest_group.name + 'members', _('Current guests')))

			for (keyname, text) in group_pack:
				if keyname in tgroups[gid]:
					accounts = {}
					uordered = {}
					for member in tgroups[gid][keyname]:
						uid = member.uidNumber
						accounts[uid] = {
							'login': member.login,
							'gecos': member.gecos,
							'gecos_sort': member.gecos + member.login
							}
						uordered[hlstr.validate_name(
							accounts[uid]['gecos_sort'], aggressive=True)] = uid

					memberkeys = sorted(uordered.iterkeys())

					mbdata = '''<table><tr><th>%s</th><th>%s</th>
					<th>%s</th></tr>\n''' % (_('Full Name'),
							_('Identifier'), _('UID'))

					for member in memberkeys:
						uid = uordered[member]
						mbdata += '''<tr><td>%s</td><td>%s</td>
						<td>%d</td></tr>\n''' % (accounts[uid]['gecos'],
							accounts[uid]['login'], uid)

					mbdata += '</table>'
					nb = len(tgroups[gid][keyname])
					if nb == 0:
						html_data += '''<td class="right faded">%s</td>\n''' % \
							_('none')
					else:
						html_data += '''<td class="right">
							<a class="nounder" title="<h4>%s</h4><br />%s">
							<strong>%d</strong>&#160;<img
							src="/images/16x16/details-light.png" alt="%s"
							/></a></td>\n''' % (text, mbdata, nb,
							_('See %s of group %s.') % (text, name))
				else:
					html_data += '''<td>&#160;</td>\n'''

			if group.is_system:
				html_data += '<td colspan="1">&#160;</td></tr>\n'
			else:
				html_data += '''
					<td class="user_action">
					<a href="/groups/delete/%s" title="%s" class="delete-entry">
					<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span>
					</a>
					</td>
				</tr>
						''' % (name,
						_('''Definitely remove this group from system.'''))
			return html_data

		data += '<tr><td class="group_class" colspan="7">%s</td></tr>\n%s' % (
			filter_name, '\n'.join(html_build_group(ordered[key]) for key in gkeys))

	def print_totals(totals):
		output = ""
		for total in totals:
			if totals[total] != 0:
				output += '''
	<tr class="list_total">
		<td colspan="6" class="total_left">%s</td>
		<td colspan="6" class="total_right">%d</td>
	</tr>
		''' % (_('number of <strong>%s</strong>:') % total, totals[total])
		return output

	data += '''
	<tr>
		<td colspan="6">&#160;</td></tr>
	%s
	<tr class="list_total">
		<td colspan="6" class="total_left"><strong>%s</strong></td>
		<td colspan="6" class="total_right">%d</td>
	</tr>
</table>
	''' % (print_totals(totals), _('Total number of groups:'), reduce(
		lambda x, y: x+y, totals.values()))

	return (w.HTTP_TYPE_TEXT, w.page(title,
		data + w.page_body_end(w.total_time(start, time.time()))))
