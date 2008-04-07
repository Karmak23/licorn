# -*- coding: utf-8 -*-
"""
Licorn webadmin functions.

These functions are used in the Web Administration Interface. They generate
HTML code, or forms, or provide useful tools to help web coding without too much headhaches.

Copyright (C) 2005-2008 Olivier Cortès <oc@5sys.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import os, cStringIO

from licorn.core import configuration

licence_text = """
%s GNU/Linux est distribué sous licence <a href="http://www.gnu.org/licenses/gpl.html">GNU GPL version 2</a> sans aucune garantie d'aucune sorte. Copyleft et droits d'auteurs &copy; 2007-2008 Olivier Cortès, Guillaume Masson &amp; Régis Cobrun pour le projet %s, ainsi qu'à tous les auteurs respectifs des logiciels libres utilisés (Notament Ubuntu, Debian, Python…).
""" % (configuration.app_name, configuration.app_name)

acronyms = {
	'SSH'  : 'Secure SHell (Protocole de connexion sécurisée à distance)',
	'FTP'  : 'File Transfer Protocol (protocole de transfert de fichiers)',
	'HTTP' : 'HyperText Transfert Protocol (Transfert de documents par liens HyperTexte)',
	'IMAP' : 'Internet Message Access Protocol (Protocole d\'accès à distance au courrier électronique)',
	'VNC'  : 'Virtual Network Computing (Protocole de prise en main d\'ordinateur à distance)',
	'RDP'  : 'Remote Desktop Protocol (Protocole de prise en main de bureau graphique à distance)',
	'POP'  : 'Post-Office Protocol (Procole simpliste de récupération du courrier électronique)',
	'SMTP' : 'Simple Mail Transfer Protocol (Protocole d\'envoi et relai du courrier électronique).',
	'RSA'  : 'Rivest Shamir Adleman (Protocole de cryptographie)',
	'DSA'  : 'Digital Signature Algorithm (Protocole de cryptographie)',
	'GNU'  : 'GNU is Not Unix (Acronyme récursif ; ensemble de logiciels libres composant le système de base d\' un Unix libre)',
	'LCN'  : 'Licorn System Tools (outils pour les administrateurs systèmes GNU/Linux, voir http://dev.licorn.org/)',
	'HAT'  : 'Licorn Admin Tools (outils de haut-niveau pour administrer un système GNU/Linux)'
	}

# EXEC / SYSTEM functions.
def run(command, uri, successfull_redirect = '/users/list', err_msg = 'Erreur durant l\'exécution de la commande') :
	"""Execute a command passed as a list or tuple"""
	
	if type(command) not in (type(()), type([])) :
		return error("La commande passée en paramètre doit être un tuple ou une liste Python&#160;!", command, "if type(command) not in (type(()), type([])) :")
	
	pin, pout, perr = os.popen3(command)

	# wait for the command to finish and close output pipe.
	pout.read()
	
	# read standard error to see if something went wrong.
	err = perr.read()[:-1]

	if err != "" :
		return error(err_msg, command, err.replace('>', '&gt;').replace('<', '&lt;'))
	else :
		if successfull_redirect != None :
			#util.redirect(req, successfull_redirect)
			#return True
			return ''
		else :
			return ''
			#return True
def total_time(start, end) :
	elapsed = end - start
	ptime   = ""
	if elapsed > 3600 :
		h = elapsed / 3600
		ptime += "%d heures," % h
		elapsed -= h * 3600
	if elapsed > 60 :
		m = elapsed / 60
		ptime += " %d minutes," % m
		elapsed -= m * 60
	ptime += " %.3f secondes." % elapsed
	return '''<div id="timer_container"><div id="timer">Temps d'exécution total du moteur (hors temps de rendu graphique par le navigateur)&#160;: %s</div></div>''' % ptime

# AJAX Functions
def doubleListBox(titles, id, values_source = [], values_dest = []) :

	def selectbox(legend, id, option_id_prefix = "", values = []) :
		data = '<fieldset style="height: 100%%"><legend>%s</legend><select name="%s" class="multiselect" multiple="multiple" id="%s" style="width: 100%%; height: 90%%; vertical-align: middle;">' % (legend, id, id)
		for value in values :
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

# GRAPHICAL functions
def question(title, message, yes_values, no_values, form_options = None) :
	"""Build ha HTML Question / Confirmation FORM.
		{yes,no}_values = ("value of the button or link", "href of link, or action of form", "accesskey" )
	***ACCESSKEYS for buttons are not yet implemented***
	"""
	
	data = """
