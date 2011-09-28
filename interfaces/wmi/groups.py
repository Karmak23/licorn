# -*- coding: utf-8 -*-

import os, time
from urllib import unquote_plus

from licorn.foundations           import exceptions, hlstr, logging
from licorn.foundations.constants import filters

from licorn.core import LMC
from licorn.interfaces.wmi.decorators import check_groups

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi import utils as w

rewind = _("<br /><br />Go back with your browser, double-check data and validate the web-form.")
successfull_redirect = '/groups/list'

# locking and unlocking.
def unlock(uri, http_user, name, sure=False, **kwargs):
	""" Make a shared group dir permissive. """

	title = _("Make group %s permissive") % name

	group = LMC.groups.by_name(name)

	if group._wmi_protected():
		return w.forgery_error(title)

	#data  = w.page_body_start(uri, http_user, ctxtnav, title, False)
	data = ''

	if not sure:
		description = _('''This will permit large access to files and folders
			in the group shared dir, and will allow any member of the group to
			modify / delete any document, even if he/she is not owner of the
			document. This option can be dangerous, but if group members are
			accustomed to work together, there is no problem. Generally speaking
			you will use this feature on small working groups. <br /> Warning:
			<strong> The operation may be lengthy because the system will change
			permissions of all current data </ strong> (duration is therefore
			depending on the volume of data, about 1 second for 100Mio).''')

		data += w.question(_('''Are you sure you want to active '''
			'''permissiveness on group <strong>%s</strong>?''') % name,
			description, yes_values = [ _("Activate") + ' >>',
			"/groups/unlock/%s/sure" % name, _("A") ],
			no_values = [ '<< ' + _("Cancel"), "/groups/list", _("N") ])

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:		# we are sure, do it !

		group.permissive = True

		#TODO
		return (w.HTTP_TYPE_REDIRECT, successfull_redirect)
def lock(uri, http_user, name, sure=False, **kwargs):
	""" Make a group not permissive. """

	group = LMC.groups.by_name(name)

	title = _("Make group %s not permissive") % name

	if group._wmi_protected():
		return w.forgery_error(title)

	#data  = w.page_body_start(uri, http_user, ctxtnav, title, False)
	data = ''

	if not sure:
		description = _('''This will ensure finer write access to files and
		folders in the group shared dir. Only the owner / creator of a document
		will be able to modify it; other group members will only be able to read
		such a document (unless the owner manually assign other permissions,
		which are not guaranteed to be maintained by the system). <br />
		Warning: <strong> The operation may be lengthy because the system will
		switch permissions of all current group shared data</strong> (duration
		is therefore depending on the volume of data, about 1 sec. for 100Mio).
		''')

		data += w.question(_('''Are you sure you want to make group '''
			'''<strong>%s</strong> not permissive?''') % name,
			description, yes_values   = [ _("Deactivate") + ' >>',
				"/groups/lock/%s/sure" % name, _("D") ],
			no_values    = [ '<< ' + _("Cancel"), "/groups/list", _("N") ])

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:
		# we are sure, do it.
		group.permissive = False

		#TODO
		return (w.HTTP_TYPE_REDIRECT, successfull_redirect)


def delete_message(uri, http_user, name, **kwargs):

	group = LMC.groups.by_name(name)

	description = _("Are you sure you want to remove group "
		"<strong>%s</strong> ? <br/><br/>") % name
	description += _('''Group shared data will be archived in directory %s,
			and accessible to members of group %s for eventual
			recovery. However, you can decideto remove them
			permanently.''') % (LMC.configuration.home_archive_dir,
			LMC.configuration.defaults.admin_group)
	description += "<br /><br /><input type='checkbox' id='delete_group_make_backup'/> " \
		"<label for='delete_group_make_backup'>Definitely remove account data (no archiving).</label> "
	return (w.HTTP_TYPE_JSON, description)
def skel_message(uri, http_user, name, **kwargs):

	#data  = w.page_body_start(uri, http_user, ctxtnav, title, False)
	data = ''

	description = _('''Are you sure you want to reapply this skel to
		all of the members of %s?<br />This will reset the desktops, icons and menus
		of all members of the group, according to the content of the
		skel you choose. This will NOT alter any of the user personnal
		data, nor the group shared data. <br /><br />Which skel do you want to apply?
		%s''') % (name,w.select("apply_skel", LMC.configuration.users.skels,
			func=os.path.basename, select_id='skel_to_apply'))

	return (w.HTTP_TYPE_JSON, description)


