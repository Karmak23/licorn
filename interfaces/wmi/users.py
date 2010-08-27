# -*- coding: utf-8 -*-

import os, time
from gettext import gettext as _

from licorn.foundations    import exceptions, hlstr, logging

from licorn.core.configuration  import LicornConfiguration
from licorn.core.users          import UsersController
from licorn.core.groups         import GroupsController
from licorn.core.profiles       import ProfilesController

from licorn.interfaces.wmi import utils as w

configuration = LicornConfiguration()
users = UsersController(configuration)
groups = GroupsController(configuration, users)
profiles = ProfilesController(configuration, groups, users)

groups_filters_lists_ids = (
	(groups.FILTER_STANDARD, [_('Customize groups'),
		_('Available groups'), _('Affected groups')],
				'standard_groups'),
	(groups.FILTER_PRIVILEGED, [_('Customize privileges'),
		_('Available privileges'), 	_('granted privileges')],
			'privileged_groups'),
	(groups.FILTER_RESPONSIBLE, [_('Assign responsibilities'),
		_('Available responsibilities'), _('Assigned responsibilities')],
			'responsible_groups'),
	(groups.FILTER_GUEST, [_('Propose invitations'),
		_('Available invitations'), _('Offered invitations')],
			'guest_groups') )

rewind = _('''<br /><br />Go back with your browser,'''
	''' double-check data and validate the web-form.''')
successfull_redirect = '/users/list'

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
def protected_user(login):
	return users.is_system_login(login)

def export(uri, http_user, type = "", yes = None):
	""" Export user accounts list."""

	groups.reload()
	users.reload()
	# profiles.reload()

	# submit button; forget it.
	del yes

	title = _("Export user accounts list")
	data  = '''<div id="banner">
		%s
		%s</div>
		%s
		<div id="main">
		%s
		<div id="content">
		<h1>%s</h1>''' % (
		w.backto(), w.metanav(http_user), w.menu(uri), ctxtnav(), title)

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
		users.Select(users.FILTER_STANDARD)

		if type == "CSV":
			data = users.ExportCSV()
		else:
			data = users.ExportXML()

		return w.HTTP_TYPE_DOWNLOAD, (type, data)
