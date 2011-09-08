# -*- coding: utf-8 -*-
"""
Licorn WMI functions.

These functions are used in the Web Administration Interface. They generate
HTML code, or forms, or provide useful tools to help web coding without too much headhaches.

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.

"""
import os

from subprocess import Popen, PIPE
from urllib     import unquote_plus

from licorn.foundations.ltrace import ltrace
from licorn.foundations.ltraces import *

# used for static data only
from licorn.core import LMC

if not hasattr(LMC, 'configuration'):
	# this is a special case for documentation generation, where licorn modules
	# are imported from sphinx, while LMC is not initialized.
	from licorn.foundations.base import LicornConfigObject
	LMC = LicornConfigObject()
	LMC.configuration = LicornConfigObject()
	LMC.configuration.app_name = 'Licorn®'

licence_text = _('{0} is distributed under the <a href="http://www.gnu.org/'
	'licenses/gpl.html">GNU GPL version 2</a> license, without any kind of '
	'waranty. Copyleft &copy; 2007-2011 Olivier Cortès, Guillaume Masson '
	'&amp; Régis Cobrun for project {0}, and all other libre software '
	'developers (Notably Ubuntu, Debian, Python…).').format(
		LMC.configuration.app_name)

acronyms = {
	'SSH' : _(u'Secure SHell (Secure remote connexion and commands protocol)'),
	'FTP' : _(u'File Transfer Protocol'),
	'HTTP': _(u'HyperText Transfert Protocol'),
	'IMAP': _(u'Internet Message Access Protocol'),
	'VNC' : _(u'Virtual Network Computing (Desktop remote connexion protocol)'),
	'RDP' : _(u'Remote Desktop Protocol (Desktop remote connexion protocol)'),
	'POP' : _(u'Post-Office Protocol (Simple mail fetching protocol)'),
	'SMTP': _(u'Simple Mail Transfer Protocol'),
	'RSA' : _(u'Rivest Shamir Adleman (cryptography protocol)'),
	'DSA' : _(u'Digital Signature Algorithm'),
	'GNU' : _(u'GNU is Not Unix (recursive acronym ; a set of libre sofware '
				'composing a libre operating system)'),
	'LCN' : _(u'LiCorN system tools (tools for IT managers, '
				'see http://docs.licorn.org/)'),
	'LAT' : _(u'Licorn Admin Tools (High-level management tools for '
				'a GNU/Linux system)'),
	'WMI' : _('%s Web Management Interface') % LMC.configuration.app_name
	}

def merge_multi_select(*lists):
	final = []

	for alist in lists:
		if alist == []:
			continue

		if type(alist) == type(''):
			final.append(alist)

		else:
			final.extend(alist)
	return final

# EXEC / SYSTEM functions.
def run(command, successfull_redirect, page_data, error_message):
	"""Execute a command passed as a list or tuple"""

	assert ltrace(TRACE_WMI, 'w.run(%s)' % command)

	if type(command) not in (type(()), type([])):
		raise exceptions.LicornWebCommandError(
			error(_("Command must be a list or tuple!"),
			command, "if type(command) not in (type(()), type([])):"))

	p = Popen(command, executable='sudo' , shell=False, stdin=PIPE,
		stdout=PIPE, stderr=PIPE, close_fds=True)

	# FIXME: why this ?
	err = False
	(out, err) = p.communicate()

	if err:
		return (
			HTTP_TYPE_TEXT,
			page_data % error(
				error_message,
				command,
				err.replace('>', '&gt;').replace('<', '&lt;')
				)
			)
	else:
		return (HTTP_TYPE_REDIRECT, successfull_redirect)
def total_time(start, end):
        elapsed = end - start
        ptime   = ""
        if elapsed > 3600:
                h = elapsed / 3600
                ptime += _("%d&nbsp;hours,") % h
                elapsed -= h * 3600
        if elapsed > 60:
                m = elapsed / 60
                ptime += _(" %d&nbsp;minutes,") % m
                elapsed -= m * 60
        ptime += _(" %.3f&nbsp;seconds.") % elapsed
        return ('''<div id="timer">%s</div>''' % _('Core execution time: %s')) % ptime