def massive_delete(uri, http_user, names, sure, no_archive=False,
	**kwargs):
	"""remove several users account."""
	assert ltrace(TRACE_WMI, '> groups.massive_delete(uri=%s, http_user=%s, '
		'names=%s, sure=%s, no_archive=%s)' % (uri, http_user,
		names, sure, no_archive))

	names = w.my_unquote(names)
	groups_deleted = []
	for name in names.split(',') if names != '' else []:
		try:
			t = delete(uri, http_user, name, sure, no_archive=no_archive)
			groups_deleted.append(name)
		except Exception, e:
			raise
	groups_deleted = '["%s"]' % '","'.join(groups_deleted)
	return (w.HTTP_TYPE_JSON, groups_deleted)
def massive_skel(uri, http_user, names, sure, apply_skel=None, **kwargs):
	"""reapply a group's skel with confirmation."""
	assert ltrace(TRACE_WMI, '> groups.massive_skel(uri=%s, http_user=%s, '
		'names=%s, sure=%s, apply_skel=%s)' % (uri, http_user,
		names, sure, apply_skel))

	if apply_skel is None:
		apply_skel = LMC.configuration.users.default_skel

	names = w.my_unquote(names)
	for name in names.split(',') if names != '' else []:
		#print 'dealing with group %s' % name
		skel(uri, http_user, name, sure=sure, apply_skel=apply_skel, massive_operation=True)

	return (w.HTTP_TYPE_JSON, None)
@check_groups('delete')
def delete(uri, http_user, name, sure=False, no_archive=False,
	massive_operation=False, **kwargs):
	""" Remove group and archive (or not) group shared dir. """

	group = LMC.groups.by_name(name)
	LMC.groups.del_Group(group=LMC.groups.by_name(name), no_archive=bool(no_archive));

	return (w.HTTP_TYPE_JSON, group.to_JSON())
@check_groups('skel')
def skel(uri, http_user, name, sure=False, apply_skel=None, **kwargs):
	"""reapply a user's skel with confirmation."""
	assert ltrace(TRACE_WMI, '> groups.skel(uri=%s, http_user=%s, '
		'name=%s, sure=%s, apply_skel=%s)' % (uri, http_user, name,
			sure, apply_skel))
	#print "dealing with group : %s" % name
	#print "members : %s" %  LMC.groups.by_name(name).members

	http_u = LMC.users.by_login(http_user)
	g = LMC.groups.by_name(name)
	wmi_group = LMC.groups.by_name(
				LMC.configuration.licornd.wmi.group)
	admins_group = LMC.groups.by_name(
				LMC.configuration.defaults.admin_group)
	for user in LMC.groups.by_name(name).members:
		if http_u not in admins_group.members and user in admins_group.members:
			logging.notice(_('You cannot reapply skel of user %s, you have not enaugh rights') % user.login)
			continue
		user.apply_skel(w.my_unquote(apply_skel))
	return (w.HTTP_TYPE_JSON, None)