def delete(uri, http_user, login, sure=False, no_archive=False, yes=None):
	"""remove user account."""

	# form submit button, forget it.
	del yes

	title = _("Remove user account %s") % login

	if protected_user(login):
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
				configuration.home_archive_dir,
				configuration.defaults.admin_group),
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
def unlock(uri, http_user, login):
	"""unlock a user account password."""

	title = _("Unlock account %s") % login

	if protected_user(login):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if users.is_system_login(login):
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
def lock(uri, http_user, login, sure=False, remove_remotessh=False, yes=None):
	"""lock a user account password."""

	# submit button: forget it.
	del yes

	title = _("Lock account %s") % login

	if protected_user(login):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if not sure:
		description = _('''This will prevent user to connect to network '''
			'''clients (thin ones, and Windows&reg;, %s/Linux&reg; and '''
			'''Macintosh&reg; ones).''') % w.acr('GNU')

		if configuration.ssh.enabled :
			if login in groups.all_members(configuration.ssh.group):
				description += _('''<br /><br />
					But this will not block incoming %s network connections, '''
					'''if the user uses %s %s or %s public/private keys. To '''
					'''block ANY access to the system, <strong>remove him/her'''
					''' from %s group</strong>.''') % (w.acr('SSH'),
					w.acr('SSH'), w.acr('RSA'), w.acr('DSA'),
					configuration.ssh.group)
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

		if configuration.ssh.enabled and remove_remotessh:
			command.extend(['--del-groups', configuration.ssh.group])

		data += w.page_body_end()

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_("Failed to lock account <strong>%s</strong>!") % login)
def skel(uri, http_user, login, sure = False,
	apply_skel = configuration.users.default_skel, yes = None):
	"""reapply a user's skel with confirmation."""

	# submit button; forget it.
	del yes

	title = _("Reapply skel to user account %s") % login

	if protected_user(login):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if not sure:
		description = _('''This will rebuild his/her desktop from scratch, '''
		'''with defaults icons and so on.<br /><br />The user must be '''
		'''disconnected for the operation to be completely successfull.''')

		form_options = _("Which skel do you want to apply? %s") % \
			w.select("apply_skel", configuration.users.skels,
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
def new(uri, http_user):
	"""Generate a form to create a new user on the system."""

	groups.reload()
	g = groups
	p = profiles

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
		return w.select('loginShell',  configuration.users.shells,
			current=configuration.users.default_shell, func=os.path.basename)

	dbl_lists = {}
	for filter, titles, id in groups_filters_lists_ids:
		groups.Select(filter)
		dest   = []
		source = [ g[gid]['name'] for gid in groups.filtered_groups ]
		source.sort()
		dbl_lists[filter] = w.doubleListBox(titles, id, source, dest)

	form_name = "user_edit"

	data += '''
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

					<script type="text/javascript">
						Event.observe(window, 'load', loadAccordions, false);
						function loadAccordions() {
							var prout = new accordion("my-accordion");
					//prout.activate($$("#my-accordion .accordion_toggle")[0]);
						}
					</script>
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
		'''signs, except '?!'.''') % configuration.mAutoPasswdSize,
		_("Password"), _("(%d chars. min.)") % configuration.mAutoPasswdSize,
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
		_('Groups'), dbl_lists[groups.FILTER_STANDARD],
		_('Privileges'), dbl_lists[groups.FILTER_PRIVILEGED],
		_('Responsibilities'), dbl_lists[groups.FILTER_RESPONSIBLE],
		_('Invitations'), dbl_lists[groups.FILTER_GUEST],
		w.button('&lt;&lt;&nbsp;' + _('Cancel'), "/users/list"),
		w.submit('create', _('Create') + '&nbsp;&gt;&gt;',
			onClick = "selectAllMultiValues('%s');" % form_name)
		)

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def create(uri, http_user, loginShell, password, password_confirm,
	profile=None, login="", gecos="", firstname="", lastname="",
	standard_groups_dest=[], privileged_groups_dest=[],
	responsible_groups_dest=[], guest_groups_dest=[],
	standard_groups_source=[], privileged_groups_source=[],
	responsible_groups_source=[], guest_groups_source=[],
	create = None ):

	# forget it; useless
	del create

	title = _("New user account %s") % login
	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	if password != password_confirm:
		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.error(_("Passwords do not match!%s") % rewind)))

	if len(password) < configuration.mAutoPasswdSize:
		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.error(_("Password must be at least %d characters long!%s")\
				% (configuration.mAutoPasswdSize, rewind))))

	command = [ "sudo", "add", "user", '--quiet', '--no-colors',
		'--password', password ]

	if firstname != '' and lastname != '':
		command.extend(['--firstname', firstname, '--lastname', lastname])
	if gecos != '':
		command.extend(['--gecos', gecos])

	# TODO: set a default profile (see issue #6)
	if profile != None:
		command.extend([ "--profile", profile ])

	if login != "":
		command.extend([ "--login", login ])
	else:
		# TODO: Idem, "gecos" should be tested against emptyness
		command.extend([ '--login',
			hlstr.validate_name(gecos).replace('_', '.').rstrip('.') ])

	(rettype, retdata) = w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_('''Failed to create account <strong>%s</strong>!''') % login)

	if rettype == w.HTTP_TYPE_TEXT:
		return (rettype, retdata)
	# else: continue the creation by adding groups...

	# This is less than suboptimal to have to reload this here...
	# but without this, adding to supplemental groups doesnt work.
	# this will be resolved and not needed when #127 is fixed.
	users.reload()

	command    = [ "sudo", "mod", "user", '--quiet', "--no-colors",
		"--login", login, "--shell", loginShell ]
	add_groups = ','.join(__merge_multi_select(
							standard_groups_dest,
							privileged_groups_dest,
							responsible_groups_dest,
							guest_groups_dest))

	if add_groups != "":
		command.extend([ '--add-groups', add_groups ])

	return w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_('''Failed to add user <strong>%s</strong> to requested
		groups/privileges/responsibilities/invitations!''') % login)
def edit(uri, http_user, login):
	"""Edit an user account, based on login."""

	users.reload()
	groups.reload()
	# profiles.reload()

	title = _('Edit account %s') % login

	if protected_user(login):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	try:
		user = users.users[users.login_to_uid(login)]

		try:
			profile = \
				profiles.profiles[
					groups.groups[user['gidNumber']]['name']
					]['name']
		except KeyError:
			profile = _("Standard account")

		dbl_lists = {}
		for filter, titles, id in groups_filters_lists_ids:
			groups.Select(filter)
			dest   = list(user['groups'].copy())
			source = [ groups.groups[gid]['name'] \
				for gid in groups.filtered_groups ]
			for current in dest[:]:
				try: source.remove(current)
				except ValueError: dest.remove(current)
			dest.sort()
			source.sort()
			dbl_lists[filter] = w.doubleListBox(titles, id, source, dest)

		form_name = "user_edit_form"

		data += '''<div id="edit_form">
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

				<script type="text/javascript">
					Event.observe(window, 'load', loadAccordions, false);
					function loadAccordions() {
						var prout = new accordion("my-accordion");
					//prout.activate($$("#my-accordion .accordion_toggle")[0]);
					}
				</script>
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
				configuration.mAutoPasswdSize,
			_("New password"), _("(%d chars. min.)") % \
				configuration.mAutoPasswdSize,
			w.input('password', "", size = 30, maxlength = 64, accesskey = 'P',
				password = True),
			_("password confirmation."),
			w.input('password_confirm', "", size = 30, maxlength = 64,
				password = True),
			_("<strong>Shell</strong><br />(Unix command line interpreter)"),
			w.select('loginShell',  configuration.users.shells,
			user['loginShell'], func = os.path.basename),
			_('Groups'), dbl_lists[groups.FILTER_STANDARD],
			_('Privileges'), dbl_lists[groups.FILTER_PRIVILEGED],
			_('Responsibilities'), dbl_lists[groups.FILTER_RESPONSIBLE],
			_('Invitations'), dbl_lists[groups.FILTER_GUEST],
			w.button('&lt;&lt;&nbsp;' + _('Cancel'), "/users/list"),
			w.submit('record', _('Record changes') + '&nbsp;&gt;&gt;',
				onClick = "selectAllMultiValues('%s');" % form_name)
			)

	except exceptions.LicornException, e:
		data += w.error("Account %s does not exist (%s)!" % (
			login, "user = users.users[users.login_to_uid(login)]", e))

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def record(uri, http_user, login, loginShell=configuration.users.default_shell,
	password = "", password_confirm = "",
	firstname = "", lastname = "", gecos = "",
	standard_groups_source    = [],    standard_groups_dest = [],
	privileged_groups_source  = [],  privileged_groups_dest = [],
	responsible_groups_source = [], responsible_groups_dest = [],
	guest_groups_source       = [],       guest_groups_dest = [],
	record = None):
	"""Record user account changes."""

	# submit button. forget it.
	del record
	users.reload()

	title = _("Modification of account %s") % login

	if protected_user(login):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	command = [ "sudo", "mod", "user", '--quiet', "--no-colors", "--login",
		login, "--shell", loginShell ]

	if password != "":
		if password != password_confirm:
			return (w.HTTP_TYPE_TEXT, w.page(title,
				data + w.error(_("Passwords do not match!%s") % rewind)))
		if len(password) < configuration.mAutoPasswdSize:
			return (w.HTTP_TYPE_TEXT, w.page(title, data + w.error(
				_("The password --%s-- must be at least %d characters long!%s")\
				% (password, configuration.mAutoPasswdSize, rewind))))

		command.extend([ '--password', password ])

	command.extend( [ "--gecos", gecos ] )

	add_groups = ','.join(__merge_multi_select(
								standard_groups_dest,
								privileged_groups_dest,
								responsible_groups_dest,
								guest_groups_dest))
	del_groups = ','.join(__merge_multi_select(
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

def main(uri, http_user, sort = "login", order = "asc"):
	""" display all users in a nice HTML page. """
	start = time.time()

	groups.reload()
	users.reload()
	# profiles.reload()

	u = users.users
	g = groups.groups
	p = profiles.profiles

	groups.Select(groups.FILTER_PRIVILEGED)
	pri_grps = [ g[gid]['name'] for gid in groups.filtered_groups ]

	groups.Select(groups.FILTER_RESPONSIBLE)
	rsp_grps = [ g[gid]['name'] for gid in groups.filtered_groups ]

	groups.Select(groups.FILTER_GUEST)
	gst_grps = [ g[gid]['name'] for gid in groups.filtered_groups ]

	groups.Select(groups.FILTER_STANDARD)
	std_grps = [ g[gid]['name'] for gid in groups.filtered_groups ]

	accounts = {}
	ordered  = {}
	totals   = {}
	prof     = {}

	for profile in p:
		prof[groups.name_to_gid(profile)] = p[profile]
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

	users.Select(users.FILTER_STANDARD)
	for uid in users.filtered_users:
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