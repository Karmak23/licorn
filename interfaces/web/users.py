# -*- coding: utf-8 -*-

import os, time

from licorn.foundations    import exceptions, hlstr, logging
from licorn.core           import configuration, groups, users, profiles
from licorn.interfaces.web import utils as w

groups_filters_lists_ids = ( 
	(groups.FILTER_STANDARD, ['Personnaliser les Groupes',     'Groupes disponibles',         'Groupes affectés'],           'standard_groups'),
	(groups.FILTER_PRIVILEGED, ['Affiner les privilèges',        'Privilèges disponibles',      'Privilèges octroyés'],        'privileged_groups'),
	(groups.FILTER_RESPONSIBLE, ['Attribuer des responsabilités', 'Responsabilités disponibles', 'Responsabilités attribuées'], 'responsible_groups'), 
	(groups.FILTER_GUEST, ['Proposer des invitations',      'Invitations disponibles',     'Invitations offertes'],       'guest_groups') )

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
		<td><a href="/users/new" title="Ajouter un nouvel utilisateur sur le système."><img src="/images/32x32/user-new.png" alt="Ajouter un compte." /><br />Ajouter un compte</a></td>
		<td><a href="/users/import" title="Importer une liste de nouveaux utilisateurs depuis un fichier CSV."><img src="/images/import-users.png" alt="Importer des comptes." /><br />Importer des comptes</a></td>
		<td><a href="/users/export" title="Exporter la liste des utilisateurs actuels vers un fichier CSV ou XML."><img src="/images/export-users.png" alt="Exporter les comptes." /><br />Exporter les comptes</a></td>
	</tr>