# AJAX Functions
def doubleListBox_orig(titles, id, values_source = [], values_dest = []):

	def selectbox(legend, id, option_id_prefix = "", values = []):
		data = '<fieldset style="height: 100%%"><legend>%s</legend><select name="%s" class="multiselect" multiple="multiple" id="%s" style="width: 100%%; height: 90%%; vertical-align: middle;">' % (legend, id, id)
		for value in values:
			data += '<option id="%s%s">%s</option>' % (option_id_prefix, value, value)
		return data + '</select></fieldset>'

	masker   = id + '_masker'
	id_left  = id + '_source'
	id_right = id + '_dest'
	return '''
	<div id="%s" class="masker">%s</div>
	<div style="display: none; visibility: hidden;" id="%s">
		<script type="text/javascript">
			function %s_hideUnhide() {
				hideUnhide('%s');
			}
			document.getElementById('%s').onclick = %s_hideUnhide;
		</script>
		<table>
			<tr>
				<td style="width: 35%%; height: 210px;">%s</td>
				<td style="width: 30%%; height: 210px; text-align: center; vertical-align: middle;">
					<input type="button" value="Ajouter >>"
						onclick="ListBoxDropping('%s', '%s', '%s')" />
					<br /><br />
					<input type="button" value="<< Enlever"
						onclick="ListBoxDropping('%s', '%s', '%s')" />
				</td>
				<td style="width: 35%%; height: 210px;">%s</td>
			</tr>
		</table>
	''' % (masker, titles[0], id, id,  id, masker, id,
		selectbox(titles[1],  id_left, id, values_source),
		id_left, id_right, id,
		id_right, id_left, id,
		selectbox(titles[2], id_right, id, values_dest) )
def doubleListBox(titles, id, values_source = [], values_dest = []):

	def selectbox(legend, id, option_id_prefix = "", values = []):
		data = '''<fieldset class="multi-group-fieldset">
		<legend><span class="multi-group-fieldset-legend">%s</span></legend>
		<select name="%s" id="%s" multiple="multiple" class="multi-group-select">''' % (legend, id, id)
		for value in values:
			data += '<option id="%s%s">%s</option>' % (option_id_prefix, value, value)
		return data + '</select></fieldset>'

	masker   = id + '_masker'
	id_left  = id + '_source'
	id_right = id + '_dest'
	data = '<select class="multiselect" multiple="multiple" name="groups[]">'
	for v in values_dest:
		data += '	<option value="%s">%s</option>' % (v,v)
	for v in values_dest:
		data += '	<option value="%s" selected="selected">%s</option>' % (v,v)
	data += '</select>'
	return data
	"""
	<div id="%s" class="accordion_content">
		<table class="accordion-multi-group-table">
			<tr>
				<td class="multi-group-left-column">%s</td>
				<td class="multi-group-center-column">
					<input type="button" value="%s >>" onclick="ListBoxDropping('%s', '%s', '%s')" />
					<div class="vspacer"></div>
					<input type="button" value="<< %s" onclick="ListBoxDropping('%s', '%s', '%s')" />
				</td>
				<td class="multi-group-right-column">%s</td>
			</tr>
		</table>
	</div>
	''' % ( id,
		selectbox(titles[1],  id_left, id, values_source),
		_('Add'),
		id_left, id_right, id,
		_('Remove'),
		id_right, id_left, id,
		selectbox(titles[2], id_right, id, values_dest) )"""
def multiselect(titles, id, values_sources = [], values_dest = []):
	data = '<select class="multiselect" multiple="multiple" name="%s">' % id
	for v in values_sources:
		data += '	<option value="%s">%s</option>' % (v,v)
	for v in values_dest:
		data += '	<option value="%s" selected="selected">%s</option>' % (v,v)
	data += '</select>'

	return data
