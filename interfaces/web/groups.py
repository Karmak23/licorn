# -*- coding: utf-8 -*-

import os, time

from licorn.foundations    import exceptions, hlstr
from licorn.core           import configuration, groups, users, profiles
from licorn.interfaces.web import utils as w

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
def __groups_actions() :
	return '''
<div id="actions">
<table>
	<tr>
		<td><a href="/groups/new" title="Ajouter un nouveau groupe système."><img src="/images/32x32/group-new.png" alt="Ajouter un groupe." /><br />Ajouter un groupe</a></td>
	</tr>
</table>
</div>
	'''

# locking and unlocking.
def unlock(uri, name, sure = False) :
	"""make a shared group dir permissive."""

	title = "Activation de la permissivité du groupe %s" % name
	data  = '%s\n%s\n%s' % (w.backto(), __groups_actions(), w.menu(uri))

	if not sure :
		description = '''Cela déverrouillera les accès aux fichiers et dossiers, 
			et permettra à n'importe quel membre du groupe de modifier/supprimer
			n'importe quel document, y compris si ce n'est pas lui le propriétaire/créateur.
			Cette option peut donc être dangereuse, mais si les membres du groupe sont habitués
			à travailler ensemble, il n'y a pas de problème.
			En général on utilise cette fonctionnalité sur des petits groupes de travail.<br />
			Attention&#160;: <strong>L'opération peut être longue car le système va modifier
			les permissions de toutes les données actuelles</strong> (la durée est donc en fonction du volume de données, de l'ordre de 1 seconde pour 100Mio).
			'''
		
		data += w.question("Êtes-vous sûr(e) de vouloir activer la permissivité du groupe <strong>%s</strong>&#160;?" % name,
			description,
			yes_values   = [ "Activer >>", "/groups/unlock/%s/sure" % name, "V" ],
			no_values    = [ "<< Annuler", "/groups/list",                  "N" ])
		
		return w.page(title, data)

	else :
		# we are sure, do it !
		command = [ "sudo", "mod", "group", "--quiet", "--no-colors", "--name", name, "--set-permissive" ]

		return w.page(title, data +
			w.run(command, uri, successfull_redirect = "/groups/list", err_msg = "Impossible d'activer la permissivité du groupe <strong>%s</strong>&#160;!" % name))
def lock(uri, name, sure = False) :
	"""make a group not permissive."""

	title = "Désactivation de la permissivité du groupe %s" % name
	data  = '%s\n%s\n%s' % (w.backto(), __groups_actions(), w.menu(uri))

	if not sure :
		description = '''Cela verrouillera les accès aux fichiers et dossiers.
			Seul le propriétaire/créateur d'un document pourra le modifier,
			les autres membres du groupe pourront seulement le lire 
			(sauf si l'utilisateur assigne manuellement d'autres permissions).<br />
			Attention&#160;: <strong>L'opération peut être longue car le système va modifier
			les permissions de toutes les données actuelles</strong> (la durée est donc en fonction du volume de données, de l'ordre de 1 seconde pour 100Mio).
			'''
		
		data += w.question("Êtes-vous sûr(e) de vouloir désactiver la permissivité du groupe <strong>%s</strong>&#160;?" % name,
			description,
			yes_values   = [ "Désactiver >>", "/groups/lock/%s/sure" % name, "V" ],
			no_values    = [ "<< Annuler",    "/groups/list",                "N" ])
		
		return w.page(title, data)

	else :
		# we are sure, do it !
		command = [ "sudo", "mod", "group", "--quiet", "--no-colors", "--name", name, "--set-not-permissive" ]

		return w.page(title, data +
			w.run(command, uri, successfull_redirect = "/groups/list", err_msg = "Impossible d'enlever la permissivité du groupe <strong>%s</strong>&#160;!" % name))

