# -*- coding: utf-8 -*-

import os, time

from licorn.foundations    import exceptions, hlstr, logging
from licorn.core           import configuration, groups, users, profiles
from licorn.interfaces.web import utils as w

groups_filters_lists_ids = ( 
	(groups.FILTER_STANDARD, [_('Personnaliser les Groupes'),     _('Groupes disponibles'),         _('Groupes affectés')],           'standard_groups'),
	(groups.FILTER_PRIVILEGED, [_('Affiner les privilèges'),        _('Privilèges disponibles'),      _('Privilèges octroyés')],        'privileged_groups'),
	(groups.FILTER_RESPONSIBLE, [_('Attribuer des responsabilités'), _('Responsabilités disponibles'), _('Responsabilités attribuées')], 'responsible_groups'), 
	(groups.FILTER_GUEST, [_('Proposer des invitations'),      _('Invitations disponibles'),     _('Invitations offertes')],       'guest_groups') )

rewind = "<br /><br />Revenez en arrière avec votre navigateur, vérifiez-les et revalidez le formulaire."

# private functions.
def __merge_multi_select(*lists) :
	final = []
	for list in lists :
		if list == [] : continue
		if type(list) == type("") :
			final.append(list)
		else :
			final.extend(list)
	return final
def __users_actions() :
	return '''
<div id="actions">
<table>
	<tr>
		<td><a href="/users/new" title="%s"><img src="/images/32x32/user-new.png" alt="%s" /><br />%s</a></td>
		<td><a href="/users/import" title="%s"><img src="/images/import-users.png" alt="%s" /><br />%s</a></td>
		<td><a href="/users/export" title="%s"><img src="/images/export-users.png" alt="%s" /><br />%s</a></td>
	</tr>
</table>
</div>
	''' % (
		_("Ajouter un nouvel utilisateur sur le système."),
		_("Ajouter un compte."),
		_("Ajouter un compte"),
		_("Importer une liste de nouveaux utilisateurs depuis un fichier CSV."),
		_("Importer des comptes."),
		_("Importer des comptes"),
		_("Exporter la liste des utilisateurs actuels vers un fichier CSV ou XML."),
		_("Exporter les comptes."),
		_("Exporter les comptes")
		)

def export(uri, type = "", yes = None) :
	"""export."""

	# TODO : reload(profiles)
	groups.reload()
	users.reload()

	del yes

	title = _("Export des comptes utilisateurs")
	data  = '%s%s' % (w.backto(), __users_actions())

	if type == "" :
		description = _('''Le format CSV est utilisé par les tableurs et la plupart des systèmes qui offrent des possibilités d'import. Le format XML est un format d'échanges de données moderne utilisé par des applications qui respectent certaines normes ou recommandations d'interopérabilité. <br /><br />Lorsque vous cliquerez sur "Exporter", votre navigateur vous proposera automatiquement d'enregistrer ou d'ouvrir le fichier d'export, il ne l'affichera pas comme une page web. Lorsque vous avez terminé, cliquez sur "Revenir".''')
		
		form_options = _("Sous quelle forme voulez-vous exporter les comptes&nbsp;? %s") % w.select("type", [ "CSV", "XML"])
	
		data += w.question(_("Choisissez le format d'export pour la liste des comptes"),
			description,
			yes_values   = [ _("Exporter >>"), "/users/export", "E" ],
			no_values    = [ _("<< Revenir"),  "/users/list",   "N" ],
			form_options = form_options)

		return w.page(title, data)

	else :
		users.Select(users.FILTER_STANDARD)

		# TODO: convert this.
		#req.headers_out["Content-type"]        = "application/force-download"
		#req.headers_out["Content-Disposition"] = "attachment; filename=export.%s" % type.lower()
		#header("Pragma: no-cache");
		#header("Expires: 0");

		if type == "CSV" : 
			return users.ExportCSV()
		else :
			return users.ExportXML()

