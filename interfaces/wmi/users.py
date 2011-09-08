# -*- coding: utf-8 -*-

import os, time, base64
from threading import current_thread

from licorn.foundations           import exceptions, hlstr, logging
from licorn.foundations.base      import Enumeration
from licorn.foundations.constants import filters
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces import *

from licorn.core import LMC
from licorn.interfaces.wmi.decorators import check_users

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi import utils as w


# messages functions : generate html output necessary when prompting
#TODO : if the user we want to delete is system, prompt warning
def delete_message(uri, http_user, login, **kwargs):
	""" return the message prompted when deleting a user """
	user = LMC.users.by_login(login)
	description = _("Are you sure you want to remove account "
		"<strong>%s</strong> ? <br/><br/>") % login
	description += _("User's <strong>personnal data</strong> "
		'(his/her HOME dir) will be <strong>archived</strong> in '
		'directory <code>%s</code> and members of group <strong>%s'
		'</strong> will be able to access it to operate an eventual'
		' recover.<br />However, you can decide to permanently '
		'remove it. <br/><br/>') % (
			LMC.configuration.home_archive_dir,
			LMC.configuration.defaults.admin_group)
	description += "<input type='checkbox' id='delete_user_make_" \
		"backup'/> <label for='delete_user_make_backup'> "
	description += _("Definitely remove")
	description += "account data (no archiving).</label> "
	return (w.HTTP_TYPE_JSON, description)
def lock_message(uri, http_user, login, **kwargs):
	""" return the message prompted when locking a user """
	user  = LMC.users.by_login(login)
	description = _(u"Do you really want to lock user {0} ?<br/><br/>"
					"This will prevent user to connect to network "
					"clients (thin ones, and Windows&reg;, {1}/Linux"
					"&reg; and Macintosh&reg; ones).").format(login,
						w.acr('GNU'))

	# TODO: move this in the extension
	if 'openssh' in LMC.extensions.keys():
		if login in LMC.groups.by_name(name=LMC.extensions.openssh.group).members:
			description += _("<br /><br /> But this will not block "
				"incoming %s network connections, if the user uses %s "
				"%s or %s public/private keys. To block ANY access to "
				"the system, <strong>remove him/her from %s group"
				"</strong>.") % (w.acr('SSH'), w.acr('SSH'),
					w.acr('RSA'), w.acr('DSA'),
					LMC.extensions.openssh.group)
			description += w.checkbox("remove_remotessh", "True",
				_("Remove user from group <code>remotessh</code> in "
				"the same time."),
				checked = True, accesskey = _('R'))

	return (w.HTTP_TYPE_JSON, description)
def skel_message(uri, http_user, login, **kwargs):
	""" return the message prompted when changing skel of a user """
	description = _("This will rebuild %s's desktop from scratch, "
		"with defaults icons and so on.<br /><br /><strong>The user "
		"must be disconnected for the operation to be completely "
		"successfull.</strong>" % login)
	description += _("<br /><br />Which skel do you want to apply? "
		"%s") % w.select("apply_skel", LMC.configuration.users.skels,
			func=os.path.basename, select_id='skel_to_apply')
	return (w.HTTP_TYPE_JSON, description)

#actions
# TODO: we need to check if passwords match before
def create(uri, http_user, password, password_confirm, loginShell=None,
	profile=None, login=None, gecos=None, groups=None, **kwargs):
	assert ltrace(TRACE_WMI, '> users.create(uri=%s, http_user=%s, '
		'password=%s, password_confirm=%s, loginShell=%s, profile=%s, '
		'login=%s, gecos=%s, groups=%s)' % (uri, http_user, password,
			password_confirm, loginShell, profile, login, gecos, groups))

	groups_text = w.my_unquote(groups) if groups is not None else ""
	profile     = w.my_unquote(profile) if profile is not None else ""
	shell       = w.my_unquote(loginShell) if loginShell is not None else ""
	gecos       = w.my_unquote(gecos) if gecos is not None else ""
	login       = w.my_unquote(login) if login is not None else ""
	groups_tab  = groups_text.split(',') if groups_text is not None else []

	user, password = LMC.users.add_User(
				login=login if login != '' else None,
				gecos=gecos if gecos != '' else None,
				password=password,
				in_groups=[ LMC.groups.by_name(g)
									for g in groups_text.split(',') ]
							if groups_text != '' else [],
				shell=LMC.configuration.users.default_shell
								if shell is None else shell,
				profile=LMC.profiles.by_gid(int(profile)))
	return (w.HTTP_TYPE_JSON, user.to_JSON())