# GRAPHICAL functions
def question(title, message, yes_values, no_values, form_options = None):
	"""Build ha HTML Question / Confirmation FORM.
		{yes,no}_values = ("value of the button or link", "href of link, or action of form", "accesskey" )
	***ACCESSKEYS for buttons are not yet implemented***
	"""

	data = """
<div id="question">
	<div class="title">%s</div>
	<div class="description">%s</div>
	""" % (title, message)

	if form_options:
		data += '	<div class="options"><form name="yes_action" action="%s" method="post">%s</div>\n' % (yes_values[1], form_options)

	data += """
	<table>
		<tr>"""

	if form_options:
		data+= """
		<td class="cancel">%s</td>
		<td class="confirm">%s</form></td>
		""" % (button(no_values[0], no_values[1]), submit("yes", yes_values[0]))

	else:
		data += """
		<td class="cancel">%s</td>
		<td class="confirm">%s</td>
		""" % (button(no_values[0], no_values[1]), button(yes_values[0], yes_values[1]))
	data += """
	</tr>
</table>
</div>
	"""

	return data
def license(text):
	return '''<div id="license">%s</div>''' % text
def error(message, command=None, error=None, description=''):
	return '''
	<div id="command_error">
		<div class="error_title">%s</div>
		%s%s%s</div>
		''' % (message, '%s<br />' % description if description else '',
			'''%s<br /><br />
		<code>%s</code>''' % (
			_('Executed command:'),
			" ".join(command)) if command else '',
		'<br /><br />%s<br /><br /><pre>%s</pre>' % (
			_('Error reported by system:'), error) if error else '')
def backto():
	return ('''<div id="header"><a id="logo" href="/" title="%s">'''
		'''<img src="/images/logo_licorn_120.png" alt="%s" /></a></div>''' % (
			_("Back to root of management interface"),
			_("Back to root of management interface")))
def metanav(http_user):
	""" Minimal function to display the user logged in.
		Will implement links to preferences, later.
	"""
	return '<div id="metanav" class="nav"><ul><li>%s</li></ul></div>' \
	% (_('Logged in as %s') % http_user)
def page_body_start(uri, http_user, ctxtnav_func, title, active=True):
		return '''
		<div id="banner">
				{back_to_home}
				{meta_nav}
				{menu}
		</div><!-- banner -->'''.format(
				back_to_home=backto(),
				meta_nav=metanav(http_user),
				menu=menu(uri))

def page_body_end(data=''):
	return '''</div><!-- content -->\n%s\n</div><!-- main -->''' % data
def bad_arg_error(message=None):
	return (HTTP_TYPE_TEXT, page(_('Bad request or argument'),
		error(_("Bad request or argument"),
			description = '%s%s' % (
				_('''There was a problem in the request you sent '''
				'''to the WMI.'''),
				'<br /><br />%s' % message if message else '')
		)))

def fool_proof_protection_error(message):
	return (HTTP_TYPE_TEXT, ajax_response('', _('Impossible action: ') + message))
# HTML FORM functions
def access_key(key):
	if key:
		return ' accesskey="%s"' % key
	else:
		return ''
def reset(value = "Revenir au valeurs d'origine"):
	return '''<input type="reset" value="%s" />''' % (value)
def submit(name, value = "", onClick = "", submit_id = '',
	accesskey = None):
	if value == "": value = name
	if onClick != "": onClickValue = 'onClick="%s"' % onClick
	else: onClickValue = ""
	if submit_id != "": id_value = 'id="%s"' % submit_id
	else: id_value = ""
	return '''<input type="submit" name="%s" value="%s" %s %s %s />''' % (name, value, id_value, onClickValue, access_key(accesskey))
def button(label, value, button_id=None, accesskey = None):
	if value is None: href_value = ''
	else: href_value = 'href="%s"' % value
	if button_id is None: id_value = ''
	else: id_value = 'id="%s"' % button_id

	return '''<a %s><button type="button" %s %s>%s</button></a>''' % (href_value, id_value, access_key(accesskey), label)
