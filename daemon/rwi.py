# -*- coding: utf-8 -*-
"""
Licorn Daemon Real World Interface.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Partial Copyright (C) 2010 Robin Lucbernet <robinlucbernet@gmail.com>
Licensed under the terms of the GNU GPL version 2.
"""
import os, Pyro.core

from threading import current_thread

from licorn.foundations           import options, exceptions, logging
from licorn.foundations           import fsapi, hlstr
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import NamedObject, pyro_protected_attrs
from licorn.foundations.messaging import LicornMessage, ListenerObject
from licorn.foundations.constants import filters

from licorn.core import LMC

class RealWorldInterface(NamedObject, ListenerObject, Pyro.core.ObjBase):
	""" Receive requests from "outside" programs and objects (typically CLI and
		WMI), and forward them to internal core controllers after having done
		preparsing and checks. """
	_licorn_protected_attrs = (
			NamedObject._licorn_protected_attrs
			+ pyro_protected_attrs
		)
	def __init__(self):
		NamedObject.__init__(self, name='rwi')
		Pyro.core.ObjBase.__init__(self)
		assert ltrace('rwi', '| RWIController.__init__()')
	def output(self, text_message):
		return current_thread().listener.process(
			LicornMessage(data=text_message),
			options.msgproc.getProxy())
	def select(self, controller, ctype, args, include_id_lists,
		exclude_id_lists=[], default_selection=filters.NONE, all=False):

		assert ltrace('cli', '''> select(controller=%s, ctype=%s, args=%s, '''
			'''include_id_lists=%s, exclude_id_lists=%s, default_selection=%s, '''
			'''all=%s)''' % (controller, ctype, args, include_id_lists,
				exclude_id_lists, default_selection, all))
		# use a set() to avoid duplicates during selections. This will allow us,
		# later in implementation to do more complex selections (unions,
		# differences, intersections and al.
		xids = set()
		if all:
			# if --all: manually included IDs (with --login, --group, --uid, --gid)
			# will be totally discarded (--all gets precedence). But excluded items
			# will still be excluded, to allow "--all --exclude-login toto"
			# semi-complex selections.
			ids = set(controller.keys())
		else:
			ids = set()

			something_tried = False

			if len(args) > 1:
				for arg in args[1:]:
					#assert ('cli', '  select(add_arg=%s)' % arg)
					include_id_lists.append((arg, controller.guess_identifier))

			# select included IDs
			for id_arg, resolver in include_id_lists:
				if id_arg is None:
					continue
				for id in id_arg.split(',') if hasattr(id_arg, 'split') else id_arg:
					if id is '':
						continue

					try:
						something_tried = True
						ids.add(resolver(id))
						assert ltrace('cli', '  select %s(%s) -> %s' %
							(resolver._RemoteMethod__name, id, resolver(id)))
					except (KeyError, exceptions.DoesntExistsException):
						logging.notice('''Skipped non existing or invalid %s or '''
							'''%sID '%s'.''' % (ctype, ctype[0].upper(),
							stylize(ST_NAME, id)))
						continue

		# select excluded IDs, to remove them from included ones
		for id_arg, resolver in exclude_id_lists:
			if id_arg is None:
				continue
			for id in id_arg.split(',') if hasattr(id_arg, 'split') else id_arg:
				if id is '':
					continue
				try:
					xids.add(resolver(id))
				except (KeyError, exceptions.DoesntExistsException):
					logging.notice('''Skipped non existing or invalid %s or '''
						'''%sID '%s'.''' % (ctype, ctype[0].upper(),
						stylize(ST_NAME, id)))
					continue

		# now return included IDs, minux excluded IDs, in different conditions.
		if ids != set():
			selection = list(ids.difference(xids))
		else:
			if something_tried:
				selection = []
			else:
				if default_selection is filters.NONE:
					logging.warning('You must specify at least one %s!' % ctype)
					selection = []
				else:
					selection = list(set(
						controller.Select(default_selection)).difference(xids))

		assert ltrace('cli', '< select(return=%s)' % selection)
		return selection
	### GET
	def get_users(self, opts, args):
		""" Get the list of POSIX user accounts (Samba / LDAP included). """

		if opts.dump:
			self.output(LMC.users.dump())
			return

		assert ltrace('get', '> get_users(%s,%s)' % (opts, args))

		users_to_get = LMC.users.Select(
			self.select(LMC.users, 'user',
				args,
				include_id_lists=[
					(opts.login, LMC.users.login_to_uid),
					(opts.uid, LMC.users.confirm_uid)
				],
				exclude_id_lists=[
					(opts.exclude, LMC.users.guess_identifier),
					(opts.exclude_login, LMC.users.login_to_uid),
					(opts.exclude_uid, LMC.users.confirm_uid)
				],
				default_selection=filters.STANDARD,
				all=opts.all)
			)

		if opts.xml:
			data = LMC.users.ExportXML(selected=users_to_get, long_output=opts.long)
		else:
			data = LMC.users.ExportCLI(selected=users_to_get, long_output=opts.long)

		if data and data != '\n':
			self.output(data)

		assert ltrace('get', '< get_users()')
	def get_groups(self, opts, args):
		""" Get the list of POSIX LMC.groups (can be LDAP). """

		if opts.dump:
			self.output(LMC.groups.dump())
			return

		assert ltrace('get', '> get_groups(%s,%s)' % (opts, args))

		selection = filters.NONE

		if opts.privileged:
			selection = filters.PRIVILEGED
		elif opts.responsibles:
			selection = filters.RESPONSIBLE
		elif opts.guests:
			selection = filters.GUEST
		elif opts.system:
			selection = filters.SYSTEM
		elif opts.empty:
			selection = filters.EMPTY
		elif opts.not_responsibles:
				selection = filters.NOT_RESPONSIBLE
		elif opts.not_guests:
				selection = filters.NOT_GUEST
		elif opts.not_system:
				selection = filters.NOT_SYSTEM
		elif opts.not_privileged:
				selection = filters.NOT_PRIVILEGED

		elif not opts.all:
			# must be the last case!
			selection = filters.STANDARD

		groups_to_get = LMC.groups.Select(
			self.select(LMC.groups, 'group',
				args,
				[
					(opts.name, LMC.groups.name_to_gid),
					(opts.gid, LMC.groups.confirm_gid)
				],
				exclude_id_lists = [
					(opts.exclude, LMC.groups.guess_identifier),
					(opts.exclude_group, LMC.groups.name_to_gid),
					(opts.exclude_gid, LMC.groups.confirm_gid)
				],
				default_selection=selection,
				all=opts.all)
			)

		if opts.xml:
			data = LMC.groups.ExportXML(selected=groups_to_get, long_output=opts.long)
		else:
			data = LMC.groups.ExportCLI(selected=groups_to_get, long_output=opts.long,
				no_colors=opts.no_colors)

		if data and data != '\n':
			self.output(data)

		assert ltrace('get', '< get_groups()')
	def get_profiles(self, opts, args):
		""" Get the list of user profiles. """

		assert ltrace('get', '> get_profiles(%s,%s)' % (opts, args))

		profiles_to_get = LMC.profiles.Select(
			self.select(LMC.profiles, 'profile',
				args,
				include_id_lists=[
					(opts.name, LMC.profiles.name_to_group),
					(opts.group, LMC.profiles.confirm_group)
				],
				default_selection=filters.ALL)
			)

		if opts.xml:
			data = LMC.profiles.ExportXML(profiles_to_get)
		else:
			data = LMC.profiles.ExportCLI(profiles_to_get)

		if data and data != '\n':
			self.output(data)

		assert ltrace('get', '< get_profiles()')
	def get_keywords(self, opts, args):
		""" Get the list of keywords. """

		assert ltrace('get', '> get_keywords(%s,%s)' % (opts, args))

		if opts.xml:
			data = LMC.keywords.ExportXML()
		else:
			data = LMC.keywords.Export()

		if data and data != '\n':
			self.output(data)

		assert ltrace('get', '< get_keywords()')
	def get_privileges(self, opts, args):
		""" Return the current privileges whitelist, one priv by line. """

		assert ltrace('get', '> get_privileges(%s,%s)' % (opts, args))

		if opts.xml:
			data = LMC.privileges.ExportXML()
		else:
			data = LMC.privileges.ExportCLI()

		self.output(data)

		assert ltrace('get', '< get_privileges()')
	def get_machines(self, opts, args):
		""" Get the list of machines known from the server (attached or not). """

		if opts.dump:
			self.output(LMC.machines.dump())
			return

		assert ltrace('get', '> get_machines(%s,%s)' % (opts, args))

		if opts.mid is not None:
			try:
				machines_to_get = LMC.machines.Select("mid=" + unicode(opts.mid))
			except KeyError:
				logging.error("No matching machine found.")
				return
		else:
			machines_to_get = None

		if opts.xml:
			data = LMC.machines.ExportXML(selected=machines_to_get,
				long_output=opts.long)
		else:
			data = LMC.machines.ExportCLI(selected=machines_to_get,
				long_output=opts.long)

		if data and data != '\n':
			self.output(data)

		assert ltrace('get', '< get_machines()')
	def get_configuration(self, opts, args):
		""" Output th current Licorn system configuration. """

		assert ltrace('get', '> get_configuration(%s,%s)' % (opts, args))

		if len(args) > 1:
			self.output(LMC.configuration.Export(args=args[1:], cli_format=opts.cli_format))
		else:
			self.output(LMC.configuration.Export())

		assert ltrace('get', '< get_configuration()')
	def get_daemon_status(self, opts, args):

		if opts.long:
			self.output(LMC.users.dump())
			self.output(LMC.groups.dump())
			self.output(LMC.machines.dump())

		self.output(LMC.system.get_daemon_status(opts.long, opts.precision))
	def get_webfilters(self, opts, args):
		""" Get the list of webfilter databases and entries.
			This function wraps SquidGuard configuration files.
		"""

		if args is None:
			pass # Tout afficher
		elif args == "time-constraints":
			import licorn.system.time_constraints as timeconstraints
			tc = timeconstraints.TimeConstraintsList()
			if opts.timespace is None:
				if opts.xml is None:
					print "timepause:"
					print tc.Export("timepause")
					print "timeworkingday:"
					print tc.Export("timeworkingday")
				else:
					print tc.ExportXML("timepause")
					print tc.ExportXML("timeworkingday")
			else:
				if opts.xml is None:
					print tc.Export(opts.timespace)
				else:
					print tc.ExportXML(opts.timespace)
		elif args == "forbidden-destinations":
			import licorn.system.forbidden_dest as forbiddendest
			fd = forbiddendest.ForbiddenDestList()
			if opts.xml:
				print "<?xml version='1.0'?>"
				print "<blacklist>"
				print fd.ExportXML("blacklist", "urls")
				print fd.ExportXML("blacklist", "domains")
				print "</blacklist>"
				print "<whitelist>"
				print fd.ExportXML("whitelist", "urls")
				print fd.ExportXML("whitelist", "domains")
				print "</whitelist>"
			else:
				print "* BLACKLIST:"
				print "Urls:"
				print fd.Export("blacklist", "urls")
				print ""
				print "Domains:"
				print fd.Export("blacklist", "domains")
				print "\n"
				print "* WHITELIST:"
				print "Urls:"
				print fd.Export("whitelist", "urls")
				print ""
				print "Domains:"
				print fd.Export("whitelist", "domains")
		else:
			print "Options are: time-constraints | forbidden-destinations"
	### ADD
	def import_users(self, opts, args):
		""" Massively import user accounts from a CSV file."""

		assert ltrace('add', '> import_user(%s,%s)' % (opts, args))

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
			# what to choose? ascii or ~sys.getsystemencoding()?
			logging.warning("can't automatically detect the file encoding, assuming iso-8859-15!")
			encoding = 'iso-8859-15'

		import csv

		try:
			if LMC.profiles[profile]: pass
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

		self.output("Reading input file: ")

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
					user['login'] =	LMC.users.make_login(inputlogin = user['login'])
				else:
					user['login'] = LMC.users.make_login(firstname = user['firstname'], lastname = user['lastname'])

			except IndexError, e:
				raise exceptions.LicornRuntimeError("\nImport error on line %d: no group specified or bad group data (was: %s)." % (i+1, e))

			except exceptions.LicornRuntimeError, e:
				raise exceptions.LicornRuntimeError("\nImport error on line %d (was: %s)." % (i+1, e))

			try:
				user['group'] =	LMC.groups.make_name(user['group'])

			except IndexError, e:
				raise exceptions.LicornRuntimeError("\nImport error on line %d: no group specified or bad group data (was: %s)." % (i+1, e))

			except exceptions.LicornRuntimeError, e:
				raise exceptions.LicornRuntimeError("\nImport error on line %d (was: %s)." % (i+1, e))

			if user['group'] not in groups_to_add:
				groups_to_add.append(user['group'])

			#print str(user)
			users_to_add.append(user)

			if not (i % 100):
				self.output(".")
				# FIXME: how do we force a flush on the client side?
				#sys.stderr.flush()
			i += 1
			user['linenumber'] = i

		assert ltrace('add', '  import_users: users_to_add=%s,\ngroups_to_add=%s' % (
			users_to_add, groups_to_add))

		import_fd.close()
		self.output(" done.\n")

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
					LMC.groups.AddGroup(name=g, batch=opts.no_sync)
					logging.progress("\rAdded group « %s » (group %d/%d), progress: %d%%" %
						( g, i, length_groups, math.ceil(progression)) )
					progression += delta
				except exceptions.AlreadyExistsException, e:
					logging.warning(str(e))
					progression += delta
				except exceptions.LicornException, e:
					# FIXME: flush the listener??
					#sys.stdout.flush()
					raise e
				data_to_export_to_html[g]= {}
				# FIXME: flush the listener??
				#sys.stdout.flush()

		if not opts.confirm_import:
			import string
			self.output(stylize(ST_PATH,
				'''Fields order:\n%s%s%s%spassword''' % (
				string.ljust("FIRSTname", LMC.configuration.users.login_maxlenght),
				string.ljust("LASTname", LMC.configuration.users.login_maxlenght),
				string.ljust("login", LMC.configuration.users.login_maxlenght),
				string.ljust("group", LMC.configuration.groups.name_maxlenght))
				) + "\n")
		i = 0
		for u in users_to_add:
			try:
				i += 1
				if opts.confirm_import:
					(uid, login, password) = LMC.users.AddUser(lastname=u['lastname'],
					firstname=u['firstname'], login=u['login'],
					password=u['password'], profile=profile, batch=opts.no_sync)
					LMC.groups.AddUsersInGroup(name=u['group'], users_to_add=[ login ],
						batch=opts.no_sync)

					logging.progress('''\rAdded user « %s %s » [login=%s, uid=%d,'''
					''' passwd=%s] (user %d/%d), progress: %d%%'''
						% ( u['firstname'], u['lastname'], login, uid, password, i,
						length_users, math.ceil(progression)) )

					# the dictionnary key is forged to have something that is sortable.
					# like this, the user accounts will be sorted in their group.
					data_to_export_to_html[ u['group'] ][ u['lastname'] + u['firstname'] ] = [ u['firstname'], u['lastname'], login, password ]
				else:
					# why make_login() for examples and not prepare the logins when loading CSV file?
					# this is a pure arbitrary choice. It just feels more consistent for me.
					if opts.login_col:
						login = u['login']
					else:
						try:
							login = LMC.users.make_login(u['lastname'], u['firstname'])
						except exceptions.LicornRuntimeError, e:
							raise exceptions.LicornRuntimeError("Import error on line %d.\n%s" % (u['linenumber'], e))

					self.output("%s%s%s%s%s\n" % (
						string.ljust(u['firstname'], LMC.configuration.users.login_maxlenght),
						string.ljust(u['lastname'], LMC.configuration.users.login_maxlenght),
						string.ljust(login, LMC.configuration.users.login_maxlenght),
						string.ljust(u['group'], LMC.configuration.groups.name_maxlenght),
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
				# FIXME: flush the listener.?
				#sys.stdout.flush()
				pass

			#FIXME sys.stdout.flush()

		#print str(data_to_export_to_html)

		if opts.confirm_import:

			self.output("Finished importing, creating summary HTML file: ")

			groups = data_to_export_to_html.keys()
			groups.sort()

			import time
			date_time = time.strftime("%d %m %Y à %H:%M:%S", time.gmtime())
			html_file = open("%s/import_%s-%s.html" % (LMC.configuration.home_archive_dir, profile, hlstr.validate_name(date_time)), "w")
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
						LMC.configuration.groups.names.plural))

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
					</tr>\n''' % (group,LMC.configuration.groups.names.singular, group))
				self.output('.')

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
						self.output('.')
				html_file.write("</table>\n")

			html_file.write("</body>\n</html>\n")
			html_file.close()
			self.output(" done.\nreport: %s\n" % html_file.name )

		if opts.no_sync:
			LMC.groups.WriteConf()
			LMC.users.WriteConf()
			LMC.profiles.WriteConf(LMC.configuration.profiles_config_file)
	def add_user(self, opts, args):
		""" Add a user account on the system. """

		assert ltrace('add', '> add_user(opts=%s, args=%s)' % (opts, args))

		if opts.profile:
			opts.profile = LMC.profiles.guess_identifier(opts.profile)

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
			if not LMC.groups.has_key(opts.primary_gid):
				opts.primary_gid = LMC.groups.name_to_gid(opts.primary_gid)

		# the else [ None ] is important for the unique case when called with only
		# --firstname and --lastname (login will be autogenerated).
		for login in opts.login.split(',') if opts.login != None else [ None ]:
			if login != '':
				try:
					LMC.users.AddUser(lastname=lastname, firstname=firstname,
						password=password, primary_gid=opts.primary_gid,
						desired_uid=opts.uid, profile=opts.profile, skel=opts.skel,
						login=login, gecos=gecos, system=opts.system,
						home=opts.home,	batch=False, force=opts.force,
						shell=opts.shell, in_groups=LMC.groups.guess_identifiers(
							opts.in_groups.split(',')) if opts.in_groups else [])
				except exceptions.AlreadyExistsException, e:
					logging.warning(str(e))
		assert ltrace('add', '< add_user()')
	def add_user_in_groups(self, opts, args):

		assert ltrace('add', '> add_user_in_group().')

		uids_to_add = self.select(LMC.users, 'user',
				args,
				[
					(opts.login, LMC.users.login_to_uid),
					(opts.uid, LMC.users.confirm_uid)
				],
				default_selection=filters.NONE)

		for g in opts.groups_to_add.split(','):
			if g != '':
				try:
					LMC.groups.AddUsersInGroup(name=g,
						users_to_add=uids_to_add)
				except exceptions.LicornRuntimeException, e:
					logging.warning("Unable to add user(s) %s in group %s (was: %s)."
						% (stylize(ST_LOGIN, opts.login),
						stylize(ST_NAME, g), str(e)))
				except exceptions.LicornException, e:
					raise exceptions.LicornRuntimeError(
						"Unable to add user(s) %s in group %s (was: %s)."
						% (stylize(ST_LOGIN, opts.login),
						stylize(ST_NAME, g), str(e)))

		assert ltrace('add', '< add_user_in_group().')
	def dispatch_add_user(self, opts, args):
		""" guess how we were called:
			- add a user (creation)
			- add a user into one or more group(s)
		"""

		assert ltrace('add', '> dispatch_add_user(%s, %s)' % (opts, args))

		if opts.login is None:
			if len(args) == 2:
				opts.login = args[1]
				args[1] = ''
				self.add_user(opts, args)
			elif len(args) == 3:
				opts.login = args[1]
				opts.groups_to_add = args[2]
				args[1] = ''
				args[2] = ''
				self.add_user_in_groups(opts, args)
			else:
				self.add_user(opts, args)
		else:
			self.add_user(opts, args)

		assert ltrace('add', '< dispatch_add_user()')
	def add_group(self, opts, args):
		""" Add a POSIX group. """

		assert ltrace('add', '> add_group().')

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		if opts.description:
			opts.description = unicode(opts.description)

		assert ltrace('add', 'group(s) to add: %s.' % opts.name)

		for name in opts.name.split(',')if opts.name != None else []:
			if name != '':
				try:
					assert ltrace('add', 'adding group %s.' % name)
					LMC.groups.AddGroup(name, description=opts.description,
						system=opts.system, groupSkel=opts.skel,
						desired_gid=opts.gid, permissive=opts.permissive,
						force=opts.force)
				except exceptions.AlreadyExistsException, e:
					logging.warning(str(e))

		assert ltrace('add', '< add_group().')
	def add_profile(self, opts, args):
		""" Add a system wide User profile. """

		assert ltrace('add', '> add_profile().')

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

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
				LMC.profiles.AddProfile(name, group=opts.group, profileQuota=opts.quota,
					groups=opts.groups, description=opts.description,
					profileShell=opts.shell, profileSkel=opts.skeldir,
					force_existing=opts.force_existing)
			except exceptions.AlreadyExistsException, e:
				logging.warning(str(e))

		assert ltrace('add', '< add_profile().')
	def add_keyword(self, opts, args):
		""" Add a keyword on the system. """

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		LMC.keywords.AddKeyword(unicode(opts.name), unicode(opts.parent),
			unicode(opts.description))
	def add_privilege(self, opts, args):

		if opts.privileges_to_add is None and len(args) == 2:
			opts.privileges_to_add = args[1]
			del args[1]

		include_priv_lists=[
			(opts.privileges_to_add, LMC.groups.guess_identifier),
		]

		privs_to_add = self.select(LMC.privileges, 'privilege', args=args,
				include_id_lists=include_priv_lists)

		LMC.privileges.add(privs_to_add)
	def add_machine(self, opts, args):

		if opts.auto_scan or opts.discover:
			LMC.machines.scan_network(
				network_to_scan=None if opts.auto_scan else [ opts.discover ])
	### DEL
	def desimport_groups(self, opts, args):
		""" Delete the groups (and theyr members) present in a import file.	"""

		if opts.filename is None:
			raise exceptions.BadArgumentError, "You must specify a file name"

		delete_file = file(opts.filename, 'r')

		groups_to_del = []

		user_re = re.compile("^\"?\w*\"?;\"?\w*\"?;\"?(?P<group>\w*)\"?$", re.UNICODE)
		for line in delete_file:
			mo = user_re.match(line)
			if mo is not None:
				u = mo.groupdict()
				g = u['group']
				if g not in groups_to_del:
					groups_to_del.append(g)

		delete_file.close()

		# Deleting
		length_groups = len(groups_to_del)
		quantity = length_groups
		if quantity <= 0:
			quantity = 1
		delta = 100.0 / float(quantity) # increment for progress indicator
		progression = 0.0
		i = 0 # to print i/length

		for g in groups_to_del:
			try:
				i += 1
				self.output("\rDeleting groups (%d/%d), progression: %.2f%%" % (
					i, length_groups, progression))
				LMC.groups.DeleteGroup(name=g, del_users=True, no_archive=True)
				progression += delta
				# FIXME: fush the listener??
				#sys.stdout.flush()
			except exceptions.LicornException, e:
				logging.warning(str(e))
		LMC.profiles.WriteConf(LMC.configuration.profiles_config_file)
		print "\nFinished"
	def del_user(self, opts, args):
		""" delete a user account. """
		include_id_lists=[
			(opts.login, LMC.users.login_to_uid),
			(opts.uid, LMC.users.confirm_uid)
		]
		exclude_id_lists=[
			(opts.exclude, LMC.users.guess_identifier),
			(opts.exclude_login, LMC.users.login_to_uid),
			(opts.exclude_uid, LMC.users.confirm_uid),
			([os.getuid()], LMC.users.confirm_uid)
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to delete all users?',
					auto_answer=opts.auto_answer) or not opts.non_interactive)):
				include_id_lists.extend([
					(LMC.users.Select(filters.STD), lambda x: x),
					(LMC.users.Select(filters.SYSUNRSTR), lambda x: x)
					])
		uids_to_del = self.select(LMC.users, 'user', args=args,
				include_id_lists=include_id_lists,
				exclude_id_lists=exclude_id_lists)

		for uid in uids_to_del:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair('''Delete user %s?''' % stylize(
				ST_LOGIN,LMC.users.uid_to_login(uid)),
				auto_answer=opts.auto_answer):
				LMC.users.DeleteUser(uid=uid, no_archive=opts.no_archive)
				#logging.notice("Deleting user : %s" % LMC.users.uid_to_login(uid))
	def del_user_from_groups(self, opts, args):

		uids_to_del = self.select(LMC.users, 'user',
				args,
				include_id_lists=[
					(opts.login, LMC.users.login_to_uid),
					(opts.uid, LMC.users.confirm_uid)
				])

		for g in opts.groups_to_del.split(','):
			if g != "":
				try:
					LMC.groups.DeleteUsersFromGroup(name=g, users_to_del=uids_to_del,
						batch=opts.batch)
				except exceptions.DoesntExistsException, e:
					logging.warning(
						"Unable to remove user(s) %s from group %s (was: %s)."
						% (stylize(ST_LOGIN, opts.login),
						stylize(ST_NAME, g), str(e)))
				except exceptions.LicornException, e:
					raise exceptions.LicornRuntimeError(
						"Unable to remove user(s) %s from group %s (was: %s)."
						% (stylize(ST_LOGIN, opts.login),
						stylize(ST_NAME, g), str(e)))
	def dispatch_del_user(self, opts, args):
		if opts.login is None:
			if len(args) == 2:
				opts.login = args[1]
				args[1] = ''
				self.del_user(opts, args)
			elif len(args) == 3:
				opts.login = args[1]
				opts.groups_to_del = args[2]
				args[1] = ''
				args[2] = ''
				self.del_user_from_groups(opts, args)
			else:
				self.del_user(opts, args)
		else:
			self.del_user(opts, args)
	def del_group(self, opts, args):
		""" delete an Licorn group. """
		selection = filters.NONE
		if opts.empty:
			selection = filters.EMPTY
		include_id_lists=[
			(opts.name, LMC.groups.name_to_gid),
			(opts.gid, LMC.groups.confirm_gid),
		]
		exclude_id_lists = [
			(opts.exclude, LMC.groups.guess_identifier),
			(opts.exclude_group, LMC.groups.name_to_gid),
			(opts.exclude_gid, LMC.groups.confirm_gid)
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to delete all groups?',
					auto_answer=opts.auto_answer) or not opts.non_interactive)):
				include_id_lists.extend([
					(LMC.groups.Select(filters.STD), lambda x: x),
					(LMC.groups.Select(filters.SYSUNRSTR), lambda x: x)
					])
		gids_to_del = self.select(LMC.groups, 'group',
					args,
					include_id_lists=include_id_lists,
					exclude_id_lists = exclude_id_lists,
					default_selection=selection)
		for gid in gids_to_del:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair('''Delete group %s?''' % stylize(
				ST_LOGIN,LMC.groups.gid_to_name(gid)),
				auto_answer=opts.auto_answer):
				LMC.groups.DeleteGroup(gid=gid, del_users=opts.del_users,
					no_archive=opts.no_archive)
				#logging.notice("Deleting group : %s" % LMC.groups.gid_to_name(gid))
	def del_profile(self, opts, args):
		""" Delete a system wide User profile. """
		include_id_lists=[
			(opts.name, LMC.profiles.name_to_group),
			(opts.group, LMC.profiles.confirm_group)
		]
		exclude_id_lists=[
			(opts.exclude, LMC.profiles.guess_identifier)
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to delete all profiles?',
					opts.auto_answer) \
				or not opts.non_interactive)
			):
				include_id_lists.extend([
						(LMC.profiles.Select(filters.ALL), lambda x: x)
					])

		profiles_to_del = self.select(LMC.profiles, 'profile', args,
				include_id_lists=include_id_lists,
				exclude_id_lists=exclude_id_lists)

		for p in profiles_to_del:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair('''Delete profile %s?''' %
					stylize(ST_LOGIN, LMC.profiles.group_to_name(p)),
					auto_answer=opts.auto_answer):
				LMC.profiles.DeleteProfile(group=p, del_users=opts.del_users,
					no_archive=opts.no_archive)
				#logging.notice("Deleting profile : %s" % LMC.profiles.group_to_name(p))
	def del_keyword(self, opts, args):
		""" delete a system wide User profile. """

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		LMC.keywords.DeleteKeyword(opts.name, opts.del_children)
	def del_privilege(self, opts, args):
		if opts.privileges_to_remove is None and len(args) == 2:
			opts.privileges_to_remove = args[1]
			del args[1]

		include_priv_lists=[
			(opts.privileges_to_remove, LMC.privileges.confirm_privilege),
		]
		exclude_priv_lists=[
			(opts.exclude, LMC.privileges.confirm_privilege),
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to delete all privileges?',
					auto_answer=opts.auto_answer) or not opts.non_interactive)):
				include_priv_lists.extend([
					(LMC.privileges.Select(filters.ALL), lambda x: x),
					])
		privs_to_del = self.select(LMC.privileges, 'privilege',args=args,
				include_id_lists=include_priv_lists,
				exclude_id_lists=exclude_priv_lists)

		for priv_name in privs_to_del:
			if priv_name is not None and (
			opts.non_interactive or opts.batch or opts.force or \
			logging.ask_for_repair('''Delete privilege %s?''' %
				stylize(ST_LOGIN, priv_name),
				auto_answer=opts.auto_answer)):
				LMC.privileges.delete(
					[priv_name])
	### MOD
	def mod_user(self, opts, args):
		""" Modify a POSIX user account (Samba / LDAP included). """

		import getpass

		include_id_lists=[
			(opts.login, LMC.users.login_to_uid),
			(opts.uid, LMC.users.confirm_uid)
			]
		exclude_id_lists=[
			(opts.exclude, LMC.users.guess_identifier),
			(opts.exclude_login, LMC.users.login_to_uid),
			(opts.exclude_uid, LMC.users.confirm_uid)
			]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to modify all users?',
					auto_answer=opts.auto_answer) \
				or not opts.non_interactive)
			):
				include_id_lists.extend([
					(LMC.users.Select(filters.STD), LMC.users.confirm_uid),
					(LMC.users.Select(filters.SYSUNRSTR), LMC.users.confirm_uid)
					])

		uids_to_mod = self.select(LMC.users, 'user',	args=args,
				include_id_lists=include_id_lists,
				exclude_id_lists=exclude_id_lists,
				default_selection='uid=%s' % LMC.users.login_to_uid(getpass.getuser()))

		assert ltrace('mod', '> mod_user(%s)' % uids_to_mod)

		something_done = False

		for uid in uids_to_mod:
			try:
				if opts.non_interactive or opts.batch or opts.force or \
					logging.ask_for_repair('''Modify user %s?''' % stylize(
					ST_LOGIN,LMC.users.uid_to_login(uid)),
					auto_answer=opts.auto_answer):

					if opts.newgecos is not None:
						something_done = True
						LMC.users.ChangeUserGecos(uid=uid, gecos=unicode(opts.newgecos))

					if opts.newshell is not None:
						something_done = True
						LMC.users.ChangeUserShell(uid=uid, shell=opts.newshell)

					if opts.newpassword is not None:
						something_done = True
						LMC.users.ChangeUserPassword(uid=uid, password=opts.newpassword)

					if opts.interactive_password:
						something_done = True

						login = LMC.users.uid_to_login(uid)
						message='Please enter new password for user %s: ' % \
							stylize(ST_NAME, login)
						confirm='Please confirm new password for user %s: ' % \
							stylize(ST_NAME, login)

						if getpass.getuser() != 'root':
							if getpass.getuser() == login:
								old_message = \
									'Please enter your OLD (current) password: '
								message='Please enter your new password: '
								confirm='Please confirm your new password: '

							else:
								old_message = \
									"Please enter %s's OLD (current) password: " % \
									stylize(ST_LOGIN, login)

							if not LMC.users.check_password(login,
								getpass.getpass(old_message)):
								raise exceptions.BadArgumentError(
									'wrong password, aborting.')

						password1 = getpass.getpass(message)
						password2 = getpass.getpass(confirm)

						if password1 == password2:
							LMC.users.ChangeUserPassword(uid=uid, password=password1)
						else:
							raise exceptions.BadArgumentError(
								'passwords do not match, sorry. Unchanged!')

					if opts.auto_passwd:
						something_done = True
						LMC.users.ChangeUserPassword(uid=uid,
							password=hlstr.generate_password(opts.passwd_size),
							display=True)

					if opts.lock is not None:
						something_done = True
						LMC.users.LockAccount(uid=uid, lock=opts.lock)

					if opts.groups_to_add:
						something_done = True
						for g in opts.groups_to_add.split(','):
							if g != '':
								try:
									LMC.groups.AddUsersInGroup(name=g, users_to_add=[ uid ])
								except exceptions.LicornRuntimeException, e:
									logging.warning(
										'''Unable to add user %s in group %s (was: '''
										'''%s).''' % (
											stylize(ST_LOGIN,
												LMC.users.uid_to_login(uid)),
											stylize(ST_NAME, g), str(e)), )
								except exceptions.LicornException, e:
									raise exceptions.LicornRuntimeError(
										'''Unable to add user %s in group %s (was: '''
										'''%s).'''
											% (stylize(ST_LOGIN,
												LMC.users.uid_to_login(uid)),
												stylize(ST_NAME, g),
												str(e)))

					if opts.groups_to_del:
						something_done = True
						for g in opts.groups_to_del.split(','):
							if g != '':
								try:
									LMC.groups.DeleteUsersFromGroup(name=g,
										users_to_del=[ uid ])
								except exceptions.LicornRuntimeException, e:
									logging.warning('''Unable to remove user %s from '''
										'''group %s (was: %s).''' % (
											stylize(ST_LOGIN, opts.login),
											stylize(ST_NAME, g),
											str(e)))
								except exceptions.LicornException, e:
									raise exceptions.LicornRuntimeError(
										'''Unable to remove user %s from '''
										'''group %s (was: %s).''' % (
											stylize(ST_LOGIN, opts.login),
											stylize(ST_NAME, g),
											str(e)))

					if opts.apply_skel is not None:
						something_done = True
						LMC.users.ApplyUserSkel(opts.login, opts.apply_skel)

			except exceptions.BadArgumentError, e:
				logging.warning(e)

		if not something_done:
			raise exceptions.BadArgumentError('''What do you want to modify '''
				'''about user(s)? Use --help to know!''')
	def mod_group(self, opts, args):
		""" Modify a group. """
		include_id_lists=[
			(opts.name, LMC.groups.name_to_gid),
			(opts.gid, LMC.groups.confirm_gid)
		]
		exclude_id_lists = [
			(opts.exclude, LMC.groups.guess_identifier),
			(opts.exclude_group, LMC.groups.name_to_gid),
			(opts.exclude_gid, LMC.groups.confirm_gid)
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to modify all groups?',
					auto_answer=opts.auto_answer) or not opts.non_interactive)
			):
					include_id_lists.extend([
						(LMC.groups.Select(filters.STD), lambda x: x),
						(LMC.groups.Select(filters.SYSUNRSTR), lambda x: x)
					])
		gids_to_mod = self.select(LMC.groups, 'group', args,
				include_id_lists=include_id_lists,
				exclude_id_lists=exclude_id_lists)

		assert ltrace('mod', '> mod_group(%s)' % gids_to_mod)

		g2n = LMC.groups.gid_to_name

		for gid in gids_to_mod:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair('''Modify group %s?''' % stylize(
				ST_LOGIN,g2n(gid)),auto_answer=opts.auto_answer):

				if opts.permissive is not None:
					LMC.groups.SetSharedDirPermissiveness(gid=gid,
						permissive=opts.permissive)

				if opts.newname is not None:
					LMC.groups.RenameGroup(gid=gid, newname=opts.newname)

				if opts.newskel is not None:
					LMC.groups.ChangeGroupSkel(gid=gid, groupSkel=opts.newskel)

				if opts.newdescription is not None:
					LMC.groups.ChangeGroupDescription(gid=gid,
						description=unicode(opts.newdescription))

				if opts.users_to_add != []:
					LMC.groups.AddUsersInGroup(gid=gid,
						users_to_add=opts.users_to_add.split(','))

				if opts.users_to_del != []:
					LMC.groups.DeleteUsersFromGroup(gid=gid,
						users_to_del=opts.users_to_del.split(','))

				if opts.resps_to_add != []:
					LMC.groups.AddUsersInGroup(
						name=LMC.configuration.groups.resp_prefix + g2n(gid),
						users_to_add=opts.resps_to_add.split(','))

				if opts.resps_to_del != []:
					LMC.groups.DeleteUsersFromGroup(
						name=LMC.configuration.groups.resp_prefix + g2n(gid),
						users_to_del=opts.resps_to_del.split(','))

				if opts.guests_to_add != []:
					LMC.groups.AddUsersInGroup(
						name=LMC.configuration.groups.guest_prefix + g2n(gid),
						users_to_add=opts.guests_to_add.split(','))

				if opts.guests_to_del != []:
					LMC.groups.DeleteUsersFromGroup(
						name=LMC.configuration.groups.guest_prefix + g2n(gid),
						users_to_del=opts.guests_to_del.split(','))

				# FIXME: do the same for guests,  or make resp-guest simply
				# --add-groups resp-…,group1,group2,guest-…

				if opts.granted_profiles_to_add is not None:
					LMC.groups.AddGrantedProfiles(gid=gid,
						profiles=opts.granted_profiles_to_add.split(','))
				if opts.granted_profiles_to_del is not None:
					LMC.groups.DeleteGrantedProfiles(gid=gid,
						profiles=opts.granted_profiles_to_del.split(','))
	def mod_profile(self, opts, args):
		""" Modify a system wide User profile. """
		include_id_lists=[
			(opts.name, LMC.profiles.name_to_group),
			(opts.group, LMC.profiles.confirm_group)
		]
		exclude_id_lists=[
			(opts.exclude, LMC.profiles.guess_identifier),
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to modify all profiles?',
					opts.auto_answer) \
				or not opts.non_interactive)
			):
				include_id_lists.extend([
					(LMC.profiles.Select(filters.ALL), lambda x: x)
				]),
		profiles_to_mod = self.select(LMC.profiles, 'profile', args,
				include_id_lists=include_id_lists,
				exclude_id_lists=exclude_id_lists)

		assert ltrace('mod', '> mod_profile(%s)' % profiles_to_mod)

		ggi = LMC.groups.guess_identifiers

		for group in profiles_to_mod:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair('''Modify profile %s?''' % stylize(
				ST_LOGIN, LMC.profiles.group_to_name(group)),
				auto_answer=opts.auto_answer):

				if opts.newname is not None:
					LMC.profiles.ChangeProfileName(group=group,
						newname=unicode(opts.newname))

				if opts.newgroup is not None:
					LMC.profiles.ChangeProfileGroup(group=group, newgroup=opts.newgroup)

				if opts.description is not None:
					LMC.profiles.ChangeProfileDescription(group=group,
						description=unicode(opts.description))

				if opts.newshell is not None:
					LMC.profiles.ChangeProfileShell(group=group,
						profileShell=opts.newshell)

				if opts.newskel is not None:
					LMC.profiles.ChangeProfileSkel(group=group,
					profileSkel=opts.newskel)

				if opts.newquota is not None:
					LMC.profiles.ChangeProfileQuota(group=group,
					profileQuota=opts.newquota)

				if opts.groups_to_add is not None:
					added_groups = LMC.profiles.AddGroupsInProfile(group=group,
						groups_to_add=opts.groups_to_add.split(','))
					if opts.instant_apply:
						prim_memb = LMC.groups.primary_members(name=group)
						for added_group in added_groups:
							LMC.groups.AddUsersInGroup(name=added_group,
								users_to_add=prim_memb,	batch=opts.no_sync)

				if opts.groups_to_del is not None:
					deleted_groups = LMC.profiles.DeleteGroupsFromProfile(group=group,
						groups_to_del=opts.groups_to_del.split(','))
					if opts.instant_apply:
						prim_memb = LMC.groups.primary_members(name=group)
						for deleted_group in deleted_groups:
							LMC.groups.DeleteUsersFromGroup(name=deleted_group,
								users_to_del=prim_memb,	batch=opts.no_sync)

				if opts.no_sync:
					LMC.groups.WriteConf()

				include_id_lists = []

				if opts.apply_to_members:
					include_id_lists.append(
						(LMC.groups.primary_members(name=group), LMC.users.login_to_uid))
				if opts.apply_to_users is not None:
					include_id_lists.append(
						(opts.apply_to_users.split(','), LMC.users.guess_identifier))
				if opts.apply_to_groups is not None:
					for gid in ggi(opts.apply_to_groups.split(',')):
						include_id_lists.append(
							(LMC.groups.primary_members(gid=gid), LMC.users.login_to_uid))

				if opts.apply_all_attributes or opts.apply_skel or opts.apply_groups:

					_users = LMC.users.Select(
						self.select(LMC.users, 'user',
							args,
							include_id_lists=include_id_lists,
							exclude_id_lists=[
								(opts.exclude, LMC.users.guess_identifier),
								(opts.exclude_login, LMC.users.login_to_uid),
								(opts.exclude_uid, LMC.users.confirm_uid)
							],
							default_selection=filters.NONE,
							all=opts.apply_to_all_accounts)
						)

					assert ltrace('mod',"  mod_profile(on_users=%s)" % _users)

					if _users != []:
						LMC.profiles.ReapplyProfileOfUsers(_users,
							apply_groups=opts.apply_groups,
							apply_skel=opts.apply_skel,
							batch=opts.batch, auto_answer=opts.auto_answer)
		assert ltrace('mod', '< mod_profile()')
	def mod_machine(self, opts, args):
		""" Modify a machine. """

		if opts.all:
			selection = host_status.IDLE | host_status.ASLEEP | host_status.ACTIVE
		else:
			selection = filters.NONE

			if opts.idle:
				selection |= host_status.IDLE

			if opts.asleep:
				selection |= host_status.ASLEEP

			if opts.active:
				selection |= host_status.ACTIVE

		mids_to_mod = self.select(LMC.machines, 'machine',
				args,
				[
					(opts.hostname, LMC.machines.by_hostname),
					(opts.mid, LMC.machines.has_key)
				],
				default_selection=selection)

		for machine in mids_to_mod:
			if opts.shutdown:
				machine.shutdown(warn_users=opts.warn_users)
	def mod_keyword(self, opts, args):
		""" Modify a keyword. """

		if len(args) == 2:
			opts.name = args[1]
			del args[1]

		if opts.newname is not None:
			LMC.keywords.RenameKeyword(opts.name, opts.newname)
		if opts.parent is not None:
			LMC.keywords.ChangeParent(opts.name, opts.parent)
		elif opts.remove_parent:
			LMC.keywords.RemoveParent(opts.name)
		if opts.description is not None:
			LMC.keywords.ChangeDescription(opts.name, opts.description)
	def mod_path(self, opts, args):
		""" Manage keywords of a file or directory. """

		raise NotImplementedError('not yet anymore.')

		if len(args) == 2:
			opts.path = args[1]
			del args[1]

		# this should go directly into system.keywords.
		from licorn.harvester import HarvestClient
		hc = HarvestClient()
		hc.UpdateRequest(opts.path)
		return

		if opts.clear_keywords:
			LMC.keywords.ClearKeywords(opts.path, opts.recursive)
		else:
			if opts.keywords_to_del is not None:
				LMC.keywords.DeleteKeywordsFromPath(opts.path, opts.keywords_to_del.split(','), opts.recursive)
			if opts.keywords_to_add is not None:
				LMC.keywords.AddKeywordsToPath(opts.path, opts.keywords_to_add.split(','), opts.recursive)
	def mod_configuration(self, opts, args):
		""" Modify some aspects or abstract directives of the system configuration
			(use with caution)."""

		if opts.setup_shared_dirs:
			LMC.configuration.check_base_dirs(minimal=False, batch=True)

		elif opts.set_hostname:
			LMC.configuration.ModifyHostname(opts.set_hostname)

		elif opts.set_ip_address:
			raise exceptions.NotImplementedError(
				"changing server IP address is not yet implemented.")

		elif opts.privileges_to_add:
			LMC.privileges.add(opts.privileges_to_add.split(','))

		elif opts.privileges_to_remove:
			LMC.privileges.delete(opts.privileges_to_remove.split(','))

		elif opts.hidden_groups != None:
			LMC.configuration.SetHiddenGroups(opts.hidden_groups)

		elif opts.disable_backends != None:
			for backend in opts.disable_backends.split(','):
				LMC.backends.disable_backend(backend)

		elif opts.enable_backends != None:
			for backend in opts.enable_backends.split(','):
				LMC.backends.enable_backend(backend)

		else:
			raise exceptions.BadArgumentError(
				"what do you want to modify? use --help to know!")
	### CHK
	def chk_user(self, opts, args):
		""" Check one or more user account(s). """
		include_id_lists=[
			(opts.login, LMC.users.login_to_uid),
			(opts.uid, LMC.users.confirm_uid)
		]
		exclude_id_lists=[
			(opts.exclude, LMC.users.guess_identifier),
			(opts.exclude_login, LMC.users.login_to_uid),
			(opts.exclude_uid, LMC.users.confirm_uid)
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
					opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to check all users?',
					auto_answer=opts.auto_answer) or not opts.non_interactive)
			):
				include_id_lists.extend([
					(LMC.users.Select(filters.STD), lambda x: x),
					(LMC.users.Select(filters.SYSUNRSTR), lambda x: x)
					])
		uids_to_chk = self.select(LMC.users, 'user', args,
			include_id_lists=include_id_lists,
			exclude_id_lists=exclude_id_lists)

		assert ltrace('chk', '> chk_user(%s)' % uids_to_chk)

		if uids_to_chk != []:
			if opts.force or opts.batch or opts.non_interactive:
				LMC.users.CheckUsers(uids_to_chk, minimal=opts.minimal,
					auto_answer=opts.auto_answer, batch=opts.batch)
			else:
				for uid in uids_to_chk:
					if logging.ask_for_repair('''Check user %s?''' %
						stylize(ST_LOGIN, LMC.users.uid_to_login(uid)),
						auto_answer=opts.auto_answer):
						LMC.users.CheckUsers([uid], minimal=opts.minimal,
							auto_answer=opts.auto_answer, batch=opts.batch)
		assert ltrace('chk', '< chk_user()')
	def chk_group(self, opts, args):
		""" Check one or more group(s). """
		include_id_lists=[
			(opts.name, LMC.groups.name_to_gid),
			(opts.gid, LMC.groups.confirm_gid)
		]
		exclude_id_lists = [
			(opts.exclude, LMC.groups.guess_identifier),
			(opts.exclude_group, LMC.groups.name_to_gid),
			(opts.exclude_gid, LMC.groups.confirm_gid)
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
					opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to check all groups?',
					auto_answer=opts.auto_answer) or not opts.non_interactive)
			):
				include_id_lists.extend([
					(LMC.groups.Select(filters.STD), lambda x: x),
					(LMC.groups.Select(filters.SYSUNRSTR), lambda x: x)
					])
		gids_to_chk = self.select(LMC.groups, 'group', args,
			include_id_lists=include_id_lists,
			exclude_id_lists=exclude_id_lists,
			default_selection=filters.STD,
			all=opts.all)

		assert ltrace('chk', '> chk_group(%s)' % gids_to_chk)

		if gids_to_chk != []:
			if opts.force or opts.batch or opts.non_interactive:
				LMC.groups.CheckGroups(gids_to_check=gids_to_chk,
					minimal=opts.minimal, batch=opts.batch,
					auto_answer=opts.auto_answer, force=opts.force)
			else:
				for gid in gids_to_chk:
					if logging.ask_for_repair('''Check group %s?''' %
						stylize(ST_LOGIN, LMC.groups.gid_to_name(gid)),
						auto_answer=opts.auto_answer):
						LMC.groups.CheckGroups(gids_to_check=[gid],
							minimal=opts.minimal, batch=opts.batch,
							auto_answer=opts.auto_answer, force=opts.force)
		assert ltrace('chk', '< chk_group()')
	def chk_profile(self, opts, args):
		""" TODO: to be implemented. """
		include_id_lists=[
			(opts.name, LMC.profiles.name_to_group),
			(opts.group, LMC.profiles.confirm_group)
		]
		exclude_id_lists=[
			(opts.exclude, LMC.profiles.guess_identifier)
		]
		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
				or (opts.non_interactive and logging.ask_for_repair(
					'Are you sure you want to delete all profiles?',
					opts.auto_answer) \
				or not opts.non_interactive)
			):
				include_id_lists.extend([
						(LMC.profiles.Select(filters.ALL), lambda x: x)
					])

		profiles_to_del = self.select(LMC.profiles, 'profile', args,
				include_id_lists=include_id_lists,
				exclude_id_lists=exclude_id_lists)

		for p in profiles_to_del:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair('''Delete profile %s?''' % stylize(
				ST_LOGIN,LMC.profiles.group_to_name(p)),
				auto_answer=opts.auto_answer):
				raise NotImplementedError("Sorry, not yet.")
	def chk_configuration(self, opts, args):
		""" TODO: to be implemented. """

		LMC.configuration.check(opts.minimal, batch=opts.batch,
			auto_answer=opts.auto_answer)