</table>
</div>
	'''

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

	title = "Suppression du compte %s" % login
	data  = '%s<h1>%s</h1><br />' % (w.backto(), title)

	
	if not sure :
		data += w.question("Êtes-vous sûr(e) de vouloir supprimer le compte <strong>%s</strong>&#160;?" % login,
			"""	<strong>Les données personnelles</strong> de l'utilisateur (son home dir) <strong>seront archivées</strong>
				dans le répertoire <code>%s</code> et accessibles aux membres du groupe
				<strong>administrateurs</strong> pour une récupération éventuelle.<br />
				Vous pouvez cependant décider de les effacer définitivement.""" % (configuration.home_archive_dir),
			yes_values   = [ "Supprimer >>", "/users/delete/%s/sure" % login, "S" ],
			no_values    = [ "<< Annuler",   "/users/list",                   "N" ],
			form_options = w.checkbox("no_archive", "True", 
				"Supprimer définitivement toutes les données avec le compte.",
				checked = False) )

		return w.page(title, data)

	else :
		users.reload()
		if users.is_system_login(login) :
			return w.page(title, w.error("Suppression de compte impossible", [ "tentative de suppression de compte non standard." ], "permissions insuffisantes pour mener à bien l'opération (non mais, tu croyais vraiment que j'allais le faire ?)."))

		# we are sure, do it !
		command = [ 'sudo', 'del', 'user', '--quiet', '--no-colors', '--login', login ]

		if no_archive :
			command.extend(['--no-archive'])
		
		return w.page(title, data + 
			w.run(command, uri, err_msg = "Impossible de supprimer le compte <strong>%s</strong>&#160;!" % login))
		
# locking and unlocking.
def unlock(uri, login) :
	"""unlock a user account password."""

	title   = "Déverrouillage du compte %s" % login
	data    = '%s<h1>%s</h1><br />' % (w.backto(), title)

	users.reload()
	if users.is_system_login(login) :
		return w.page(title, w.error("Déverrouillage de compte impossible", [ "tentative de déverrouillage de compte non standard." ], "permissions insuffisantes pour mener à bien l'opération."))

	command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login", login, "--unlock" ]
	return w.page(title, data + 
		w.run(command, uri, err_msg = "Impossible de déverrouiller le compte <strong>%s</strong>&#160;!" % login))
def lock(uri, login, sure = False, remove_remotessh = False, yes = None) :
	"""lock a user account password."""

	# forget about it, this is a scoria from the POST FORM to variable conversion.
	del yes
	
	groups.reload()
	users.reload()

	title = "Verrouillage du compte %s" % login
	data  = '%s<h1>%s</h1><br />' % (w.backto(), title)

	if not sure :
		description = '''Cela l'empêchera de se connecter sur les terminaux légers
			 %s/Linux et les postes autonomes Windows&reg; et Macintosh&reg;.''' % w.acr('GNU')
		
		# TODO : Vérifier que le groupe "remotessh" existe bien sur le système...
		if login in groups.all_members('remotessh') :
			description += """<br /><br />
				Mais <em>cela n'empêchera pas les connexions à distance par %s</em>
				si cet utilisateur se sert de clés %s %s/%s pour se connecter.
				Pour lui interdire complètement l'accès au système, 
				<strong>retirez-le aussi du groupe remotessh</strong>.""" % (w.acr('SSH'), w.acr('SSH'), w.acr('RSA'), w.acr('DSA'))
			form_options = w.checkbox("remove_remotessh", "True",
				"Supprimer l'utilisateur du groupe <code>remotessh</code> en même temps.",
				checked = True, accesskey = 'R')
		else :
			form_options = None
	
		data += w.question("Êtes-vous sûr(e) de vouloir verrouiller le mot de passe du compte <strong>%s</strong>&#160;?" % login,
			description,
			yes_values   = [ "Verrouiller >>", "/users/lock/%s/sure" % login, "V" ],
			no_values    = [ "<< Annuler",     "/users/list",                 "N" ],
			form_options = form_options)

		return w.page(title, data)

	else :
		if users.is_system_login(login) :
			return w.page(title, w.error("Verrouillage de compte impossible", [ "tentative de verrouillage de compte non standard." ], "permissions insuffisantes pour mener à bien l'opération (non mais, tu y croyais vraiment ?)."))

		# we are sure, do it !
		command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login", login, "--lock" ]

		if remove_remotessh :
			command.extend(['--del-groups', 'remotessh'])
		
		return w.page(title, data +
			w.run(command, uri, err_msg = "Impossible de verrouiller le compte <strong>%s</strong>&#160;!" % login))

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

	title = "Réapplication du profil pour le compte %s" % login
	data  = '%s<h1>%s</h1><br />' % (w.backto(), title)

	if users.is_system_login(login) :
		return w.page(title, w.error("Suppression de compte impossible", [ "tentative de suppression de compte non standard." ], "permissions insuffisantes pour mener à bien l'opération."))

	if not sure :
		description = '''Cela remettra son bureau à zéro, avec les icônes d'origine.<br /><br /><strong>Il est nécessaire que l'utilisateur soit déconnecté du système pour que l'opération réussisse.</strong>'''
		
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
			
		form_options = "Quel skelette voulez-vous lui appliquer&nbsp;? %s" % w.select("apply_skel", filter_skels(pri_group, configuration.users.skels), func = os.path.basename)
	
		data += w.question("Êtes-vous sûr(e) de vouloir ré-appliquer le profil au compte <strong>%s</strong>&#160;?" % login,
			description,
			yes_values   = [ "Appliquer >>", "/users/skel/%s/sure" % login, "V" ],
			no_values    = [ "<< Annuler",     "/users/list",                 "N" ],
			form_options = form_options)

		return w.page(title, data)

	else :
		# we are sure, do it !
		command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login", login, '--apply-skel', skel ]

		return w.page(title, data +
			w.run(command, uri, err_msg = "Impossible d'appliquer le skelette <strong>%s</strong> sur le compte <strong>%s</strong>&#160;!" % (os.path.basename(apply_skel), login)))

