#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://ilcorn.org/documentation/cli

add - add something on the system, a user account, a group...

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys

from licorn.foundations import logging, exceptions, options, styles, hlstr, fsapi, file_locks
from licorn.core        import configuration, users, groups, profiles

_app = {
	"name"     		 : "licorn-add",
	"description"	 : "Licorn Add Entries",
	"author"   		 : "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def import_users() :
	""" Massively import user accounts from a CSV file."""

	def clean_csv_field(field) :
		return field.replace("'","").replace('"','')

	if opts.filename is None :
		raise exceptions.BadArgumentError, "You must specify a file name."
	else :
		import_filename = opts.filename

	if opts.profile is None :
		raise exceptions.BadArgumentError, "You must specify a profile."
	else :
		profile = opts.profile

	if opts.firstname_col is None :
		raise  exceptions.BadArgumentError("You must specify a firstname column number.")
	else :
		firstname_col = opts.firstname_col

	if opts.lastname_col is None :
		raise  exceptions.BadArgumentError("You must specify a lastname column number.")
	else :
		lastname_col = opts.lastname_col

	if opts.group_col is None :
		raise  exceptions.BadArgumentError("You must specify a group column number.")
	else :
		group_col = opts.group_col

	if (firstname_col == lastname_col) or (firstname_col == group_col) or (lastname_col == group_col) :
		raise exceptions.BadArgumentError("two columns have the same number (lastname = %d, firstname = %d, group = %d)" %
			(lastname_col, firstname_col, group_col) )

	maxval = 0
	import math
	for number in (lastname_col, firstname_col, group_col) :
		maxval = max(maxval, number)

	if maxval > 127 :
		raise exceptions.BadArgumentError("Sorry, CSV file must have no more than 128 columns.")

	# WARNING :
	# we can't do any checks on login_col and password_col, because
	# the admin can choose the firstname as password, the firstname as login
	# the group as password (in elementary schools, children can't remember
	# complicated "real" password) and so on. The columns number can totally
	# overlap and this beiing intentionnal.

	encoding = fsapi.get_file_encoding(import_filename)
	if encoding is None :
		# what to choose ? ascii or ~sys.getsystemencoding() ?
		logging.warning("can't automatically detect the file encoding, assuming iso-8859-15 !")
		encoding = 'iso-8859-15'

	import csv

	try :
		if profiles.profiles[profile] : pass
	except KeyError :
		raise exceptions.LicornRuntimeException, "The profile '%s' doesn't exist." % profile
	
	firstline    = open(import_filename).readline()
	hzndialect   = csv.Sniffer().sniff(firstline)
	if hzndialect.delimiter != opts.separator :
		separator = hzndialect.delimiter 
	else :
		separator =  opts.separator

	try :
		import_fd   = open(import_filename,"rb")
	except (OSError, IOError), e :
		raise exceptions.LicornRuntimeError("can't load CSV file (was: %s)" % str(e))

	groups_to_add = []
	users_to_add  = []

	sys.stderr.write("Reading input file : ")

	i = 0
	for fdline in import_fd :

		line = fdline[:-1].split(separator)
		#print(str(line))

		user = {}
		for (column, number) in ( ("firstname", firstname_col), ("lastname", lastname_col), ("group", group_col), ("login", opts.login_col), ("password", opts.password_col) ) :
	
			try :
				if number is None :
					user[column] = None
				else :
					if column == "password" and number in (lastname_col, firstname_col) :
						# FIXME: decide wether to kill this code or not.
						#
						# AbulEdu specific :
						# for small children, make the password as simple as the login to type.
						# tell validate_name() to be aggressive to achieve this.
						user[column] = hlstr.validate_name(unicode(line[number], encoding), True)
					else :
						user[column] = unicode(clean_csv_field(line[number]), encoding)

			except IndexError, e :
				raise exceptions.LicornRuntimeError("\nImport error on line %d : no %s specified or bad %s data (was: %s)." % (i+1, column, column, e))

			except UnicodeEncodeError, e :
				raise exceptions.LicornRuntimeError("Encoding not supported for input filename (was: %s)." % str(e))

		try :
			if opts.login_col is not None :
				user['login'] =	users.UsersList.make_login(inputlogin = user['login'])
			else :
				user['login'] = users.UsersList.make_login(firstname = user['firstname'], lastname = user['lastname'])
		
		except IndexError, e :
			raise exceptions.LicornRuntimeError("\nImport error on line %d : no group specified or bad group data (was: %s)." % (i+1, e))

		except exceptions.LicornRuntimeError, e :
			raise exceptions.LicornRuntimeError("\nImport error on line %d (was: %s)." % (i+1, e))

		try :
			user['group'] =	groups.GroupsList.make_name(user['group'])
		
		except IndexError, e :
			raise exceptions.LicornRuntimeError("\nImport error on line %d : no group specified or bad group data (was: %s)." % (i+1, e))

		except exceptions.LicornRuntimeError, e :
			raise exceptions.LicornRuntimeError("\nImport error on line %d (was: %s)." % (i+1, e))

		if user['group'] not in groups_to_add :
			groups_to_add.append(user['group'])

		#print str(user)
		users_to_add.append(user)

		if not (i % 100) :
			sys.stderr.write(".")
			sys.stderr.flush()
		i+=1
		user['linenumber'] = i

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
	if quantity <= 0 :
		quantity = 1
	delta = 100.0 / float(quantity) # increment for progress indicator
	progression = 0.0

	if opts.confirm_import :
		i = 0 # to print i/length
		for g in groups_to_add :
			try :
				i += 1
				groups.AddGroup(g, "", False, "/etc/skel", batch=opts.no_sync)
				logging.progress("\rAdded group « %s » (group %d/%d), progress : %d%%" %
					( g, i, length_groups, math.ceil(progression)) )
				progression += delta
			except exceptions.AlreadyExistsException, e :
				logging.warning(str(e))
				progression += delta
			except exceptions.LicornException, e :
				sys.stdout.flush()
				raise e
			data_to_export_to_html[g]= {}
			sys.stdout.flush()
				
	if not opts.confirm_import :
		sys.stderr.write(styles.stylize(styles.ST_PATH, "Fields order : FIRSTname ; LASTname ; login ; password ; group") + "\n")

	i = 0
	for u in users_to_add :
		try :
			i += 1
			if opts.confirm_import :
				(uid, login, password) = users.AddUser(u['lastname'], u['firstname'], login=u['login'], password=u['password'], profile=profile, batch=opts.no_sync)
				groups.AddUsersInGroup(u['group'], [ login ], batch=opts.no_sync)

				logging.progress("\rAdded user « %s %s » [login=%s,uid=%d,passwd=%s] (user %d/%d), progress : %d%%" 
					% ( u['firstname'], u['lastname'], login, uid, password, i, length_users, math.ceil(progression)) )

				# the dictionnary key is forged to have something that is sortable.
				# like this, the user accounts will be sorted in their group.
				data_to_export_to_html[ u['group'] ][ u['lastname'] + u['firstname'] ] = [ u['firstname'], u['lastname'], login, password ]
			else :
				# why make_login() for examples and not prepare the logins whenloading CSV file ?
				# this is a pure arbitrary choice. It just feels more consistent for me.
				if opts.login_col :
					login = u['login']
				else :
					try :
						login = users.make_login(u['lastname'], u['firstname'])
					except exceptions.LicornRuntimeError, e :
						raise exceptions.LicornRuntimeError("Import error on line %d.\n%s" % (u['linenumber'], e))

				sys.stdout.write("%s;%s;%s;%s;%s;\n" % ( u['firstname'], u['lastname'], login, u['password'], u['group'] ) )

				if i > 10 :
					# 10 examples should be sufficient for admin to see if his options
					# are correct or not.
					break
			progression += delta
		except exceptions.AlreadyExistsException, e :
			logging.warning(str(e))
			progression += delta
			# FIXME : if user already exists, don't put it in the data / HTML report.
			continue
		except exceptions.LicornException, e :
			sys.stdout.flush()
			raise e
		sys.stdout.flush()

	#print str(data_to_export_to_html)

	if opts.confirm_import :

		sys.stderr.write ("Finished importing, creating summary HTML file : ")

		groups = data_to_export_to_html.keys()
		groups.sort()

		import time
		date_time = time.strftime("%d %m %Y à %H:%M:%S", time.gmtime())
		html_file = open("%s/import_%s-%s.html" % (configuration.home_archive_dir, profile, hlstr.validate_name(date_time)), "w")
		html_file.write("<html>\n<head>\n"
			+ "<title>Import de comptes %s du %s</title>\n" % (profile, date_time)
			+ "<style type=\"text/css\">\n"
			+ "<!--\n"
			+ "body { font-size:14pt; }\n"
			+ "h1,h2,h3 { text-align:center; }\n"
			+ "p,div { text-align:center; }\n"
			+ "table { margin: 3em 10%; width: 80%; border: 5px groove #369; border-collapse: collapse; }\n"
			+ "tr { border : 1px solid black; }\n" 
			+ "th {border-bottom: 3px solid #369; background-color: #99c; }\n"
			+ "td,th { text-align: center; padding: 0.7em; }\n"
			+ ".even { background-color: #eef; }\n"
			+ ".odd { background-color: #efe; }\n"
			+ "div.secflaw {color: #f00; background-color: #fdd; text-align: center; border: 2px dashed #f00; margin: 3em 10%; padding: 1em; }\n"
			+ "-->\n"
			+ "</style>\n"
			+ "</head>\n"
			+ "<body><h1>Comptes %s et mots de passes</h1>\n" % profile
			+ "<h2>Import réalisé le %s</h2>\n" % date_time
			+ "<div class=\"secflaw\">\n"
			+ "La conservation de mots de passe sous toute forme écrite est une vulnérabilité pour votre système."
			+ "<br />"
			+ "Merci de supprimer ce fichier et ses versions imprimées une fois les mots de passe distribués.\n"
			+ "</div>\n"
			+ "<div>Accès direct aux %s&nbsp;: " % configuration.groups.names['plural'])
		for group in groups :
			html_file.write("&nbsp; <a href=\"#%s\">%s</a> &nbsp;" % (group, group))
		html_file.write("</div>\n")

		for group in groups :
			html_file.write(
				"<a id=\"%s\"></a>\n" % group
				+ "<h1>%s «&nbsp;%s&nbsp;»</h1>\n" % (configuration.groups.names['singular'], group)
				+ "<table>\n"
				+ "<tr>\n"
				+ "<th>Nom</th><th>Prénom</th><th>identifiant</th><th>mot de passe</th>\n"
				+ "</tr>\n")
			sys.stderr.write('.')

			groupdata = data_to_export_to_html[group]
			users = groupdata.keys()
			users.sort()
			i        = 0
			tr_style = [ "even", "odd" ]
			for user in users :
				html_file.write(
				"<tr class=%s>\n" % tr_style[i%2]
					+ "<td>" + groupdata[user][1] + "</td>\n"
					+ "<td>" + groupdata[user][0] + "</td>\n"
					+ "<td><code>" + groupdata[user][2] + "</code></td>\n"
					+ "<td><code>" + groupdata[user][3] + "</code></td>\n"
				+ "</tr>\n")
				i+=1
				if not (i % 10) :
					sys.stderr.write('.')
			html_file.write("</table>\n")

		html_file.write("</body>\n</html>\n")
		html_file.close()
		sys.stderr.write(" done." + "\n")
		sys.stdout.write("report : %s\n" % html_file.name )
	
	if opts.no_sync :
		groups.WriteConf()
		users.WriteConf()
		profiles.WriteConf(configuration.profiles_config_file)
		
def add_user() :
	""" Add a user account on the system. """

	if opts.firstname is None :
		firstname = None
	else :
		firstname = unicode(opts.firstname)
	
	if opts.lastname is None :
		lastname = None
	else :
		lastname = unicode(opts.lastname)
	
	if opts.gecos is None :
		gecos = None
	else :
		gecos = unicode(opts.gecos)
	
	if opts.password is None :
		password = None
	else :
		password = unicode(opts.password)
	
	for login in opts.login.split(',') :
		if login != '' :
			try :
				users.AddUser(lastname, firstname, password, opts.primary_group, opts.profile, opts.skel, login, gecos, False)
			except exceptions.AlreadyExistsException :
				logging.warning('User %s already exists on the system.' % login)
def add_group() :
	""" Add a POSIX group. """

	if opts.description == '' :
		description = ''
	else :
		description = unicode(opts.description)
	
	for name in opts.name.split(',') :
		if name != '' :
			try :
				groups.AddGroup(name, description = description, system = opts.system, skel = opts.skel, gid = opts.gid, permissive = opts.permissive)
			except exceptions.AlreadyExistsException :
				logging.warning('Group %s already exists on the system.' % name)
def add_profile() :
	""" Add a system wide User profile. """

	_groups = []
	if opts.groups is not None :
		_groups = opts.groups.split(',')

	if opts.name :
		name = unicode(opts.name)
	else :
		name = None
	
	if opts.comment :
		comment = unicode(opts.comment)
	else :
		comment = None

	profiles.AddProfile(name, group = opts.group, quota = opts.quota, groups = _groups, comment = comment, shell = opts.shell, skeldir = opts.skeldir, force_existing = opts.force_existing)
	profiles.WriteConf(configuration.profiles_config_file)
def add_keyword() :
	""" Add a keyword on the system. """
	from licorn.core import keywords
	keywords.AddKeyword(unicode(opts.name), unicode(opts.parent), unicode(opts.description))
def add_workstation() :
	raise NotImplementedError("add_workstations not implemented.")
def add_webfilter() :
	raise NotImplementedError("add_webfilters_types not implemented.")

if __name__ == "__main__" :

	try :
		giantLock = file_locks.FileLock(configuration, "add", 10)
		giantLock.Lock()
	except (IOError, OSError), e :
		logging.error(logging.GENERAL_CANT_ACQUIRE_GIANT_LOCK % str(e))

	try :
		try :

			if "--no-colors" in sys.argv :
				options.SetNoColors(True)

			from licorn.interfaces.cli import argparser

			if len(sys.argv) < 2 :
				# automatically display help if no arg/option is given.
				sys.argv.append("--help")
				argparser.general_parse_arguments(_app)

			if len(sys.argv) < 3 :
				# this will display help, but when parsed later by specific functions.
				# (for user/group/profile specific help)
				sys.argv.append("--help")
				help_appended = True
			else :
				help_appended = False

			mode = sys.argv[1]

			if mode == 'user' :
				(opts, args) = argparser.add_user_parse_arguments(_app)
				options.SetFrom(opts)

				if len(args) == 2 :
					opts.login = args[1]
					add_user()
				elif len(args) == 3 :
					login = args[1]
					ingroups = args[2]
					#
					# FIXME : refactoring + why don't we see logging.info of groups.AddUsersInGroup ?
					#

					for g in ingroups.split(',') :
						if g != "" :
							try :
								groups.AddUsersInGroup(g, login.split(','))
							except exceptions.LicornRuntimeException, e :
								logging.warning("Unable to add user %s in group %s (was: %s)." % (styles.stylize(styles.ST_LOGIN, login), styles.stylize(styles.ST_NAME, g), str(e)))
							except exceptions.LicornException, e:
								raise exceptions.LicornRuntimeError("Unable to add user %s in group %s (was: %s)." % (styles.stylize(styles.ST_LOGIN, login), styles.stylize(styles.ST_NAME, g), str(e)))
				else :
					add_user()
					
			elif mode == 'users' :
				(opts, args) = argparser.addimport_parse_arguments(_app)
				options.SetFrom(opts)
				import_users()
			elif mode == 'group' :
				(opts, args) = argparser.add_group_parse_arguments(_app)
				if len(args) == 2 :
					opts.name = args[1]
				options.SetFrom(opts)
				add_group()
			elif mode == 'profile' :
				(opts, args) = argparser.add_profile_parse_arguments(_app)
				if len(args) == 2 :
					opts.name = args[1]
				options.SetFrom(opts)
				add_profile()
			elif mode == 'keyword' :
				(opts, args) = argparser.add_keyword_parse_arguments(_app)
				if len(args) == 2 :
					opts.name = args[1]
				options.SetFrom(opts)
				add_keyword()
			else :
				if not help_appended :
					logging.warning(logging.GENERAL_UNKNOWN_MODE % mode)
					sys.argv.append("--help")

				argparser.general_parse_arguments(_app)

		except exceptions.LicornException, e :
			configuration.CleanUp()
			giantLock.Unlock()
			logging.error (str(e), e.errno)

		except KeyboardInterrupt :
			logging.warning(logging.GENERAL_INTERRUPTED)

	finally :
		configuration.CleanUp()
		giantLock.Unlock()
