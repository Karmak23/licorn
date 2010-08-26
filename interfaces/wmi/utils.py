# -*- coding: utf-8 -*-
"""
Licorn WMI functions.

These functions are used in the Web Administration Interface. They generate
HTML code, or forms, or provide useful tools to help web coding without too much headhaches.

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.

"""

from gettext import gettext as _

import os, cStringIO
from subprocess  import Popen, PIPE

from licorn.core.configuration import LicornConfiguration

configuration = LicornConfiguration()

licence_text = _('''
%s is distributed under the <a href="http://www.gnu.org/licenses/gpl.html">GNU
 GPL version 2</a> license, without any kind of waranty. Copyleft &copy;
 2007-2008 Olivier Cortès, Guillaume Masson &amp; Régis Cobrun for project %s,
  and all other libre software developers (Notably Ubuntu, Debian, Python…).
''') % (configuration.app_name, configuration.app_name)

acronyms = {
	'SSH' : _('Secure SHell (Secure remote connexion and commands protocol)'),
	'FTP' : _('File Transfer Protocol'),
	'HTTP': _('HyperText Transfert Protocol'),
	'IMAP': _('Internet Message Access Protocol'),
	'VNC' : _('Virtual Network Computing (Desktop remote connexion protocol)'),
	'RDP' : _('Remote Desktop Protocol (Desktop remote connexion protocol)'),
	'POP' : _('Post-Office Protocol (Simple mail fetching protocol)'),
	'SMTP': _('Simple Mail Transfer Protocol'),
	'RSA' : _('Rivest Shamir Adleman (cryptography protocol)'),
	'DSA' : _('Digital Signature Algorithm'),
	'GNU' : _('''GNU is Not Unix (recursive acronym ; a set of libre sofware
		composing a libre operating system)'''),
	'LCN' : _('''LiCorN system tools (tools for IT managers,
		see http://dev.licorn.org/)'''),
	'LAT' : _('''Licorn Admin Tools (High-level management tools for
		a GNU/Linux system)''')
	}

# EXEC / SYSTEM functions.
def run(command, successfull_redirect, page_data, error_message):
	"""Execute a command passed as a list or tuple"""

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
	return '''
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
		selectbox(titles[2], id_right, id, values_dest) )

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
def error(text, command = [ "inconnue" ], error = "inconnue"):
	return '''
	<div id="command_error">
		<div class="error_title">%s</div>
		La commande lancée était&#160;:<br /><br />
		<code>%s</code><br /><br />
		L'erreur rapportée par le système est&#160;:<br /><br />
		<pre>%s</pre>
		</div>
		''' % (text, " ".join(command), error)
def backto():
	return '<div id="header"><a id="logo" href="/" title="retourner vers la racine de l\'interface d\'administration."><img src="/images/logo_licorn_120.png" alt="retourner vers la racine de l\'interface d\'administration." /></a></div>'
def metanav(http_user):
	""" Minimal function to display the user logged in.
		Will implement links to preferences, later.
	"""
	return '<div id="metanav" class="nav"><ul><li>%s</li></ul></div>' \
	% (_('Logged in as %s') % http_user)
def page_body_start(uri, http_user, ctxtnav, title, active=True):
	return '''<div id="banner">
	%s
	%s
	%s