def select(name, values, select_id=None, current = "", dont_display = (), func = str, accesskey = None, instant_apply = False, instant_apply_action=None):
	instant_apply_text = ''
	if select_id is None: id_text = ''
	else: id_text = "id='%s'" % select_id
	if instant_apply and instant_apply_action is not None:
		instant_apply_text = "class='instant_apply_select' action='%s'" % instant_apply_action
	data = '<select name="%s" %s %s %s>\n' % (name, access_key(accesskey), instant_apply_text, id_text)
	for value in values:
		if value in dont_display: continue
		elif value == current: selected = "selected=selected"
		else: selected = ""
		data += '	<option value="%s" %s>%s</option>\n' % (value, selected, func(value))
	data += '</select>'
	return data
def	input(name, value, size = 20, maxlength = 1024, disabled = False,
	password = False, accesskey = None, instant_apply = False,
	instant_apply_action = None, instant_apply_password = False,
	input_id=None):

	if input_id is None: id_value = ''
	else: id_value = "id='%s'" % input_id
	if disabled: disabled = 'disabled="disabled"'
	else: disabled = ""
	if password: type = "password"
	else: type = "text"
	if instant_apply:
		instant_apply_text = "class='instant_apply_textbox' action='%s'" % instant_apply_action
	elif instant_apply_password:
		instant_apply_text = "class='instant_apply_password' action='%s'" % instant_apply_action
	else:
		instant_apply_text = ""
	return '''<input type="%s" name="%s" value="%s" size="%d" maxlength="%d" %s %s %s %s/>''' % (type, name, value, size, maxlength, id_value, disabled, access_key(accesskey), instant_apply_text)
def	checkbox(name, value, label, checked=False, disabled=False, accesskey=None, checkbox_id="", instant_apply=False, instant_apply_action=''):
	if checkbox_id == "":
		chk_id = ''
	else:
		chk_id= 'id=%s' % checkbox_id
	if disabled:
		disabled = 'disabled="disabled"'
	else:
		disabled = ""
	if checked:
		checked = 'checked="checked"'
	else:
		checked = ""
	if instant_apply:
		instant_apply_text = "class='instant_apply_checkbox' action='%s'" % instant_apply_action
	else:
		instant_apply_text = ""
	return '''<label><input type="checkbox" name="%s" value="%s" %s %s %s %s %s/>&#160;%s</label>''' % (name, value, chk_id, checked, disabled, access_key(accesskey), instant_apply_text, label)

# HTML DOCUMENT functions
def acr(word):
	try:
		return '<acronym title="%s">%s</acronym>' % (acronyms[word.upper()], word)
	except KeyError:
		return word
