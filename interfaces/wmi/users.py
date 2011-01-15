# -*- coding: utf-8 -*-

import os, time
from gettext import gettext as _

from licorn.foundations           import exceptions, hlstr
from licorn.foundations.constants import filters

from licorn.core import LMC

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi import utils as w

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

rewind = _('''<br /><br />Go back with your browser,'''
	''' double-check data and validate the web-form.''')
successfull_redirect = '/users/list'

# private functions.

def ctxtnav(active=True):

	if active:
		disabled = '';
		onClick  = '';
	else:
		disabled = 'un-clickable';
		onClick  = 'onClick="javascript: return(false);"'

	return '''
	<div id="ctxtnav" class="nav">
		<h2>Context Navigation</h2>
		<ul>
			<li><a href="/users/new" title="%s" %s class="%s">
			<div class="ctxt-icon %s" id="icon-add">%s</div></a></li>
			<li><a href="/users/import" title="%s" %s class="%s">
			<div class="ctxt-icon %s" id="icon-import">%s</div></a></li>
			<li><a href="/users/export" title="%s" %s class="%s">
			<div class="ctxt-icon %s" id="icon-export">%s</div></a></li>
		</ul>
	</div>
	''' % (
		_("Add a new user account on the system."),
			onClick, disabled, disabled,
		_("Add an account"),
		_("Import new user accounts from a CSV-delimited file."),
			onClick, disabled, disabled,
		_("Import accounts"),
		_("Export current user accounts list to a CSV or XML file."),
			onClick, disabled, disabled,
		_("Export accounts")
		)
def protected_user(login, users):
	return LMC.users.is_system_login(login)
def export(uri, http_user, type="", yes=None, users=None, **kwargs):
	""" Export user accounts list."""

	# submit button; forget it.
	del yes

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
		LMC.users.Select(filters.STANDARD)

		if type == "CSV":
			data = LMC.users.ExportCSV()
		else:
			data = LMC.users.ExportXML()

		return w.HTTP_TYPE_DOWNLOAD, (type, data)