@check_users('skel')
def skel(uri, http_user, login, sure=False, apply_skel=None, **kwargs):
	"""reapply a user's skel with confirmation."""
	assert ltrace(TRACE_WMI, '> users.skel(uri=%s, http_user=%s, '
		'login=%s, sure=%s, apply_skel=%s)' % (uri, http_user, login,
			sure, apply_skel))

	LMC.users.by_login(login).apply_skel(w.my_unquote(apply_skel))
	return (w.HTTP_TYPE_JSON, None)
@check_users('delete')
def delete(uri, http_user, login, sure, no_archive=False, **kwargs):
	"""remove user account."""
	assert ltrace(TRACE_WMI, '> users.delete(uri=%s, http_user=%s, '
	'login=%s, sure=%s, no_archive=%s)' % (uri, http_user, login,
		sure, no_archive))
	LMC.users.del_User(user=LMC.users.by_login(login),
		no_archive=no_archive);
	return (w.HTTP_TYPE_JSON, LMC.users.by_login(login).to_JSON())
@check_users('unlock')
def unlock(uri, http_user, login, **kwargs):
	"""unlock a user account password."""
	assert ltrace(TRACE_WMI, '> users.unlock(uri=%s, http_user=%s, '
		'login=%s)' % (uri, http_user, login))

	LMC.users.by_login(login).locked = False

	return (w.HTTP_TYPE_JSON, LMC.users.by_login(login).to_JSON())
@check_users('lock')
def lock(uri, http_user, login, sure=False, remove_remotessh=False, **kwargs):
	"""lock a user account password."""
	assert ltrace(TRACE_WMI, '> users.lock(uri=%s, http_user=%s, '
		'login=%s, sure=%s, remove_remotessh=%s)' % (uri, http_user,
		login, sure, remove_remotessh))

	LMC.users.by_login(login).locked   = True
	return (w.HTTP_TYPE_JSON, LMC.users.by_login(login).to_JSON())
def export(uri, http_user, type="", **kwargs):
	""" Export user accounts list.
			TODO !!
	"""

	"""
	title = _("Export user accounts list")
	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if type == "":
		description = _('''CSV file-format is used by spreadsheets and most '''
		'''systems which offer import functionnalities. XML file-format is a '''
		'''modern exchange format, used in soma applications which respect '''
		'''interoperability constraints.<br /><br />When you submit this '''
		'''form, your web browser will automatically offer you to download '''
		'''and save the export-file (it won't be displayed). When you're '''
		'''done, please click the “back” button of your browser.''')

		form_options = \
			_("Which file format do you want accounts to be exported to? %s") \
				% w.select("type", [ "CSV", "XML"])

		data += w.question(_("Please choose file format for export list"),
			description,
			yes_values   = [ _("Export >>"), "/users/export", "E" ],
			no_values    = [ _("<< Cancel"),  "/users/list",   "N" ],
			form_options = form_options)

		data += '</div><!-- end main -->'

		return (w.HTTP_TYPE_TEXT, w.page(title, data))

	else:
		LMC.users.select(filters.STANDARD)

		if type == "CSV":
			data = LMC.users.ExportCSV()
		else:
			data = LMC.users.ExportXML()

		return w.HTTP_TYPE_DOWNLOAD, (type, data)
	"""

# massive actions
def massive_import(uri, http_user, filename, firstname_col, lastname_col,
	group_col, **kwargs):
	#TODO
	pass
def massive_delete(uri, http_user, logins, sure, no_archive=False,
	**kwargs):
	"""remove several users account."""
	assert ltrace(TRACE_WMI, '> users.massive_delete(uri=%s, http_user=%s, '
		'logins=%s, sure=%s, no_archive=%s)' % (uri, http_user,
			logins, sure, no_archive))

	logins = w.my_unquote(logins)
	users_deleted = []
	for login in logins.split(',') if logins != '' else []:
		try:
			t = delete(uri, http_user, login, sure, no_archive=no_archive)
			users_deleted.append(login)

		except Exception, e:
			raise
	users_deleted = '["%s"]' % '","'.join(users_deleted)
	return (w.HTTP_TYPE_JSON, users_deleted)