def menu(uri):

	import licorn.interfaces.wmi as wmi

	class defdict(dict):
		def __init__(self, default=''):
			dict.__init__(self)
			self.default = default
		def __getitem__(self, key):
			try:
				return dict.__getitem__(self, key)
			except KeyError:
				return self.default

	classes = defdict()

	if uri == '/':
		classes['/'] = ' class="active"'
	else:
		classes[uri.split('/')[1].split('.')[0]] = ' class="active"'

	return '''
<div id="mainnav" class="nav">
	<div class="menu-item" >
		<div class="menu-title current">
			<a href="/" class="menu_link" title="%s">
				<div class="menu-back "></div>
				<div class='menu-text'>%s</div>
			</a>
		</div>
		<div class="menu-content">
			<span class="menu-content-item">
				<img src="/images/24x24/eteindre.png"/>
				<span class="menu-content-text"> %s	</span>
			</span>
			<span class="menu-content-item">
				<img src="/images/24x24/redemarrer.png"/>
				<span class="menu-content-text"> %s </span>
			</span>
		</div>
	</div>

	<div class="menu-item" >
		<div class="menu-title">
			<a href="/users" class="menu_link" title="%s">
				<div class="menu-back "></div>
				<div class='menu-text'>%s</div>
			</a>
		</div>
		<div class="menu-content">
			<span class="menu-content-item">
				<img src="/images/24x24/ajouter.png"/>
				<span class="menu-content-text" id='add_user_menu'> 
					%s 
				</span>
			</span>
			<span class="menu-content-item">
				<img src="/images/24x24/importer.png"/>
				<span class="menu-content-text" id='import_user_menu'> 
					%s
				</span>
			</span>
		</div>
	</div>




	<div class="menu-item" >
		<div class="menu-title">
			<a href="/groups" class="menu_link" title="%s">
				<div class="menu-back "></div>
				<div class='menu-text'>%s</div>
			</a>
		</div>
		<div class="menu-content">
			<span class="menu-content-item">
				<img src="/images/24x24/shutdown.png"/>
				<span class="menu-content-text" id='add_group_menu'>
					%s
				</span>
			</span>
			<span class="menu-content-item">
				<img src="/images/24x24/shutdown.png"/>
				<span class="menu-content-text" id='import_group_menu'>
					%s
				</span>
			</span>
		</div>
	</div>
		%s
		<!--
		<div class="menu-item" >
		<div class="menu-title">
			<a href="/internet" class="menu_link" title="%s">
				<div class="menu-back "></div>
				<div class='menu-text'>%s</div>
			</a>
		</div>
		<div class="menu-content">
			<span class="menu-content-item">
				<img src="/images/24x24/shutdown.png"/>
				<span class="menu-content-text">
				blabla
				</span>
			</span>
			<span class="menu-content-item">
				<img src="/images/24x24/shutdown.png"/>
				<span class="menu-content-text">
				blabla
				</span>
			</span>
		</div>
	</div>
		-->
	<div class="menu-item" >
		<div class="menu-title">
			<a href="http://docs.licorn.org/userdoc/index.html" class="menu_link" title="%s">
				<div class="menu-back "></div>
				<div class='menu-text'>%s</div>
			</a>
		</div>
	</div>
	<div class="menu-item" >
		<div class="menu-title">
			<a href="mailto:support@meta-it.fr?subject=[Support Licorn®]" class="menu_link" title="%s">
				<div class="menu-back "></div>
				<div class='menu-text'>%s</div>
			</a>
		</div>
	</div>
</div>
<!--<div id="auxnav" class="nav">-->

</div>
''' % ( _('Server, UPS and hardware sub-systems status.'), _('Status'),
		_('Shutdown'), _('Restart'),
		_('Manage user accounts.'), _('Users'),
		_('Add'), _('Import'),
		_('Manage groups and shared data.'), _('Groups'),
		_('Add'), _('Import'),
		'\n'.join([ '''
		<div class="menu-item" >
			<div class="menu-title">
				<a href="/{menu_uri}/" class="menu_link" title="{menu_alt}">
					<div class="menu-back "></div>
					<div class='menu-text'>{menu_title}</div>
				</a>
			</div>
			<div class="menu-content">
				{menu_content}
			</div>
		</div>'''.format(
			menu_uri = ext.uri,
			menu_alt = ext.alt_string(),
			menu_title = ext.name(),
			menu_content = '\n'.join(['''
				<span class="menu-content-item">
					<img src="{sub_menu_icon}"/>
					<span class="menu-content-text">
						{sub_menu_text}
					</span>
				</span>
			'''.format(
				sub_menu_icon = icon,
				sub_menu_text = name) for name, link, alt, class_text, icon, fct in ext.context_menu()])
			) for ext in wmi.__dict__.values() if hasattr(ext, 'uri') ]
		),
		 _('Manage Internet connexion and parameters, firewall protection, URL filter and e-mail parameters.'), _('Internet'),
		_('Go to online documentation website.'), _('Documentation'),
		_('Get product support / help'), _('Support'),
		)
def page(title, data):
	return head(title) + data + tail()
def head(title=_("%s Management") % LMC.configuration.app_name):
	"""Build the HTML Page header.
	Bubble Tooltips come from:	http://www.dustindiaz.com/sweet-titles
	Rounded Divs comme from  : http://www.html.it/articoli/niftycube/index.html
	"""

	return """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
		<html xmlns="http://www.w3.org/1999/xhtml">
			<head>
			<title>%s %s</title>
			<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
				<!--
					<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/jquery-ui.css" />
					<link rel="stylesheet" type="text/css" href="/css/jquery.jqplot.css" />
				-->
				<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/style.css" />
				<script language="javascript" type="text/javascript" src="/js/jquery.js"></script>
				<script language="javascript" type="text/javascript" src="/js/jquery.gettext.js"></script>
				%s
				<script language="javascript" type="text/javascript" src="/js/jquery.easing.js"></script>
				<script language="javascript" type="text/javascript" src="/js/jquery.base64.js"></script>
				<script language="javascript" type="text/javascript" src="/js/utils.js"></script>
				<script language="javascript" type="text/javascript" src="/js/main.js"></script>
				<script language="javascript" type="text/javascript" src="/js/menu.js"></script>
				<!-- <script language="javascript" type="text/javascript" src="/js/tools.js"></script> -->
			</head>
			<body>""" % (
				_("%s WMI:") % LMC.configuration.app_name,
				title,
				'\n'.join('<link href="/js/json/%s" lang="%s" rel="gettext"/>' % (
						entry, entry.split('.')[1]
					) for entry in os.listdir('%s/wmi/js/json' % LMC.configuration.share_data_dir)
						if entry.endswith('.json'))
			)