# delete a user account.
def delete(uri, login, sure = False, no_archive = False, yes = None) :
	"""remove user account."""

	# forget about it, this is a scoria from the POST FORM to variable conversion.
	del yes

	title = _("Suppression du compte %s") % login
	data  = '%s<h1>%s</h1><br />' % (w.backto(), title)

	
	if not sure :
		data += w.question(_("Êtes-vous sûr(e) de vouloir supprimer le compte <strong>%s</strong>&#160;?") % login,
			_("""<strong>Les données personnelles</strong> de l'utilisateur (son home dir) <strong>seront archivées</strong>
				dans le répertoire <code>%s</code> et accessibles aux membres du groupe
				<strong>administrateurs</strong> pour une récupération éventuelle.<br />
				Vous pouvez cependant décider de les effacer définitivement.""") % (configuration.home_archive_dir),
			yes_values   = [ "Supprimer >>", "/users/delete/%s/sure" % login, "S" ],
			no_values    = [ "<< Annuler",   "/users/list",                   "N" ],
			form_options = w.checkbox("no_archive", "True", 
				_("Supprimer définitivement toutes les données avec le compte."),
				checked = False) )

		return w.page(title, data)

	else :
		users.reload()
		if users.is_system_login(login) :
			return w.page(title, w.error(_("Suppression de compte impossible"), [ _("tentative de suppression de compte non standard.") ], _("permissions insuffisantes pour mener à bien l'opération (non mais, tu croyais vraiment que j'allais le faire ?).")))

		# we are sure, do it !
		command = [ 'sudo', 'del', 'user', '--quiet', '--no-colors', '--login', login ]

		if no_archive :
			command.extend(['--no-archive'])
		
		return w.page(title, data + 
			w.run(command, uri, err_msg = _("Impossible de supprimer le compte <strong>%s</strong>&#160;!") % login))
		
# locking and unlocking.
def unlock(uri, login) :
	"""unlock a user account password."""

	title   = _("Déverrouillage du compte %s") % login
	data    = '%s<h1>%s</h1><br />' % (w.backto(), title)

	users.reload()
	if users.is_system_login(login) :
		return w.page(title, w.error(_("Déverrouillage de compte impossible"), [ _("tentative de déverrouillage de compte non standard.") ], _("permissions insuffisantes pour mener à bien l'opération.")))

	command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login", login, "--unlock" ]
	return w.page(title, data + 
		w.run(command, uri, err_msg = _("Impossible de déverrouiller le compte <strong>%s</strong>&#160;!") % login))
def lock(uri, login, sure = False, remove_remotessh = False, yes = None) :
	"""lock a user account password."""

	# forget about it, this is a scoria from the POST FORM to variable conversion.
	del yes
	
	groups.reload()
	users.reload()

	title = _("Verrouillage du compte %s") % login
	data  = '%s<h1>%s</h1><br />' % (w.backto(), title)

	if not sure :
		description = _('''Cela l'empêchera de se connecter sur les terminaux légers
			 %s/Linux et les postes autonomes Windows&reg; et Macintosh&reg;.''') % w.acr('GNU')
		
		# TODO : Vérifier que le groupe "remotessh" existe bien sur le système...
		if login in groups.all_members('remotessh') :
			description += _("""<br /><br />
				Mais <em>cela n'empêchera pas les connexions à distance par %s</em>
				si cet utilisateur se sert de clés %s %s/%s pour se connecter.
				Pour lui interdire complètement l'accès au système, 
				<strong>retirez-le aussi du groupe remotessh</strong>.""") % (w.acr('SSH'), w.acr('SSH'), w.acr('RSA'), w.acr('DSA'))
			form_options = w.checkbox("remove_remotessh", "True",
				_("Supprimer l'utilisateur du groupe <code>remotessh</code> en même temps."),
				checked = True, accesskey = 'R')
		else :
			form_options = None
	
		data += w.question(_("Êtes-vous sûr(e) de vouloir verrouiller le mot de passe du compte <strong>%s</strong>&#160;?") % login,
			description,
			yes_values   = [ _("Verrouiller >>"), "/users/lock/%s/sure" % login, "V" ],
			no_values    = [ _("<< Annuler"),     "/users/list",                 "N" ],
			form_options = form_options)

		return w.page(title, data)

	else :
		if users.is_system_login(login) :
			return w.page(title, w.error(_("Verrouillage de compte impossible"), [ _("tentative de verrouillage de compte non standard.") ], _("permissions insuffisantes pour mener à bien l'opération (non mais, tu y croyais vraiment ?).")))

		# we are sure, do it !
		command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login", login, "--lock" ]

		if remove_remotessh :
			command.extend(['--del-groups', 'remotessh'])
		
		return w.page(title, data +
			w.run(command, uri, err_msg = _("Impossible de verrouiller le compte <strong>%s</strong>&#160;!") % login))