def new(uri, http_user, **kwargs):
	"""Generate a form to create a new group on the system."""

	title = _("Creating a new group")
	#data  = w.page_body_start(uri, http_user, ctxtnav, title, False)
	data = ''

	data += '''
		<span id='sub_content_header'>
			<span id='sub_content_back'><img src='images/16x16/close.png'/></span>
			<span id='sub_content_title'>{sub_content_title}</span>
		</span>
		<div id='sub_content_area'>
			<div class='sub_content_line one_line'>
				<div class='sub_content_half_line font_bold'>{group_name_label}</div>
				<div class='sub_content_half_line align_right'>{group_name_input}</div>
			</div>
			<div class='sub_content_line big_line'>
				<div class='sub_content_half_line font_bold'>{group_descr_label}<br/><span class="sub_content_title_sub">{group_optional_info}</span></div>
				<div class='sub_content_half_line align_right'>{group_descr_input}</div>
			</div>
			<div class='sub_content_line one_line'>
				<div class='sub_content_half_line font_bold'>{group_skel_label}</div>
				<div class='sub_content_half_line align_right'>{group_skel_input}</div>
			</div>
			<div class='sub_content_line one_line'>
				<div class='sub_content_half_line font_bold'>{group_perm_label}</div>
				<div class='sub_content_half_line align_right'>{group_perm_input}</div>
			</div>

			<div class='sub_content_line last_line'>
					<div class='sub_content_half_line'>&nbsp;</div>
					<div class='sub_content_half_line align_right'>{create_button}</div>
			</div>
		</div>
	'''.format( sub_content_title= _(u"Add a new group"),
		group_name_label=_('Group name'),
		group_name_input=w.input('name', "", size=30, maxlength=64,
			accesskey=_('A'), input_id='new_group_name'),
		group_descr_label=_('Group description'),
		group_optional_info=_('(optional)'),
		group_descr_input=w.input('description', "", size=30,
			maxlength=256, accesskey=_('D'), input_id='new_group_desc'),
		group_skel_label=_('Skel of future group members'),
		group_skel_input=w.select('skel',  LMC.configuration.users.skels,
							current=LMC.configuration.users.default_skel,
							func=os.path.basename, select_id='new_group_skel'),
		group_perm_label=_('Permissive shared dir?'),
		group_perm_input=w.checkbox('permissive', "True", _("Yes"),
			accesskey=_('P'), checkbox_id='new_group_perm'),
		create_button=w.submit('create', _('Create') + ' >>',
			submit_id='save_group_button')
		)
	return (w.HTTP_TYPE_JSON, data)
def create(uri, http_user, name, description=None, skel="", permissive=False,
	**kwargs):

	if permissive == 'true':
		permissive = True
	else:
		permissive = False

	LMC.groups.add_Group(name,
		description=w.my_unquote(description),
		groupSkel=w.my_unquote(skel),
		permissive=permissive)

	return (w.HTTP_TYPE_JSON, LMC.groups.by_name(name).to_JSON())

def view(uri, http_user, name,**kwargs):
	"""Prepare a group view to be printed."""

	title = _("Details of group %s") % name

	group = LMC.groups.by_name(name)

	#data  = w.page_body_start(uri, http_user, ctxtnav, title)
	data = ''

	u = LMC.users
	g = LMC.groups

	try:

		# keep a copy here, to avoid rebuilding from the weakref lists every
		# time we need the members.
		members = group.all_members

		def user_line(user):
				return '''<tr>
					<td><a href="/users/view/{user.login}">{user.gecos}</a></td>
					<td><a href="/users/view/{user.login}">{user.login}</a></td>
					<td>{user.uidNumber}</td>
					</tr>'''.format(user=user)

		members_html = '''
		<div class="group_listing">
			<strong>%s</strong>
		</div>''' % _(u'Members')

		if members != []:
			members.sort()

			members_html += '''
			<table class="group_members">
			<tr>
				<th><strong>{full_name_label}</strong></th>
				<th><strong>{identifier_label}</strong></th>
				<th><strong>{uid_label}</strong></th>
			</tr>
			{membs}
			</table>
			'''.format(
					members_label=_('Members'),
					ordered=_('(ordered by login)'),
					full_name_label=_('Full Name'),
					identifier_label=_('Identifier'),
					uid_label=_('UID'),
					membs="\n".join(user_line(u) for u in members)
				)

		else:
			members_html += '%s' % _('No member in this group.')

		if group.is_standard:
			resps = group.responsible_group.all_members

			resps_html = '''
				<div class="group_listing">
					<strong>%s</strong>
				</div>''' % _(u'Responsibles')
			guests_html = '''
				<div class="group_listing">
					<strong>%s</strong>
				</div>''' % _(u'Guests')

			if resps != []:
				resps.sort()

				resps_html += '''
			<!--<div style="text-align:left;">{ordered}</div>-->
			<table class="group_members">
			<tr>
				<th><strong>{full_name_label}</strong></th>
				<th><strong>{identifier_label}</strong></th>
				<th><strong>{uid_label}</strong></th>
			</tr>
			{responsibles}
			</table>
			'''.format(
					ordered=_('(ordered by login)'),
					full_name_label=_('Full Name'),
					identifier_label=_('Identifier'),
					uid_label=_('UID'),
					responsibles="\n".join(user_line(r) for r in resps)
				)

			else:
				resps_html += "%s" % \
					_('No responsible for this group.')

			guests = group.guest_group.all_members

			if guests != []:
				guests.sort()

				guests_html += '''
			<!--<div style="text-align:left;">{ordered}</div>-->
			<table class="group_members">
			<tr>
				<th><strong>{full_name_label}</strong></th>
				<th><strong>{identifier_label}</strong></th>
				<th><strong>{uid_label}</strong></th>
			</tr>
			{gsts}
			</table>
			'''.format(
					ordered=_('(ordered by login)'),
					full_name_label=_('Full Name'),
					identifier_label=_('Identifier'),
					uid_label=_('UID'),
					gsts="\n".join(user_line(g) for g in guests)
				)
			else:
				guests_html += "%s" % _('No guest in this group.')

		else:
			resps_html = guests_html = ''

		data = '''
		<span id='sub_content_header'>
			<span id='sub_content_title'>{sub_content_title}</span>
		</span>
		<div id="details">
			<table>
				<tr>
					<td>
						<strong>{gid_title}</strong><br />{immutable}
					</td>
					<td class="not_modifiable">
						{group_gid}
					</td>
				</tr>
				<tr>
					<td>
						<strong>{name_title}</strong><br />{immutable}
					</td>
					<td class="not_modifiable">
						{group_name}
					</td>
				</tr>
				<tr>
					<td>
						<strong>{desc_title}</strong><br />
					</td>
					<td class="not_modifiable">
						{group_desc}
					</td>
				</tr>
				<tr>
					<td>
						<strong>{permissive_title}</strong><br />
					</td>
					<td class="not_modifiable">
						{group_permissive}
					</td>
				</tr>
				<tr>
					<td colspan="2" class="double_selector">
						{members_html}
					</td>
				</tr>
				<tr>
					<td colspan="2" class="double_selector">
						{resps_html}
					</td>
				</tr>
				<tr>
					<td colspan="2" class="double_selector">
						{guests_html}
					</td>
				</tr>

			</table>
		</div>
			'''.format(
					sub_content_title="Group information of %s" % name,
					gid_title = _('GID'),
					immutable = _('immutable'),
					group_gid = group.gidNumber,
					name_title = _('Name'),
					group_name = name,
					desc_title = _('Description'),
					group_desc = group.description,
					permissive_title = _('Permissive'),
					group_permissive = _("True") if group.permissive else _("False"),
					members_html = members_html,
					resps_html = resps_html,
					guests_html = guests_html
				)

	except exceptions.LicornException, e:
		data += w.error(_("Group %s doesn't exist (%s, %s)!") % (
			name, "group = g[LMC.groups.name_to_gid(name)]", e))

	return (w.HTTP_TYPE_JSON, data)