<div id="question">
	<div class="title">%s</div>
	<div class="description">%s</div>
	""" % (title, message)

	if form_options :
		data += '	<div class="options"><form name="yes_action" action="%s" method="post">%s</div>\n' % (yes_values[1], form_options)

	data += """
	<table>
		<tr>"""

	if form_options :
		data+= """
		<td class="cancel">%s</td>
		<td class="confirm">%s</form></td>
		""" % (button(no_values[0], no_values[1]), submit("yes", yes_values[0]))

	else :
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
def hcadre(text, id = None) :
	if id :
		id = 'id="%s"' % id
	else :
		id = ""
	return '''<div class="hcadre" %s>%s</div>''' % (id, text)
def error(text, command = [ "inconnue" ], error = "inconnue") :
	return '''
	<div id="command_error">
		<div class="error_title">%s</div>
		La commande lancée était&#160;:<br /><br />
		<code>%s</code><br /><br />
		L'erreur rapportée par le système est&#160;:<br /><br />
		<pre>%s</pre>
		</div>
		''' % (text, " ".join(command), error)
def backto() :
	return '<div id="backto"><a href="/" title="retourner vers la racine de l\'interface d\'administration."><img src="/images/webadmin.png" alt="retourner vers la racine de l\'interface d\'administration." /></a></div>'

# HTML FORM functions
def access_key(key) :
	if key :
		return ' accesskey="%s"' % key
	else :
		return ''
def reset(value = "Revenir au valeurs d'origine") :
	return '<input type="reset" value="%s" />' % (value)
def submit(name, value = "", onClick = "") :
	if value == "" : value = name
	if onClick != "" : onClickValue = 'onClick="%s"' % onClick
	else : onClickValue = ""
	return '<input type="submit" name="%s" value="%s" %s />' % (name, value, onClickValue)
def button(label, value, accesskey = None) :
	return '<a href="%s"><button type="button" %s>%s</button></a>' % (value, access_key(accesskey), label)
def select(name, values, current = "", dont_display = (), func = str, accesskey = None) :
	data = '\n			<select name="%s" %s>\n' % (name, access_key(accesskey))
	for value in values :
		if value in dont_display : continue
		elif value == current : selected = "selected=selected"
		else : selected = ""
		data += '				<option value="%s" %s>%s</option>\n' % (value, selected, func(value))
	data += '			</select>\n'
	return data
def	input(name, value, size = 20, maxlength = 1024, disabled = False, password = False, accesskey = None) :
	if disabled : disabled = 'disabled="disabled"'
	else : disabled = ""
	if password : type = "password"
	else : type = "text"
	return '<input type="%s" name="%s" value="%s" size="%d" maxlength="%d" %s %s />\n' % (type, name, value, size, maxlength, disabled, access_key(accesskey)) 
def	checkbox(name, value, label, checked = False, disabled = False, accesskey = None) :
	if disabled :
		disabled = 'disabled="disabled"'
	else :
		disabled = ""
	if checked :
		checked = 'checked="checked"'
	else :
		checked = ""
	return '<label><input type="checkbox" name="%s" value="%s" %s %s %s />&#160;%s</label>\n' % (name, value, checked, disabled, access_key(accesskey), label) 

# HTML DOCUMENT functions
def acr(word) :
	try :
		return '<acronym title="%s">%s</acronym>' % (acronyms[word.upper()], word)
	except KeyError :
		return word
def menu(uri) :
	
	class defdict(dict) :
		def __init__(self, default='') :
			dict.__init__(self)
			self.default = default
		def __getitem__(self, key) :
			try :
				return dict.__getitem__(self, key)
			except KeyError :
				return self.default

	classes = defdict()

	if uri == '/' :
		classes['/'] = ' class="active"'
	else :
		classes[uri.split('/')[1].split('.')[0]] = ' class="active"'

	return '''
<div id="menu">
<ul>
<li%s><a href="/" title="État et charge du serveur, de l'onduleur, des sous-systèmes matériels et logiciels de la machine.">État</a></li>
<li%s><a href="/users/" title="Gérer les comptes utilisateurs.">Utilisateurs</a></li>
<li%s><a href="/groups/" title="Gérer les groupes et les données partagées.">Groupes</a></li>
<li%s><a href="/internet/" title="Gérer la connexion internet et ses paramètres, les protections par pare-feu et filtrage d'URL, les services de courrier électronique.">Internet</a></li>
</ul>
</div>

<div id="helpmenu">
<ul>
<li%s><a href="/support/" title="Obtenir du support sur le produit.">Support</a></li>
<li><a href="http://docs.licorn.org/webadmin" title="Accéder à l'aide en ligne de webadmin (dans une nouvelle fenêtre ou un nouvel onglet).">Documentation</a></li>
</div>
''' % (classes['/'], classes['users'], classes['groups'], classes['internet'], classes['support'])
def page(title, data) :
	return head(title) + data + tail()
def head(title = "administration d'%s" % configuration.app_name) :
	"""Build the HTML Page header.
	Bubble Tooltips come from :	http://www.dustindiaz.com/sweet-titles
	Rounded Divs comme from   : http://www.html.it/articoli/niftycube/index.html
	"""
	return """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>Webadmin : %s</title>
<link rel="shortcut icon" href="/favicon.ico" type="image/vnd.microsoft.icon" />
<link rel="icon" href="/favicon.ico" type="image/vnd.microsoft.icon" />
<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/style.css" />
<link rel="stylesheet" type="text/css" media="screen,projection" href="/css/sweetTitles.css" />
<script type="text/javascript" src="/js/tools.js"></script>
<script type="text/javascript" src="/js/niftyCube.js"></script>
<script type="text/javascript" src="/js/sweetTitles.js"></script>
<script type="text/javascript" src="/js/addEvent.js"></script>
</head>
<body>
""" % (title) 
def tail() :
	return """
%s
</body>
</html>
""" % hcadre(licence_text, "license")


# Image generation
def img(type = 'progressbar', width = 150, height = 22, text = '') :
	"""Create an img with GD, but look in the cache first if the image already exists."""

	# TODO: implement the cache here, before automatic file generation.

	#f=cStringIO.StringIO()
	#im.writePng(f)

	if type == 'progressbar' :
		# return f
		pass
	else :
		return None