# user account creation
def new(uri) :
	"""Generate a form to create a new user on the system."""

	# TODO : profiles.reload()
	groups.reload()
	
	g = groups.groups
	p = profiles.profiles
	
	title = "Création d'un compte utilisateur"
	data  = '%s%s\n%s\n' % (w.backto(), __users_actions(), w.menu(uri))

	def profile_input() :

		#TODO : To be rewritten ?
		return """
	<tr>
		<td><strong>Ce compte sera un</strong></td><td>%s</td>
	</tr>
			""" % w.select('profile',  p.keys(), func = lambda x: p[x]['name'])
	def gecos_input() :
		return """
	<tr>
		<td><strong>Nom Complet</strong></td><td>%s</td>
	</tr>
			""" % w.input('gecos', "", size = 30, maxlength = 64, accesskey = 'N')
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
		<td><strong><a href="#" class="help" title="Le mot de passe doit comporter au moins %d caractères. Vous pouvez utiliser toutes les lettre de l'alphabet, les chiffres, les caractères spéciaux et les signes de ponctuation sauf '?!'.">Mot de passe</a></strong> (%d car. min.)</td><td>%s</td>
	</tr>
	<tr>
		<td><strong>Confirmation du MDP.</strong></td><td>%s</td>
	</tr>
	<tr>
		<td><strong><a href="#" class="help" title="L'identifiant doit être saisi en lettres minuscules, sans accents ni caractères spéciaux (vous pouvez cependant utiliser le point et le tiret).<br /><br />Si vous laissez le champ vide, l'identifiant sera automatiquement déterminé depuis le nom complet.">Identifiant</a></strong><br /></td><td>%s</td>
	</tr>
	<tr>
		<td><strong>Shell</strong><br />(interpréteur de commandes Unix)</td><td>%s</td>
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
		configuration.mAutoPasswdSize, configuration.mAutoPasswdSize, w.input('password', "", size = 30, maxlength = 64, accesskey = 'P', password = True),
		w.input('password_confirm', "", size = 30, maxlength = 64, password = True ),
		w.input('login', "", size = 30, maxlength = 64, accesskey = 'L'),
		shell_input(),	
		dbl_lists[groups.FILTER_STANDARD], dbl_lists[groups.FILTER_PRIVILEGED], dbl_lists[groups.FILTER_RESPONSIBLE], dbl_lists[groups.FILTER_GUEST],
		w.button('<< Annuler', "/users/list"),
		w.submit('create', 'Créer >>', onClick = "selectAllMultiValues('%s');" % form_name)
		)
	return w.page(title, data)
def create(uri, loginShell, password, password_confirm, profile = None, login = "", gecos = "", firstname = "", lastname = "",
	standard_groups_dest = [], privileged_groups_dest = [], responsible_groups_dest = [], guest_groups_dest = [],
		standard_groups_source = [], privileged_groups_source = [], responsible_groups_source = [], guest_groups_source = [], create = None ) :

	# forget about it, this is a scoria from the POST FORM to variable conversion.
	del create

	title      = "Création du compte %s" % login
	data       = '%s<h1>%s</h1><br />' % (w.backto(), title)
	
	if password != password_confirm :
		return w.page(title, data + w.error("Les mots de passe ne correspondent pas&#160;!%s" % rewind))

	if len(password) < configuration.mAutoPasswdSize :
		return w.page(title, data + w.error("Le mot de passe doit comporter au moins %d caractères&#160;!%s" % (configuration.mAutoPasswdSize, rewind)))

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
	
	retval = w.run(command, uri, err_msg = 'Erreur à la création du compte <strong>%s</strong>&#160;!' % login)

	# TODO : Change test since message received : Added user <login>
	if retval != "" :
		return w.page(title, data + retval)
	
	command    = [ "sudo", "mod", "user", '--quiet', "--no-colors", "--login", login, "--shell", loginShell ]
	add_groups = ','.join(__merge_multi_select(standard_groups_dest, privileged_groups_dest, responsible_groups_dest, guest_groups_dest))

	if add_groups != "" :
		command.extend([ '--add-groups', add_groups ])

	return w.page(title, 
		data + w.run(command, uri,
		err_msg = 'Impossible d\'inscrire l\'utilisateur <strong>%s</strong> dans un ou plusieurs groupes demandés&#160;!' % login))

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

	title      = "Modification du compte %s" % login
	data       = '%s<h1>%s</h1><br />' % (w.backto(), title)
	command    = [ "sudo", "mod", "user", '--quiet', "--no-colors", "--login", login, "--shell", loginShell ]

	users.reload()
	if users.is_system_login(login) :
		return w.page(title, w.error("Enregistrement de compte impossible", [ "tentative de modification de compte non standard." ], "permissions insuffisantes pour mener à bien l'opération (dis-donc, tu n'essaierais pas de t'amuser par hasard ?)."))

	if password != "" :
		if password != password_confirm :
			return w.page(title, data + w.error("Les mots de passe ne correspondent pas&#160;!%s" % rewind))
		if len(password) < configuration.mAutoPasswdSize :
			return w.page(title, data + w.error("Le mot de passe --%s-- doit comporter au moins %d caractères&#160;!%s" % (password, configuration.mAutoPasswdSize, rewind)))

		command.extend([ '--password', password ])

	command.extend( [ "--gecos", gecos ] )

	add_groups = ','.join(__merge_multi_select(standard_groups_dest,   privileged_groups_dest,   responsible_groups_dest,   guest_groups_dest))
	del_groups = ','.join(__merge_multi_select(standard_groups_source, privileged_groups_source, responsible_groups_source, guest_groups_source))

	if add_groups != "" :
		command.extend([ '--add-groups', add_groups ])
		
	if del_groups != "" :
		command.extend(['--del-groups', del_groups ])

	return w.page(title, data + w.run(command, uri, err_msg = 'Impossible de modifier un ou plusieurs paramètre(s) du compte <strong>%s</strong>&#160;!' % login))