# skel reapplyin'
def skel(uri, login, sure = False, apply_skel = configuration.users.default_skel, yes = None) :
	"""reapply a user's skel with confirmation."""

	# forget about it, this is a scoria from the POST FORM to variable conversion.
	del yes
	
	# TODO : profiles.reload()
	groups.reload()
	users.reload()
	
	u = users.users
	g = groups.groups

	title = _("Réapplication du profil pour le compte %s") % login
	data  = '%s<h1>%s</h1><br />' % (w.backto(), title)

	if users.is_system_login(login) :
		return w.page(title, w.error(_("Suppression de compte impossible"), [ _("tentative de suppression de compte non standard.") ], _("permissions insuffisantes pour mener à bien l'opération.")))

	if not sure :
		description = _('''Cela remettra son bureau à zéro, avec les icônes d'origine.<br /><br /><strong>Il est nécessaire que l'utilisateur soit déconnecté du système pour que l'opération réussisse.</strong>''')
		
		pri_group = g[u[users.login_to_uid(login)]['gid']]['name']
		
		# liste des skels du profile en cours.
		def filter_skels(pri_group, sk_list) :
			'''
			TODO: to be converted to licorn model
			if pri_group == configuration.mNames['RESPONSABLES_GROUP'] :
				return filter(lambda x: x.rfind("/%s/" % configuration.mNames['RESPONSABLES_GROUP']) != -1, sk_list)
			elif pri_group == configuration.mNames['USAGERS_GROUP'] :
				return filter(lambda x: x.rfind("/%s/" % configuration.mNames['USAGERS_GROUP']) != -1, sk_list)
			else :
			'''
			return sk_list
			
		form_options = _("Quel skelette voulez-vous lui appliquer&nbsp;? %s") % w.select("apply_skel", filter_skels(pri_group, configuration.users.skels), func = os.path.basename)
	
		data += w.question(_("Êtes-vous sûr(e) de vouloir ré-appliquer le profil au compte <strong>%s</strong>&#160;?") % login,
			description,
			yes_values   = [ _("Appliquer >>"), "/users/skel/%s/sure" % login, "V" ],
			no_values    = [ _("<< Annuler"),     "/users/list",                 "N" ],
			form_options = form_options)

		return w.page(title, data)

	else :
		# we are sure, do it !
		command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login", login, '--apply-skel', skel ]

		return w.page(title, data +
			w.run(command, uri, err_msg = _("Impossible d'appliquer le skelette <strong>%s</strong> sur le compte <strong>%s</strong>&#160;!") % (os.path.basename(apply_skel), login)))