def massive_skel(uri, http_user, logins, sure, apply_skel=None, **kwargs):
	"""reapply a user's skel with confirmation."""
	assert ltrace(TRACE_WMI, '> users.massive_skel(uri=%s, http_user=%s, '
		'logins=%s, sure=%s, apply_skel=%s)' % (uri, http_user,
		logins, sure, apply_skel))

	if apply_skel is None:
		apply_skel = LMC.configuration.users.default_skel

	logins = w.my_unquote(logins)
	for login in logins.split(',') if logins != '' else []:
		skel(uri, http_user, login, sure=sure, apply_skel=apply_skel, massive_operation=True)

	return (w.HTTP_TYPE_JSON, None)

# instant apply functions
@check_users('edit_gecos')
def edit_gecos(uri, http_user, login, gecos, **kwargs):
	""" edit the gecos of the user """
	assert ltrace(TRACE_WMI, '> users.edit_gecos(uri=%s, http_user=%s, '
		'login=%s, gecos=%s)' % (uri, http_user, login, gecos))

	user=LMC.users.by_login(login)
	user.gecos = w.my_unquote(gecos)
	return (w.HTTP_TYPE_JSON, user.to_JSON())
@check_users('edit_password')
def edit_password(uri, http_user, login, pwd, **kwargs):
	""" edit user password function"""
	assert ltrace(TRACE_WMI, '> users.edit_password(uri=%s, http_user=%s, '
		'login=%s, pwd=%s)' % (uri, http_user, login, '*'*len(pwd)))

	LMC.users.by_login(login).password = pwd
	return (w.HTTP_TYPE_JSON, None)
@check_users('edit_groups')
def edit_groups(uri, http_user, login, groups='', **kwargs):
	""" edit user groups function"""
	assert ltrace(TRACE_WMI, '> users.edit_group(uri=%s, http_user=%s, '
		'login=%s, groups=%s)' % (uri, http_user, login, groups))

	user = LMC.users.by_login(login)

	groups_wmi      = []
	user_groups     = user.groups
	del_groups_list = []
	add_groups_list = []

	groups = groups.split(',')

	for group in groups:
		if group != '':
			groups_wmi.append(LMC.groups.by_name(group))

	for group in user_groups:
		if group.name in groups or group.name in ('admin',
			LMC.configuration.defaults.admin_group):
			pass
		else:
			del_groups_list.append(group)

	for group in groups_wmi:
		if group not in user_groups:
			add_groups_list.append(group)

	assert ltrace(TRACE_WMI, 'initial list %s' % groups)
	assert ltrace(TRACE_WMI, 'initial group list %s' % user_groups)
	assert ltrace(TRACE_WMI, 'add list %s' % add_groups_list)
	assert ltrace(TRACE_WMI, 'del list %s' % del_groups_list)

	for group in del_groups_list:
		group.del_Users(users_to_del=[user])

	for group in add_groups_list:
		group.add_Users(users_to_add=[user], force=True)

	groups_added = ''
	groups_removed = ''
	separator = "<br /> &nbsp;&nbsp;&nbsp;"

	if add_groups_list != []:
		groups_added = _(u'Added: %s') % ', '.join(g.name for g in add_groups_list)

	if del_groups_list != []:
		groups_removed = _(u'Removed: %s') % ', '.join(g.name for g in del_groups_list)

	assert ltrace(TRACE_WMI, '< users.edit_groups()')

	return (w.HTTP_TYPE_JSON, None)
@check_users('edit_shell')
def edit_shell(uri, http_user, login, newshell, **kwargs):
	""" edit user shell function"""
	assert ltrace(TRACE_USERS, '> users.edit_shell(uri=%s, http_user=%s, '
		'login=%s, newshell=%s)' % (uri, http_user, login, newshell))

	LMC.users.by_login(login).shell = w.my_unquote(newshell)
	return (w.HTTP_TYPE_JSON, None)


# generation of html pages
groups_filters_lists_ids = (
	(filters.STANDARD, [_('Customize groups'),
		_('Available groups'), _('Affected groups')],
				'standard_groups'),
	(filters.PRIVILEGED, [_('Customize privileges'),
		_('Available privileges'), 	_('granted privileges')],
			'privileged_groups'),
	(filters.RESPONSIBLE, [_('Assign responsibilities'),
		_('Available responsibilities'), _('Assigned responsibilities')],
			'responsible_groups'),
	(filters.GUEST, [_('Propose invitations'),
		_('Available invitations'), _('Offered invitations')],
			'guest_groups') )