# delete a group.
def delete(uri, name, sure = False, no_archive = False, yes = None) :
	"""remove group."""

	title = "Suppression du groupe %s" % name
	data  = '%s\n%s\n%s' % (w.backto(), __groups_actions(), w.menu(uri))

	groups.reload()
	g = groups.groups

	del yes
	
	if groups.is_system_group(name) :
		return w.page(title, w.error("Suppression de groupe impossible", [ "tentative de suppression de groupe non standard." ], "permissions insuffisantes pour mener à bien l'opération."))

	if not sure :
		data += w.question("Êtes-vous sûr(e) de vouloir supprimer le groupe <strong>%s</strong>&#160;?" % name,
			"""	<strong>Les données partagées</strong> du groupe <strong>seront archivées</strong>
				dans le répertoire <code>%s</code> et accessibles aux membres du groupe
				<strong>administrateurs</strong> pour une récupération éventuelle. Vous pouvez cependant décider de les effacer définitivement.
				""" % (configuration.home_archive_dir),
			yes_values   = [ "Supprimer >>", "/groups/delete/%s/sure" % name, "S" ],
			no_values    = [ "<< Annuler",   "/groups/list",                  "N" ],
			form_options = w.checkbox("no_archive", "True", 
				"Supprimer définitivement toutes les données partagées.",
				checked = False) )

		return w.page(title, data)

	else :
		# we are sure, do it !
		command = [ 'sudo', 'del', 'group', '--quiet', '--no-colors', '--name', name ]

		if no_archive :
			command.extend(['--no-archive'])
		
		return w.page(title, data + 
			w.run(command, uri, successfull_redirect = "/groups/list", err_msg = "Impossible de supprimer le groupe <strong>%s</strong>&#160;!" % name))
		
# skel reapplyin'
def skel(req, name, sure = False, apply_skel = configuration.users.default_skel) :
	"""reapply a user's skel with confirmation."""

	users.reload()
	profiles.reload()
	groups.reload()

	title = "Réapplication du profil pour le groupe %s" % name
	data  = '%s%s' % (w.backto(), __groups_actions(title))

	if not sure :
		allusers  = u.UsersList(configuration)
		allgroups = g.GroupsList(configuration, allusers)

		description = '''Cela remettra son bureau à zéro, avec les icônes d'origine.<br /><br /><strong>Il est nécessaire que l'utilisateur soit déconnecté du système pour que l'opération réussisse.</strong>'''
		
		pri_group = allgroups.groups[allusers.users[users.UsersList.login_to_uid(login)]['gid']]['name']
		
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
			no_values    = [ "<< Annuler",     "/groups/list",                 "N" ],
			form_options = form_options)

		return w.page(title, data)

	else :
		# we are sure, do it !
		command = [ "sudo", "mod", "user", "--quiet", "--no-colors", "--login", login, '--apply-skel', skel ]

		return w.page(title, data +
			w.run(command, req,  successfull_redirect = "/groups/list", err_msg = "Impossible d'appliquer le skelette <strong>%s</strong> sur le compte <strong>%s</strong>&#160;!" % (os.path.basename(apply_skel), login)))

# user account creation
def new(uri) :
	"""Generate a form to create a new group on the system."""

	title = "Création d'un nouveau groupe"
	data  = '%s%s\n%s\n' % (w.backto(), __groups_actions(), w.menu(uri))

	form_name = "group_create"

	data += '''<div id="create_group">
<form name="%s" id="%s" action="/groups/create" method="post">
<table id="group_new">
	<tr>
		<td><strong>Nom du groupe</strong></td><td>%s</td>
	</tr>
	<tr>
		<td><strong>Description du groupe</strong><br />(optionnel)</td><td>%s</td>
	</tr>
	<tr>
		<td><strong>Squelette des membres du groupe</strong></td><td>%s</td>
	</tr>
	<tr>
		<td><strong>Répertoire partagé permissif&#160;?</strong></td><td>%s</td>
	</tr>
	<tr>
		<td></td>	
	</tr>
	<tr>
		<td class="paddedleft">%s</td>
		<td class="paddedright">%s</td>
	</tr>
</table>
</form>
</div>
	''' % ( form_name, form_name,
		w.input('name',        "", size = 30, maxlength = 64, accesskey = 'N'),
		w.input('description', "", size = 30, maxlength = 256, accesskey = 'D'),
		w.select('skel',  configuration.users.skels, current = configuration.users.default_skel, func = os.path.basename),
		w.checkbox('permissive', "True", "Oui"),
		w.button('<< Annuler', "/groups/list"),
		w.submit('create', 'Créer >>', onClick = "selectAllMultiValues('%s');" % form_name)
		)
	return w.page(title, data)
