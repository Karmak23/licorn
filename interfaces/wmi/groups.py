# -*- coding: utf-8 -*-

import os, time
from gettext import gettext as _

from licorn.foundations         import exceptions, hlstr
from licorn.core.configuration  import LicornConfiguration
from licorn.core.users          import UsersController
from licorn.core.groups         import GroupsController
from licorn.core.profiles       import ProfilesController

from licorn.interfaces.wmi import utils as w

configuration = LicornConfiguration()
users         = UsersController(configuration)
groups        = GroupsController(configuration, users)
profiles      = ProfilesController(configuration, groups, users)

rewind = _("<br /><br />Go back with your browser, double-check data and validate the web-form.")
successfull_redirect = '/groups/list'

# private functions.
def __merge_multi_select(*lists):
	final = []
	for list in lists:
		if list == []: continue
		if type(list) == type(""):
			final.append(list)
		else:
			final.extend(list)
	return final
def ctxtnav(active = True):

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
def protected_group(name, complete=True):
	if complete:
		return groups.is_system_group(name)
	else:
		return groups.is_system_group(name) and not groups.is_privilege(name)

# locking and unlocking.
def unlock(uri, http_user, name, sure=False):
	""" Make a shared group dir permissive. """

	title = _("Make group %s permissive") % name

	if protected_group(name):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

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

		command = [ "sudo", "mod", "group", "--quiet", "--no-colors",
			"--name", name, "--set-permissive" ]

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to activate permissivenes on group
			<strong>%s</strong>!''') % name)
def lock(uri, http_user, name, sure=False):
	""" Make a group not permissive. """

	title = _("Make group %s not permissive") % name

	if protected_group(name):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

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

	else:		# we are sure, do it.
		command = [ "sudo", "mod", "group", "--quiet", "--no-colors",
			"--name", name, "--set-not-permissive" ]

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to remove permissiveness from group
				<strong>%s</strong>!''') % name)
def delete(uri, http_user, name, sure=False, no_archive=False, yes=None):
	""" Remove group and archive (or not) group shared dir. """

	# submit button, forget it.
	del yes

	title = _("Remove group %s") % name

	if protected_group(name):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	groups.reload()

	if not sure:
		data += w.question(_('''Are you sure you want to remove group
			<strong>%s</strong>?''') % name,
			_('''Group shared data will be archived in directory %s,
				and accessible to members of group %s for eventual
				recovery. However, you can decideto remove them
				permanently.''') % (configuration.home_archive_dir,
				configuration.defaults.admin_group),
			yes_values   = [ _("Remove") + ' >>',
				"/groups/delete/%s/sure" % name, _("R") ],
			no_values    = [ '<< ' + _("Cancel"),
				"/groups/list", _("N") ],
			form_options = w.checkbox("no_archive", "True",
				_("Definitely remove group shared data."),
				checked = False) )

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:		# we are sure, do it !
		command = [ 'sudo', 'del', 'group', '--quiet', '--no-colors',
			'--name', name ]

		if no_archive:
			command.extend(['--no-archive'])

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to remove group <strong>%s</strong>!''') % name)
def skel(req, name, sure=False, apply_skel=configuration.users.default_skel):
	""" TO BE IMPLEMENTED ! reapply a user's skel with confirmation."""

	users.reload()
	profiles.reload()
	groups.reload()

	title = _("Skeleton reapplying for group %s") % name

	if protected_group(name):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	if not sure:
		allusers  = u.UsersList(configuration)
		allgroups = g.GroupsList(configuration, allusers)

		description = _('''This will reset the desktops, icons and menus
			of all members of the group, according to the content of the
			skel you choose. This will NOT alter any of the user personnal
			data, nor the group shared data.''')

		pri_group = allgroups.groups[allusers.users[
			users.UsersList.login_to_uid(login)]['gidNumber']]['name']

		# liste des skels du profile en cours.
		def filter_skels(pri_group, sk_list):
			'''
			TODO: to be converted to licorn model
			if pri_group == configuration.mNames['RESPONSABLES_GROUP']:
				return filter(lambda x: x.rfind("/%s/" % configuration.mNames['RESPONSABLES_GROUP']) != -1, sk_list)
			elif pri_group == configuration.mNames['USAGERS_GROUP']:
				return filter(lambda x: x.rfind("/%s/" % configuration.mNames['USAGERS_GROUP']) != -1, sk_list)
			else:
			'''
			return sk_list

		form_options = _('''Which skel do you wish to reapply to members of
			this group? %s''') \
			% w.select("apply_skel",
			filter_skels(pri_group, configuration.users.skels),
			func=os.path.basename)

		data += w.question( _('''Are you sure you want to reapply this skel to
			all of the members of %s?''') % login,
			description,
			yes_values   = [ _("Apply") + ' >>',
				"/users/skel/%s/sure" % login, _("A") ],
			no_values    = [ '<< ' + _("Cancel"),
				"/groups/list", _("N") ],
			form_options = form_options)

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:
		# we are sure, do it !
		command = [ "sudo", "mod", "user", "--quiet", "--no-colors",
			"--login", login, '--apply-skel', skel ]

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to apply skel %s to members of group %s.''') % (
				os.path.basename(apply_skel), login))