def delete(uri, http_user, login, sure=False, no_archive=False, yes=None,
	configuration=None, users=None, **kwargs):
	"""remove user account."""

	# form submit button, forget it.
	del yes

	title = _("Remove user account %s") % login

	if protected_user(login, users):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if not sure:
		data += w.question(
			_("Are you sure you want to remove account <strong>%s</strong>?") \
			% login,
			_('''User's <strong>personnal data</strong> (his/her HOME dir) '''
			'''will be <strong>archived</strong> in directory <code>%s</code>'''
			''' and members of group <strong>%s</strong> will be able to '''
			''' access it to operate an eventual recover.<br />However, you '''
			'''can decide to permanently remove it.''') % (
				LMC.configuration.home_archive_dir,
				LMC.configuration.defaults.admin_group),
			yes_values   = \
				[ _("Remove >>"), "/users/delete/%s/sure" % login, _("R") ],
			no_values    = \
				[ _("<< Cancel"),   "/users/list",                 _("C") ],
			form_options = w.checkbox("no_archive", "True",
				_("Definitely remove account data (no archiving)."),
				checked = False) )

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:
		# we are sure, do it !
		command = [ 'sudo', 'del', 'user', '--quiet', '--no-colors',
			'--login', login ]

		if no_archive:
			command.extend(['--no-archive'])

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to remove account <strong>%s</strong>!''') % login)
def unlock(uri, http_user, login, users=None, **kwargs):
	"""unlock a user account password."""

	title = _("Unlock account %s") % login

	if protected_user(login, users):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if LMC.users.is_system_login(login):
		return (w.HTTP_TYPE_TEXT, w.page(title,
			w.error(_("Failed to unlock account"),
			[ _("alter system account.") ],
			_("insufficient permission to perform operation.")) \
			+ w.page_body_end()))

	command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login",
		login, "--unlock" ]

	return w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_("Failed to unlock account <strong>%s</strong>!") % login)
def lock(uri, http_user, login, sure=False, remove_remotessh=False, yes=None,
	users=None, configuration=None, groups=None, **kwargs):
	"""lock a user account password."""

	# submit button: forget it.
	del yes

	title = _("Lock account %s") % login

	if protected_user(login, users):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if not sure:
		description = _('''This will prevent user to connect to network '''
			'''clients (thin ones, and Windows&reg;, %s/Linux&reg; and '''
			'''Macintosh&reg; ones).''') % w.acr('GNU')

		if LMC.configuration.ssh.enabled :
			if login in LMC.groups.all_members(LMC.configuration.ssh.group):
				description += _('''<br /><br />
					But this will not block incoming %s network connections, '''
					'''if the user uses %s %s or %s public/private keys. To '''
					'''block ANY access to the system, <strong>remove him/her'''
					''' from %s group</strong>.''') % (w.acr('SSH'),
					w.acr('SSH'), w.acr('RSA'), w.acr('DSA'),
					LMC.configuration.ssh.group)
				form_options = w.checkbox("remove_remotessh", "True",
					_('''Remove user from group <code>remotessh</code> in '''
					'''the same time.'''),
					checked = True, accesskey = _('R'))
			else:
				form_options = None
		else:
			form_options = None

		data += w.question(
			_("Are you sure you want to lock account <strong>%s</strong>?") % \
			login,
			description,
			yes_values   = \
				[ _("Lock >>"), "/users/lock/%s/sure" % login, _("L") ],
			no_values    = \
				[ _("<< Cancel"),     "/users/list",           _("C") ],
			form_options = form_options)

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:
		# we are sure, do it !
		command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login",
			login, "--lock" ]

		if LMC.configuration.ssh.enabled and remove_remotessh:
			command.extend(['--del-groups', LMC.configuration.ssh.group])

		data += w.page_body_end()

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_("Failed to lock account <strong>%s</strong>!") % login)
def skel(uri, http_user, login, sure=False, apply_skel=None, yes=None,
	configuration=None, users=None, **kwargs):
	"""reapply a user's skel with confirmation."""

	# submit button; forget it.
	del yes

	title = _("Reapply skel to user account %s") % login

	if protected_user(login, users):
		return w.forgery_error(title)

	if apply_skel is None:
		apply_skel = LMC.configuration.users.default_skel

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if not sure:
		description = _('''This will rebuild his/her desktop from scratch, '''
		'''with defaults icons and so on.<br /><br />The user must be '''
		'''disconnected for the operation to be completely successfull.''')

		form_options = _("Which skel do you want to apply? %s") % \
			w.select("apply_skel", LMC.configuration.users.skels,
			func=os.path.basename)

		data += w.question(_('''Are you sure you want to apply this skel to'''
			''' account <strong>%s</strong>?''') % login,
			description,
			yes_values = [ _("Apply") + "@nbsp;&gt;&gt;",
				"/users/skel/%s/sure" % login, _("A") ],
			no_values = [ "&lt;&lt;&nbsp;" + _("Cancel"),
				"/users/list", _("C") ],
			form_options = form_options)

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:
		# we are sure, do it !
		command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login",
			login, '--apply-skel', apply_skel ]

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to apply skel <strong>%s</strong> on user
			account <strong>%s</strong>!''') % (os.path.basename(apply_skel),
				login))