# user account creation
def new(uri) :
	"""Generate a form to create a new user on the system."""

	# TODO : profiles.reload()
	groups.reload()
	
	g = groups.groups
	p = profiles.profiles
	
	title = _("Création d'un compte utilisateur")
	data  = '%s%s\n%s\n' % (w.backto(), __users_actions(), w.menu(uri))

	def profile_input() :

		#TODO : To be rewritten ?
		return """
	<tr>
		<td><strong>%s</strong></td><td>%s</td>
	</tr>
			""" % (_("Ce compte sera un"), w.select('profile',  p.keys(), func = lambda x: p[x]['name']))
	def gecos_input() :
		return """
	<tr>
		<td><strong>%s</strong></td><td>%s</td>
	</tr>
			""" % (_("Nom Complet"), w.input('gecos', "", size = 30, maxlength = 64, accesskey = 'N'))
	def shell_input() :
		return w.select('loginShell',  configuration.users.shells, current = configuration.users.default_shell, func = os.path.basename)

	dbl_lists = {}
	for filter, titles, id in groups_filters_lists_ids :
		groups.Select(filter)
		dest   = []
		source = [ g[gid]['name'] for gid in groups.filtered_groups ]
		source.sort()
		dbl_lists[filter] = w.doubleListBox(titles, id, source, dest)

	form_name = "user_edit"

	data += '''<div id="edit_user">
<form name="%s" id="%s" action="/users/create" method="post">
<table id="user_account">
	%s
	%s
	<tr>
		<td><strong><a href="#" class="help" title="%s">%s</a></strong> %s</td><td>%s</td>
	</tr>
	<tr>
		<td><strong>%s</strong></td><td>%s</td>
	</tr>
	<tr>
		<td><strong><a href="#" class="help" title="%s">%s</a></strong><br /></td><td>%s</td>
	</tr>
	<tr>
		<td>%s</td><td>%s</td>
	</tr>
	<tr><td colspan="2" class="double_selector">%s</td></tr>
	<tr><td colspan="2" class="double_selector">%s</td></tr>
	<tr><td colspan="2" class="double_selector">%s</td></tr>
	<tr><td colspan="2" class="double_selector">%s</td></tr>
	<tr>
		<td class="paddedleft">%s</td>
		<td class="paddedright">%s</td>
	</tr>
</table>
</form>
</div>
	''' % ( form_name, form_name,
		profile_input(),
		gecos_input(),
		_("""Le mot de passe doit comporter au moins %d caractères. Vous pouvez utiliser toutes
			les lettre de l'alphabet, les chiffres, les caractères spéciaux et les signes de
			ponctuation sauf '?!'.""") % configuration.mAutoPasswdSize,
		_("Mot de passe"), _("(%d car. min.)") % configuration.mAutoPasswdSize,
		w.input('password', "", size = 30, maxlength = 64, accesskey = 'P', password = True),
		_("Confirmation du MDP."), w.input('password_confirm', "", size = 30, maxlength = 64, password = True ),
		_("""L'identifiant doit être saisi en lettres minuscules, sans accents ni caractères spéciaux 
			(vous pouvez cependant utiliser le point et le tiret).<br /><br />Si vous laissez le champ
			vide, l'identifiant sera automatiquement déterminé depuis le nom complet."""),
		_("Identifiant"), w.input('login', "", size = 30, maxlength = 64, accesskey = 'L'),
		_("<strong>Shell de connexion</strong>br />(interpréteur de commandes Unix)"), shell_input(),	
		dbl_lists[groups.FILTER_STANDARD], dbl_lists[groups.FILTER_PRIVILEGED],
		dbl_lists[groups.FILTER_RESPONSIBLE], dbl_lists[groups.FILTER_GUEST],
		w.button('<< Annuler', "/users/list"),
		w.submit('create', 'Créer >>', onClick = "selectAllMultiValues('%s');" % form_name)
		)
	return w.page(title, data)
def create(uri, loginShell, password, password_confirm, profile = None, login = "", gecos = "", firstname = "", lastname = "",
	standard_groups_dest = [], privileged_groups_dest = [], responsible_groups_dest = [], guest_groups_dest = [],
	standard_groups_source = [], privileged_groups_source = [], responsible_groups_source = [], guest_groups_source = [],
	create = None ) :

	# forget about it, this is a scoria from the POST FORM to variable conversion.
	del create

	title      = _("Création du compte %s") % login
	data       = '%s<h1>%s</h1><br />' % (w.backto(), title)
	
	if password != password_confirm :
		return w.page(title, data + w.error(_("Les mots de passe ne correspondent pas&#160;!%s") % rewind))

	if len(password) < configuration.mAutoPasswdSize :
		return w.page(title, data + w.error(_("Le mot de passe doit comporter au moins %d caractères&#160;!%s") % (configuration.mAutoPasswdSize, rewind)))

	command = [ "sudo", "add", "user", '--quiet', '--no-colors', '--password', password ]

	if firstname != '' and lastname != '' :
		command.extend(['--firstname', firstname, '--lastname', lastname])
	if gecos != '' :
		command.extend(['--gecos', gecos])
	
	# TODO : set a default profile (see issue #6)
	if profile != None :
		command.extend([ "--profile", profile ])

	if login != "" :
		command.extend([ "--login", login ])
	else :
		# TODO : Idem, "gecos" should be tested against emptyness
		command.extend([ '--login', hlstr.validate_name(gecos).replace('_', '.').rstrip('.') ])
	
	retval = w.run(command, uri, err_msg = _('Erreur à la création du compte <strong>%s</strong>&#160;!') % login)

	# TODO : Change test since message received : Added user <login>
	if retval != "" :
		return w.page(title, data + retval)
	
	command    = [ "sudo", "mod", "user", '--quiet', "--no-colors", "--login", login, "--shell", loginShell ]
	add_groups = ','.join(__merge_multi_select(standard_groups_dest, privileged_groups_dest, responsible_groups_dest, guest_groups_dest))

	if add_groups != "" :
		command.extend([ '--add-groups', add_groups ])

	return w.page(title, 
		data + w.run(command, uri,
		err_msg = _('Impossible d\'inscrire l\'utilisateur <strong>%s</strong> dans un ou plusieurs groupes demandés&#160;!') % login))