def edit(uri, http_user, login, **kwargs):
	"""Edit an user account, based on login."""

	user = LMC.users.by_login(login)
	try:
		try:
			profile = user.primaryGroup.profile.name
		except Exception:
			profile = _("Standard account")

		# keep it here to avoid reconstruction every time.
		user_groups = user.groups

		dbl_lists = {}
		for filter, titles, id in groups_filters_lists_ids:
			dest   = user_groups[:]
			source = [ g.name for g in LMC.groups.select(filter) ]
			for current in dest[:]:
				try: source.remove(current)
				except ValueError: dest.remove(current)
			dest.sort()
			source.sort()
			dbl_lists[filter] = w.multiselect(titles, id, source, dest)

		form_name = "user_edit_form"

		data = '''
		<div id='sub_content_header'>
			<div id='sub_content_back'><img src='images/16x16/close.png'/></div>
			<div id='sub_content_title'>{sub_content_title}</div>
		</div>
		<div id='sub_content_area'>
			<div class='sub_content_line big_line'>
				<div class='sub_content_half_line'>{uid_text}</div>
				<div class='sub_content_half_line align_right'>{uid_value}</div>
			</div>
			<div class='sub_content_line big_line'>
				<div class='sub_content_half_line'>{profile_text}</div>
				<div class='sub_content_half_line align_right'>{profile_value}</div>
			</div>
			<div class='sub_content_line one_line'>
				<div class='sub_content_half_line'>{gecos_text}</div>
				<div class='sub_content_half_line align_right'>{gecos_input}</div>
			</div>
			<div class='sub_content_line big_line'>
				<div class='sub_content_half_line'>{password_text}<br />{password_sub}</div>
				<div class='sub_content_half_line align_right'>{password_input}</div>
			</div>
			<div class='sub_content_line one_line'>
				<div class='sub_content_half_line'>{password_confirm_text}</div>
				<div class='sub_content_half_line align_right'>{password_confirm_input}</div>
			</div>
			<div class='sub_content_line big_line'>
				<div class='sub_content_half_line'>{shell_text}</div>
				<div class='sub_content_half_line align_right'>{shell_input}</div>
			</div>
			<div class='sub_content_line instant_apply_part' action="/users/edit_groups/{login}">
				<div class='sub_content_title'>{groups_title}</div>
				<div class='sub_content_list'>
					{groups_content}
				</div>
			</div>
			<div class='sub_content_line instant_apply_part' action="/users/edit_groups/{login}">
				<div class='sub_content_title'>{privs_title}</div>
				<div class='sub_content_list'>
					{privs_content}
				</div>
			</div>
			{groups_sys_list}
		</div>
		'''.format(
			sub_content_title= _("Edit account %s") % login,
			form_name = form_name,
			login = user.login,
			uid_text = _("<strong>UID</strong> (fixed)"),
			uid_value = user.uidNumber,
			identifier_text = _("<strong>Identifier</strong> (fixed)"),
			profile_text = _("<strong>Profile</strong> (fixed)"),
			profile_value = profile,
			gecos_text = _("<strong>Full name</strong>"),
			gecos_input = w.input('gecos', user.gecos, size=30,
				maxlength=64,	accesskey='N', instant_apply=True,
				instant_apply_action='/users/edit_gecos/%s/' % login),
			password_title = _("Password must be at least %d "
				"characters long. You can use all alphabet characters, "
				"numbers, special characters and punctuation signs, "
				"except '?!'.") %
					LMC.configuration.users.min_passwd_size,
			password_text = _("<strong>New password</strong>"),
			password_sub = _("(%d chars. min.)") % \
				LMC.configuration.users.min_passwd_size,
			password_input = w.input('password', '', size=30,
				maxlength=64, accesskey='P', password=True,
				instant_apply_password=True,
				instant_apply_action='/users/edit_password/%s/' % login),
			password_confirm_text=_("password confirmation."),
			password_confirm_input=w.input('password_confirm', '',
				size=30, maxlength=64, password=True,
				instant_apply_password=True,
				instant_apply_action='/users/edit_password/%s/' % login),
			shell_text = _("<strong>Shell</strong><br />(Unix command "
				"line interpreter)"),
			shell_input = w.select('loginShell',
				LMC.configuration.users.shells,	current=user.shell,
				func=os.path.basename, instant_apply=True,
				instant_apply_action='/users/edit_shell/%s/' % login),
			groups_title = _('Groups'),
			groups_content = make_groups_list(user),
			privs_title = _('Privileges'),
			privs_content = make_privs_list(user),
			groups_sys_list = make_groups_sys_list(http_user, user)
			)
	except exceptions.LicornException, e:
		data += w.error("Account %s does not exist (%s)!" % (
			login, "user = LMC.users.by_login(login)", e))

	return (w.HTTP_TYPE_JSON, data)

