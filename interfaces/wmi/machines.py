# -*- coding: utf-8 -*-

import os, time
from gettext import gettext as _

from licorn.foundations           import exceptions, hlstr, logging
from licorn.foundations.pyutils   import format_time_delta
from licorn.foundations.constants import host_status, filters

from licorn.interfaces.wmi import utils as w

rewind = _('''<br /><br />Go back with your browser,'''
	''' double-check data and validate the web-form.''')
successfull_redirect = '/machines/list'

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
			<li><a href="/machines/new" title="%s" %s class="%s">
			<div class="ctxt-icon %s" id="icon-add">%s</div></a></li>
			<li><a href="/machines/massshutdown" title="%s" %s class="%s">
			<div class="ctxt-icon %s" id="icon-massshutdown">%s</div></a></li>
			<li><a href="/machines/energyprefs" title="%s" %s class="%s">
			<div class="ctxt-icon %s" id="icon-energyprefs">%s</div></a></li>
			<li><a href="/machines/export" title="%s" %s class="%s">
			<div class="ctxt-icon %s" id="icon-export">%s</div></a></li>
		</ul>
	</div>
	''' % (
		_("""Create a configuration record for a machine which is not yet on """
			"""the network."""),
			onClick, disabled, disabled,
		_("Add a machine"),
		_("Shutdown machines on the network."),
			onClick, disabled, disabled,
		_("Shutdown machines"),
		_("Edit Energy &amp; power saving policies."),
			onClick, disabled, disabled,
		_("Energy policies"),
		_("Export current machines list to a CSV or XML file."),
			onClick, disabled, disabled,
		_("Export this list")
		)

def shutdown(uri, http_user, hostname=None, sure=False, warn_users=True, yes=None):
	""" Export machine list."""

	# submit button; forget it.
	del yes

	title = _("Shutdown machine %s") % hostname
	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if not sure:
		description = _('''Are you sure you want to remotely shutdown '''
			'''machine %s?''') % hostname

		form_options = w.checkbox("warn_users", "True",
				'<strong>' + _("Warn connected user(s) before shuting system down.") + '</strong>', True)

		data += w.question(_("Please confirm operation"),
			description,
			yes_values   = [ _("Shutdown") + ' >>', "/machines/shutdown/%s/sure" % hostname, "S" ],
			no_values    = [ '<< ' + _("Cancel"),  "/machines/list",   "N" ],
			form_options = form_options)

		data += '</div><!-- end main -->'

		return (w.HTTP_TYPE_TEXT, w.page(title, data))

	else:
		# we are sure, do it !
		command = [ 'sudo', 'mod', 'machines', '--shutdown', '--no-colors' ]

		if warn_users:
			command.extend([ '--warn-users' ])
		else:
			command.extend([ '--dont-warn-users' ])

		command.extend([ '--hostname', hostname ])

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to shutdown machine %s!''' % hostname))
def massshutdown(uri, http_user, sure=False, asleep=None, idle=None,
	active=None, warn_users=None, admin=None, yes=None):
	""" Export machine list."""

	# submit button; forget it.
	del yes

	title = _("Massive shutdown")
	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if not sure:
		description = _('''You can shutdown all currently running and/or idle'''
			''' machines. This is a quite dangerous operation, because users'''
			''' will be disconnected, and there is a potential to loose '''
			'''unsaved work on idle machines (users are not in front of'''
			''' them, they won't notice the system is shuting down.<br />'''
			'''<br />Systems will be shut down <strong>ONE minute</strong> '''
			'''after validation.''')

		form_options = '%s<br />%s<br />%s<br />%s<br /><br />%s' % (
			w.checkbox("active", "True",
				_("Shutdown <strong>active</strong> machines"), True),
			w.checkbox("idle", "True",
				_("Shutdown <strong>idle</strong> machines"), True),
			w.checkbox("asleep", "True",
				_("Shutdown <strong>asleep</strong> machines"), True),
			w.checkbox("admin", "True",
				_("Shutdown the <strong>administrator</strong> machine too<br/>(the one currently connected to the WMI)."), False),
			w.checkbox("warn_users", "True",
				'<strong>' + _("Warn connected users before shuting systems down.") + '</strong>', True)
			)

		data += w.question(_("Choose machines to shutdown"),
			description,
			yes_values   = [ _("Shutdown") + ' >>', "/machines/massshutdown/sure", "S" ],
			no_values    = [ '<< ' + _("Cancel"),  "/machines/list",   "N" ],
			form_options = form_options)

		data += '</div><!-- end main -->'

		return (w.HTTP_TYPE_TEXT, w.page(title, data))

	else:
		# we are sure, do it !
		command = [ 'sudo', 'mod', 'machines', '--shutdown', '--no-colors' ]

		for option, argument in (
			(asleep,     '--asleep'),
			(idle,       '--idle'),
			(active,     '--active'),
			# not implemented yet
			#(no_admin,      '--admin'),
			(warn_users, '--warn-users')
			):
			if option:
				command.extend([argument])

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to shutdown one or more machines!'''))
def energyprefs(uri, http_user):
	""" Export machine list."""

	# submit button; forget it.
	del yes

	title = _("Energy saving policies")

	if type == "":
		description = _('''CSV file-format is used by spreadsheets and most '''
		'''systems which offer import functionnalities. XML file-format is a '''
		'''modern exchange format, used in soma applications which respect '''
		'''interoperability constraints.<br /><br />When you submit this '''
		'''form, your web browser will automatically offer you to download '''
		'''and save the export-file (it won't be displayed). When you're '''
		'''done, please click the “back” button of your browser.''')

		form_options = \
			_("Which file format do you want the machines list to be exported to? %s") \
				% w.select("type", [ "CSV", "XML"])

		data += w.question(_("Please choose file format for export list"),
			description,
			yes_values   = [ _("Export >>"), "/machines/export", "E" ],
			no_values    = [ _("<< Cancel"),  "/machines/list",   "N" ],
			form_options = form_options)

		data += '</div><!-- end main -->'

		return (w.HTTP_TYPE_TEXT, w.page(title, data))

	else:
		machines.Select(machines.FILTER_STANDARD)

		if type == "CSV":
			data = machines.ExportCSV()
		else:
			data = machines.ExportXML()

		return w.HTTP_TYPE_DOWNLOAD, (type, data)
def export(uri, http_user, type = "", yes = None):
	""" Export machine list."""

	# submit button; forget it.
	del yes

	return (w.HTTP_TYPE_TEXT, "not implemented yet.")

	title = _("Export machines list")
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
			_("Which file format do you want the machines list to be exported to? %s") \
				% w.select("type", [ "CSV", "XML"])

		data += w.question(_("Please choose file format for export list"),
			description,
			yes_values   = [ _("Export >>"), "/machines/export", "E" ],
			no_values    = [ _("<< Cancel"),  "/machines/list",   "N" ],
			form_options = form_options)

		data += '</div><!-- end main -->'

		return (w.HTTP_TYPE_TEXT, w.page(title, data))

	else:
		machines.Select(machines.FILTER_STANDARD)

		if type == "CSV":
			data = machines.ExportCSV()
		else:
			data = machines.ExportXML()

		return w.HTTP_TYPE_DOWNLOAD, (type, data)
def forget(uri, http_user, hostname, sure=False, yes=None):
	"""remove machine account."""

	# form submit button, forget it.
	del yes

	return (w.HTTP_TYPE_TEXT, "not implemented yet.")

	title = _("Remove machine %s's record") % hostname

	if protected_user(hostname):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if not sure:
		data += w.question(
			_("Are you sure you want to remove record for machine <strong>%s</strong>?") \
			% hostname,
			_('''User's <strong>personnal data</strong> (his/her HOME dir) '''
			'''will be <strong>archived</strong> in directory <code>%s</code>'''
			''' and members of group <strong>%s</strong> will be able to '''
			''' access it to operate an eventual recover.<br />However, you '''
			'''can decide to permanently remove it.''') % (
				configuration.home_archive_dir,
				configuration.defaults.admin_group),
			yes_values   = \
				[ _("Remove >>"), "/machines/delete/%s/sure" % hostname, _("R") ],
			no_values    = \
				[ _("<< Cancel"),   "/machines/list",                 _("C") ],
			form_options = w.checkbox("no_archive", "True",
				_("Definitely remove record data (no archiving)."),
				checked = False) )

		return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))

	else:
		# we are sure, do it !
		command = [ 'sudo', 'del', 'machine', '--quiet', '--no-colors',
			'--hostname', hostname ]

		if no_archive:
			command.extend(['--no-archive'])

		return w.run(command, successfull_redirect,
			w.page(title, data + '%s' + w.page_body_end()),
			_('''Failed to remove record <strong>%s</strong>!''') % hostname)