# record user account edition.
def record(uri, login, loginShell = configuration.users.default_shell,
	password = "", password_confirm = "",
	firstname = "", lastname = "", gecos = "",
	standard_groups_source    = [],    standard_groups_dest = [],
	privileged_groups_source  = [],  privileged_groups_dest = [],
	responsible_groups_source = [], responsible_groups_dest = [],
	guest_groups_source       = [],       guest_groups_dest = [],
	record = None) :
	"""Record user account changes."""

	# forget about it, this is a scoria from the POST FORM to variable conversion.
	del record

	title      = _("Modification du compte %s") % login
	data       = '%s<h1>%s</h1><br />' % (w.backto(), title)
	command    = [ "sudo", "mod", "user", '--quiet', "--no-colors", "--login", login, "--shell", loginShell ]

	users.reload()
	if users.is_system_login(login) :
		return w.page(title, w.error(_("Enregistrement de compte impossible"), [ _("tentative de modification de compte non standard.") ], _("permissions insuffisantes pour mener à bien l'opération (dis-donc, tu n'essaierais pas de t'amuser par hasard ?).")))

	if password != "" :
		if password != password_confirm :
			return w.page(title, data + w.error(_("Les mots de passe ne correspondent pas&#160;!%s") % rewind))
		if len(password) < configuration.mAutoPasswdSize :
			return w.page(title, data + w.error(_("Le mot de passe --%s-- doit comporter au moins %d caractères&#160;!%s") % (password, configuration.mAutoPasswdSize, rewind)))

		command.extend([ '--password', password ])

	command.extend( [ "--gecos", gecos ] )

	add_groups = ','.join(__merge_multi_select(standard_groups_dest,   privileged_groups_dest,   responsible_groups_dest,   guest_groups_dest))
	del_groups = ','.join(__merge_multi_select(standard_groups_source, privileged_groups_source, responsible_groups_source, guest_groups_source))

	if add_groups != "" :
		command.extend([ '--add-groups', add_groups ])
		
	if del_groups != "" :
		command.extend(['--del-groups', del_groups ])

	return w.page(title, data + w.run(command, uri, err_msg = _('Impossible de modifier un ou plusieurs paramètre(s) du compte <strong>%s</strong>&#160;!') % login))