def view(uri, http_user, login, **kwargs):
	""" View a user account parameters, based on login."""

	user = LMC.users.by_login(login)
	data = ''
	try:
		try:
			profile = user.primaryGroup.profile.name

		except Exception:
			profile = _("Standard account")

		resps     = []
		guests    = []
		stdgroups = []
		privs     = []
		sysgroups = []

		for group in user.groups:
			if group.is_responsible:
				resps.append(group)
			elif group.is_guest:
				guests.append(group)
			elif group.is_standard:
				stdgroups.append(group)
			elif group.is_privilege:
				privs.append(group)
			else:
				sysgroups.append(group)

		exts_wmi_group_meths = [ ext._wmi_group_data
									for ext in LMC.extensions
									if 'groups' in ext.controllers_compat
									and hasattr(ext, '_wmi_group_data')
								]

		def html_build_group(group):
			return '''<tr>
	<td>
		<a href="/groups/view/{name}">{name}&nbsp;({gid})</a>
		<br />
		{description}
	</td>
	<td>{extensions_group_data}</td>
	</tr>'''.format(

				name=group.name,
				gid=group.gidNumber,
				description=group.description,
				extensions_group_data='\n'.join(wmi_meth(group,
								templates=(
									'%s<br/>%s', '&nbsp;'),
								hostname=kwargs['wmi_hostname'])
							for wmi_meth in exts_wmi_group_meths)
			)

		colspan = 2 + len(exts_wmi_group_meths)

		data += '''
		<span id='sub_content_header'>
			<span id='sub_content_title'>{sub_content_title}</span>
		</span>
		<div id="details">
			<form name="{form_name}" id="{form_name}"
					action="/users/view/{user.login}" method="post">
				<table>
					<tr>
						<td><strong>{uid_label}</strong><br />
						{immutable_label}</td>
						<td class="not_modifiable">{user.uidNumber}</td>
					</tr>
					<tr>
						<td><strong>{login_label}</strong><br />
						{immutable_label}</td>
						<td class="not_modifiable">{user.login}</td>
					</tr>
					<tr>
						<td><strong>{gecos_label}</strong></td>
						<td class="not_modifiable">{user.gecos}</td>
					</tr>
					{extensions_data}
					<tr class="group_listing">
						<td colspan="{colspan}" ><strong>{resp_label}</strong></td>
					</tr>
					{resp_group_data}
					<tr class="group_listing">
						<td colspan="{colspan}" ><strong>{std_label}</strong></td>
					</tr>
					{std_group_data}
					<tr class="group_listing">
						<td colspan="{colspan}" ><strong>{guest_label}</strong></td>
					</tr>
					{guest_group_data}
					<tr class="group_listing">
						<td colspan="{colspan}" ><strong>{priv_label}</strong></td>
					</tr>
					{priv_group_data}
					<tr class="group_listing">
						<td colspan="{colspan}" ><strong>{sys_label}</strong></td>
					</tr>
					{sys_group_data}
					<tr>
						<td>{back_button}</td>
						<td class="right">{print_button}</td>
					</tr>
				</table>
			</form>
		</div>
			'''.format(
				sub_content_title=_(u"User account %s's informations" % user.login),
				form_name="group_print_form",
				colspan=colspan,
				uid_label=_('UID'),
				login_label=_('Login'),
				immutable_label=_('immutable'),
				gecos_label=_('Gecos'),
				resp_label=_('Responsibilities'),
				std_label=_('Standard memberships'),
				guest_label=_('Invitations'),
				priv_label=_('Privileges'),
				sys_label=_('Other system memberships'),

				user=user,
				extensions_data='\n'.join('<tr><td><strong>%s</strong></td>'
					'<td class="not_modifiable">%s</td></tr>\n'
						% ext._wmi_user_data(user, hostname=kwargs['wmi_hostname'])
							for ext in LMC.extensions
								if 'users' in ext.controllers_compat
									and hasattr(ext, '_wmi_user_data')),

				resp_group_data='\n'.join([html_build_group(group)
														for group in resps]),
				std_group_data='\n'.join([html_build_group(group)
													for group in stdgroups]),
				guest_group_data='\n'.join([html_build_group(group)
														for group in guests]),
				priv_group_data='\n'.join([html_build_group(group)
														for group in privs]),
				sys_group_data='\n'.join([html_build_group(group)
													for group in sysgroups]),

				back_button=w.button(_('<< Go back'), "/users/list",
														accesskey=_('B')),
				print_button=w.submit('print', _('Print') + ' >>',
							onClick="javascript:window.print(); return false;",
							accesskey=_('P'))
				)

	except exceptions.LicornException, e:
		data += w.error("Account %s does not exist (%s)!" % (
			login, "user = LMC.users.by_login(login)", e))

	return (w.HTTP_TYPE_JSON, data)