def new(uri, http_user):
	"""Generate a form to create a new machine on the system."""

	return (w.HTTP_TYPE_TEXT, "not implemented yet.")

	title = _("New machine record")
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
			""" % (_("This machine is a"), w.select('profile',  p.keys(),
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
		return w.select('loginShell', configuration.machines.shells,
			current=configuration.users.default_shell, func=os.path.basename)

	dbl_lists = {}
	for filter, titles, id in groups_filters_lists_ids:

		dest   = []
		source = [ g[gid]['name'] for gid in groups.Select(filter) ]
		source.sort()
		dbl_lists[filter] = w.doubleListBox(titles, id, source, dest)

	form_name = "user_edit"

	data += '''
	<div id="edit_form">
	<form name="%s" id="%s" action="/machines/create" method="post">
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
		'''signs, except '?!'.''') % configuration.users.min_passwd_size,
		_("Password"), _("(%d chars. min.)") % configuration.users.min_passwd_size,
		w.input('password', "", size = 30, maxlength = 64, accesskey = _('P'),
			password = True),
		_("Password confirmation."), w.input('password_confirm', "", size = 30,
			maxlength = 64, password = True ),
		_('''Identifier must be lowercase, without accents or special '''
		'''characters (you can use dots and carets).<br /><br />'''
		'''If you let this field empty, identifier will be automaticaly '''
		'''guessed from first name and last name.'''),
		_("Identifier"), w.input('hostname', "", size = 30, maxlength = 64,
			accesskey = _('I')),
		_("<strong>Shell</strong><br />(Unix command line interpreter)"),
		shell_input(),
		_('Groups'), dbl_lists[groups.FILTER_STANDARD],
		_('Privileges'), dbl_lists[groups.FILTER_PRIVILEGED],
		_('Responsibilities'), dbl_lists[groups.FILTER_RESPONSIBLE],
		_('Invitations'), dbl_lists[groups.FILTER_GUEST],
		w.button('&lt;&lt;&nbsp;' + _('Cancel'), "/machines/list"),
		w.submit('create', _('Create') + '&nbsp;&gt;&gt;',
			onClick = "selectAllMultiValues('%s');" % form_name)
		)

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def create(uri, http_user, loginShell, password, password_confirm,
	profile=None, hostname="", gecos="", firstname="", lastname="",
	standard_groups_dest=[], privileged_groups_dest=[],
	responsible_groups_dest=[], guest_groups_dest=[],
	standard_groups_source=[], privileged_groups_source=[],
	responsible_groups_source=[], guest_groups_source=[],
	create = None ):

	# forget it; useless
	del create

	return (w.HTTP_TYPE_TEXT, "not implemented yet.")

	title = _("New machine record %s") % hostname
	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	if password != password_confirm:
		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.error(_("Passwords do not match!%s") % rewind)))

	if len(password) < configuration.users.min_passwd_size:
		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.error(_("Password must be at least %d characters long!%s")\
				% (configuration.users.min_passwd_size, rewind))))

	command = [ "sudo", "add", "machine", '--quiet', '--no-colors',
		'--password', password ]

	if firstname != '' and lastname != '':
		command.extend(['--firstname', firstname, '--lastname', lastname])
	if gecos != '':
		command.extend(['--gecos', gecos])

	# TODO: set a default profile (see issue #6)
	if profile != None:
		command.extend([ "--profile", profile ])

	if hostname != "":
		command.extend([ "--hostname", hostname ])
	else:
		# TODO: Idem, "gecos" should be tested against emptyness
		command.extend([ '--hostname',
			hlstr.validate_name(gecos).replace('_', '.').rstrip('.') ])

	(rettype, retdata) = w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_('''Failed to create record <strong>%s</strong>!''') % hostname)

	if rettype == w.HTTP_TYPE_TEXT:
		return (rettype, retdata)
	# else: continue the creation by adding groups…

	command    = [ "sudo", "mod", "machine", '--quiet', "--no-colors",
		"--hostname", hostname, "--shell", loginShell ]
	add_groups = ','.join(__merge_multi_select(
							standard_groups_dest,
							privileged_groups_dest,
							responsible_groups_dest,
							guest_groups_dest))

	if add_groups != "":
		command.extend([ '--add-groups', add_groups ])

	return w.run(command, successfull_redirect,
		w.page(title, data + '%s' + w.page_body_end()),
		_('''Failed to add machine <strong>%s</strong> to requested
		groups/privileges/responsibilities/invitations!''') % hostname)
def edit(uri, http_user, hostname):
	"""Edit an machine record, based on hostname."""

	return (w.HTTP_TYPE_TEXT, "not implemented yet.")

	title = _("Edit %s's record") % hostname

	if protected_user(hostname):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	try:
		machine = machines.machines[machines.hostname_to_mid(hostname)]

		try:
			profile = \
				profiles.profiles[
					groups.groups[machine['gidNumber']]['name']
					]['name']
		except KeyError:
			profile = _("Standard account")

		dbl_lists = {}
		for filter, titles, id in groups_filters_lists_ids:

			dest   = list(machine['groups'].copy())
			source = [ groups.groups[gid]['name'] \
				for gid in groups.Select(filter) ]
			for current in dest[:]:
				try: source.remove(current)
				except ValueError: dest.remove(current)
			dest.sort()
			source.sort()
			dbl_lists[filter] = w.doubleListBox(titles, id, source, dest)

		form_name = "user_edit_form"

		data += '''<div id="edit_form">
<form name="%s" id="%s" action="/machines/record/%s" method="post">
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
			form_name, form_name, hostname,
			_("<strong>mid</strong> (fixed)"), machine['midNumber'],
			_("<strong>Identifier</strong> (fixed)"), hostname,
			_("<strong>Profile</strong> (fixed)"), profile,
			_("<strong>Full name</strong>"),
			w.input('gecos', machine['gecos'], size = 30, maxlength = 64,
				accesskey = 'N'),
			_('''Password must be at least %d characters long. You can use '''
			'''all alphabet characters, numbers, special characters and '''
			'''punctuation signs, except '?!'.''') % \
				configuration.users.min_passwd_size,
			_("New password"), _("(%d chars. min.)") % \
				configuration.users.min_passwd_size,
			w.input('password', "", size = 30, maxlength = 64, accesskey = 'P',
				password = True),
			_("password confirmation."),
			w.input('password_confirm', "", size = 30, maxlength = 64,
				password = True),
			_("<strong>Shell</strong><br />(Unix command line interpreter)"),
			w.select('loginShell',  configuration.users.shells,
			machine['loginShell'], func = os.path.basename),
			_('Groups'), dbl_lists[groups.FILTER_STANDARD],
			_('Privileges'), dbl_lists[groups.FILTER_PRIVILEGED],
			_('Responsibilities'), dbl_lists[groups.FILTER_RESPONSIBLE],
			_('Invitations'), dbl_lists[groups.FILTER_GUEST],
			w.button('&lt;&lt;&nbsp;' + _('Cancel'), "/machines/list"),
			w.submit('record', _('Record changes') + '&nbsp;&gt;&gt;',
				onClick = "selectAllMultiValues('%s');" % form_name)
			)

	except exceptions.LicornException, e:
		data += w.error("Record %s does not exist (%s)!" % (
			hostname, "machine = machines.machines[machines.hostname_to_mid(hostname)]", e))

	return (w.HTTP_TYPE_TEXT, w.page(title, data + w.page_body_end()))
def record(uri, http_user, hostname, loginShell=None,
	password = "", password_confirm = "",
	firstname = "", lastname = "", gecos = "",
	standard_groups_source    = [],    standard_groups_dest = [],
	privileged_groups_source  = [],  privileged_groups_dest = [],
	responsible_groups_source = [], responsible_groups_dest = [],
	guest_groups_source       = [],       guest_groups_dest = [],
	record = None):
	"""Record machine changes."""

	# submit button. forget it.
	del record

	return (w.HTTP_TYPE_TEXT, "not implemented yet.")

	title = _("Modification of %s's record") % hostname

	if protected_user(hostname):
		return w.forgery_error(title)

	data  = w.page_body_start(uri, http_user, ctxtnav, title, False)

	command = [ "sudo", "mod", "machine", '--quiet', "--no-colors", "--hostname",
		hostname, "--shell", loginShell ]

	if password != "":
		if password != password_confirm:
			return (w.HTTP_TYPE_TEXT, w.page(title,
				data + w.error(_("Passwords do not match!%s") % rewind)))
		if len(password) < configuration.users.min_passwd_size:
			return (w.HTTP_TYPE_TEXT, w.page(title, data + w.error(
				_("The password --%s-- must be at least %d characters long!%s")\
				% (password, configuration.users.min_passwd_size, rewind))))

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
		_('''Failed to modify one or more parameters of record
		 <strong>%s</strong>!''') % hostname)
def main(uri, http_user, sort = "hostname", order = "asc"):
	""" display all machines in a nice HTML page. """

	start = time.time()

	m = machines.machines

	accounts = {}
	ordered  = {}
	totals   = {
		_('managed'): 0,
		_('floating'): 0
		}

	title = _("Machines")
	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	if order == "asc": reverseorder = "desc"
	else:              reverseorder = "asc"

	data += '<table>\n		<tr>'

	for (sortcolumn, sortname) in (
			("status", _("Status")),
			("hostname", _("Host name")),
			("ip", _("IP address")),
			("ether", _("Hardware address")),
			("expiry", _("Expiry")),
			("managed", _("Managed"))
		):
		if sortcolumn == sort:
			data += '''
			<th><img src="/images/sort_%s.gif"
				alt="%s order image" />&#160;
				<a href="/machines/list/%s/%s" title="%s">%s</a>
			</th>\n''' % (order, order, sortcolumn, reverseorder,
					_("Click to sort in reverse order."), sortname)
		else:
			data += '''
			<th>
				<a href="/machines/list/%s/asc"	title="%s">%s</a>
			</th>\n''' % (sortcolumn,
				_("Click to sort on this column."), sortname)
	data += '		</tr>\n'

	def html_build_compact(index, accounts = accounts):
		mid      = ordered[index]
		hostname = m[mid]['hostname']
		edit     = 'machine %s (IP %s)' % (hostname, m[mid]['ip'])
		if m[mid]['managed']:
			totals[_('managed')] += 1
		else:
			totals[_('floating')] += 1

		power_statuses = {
			host_status.UNKNOWN: (None, 'unknown',
				_('''Host %s is in an unknown state. Nothing is possible. '''
					'''Please wait for a reconnection.''')),
			host_status.OFFLINE: (None, 'offline',
				_('''Host %s is offline, and cannot be powered on from here,'''
					'''Only from the machine itself.''')),
			host_status.ASLEEP: ('shutdown', 'asleep',
				_('Shutdown the machine %s')),
			host_status.IDLE: ('shutdown', 'idle',
				_('Shutdown the machine %s')),
			host_status.ACTIVE: ('shutdown', 'active',
				_('Shutdown the machine %s')),
			}

		status = m[mid]['status']
		if power_statuses[status][0]:

			html_data = '''
	<tr class="userdata">
		<!-- STATUS -->
		<td class="user_action_center">
			<a href="/machines/%s/%s" title="%s" class="%s">
			<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span></a>
		</td>''' % (
			power_statuses[status][0],
			hostname,
			power_statuses[status][2] % hostname,
			power_statuses[status][1]
			)

		else:
			html_data = '''
	<tr class="userdata">
		<!-- STATUS -->
		<td class="user_action_center">
			<span class="%s" title="%s">&nbsp;&nbsp;&nbsp;&nbsp;</span>
		</td>''' % (
			power_statuses[status][1],
			power_statuses[status][2] % hostname)

		html_data += '''

		<!-- HOSTNAME -->
		<td class="paddedright">
			<a href="/machines/edit/%s" title="%s" class="edit-entry">%s%s</a>
		</td>
		<!-- IP -->
		<td class="paddedright">
			<a href="/machines/edit/%s" title="%s" class="edit-entry">%s</a>
		</td>
		<!-- ETHER -->
		<td class="paddedright">
			<a href="/machines/edit/%s" title="%s" class="edit-entry">%s</a>
		</td>
		<!-- EXPIRY -->
		<td class="paddedright">
			<a href="/machines/edit/%s" title="%s" class="edit-entry">%s</a>
		</td>
			''' % (
				hostname, edit, hostname,
					'''&nbsp;<img src='/images/16x16/alt.png' alt='%s' />''' % _('This machine is an ALT® client.') if machines.is_alt(mid) else '',
				hostname, edit, m[mid]['ip'],
				hostname, edit, m[mid]['ether'],
				hostname, edit, format_time_delta(
					float(m[mid]['expiry']) - time.time(), use_neg=True) \
							if m[mid]['expiry'] else '-'
				)

		if m[mid]['managed']:
			html_data += '''

		<!-- MANAGED -->
		<td class="user_action_center">
			<a href="/machines/unmanage/%s" title="%s" class="managed">
			<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span></a>
		</td>
			''' % (hostname, _("""Unmanage machine (remove it from """
				"""configuration, in order to allow it to be managed by """
				"""another server."""))
		else:
			html_data += '''

		<!-- UNMANAGED -->
		<td class="user_action_center">
			<a href="/machines/manage/%s" title="%s" class="floating">
			<span class="delete-entry">&nbsp;&nbsp;&nbsp;&nbsp;</span></a>
		</td>
			''' % (hostname, _("""Manage machine (fix its IP address and """
				"""configure various aspects of the client)."""))

		return html_data

	for mid in machines.keys():
		machine  = m[mid]
		hostname = machine['hostname']

		# we add the hostname to gecosValue and lockedValue to be sure to obtain
		# unique values. This prevents problems with empty or non-unique GECOS
		# and when sorting on locked status (accounts would be overwritten and
		# lost because sorting must be done on unique values).
		accounts[mid] = {
			'status'  : str(machine['status']) + hostname,
			'hostname': hostname,
			'ip'      : machine['ip'],
			'ether'   : machine['ether'],
			'expiry'  : machine['expiry'],
			'managed' : str(machine['managed']) + hostname
		}

		# index on the column choosen for sorting, and keep trace of the mid
		# to find account data back after ordering.
		ordered[hlstr.validate_name(accounts[mid][sort])] = mid

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
		<td colspan="5" class="total_left">%s</td>
		<td class="total_right">%d</td>
	</tr>
		''' % (_("number of <strong>%s</strong> machines:") % total, totals[total])
		return output

	data += '''
	<tr>
		<td colspan="5">&#160;</td></tr>
	%s
	<tr class="list_total">
		<td colspan="5" class="total_left">%s</td>
		<td class="total_right">%d</td>
	</tr>
</table>
	''' % (print_totals(totals),
		_("<strong>Total number of machines:</strong>"),
		reduce(lambda x, y: x+y, totals.values()))

	return (w.HTTP_TYPE_TEXT, w.page(title,
		data + w.page_body_end(w.total_time(start, time.time()))))