def tail():
	return """
		</body>
	</html>
	"""

# LightBox type windows
def minihead(title = _("administration %s") % LMC.configuration.app_name):
	"""Build a mini-HTML page header, for lighbox type popups / windows.  """
	return """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>%s WMI: %s</title>
<link rel="shortcut icon" href="/favicon.ico" type="image/vnd.microsoft.icon" />
<link rel="icon" href="/favicon.ico" type="image/vnd.microsoft.icon" />
<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/style.css" />
<script type="text/javascript" src="/js/tools.js"></script>
<script type="text/javascript" src="/js/addEvent.js"></script>
</head>
<body>
""" % (LMC.configuration.app_name, title)
def minitail():
	return """</body></html>"""
def minipage(data):
	#return ('%s%s%s' % (minihead(title), data, minitail()))
	return data

def lbox(data, width = '300px', height = '100px'):
	return '''<div style=" margin-top: 20px; text-align: center; min-width: %s; min-height: %s;">%s\n</div>''' % (width, height, data)

# Image generation
def img(type = 'progressbar', width = 150, height = 22, text = ''):
	"""Create an img with GD, but look in the cache first if the image already exists."""

	# TODO: implement the cache here, before automatic file generation.

	#f=cStringIO.StringIO()
	#im.writePng(f)

	if type == 'progressbar':
		# return f
		pass
	else:
		return None


HTTP_TYPE_TEXT     = 1
HTTP_TYPE_IMG      = 2
HTTP_TYPE_DOWNLOAD = 3
HTTP_TYPE_REDIRECT = 4
HTTP_TYPE_AJAX     = 5
HTTP_TYPE_JSON     = 6
HTTP_TYPE_JSON_NOTIF    = 7

def main_content(content):
	return '''
	<div id="notification"></div>
	<div id="dialog" ></div>
	<div id='dialog-content'></div>
	<div id="content"> <!-- start content -->
		<div id=main_content> <!-- start main_content -->
			{content}
		</div> <!-- end main_content -->
		'''.format(content=content)
def sub_content(sub_content):
	return '''
		<div id=sub_content> <!-- start sub_content -->
			<div id="sub_content_main">
				%s
			</div>

		</div> <!-- end sub_content -->\n
		'''% sub_content

def ajax_response(data, notification):
	return '''
	<div class='ajax_response'>%s</div>
	<div class='notif'>%s</div>''' % (data, notification)

def notifications_success(msg):
	return '<span class="notifications_success">%s</span>' % msg

def notifications_error(msg):
	return '<span class="notifications_error">%s</span>' % msg

def notifications_color_name(msg):
	return '<span class="notifications_color_name">%s</span>' % msg
def notifications_color_uid(msg):
	return '<span class="notifications_color_uid">%s</span>' % msg
def notifications_color_comment(msg):
	return '<span class="notifications_color_comment">%s</span>' % msg
def notifications_color_regex(msg):
	return '<span class="notifications_color_regex">%s</div>' % msg

def my_unquote(string):
	try:
		return unquote_plus(string).decode('utf8')
	except UnicodeError:
		try:
			return unquote_plus(string).decode('ISO-8859-1')
		except UnicodeError:
			return unquote_plus(string)

def forgery_error(msg):
	return (HTTP_TYPE_JSON_NOTIF, msg)