def main(uri, http_user, sort="login", order="asc", select=None,
	**kwargs):
	""" display all users in a nice HTML page. """

	start = time.time()

	title = _("User accounts")
	data  = w.page_body_start(uri, http_user, None, title)

	# FIXME: turn this into "read-only" lock, else wmi fails to load the
	# list if one user / group is beiing checked.
	#LMC.users.acquire()
	#LMC.groups.acquire()
	#MC.profiles.acquire()


	users_list='''
	<script language="javascript" type="text/javascript" src="/js/users.js"></script>
	<center><img style="margin-top:30px;" src="/images/progress/ajax-loader.gif"/></center>'''

	data += w.main_content(users_list)
	data += w.sub_content('')

	page = w.page(title,
		data + w.page_body_end(w.total_time(start, time.time())))

	return (w.HTTP_TYPE_TEXT, page)

def new(uri, http_user, **kwargs):
	"""Generate a form to create a new user on the system."""

	g = LMC.groups
	p = LMC.profiles


	def gecos_input():
		return """
			<tr>
				<td><strong>%s</strong></td>
				<td class="right">%s</td>
			</tr>
			""" % (_("Full name"), w.input('gecos', "", size = 30,
					maxlength = 64, accesskey = 'N'))

	dbl_lists = {}

	for filter, titles, id in groups_filters_lists_ids:
		dest   = []
		source = [ group.name for group in LMC.groups.select(filter) ]
		source.sort()
		dbl_lists[filter] = w.multiselect(titles, id, source, dest)

	form_name = "user_edit"

	data = '''
	<span id='sub_content_header'>
		<span id='sub_content_back'><img src='images/16x16/close.png'/></span>
		<span id='sub_content_title'>{sub_content_title}</span>
	</span>
	<div id='sub_content_area'>
		<div class='sub_content_line one_line'>
			<div class='sub_content_half_line font_bold'>{profile_text}</div>
			<div class='sub_content_half_line align_right'>{profile_select}</div>
		</div>
		<div class='sub_content_line one_line'>
			<div class='sub_content_half_line font_bold'>{gecos_text}</div>
			<div class='sub_content_half_line align_right'>{gecos_input}</div>
		</div>
		<div class='sub_content_line big_line'>
			<div class='sub_content_half_line font_bold' title='{password_title}'>{password_text}<br/><span class="sub_content_title_sub">{password_sub}</span></div>
			<div class='sub_content_half_line align_right'>{password_input}</div>
		</div>
		<div class='sub_content_line one_line'>
			<div class='sub_content_half_line font_bold'>{password_confirm_text}</div>
			<div class='sub_content_half_line align_right'>{password_confirm_input}</div>
		</div>
		<div class='sub_content_line big_line'>
			<div class='sub_content_half_line font_bold' title='{identifier_title}'>{identifier_text}<br/><span class="sub_content_title_sub">{password_sub}</span></div>
			<div class='sub_content_half_line align_right'>{identifier_input}</div>
		</div>
		<div class='sub_content_line big_line'>
			<div class='sub_content_half_line font_bold'>{shell_text}<br/><span class="sub_content_title_sub">{shell_text_sub}</span></div>
			<div class='sub_content_half_line align_right'>{shell_input}</div>
		</div>
		<div class='sub_content_line'>
			<div class='sub_content_title'>{groups_title}</div>
			<div class='sub_content_list'>
				{groups_content}
			</div>
		</div>
		<div class='sub_content_line'>
			<div class='sub_content_title'>{privs_title}</div>
			<div class='sub_content_list'>
				{privs_content}
			</div>
		</div>
		<div class='sub_content_line last_line'>
				<div class='sub_content_half_line'>&nbsp;</div>
				<div class='sub_content_half_line align_right'>{save_button}</div>
		</div>
	</div>


	'''.format(
			sub_content_title=_(u"New account creation:"),
			form_name=form_name,
			profile_text=_(u"This user will be a"),
			profile_select = w.select('profile',  p.keys(),
				func = lambda x: LMC.profiles.by_gid(x).name,
				current = LMC.configuration.users.group,
				select_id = 'new_user_profile'),
			gecos_text = _(u"Full name"),
			gecos_input = w.input('gecos', '', size = 30, maxlength=64,
				accesskey = 'N', input_id='new_user_gecos'),
			password_title =  _(u"Password must be at least %d characters "
				u"long. You can use all alphabet characters, numbers, "
				u"special characters and punctuation signs, except '?!'."
				) % LMC.configuration.users.min_passwd_size,
			password_text = _(u'Password'),
			password_sub = _(u'(%d chars. min.)') %
				LMC.configuration.users.min_passwd_size,
			password_input = w.input('password', '', size=30,
				input_id='new_user_password', maxlength=64,
				accesskey = _('P'),password = True),
			password_confirm_text = _(u'Password confirmation.'),
			password_confirm_input = w.input('password_confirm', '',
				size=30, maxlength=64, password=True,
				input_id='new_user_confirm_password'),
			identifier_title = _(u"Identifier must be lowercase, "
				u"without accents or special characters (you can use "
				u"dots and carets). If you let this field "
				u"empty, identifier will be automaticaly guessed from "
				u"first name and last name."),
			identifier_text = _(u'Identifier'),
			identifier_input =  w.input('login', '', size=30,
				input_id='new_user_login', maxlength=64,
				accesskey = _('I')),
			shell_text = _(u'Shell'),
			shell_text_sub = _(u'(Unix command line interpreter)'),
			shell_input = w.select('loginShell',
				LMC.configuration.users.shells,
				current=LMC.configuration.users.default_shell,
				func=os.path.basename, select_id='new_user_shell'),
			groups_title = _(u'Groups'),
			groups_content = make_groups_list(None),
			privs_title = _(u'Privileges'),
			privs_content = make_privs_list(None),
			cancel_button = w.button('&lt;&lt;&nbsp;' + _('uCancel'),
				None, button_id="cancel_button"),
			save_button = w.submit('save', _(u'Record new user') +
				'&nbsp;&gt;&gt;', submit_id='save_user_button')
		)
	return (w.HTTP_TYPE_JSON, data)