def edit(uri, http_user, name, **kwargs):
	"""Edit a group."""
	is_super_admin = LMC.users.by_login(http_user) in LMC.groups.by_name(
			LMC.configuration.defaults.admin_group).all_members

	group = LMC.groups.by_name(name)

	title = _("Editing group %s") %  name


	#data  = w.page_body_start(uri, http_user, ctxtnav, title, False)
	data = ''
	try:
		dbl_lists = {}

		def skel(cur_skel, system):
			return '' if system else \
				'''
				<div class="sub_content_line one_line">
					<div class="sub_content_half_line font_bold">%s</div>
					<div class="sub_content_half_line align_right">%s</div>
				</div>
				''' % (_('Skeleton'),
					w.select('skel', LMC.configuration.users.skels,
					cur_skel, func = os.path.basename))
		def permissive(perm, system):
			return '' if system else \
				'''
				<div class="sub_content_line one_line">
					<div class="sub_content_half_line font_bold">%s</div>
					<div class="sub_content_half_line align_right">%s</div>
				</div>
				''' % (_('Permissive shared dir?'),
					w.checkbox('permissive',
					"True", _(u"Yes"), checked=perm, instant_apply=True,
					instant_apply_action= \
						"/groups/edit_permissive/%s/"%group.name))

		data = '''

	<span id='sub_content_header'>
		<span id='sub_content_back'><img src='images/16x16/close.png'/></span>
		<span id='sub_content_title'>{sub_content_title}</span>
	</span>
	<div id='sub_content_area'>
		<div class='sub_content_line big_line'>
			<div class='sub_content_half_line font_bold'>{gid_text}<br/>
			<span class="sub_content_title_sub">{gid_sub}</span></div>
			<div class='sub_content_half_line align_right'>{gid}</div>
		</div>
		<div class='sub_content_line big_line'>
			<div class='sub_content_half_line font_bold'>{group_name_text}<br/>
			<span class="sub_content_title_sub">{group_name_sub}</span></div>
			<div class='sub_content_half_line align_right'>{group_name}</div>
		</div>
		{permissive}
		<div class='sub_content_line one_line'>
			<div class='sub_content_half_line font_bold'>{desc_text}</div>
			<div class='sub_content_half_line align_right'>{desc_input}</div>
		</div>
		{skel}
		<div class='sub_content_line sub_list'>
			<div class='sub_content_title'>{users_title}</div>
			<div class='sub_content_list'>
				{users_content}
			</div>
		</div>
		{users_sys_list}
	</div>'''.format(
			sub_content_title = _('Edit group %s') % name,
			gid_text = _('GID'),
			gid_sub = _('(immutable)'),
			gid = group.gidNumber,
			group_name_text = _('Group name'),
			group_name_sub = _('(immutable)'),
			group_name = group.name,
			permissive = permissive(group.permissive, group.is_system),
			desc_text = _('Group description'),
			desc_input = w.input('description', group.description,
				size=30, maxlength=256,	accesskey='D',
				instant_apply=True,
				instant_apply_action='/groups/edit_description/%s/' % name),
			skel = skel(group.groupSkel, group.is_system),
			users_title = _('Users'),
			users_content = make_users_list(group),
			users_sys_list = make_users_sys_list(is_super_admin, group)
			)

	except exceptions.LicornException, e:
		data = w.error(_("Group %s doesn't exist (%s, %s)!") % (name,
			"group = allgroups.groups[LMC.groups.name_to_gid(name)]", e))

	return (w.HTTP_TYPE_JSON, data)