# edit user accout parameters.
def edit(uri, login) :
	"""Edit an user account, based on login."""

	groups.reload()
	users.reload()
	# TODO: profiles.reload()

	title = _('Édition du compte %s') % login 
	data  = '%s\n%s\n%s<br />\n' % (w.backto(), __users_actions(), w.menu(uri))

	if users.is_system_login(login) :
		return w.page(title, w.error(_('Édition de compte impossible'), [ _("tentative d'édition de compte non standard.") ], _("permissions insuffisantes pour mener à bien l'opération.")))

	try :
		user = users.users[users.login_to_uid(login)]

		try :
			profile = profiles.profiles[groups.groups[user['gid']]['name']]['name']
		except KeyError :
			profile = _("Standard account")

		dbl_lists = {}
		for filter, titles, id in groups_filters_lists_ids :
			groups.Select(filter)
			dest   = list(user['groups'].copy())
			source = [ groups.groups[gid]['name'] for gid in groups.filtered_groups ]
			for current in dest[:] :
				try : source.remove(current)
				except ValueError : dest.remove(current)
			dest.sort()
			source.sort()
			dbl_lists[filter] = w.doubleListBox(titles, id, source, dest)

		form_name = "user_edit_form"

		data += '''<div id="edit_user">
<form name="%s" id="%s" action="/users/record/%s" method="post">
	<table id="user_account">
		<tr>
			<td>%s</td><td class="not_modifiable">%d</td>
		</tr>
		<tr>
			<td>%s</td><td class="not_modifiable">%s</td>
		</tr>
		<tr>
			<td>%s</td><td class="not_modifiable">%s</td>
		</tr>
		<tr>
			<td>%s</td><td>%s</td>
		</tr>
		<tr>
			<td><strong><a href="#" class="help" title="%s">%s</a></strong> %s</td><td>%s</td>
		</tr>
		<tr>
			<td><strong>%s</strong></td><td>%s</td>
		</tr>
		<tr>
			<td>%s</td><td>%s</td>
		</tr>
		<tr><td colspan="2" class="double_selector">%s</td></tr>
		<tr><td colspan="2" class="double_selector">%s</td></tr>
		<tr><td colspan="2" class="double_selector">%s</td></tr>
		<tr><td colspan="2" class="double_selector">%s</td></tr>
		<tr>
			<td class="paddedleft">%s</td>
			<td class="paddedright">%s</td>
		</tr>
	</table>
</form>
</div>
		''' % (
			form_name, form_name, login,
			_("<strong>UID</strong><br />(non modifiable)"), user['uid'],
			_("<strong>Identifiant</strong><br />(non modifiable)"), login,
			_("<strong>Profil</strong><br />(non modifiable)"), profile,
			_("<strong>Nom Complet</strong>"),
			w.input('gecos', user['gecos'], size = 30, maxlength = 64, accesskey = 'N'),
			_("""Le mot de passe doit comporter au moins %d caractères. Vous pouvez utiliser toutes
				les lettre de l'alphabet, les chiffres, les caractères spéciaux et les signes de 
				ponctuation sauf '?!'.""") % configuration.mAutoPasswdSize,
			_("Nouveau mot de passe"), _("(%d car. min.)") % configuration.mAutoPasswdSize,
			w.input('password', "", size = 30, maxlength = 64, accesskey = 'P', password = True),
			_("Confirmation du MDP."), w.input('password_confirm', "", size = 30, maxlength = 64, password = True),
			_("<strong>Shell</strong><br />(interpréteur de commandes Unix)"),
			w.select('loginShell',  configuration.users.shells, user['loginShell'], func = os.path.basename),
			dbl_lists[groups.FILTER_STANDARD], dbl_lists[groups.FILTER_PRIVILEGED],
			dbl_lists[groups.FILTER_RESPONSIBLE], dbl_lists[groups.FILTER_GUEST],
			w.button(_('<< Annuler'), "/users/list"),
			w.submit('record', _('Enregistrer >>'), onClick = "selectAllMultiValues('%s');" % form_name)
			)
	
	except exceptions.LicornException, e :
		data += w.error("Le compte %s n'existe pas (%s)&#160;!" % (login, "user = users.users[users.login_to_uid(login)]", e))

	return w.page(title, data)