def create(uri, name, description = None, skel = "", permissive = False, create = None) :

	title      = "Création du groupe %s" % name
	data       = '%s<h1>%s</h1><br />' % (w.backto(), title)
	
	del create
	
	command = [ 'sudo', 'add', 'group', '--quiet', '--no-colors', '--name', name, '--skel', skel ]

	if description :
		command.extend([ '--description', description ])
	
	if permissive :
		command.append('--permissive')
	
	return w.page(title, data + w.run(command, uri,  successfull_redirect = "/groups/list", err_msg = '''Impossible de créer le groupe <strong>%s</strong>&#160;!''' % name))
def view(uri, name) :
	"""Prepare a group view to be printed."""

	users.reload()
	groups.reload()

	title = "Visualisation du groupe %s" % name 
	data  = '%s\n%s\n%s<br />\n' % (w.backto(), __groups_actions(), w.menu(uri))
	
	u = users.users
	g = groups.groups

	# est-ce qu'on empêche le visu des groupes système ou pas ?
	# pour l'instant non, ça mange pas de pain de les avoir, il faut
	# quand même forger l'URL...

	try :
		group   = g[groups.name_to_gid(name)]
		members = groups.all_members(name)
		members.sort()

		members_html = '''
		<h2>Membres</h2>
		<table class="group_members">
		<tr>
			<td><strong>Nom Complet</strong></td>
			<th><strong>Identifiant</strong></th>
			<th><strong>UID</strong></th>
		</tr>
		'''
		def user_line(login) :
			uid = users.login_to_uid(login)
			return '''<tr><td>%s</td><td>%s</td><td>%s</td></tr>''' % (u[uid]['gecos'], login, uid)

		members_html += "\n".join(map(user_line, members)) + '</table>'

		if not groups.is_system_group(name) :
			resps  = groups.all_members(configuration.groups.resp_prefix + name)
			resps.sort()
			guests = groups.all_members(configuration.groups.guest_prefix + name)
			guests.sort()

			if resps != [] :
				resps_html = '''
		<h2>Responsables</h2><div style="text-align:center;">(classés par identifiant)</div>
		<table class="group_members">
		<tr>
			<th><strong>Nom Complet</strong></th>
			<th><strong>Identifiant</strong></th>
			<th><strong>UID</strong></th>
		</tr>
			'''
			if guests != [] :
				guests_html = '''
		<h2>Invités</h2><div style="text-align:center;">(classés par identifiant)</div>
		<table class="group_members">
		<tr>
			<th><strong>Nom Complet</strong></th>
			<th><strong>Identifiant</strong></th>
			<th><strong>UID</strong></th>
		</tr>
			'''

			if resps != [] : 
				resps_html  += "\n".join(map(user_line, resps)) + '</table>'
			else :
				resps_html = "<h2>Pas de responsables pour ce groupe</h2>"

			if guests != [] : 
				guests_html += "\n".join(map(user_line, guests)) + '</table>'
			else :
				guests_html = "<h2>Pas d'invités pour ce groupe</h2>"

		else :
			resps_html = guests_html = ''

		form_name = "group_print_form"
		data += '''
		<div id="edit_user">
		<form name="%s" id="%s" action="/groups/view/%s" method="post">
		<table id="user_account">
			<tr><td><strong>GID</strong><br />(non modifiable)</td><td class="not_modifiable">%d</td></tr>
			<tr><td><strong>Nom</strong><br />(non modifiable)</td><td class="not_modifiable">%s</td></tr>
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
			''' % ( form_name, form_name, name,
				group['gid'],
				name,
				members_html, resps_html, guests_html,
				w.button('<< Revenir', "/groups/list"),
				w.submit('print', 'Imprimer >>', onClick = "javascript:window.print(); return false;")
				)

	except exceptions.LicornException, e :
		data += w.error("Le groupe %s n'existe pas (%s)&#160;!" % (name, "group = g[groups.name_to_gid(name)]", e))

	return w.page(title, data)