@check_groups('edit_description')
def edit_description(uri, http_user, gname, desc, **kwargs):

	LMC.groups.by_name(gname).description =  w.my_unquote(desc)

	return (w.HTTP_TYPE_JSON, LMC.groups.by_name(gname).to_JSON())
def edit_permissive(uri, http_user, gname, permissive, **kwargs):

	group = LMC.groups.by_name(gname)

	if (permissive == "true"):
		group.permissive = True;
	else:
		group.permissive = False

	return (w.HTTP_TYPE_JSON, group.to_JSON())

@check_groups('edit_members')
def edit_members(uri, http_user, gname, users='', **kwargs):
	""" edit user groups function"""
	group = LMC.groups.by_name(gname)

	# TODO : check if group is a standard group ? normaly it is
	current_standard_users_list = group.members
	current_resp_users_list = group.responsible_group.members if group.responsible_group is not None else []
	current_guest_users_list = group.guest_group.members if group.guest_group is not None else []

	standard_users_list = []
	guest_users_list = []
	resp_users_list = []

	users_added_in_standard = []
	users_removed_in_standard = []
	users_added_in_resp = []
	users_removed_in_resp = []
	users_added_in_guest = []
	users_removed_in_guest = []

	errors = ""

	user_list = users.split(',')

	for login in user_list:
		if login != '':
			if login.find(LMC.configuration.groups.guest_prefix) != -1:
				user = LMC.users.by_login(login[4:])
				if not user in guest_users_list:
					guest_users_list.append(user)
			elif login.find(LMC.configuration.groups.resp_prefix) != -1:
				user = LMC.users.by_login(login[4:])
				if not user in resp_users_list:
					resp_users_list.append(user)
			else:
				user = LMC.users.by_login(login)
				if user not in standard_users_list:
					standard_users_list.append(user)

	#print "users in standard group : %s" % standard_users_list
	#print "users in guest group : %s" % guest_users_list
	#print "users in resp group : %s" % resp_users_list

	for list, list_ref, _group, tab_add, tab_del in (
		(resp_users_list, current_resp_users_list, group.responsible_group, users_added_in_resp, users_removed_in_resp),
		(standard_users_list, current_standard_users_list, group, users_added_in_standard, users_removed_in_standard),
		(guest_users_list, current_guest_users_list, group.guest_group, users_added_in_guest, users_removed_in_guest)):
		if _group is not None:
			for user in list_ref:
				if user not in list:
					try:
						_group.del_Users(users_to_del=[user])
						tab_del.append(user)
					except Exception, e:
						errors += "Error while removing member %s from " \
						"group %s (gid=%s) : %s" % (user.login, _group.name,
							_group.gid, e)

			for user in list:
				if user not in list_ref:
					try:
						_group.add_Users(users_to_add=[user], force=True)
						tab_add.append(user)
					except Exception, e:
						errors += "Error while adding member %s in " \
						"group %s (gid=%s) : %s" % (user.login, _group.name,
							_group.gid, e)

	#print "users removed from standard : %s" % ', '.join(u.login for u in users_removed_in_standard)
	#print "users added from standard : %s" % ', '.join(u.login for u in users_added_in_standard)
	#print "users removed from guest : %s" % ', '.join(u.login for u in users_removed_in_guest)
	#print "users added from guest : %s" % ', '.join(u.login for u in users_added_in_guest)
	#print "users removed from resp : %s" % ', '.join(u.login for u in users_removed_in_resp)
	#print "users added from resp : %s" % ', '.join(u.login for u in users_added_in_resp)

	return (w.HTTP_TYPE_JSON, None)