def new(uri, http_user, configuration=None, users=None, groups=None,
	profiles=None, **kwargs):
	"""Generate a form to create a new user on the system."""

	g = LMC.groups
	p = LMC.profiles

	title = _("New user account")
	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	def profile_input():

		#TODO: To be rewritten ?
		return """
			<tr>
				<td><strong>%s</strong></td>
				<td class="right">
%s
				</td>
			</tr>
			""" % (_("This user is a"), w.select('profile',  p.keys(),
				func = lambda x: p[x]['name']))
	def gecos_input():
		return """
			<tr>
				<td><strong>%s</strong></td>
				<td class="right">%s</td>
			</tr>
			""" % (_("Full name"), w.input('gecos', "", size = 30,
					maxlength = 64, accesskey = 'N'))
	def shell_input():
		return w.select('loginShell',  LMC.configuration.users.shells,
			current=LMC.configuration.users.default_shell, func=os.path.basename)

	dbl_lists = {}
	for filter, titles, id in groups_filters_lists_ids:
		dest   = []
		source = [ g[gid]['name'] for gid in LMC.groups.Select(filter) ]
		source.sort()
		dbl_lists[filter] = w.doubleListBox(titles, id, source, dest)

	form_name = "user_edit"

	data += '''
	<script type="text/javascript" src="/js/jquery.js"></script>
	<script type="text/javascript" src="/js/accordeon.js"></script>
	
	<div id="edit_form">
	<form name="%s" id="%s" action="/users/create" method="post">
		<table>
%s
%s
			<tr>
				<td><strong><a href="#" class="help" title="%s">%s</a></strong>
					%s</td>
				<td class="right">%s</td>
			</tr>
			<tr>
				<td><strong>%s</strong></td>
				<td class="right">%s</td>
			</tr>
			<tr>
				<td><strong><a href="#" class="help" title="%s">%s</a></strong>
					</td>
				<td class="right">%s</td>
			</tr>
			<tr>
				<td>%s</td>
				<td class="right">%s</td>
			</tr>
			<tr>
				<td colspan="2" id="my-accordion">
					<h2 class="accordion_toggle">≫&nbsp;%s</h2>
					<div class="accordion_content">%s</div>
					<h2 class="accordion_toggle">≫&nbsp;%s</h2>
					<div class="accordion_content">%s</div>
					<h2 class="accordion_toggle">≫&nbsp;%s</h2>
					<div class="accordion_content">%s</div>
					<h2 class="accordion_toggle">≫&nbsp;%s</h2>
					<div class="accordion_content">%s</div>
				</td>
			</tr>
			<tr>
				<td>%s</td>
				<td class="right">%s</td>
			</tr>
		</table>
	</form>
	''' % ( form_name, form_name,
		profile_input(),
		gecos_input(),
		_('''Password must be at least %d characters long. You can use all '''
		'''alphabet characters, numbers, special characters and punctuation '''
		'''signs, except '?!'.''') % LMC.configuration.users.min_passwd_size,
		_("Password"), _("(%d chars. min.)") % LMC.configuration.users.min_passwd_size,
		w.input('password', "", size = 30, maxlength = 64, accesskey = _('P'),
			password = True),
		_("Password confirmation."), w.input('password_confirm', "", size = 30,
			maxlength = 64, password = True ),
		_('''Identifier must be lowercase, without accents or special '''
		'''characters (you can use dots and carets).<br /><br />'''
		'''If you let this field empty, identifier will be automaticaly '''
		'''guessed from first name and last name.'''),
		_("Identifier"), w.input('login', "", size = 30, maxlength = 64,
			accesskey = _('I')),
		_("<strong>Shell</strong><br />(Unix command line interpreter)"),
		shell_input(),
		_('Groups'), dbl_lists[filters.STANDARD],
		_('Privileges'), dbl_lists[filters.PRIVILEGED],
		_('Responsibilities'), dbl_lists[filters.RESPONSIBLE],
		_('Invitations'), dbl_lists[filters.GUEST],
		w.button('&lt;&lt;&nbsp;' + _('Cancel'), "/users/list"),
		w.submit('create', _('Create') + '&nbsp;&gt;&gt;',
			onClick = "selectAllMultiValues('%s');" % form_name)
		)

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def create(uri, http_user, password, password_confirm, loginShell=None,
	profile=None, login="", gecos="", standard_groups_dest=[],
	privileged_groups_dest=[], responsible_groups_dest=[],
	guest_groups_dest=[], standard_groups_source=[],
	privileged_groups_source=[], responsible_groups_source=[],
	guest_groups_source=[],	create=None, configuration=None, users=None,
	profiles=None, **kwargs):

	# forget it; useless
	del create

	title = _("New user account %s") % login
	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	if password != password_confirm:
		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.error(_("Passwords do not match!%s") % rewind)))

	if len(password) < LMC.configuration.users.min_passwd_size:
		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.error(_("Password must be at least %d characters long!%s")\
				% (LMC.configuration.users.min_passwd_size, rewind))))

	if loginShell == None:
		loginShell = LMC.configuration.users.default_shell

	command = [ "sudo", "add", "user", '--quiet', '--no-colors',
		'--password', password ]

	for value, argument in (
		(loginShell, '--shell'),
		(profile, '--profile'),
		(gecos, '--gecos')):
		if value is not None and value != '':
			command.extend([ argument, value ])

	add_groups = ','.join(w.merge_multi_select(
							standard_groups_dest,
							privileged_groups_dest,
							responsible_groups_dest,
							guest_groups_dest))

	if add_groups != '':
		command.extend([ '--add-to-groups', add_groups ])

	if login != '':
		command.extend(['--login', login])
	elif gecos != '':
		command.extend([ '--login',
			hlstr.validate_name(gecos).replace('_', '.').rstrip('.') ])
	else:
		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.error(_("GECOS and login can't be both empty!%s") %
				rewind)))

	return w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_('''Failed to create account <strong>%s</strong>!''') % login)