def new(uri, http_user):
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
		w.select('skel',  configuration.users.skels,
		current = configuration.users.default_skel,
		func = os.path.basename),
		_('Permissive shared dir?'),
		w.checkbox('permissive', "True", _("Yes"), accesskey=_('P')),
		w.button(_('<< Cancel'), "/groups/list", accesskey=_('N')),
		w.submit('create', _('Create') + ' >>',
		onClick="selectAllMultiValues('%s');" % form_name, accesskey=_('T'))
		)
	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def create(uri, http_user, name, description=None, skel="", permissive=False,
	create=None):

	title = _("Creating group %s") % name
	data = '%s<h1>%s</h1><br />' % (w.backto(), title)

	# web button (submit)
	del create

	command = [ 'sudo', 'add', 'group', '--quiet', '--no-colors',
		'--name', name, '--skel', skel ]

	if description:
		command.extend([ '--description', description ])

	if permissive:
		command.append('--permissive')

	return w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_('''Failed to create group %s!''') % name)
def view(uri, http_user, name):
	"""Prepare a group view to be printed."""

	users.reload()
	groups.reload()

	title = _("Details of group %s") % name

	if protected_group(name, complete=False):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	u = users.users
	g = groups.groups

	try:
		group   = g[groups.name_to_gid(name)]
		members = list(groups.all_members(name))

		if members != []:
			members.sort()

			members_html = '''
			<h2>%s</h2>
			<div style="text-align:left;">%s</div>
			<table class="group_members">
			<tr>
				<th><strong>%s</strong></th>
				<th><strong>%s</strong></th>
				<th><strong>%s</strong></th>
			</tr>
			''' % (
				_('Members'),
				_('(ordered by login)'),
				_('Full Name'),
				_('Identifier'),
				_('UID')
				)
			def user_line(login):
				uid = users.login_to_uid(login)
				return '''<tr>
					<td>%s</td>
					<td>%s</td>
					<td>%s</td>
					</tr>''' % (
					u[uid]['gecos'],
					login,
					uid
					)

			members_html += "\n".join(map(user_line, members)) + '</table>'
		else:
			members_html = "<h2>%s</h2>" % _('No members in this group.')

		if not groups.is_system_group(name):
			resps = list(
				groups.all_members(configuration.groups.resp_prefix + name))

			if resps != []:
				resps.sort()
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
			"\n".join(map(user_line, resps))
			)

			else:
				resps_html = "<h2>%s</h2>" % \
					_('No responsibles for this group.')

			guests = list(
				groups.all_members(configuration.groups.guest_prefix + name))

			if guests != []:
				guests.sort()
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
			"\n".join(map(user_line, guests))
			)
			else:
				guests_html = "<h2>%s</h2>" % _('No guests in this group.')

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
				_('GID'), _('immutable'), group['gidNumber'],
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
			name, "group = g[groups.name_to_gid(name)]", e))

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def edit(uri, http_user, name):
	"""Edit a group."""

	users.reload()
	groups.reload()

	u = users.users
	g = groups.groups

	title = _("Editing group %s") %  name

	if protected_group(name, complete=False):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	try:
		group     = g[groups.name_to_gid(name)]
		sys       = groups.is_system_group(name)
		dbl_lists = {}

		if sys:
			groups_filters_lists_ids = [
				(name, [ _('Manage members'), _('Users not yet members'),
				_('Current members') ], 'members' )
				]

			#	,
			#	(configuration.groups.resp_prefix + name, None, '&#160;' ),
			#	(configuration.groups.guest_prefix + name, None, '&#160;' )
		else:
			groups_filters_lists_ids = (
				(name,
					[_('Manage members'),
					_('Users not yet members'),
					_('Current members')],
					'members'),
				(configuration.groups.resp_prefix + name,
					[_('Manage responsibles'),
					_('Users not yet responsibles'),
					_('Current responsibles')],
					'resps'),
				(configuration.groups.guest_prefix + name,
					[_('Manage guests'),
					_('Users not yet guests'),
					_('Current guests')],
					'guests') )

		for (gname, titles, id) in groups_filters_lists_ids:
			if titles is None:
				dbl_lists[gname] = id
			else:
				users.Select(users.FILTER_STANDARD)
				dest   = list(group['memberUid'])
				source = [ u[uid]['login'] for uid in users.filtered_users ]
				for current in group['memberUid']:
					try:
						source.remove(current)
					except ValueError:
						dest.remove(current)
				dest.sort()
				source.sort()
				dbl_lists[gname] = w.doubleListBox(titles, id, source, dest)

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
					w.select('skel', configuration.users.skels,
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
					"True", "Oui", checked = perm ))

		form_name = "group_edit_form"

		if sys:
			data_rsp_gst =''
		else :
			data_rsp_gst = '''
<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>
				<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>

			''' % (
			_('Group responsibles') ,
			dbl_lists[configuration.groups.resp_prefix+name],
			_('Group guests'),
			dbl_lists[configuration.groups.guest_prefix+name]
			)

		data += '''<div id="edit_form">
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

				<script type="text/javascript">
					Event.observe(window, 'load', loadAccordions, false);
					function loadAccordions() {
						var prout = new accordion("my-accordion");
					//prout.activate($$("#my-accordion .accordion_toggle")[0]);
					}
				</script>

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
			group['gidNumber'],
			_('Group name'), _('(immutable)'),
			group['name'],
			permissive(group['permissive'], sys),
			_('Group description'),
			descr(group['description'], sys),
			skel(group['groupSkel'], sys),
			_('Group members'),
				dbl_lists[name],
			data_rsp_gst,
			w.button('<< ' + _('Cancel'), "/groups/list", accesskey=_('N')),
			w.submit('record', _('Record') + ' >>',
			onClick="selectAllMultiValues('%s');" % form_name,
			accesskey=_('R'))
			)

	except exceptions.LicornException, e:
		data += w.error(_("Group %s doesn't exist (%s, %s)!") % (name,
			"group = allgroups.groups[groups.name_to_gid(name)]", e))

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def record(uri, http_user, name, skel=None, permissive=False, description=None,
	members_source    = [], members_dest = [],
	resps_source      = [], resps_dest   = [],
	guests_source     = [], guests_dest  = [],
	record = None):
	""" Record group modification changes."""

	# web submit -> forget it
	del record

	title   = _("Modifying group %s") % name

	if protected_group(name, complete=False):
		return w.forgery_error(title)

	data    = '%s<h1>%s</h1>' % (w.backto(), title)
	command = [ 'sudo', 'mod', 'group', '--quiet', '--no-colors',
		'--name', name ]

	if description:
		command.extend(["--description", description])

	if skel:
		command.extend(["--skel", skel])

	# fix #194
	if permissive:
		command.extend([ '--permissive' ])
	else:
		command.extend([ '--not-permissive' ])

	add_members = ','.join(__merge_multi_select(members_dest))
	del_members = ','.join(__merge_multi_select(members_source))

	add_resps = ','.join(__merge_multi_select(resps_dest))
	del_resps = ','.join(__merge_multi_select(resps_source))

	add_guests = ','.join(__merge_multi_select(guests_dest))
	del_guests = ','.join(__merge_multi_select(guests_source))

	for (var, cmd) in (
		(add_members, "--add-users"),
		(del_members, "--del-users"),
		(add_resps,   "--add-resps"),
		(del_resps,   '--del-resps'),
		(add_guests,  "--add-guests"),
		(del_guests,  '--del-guests') ):
		if var != "":
			command.extend([ cmd, var ])

	return w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_('''Failed to modify one or more parameter of group %s!''') % name)
def main(uri, http_user, sort = "name", order = "asc"):
	"""List all groups and provileges on the system, displaying them
	in a nice HTML page. """

	start = time.time()

	users.reload()
	groups.reload()
	#profiles.reload()

	g = groups.groups

	users.Select(users.FILTER_STANDARD)

	tgroups  = {}
	totals   = {}

	title = _('Groups')
	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if order == "asc": reverseorder = "desc"
	else:              reverseorder = "asc"

	data += '<table>\n		<tr>\n'

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
		<th><img src="/images/sort_%s.gif" alt="%s" />&#160;
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
		(groups.FILTER_STANDARD, _('Groups')),
		(groups.FILTER_PRIVILEGED, _("Privileges")) ):

		tgroups  = {}
		ordered  = {}
		totals[filter_name] = 0
		groups.Select(filter)

		for gid in groups.filtered_groups:
			group = groups.groups[gid]
			name  = group['name']

			tgroups[gid] = {
				'name'        : name,
				'description' : group['description'] + name,
				'skel'        : group['groupSkel'] + name,
				'permissive'  : str(group['permissive']) + name
				}
			totals[filter_name] += 1

			# index on the column choosen for sorting, and keep trace of the uid
			# to find account data back after ordering.

			ordered[hlstr.validate_name(tgroups[gid][sort])] = gid

			tgroups[gid]['memberUid'] = []
			for member in group['memberUid']:
				if not users.is_system_login(member):
					tgroups[gid]['memberUid'].append(
						users.users[users.login_to_uid(member)])

			if not groups.is_system_gid(gid):
				for prefix in (
					configuration.groups.resp_prefix,
					configuration.groups.guest_prefix):
					tgroups[gid][prefix + 'memberUid'] = []
					for member in \
						groups.groups[groups.name_to_gid(
							prefix + name)]['memberUid']:
						if not users.is_system_login(member):
							tgroups[gid][prefix + 'memberUid'].append(
								users.users[users.login_to_uid(member)])

		gkeys = ordered.keys()
		gkeys.sort()
		if order == "desc": gkeys.reverse()

		def html_build_group(index, tgroups = tgroups ):
			gid   = ordered[index]
			name  = g[gid]['name']
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
				name, g[gid]['description'], name,
				name, g[gid]['description'], g[gid]['description'],
				name, g[gid]['groupSkel'])

			if groups.is_system_gid(gid):
				html_data += '<td>&#160;</td>'
			else:
				if g[gid]['permissive']:
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

			for (keyname, text) in (
				('memberUid', _('Current members')),
				('rsp-memberUid', _('Current responsibles')),
				('gst-memberUid', _('Current guests')) ):
				if tgroups[gid].has_key(keyname):
					accounts = {}
					uordered = {}
					for member in tgroups[gid][keyname]:
						uid = member['uidNumber']
						accounts[uid] = {
							'login': member['login'],
							'gecos': member['gecos'],
							'gecos_sort': member['gecos'] + member['login']
							}
						uordered[hlstr.validate_name(
							accounts[uid]['gecos_sort'], aggressive=True)] = uid

					memberkeys = uordered.keys()
					memberkeys.sort()
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

			if groups.is_system_gid(gid):
				html_data += '<td colspan="1">&#160;</td></tr>\n'
			else:
				html_data += '''
					<!-- TODO: implement skel reapplying for all users of
					curent group
					<td class="user_action">
					<a href="/users/skel/%s" title="%s" class="reapply-skel">
					<span class="reapply-skel">&nbsp;&nbsp;&nbsp;&nbsp;</span>
					</a>
					</td>
					-->
					<td class="user_action">
					<a href="/groups/delete/%s" title="%s" class="delete-entry">
					<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span>
					</a>
					</td>
				</tr>
						''' % (name, _('''This will rebuild his/her desktop
						from scratch, with defaults icons and so on.
						<br /><br />The user must be disconnected for the
						operation to be completely successfull.'''),
						name,
						_('''Definitely remove this group from system.'''))
			return html_data

		data += '<tr><td class="group_class" colspan="8">%s</td></tr>\n%s' % (
			filter_name, ''.join(map(html_build_group, gkeys)))

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