# edit group parameters.
def edit(uri, name) :
	"""Edit a group."""

	users.reload()
	groups.reload()
	
	u = users.users
	g = groups.groups

	title = "Édition du groupe %s" %  name
	data  = '%s\n%s\n%s<br />\n' % (w.backto(), __groups_actions(), w.menu(uri))

	try :
		group     = g[groups.name_to_gid(name)]
		sys       = groups.is_system_group(name)
		dbl_lists = {}

		if sys :
			groups_filters_lists_ids   = ( 
				(name, ( 'Gérer les membres', 'Utilisateurs non affectés', 'Membres actuels' ), 'members' ),
				(configuration.groups.resp_prefix + name, None, '&#160;' ),
				(configuration.groups.guest_prefix + name, None, '&#160;' )
				)
		else :
			groups_filters_lists_ids = ( 
				(name,            ['Gérer les membres',      'Utilisateurs non affectés', 'Membres actuels'],      'members'),
				(configuration.groups.resp_prefix + name,  ['Gérer les responsables', 'Utilisateurs non affectés', 'Responsables actuels'], 'resps'), 
				(configuration.groups.guest_prefix + name, ['Gérer les invités',      'Utilisateurs non affectés', 'Invités actuels'],      'guests') )

		for (gname, titles, id) in groups_filters_lists_ids :
			if titles is None :
				dbl_lists[gname] = id
			else :
				users.Select(users.FILTER_STANDARD)
				dest   = g[groups.name_to_gid(gname)]['members'][:]
				source = [ u[uid]['login'] for uid in users.filtered_users ]
				for current in g[groups.name_to_gid(gname)]['members'] :
					try : source.remove(current)
					except ValueError : dest.remove(current)
				dest.sort()
				source.sort()
				dbl_lists[gname] = w.doubleListBox(titles, id, source, dest)

		def descr(desc, system) :
			if system :
				return desc
			else :
				return w.input('description', desc, size = 30, maxlength = 256, accesskey = 'D')


		def skel(cur_skel, system) :
			if system :
				return ''
			else :
				return '''
				<tr>
					<td><strong>Squelette</strong></td><td>%s</td>
				</tr>
				''' % w.select('skel',  configuration.users.skels, cur_skel, func = os.path.basename)

		def permissive(perm, sys) :

			if sys :
				return ''
			else :
				return '''
				<tr>
					<td><strong>Répertoire permissif&#160;?</strong></td><td>%s</td>
				</tr>
				''' % w.checkbox('permissive', "True", "Oui", checked = perm )

		form_name = "user_edit_form"

		data += '''<div id="edit_user">
<form name="%s" id="%s" action="/groups/record/%s" method="post">
	<table id="user_account">
		<tr>
			<td><strong>GID</strong><br />(non modifiable)</td><td class="not_modifiable">%d</td>
		</tr>
		<tr>
			<td><strong>Nom de groupe</strong><br />(non modifiable)</td><td class="not_modifiable">%s</td>
		</tr>
		<tr>
			<td><strong>Description du groupe</strong></td><td>%s</td>
		</tr>
		%s
		%s
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
		''' % ( form_name, form_name, name,
			group['gid'],
			group['name'],
			descr(group['description'], sys),
			skel(group['skel'], sys),	
			permissive(group['permissive'], sys),	
			dbl_lists[name], dbl_lists[configuration.groups.resp_prefix+name], dbl_lists[configuration.groups.guest_prefix+name],
			w.button('<< Annuler', "/groups/list"),
			w.submit('record', 'Enregistrer >>', onClick = "selectAllMultiValues('%s');" % form_name)
			)
	
	except exceptions.LicornException, e :
		data += w.error("Le groupe %s n'existe pas (%s, %s)&#160;!" % (name, "group = allgroups.groups[groups.name_to_gid(name)]", e))

	return w.page(title, data)
def record(uri, name, skel = None, permissive = False, description = None,
	members_source    = [], members_dest = [],
	resps_source      = [], resps_dest   = [],
	guests_source     = [], guests_dest  = [],
	record = None) :
	"""Record user account changes."""

	# forget about it, this is a scoria from the POST FORM to variable conversion.
	del record

	title      = "Modification du groupe %s" % name
	data       = '%s<h1>%s</h1><br />' % (w.backto(), title)
	command    = [ 'sudo', 'mod', 'group', '--quiet', '--no-colors', '--name', name ]

	if skel :
		command.extend([ "--skel", skel ])

	add_members = ','.join(__merge_multi_select(members_dest))
	del_members = ','.join(__merge_multi_select(members_source))

	add_resps = ','.join(__merge_multi_select(resps_dest))
	del_resps = ','.join(__merge_multi_select(resps_source))

	add_guests = ','.join(__merge_multi_select(guests_dest))
	del_guests = ','.join(__merge_multi_select(guests_source))

	for (var, cmd) in ( (add_members, "--add-users"), (del_members, "--del-users"), (add_resps, "--add-resps"), (del_resps, '--del-resps'), (add_guests, "--add-guests"), (del_guests, '--del-guests') ) :
		if var != "" :
			command.extend([ cmd, var ])

	return w.page(title, 
		data + w.run(command, uri, successfull_redirect = "/groups/list",
		err_msg = 'Impossible de modifier un ou plusieurs paramètre(s) du groupe <strong>%s</strong>&#160;!' % name))