def edit(uri, http_user, login, configuration=None, users=None, groups=None,
	profiles=None, **kwargs):
	"""Edit an user account, based on login."""

	title = _('Edit account %s') % login

	if protected_user(login, users):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	try:
		user = LMC.users.users[LMC.users.login_to_uid(login)]

		try:
			profile = \
				LMC.profiles.profiles[
					LMC.groups.groups[user['gidNumber']]['name']
					]['name']
		except KeyError:
			profile = _("Standard account")

		dbl_lists = {}
		for filter, titles, id in groups_filters_lists_ids:
			dest   = list(user['groups'][:])
			source = [ LMC.groups.groups[gid]['name']
				for gid in LMC.groups.Select(filter) ]
			for current in dest[:]:
				try: source.remove(current)
				except ValueError: dest.remove(current)
			dest.sort()
			source.sort()
			dbl_lists[filter] = w.doubleListBox(titles, id, source, dest)

		form_name = "user_edit_form"

		data += '''
		<script type="text/javascript" src="/js/jquery.js"></script>
		<script type="text/javascript" src="/js/accordeon.js"></script>
		
		<div id="edit_form">
<form name="%s" id="%s" action="/users/record/%s" method="post">
	<table id="user_account">
		<tr>
			<td>%s</td>
			<td class="not_modifiable right">%d</td>
		</tr>
		<tr>
			<td>%s</td>
			<td class="not_modifiable right">%s</td>
		</tr>
		<tr>
			<td>%s</td>
			<td class="not_modifiable right">%s</td>
		</tr>
		<tr>
			<td>%s</td>
			<td class="right">%s</td>
		</tr>
		<tr>
			<td><strong><a href="#" class="help" title="%s">%s</a></strong>
				%s</td>
			<td class="right">%s</td>
		</tr>
		<tr>
			<td><strong>%s</strong></td>
			<td class="right">%s</td>
		</tr>
		<tr>
			<td>%s</td>
			<td class="right">%s</td>
		</tr>
		<tr>
			<td colspan="2" id="my-accordion">
				<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>
				<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>
				<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>
				<h2 class="accordion_toggle">≫&nbsp;%s</h2>
				<div class="accordion_content">%s</div>
			</td>
		</tr>
		<tr>
			<td>%s</td>
			<td class="right">%s</td>
		</tr>
	</table>
</form>
</div>
		''' % (
			form_name, form_name, login,
			_("<strong>UID</strong> (fixed)"), user['uidNumber'],
			_("<strong>Identifier</strong> (fixed)"), login,
			_("<strong>Profile</strong> (fixed)"), profile,
			_("<strong>Full name</strong>"),
			w.input('gecos', user['gecos'], size = 30, maxlength = 64,
				accesskey = 'N'),
			_('''Password must be at least %d characters long. You can use '''
			'''all alphabet characters, numbers, special characters and '''
			'''punctuation signs, except '?!'.''') % \
				LMC.configuration.users.min_passwd_size,
			_("New password"), _("(%d chars. min.)") % \
				LMC.configuration.users.min_passwd_size,
			w.input('password', "", size = 30, maxlength = 64, accesskey = 'P',
				password = True),
			_("password confirmation."),
			w.input('password_confirm', "", size = 30, maxlength = 64,
				password = True),
			_("<strong>Shell</strong><br />(Unix command line interpreter)"),
			w.select('loginShell',  LMC.configuration.users.shells,
			user['loginShell'], func = os.path.basename),
			_('Groups'), dbl_lists[filters.STANDARD],
			_('Privileges'), dbl_lists[filters.PRIVILEGED],
			_('Responsibilities'), dbl_lists[filters.RESPONSIBLE],
			_('Invitations'), dbl_lists[filters.GUEST],
			w.button('&lt;&lt;&nbsp;' + _('Cancel'), "/users/list"),
			w.submit('record', _('Record changes') + '&nbsp;&gt;&gt;',
				onClick = "selectAllMultiValues('%s');" % form_name)
			)

	except exceptions.LicornException, e:
		data += w.error("Account %s does not exist (%s)!" % (
			login, "user = LMC.users.users[LMC.users.login_to_uid(login)]", e))

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def record(uri, http_user, login, loginShell=None, password="",
	password_confirm="", gecos="",
	standard_groups_source    = [],    standard_groups_dest = [],
	privileged_groups_source  = [],  privileged_groups_dest = [],
	responsible_groups_source = [], responsible_groups_dest = [],
	guest_groups_source       = [],       guest_groups_dest = [],
	record=None, configuration=None, users=None, groups=None, profiles=None,
	**kwargs):
	"""Record user account changes."""

	# submit button. forget it.
	del record

	title = _("Modification of account %s") % login

	if protected_user(login, users):
		return w.forgery_error(title)

	if loginShell is None:
		loginShell = LMC.configuration.users.default_shell

	data  = w.page_body_start(uri, http_user, ctxtnav, title, True)

	command = [ "sudo", "mod", "user", '--quiet', "--no-colors", "--login",
		login, "--shell", loginShell ]

	if password != "":
		if password != password_confirm:
			return (w.HTTP_TYPE_TEXT, w.page(title,
				data + w.error(_("Passwords do not match!%s") % rewind)))
		if len(password) < LMC.configuration.users.min_passwd_size:
			return (w.HTTP_TYPE_TEXT, w.page(title, data + w.error(
				_("The password --%s-- must be at least %d characters long!%s")\
				% (password, LMC.configuration.users.min_passwd_size, rewind))))

		command.extend([ '--password', password ])

	command.extend( [ "--gecos", gecos ] )

	add_groups = ','.join(w.merge_multi_select(
								standard_groups_dest,
								privileged_groups_dest,
								responsible_groups_dest,
								guest_groups_dest))
	del_groups = ','.join(w.merge_multi_select(
								standard_groups_source,
								privileged_groups_source,
								responsible_groups_source,
								guest_groups_source))

	if add_groups != "":
		command.extend([ '--add-groups', add_groups ])

	if del_groups != "":
		command.extend(['--del-groups', del_groups ])

	return w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_('''Failed to modify one or more parameters of account
		 <strong>%s</strong>!''') % login)