</div><!-- banner -->
<div id="main">
%s
<div id="content">
	<h1>%s</h1>
	''' % (
		backto(), metanav(http_user), menu(uri), ctxtnav(active), title)
def page_body_end(data=''):
	return '''</div><!-- content -->\n%s\n</div><!-- main -->''' % data
def forgery_error(title):
	return (w.HTTP_TYPE_TEXT, w.page(title,
		w.error(_("Forbidden action"),
		[ _("Some parts of the system cannot be modified.") ],
		_("insufficient permissions to perform operation."))))

# HTML FORM functions
def access_key(key):
	if key:
		return ' accesskey="%s"' % key
	else:
		return ''
def reset(value = "Revenir au valeurs d'origine"):
	return '''<input type="reset" value="%s" />''' % (value)
def submit(name, value = "", onClick = "", accesskey = None):
	if value == "": value = name
	if onClick != "": onClickValue = 'onClick="%s"' % onClick
	else: onClickValue = ""
	return '''<input type="submit" name="%s" value="%s" %s %s />''' % (name, value, onClickValue, access_key(accesskey))
def button(label, value, accesskey = None):
	return '''<a href="%s"><button type="button" %s>%s</button></a>''' % (value, access_key(accesskey), label)
def select(name, values, current = "", dont_display = (), func = str, accesskey = None):
	data = '<select name="%s" %s>\n' % (name, access_key(accesskey))
	for value in values:
		if value in dont_display: continue
		elif value == current: selected = "selected=selected"
		else: selected = ""
		data += '	<option value="%s" %s>%s</option>\n' % (value, selected, func(value))
	data += '</select>'
	return data
def	input(name, value, size = 20, maxlength = 1024, disabled = False, password = False, accesskey = None):
	if disabled: disabled = 'disabled="disabled"'
	else: disabled = ""
	if password: type = "password"
	else: type = "text"
	return '''<input type="%s" name="%s" value="%s" size="%d" maxlength="%d" %s %s />''' % (type, name, value, size, maxlength, disabled, access_key(accesskey))
def	checkbox(name, value, label, checked = False, disabled = False, accesskey = None):
	if disabled:
		disabled = 'disabled="disabled"'
	else:
		disabled = ""
	if checked:
		checked = 'checked="checked"'
	else:
		checked = ""
	return '''<label><input type="checkbox" name="%s" value="%s" %s %s %s />&#160;%s</label>''' % (name, value, checked, disabled, access_key(accesskey), label)

# HTML DOCUMENT functions
def acr(word):
	try:
		return '<acronym title="%s">%s</acronym>' % (acronyms[word.upper()], word)
	except KeyError:
		return word
def menu(uri):

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
<ul>
<li%s><a href="/" title="%s">%s</a></li>
<li%s><a href="/users/" title="%s">%s</a></li>
<li%s><a href="/groups/" title="%s">%s</a></li>
<!--<li%s><a href="/machines/" title="%s">%s</a></li>
<li%s><a href="/internet/" title="%s">%s</a></li>-->
</ul>
</div>
<div id="auxnav" class="nav">
<ul>
<li><a href="http://dev.licorn.org/wiki/UserDoc/WMI" title="%s">%s</a></li>
<li%s><a href="mailto:support@meta-it.fr?subject=[support] " title="%s">%s</a></li>
</ul>
</div>
''' % (classes['/'], _('Server, UPS and hardware sub-systems status.'), _('Status'),
		classes['users'], _('Manage user accounts.'), _('Users'),
		classes['groups'], _('Manage groups and shared data.'), _('Groups'),
		classes['machines'], _('Manage network clients: computers, printers, switches and other network enabled active systems.'), _('Machines'),
		classes['internet'], _('Manage Internet connexion and parameters, firewall protection, URL filter and e-mail parameters.'), _('Internet'),
		_('Go to online documentation and community website (in new window or new tab).'), _('Documentation'),
		classes['support'], _('Get product support / help'), _('Support')
		)
def page(title, data):
	return head(title) + data + tail()
def head(title=_("%s Management") % configuration.app_name):
	"""Build the HTML Page header.
	Bubble Tooltips come from:	http://www.dustindiaz.com/sweet-titles
	Rounded Divs comme from  : http://www.html.it/articoli/niftycube/index.html
	"""
	return """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>%s %s</title>
<link rel="shortcut icon" href="/favicon.ico" type="image/vnd.microsoft.icon" />
<link rel="icon" href="/favicon.ico" type="image/vnd.microsoft.icon" />
<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/style.css" />
<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/sweetTitles.css" />
<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/lightwindow.css" />
<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/accordion.css" />
<script type="text/javascript" src="/js/tools.js"></script>
<script type="text/javascript" src="/js/niftyCube.js"></script>
<script type="text/javascript" src="/js/sweetTitles.js"></script>
<script type="text/javascript" src="/js/addEvent.js"></script>
<script type="text/javascript" src="/js/prototype.js"></script>
<script type="text/javascript" src="/js/effects.js"></script>
<script type="text/javascript" src="/js/lightwindow.js"></script>
<script type="text/javascript" src="/js/accordion.js"></script>
</head>
<body>
""" % (_("%s WMI:") %configuration.app_name, title)
def tail():
	return """\n</body></html>"""

# LightBox type windows
def minihead(title = _("administration %s") % configuration.app_name):
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
""" % (configuration.app_name, title)
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