def make_users_list( group):

	def get_relationship(user, group):
		if user is None:
			return 'no_membership'

		# keep a copy here to avoid rebuilding from the weakrefs every "if".
		user_groups = user.groups


		if not group.is_system and group.responsible_group in user_groups:
			return 'resp'
		if group in user_groups:
			return 'member'
		if not group.is_system and group.guest_group in user_groups:
			return 'guest'

		#if none of them match return default value
		return 'no_membership'

	data = ''

	#if is_super_admin:
	#	_filter = filters.ALL
	#else:
	_filter = filters.STANDARD


	for user in LMC.users.select(_filter):
		#print "EEEEEEEEEEEEEEEEEEEEEEEEEEEEE %s" % group
		#print "EEEEEEEEEEEEEEEEEEEEEEEEEEEEE %s" % group.is_privilege
		#print LMC.groups[group]['name']

		if group.is_privilege or group.is_system:
			data += "<span class='click_item priv_item " \
			"instant_apply_click cat_%s' action='/groups/" \
			"edit_members/%s'>" % (get_relationship(user, group),
			group.name)
		else:
			data += "<span class='click_item instant_apply_click cat_%s" \
			"' action='/groups/edit_members/%s'>" % (get_relationship(user, group),
			group.name)
		data += '''	<input type='hidden' class='item_hidden_input' name='{relationship}' value='{user_login}'/>
					<span class='item_title'>{user_login}</span>
					<span class='item_relation'></span>
				</span>
			'''.format(
				user_login = user.login,
				relationship = get_relationship(user, group))

	return data

def make_users_sys_list(is_super_admin, group):
	if not is_super_admin:
		return ''

	def get_relationship(user, group):
		if user is None:
			return 'no_membership'

		# keep a copy here to avoid rebuilding from the weakrefs every "if".
		user_groups = user.groups


		if not group.is_system and group.responsible_group in user_groups:
			return 'resp'
		if group in user_groups:
			return 'member'
		if not group.is_system and group.guest_group in user_groups:
			return 'guest'

		#if none of them match return default value
		return 'no_membership'

	data = ''

	#if is_super_admin:
	#	_filter = filters.ALL
	#else:
	_filter = filters.SYSTEM


	for user in LMC.users.select(_filter):
		#print "EEEEEEEEEEEEEEEEEEEEEEEEEEEEE %s" % group
		#print "EEEEEEEEEEEEEEEEEEEEEEEEEEEEE %s" % group.is_privilege
		#print LMC.groups[group]['name']

		if group.is_privilege or group.is_system:
			data += "<span class='click_item priv_item " \
			"instant_apply_click cat_%s' action='/groups/" \
			"edit_members/%s'>" % (get_relationship(user, group),
			group.name)
		else:
			data += "<span class='click_item instant_apply_click cat_%s" \
			"' action='/groups/edit_members/%s'>" % (get_relationship(user, group),
			group.name)
		data += '''	<input type='hidden' class='item_hidden_input' name='{relationship}' value='{user_login}'/>
					<span class='item_title'>{user_login}</span>
					<span class='item_relation'></span>
				</span>
			'''.format(
				user_login = user.login,
				relationship = get_relationship(user, group))

	data_html = '''<div class='sub_content_line sub_list'>
			<div class='sub_content_title'>{users_sys_title}</div>
			<div class='sub_content_list'>
				{users_sys_content}
			</div>
		</div>'''.format(
			users_sys_title = _('System users:'),
			users_sys_content = data
		)


	return data_html