def main(uri, http_user, sort="login", order="asc", configuration=None,
	users=None, groups=None, profiles=None, **kwargs):
	""" display all users in a nice HTML page. """
	start = time.time()

	LMC.users.acquire()
	LMC.groups.acquire()
	LMC.profiles.acquire()

	try:
		u = LMC.users
		g = LMC.groups
		p = LMC.profiles

		pri_grps = [ g[gid]['name'] for gid in LMC.groups.Select(filters.PRIVILEGED) ]

		rsp_grps = [ g[gid]['name'] for gid in LMC.groups.Select(filters.RESPONSIBLE) ]

		gst_grps = [ g[gid]['name'] for gid in LMC.groups.Select(filters.GUEST) ]

		std_grps = [ g[gid]['name'] for gid in LMC.groups.Select(filters.STANDARD) ]

		accounts = {}
		ordered  = {}
		totals   = {}
		prof     = {}

		for profile in p.keys():
			prof[LMC.groups.name_to_gid(profile)] = p[profile]
			totals[p[profile]['name']] = 0
		totals[_('Standard account')] = 0

		title = _("User accounts")
		data  = w.page_body_start(uri, http_user, ctxtnav, title)

		if order == "asc": reverseorder = "desc"
		else:              reverseorder = "asc"

		data += '<table>\n		<tr>\n'

		for (sortcolumn, sortname) in ( ("gecos", _("Full name")),
			("login", _("Identifier")), ("profile", _("Profile")),
			("locked", _("Locked")) ):
			if sortcolumn == sort:
				data += '''			<th><img src="/images/sort_%s.gif"
					alt="%s order image" />&#160;
					<a href="/users/list/%s/%s" title="%s">%s</a>
					</th>\n''' % (order, order, sortcolumn, reverseorder,
						_("Click to sort in reverse order."), sortname)
			else:
				data += '''			<th><a href="/users/list/%s/asc"
				title="%s">%s</a></th>\n''' % (sortcolumn,
					_("Click to sort on this column."), sortname)
		data += '		</tr>\n'

		def html_build_compact(index, accounts = accounts):
			uid   = ordered[index]
			login = u[uid]['login']
			edit  = (_('''<em>Click to edit current user account parameters:</em>
					<br />
					UID: <strong>%d</strong><br />
					GID: %d (primary group <strong>%s</strong>)<br /><br />
					Groups:&#160;<strong>%s</strong><br /><br />
					Privileges:&#160;<strong>%s</strong><br /><br />
					Responsabilities:&#160;<strong>%s</strong><br /><br />
					Invitations:&#160;<strong>%s</strong><br /><br />
					''') % (
					uid, u[uid]['gidNumber'], g[u[uid]['gidNumber']]['name'],
					", ".join(filter(lambda x: x in std_grps, u[uid]['groups'])),
					", ".join(filter(lambda x: x in pri_grps, u[uid]['groups'])),
					", ".join(filter(lambda x: x in rsp_grps, u[uid]['groups'])),
					", ".join(filter(
					lambda x: x in gst_grps, u[uid]['groups'])))).replace(
						'<','&lt;').replace('>','&gt;')

			html_data = '''
		<tr class="userdata">
			<td class="paddedleft">
				<a href="/users/edit/%s" title="%s" class="edit-entry">%s</a>
			</td>
			<td class="paddedright">
				<a href="/users/edit/%s" title="%s" class="edit-entry">%s</a>
			</td>
			<td style="text-align:center;">%s</td>
				''' % (login, edit, u[uid]['gecos'],
				login, edit, login,
				accounts[uid]['profile_name'])

			if u[uid]['locked']:
				html_data += '''
			<td class="user_action_center">
				<a href="/users/unlock/%s" title="%s">
				<img src="/images/16x16/locked.png" alt="%s"/></a>
			</td>
				''' % (login, _("Unlock password (re-grant access to machines)."),
					_("Remove account."))
			else:
				html_data += '''
			<td class="user_action_center">
				<a href="/users/lock/%s" title="%s">
				<img src="/images/16x16/unlocked.png" alt="%s"/></a>
			</td>
				''' % (login, _("Lock password (revoke access to machines)."),
					_("Lock account."))

			html_data += '''
			<td class="user_action">
				<a href="/users/skel/%s" title="%s" class="reapply-skel">
				<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span></a>
			</td>
			<td class="user_action">
				<a href="/users/delete/%s" title="%s" class="delete-entry">
				<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span></a>
			</td>
		</tr>
				''' % (login, _('''Reapply origin skel data in the personnal '''
					'''directory of user. This is usefull'''
					''' when user has lost icons, or modified too much his/her '''
					'''desktop (menus, panels and so on).
					This will get all his/her desktop back.'''), login,
					_("Definitely remove account from the system."))
			return html_data


		for uid in LMC.users.Select(filters.STANDARD):
			user  = u[uid]
			login = user['login']

			# we add the login to gecosValue and lockedValue to be sure to obtain
			# unique values. This prevents problems with empty or non-unique GECOS
			# and when sorting on locked status (accounts would be overwritten and
			# lost because sorting must be done on unique values).
			accounts[uid] = {
				'login'  : login,
				'gecos'  : user['gecos'] + login ,
				'locked' : str(user['locked']) + login
				}
			try:
				p = prof[user['gidNumber']]['name']
			except KeyError:
				p = _("Standard account")

			accounts[uid]['profile']      = "%s %s" % ( p, login )
			accounts[uid]['profile_name'] = p
			totals[p] += 1

			# index on the column choosen for sorting, and keep trace of the uid
			# to find account data back after ordering.
			ordered[hlstr.validate_name(accounts[uid][sort])] = uid

		memberkeys = ordered.keys()
		memberkeys.sort()
		if order == "desc": memberkeys.reverse()

		data += ''.join(map(html_build_compact, memberkeys))

		def print_totals(totals):
			output = ""
			for total in totals:
				if totals[total] != 0:
					output += '''
		<tr class="list_total">
			<td colspan="3" class="total_left">%s</td>
			<td colspan="3" class="total_right">%d</td>
		</tr>
			''' % (_("number of <strong>%s</strong>:") % total, totals[total])
			return output

		data += '''
		<tr>
			<td colspan="6">&#160;</td></tr>
		%s
		<tr class="list_total">
			<td colspan="3" class="total_left">%s</td>
			<td colspan="3" class="total_right">%d</td>
		</tr>
	</table>
		''' % (print_totals(totals),
			_("<strong>Total number of accounts:</strong>"),
			reduce(lambda x, y: x+y, totals.values()))

		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.page_body_end(w.total_time(start, time.time()))))
	finally:
		LMC.profiles.release()
		LMC.groups.release()
		LMC.users.release()