# list user accounts.
def main(uri, sort = "login", order = "asc") :
		
	start = time.time()

	groups.reload()
	users.reload()
	# TODO: profiles.reload()

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

	for profile in p :
		prof[groups.name_to_gid(profile)] = p[profile]
		totals[p[profile]['name']] = 0
	totals[_('Standard account')] = 0

	title = _("User accounts")
	data  = '%s\n%s\n%s\n<div id="content">' % (w.backto(), __users_actions(), w.menu(uri)) 

	if order == "asc" : reverseorder = "desc"
	else :              reverseorder = "asc"

	data += '<table>\n		<tr>\n'

	for (sortcolumn, sortname) in ( ("gecos", _("Full name")), ("login", _("Identifier")), ("profile", _("Profile")), ("locked", _("Locked")) ) :
		if sortcolumn == sort :
			data += '''			<th><img src="/images/sort_%s.gif" alt="%s order image" />&#160;
				<a href="/users/list/%s/%s" title="%s">%s</a>
				</th>\n''' % (order, order, sortcolumn, reverseorder, _("Click to sort in reverse order."), sortname)
		else :
			data += '			<th><a href="/users/list/%s/asc" title="%s">%s</a></th>\n' % (sortcolumn, _("Click to sort on this column."), sortname)
	data += '		</tr>\n'

	def html_build_compact(index, accounts = accounts) :
		uid   = ordered[index]
		login = u[uid]['login']
		edit  = (_("""<em>Éditer les paramètres actuels du compte utilisateur&#160;:</em><br />
				UID: <strong>%d</strong><br />
				GID: %d (groupe primaire <strong>%s</strong>)<br /><br />
				Groupes:&#160;<strong>%s</strong><br /><br />
				Privilèges:&#160;<strong>%s</strong><br /><br />
				Responsabilités:&#160;<strong>%s</strong><br /><br />
				Invitations:&#160;<strong>%s</strong><br /><br />
				""") % (
				uid, u[uid]['gid'], g[u[uid]['gid']]['name'],
				", ".join(filter(lambda x: x in std_grps, u[uid]['groups'])),
				", ".join(filter(lambda x: x in pri_grps, u[uid]['groups'])),
				", ".join(filter(lambda x: x in rsp_grps, u[uid]['groups'])),
				", ".join(filter(lambda x: x in gst_grps, u[uid]['groups'])))).replace('<','&lt;').replace('>','&gt;')

		html_data = '''
	<tr class="userdata">
		<td class="paddedleft">
			<a href="/users/edit/%s" title="%s">%s</a></td>
		<td class="paddedright">
			<a href="/users/edit/%s" title="%s">
			%s&#160;<img src="/images/16x16/edit.png" alt="%s"/></a>
		</td>
		<td style="text-align:center;">%s</td>
			''' % (login, edit, u[uid]['gecos'],
			login, edit, login, _("Éditer les paramètres du compte."),
			accounts[uid]['profile_name'])

		if u[uid]['locked'] :
			html_data += '''
		<td class="user_action_center">
			<a href="/users/unlock/%s" title="%s">
			<img src="/images/16x16/locked.png" alt="%s"/></a>
		</td>
			''' % (login, _("Déverrouiller le mot de passe (redonne l\'accès terminaux légers et postes autonomes)."), _("Supprimer le compte."))
		else :
			html_data += '''
		<td class="user_action_center">
			<a href="/users/lock/%s" title="%s">
			<img src="/images/16x16/unlocked.png" alt="%s"/></a>
		</td>
			''' % (login, _("Verrouiller le mot de passe (bloque l\'accès aux terminaux légers et postes autonomes)."), _("Verrouiller le compte."))

		html_data += '''
		<td class="user_action">
			<a href="/users/skel/%s" title="%s">
			<img src="/images/16x16/reapply-skel.png" alt="%s"/></a>
		</td>
		<td class="user_action">
			<a href="/users/delete/%s" title="%s">
			<img src="/images/16x16/delete.png" alt="%s"/></a>
		</td>
	</tr>
			''' % (login, _("""Réappliquer les données du skelette d'origine dans le répertoire personnel de
				l'utilisateur. Ceci est utilisé lorsque l'utilisateur a perdu ou trop modifié le contenu de
				son bureau (icônes, menus, panneaux et barres d'outils) et permet de lui remettre le bureau
				d'«&#160;usine&#160;»."""), _("Réappliquer le skelette."), login,
				_("Supprimer définitivement le compte du système."), _("Supprimer le compte."))
		return html_data
		
	users.Select(users.FILTER_STANDARD)
	for uid in users.filtered_users :
		user  = u[uid]
		login = user['login'] 
			
		# we add the login to gecosValue and lockedValue to be sure to obtain 
		# unique values. This prevents problems with empty or non-unique GECOS
		# and when sorting on locked status (accounts would be overwritten and 
		# lost because sorting must be done on unique values).
		accounts[uid] = {
			'login'   : login,
			'gecos'   : "%s %s" % ( user['gecos'], login ),
			'locked'  : "%s %s" % ( str(user['locked']), login )
			}
		try :
			p = prof[user['gid']]['name']
		except KeyError :
			p = _("Standard account")

		accounts[uid]['profile']      = "%s %s" % ( p, login )
		accounts[uid]['profile_name'] = p
		totals[p] += 1

		# index on the column choosen for sorting, and keep trace of the uid
		# to find account data back after ordering.
		ordered[hlstr.validate_name(accounts[uid][sort])] = uid

	memberkeys = ordered.keys()
	memberkeys.sort()
	if order == "desc" : memberkeys.reverse()
	
	data += ''.join(map(html_build_compact, memberkeys))

	def print_totals(totals) :
		output = ""
		for total in totals :
			if totals[total] != 0 :
				output += '''
	<tr class="list_total">
		<td colspan="3" class="total_left">%s</td>
		<td colspan="3" class="total_right">%d</td>
	</tr>
		''' % (_("nombre de comptes pour le profil <strong>%s</strong>&#160;:") % total, totals[total])
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
</div>
%s
	''' % (print_totals(totals), _("<strong>Nombre total de comptes&#160;:</strong>"), 
		reduce(lambda x,y: x+y, totals.values()), w.total_time(start, time.time()))

	return w.page(title, data)