# helper for html generation
def make_groups_list(user):

	def get_relationship(user, group):
		if user is None:
			return 'no_membership'

		# we hold the list here, because it is built from a list of weakref,
		# to avoid rebuilding it at each comparison.
		user_groups = user.groups

		if group in user_groups:
			return 'member'
		elif group.guest_group in user_groups:
			return 'guest'
		elif group.responsible_group in user_groups:
			return 'resp'
		else:
			return 'no_membership'

	data = ''
	for group in LMC.groups.select(filters.STANDARD):
		if user is None:
			data += "<span class='click_item'>"
		else:
			data += "<span class='click_item instant_apply_click' action='/users/edit_groups/%s'>" % user.login
		data += '''
				<input type='hidden' class='item_hidden_input' name='{relationship}' value='{group_name}'/>
				<span class='item_title'>{group_name}</span>
				<span class='item_relation'></span>
			</span>
		'''.format(
			group_name = group.name,
			relationship = get_relationship(user, group))

	return data
def make_privs_list(user):
	data = ''
	def get_relationship(user, group):
		if user is None:
			return 'no_membership'

		if group in user.groups:
			return 'member'
		else:
			return 'no_membership'

	for group in LMC.groups.select(filters.PRIVILEGED):
		if user is None:
			data += "<span class='click_item priv_item'>"
		else:
			data += "<span class='click_item priv_item instant_apply_click' action='/users/edit_groups/%s'>" % user.login

		data += '''	<input type='hidden' class='item_hidden_input' name='{relationship}' value='{group_name}'/>
					<span class='item_title'>{group_name}</span>
					<span class='item_relation'></span>
				</span>
			'''.format(
				group_name = group.name,
				relationship = get_relationship(user, group))

	return data