def main(uri, http_user, sort="name", order="asc", **kwargs):
	"""List all groups and provileges on the system, displaying them
	in a nice HTML page. """

	start = time.time()

	g = LMC.groups

	LMC.users.select(filters.STANDARD)

	tgroups  = {}
	totals   = {}

	title = _('Groups')
	data  = w.page_body_start(uri, http_user, None, title)

	if order == "asc": reverseorder = "desc"
	else:              reverseorder = "asc"

	group_list = '''
	<script language="javascript" type="text/javascript" src="/js/groups.js"></script>
	<center><img style="margin-top:30px;" src="/images/progress/ajax-loader.gif"/></center>'''

	data += w.main_content(group_list)

	sub_content=''

	data += w.sub_content(sub_content)

	page = w.page(title,
		data + w.page_body_end(w.total_time(start, time.time())))

	return (w.HTTP_TYPE_TEXT, page)

def get_main_content_JSON(uri, http_user, **kwargs):
	is_super_admin = LMC.users.by_login(http_user) in LMC.groups.by_name(
			LMC.configuration.defaults.admin_group).all_members

	if is_super_admin:
		_filter_priv = filters.SYSTEM
	else:
		_filter_priv = filters.PRIVILEGED

	obj_content = ('{'
	   '"lists" : [ '
	  		'{ "name" : "groups", '
	 			'"uri" : "groups", '
	 			'"title" : "%s", '
	 			'"items" : %s,'
	 			'"displayed" : "True",'
	 			'"main_attr" : "name",'
	 			'"massive_operations" : {'
					'"displayed" : "True",'
					'"items" : [ '
						'{ "icon_link" : "/images/24x24/mass_del.png",'
						'"id" : "groups_massive_delete"},'
						'{ "icon_link" : "/images/24x24/mass_skel.png",'
						'"id" : "groups_massive_skel"},'
						'{ "icon_link" : "/images/24x24/mass_export.png",'
						'"id" : "groups_massive_export"}'
					']'
				'},'
				'"search" : {'
					'"displayed" : "True"'
				'},'
				'"headers" : {'
					'"displayed" : "True",'
					'"items" : [ '
						'{ "name" : "select",'
						'"content" : "<input type=\'checkbox\' name=\'select\' id=\'groups_massive_select\'>",'
						'"sortable" : "False"},'
						'{ "name" : "permissive",'
						'"content" : "<img src=\'/images/24x24/locked_header.png\'/>",'
						'"sortable" : "True"},'
						'{ "name" : "name",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "description",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "gidNumber",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "skel",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "nav",'
						'"content" : "",'
						'"sortable" : "False"}'
					']'
				'}'
	 		'},'
	 		'{ "name" : "privs", '
	 			'"uri" : "groups", '
	 			'"title" : "%s", '
	 			'"items" : %s,'
	 			'"displayed" : "False",'
	 			'"main_attr" : "name",'
	 			'"massive_operations" : {'
					'"displayed" : "True",'
					'"items" : [ '
						'{ "icon_link" : "/images/24x24/mass_del.png",'
						'"id" : "privs_massive_delete"},'
						'{ "icon_link" : "/images/24x24/mass_export.png",'
						'"id" : "privs_massive_export"}'
					']'
				'},'
				'"search" : {'
					'"displayed" : "True"'
				'},'
				'"headers" : {'
					'"displayed" : "True",'
					'"items" : [ '
						'{ "name" : "select",'
						'"content" : "<input type=\'checkbox\' name=\'select\' id=\'privs_massive_select\'>",'
						'"sortable" : "False"},'
						'{ "name" : "is_priv",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "name",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "description",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "gidNumber",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "nav",'
						'"content" : "",'
						'"sortable" : "False"}'
					']'
				'}'
	 		'} ]'
	 '}' % (_(u'Groups'), LMC.groups.to_JSON(selected=LMC.groups.select(filters.STANDARD)),
		_(u"Name"), _(u"Description"), _(u"GID"), _(u"Skel"),
		_(u"System groups") if is_super_admin else _(u"Privileges"),
		LMC.groups.to_JSON(selected=LMC.groups.select(_filter_priv)),
		_(u"Priv."), _(u"Name"), _(u"Description"), _(u"GID")))

	return (w.HTTP_TYPE_JSON, obj_content)