# list user accounts.
def main(uri, sort = "name", order = "asc") :
		
	start = time.time()

	users.reload()
	groups.reload()
	#reload(p)

	g = groups.groups
	
	users.Select(users.FILTER_STANDARD)

	tgroups  = {}
	totals   = {}

	title = "%s" % configuration.groups.names['plural']
	data  = '%s\n%s\n%s\n<div id="groupslist">' % (w.backto(), __groups_actions(), w.menu(uri)) 

	if order == "asc" : reverseorder = "desc"
	else :              reverseorder = "asc"

	data += '<table>\n		<tr>\n'

	sortcols = ( ('', '', False), ("name", "Nom", True), ("skel", "Squelette", True), ("permissive", "Perm.", True), ('members', "Membres", False), ("resps", "Responsables", False), ("guests", "Invités", False) )
	
	for (column, name, can_sort) in sortcols :
		if can_sort :
			if column == sort :
					data += '''
		<th><img src="/images/sort_%s.gif" alt="ordre %s" />&#160;
			<a href="/groups/list/%s/%s" title="cliquez pour trier dans l\'autre sens.">%s</a>
		</th>\n''' % (order, order, column, reverseorder, name)
			else :
				data += '		<th><a href="/groups/list/%s/asc" title="cliquez pour trier sur cette colonne.">%s</a></th>\n' % (column, name)
		else :
			data += '		<th>%s</th>\n' % name
			

	data += '		</tr>\n'

	for (filter, filter_name) in ( (groups.FILTER_STANDARD, configuration.groups.names['plural']), (groups.FILTER_PRIVILEGED, "Privilèges") ) :

		tgroups  = {}
		ordered  = {}
		totals[filter_name] = 0
		groups.Select(filter)

		for gid in groups.filtered_groups :
			group = groups.groups[gid]
			name  = group['name'] 

			tgroups[gid] = {
				'name'       : name,
				'skel'       : group['skel'] + name,
				'permissive' : group['permissive']
				}
			totals[filter_name] += 1

			# index on the column choosen for sorting, and keep trace of the uid
			# to find account data back after ordering.

			ordered[hlstr.validate_name(tgroups[gid][sort])] = gid

			tgroups[gid]['members'] = []
			for member in groups.groups[gid]['members'] :
				if not users.is_system_login(member) :
					tgroups[gid]['members'].append(users.users[users.login_to_uid(member)]) 

			if not groups.is_system_gid(gid) :
				for prefix in (configuration.groups.resp_prefix, configuration.groups.guest_prefix) :
					tgroups[gid][prefix + 'members'] = []
					for member in groups.groups[groups.name_to_gid(prefix + name)]['members'] :
						if not users.is_system_login(member) :
							tgroups[gid][prefix + 'members'].append(users.users[users.login_to_uid(member)])

		gkeys = ordered.keys()
		gkeys.sort()
		if order == "desc" : gkeys.reverse()

		def html_build_group(index, tgroups = tgroups ) :
			gid   = ordered[index]
			name  = g[gid]['name']
			html_data = '''
		<tr class="userdata">
			<td class="nopadding"><a href="/groups/view/%s" title="Visualiser le groupe, ses paramètres, ses membres, responsables et invités, en vue de les imprimer."><img src="/images/16x16/preview.png" alt="prévisualiser le groupe et ses données." /></a></td>
			<td class="group_name">
				<a href="/groups/edit/%s" title="%s"><img src="/images/16x16/edit.png" alt="éditer les paramètres du groupe."/>&#160;%s</a>
			</td>
			<td class="paddedright">
				<a href="/groups/edit/%s">%s</a>
			</td>
				''' % (name, name, g[gid]['description'], name, name, g[gid]['skel'])
	
			if groups.is_system_gid(gid) :
				html_data += '<td>&#160;</td>'
			else :
				if g[gid]['permissive'] :
					html_data += '''
				<td class="user_action_center">
					<a href="/groups/lock/%s" title="Le répertoire de groupe est actuellement <strong>permissif</strong>. Cliquez pour désactiver la permissivité.">
					<img src="/images/16x16/unlocked.png" alt="Le groupe est actuellement permissif."/></a>
				</td>
					''' % name
				else :
					html_data += '''
				<td class="user_action_center">
					<a href="/groups/unlock/%s" title="Le répertoire de groupe est actuellement <strong>NON</strong> permissif. Cliquez pour activer la permissivité.">
					<img src="/images/16x16/locked.png" alt="Le groupe N'EST PAS permissif actuellement."/></a>
				</td>
					''' % name

			for (keyname, text) in (('members', 'Membres actuels'), ('rsp-members', 'Responsables actuels'), ('gst-members', 'Invités actuels') ) :
				if tgroups[gid].has_key(keyname) :
					accounts = {}
					uordered = {}
					for member in tgroups[gid][keyname] :
						uid = member['uid']
						accounts[uid] = { 'login' : member['login'], 'gecos' : member['gecos'], 'gecos_sort' : member['gecos'] + member['login'] }
						uordered[hlstr.validate_name(accounts[uid]['gecos_sort'], aggressive = True)] = uid
					memberkeys = uordered.keys()
					memberkeys.sort()
					mbdata = "<table><tr><th>Nom Complet</th><th>Identifiant</th><th>UID</th></tr>\n"
					for member in memberkeys :
						uid = uordered[member]
						mbdata += '''<tr><td>%s</td><td>%s</td><td>%d</td></tr>\n''' % (accounts[uid]['gecos'], accounts[uid]['login'], uid)
					mbdata += '</table>'
					nb = len(tgroups[gid][keyname])
					if nb == 0 :
						html_data += '''<td class="paddedright faded">aucun</td>\n'''
					else :
						html_data += '''<td class="paddedright"><a class="nounder" title="<h4>%s</h4><br />%s"><strong>%d</strong>&#160;<img src="/images/16x16/details-light.png" alt="voir les %s du groupe %s." /></a></td>\n''' % (text, mbdata, nb, text, name)	
				else :
					html_data += '''<td>&#160;</td>\n'''
	
			if groups.is_system_gid(gid) :
				html_data += '<td colspan="1">&#160;</td></tr>\n'
			else :
				html_data += '''
					<!--
					<td class="user_action">
						<a href="/users/skel/%s" title="Réappliquer les données du skelette d'origine dans le répertoire personnel de l'utilisateur. Ceci est utilisé lorsque l'utilisateur a perdu ou trop modifié le contenu de son bureau (icônes, menus, panneaux et barres d'outils) et permet de lui remettre le bureau d'«&#160;usine&#160;».">
						<img src="/images/16x16/reapply-skel.png" alt="Réappliquer le skelette à tous les membres."/></a>
					</td>
					-->
					<td class="user_action">
						<a href="/groups/delete/%s" title="Supprimer définitivement le groupe du système.">
						<img src="/images/16x16/delete.png" alt="Supprimer le groupe."/></a>
					</td>
				</tr>
						''' % (name, name)
			return html_data
	
		data += '<tr><td class="group_class" colspan="8">%s</td></tr>\n%s' % (filter_name, ''.join(map(html_build_group, gkeys)))

	def print_totals(totals) :
		output = ""
		for total in totals :
			if totals[total] != 0 :
				output += '''
	<tr class="list_total">
		<td colspan="6" class="total_left">nombre de <strong>%s</strong>&#160;:</td>
		<td colspan="6" class="total_right">%d</td>
	</tr>
		''' % (total, totals[total])
		return output

	data += '''
	<tr>
		<td colspan="6">&#160;</td></tr>
	%s
	<tr class="list_total">
		<td colspan="6" class="total_left"><strong>Nombre total de groupes&#160;:</strong></td>
		<td colspan="6" class="total_right">%d</td>
	</tr>
</table>
</div>
%s
	''' % (print_totals(totals), reduce(lambda x,y: x+y, totals.values()), w.total_time(start, time.time()))

	return w.page(title, data)