# edit user accout parameters.
def edit(uri, login) :
	"""Edit an user account, based on login."""

	groups.reload()
	users.reload()
	# TODO: profiles.reload()

	title = "Édition du compte %s" % login 
	data  = '%s\n%s\n%s<br />\n' % (w.backto(), __users_actions(), w.menu(uri))

	if users.is_system_login(login) :
		return w.page(title, w.error("Édition de compte impossible", [ "tentative d'édition de compte non standard." ], "permissions insuffisantes pour mener à bien l'opération."))

	try :
		user = users.users[users.login_to_uid(login)]

		try :
			profile = profiles.profiles[groups.groups[user['gid']]['name']]['name']
		except KeyError :
			profile = "Compte Standard"

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
			<td><strong>UID</strong><br />(non modifiable)</td><td class="not_modifiable">%d</td>
		</tr>
		<tr>
			<td><strong>Identifiant</strong><br />(non modifiable)</td><td class="not_modifiable">%s</td>
		</tr>
		<tr>
			<td><strong>Profil</strong><br />(non modifiable)</td><td class="not_modifiable">%s</td>
		</tr>
		<tr>
			<td><strong>Nom Complet</strong></td><td>%s</td>
		</tr>
		<tr>
			<td><strong><a href="#" class="help" title="Le mot de passe doit comporter au moins %d caractères. Vous pouvez utiliser toutes les lettre de l'alphabet, les chiffres, les caractères spéciaux et les signes de ponctuation sauf '?!'.">Nouveau mot de passe</a></strong> (%d car. min.)</td><td>%s</td>
		</tr>
		<tr>
			<td><strong>Confirmation du MDP.</strong></td><td>%s</td>
		</tr>
		<tr>
			<td><strong>Shell</strong><br />(interpréteur de commandes Unix)</td><td>%s</td>
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
		''' % ( form_name, form_name, login, user['uid'], login,
			profile,
			w.input('gecos', user['gecos'], size = 30, maxlength = 64, accesskey = 'N'),
			configuration.mAutoPasswdSize, configuration.mAutoPasswdSize, w.input('password', "", size = 30, maxlength = 64, accesskey = 'P', password = True),
			w.input('password_confirm', "", size = 30, maxlength = 64, password = True ),
			w.select('loginShell',  configuration.users.shells, user['loginShell'], func = os.path.basename),
			dbl_lists[groups.FILTER_STANDARD], dbl_lists[groups.FILTER_PRIVILEGED],
			dbl_lists[groups.FILTER_RESPONSIBLE], dbl_lists[groups.FILTER_GUEST],
			w.button('<< Annuler', "/users/list"),
			w.submit('record', 'Enregistrer >>', onClick = "selectAllMultiValues('%s');" % form_name)
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
	totals['compte standard'] = 0

	title = _("User accounts")
	data  = '%s\n%s\n%s\n<div id="content">' % (w.backto(), __users_actions(), w.menu(uri)) 

	if order == "asc" : reverseorder = "desc"
	else :              reverseorder = "asc"

	data += '<table>\n		<tr>\n'

	for (sortcolumn, sortname) in ( ("gecos", "Nom Complet"), ("login", "Identifiant"), ("profile", "Profil"), ("locked", "Verr.") ) :
		if sortcolumn == sort :
			data += '''			<th><img src="/images/sort_%s.gif" alt="ordre %s" />&#160;
				<a href="/users/list/%s/%s" title="cliquez pour trier dans l\'autre sens.">%s</a>
				</th>\n''' % (order, order, sortcolumn, reverseorder, sortname)
		else :
			data += '			<th><a href="/users/list/%s/asc" title="cliquez pour trier sur cette colonne.">%s</a></th>\n' % (sortcolumn, sortname)
	data += '		</tr>\n'

	def html_build_compact(index, accounts = accounts) :
		uid   = ordered[index]
		login = u[uid]['login']
		edit  = ('''<em>Éditer les paramètres actuels du compte utilisateur&#160;:</em><br />
				UID: <strong>%d</strong><br />
				GID: %d (groupe primaire <strong>%s</strong>)<br /><br />
				Groupes:&#160;<strong>%s</strong><br /><br />
				Privilèges:&#160;<strong>%s</strong><br /><br />
				Responsabilités:&#160;<strong>%s</strong><br /><br />
				Invitations:&#160;<strong>%s</strong><br /><br />
				''' % (uid, u[uid]['gid'], g[u[uid]['gid']]['name'],
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
			%s&#160;<img src="/images/16x16/edit.png" alt="éditer les paramètres du compte."/></a>
		</td>
		<td style="text-align:center;">%s</td>
			''' % (login, edit, u[uid]['gecos'],
			login, edit, login,
			accounts[uid]['profile_name'])

		if u[uid]['locked'] :
			html_data += '''
		<td class="user_action_center">
			<a href="/users/unlock/%s" title="Déverrouiller le mot de passe (redonne l\'accès terminaux légers et postes autonomes).">
			<img src="/images/16x16/locked.png" alt="Supprimer le compte."/></a>
		</td>
			''' % login
		else :
			html_data += '''
		<td class="user_action_center">
			<a href="/users/lock/%s" title="Verrouiller le mot de passe (bloque l\'accès aux terminaux légers et postes autonomes).">
			<img src="/images/16x16/unlocked.png" alt="Verrouiller le compte."/></a>
		</td>
			''' % login

		html_data += '''
		<td class="user_action">
			<a href="/users/skel/%s" title="Réappliquer les données du skelette d'origine dans le répertoire personnel de l'utilisateur. Ceci est utilisé lorsque l'utilisateur a perdu ou trop modifié le contenu de son bureau (icônes, menus, panneaux et barres d'outils) et permet de lui remettre le bureau d'«&#160;usine&#160;».">
			<img src="/images/16x16/reapply-skel.png" alt="Réappliquer le skelette."/></a>
		</td>
		<td class="user_action">
			<a href="/users/delete/%s" title="Supprimer définitivement le compte du système.">
			<img src="/images/16x16/delete.png" alt="Supprimer le compte."/></a>
		</td>
	</tr>
			''' % (login, login)
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
			p = "compte standard"

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
		<td colspan="3" class="total_left">nombre de comptes pour le profil <strong>%s</strong>&#160;:</td>
		<td colspan="3" class="total_right">%d</td>
	</tr>
		''' % (total, totals[total])
		return output

	data += '''
	<tr>
		<td colspan="6">&#160;</td></tr>
	%s
	<tr class="list_total">
		<td colspan="3" class="total_left"><strong>Nombre total de comptes&#160;:</strong></td>
		<td colspan="3" class="total_right">%d</td>
	</tr>
</table>
</div>
%s
	''' % (print_totals(totals), reduce(lambda x,y: x+y, totals.values()), w.total_time(start, time.time()))

	return w.page(title, data)