def make_groups_sys_list(http_user, user):
	is_super_admin = LMC.users.by_login(http_user) in LMC.groups.by_name(
			LMC.configuration.defaults.admin_group).all_members
	if not is_super_admin:
		return ''


	data = ''
	def get_relationship(user, group):
		if user is None:
			return 'no_membership'

		if group in user.groups:
			return 'member'
		else:
			return 'no_membership'

	privs = LMC.groups.select(filters.PRIVILEGED)
	filtered_groups = [ g for g in LMC.groups.select(filters.SYSTEM) if g not in privs ]

	for group in filtered_groups:
		if user is None:
			data += "<span class='click_item priv_item'>"
		else:
			data += "<span class='click_item priv_item instant_apply_click' action='/users/edit_groups/%s'>" % user.login

		data += '''	<input type='hidden' class='item_hidden_input' name='{relationship}' value='{group_name}'/>
					<span class='item_title'>{group_name}</span>
					<span class='item_relation'></span>
				</span>
			'''.format(
				group_name = group.name,
				relationship = get_relationship(user, group))

	data_return = '''<div class='sub_content_line instant_apply_part' action="/users/edit_groups/{login}">
				<div class='sub_content_title'>{group_sys_title}</div>
				<div class='sub_content_list'>
					{group_sys_content}
				</div>
			</div>'''.format(
				login = user.login,
				group_sys_title = _(u'System groups'),
				group_sys_content = data
			)

	return data_return

def get_main_content_JSON(uri, http_user, **kwargs):
	is_super_admin = LMC.users.by_login(http_user) in LMC.groups.by_name(
			LMC.configuration.defaults.admin_group).all_members

	#if is_super_admin:
	#	_filter = filters.SYSTEM
	#else:
	_filter = filters.STANDARD

	obj_content = ('{'
	   '"lists" : [ '
	  		'{ "name" : "users", '
	 			'"uri" : "users", '
	 			'"title" : "%s", '
	 			'"items" : %s,'
	 			'"displayed" : "True",'
	 			'"main_attr" : "login",'
	 			'"massive_operations" : {'
					'"displayed" : "True",'
					'"items" : [ '
						'{ "icon_link" : "/images/24x24/mass_del.png",'
						'"id" : "users_massive_delete"},'
						'{ "icon_link" : "/images/24x24/mass_skel.png",'
						'"id" : "users_massive_skel"},'
						'{ "icon_link" : "/images/24x24/mass_export.png",'
						'"id" : "users_massive_export"}'
					']'
				'},'
				'"search" : {'
					'"displayed" : "True"'
				'},'
				'"headers" : {'
					'"displayed" : "True",'
					'"items" : [ '
						'{ "name" : "select",'
						'"content" : "<input type=\'checkbox\' name=\'select\' id=\'users_massive_select\'>",'
						'"sortable" : "False"},'
						'{ "name" : "locked",'
						'"content" : "<img src=\'/images/24x24/locked_header.png\'/>",'
						'"sortable" : "True"},'
						'{ "name" : "login",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "gecos",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "uidNumber",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "profile",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "nav",'
						'"content" : "",'
						'"sortable" : "False"}'
					']'
				'}'
	 		'} ' % (_(u'User accounts'), 
				LMC.users.to_JSON(selected=LMC.users.select(_filter)),
				_('Login'), _('GECOS'), _('UID'), _('Skel')))

	if is_super_admin:
		 obj_content += (', { "name" : "users_system", '
				'"uri" : "users", '
				'"title" : "%s", '
				'"items" : %s,'
				'"displayed" : "False",'
				'"main_attr" : "login",'
				'"massive_operations" : {'
					'"displayed" : "True",'
					'"items" : [ '
						'{ "icon_link" : "/images/24x24/mass_del.png",'
						'"id" : "users_system_massive_delete"},'
						'{ "icon_link" : "/images/24x24/mass_skel.png",'
						'"id" : "users_system_massive_skel"},'
						'{ "icon_link" : "/images/24x24/mass_export.png",'
						'"id" : "users_system_massive_export"}'
					']'
				'},'
				'"search" : {'
					'"displayed" : "True"'
				'},'
				'"headers" : {'
					'"displayed" : "True",'
					'"items" : [ '
						'{ "name" : "select",'
						'"content" : "<input type=\'checkbox\' name=\'select\' id=\'users_system_massive_select\'>",'
						'"sortable" : "False"},'
						'{ "name" : "locked",'
						'"content" : "<img src=\'/images/24x24/locked_header.png\'/>",'
						'"sortable" : "True"},'
						'{ "name" : "login",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "gecos",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "uidNumber",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "profile",'
						'"content" : "%s",'
						'"sortable" : "True"},'
						'{ "name" : "nav",'
						'"content" : "",'
						'"sortable" : "False"}'
					']'
				'}'
			'}' % (_(u'System user accounts'), 
				LMC.users.to_JSON(selected=LMC.users.select(filters.SYSTEM)),
				_('Login'), _('GECOS'), _('UID'), _('Skel')))

	obj_content += '] }'

	return (w.HTTP_TYPE_JSON, obj_content)
