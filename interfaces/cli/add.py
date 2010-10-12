#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://ilcorn.org/documentation/cli

add - add something on the system, a user account, a group…

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys

from licorn.foundations           import logging, exceptions, styles
from licorn.foundations           import hlstr, fsapi
from licorn.foundations.constants import filters
from licorn.foundations.ltrace    import ltrace

from licorn.interfaces.cli import cli_main, cli_select

_app = {
	"name"        : "licorn-add",
	"description" : "Licorn Add Entries",
	"author"      : "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def import_users(opts, args, configuration, users, groups, profiles, **kwargs):
	""" Massively import user accounts from a CSV file."""

	ltrace('add', '> import_user(%s,%s)' % (opts, args))

	def clean_csv_field(field):
		return field.replace("'","").replace('"','')

	if opts.filename is None:
		raise exceptions.BadArgumentError, "You must specify a file name."
	else:
		import_filename = opts.filename

	if opts.profile is None:
		raise exceptions.BadArgumentError, "You must specify a profile."
	else:
		profile = opts.profile

	if opts.firstname_col is None:
		raise  exceptions.BadArgumentError("You must specify a firstname column number.")
	else:
		firstname_col = opts.firstname_col

	if opts.lastname_col is None:
		raise  exceptions.BadArgumentError("You must specify a lastname column number.")
	else:
		lastname_col = opts.lastname_col

	if opts.group_col is None:
		raise  exceptions.BadArgumentError("You must specify a group column number.")
	else:
		group_col = opts.group_col

	if (firstname_col == lastname_col) or (firstname_col == group_col) or (lastname_col == group_col):
		raise exceptions.BadArgumentError("two columns have the same number (lastname = %d, firstname = %d, group = %d)" %
			(lastname_col, firstname_col, group_col) )

	maxval = 0
	import math
	for number in (lastname_col, firstname_col, group_col):
		maxval = max(maxval, number)

	if maxval > 127:
		raise exceptions.BadArgumentError("Sorry, CSV file must have no more than 128 columns.")

	# WARNING:
	# we can't do any checks on login_col and password_col, because
	# the admin can choose the firstname as password, the firstname as login
	# the group as password (in elementary schools, children can't remember
	# complicated "real" password) and so on. The columns number can totally
	# overlap and this beiing intentionnal.

	encoding = fsapi.get_file_encoding(import_filename)
	if encoding is None:
		# what to choose ? ascii or ~sys.getsystemencoding() ?
		logging.warning("can't automatically detect the file encoding, assuming iso-8859-15 !")
		encoding = 'iso-8859-15'

	import csv

	try:
		if profiles.profiles[profile]: pass
	except KeyError:
		raise exceptions.LicornRuntimeException, "The profile '%s' doesn't exist." % profile

	firstline    = open(import_filename).readline()
	lcndialect   = csv.Sniffer().sniff(firstline)
	if lcndialect.delimiter != opts.separator:
		separator = lcndialect.delimiter
	else:
		separator =  opts.separator

	try:
		import_fd   = open(import_filename,"rb")
	except (OSError, IOError), e:
		raise exceptions.LicornRuntimeError("can't load CSV file (was: %s)" % str(e))

	groups_to_add = []
	users_to_add  = []

	sys.stderr.write("Reading input file: ")

	i = 0
	for fdline in import_fd:

		line = fdline[:-1].split(separator)
		#print(str(line))

		user = {}
		for (column, number) in ( ("firstname", firstname_col), ("lastname", lastname_col), ("group", group_col), ("login", opts.login_col), ("password", opts.password_col) ):

			try:
				if number is None:
					user[column] = None
				else:
					if column == "password" and number in (lastname_col, firstname_col):
						# FIXME: decide wether to kill this code or not:
						# for small children, make the password as simple as the login to type.
						# tell validate_name() to be aggressive to achieve this.
						user[column] = hlstr.validate_name(unicode(line[number], encoding), True)
					else:
						user[column] = unicode(clean_csv_field(line[number]), encoding)

			except IndexError, e:
				raise exceptions.LicornRuntimeError("\nImport error on line %d: no %s specified or bad %s data (was: %s)." % (i+1, column, column, e))

			except UnicodeEncodeError, e:
				raise exceptions.LicornRuntimeError("Encoding not supported for input filename (was: %s)." % str(e))

		try:
			if opts.login_col is not None:
				user['login'] =	users.make_login(inputlogin = user['login'])
			else:
				user['login'] = users.make_login(firstname = user['firstname'], lastname = user['lastname'])

		except IndexError, e:
			raise exceptions.LicornRuntimeError("\nImport error on line %d: no group specified or bad group data (was: %s)." % (i+1, e))

		except exceptions.LicornRuntimeError, e:
			raise exceptions.LicornRuntimeError("\nImport error on line %d (was: %s)." % (i+1, e))

		try:
			user['group'] =	groups.make_name(user['group'])

		except IndexError, e:
			raise exceptions.LicornRuntimeError("\nImport error on line %d: no group specified or bad group data (was: %s)." % (i+1, e))

		except exceptions.LicornRuntimeError, e:
			raise exceptions.LicornRuntimeError("\nImport error on line %d (was: %s)." % (i+1, e))

		if user['group'] not in groups_to_add:
			groups_to_add.append(user['group'])

		#print str(user)
		users_to_add.append(user)

		if not (i % 100):
			sys.stderr.write(".")
			sys.stderr.flush()
		i += 1
		user['linenumber'] = i

	ltrace('add', '  import_users: users_to_add=%s,\ngroups_to_add=%s' % (
		users_to_add, groups_to_add))

	import_fd.close()
	sys.stderr.write(" done." + "\n")

	# this will be used to recursive build an HTML page of all groups / users
	# with theyr respective passwords to be printed / distributed to all users.
	# this is probably unefficient because CSV file could be already sorted, but
	# constructing this structure will not cost that much.
	data_to_export_to_html = {}

	# Add groups and users
	length_groups = len(groups_to_add)
	length_users  = len(users_to_add)

	quantity = length_groups + length_users
	if quantity <= 0:
		quantity = 1
	delta = 100.0 / float(quantity) # increment for progress indicator
	progression = 0.0

	if opts.confirm_import:
		i = 0 # to print i/length
		for g in groups_to_add:
			try:
				i += 1
				groups.AddGroup(name=g, batch=opts.no_sync)
				logging.progress("\rAdded group « %s » (group %d/%d), progress: %d%%" %
					( g, i, length_groups, math.ceil(progression)) )
				progression += delta
			except exceptions.AlreadyExistsException, e:
				logging.warning(str(e))
				progression += delta
			except exceptions.LicornException, e:
				sys.stdout.flush()
				raise e
			data_to_export_to_html[g]= {}
			sys.stdout.flush()

	if not opts.confirm_import:
		import string
		sys.stderr.write(styles.stylize(styles.ST_PATH,
			'''Fields order:\n%s%s%s%spassword''' % (
			string.ljust("FIRSTname",configuration.users.login_maxlenght),
			string.ljust("LASTname",configuration.users.login_maxlenght),
			string.ljust("login",configuration.users.login_maxlenght),
			string.ljust("group",configuration.groups.name_maxlenght))
			) + "\n")
	i = 0
	for u in users_to_add:
		try:
			i += 1
			if opts.confirm_import:
				(uid, login, password) = users.AddUser(lastname=u['lastname'],
				firstname=u['firstname'], login=u['login'],
				password=u['password'], profile=profile, batch=opts.no_sync)
				groups.AddUsersInGroup(name=u['group'], users_to_add=[ login ],
					batch=opts.no_sync)

				logging.progress('''\rAdded user « %s %s » [login=%s, uid=%d,'''
				''' passwd=%s] (user %d/%d), progress: %d%%'''
					% ( u['firstname'], u['lastname'], login, uid, password, i,
					length_users, math.ceil(progression)) )

				# the dictionnary key is forged to have something that is sortable.
				# like this, the user accounts will be sorted in their group.
				data_to_export_to_html[ u['group'] ][ u['lastname'] + u['firstname'] ] = [ u['firstname'], u['lastname'], login, password ]
			else:
				# why make_login() for examples and not prepare the logins whenloading CSV file ?
				# this is a pure arbitrary choice. It just feels more consistent for me.
				if opts.login_col:
					login = u['login']
				else:
					try:
						login = users.make_login(u['lastname'], u['firstname'])
					except exceptions.LicornRuntimeError, e:
						raise exceptions.LicornRuntimeError("Import error on line %d.\n%s" % (u['linenumber'], e))

				sys.stdout.write("%s%s%s%s%s\n" % (
					string.ljust(u['firstname'],configuration.users.login_maxlenght),
					string.ljust(u['lastname'],configuration.users.login_maxlenght),
					string.ljust(login,configuration.users.login_maxlenght),
					string.ljust(u['group'],configuration.groups.name_maxlenght),
					u['password'] if u['password'] else '(autogenerated upon creation)'))

				if i > 10:
					# 10 examples should be sufficient for admin to see if his options
					# are correct or not.
					break
			progression += delta
		except exceptions.AlreadyExistsException, e:
			logging.warning(str(e))
			progression += delta
			# FIXME: if user already exists, don't put it in the data / HTML report.
			continue
		except exceptions.LicornException, e:
			sys.stdout.flush()

		sys.stdout.flush()

	#print str(data_to_export_to_html)

	if opts.confirm_import:

		sys.stderr.write ("Finished importing, creating summary HTML file: ")

		groups = data_to_export_to_html.keys()
		groups.sort()

		import time
		date_time = time.strftime("%d %m %Y à %H:%M:%S", time.gmtime())
		html_file = open("%s/import_%s-%s.html" % (configuration.home_archive_dir, profile, hlstr.validate_name(date_time)), "w")
		html_file.write('''<html>
			<head>
				<meta http-equiv="content-type" content="text/html; charset=utf-8" />
				<style type=\"text/css\">
				<!--
					body { font-size:14pt; }
					h1,h2,h3 { text-align:center; }
					p,div { text-align:center; }
					table { margin: 3em 10%%; width: 80%%; border: 5px groove #369; border-collapse: collapse; }
					tr { border: 1px solid black; }
					th {border-bottom: 3px solid #369; background-color: #99c; }
					td,th { text-align: center; padding: 0.7em; }
					.even { background-color: #eef; }
					.odd { background-color: #efe; }
					div.secflaw {color: #f00; background-color: #fdd; text-align: center; border: 2px dashed #f00; margin: 3em 10%%; padding: 1em; }
				-->
				</style>
			</head>
			<body>
				<h1>Comptes %s et mots de passes</h1>
				<h2>Import réalisé le %s</h2>
				<div class="secflaw">
				La conservation de mots de passe sous toute forme écrite est une vulnérabilité pour votre système.
				<br />
				Merci de supprimer ce fichier et ses versions imprimées une fois les mots de passe distribués.
				</div>
				<div>Accès direct aux %s&nbsp;:''' % (profile, date_time,
					configuration.groups.names.plural))

		for group in groups:
			html_file.write("&nbsp; <a href=\"#%s\">%s</a> &nbsp;" % (group, group))
		html_file.write("</div>")

		for group in groups:
			html_file.write(
				'''<a id="%s"></a>
				<h1>%s «&nbsp;%s&nbsp;»</h1>
				<table>
				<tr>
				<th>Nom</th><th>Prénom</th><th>identifiant</th><th>mot de passe</th>
				</tr>\n''' % (group,configuration.groups.names.singular, group))
			sys.stderr.write('.')

			groupdata = data_to_export_to_html[group]
			users = groupdata.keys()
			users.sort()
			i        = 0
			tr_style = [ "even", "odd" ]
			for user in users:
				html_file.write(
				'''<tr class=%s>
					<td> %s </td>
					<td> %s </td>
					<td><code> %s </code></td>
					<td><code> %s </code></td>
					</tr>''' % (tr_style[i%2],groupdata[user][1],
						groupdata[user][0],groupdata[user][2],
						groupdata[user][3]))
				i += 1
				if not (i % 10):
					sys.stderr.write('.')
			html_file.write("</table>\n")

		html_file.write("</body>\n</html>\n")
		html_file.close()
		sys.stderr.write(" done." + "\n")
		sys.stdout.write("report: %s\n" % html_file.name )

	if opts.no_sync:
		groups.WriteConf()
		users.WriteConf()
		profiles.WriteConf(configuration.profiles_config_file)
def add_user(opts, args, users, groups, profiles):
	""" Add a user account on the system. """

	ltrace('add', '> add_user(opts=%s, args=%s)' % (opts, args))

	if opts.profile and not profiles.has_key(opts.profile):
		opts.profile = profiles.name_to_group(opts.profile)

	if opts.firstname is None:
		firstname = None
	else:
		firstname = unicode(opts.firstname)

	if opts.lastname is None:
		lastname = None
	else:
		lastname = unicode(opts.lastname)

	if opts.gecos is None:
		gecos = None
	else:
		gecos = unicode(opts.gecos)

	if opts.password is None:
		password = None
	else:
		password = unicode(opts.password)

	if opts.primary_gid:
		# if the opts.primary_gid is not an existing GID, try to guess if it is
		# an existing group name, and then convert it to a GID.
		if not groups.has_key(opts.primary_gid):
			opts.primary_gid = groups.name_to_gid(opts.primary_gid)

	# the else [ None ] is important for the unique case when called with only
	# --firstname and --lastname (login will be autogenerated).
	for login in opts.login.split(',') if opts.login != None else [ None ]:
		if login != '':
			try:
				users.AddUser(lastname=lastname, firstname=firstname,
					password=password, primary_gid=opts.primary_gid,
					desired_uid=opts.uid, profile=opts.profile, skel=opts.skel,
					login=login, gecos=gecos, system=opts.system,
					home=opts.home,	batch=False, force=opts.force,
					listener=opts.listener)
			except exceptions.AlreadyExistsException, e:
				logging.warning(str(e))
	ltrace('add', '< add_user()')
def add_user_in_groups(opts, args, users, groups):

	ltrace('add', '> add_user_in_group().')

	uids_to_add = cli_select(users, 'user',
			args,
			[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			],
			default_selection=filters.NONE)

	for g in opts.groups_to_add.split(','):
		if g != '':
			try:
				groups.AddUsersInGroup(name=g,
					users_to_add=uids_to_add, listener=opts.listener)
			except exceptions.LicornRuntimeException, e:
				logging.warning("Unable to add user(s) %s in group %s (was: %s)."
					% (styles.stylize(styles.ST_LOGIN, opts.login),
					styles.stylize(styles.ST_NAME, g), str(e)))
			except exceptions.LicornException, e:
				raise exceptions.LicornRuntimeError(
					"Unable to add user(s) %s in group %s (was: %s)."
					% (styles.stylize(styles.ST_LOGIN, opts.login),
					styles.stylize(styles.ST_NAME, g), str(e)))

	ltrace('add', '< add_user_in_group().')
def dispatch_add_user(opts, args, users, groups, profiles, **kwargs):
	""" guess how we were called:
		- add a user (creation)
		- add a user into one or more group(s)
	"""

	ltrace('add', '> dispatch_add_user(%s, %s)' % (opts, args))

	if opts.login is None:
		if len(args) == 2:
			opts.login = args[1]
			args[1] = ''
			add_user(opts, args, users, groups, profiles)
		elif len(args) == 3:
			opts.login = args[1]
			opts.groups_to_add = args[2]
			args[1] = ''
			args[2] = ''
			add_user_in_groups(opts, args, users, groups)
		else:
			add_user(opts, args, users, groups, profiles)
	else:
		add_user(opts, args, users, groups, profiles)

	ltrace('add', '< dispatch_add_user()')
def add_group(opts, args, groups, **kwargs):
	""" Add a POSIX group. """

	ltrace('add', '> add_group().')

	if opts.name is None and len(args) == 2:
		opts.name = args[1]

	if opts.description:
		opts.description = unicode(opts.description)

	ltrace('add', 'group(s) to add: %s.' % opts.name)

	for name in opts.name.split(',')if opts.name != None else []:
		if name != '':
			try:
				ltrace('add', 'adding group %s.' % name)
				groups.AddGroup(name, description=opts.description,
					system=opts.system, groupSkel=opts.skel,
					desired_gid=opts.gid, permissive=opts.permissive,
					force=opts.force, listener=opts.listener)
			except exceptions.AlreadyExistsException, e:
				logging.warning(str(e))

	ltrace('add', '< add_group().')
def add_profile(opts, args, profiles, **kwargs):
	""" Add a system wide User profile. """

	ltrace('add', '> add_profile().')

	if opts.name is None and len(args) == 2:
		opts.name = args[1]

	if opts.groups != []:
		opts.groups = opts.groups.split(',')

	if opts.name:
		opts.name = unicode(opts.name)

	if opts.description:
		opts.description = unicode(opts.description)

	for name in opts.name.split(',') if opts.name != None else []:
		if name == '':
			continue
		try:
			profiles.AddProfile(name, group=opts.group, profileQuota=opts.quota,
				groups=opts.groups, description=opts.description,
				profileShell=opts.shell, profileSkel=opts.skeldir,
				force_existing=opts.force_existing, listener=opts.listener)
		except exceptions.AlreadyExistsException, e:
			logging.warning(str(e))

	ltrace('add', '< add_profile().')
def add_keyword(opts, args, keywords, **kwargs):
	""" Add a keyword on the system. """

	if opts.name is None and len(args) == 2:
		opts.name = args[1]

	keywords.AddKeyword(unicode(opts.name), unicode(opts.parent),
		unicode(opts.description), listener=opts.listener)
def add_privilege(opts, args, privileges, **kwargs):

	if opts.privileges_to_add is None and len(args) == 2:
		opts.privileges_to_add = args[1]

	privileges.add(opts.privileges_to_add.split(','), listener=opts.listener)
def add_main():
	import argparser as agp

	functions = {
		'usr':	         (agp.add_user_parse_arguments, dispatch_add_user),
		'user':	         (agp.add_user_parse_arguments, dispatch_add_user),
		'users':         (agp.addimport_parse_arguments, import_users),
		'grp':           (agp.add_group_parse_arguments, add_group),
		'group':         (agp.add_group_parse_arguments, add_group),
		'groups':        (agp.add_group_parse_arguments, add_group),
		'profile':       (agp.add_profile_parse_arguments, add_profile),
		'profiles':      (agp.add_profile_parse_arguments, add_profile),
		'priv':			 (agp.add_privilege_parse_arguments, add_privilege),
		'privs':		 (agp.add_privilege_parse_arguments, add_privilege),
		'privilege':	 (agp.add_privilege_parse_arguments, add_privilege),
		'privileges':	 (agp.add_privilege_parse_arguments, add_privilege),
		'kw':            (agp.add_keyword_parse_arguments, add_keyword),
		'tag':           (agp.add_keyword_parse_arguments, add_keyword),
		'tags':          (agp.add_keyword_parse_arguments, add_keyword),
		'keyword':       (agp.add_keyword_parse_arguments, add_keyword),
		'keywords':      (agp.add_keyword_parse_arguments, add_keyword),
	}

	cli_main(functions, _app)

if __name__ == "__main__":
	add_main()
