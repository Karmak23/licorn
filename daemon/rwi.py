# -*- coding: utf-8 -*-
"""
Licorn Daemon Real World Interface.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Partial Copyright (C) 2010 Robin Lucbernet <robinlucbernet@gmail.com>
Licensed under the terms of the GNU GPL version 2.
"""
import os, uuid, Pyro.core, time, gc, __builtin__

from operator  import attrgetter
from threading import current_thread, RLock

from licorn.foundations           import options, exceptions, logging
from licorn.foundations           import fsapi, hlstr
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import NamedObject, pyro_protected_attrs
from licorn.foundations.messaging import LicornMessage, ListenerObject
from licorn.foundations.constants import filters, interactions, host_status

from licorn.core import LMC

class RealWorldInterface(NamedObject, ListenerObject, Pyro.core.ObjBase):
	""" Receive requests from "outside" programs and objects (typically CLI and
		WMI), and forward them to internal core controllers after having done
		preparsing and checks. """
	_licorn_protected_attrs = (
			NamedObject._licorn_protected_attrs
			+ pyro_protected_attrs
		)
	def __init__(self, licornd):
		NamedObject.__init__(self, name='rwi')
		Pyro.core.ObjBase.__init__(self)
		self.__licornd = licornd
		assert ltrace(TRACE_RWI, '| RWIController.__init__()')
	@property
	def licornd(self):
		return self.__licornd
	def __setup_gettext(self):
		th = current_thread()

		#print '>> gettext setup', th.listener, th.listener.lang

		try:
			th._ = self.__licornd.langs[th.listener.lang].ugettext
			#print '>> switched to', th.listener.lang
		except KeyError:
			# the daemon doesn't have the client lang installed. Not a problem.
			# Still, make a shortcut to the daemon's default translator to
			# avoid trigerring an exception at every call of our translator
			# wrapper.
			th._ = __builtin__.__dict__['_orig__']
	def output(self, text_message, clear_terminal=False):
		""" Output a text message remotely, in CLI caller process, whose
			reference is stored in :obj:`current_thread().listener`. """
		return current_thread().listener.process(
			LicornMessage(data=text_message, channel=1,
							clear_terminal=clear_terminal),
			options.msgproc.getProxy())
	def interact(self, text_message, interaction):
		""" Send a bi-directionnal message remotely, in CLI caller process,
			whose reference is stored in :obj:`current_thread().listener`.
		"""
		return current_thread().listener.process(
			LicornMessage(data=text_message, interaction=interaction),
			options.msgproc.getProxy())
	def prefered_groups_backend_name(self):
		""" comfort method, to forward prefered groups backend, used in CLI
			argparser.
		"""
		return LMC.groups._prefered_backend.name
	def groups_backends_names(self):
		""" comfort method to get only the names of current enabled backends,
			used in CLI argparser.
		"""

		# NOTE: don't try to turn this into a generator with (), it is meant
		# to be used via Pyro and thus must be pickled: it stays a LIST.
		return [ x.name for x in LMC.groups.backends ]
	def backends_names(self):
		""" comfort method to get only the names of current enabled backends,
			used in CLI argparser.
		"""
		# NOTE: no (generator) for pyro methods...
		return [ x.name for x in LMC.backends ]
	def select(self, controller, args=None, opts=None, include_id_lists=None,
		exclude_id_lists=None, default_selection=filters.NONE, all=False):

		assert ltrace(TRACE_CLI, '''> select(controller=%s, args=%s, '''
			'''include_id_lists=%s, exclude_id_lists=%s, default_selection=%s, '''
			'''all=%s)''' % (controller.name, args, include_id_lists,
				exclude_id_lists, default_selection, all))

		# use a set() to avoid duplicates during selections. This will allow us,
		# later in implementation to do more complex selections (unions,
		# differences, intersections and al.

		if include_id_lists is None:
			include_id_lists = ()

		if exclude_id_lists is None:
			exclude_id_lists = ()

		if args is None:
			args = ()

		xids = set()
		if all:
			# if --all: manually included IDs (with --login, --group, --uid, --gid)
			# will be totally discarded (--all gets precedence). But excluded items
			# will still be excluded, to allow "--all --exclude-login toto"
			# semi-complex selections.
			ids = set(controller)
		else:
			ids = set()

			something_tried = False

			if len(args) > 1:
				for arg in args[1:]:
					if arg == '':
						continue

					include_id_lists.append((arg, controller.guess_one))

			if hasattr(opts, 'word_match'):
				for arg in opts.word_match.split(','):
					if arg == '':
						continue

					include_id_lists.append((controller.word_match(arg), controller.guess_one))

			# select included IDs
			for id_arg, resolver in include_id_lists:
				if id_arg is None:
					continue

				for oid in id_arg.split(',') if hasattr(id_arg, 'split') else id_arg:
					if oid is '':
						continue

					try:
						something_tried = True
						ids.add(resolver(oid))
						#assert ltrace(TRACE_CLI, '  select %s(%s) -> %s' %
						#	(str(resolver), oid, resolver(oid)))

					except (KeyError, ValueError, exceptions.DoesntExistException):
						logging.notice(_(u'Skipped non existing or invalid '
							'{0} or {1} "{2}".').format(
								controller.object_type_str,
								controller.object_id_str,
								stylize(ST_NAME, oid)), to_local=False)
						continue

		# select excluded IDs, to remove them from included ones

		if hasattr(opts, 'exclude_word_match'):
			for arg in opts.exclude_word_match.split(','):
				if arg == '':
					continue

				exclude_id_lists.append((controller.word_match(arg), controller.guess_one))

		for id_arg, resolver in exclude_id_lists:
			if id_arg is None:
				continue

			for oid in id_arg.split(',') if hasattr(id_arg, 'split') else id_arg:
				if oid is '':
					continue
				try:
					xids.add(resolver(oid))
				except (KeyError, ValueError, exceptions.DoesntExistException):
					logging.notice(_(u'Skipped non existing or invalid {0} or '
						'{1} "{2}".').format(
							controller.object_type_str,
							controller.object_id_str,
							stylize(ST_NAME, oid)), to_local=False)
					continue

		# now return included IDs, minux excluded IDs, in different conditions.
		if ids != set():
			selection = list(ids.difference(xids))
		else:
			if something_tried:
				selection = []
			else:
				if default_selection is filters.NONE:
					logging.warning(_(u'You must specify at least one %s!')
												% controller.object_type_str,
									to_local=False)
					selection = []
				else:
					selection = list(set(
						controller.select(default_selection)).difference(xids))

		assert ltrace(TRACE_CLI, '< select(return=%s)' % selection)
		return sorted(selection, key=attrgetter(controller.sort_key))
	### GET
	def get_volumes(self, opts, args):

		self.__setup_gettext()

		self.output(LMC.extensions.volumes.get_CLI(opts, args))
	def get_users(self, opts, args):
		""" Get the list of POSIX user accounts (Samba / LDAP included). """

		self.__setup_gettext()

		if opts.dump:
			self.output(LMC.users.dump())
			return

		assert ltrace(TRACE_GET, '> get_users(%s,%s)' % (opts, args))

		selection = filters.SYSUNRSTR | filters.STANDARD

		if opts.system:
			selection = filters.SYSTEM

		elif opts.not_system:
			selection = filters.NOT_SYSTEM

		users_to_get = self.select(LMC.users, args, opts,
					include_id_lists = [
						(opts.login, LMC.users.by_login),
						(opts.uid, LMC.users.by_uid)
					],
					exclude_id_lists = [
						(opts.exclude, LMC.users.guess_one),
						(opts.exclude_login, LMC.users.by_login),
						(opts.exclude_uid, LMC.users.by_uid)
					],
					default_selection = selection,
					all=opts.all)

		if opts.xml:
			data = LMC.users.to_XML(selected=users_to_get,
										long_output=opts.long_output)
		else:
			data = LMC.users._cli_get(selected=users_to_get,
										long_output=opts.long_output)

		if data and data != '\n':
			self.output(data)

		assert ltrace(TRACE_GET, '< get_users()')
	def get_groups(self, opts, args):
		""" Get the list of POSIX LMC.groups (can be LDAP). """

		self.__setup_gettext()

		if opts.dump:
			self.output(LMC.groups.dump())
			return

		assert ltrace(TRACE_GET, '> get_groups(%s,%s)' % (opts, args))

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

		groups_to_get = self.select(LMC.groups,	args, opts,
				include_id_lists = [
					(opts.name, LMC.groups.by_name),
					(opts.gid, LMC.groups.by_gid)
				],
				exclude_id_lists = [
					(opts.exclude, LMC.groups.guess_one),
					(opts.exclude_group, LMC.groups.by_name),
					(opts.exclude_gid, LMC.groups.by_gid)
				],
				default_selection=selection,
				all=opts.all)

		if opts.xml:
			data = LMC.groups.to_XML(selected=groups_to_get,
										long_output=opts.long_output)
		else:
			data = LMC.groups._cli_get(selected=groups_to_get,
										long_output=opts.long_output,
										no_colors=opts.no_colors)

		if data and data != '\n':
			self.output(data)

		assert ltrace(TRACE_GET, '< get_groups()')
	def get_profiles(self, opts, args):
		""" Get the list of user profiles. """

		self.__setup_gettext()

		assert ltrace(TRACE_GET, '> get_profiles(%s,%s)' % (opts, args))

		profiles_to_get = self.select(LMC.profiles, args, opts,
				include_id_lists = [
					(opts.name, LMC.profiles.by_name),
					(opts.group, LMC.profiles.by_group)
				],
				default_selection=filters.ALL)

		if opts.xml:
			data = LMC.profiles.to_XML(profiles_to_get)
		else:
			data = LMC.profiles._cli_get(profiles_to_get)

		if data and data != '\n':
			self.output(data)

		assert ltrace(TRACE_GET, '< get_profiles()')
	def get_keywords(self, opts, args):
		""" Get the list of keywords. """

		self.__setup_gettext()

		assert ltrace(TRACE_GET, '> get_keywords(%s,%s)' % (opts, args))

		if opts.xml:
			data = LMC.keywords.ExportXML()
		else:
			data = LMC.keywords.Export()

		if data and data != '\n':
			self.output(data)

		assert ltrace(TRACE_GET, '< get_keywords()')
	def get_privileges(self, opts, args):
		""" Return the current privileges whitelist, one priv by line. """

		self.__setup_gettext()

		assert ltrace(TRACE_GET, '> get_privileges(%s,%s)' % (opts, args))

		if opts.xml:
			data = LMC.privileges.ExportXML()
		else:
			data = LMC.privileges.ExportCLI()

		self.output(data)

		assert ltrace(TRACE_GET, '< get_privileges()')
	def get_machines(self, opts, args):
		""" Get the list of machines known from the server (attached or not). """

		self.__setup_gettext()

		if opts.dump:
			self.output(LMC.machines.dump())
			return

		assert ltrace(TRACE_GET, '> get_machines(%s,%s)' % (opts, args))

		if opts.all:
			selection = host_status.ALL
		else:
			selection = host_status.ONLINE

			if opts.unknown:
				selection |= host_status.UNKNOWN

			if opts.offline:
				selection |= host_status.OFFLINE

			if opts.going_to_sleep:
				selection |= host_status.GOING_TO_SLEEP

			if opts.asleep:
				selection |= host_status.ASLEEP

			if opts.online:
				selection |= host_status.ONLINE

			if opts.booting:
				selection |= host_status.BOOTING

			if opts.idle:
				selection |= host_status.IDLE

			if opts.active:
				selection |= host_status.ACTIVE

			if opts.loaded:
				selection |= host_status.LOADED

		# FIXME: implement inclusions / exclusions (#375)

		if opts.mid is not None:
			try:
				machines_to_get = LMC.machines.select("mid=" + unicode(opts.mid))
			except KeyError:
				logging.error("No matching machine found.", to_local=False)
				return
		else:
			machines_to_get = LMC.machines.select(selection, return_ids=True)

		if opts.xml:
			data = LMC.machines.ExportXML(selected=machines_to_get,
											long_output=opts.long_output)
		else:
			data = LMC.machines.ExportCLI(selected=machines_to_get,
											long_output=opts.long_output)

		if data and data != '\n':
			self.output(data)

		assert ltrace(TRACE_GET, '< get_machines()')
	def get_configuration(self, opts, args):
		""" Output th current Licorn system configuration. """

		self.__setup_gettext()

		assert ltrace(TRACE_GET, '> get_configuration(%s,%s)' % (opts, args))

		if len(args) > 1:
			self.output(LMC.configuration.Export(args=args[1:],
						cli_format=opts.cli_format))
		else:
			self.output(LMC.configuration.Export())

		assert ltrace(TRACE_GET, '< get_configuration()')
	def get_daemon_status(self, opts, args):

		self.__setup_gettext()

		self.output(self.licornd.dump_status(opts.long_output, opts.precision),
								clear_terminal=opts.monitor_clear)
	def register_monitor(self, facilities):
		t = current_thread()
		t.monitor_facilities = ltrace_str_to_int(facilities)

		t.monitor_uuid = uuid.uuid4()

		logging.notice(_(u'New trace session started with UUID {0}, '
			u'facilities {1}.').format(stylize(ST_UGID, t.monitor_uuid),
				stylize(ST_COMMENT, facilities)))

		# The monitor_lock avoids collisions on listener.verbose
		# modifications while a flood of messages are beiing sent
		# on the wire. Having a per-thread lock avoids locking
		# the master `options.monitor_lock` from the client side
		# when only one monitor changes its verbose level. This
		# is more fine grained.
		t.monitor_lock = RLock()

		with options.monitor_lock:
			options.monitor_listeners.append(t)

		# return the UUID of the thread, so that the remote side
		# can detach easily when it terminates.
		return t.monitor_uuid
	def unregister_monitor(self, muuid):

		found = None

		with options.monitor_lock:
			for t in options.monitor_listeners[:]:
				if t.monitor_uuid == muuid:
					found = t
					options.monitor_listeners.remove(t)
					break

		if found:
			del t.monitor_facilities
			del t.monitor_uuid
			del t.monitor_lock

		else:
			logging.warning(_(u'Monitor listener with UUID %s not found!') % muuid)

		logging.notice(_(u'Trace session UUID {0} ended.').format(
													stylize(ST_UGID, muuid)))
	def get_webfilters(self, opts, args):
		""" Get the list of webfilter databases and entries.
			This function wraps SquidGuard configuration files.
		"""

		self.__setup_gettext()

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

		# already done in dispatch_*
		#self.__setup_gettext()

		assert ltrace(TRACE_ADD, '> import_user(%s,%s)' % (opts, args))

		def clean_csv_field(field):
			return field.replace("'", "").replace('"', '')

		if opts.filename is None:
			raise exceptions.BadArgumentError(
									_(u'You must specify an import filename.'))
		else:
			import_filename = opts.filename

		if opts.profile is None:
			raise exceptions.BadArgumentError(_(u'You must specify a profile.'))
		else:
			profile = opts.profile

		if opts.firstname_col is None:
			raise exceptions.BadArgumentError(
							_(u'You must specify a firstname column number.'))
		else:
			firstname_col = opts.firstname_col

		if opts.lastname_col is None:
			raise exceptions.BadArgumentError(
							_(u'You must specify a lastname column number.'))
		else:
			lastname_col = opts.lastname_col

		if opts.group_col is None:
			raise exceptions.BadArgumentError(
								_(u'You must specify a group column number.'))
		else:
			group_col = opts.group_col

		if (firstname_col == lastname_col
			or firstname_col == group_col
			or lastname_col == group_col):
			raise exceptions.BadArgumentError(_(u'Two columns have the same '
				'number (lastname={0}, firstname={1}, group={2})').format(
				lastname_col, firstname_col, group_col))

		maxval = 0
		for number in (lastname_col, firstname_col, group_col):
			maxval = max(maxval, number)

		if maxval > 127:
			raise exceptions.BadArgumentError(_(u'Sorry, CSV file must have '
				'no more than 128 columns."'))

		# WARNING:
		# we can't do any checks on login_col and password_col, because
		# the admin can choose the firstname as password, the firstname as login
		# the group as password (in elementary schools, children can't remember
		# complicated "real" password) and so on. The columns number can totally
		# overlap and this beiing intentionnal.

		encoding = fsapi.get_file_encoding(import_filename)
		if encoding is None:
			# what to choose? ascii or ~sys.getsystemencoding()?
			logging.warning(_(u'Cannot automatically detect the file '
				'encoding, assuming iso-8859-15 (latin-1)!'), to_local=False)
			encoding = 'iso-8859-15'

		try:
			profile = self.select(LMC.profiles,
				include_id_lists=[ (profile, LMC.profiles.guess_one) ])[0]
		except KeyError:
			raise exceptions.LicornRuntimeException(_(u'The profile "%s" does '
				'not exist.') % stylize(ST_NAME, profile))

		import math, csv
		from licorn.core.users  import User
		from licorn.core.groups import Group


		firstline  = open(import_filename).readline()
		lcndialect = csv.Sniffer().sniff(firstline)

		if lcndialect.delimiter != opts.separator:
			separator = lcndialect.delimiter
		else:
			separator = opts.separator

		try:
			import_fd = open(import_filename, 'rb')
		except (OSError, IOError), e:
			raise exceptions.LicornRuntimeError(_(u'Cannot load CSV file '
				'(was: %s).') % str(e))

		groups_to_add = []
		users_to_add  = []

		self.output(_(u'Reading input file: '))

		i = 0
		for fdline in import_fd:

			line = fdline[:-1].split(separator)
			#print(str(line))

			user = {}
			for (column, number) in (
					('firstname', firstname_col),
					('lastname', lastname_col),
					('group', group_col),
					('login', opts.login_col),
					('password', opts.password_col)
				):

				try:
					if number is None:
						user[column] = None
					else:
						if column == 'password' and number in (
												lastname_col, firstname_col):
							# FIXME: decide wether to kill this code or not:
							# for small children, make the password as simple
							# as the login to type. tell validate_name() to be
							# aggressive to achieve this.
							user[column] = hlstr.validate_name(
										unicode(line[number], encoding), True)
						else:
							user[column] = unicode(
									clean_csv_field(line[number]), encoding)

				except IndexError, e:
					raise exceptions.LicornRuntimeError('\n'+_(u'Import error '
						'on line {0}: no {1} specified or bad {2} data '
						'(was: {3}).').format(i + 1, column, translation, e))

				except UnicodeEncodeError, e:
					raise exceptions.LicornRuntimeError('\n'+_(u'Encoding not '
						'supported for input filename (was: %s).') % str(e))
			try:
				if opts.login_col is None:
					user['login'] = User.make_login(
										firstname=user['firstname'],
										lastname=user['lastname'])
				else:
					user['login'] =	User.make_login(
										inputlogin=user['login'])
			except IndexError, e:
				raise exceptions.LicornRuntimeError('\n' + _(u'Import error '
					'on line {0}: no group specified or bad {2} data '
					'(was: {1}).').format(i+1, e, (_(u'firstname or lastname')
						if opts.login_col is None else _(u'login'))))

			except exceptions.LicornRuntimeError, e:
				raise exceptions.LicornRuntimeError('\n' + _(u'Import error '
					'on line {0} (was: {1}).').format(i+1, e))

			try:
				user['group'] =	Group.make_name(user['group'])

			except IndexError, e:
				raise exceptions.LicornRuntimeError('\n' + _(u'Import error '
					'on line {0}: no group specified or bad {2} data '
					'(was: {1}).').format(i+1, e, _(u'group')))

			except exceptions.LicornRuntimeError, e:
				raise exceptions.LicornRuntimeError('\n' + _(u'Import error '
					'on line {0} (was: {1}).').format(i+1, e))

			if user['group'] not in groups_to_add:
				groups_to_add.append(user['group'])

			#print str(user)
			users_to_add.append(user)

			if not (i % 100):
				self.output('.')
				# FIXME: how do we force a flush on the client side?
				#sys.stderr.flush()
			i += 1
			user['linenumber'] = i

		assert ltrace(TRACE_ADD,
			'  import_users: users_to_add=%s,\ngroups_to_add=%s' % (
			users_to_add, groups_to_add))

		import_fd.close()
		self.output(_(u' done.') + '\n')

		# this will be used to recursive build an HTML page of all groups / users
		# with theyr respective passwords to be printed / distributed to all users.
		# this is probably unefficient because CSV file could be already sorted, but
		# constructing this structure will not cost that much.
		data_to_export_to_html = {}

		# Add groups and users
		length_groups = len(groups_to_add)
		length_users  = len(users_to_add)
		quantity      = length_groups + length_users

		if quantity <= 0:
			quantity = 1

		delta       = 100.0 / float(quantity) # increment for progress indicator
		progression = 0.0
		col_width   = LMC.configuration.users.login_maxlenght

		if opts.confirm_import:
			# store a ref to the groups locally to avoid selecting them again
			# and again when creating users, later.
			groups = {}

			# to print i/length progression
			i = 0

			for g in groups_to_add:
				try:
					i += 1
					groups[g] = LMC.groups.add_Group(name=g, batch=opts.no_sync)

					logging.progress('\r' + _(u'Added group {0} ({1}/{2}); '
						'progress: {3}%').format( g, i, length_groups,
							math.ceil(progression)), to_local=False)

					progression += delta

				except exceptions.AlreadyExistsException, e:
					logging.warning(str(e), to_local=False)
					progression += delta

				except exceptions.LicornException, e:
					# FIXME: flush the listener??
					#sys.stdout.flush()
					raise e

				data_to_export_to_html[g]= {}
				# FIXME: flush the listener??
				#sys.stdout.flush()

		else:
			import string
			self.output('\n%s\n%s%s%s%s%s\n' % (
				_(u'Fields order:'),
				stylize(ST_PATH, string.ljust(_('FIRSTname'), col_width)),
				stylize(ST_PATH, string.ljust(_('LASTname'), col_width)),
				stylize(ST_PATH, string.ljust(_('login'), col_width)),
				stylize(ST_PATH, string.ljust(_('group'), col_width)),
				stylize(ST_PATH, _(u'password'))))

		i = 0
		for u in users_to_add:
			try:
				i += 1
				if opts.confirm_import:
					user, password = LMC.users.add_User(lastname=u['lastname'],
											firstname=u['firstname'],
											login=u['login'],
											password=u['password'],
											profile=profile,
											in_groups=[ groups[u['group']] ],
											batch=opts.no_sync)

					logging.progress('\r' + _(u'Added user {0} {1} '
						'[login={2}, uid={3}, passwd={4}] ({5}/{6}); '
						'progress: {7}%').format(u['firstname'], u['lastname'],
						user.login, user.uidNumber, u['password'], i,
						length_users, math.ceil(progression)), to_local=False)

					# the dictionnary key is forged to have something that is sortable.
					# like this, the user accounts will be sorted in their group.
					data_to_export_to_html[ u['group'] ][
							'%s%s' % (u['lastname'], u['firstname'])
						] = [ u['firstname'], u['lastname'],
								user.login, password ]
				else:
					# Why make_login() for examples and not prepare the logins
					# when loading CSV file? this is a pure arbitrary choice.
					# It just feels more consistent for me.
					if opts.login_col:
						login = u['login']
					else:
						try:
							login = User.make_login(u['lastname'], u['firstname'])
						except exceptions.LicornRuntimeError, e:
							raise exceptions.LicornRuntimeError(_(u'Import '
								'error on line {0}.\n{1}').format(
									u['linenumber'], e))

					self.output("%s%s%s%s%s\n" % (
						string.ljust(u['firstname'], col_width),
						string.ljust(u['lastname'], col_width),
						string.ljust(login, col_width),
						string.ljust(u['group'], col_width),
						u['password']
							if u['password']
							else _(u'(autogenerated upon creation)')))

					if i > 10:
						# 10 examples should be sufficient for admin
						# to see if his options are correct or not.
						break
				progression += delta
			except exceptions.AlreadyExistsException, e:
				logging.warning(str(e), to_local=False)
				progression += delta
				# FIXME: if user already exists,
				# don't put it in the data / HTML report.
				continue
			except exceptions.LicornException, e:
				# FIXME: flush the listener.?
				#sys.stdout.flush()
				pass

			#FIXME sys.stdout.flush()

		#print str(data_to_export_to_html)

		if opts.confirm_import:

			self.output(_(u'Finished importing, creating summary HTML file: '))

			groups = data_to_export_to_html.keys()
			groups.sort()

			import time
			date_time = time.strftime(_(u'%d %m %Y at %H:%M:%S'), time.gmtime())
			html_file = open('%s/import_%s-%s.html' % (
								LMC.configuration.home_archive_dir,
								# don't take the name, it could have spaces in it.
								profile.groupName,
								hlstr.validate_name(date_time)), 'w')
			html_file.write('''<html>
				<head>
					<meta http-equiv="content-type" content="text/html; charset=utf-8" />
					<style type=\"text/css\">
					<!-- {css} -->
					</style>
				</head>
				<body>
					<h1>{title}</h1>
					<h2>{import_on_date}</h2>
					<div class="secflaw">{security_flaw}</div>
					<div>{direct_access}'''.format(
					title=_(u'{0} accounts and passwords').format(profile.name),
					import_on_date=_(u'Import made on {0}.').format(date_time),
					security_flaw=_(u'Keeping passwords in any written form '
						'is a major security flaw for you information system.'
						'<br />Please be sure obliterate this file and any '
						'printed version after having transmitted their '
						'password to your users.'),
					direct_access=_(u'Direct access to {0}:').format(
						LMC.configuration.groups._plural),
					css='''
						body { font-size:14pt; }
						h1,h2,h3 { text-align:center; }
						p,div { text-align:center; }
						table { margin: 3em 10%%; width: 80%%; border: 5px groove #369; border-collapse: collapse; }
						tr { border: 1px solid black; }
						th {border-bottom: 3px solid #369; background-color: #99c; }
						td,th { text-align: center; padding: 0.7em; }
						.even { background-color: #eef; }
						.odd { background-color: #efe; }
						div.secflaw { color: #f00; background-color: #fdd; text-align: center; border: 2px dashed #f00; margin: 3em 10%%; padding: 1em; }
						'''))

			for group in groups:
				html_file.write("&nbsp; <a href=\"#%s\">%s</a> &nbsp;" % (group, group))
			html_file.write("</div>")

			for group in groups:
				html_file.write(
					'''<a id="{group}"></a>
					<h1>{singular} «&nbsp;{group}&nbsp;»</h1>
					<table>
					<tr>
					<th>{lastname}</th><th>{firstname}</th><th>{login}</th><th>password</th>
					</tr>\n'''.format(
					group=group,
					singular=LMC.configuration.groups._singular,
					lastname=_(u'Lastname'),
					firstname=_(u'Firstname'),
					login=_(u'Login'),
					password=_(u'Password')
					))

				self.output('.')

				groupdata = data_to_export_to_html[group]
				users = groupdata.keys()
				users.sort()
				i        = 0
				tr_style = [ 'even', 'odd' ]
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
				html_file.write('</table>\n')

			html_file.write('</body>\n</html>\n')
			html_file.close()
			self.output(' %s\n%s %s\n' %(_(u'done.'), _(u'report:'),
				html_file.name))

		if opts.no_sync:
			LMC.groups.serialize()
			LMC.users.serialize()
			LMC.profiles.serialize()

		gc.collect()
	def add_user(self, opts, args):
		""" Add a user account on the system. """

		# already done in dispatch_*
		#self.__setup_gettext()

		assert ltrace(TRACE_ADD, '> add_user(opts=%s, args=%s)' % (opts, args))

		if opts.profile:
			opts.profile = LMC.profiles.guess_one(opts.profile)

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
			opts.primary_gid = LMC.groups.guess_one(opts.primary_gid)

		if opts.in_backend:
			opts.in_backend = LMC.backends.guess_one(opts.in_backend)

		if opts.in_groups:
			opts.in_groups = LMC.groups.guess_list(opts.in_groups.split(','))
		else:
			opts.in_groups = []

		# NOTE: the "else [ None ]" is important for the unique case when CLI
		# add is called with only --firstname and --lastname: in this particular
		#case, login will be autogenerated, and this loop must be called at
		# least once for this to work as expected.
		for login in sorted(opts.login.split(',')) if opts.login != None else [ None ]:
			if login != '':
				try:
					LMC.users.add_User(login=login, gecos=gecos,
						system=opts.system, password=password,
						desired_uid=opts.uid, home=opts.home,
						primary_group=opts.primary_gid,
						profile=opts.profile,
						backend=opts.in_backend,
						skel=opts.skel, batch=opts.batch, force=opts.force,
						shell=opts.shell, lastname=lastname, firstname=firstname,
						in_groups=opts.in_groups)
				except (exceptions.AlreadyExistsException,
						exceptions.BadArgumentError), e:
					logging.warning(str(e), to_local=False)

		gc.collect()
		assert ltrace(TRACE_ADD, '< add_user()')
	def add_user_in_groups(self, opts, args):

		# already done in dispatch_*
		#self.__setup_gettext()

		assert ltrace(TRACE_ADD, '> add_user_in_group().')

		users_to_add = self.select(LMC.users, args, opts,
				include_id_lists = [
					(opts.login, LMC.users.by_login),
					(opts.uid, LMC.users.by_uid)
				])

		guess = LMC.groups.guess_one

		for g in opts.groups_to_add.split(','):
			if g != '':
				try:
					g = guess(g)
					g.add_Users(users_to_add, force=opts.force)

				except exceptions.LicornException, e:
					logging.warning(_(u'Unable to add user(s) {0} '
						'in group {1} (was: {2}).').format(
						', '.join((stylize(ST_LOGIN, user.login)
							for user in users_to_add)),
						stylize(ST_NAME, g.name), str(e)), to_local=False)

		gc.collect()
		assert ltrace(TRACE_ADD, '< add_user_in_group().')
	def dispatch_add_user(self, opts, args):
		""" guess how we were called:
			- add a user (creation)
			- add a user into one or more group(s)
		"""

		self.__setup_gettext()

		assert ltrace(TRACE_ADD, '> dispatch_add_user(%s, %s)' % (opts, args))

		if opts.filename:
			self.import_users(opts, args)

		else:
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

		assert ltrace(TRACE_ADD, '< dispatch_add_user()')
	def add_group(self, opts, args):
		""" Add a POSIX group. """

		self.__setup_gettext()

		assert ltrace(TRACE_ADD, '> add_group().')

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		if opts.description:
			opts.description = unicode(opts.description)

		if opts.in_backend:
			opts.in_backend = LMC.backends.guess_one(opts.in_backend)

		assert ltrace(TRACE_ADD, 'group(s) to add: %s.' % opts.name)

		for name in sorted(opts.name.split(',')) if opts.name != None else []:
			if name != '':
				try:
					assert ltrace(TRACE_ADD, 'adding group %s.' % name)

					LMC.groups.add_Group(name, description=opts.description,
						system=opts.system, groupSkel=opts.skel,
						desired_gid=opts.gid, permissive=opts.permissive,
						backend=opts.in_backend,
						users_to_add=self.select(LMC.users,
										include_id_lists=
											[ (opts.users_to_add,
												LMC.users.guess_one) ])
									if opts.users_to_add else [],
						force=opts.force)

				except exceptions.AlreadyExistsException, e:
					logging.warning(str(e), to_local=False)

		gc.collect()
		assert ltrace(TRACE_ADD, '< add_group().')
	def add_profile(self, opts, args):
		""" Add a system wide User profile. """

		self.__setup_gettext()

		assert ltrace(TRACE_ADD, '> add_profile().')

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		if opts.name:
			opts.name = unicode(opts.name)

		if opts.description:
			opts.description = unicode(opts.description)

		guess_one_group = LMC.groups.guess_one

		# NOTE: don't do this, in case we need to create a new group. It must
		# be validated inside the add_Profile / add_Group controller methods.
		# It will be resolved inside them if we don't need to create it.
		#
		#if opts.group:
		#	opts.group = guess_one_group(opts.group)

		for name in sorted(opts.name.split(',')) if opts.name != None else []:
			if name == '':
				continue
			try:
				LMC.profiles.add_Profile(name, group=opts.group,
					profileQuota=opts.quota,
					groups=self.select(LMC.groups,
						include_id_lists=[(opts.groups, LMC.groups.guess_one)])
							if opts.groups else [],
					description=opts.description,
					profileShell=opts.shell, profileSkel=opts.skeldir,
					force_existing=opts.force_existing)
			except exceptions.AlreadyExistsException, e:
				logging.warning(str(e), to_local=False)

		gc.collect()
		assert ltrace(TRACE_ADD, '< add_profile().')
	def add_keyword(self, opts, args):
		""" Add a keyword on the system. """

		self.__setup_gettext()

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		LMC.keywords.AddKeyword(unicode(opts.name), unicode(opts.parent),
			unicode(opts.description))
	def add_privilege(self, opts, args):

		self.__setup_gettext()

		if opts.privileges_to_add is None and len(args) == 2:
			opts.privileges_to_add = args[1]
			del args[1]

		include_priv_lists = [
			(opts.privileges_to_add, LMC.groups.guess_one),
		]

		privs_to_add = self.select(LMC.privileges, args, opts,
				include_id_lists=include_priv_lists)

		LMC.privileges.add(privs_to_add)
	def add_machine(self, opts, args):

		self.__setup_gettext()

		if opts.auto_scan or opts.discover:
			LMC.machines.scan_network(
				network_to_scan=None if opts.auto_scan else [ opts.discover ])
	def add_volume(self, opts, args):
		""" Modify volumes. """

		self.__setup_gettext()

		if opts.rescan:
			LMC.extensions.volumes.rescan_volumes()
			return

		# TODO: we need the guess_* methods here, to add some flexiness to
		# the CLI tools (e.g be able to say "sda3" instead of the full "/dev/sda3")

		elif opts.all:
			# volumes.mount_volumes() treats "None" arguments (very different
			# from "[]") as saying "mount all please".
			volumes = None

		else:
			volumes = args[1:]

		# TODO: move that code into the extension.
		LMC.extensions.volumes.mount_volumes(volumes=volumes)

	### DEL
	def del_user(self, opts, args):
		""" delete one or more user account(s). """

		# already done in dispatch_*
		#self.__setup_gettext()

		if opts.system:
			selection = filters.SYSTEM

		elif opts.not_system:
			selection = filters.NOT_SYSTEM

		else:
			# be careful. default selection is NONE for a DEL operation.
			selection = filters.NONE

		include_id_lists = [
			(opts.login, LMC.users.by_login),
			(opts.uid, LMC.users.by_uid)
		]

		exclude_id_lists = [
			(opts.exclude, LMC.users.guess_one),
			(opts.exclude_login, LMC.users.by_login),
			(opts.exclude_uid, LMC.users.by_uid),
			([os.getuid()], lambda x: x)
		]

		if opts.all and (
					(
						# NOTE TO THE READER: don't event try to simplify these conditions,
						# or the order the tests: they just MATTER. Read the tests in pure
						# english to undestand them and why the order is important.
						opts.non_interactive and opts.force
					)
					or opts.batch
					or (
						opts.non_interactive and logging.ask_for_repair(
							_(u'Are you sure you want to delete all users?'),
							auto_answer=opts.auto_answer)
						or not opts.non_interactive
					)
				):
			include_id_lists.extend([
					(LMC.users.select(filters.STD), lambda x: x),
					(LMC.users.select(filters.SYSUNRSTR), lambda x: x)
				])

		users_to_del = self.select(LMC.users, args, opts,
						include_id_lists = include_id_lists,
						exclude_id_lists = exclude_id_lists,
						default_selection = selection
					)

		for user in users_to_del:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair(_(u'Delete user %s?') %
						stylize(ST_LOGIN, user.login),
					auto_answer=opts.auto_answer):
				LMC.users.del_User(user, no_archive=opts.no_archive,
									force=opts.force, batch=opts.batch)

		gc.collect()
	def del_user_from_groups(self, opts, args):

		# already done in dispatch_*
		#self.__setup_gettext()

		assert ltrace(TRACE_DEL, '> del_users_from_group(%s, %s)' % (opts, args))

		users_to_del = self.select(LMC.users, args, opts,
				include_id_lists = [
					(opts.login, LMC.users.by_login),
					(opts.uid, LMC.users.by_uid)
				])

		by_name = LMC.groups.by_name

		for g in sorted(opts.groups_to_del.split(',')):
			if g != '':
				try:
					g = by_name(g)
					g.del_Users(users_to_del, batch=opts.batch)
				except exceptions.DoesntExistException, e:
					logging.warning(_(u'Unable to remove user(s) {0} '
						'from group {1} (was: {2}).').format(
						', '.join((stylize(ST_LOGIN, u.login)
							for u in users_to_del)),
						stylize(ST_NAME, g), str(e)), to_local=False)

		gc.collect()
		assert ltrace(TRACE_DEL, '< del_users_from_group()')
	def dispatch_del_user(self, opts, args):

		self.__setup_gettext()

		if opts.login is None:
			if len(args) == 3:
				opts.login = args[1]
				opts.groups_to_del = args[2]
				args[1] = ''
				args[2] = ''
				self.del_user_from_groups(opts, args)
			else:
				self.del_user(opts, args)
		else:
			self.del_user(opts, args)
	def dispatch_del_group(self, opts, args):

		self.__setup_gettext()

		if opts.filename:
			self.desimport_groups(opts, args)
		else:
			self.del_group(opts, args)
	def desimport_groups(self, opts, args):
		""" Delete the groups (and theyr members) present in a import file.	"""

		# already done in dispatch_*
		#self.__setup_gettext()

		raise NotImplementedError('this method must be refreshed before use.')

		if opts.filename is None:
			raise exceptions.BadArgumentError(
										_(u'You must specify a file name'))

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
				group = LMC.groups.guess_one(g)
				i += 1
				self.output('\r' + _(u'Deleting groups ({0}/{1}), '
					'progression: {3:.2f}%').format(i, length_groups, progression))

				LMC.groups.del_Group(group, del_users=True, no_archive=True)
				progression += delta
				# FIXME: fush the listener??
				#sys.stdout.flush()
			except exceptions.LicornException, e:
				logging.warning(str(e),	to_local=False)
		LMC.profiles.WriteConf(LMC.configuration.profiles_config_file)
		print "\nFinished"
		gc.collect()
	def del_group(self, opts, args):
		""" delete an Licorn group. """

		# already done in dispatch_*
		#self.__setup_gettext()

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
		else:
			selection = filters.NONE

		# no else: clause. default selection for DEL is NONE (be careful)

		include_id_lists = [
			(opts.name, LMC.groups.by_name),
			(opts.gid, LMC.groups.by_gid),
		]

		exclude_id_lists = [
			(opts.exclude, LMC.groups.guess_one),
			(opts.exclude_group, LMC.groups.by_name),
			(opts.exclude_gid, LMC.groups.by_gid)
		]

		if opts.all and (
				(
					# NOTE TO THE READER: don't event try to simplify these conditions,
					# or the order the tests: they just MATTER. Read the tests in pure
					# english to undestand them and why the order is important.
					opts.non_interactive and opts.force
				)
				or opts.batch
				or (
					opts.non_interactive and logging.ask_for_repair(
						_(u'Are you sure you want to delete all groups?'),
						auto_answer=opts.auto_answer)
					or not opts.non_interactive
				)
			):
				include_id_lists.extend([
					(LMC.groups.select(filters.STD), lambda x: x),
					(LMC.groups.select(filters.SYSUNRSTR), lambda x: x)
					])

		groups_to_del = self.select(LMC.groups, args, opts,
						include_id_lists = include_id_lists,
						exclude_id_lists = exclude_id_lists,
						default_selection=selection)

		#gc.set_debug(gc.DEBUG_LEAK)

		for group in groups_to_del:
			if opts.non_interactive or opts.batch or opts.force or \
					logging.ask_for_repair(_(u'Delete group %s?') % stylize(
					ST_NAME, group.name), auto_answer=opts.auto_answer):

				try:
					LMC.groups.del_Group(group, del_users=opts.del_users,
						no_archive=opts.no_archive, force=opts.force)

				except exceptions.BadArgumentError, e:
					logging.warning(e, to_local=False)

		# NOTE on 2011 02 17: I can't seem to find why (perhaps it has
		# something to do with pyro threads not beeiing terminated immediately),
		# but the gc.collect() call is mandatory for this to work as expected:
		#
		#	add profile test
		#	del group test 		(fails because profile groups are protected)
		#	del profile test
		#	get group test		(fails because inexistant group)
		#	add profile test
		#
		# Without the collection, group test is still present in memory after
		# the profile deletion (and get group shows it, but del group crashes).
		#
		# I thus add this gc.collect() call at the end of all RWI methods.
		gc.collect()

		# this one has no effect at all. Only the gc.collect() has.
		#del groups_to_del

	def del_profile(self, opts, args):
		""" Delete a system wide User profile. """

		self.__setup_gettext()

		include_id_lists = [
				(opts.name, LMC.profiles.by_name),
				(opts.group, LMC.profiles.by_group)
			]

		exclude_id_lists = [
				(opts.exclude, LMC.profiles.guess_one)
			]

		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch
				or (opts.non_interactive and logging.ask_for_repair(
					_(u'Are you sure you want to delete all profiles?'),
					opts.auto_answer)
				or not opts.non_interactive)
			):
				include_id_lists.extend([
						(LMC.profiles.select(filters.ALL), lambda x: x)
					])

		profiles_to_del = self.select(LMC.profiles, args, opts,
				include_id_lists = include_id_lists,
				exclude_id_lists = exclude_id_lists)

		for p in profiles_to_del:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair(_(u'Delete profile %s?') %
					stylize(ST_LOGIN, p.name),
					auto_answer=opts.auto_answer):

				LMC.profiles.del_Profile(p,
					del_users=opts.del_users,
					no_archive=opts.no_archive)

		gc.collect()
	def del_keyword(self, opts, args):
		""" Delete a system wide User profile. """

		self.__setup_gettext()

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		LMC.keywords.DeleteKeyword(opts.name, opts.del_children)
	def del_privilege(self, opts, args):

		self.__setup_gettext()

		if opts.privileges_to_remove is None and len(args) == 2:
			opts.privileges_to_remove = args[1]
			del args[1]

		include_priv_lists = [
				(opts.privileges_to_remove, LMC.groups.guess_one),
			]

		exclude_priv_lists = [
				(opts.exclude, LMC.privileges.guess_one),
			]

		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch
				or (opts.non_interactive and logging.ask_for_repair(
					_(u'Are you sure you want to delete all privileges?'),
					auto_answer=opts.auto_answer) or not opts.non_interactive)):

				include_priv_lists.extend([
					(LMC.privileges.select(filters.ALL), lambda x: x),
					])

		privs_to_del = self.select(LMC.privileges, args, opts,
				include_id_lists = include_priv_lists,
				exclude_id_lists = exclude_priv_lists)

		for priv in privs_to_del:
			if priv is not None and (
				opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair(_(u'Delete privilege %s?') %
					stylize(ST_LOGIN, priv.name),
					auto_answer=opts.auto_answer)):

				LMC.privileges.delete((priv,))
	def del_volume(self, opts, args):
		""" Modify volumes. """

		self.__setup_gettext()

		if opts.all:
			volumes = LMC.extensions.volumes.keys()
		else:
			volumes = args[1:]

		# TODO: move that code into the extension.
		LMC.extensions.volumes.unmount_volumes(volumes=volumes,
															force=opts.force)
	### MOD
	def mod_user(self, opts, args):
		""" Modify a POSIX user account (Samba / LDAP included). """

		self.__setup_gettext()

		if opts.system:
			selection = filters.SYSTEM

		elif opts.not_system:
			selection = filters.NOT_SYSTEM

		else:
			# by default if nothing is specified, we modify the current user.
			# this is a special comfort-shortcut behavior.
			selection = [ LMC.users.by_login(opts.current_user) ]

		include_id_lists = [
			(opts.login, LMC.users.by_login),
			(opts.uid, LMC.users.by_uid)
			]

		exclude_id_lists = [
			(opts.exclude, LMC.users.guess_one),
			(opts.exclude_login, LMC.users.by_login),
			(opts.exclude_uid, LMC.users.by_uid)
			]

		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch
				or (opts.non_interactive and logging.ask_for_repair(
					_(u'Are you sure you want to modify all users?'),
					auto_answer=opts.auto_answer)
				or not opts.non_interactive)
			):
				include_id_lists.extend([
					(LMC.users.select(filters.STD), lambda x: x),
					(LMC.users.select(filters.SYSUNRSTR), lambda x: x)
					])

		users_to_mod = self.select(LMC.users, args, opts,
				include_id_lists = include_id_lists,
				exclude_id_lists = exclude_id_lists,
				default_selection = selection)

		assert ltrace(TRACE_MOD, '> mod_user(%s)' % ', '.join(user.login for user in users_to_mod))

		something_done = False

		for user in users_to_mod:
			try:
				if opts.non_interactive or opts.batch or opts.force or \
					logging.ask_for_repair(_(u'Modify user %s?') % stylize(
						ST_LOGIN, user.login),
					auto_answer=opts.auto_answer):

					if opts.restore_watch:
						something_done = True
						user._inotifier_add_watch(self.licornd, force_reload=True)

					if opts.newgecos is not None:
						something_done = True
						user.gecos = unicode(opts.newgecos)

					if opts.newshell is not None:
						something_done = True
						user.loginShell = opts.newshell

					if opts.newpassword is not None:
						something_done = True
						user.password = opts.newpassword

					if opts.interactive_password:
						something_done = True

						login = user.login
						message=_(u'Please enter new password for user %s: ') % \
							stylize(ST_NAME, login)
						confirm=_(u'Please confirm new password for user %s: ') % \
							stylize(ST_NAME, login)

						if opts.current_user != 'root':
							if opts.current_user == login:
								old_message = _(u'Please enter your OLD '
										'(current) password: ')
								message=_(u'Please enter your new password: ')
								confirm=_(u'Please confirm your new password: ')

							else:
								old_message = _(u"Please enter %s's OLD "
									"(current) password: ") % stylize(ST_LOGIN, login)

							if not user.check_password(
									self.interact(old_message,
									interaction=interactions.GET_PASSWORD)):
								raise exceptions.BadArgumentError(
									_('Wrong password, procedure aborted.'))

						password1 = self.interact(message,
							interaction=interactions.GET_PASSWORD)
						password2 = self.interact(confirm,
							interaction=interactions.GET_PASSWORD)

						if password1 == password2:
							user.password = password1
						else:
							raise exceptions.BadArgumentError(_(u'Passwords '
								'do not match, leaving the old one in place.'))

					if opts.auto_passwd:
						something_done = True
						user.password = None

					if opts.lock is not None:
						something_done = True
						user.locked = opts.lock

					# NOTE: it is important to do the "del" operation before the
					# "add" one. In the other direction, there is a bad
					# side-effect if you add a user to resp-G and delete it from
					# G after that: the symlink to G is gone for the new resp-G
					# and this is not wanted (we would need to check --extended
					# to correct the problem, which would waste CPU cycles and
					# I/O, to fix a thing that should not have existed).
					if opts.groups_to_del:
						something_done = True
						for g in sorted(opts.groups_to_del.split(',')):
							if g != '':
								try:
									group = LMC.groups.guess_one(g)
									group.del_Users([ user ])
								except exceptions.LicornRuntimeException, e:
									logging.warning(_(u'Unable to remove '
										'user {0} from group {1} '
										'(was: {2}).').format(
											stylize(ST_LOGIN, user.login),
											stylize(ST_NAME, group.name),
											str(e)), to_local=False)
								except exceptions.LicornException, e:
									raise exceptions.LicornRuntimeError(
										_(u'Unable to remove '
										'user {0} from group {1} '
										'(was: {2}).').format(
											stylize(ST_LOGIN, user.login),
											stylize(ST_NAME, group.name),
											str(e)))

					if opts.groups_to_add:
						something_done = True
						for g in sorted(opts.groups_to_add.split(',')):
							if g != '':
								try:
									group = LMC.groups.guess_one(g)
									group.add_Users([ user ], force=opts.force)
								except exceptions.LicornRuntimeException, e:
									logging.warning(_(u'Unable to add user '
										'{0} in group {1} (was: {2}).').format(
											stylize(ST_LOGIN, user.login),
											stylize(ST_NAME, group.name),
											str(e)), to_local=False)
								except exceptions.LicornException, e:
									raise exceptions.LicornRuntimeError(
										_(u'Unable to add user '
										'{0} in group {1} (was: {2}).').format(
											stylize(ST_LOGIN, user.login),
											stylize(ST_NAME, group.name),
											str(e)))

					if opts.apply_skel is not None:
						something_done = True
						user.apply_skel(opts.apply_skel)

			except exceptions.BadArgumentError, e:
				logging.warning(e, to_local=False)

		if not something_done:
			raise exceptions.NeedHelpException(_(u'What do you want to modify '
				'about user(s) %s ?') % ', '.join(stylize(ST_LOGIN, user.login)
					for user in users_to_mod))
	def mod_group(self, opts, args):
		""" Modify a group. """

		self.__setup_gettext()

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
			selection = filters.NONE

		include_id_lists = [
			(opts.name, LMC.groups.by_name),
			(opts.gid, LMC.groups.by_gid)
		]

		exclude_id_lists = [
			(opts.exclude, LMC.groups.guess_one),
			(opts.exclude_group, LMC.groups.by_name),
			(opts.exclude_gid, LMC.groups.by_gid)
		]

		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch
				or (opts.non_interactive and logging.ask_for_repair(
					_(u'Are you sure you want to modify all groups?'),
					auto_answer=opts.auto_answer) or not opts.non_interactive)
			):
					include_id_lists.extend([
						(LMC.groups.select(filters.STD), lambda x: x),
						(LMC.groups.select(filters.SYSUNRSTR), lambda x: x)
					])

		groups_to_mod = self.select(LMC.groups, args, opts,
					include_id_lists = include_id_lists,
					exclude_id_lists = exclude_id_lists,
					default_selection = selection)

		guess_one_user   = LMC.users.guess_one
		guess_users_list = LMC.users.guess_list

		if opts.move_to_backend:
			# resolve the backend object from the name
			opts.move_to_backend = LMC.backends.guess_one(opts.move_to_backend)

		assert ltrace(TRACE_MOD, '> mod_group(%s)' % groups_to_mod)

		something_done = False

		for group in groups_to_mod:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair(_(u'Modify group %s?') % stylize(
				ST_NAME, group.name),auto_answer=opts.auto_answer):

				if opts.move_to_backend is not None:
					gname = group.name
					if group.is_helper:
						logging.info(_(u'Skipped associated system group %s, '
							'handled automatically by standard group move.') %
								stylize(ST_NAME, gname), to_local=False)
					else:
						something_done = True
						group.move_to_backend(opts.move_to_backend,	opts.force)

				if opts.permissive is not None:
					something_done = True
					group.permissive = opts.permissive

				if opts.restore_watch:
					something_done = True
					group._inotifier_add_watch(self.licornd, force_reload=True)

				if opts.newname is not None:
					something_done = True
					LMC.groups.RenameGroup(gid=gid, newname=opts.newname)

				if opts.newskel is not None:
					something_done = True
					group.groupSkel = opts.newskel

				if opts.newdescription is not None:
					something_done = True
					group.description = unicode(opts.newdescription)

				if opts.users_to_add:
					something_done = True
					group.add_Users(
						guess_users_list(sorted(opts.users_to_add.split(','))),
						force=opts.force)

				if opts.users_to_del:
					something_done = True
					group.del_Users(
						guess_users_list(sorted(opts.users_to_del.split(','))))

				if opts.resps_to_add:
					if group.is_standard:
						something_done = True
						group.responsible_group.add_Users(
							guess_users_list(sorted(opts.resps_to_add.split(','))),
							force=opts.force)
					else:
						logging.warning(_(u'Skipped responsible(s) {0} addition '
							'on non-standard group {1}.').format(resps_to_add,
								group.name), to_local=False)

				if opts.resps_to_del:
					if group.is_standard:
						something_done = True
						group.responsible_group.del_Users(
							guess_users_list(sorted(opts.resps_to_del.split(','))),
							force=opts.force)
					else:
						logging.warning(_(u'Skipped responsible(s) {0} deletion '
							'on non-standard group {1}.').format(resps_to_del,
								group.name), to_local=False)

				if opts.guests_to_add:
					if group.is_standard:
						something_done = True
						group.guest_group.add_Users(
							guess_users_list(sorted(opts.guests_to_add.split(','))),
							force=opts.force)
					else:
						logging.warning(_(u'Skipped guest(s) {0} addition '
							'on non-standard group {1}.').format(guests_to_add,
								group.name), to_local=False)

				if opts.guests_to_del:
					if group.is_standard:
						something_done = True
						group.guest_group.del_Users(
							guess_users_list(sorted(opts.guests_to_del.split(','))),
							force=opts.force)
					else:
						logging.warning(_(u'Skipped guest(s) {0} deletion '
							'on non-standard group {1}.').format(guests_to_del,
								group.name), to_local=False)

				if opts.granted_profiles_to_add is not None:
					something_done = True
					LMC.groups.AddGrantedProfiles(gid=gid,
						profiles=sorted(opts.granted_profiles_to_add.split(',')))

				if opts.granted_profiles_to_del is not None:
					something_done = True
					LMC.groups.DeleteGrantedProfiles(gid=gid,
						profiles=sorted(opts.granted_profiles_to_del.split(',')))

		if not something_done:
			raise exceptions.NeedHelpException(_(u'What do you want to modify '
				'about group(s) %s?') % ', '.join(stylize(ST_NAME, group.name)
					for group in groups_to_mod))
	def mod_profile(self, opts, args):
		""" Modify a system wide User profile. """

		self.__setup_gettext()

		include_id_lists = [
			(opts.name, LMC.profiles.by_name),
			(opts.group, LMC.profiles.by_group)
		]
		exclude_id_lists = [
			(opts.exclude, LMC.profiles.guess_one),
		]

		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch
				or (opts.non_interactive and logging.ask_for_repair(
					_(u'Are you sure you want to modify all profiles?'),
					opts.auto_answer)
				or not opts.non_interactive)
			):
				include_id_lists.extend([
					(LMC.profiles.select(filters.ALL), lambda x: x)
				])

		profiles_to_mod = self.select(LMC.profiles, args, opts,
				include_id_lists = include_id_lists,
				exclude_id_lists = exclude_id_lists)

		assert ltrace(TRACE_MOD, '> mod_profile(%s)' % profiles_to_mod)

		ggi = LMC.groups.guess_list

		something_done = False

		for profile in profiles_to_mod:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair(_(u'Modify profile %s?') % stylize(
				ST_LOGIN, profile.name),
				auto_answer=opts.auto_answer):

				if opts.newname is not None:
					something_done = True
					profile.name = unicode(opts.newname)

				if opts.newgroup is not None:
					something_done = True
					LMC.profiles.ChangeProfileGroup(group=group,
												newgroup=opts.newgroup)

				if opts.description is not None:
					something_done = True
					profile.description = unicode(opts.description)

				if opts.newshell is not None:
					something_done = True
					profile.profileShell = opts.newshell

				if opts.newskel is not None:
					something_done = True
					profile.profileSkel = opts.newskel

				if opts.newquota is not None:
					something_done = True
					profile.profileQuota = opts.newquota

				if opts.groups_to_del is not None:
					something_done = True
					profile.del_Groups(ggi(sorted(opts.groups_to_del.split(','))),
										instant_apply=opts.instant_apply)

				if opts.groups_to_add is not None:
					something_done = True
					profile.add_Groups(ggi(sorted(opts.groups_to_add.split(','))),
										instant_apply=opts.instant_apply)

				local_include_id_lists = []

				if opts.apply_to_members:
					something_done = True
					local_include_id_lists.append((profile.group.gidMembers, lambda x: x))

				if opts.apply_to_users is not None:
					local_include_id_lists.append(
						(opts.apply_to_users.split(','), LMC.users.guess_one))

				if opts.apply_to_groups is not None:
					for group in LMC.groups.guess_list(
											sorted(opts.apply_to_groups.split(','))):
						local_include_id_lists.append(
							(group.all_members, lambda x: x))

				if opts.apply_all_attributes or opts.apply_skel or opts.apply_groups:

					_users = self.select(LMC.users,
							include_id_lists = local_include_id_lists,
							exclude_id_lists = [
								(opts.exclude, LMC.users.guess_one),
								(opts.exclude_login, LMC.users.by_login),
								(opts.exclude_uid, LMC.users.by_uid)
							],
							default_selection = filters.NONE,
							all=opts.apply_to_all_accounts)

					assert ltrace(TRACE_MOD,"  mod_profile(on_users=%s)" % _users)

					if _users != []:
						something_done = True
						LMC.profiles.reapply_Profile(_users,
							apply_groups=opts.apply_groups,
							apply_skel=opts.apply_skel,
							batch=opts.batch, auto_answer=opts.auto_answer)

		if not something_done:
			raise exceptions.NeedHelpException(_(u'What do you want to modify '
				'about profile(s) %s?') % ', '.join(stylize(ST_NAME, p.name)
											for p in profiles_to_mod))
		assert ltrace(TRACE_MOD, '< mod_profile()')
	def mod_machine(self, opts, args):
		""" Modify a machine. """

		self.__setup_gettext()

		if opts.all:
			selection = host_status.ALL
		else:
			selection = filters.NONE

			if opts.idle:
				selection |= host_status.IDLE

			if opts.asleep:
				selection |= host_status.ASLEEP

			if opts.active:
				selection |= host_status.ACTIVE

		mids_to_mod = self.select(LMC.machines, args, opts,
				include_id_lists = [
					(opts.hostname, LMC.machines.by_hostname),
					(opts.mid, LMC.machines.has_key)
				],
				default_selection=selection)

		for machine in mids_to_mod:
			if opts.shutdown:
				machine.shutdown(warn_users=opts.warn_users)
	def mod_keyword(self, opts, args):
		""" Modify a keyword. """

		self.__setup_gettext()

		raise NotImplementedError(_(u'not yet anymore.'))

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

		self.__setup_gettext()

		raise NotImplementedError(_(u'not yet anymore.'))

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
				LMC.keywords.DeleteKeywordsFromPath(opts.path,
					sorted(opts.keywords_to_del.split(',')), opts.recursive)
			if opts.keywords_to_add is not None:
				LMC.keywords.AddKeywordsToPath(opts.path,
					sorted(opts.keywords_to_add.split(',')), opts.recursive)
	def mod_configuration(self, opts, args):
		""" Modify some aspects or abstract directives of the system configuration
			(use with caution)."""

		self.__setup_gettext()

		if opts.setup_shared_dirs:
			LMC.configuration.check_base_dirs(minimal=False, batch=True)

		elif opts.set_hostname:
			LMC.configuration.ModifyHostname(opts.set_hostname)

		elif opts.set_ip_address:
			raise exceptions.NotImplementedError(
				"changing server IP address is not yet implemented.")

		elif opts.privileges_to_add:
			LMC.privileges.add(sorted(opts.privileges_to_add.split(',')))

		elif opts.privileges_to_remove:
			LMC.privileges.delete(sorted(opts.privileges_to_remove.split(',')))

		elif opts.hidden_groups != None:
			LMC.configuration.SetHiddenGroups(opts.hidden_groups)

		#FIXME: refactor the next 4 blocks
		# don't sort the backends, the order is probably important.

		elif opts.disable_backends != None:
			for backend in opts.disable_backends.split(','):
				try:
					LMC.backends.disable_backend(backend)
				except exceptions.DoesntExistException, e:
					logging.warning(_(u'Skipped non-existing backend %s.') %
						stylize(ST_NAME, backend), to_local=False)

		elif opts.enable_backends != None:
			for backend in opts.enable_backends.split(','):
				try:
					LMC.backends.enable_backend(backend)
				except exceptions.DoesntExistException, e:
					logging.warning(_(u'Skipped non-existing backend %s.') %
						stylize(ST_NAME, backend), to_local=False)

		elif opts.disable_extensions != None:
			for extension in opts.disable_extensions.split(','):
				try:
					LMC.extensions.disable_extension(extension)
				except exceptions.DoesntExistException, e:
					logging.warning(_(u'Skipped non-existing extension %s.') %
						stylize(ST_NAME, extension), to_local=False)

		elif opts.enable_extensions != None:
			for extension in opts.enable_extensions.split(','):
				try:
					LMC.extensions.enable_extension(extension)
				except exceptions.DoesntExistException, e:
					logging.warning(_(u'Skipped non-existing extension %s.') %
						stylize(ST_NAME, extension), to_local=False)

		else:
			raise exceptions.NeedHelpException(_(u'What do you want to '
				'modify? use --help to know!'))
	def mod_volume(self, opts, args):
		""" Modify volumes. """

		self.__setup_gettext()

		# TODO: move that code into the extension.

		nothing_done = True

		if opts.rescan:
			nothing_done = False
			LMC.extensions.volumes.rescan_volumes()

		if opts.unmount_volumes:
			nothing_done = False
			LMC.extensions.volumes.unmount_volumes(
										opts.unmount_volumes.split(','))

		if opts.mount_volumes:
			nothing_done = False
			LMC.extensions.volumes.mount_volumes(opts.mount_volumes.split(','))

		if opts.del_volumes:
			nothing_done = False
			for volume in opts.del_volumes.split(','):
				LMC.extensions.volumes.del_volume(by_string=volume)

		if opts.add_volumes:
			nothing_done = False
			for volume in opts.add_volumes.split(','):
				LMC.extensions.volumes.add_volume(by_string=volume)

		if opts.disable_volumes:
			nothing_done = False
			LMC.extensions.volumes.disable_volumes(opts.disable_volumes.split(','))

		if opts.enable_volumes:
			nothing_done = False
			LMC.extensions.volumes.enable_volumes(opts.enable_volumes.split(','))

		if nothing_done:
			raise exceptions.NeedHelpException(_(u'What do you want to modify '
				'on volumes? use --help to know!'))
	### CHK
	def chk_user(self, opts, args):
		""" Check one or more user account(s). """

		self.__setup_gettext()

		if opts.system:
			selection = filters.SYSTEM

		elif opts.not_system:
			selection = filters.NOT_SYSTEM

		else:
			# by default we check the current user
			selection = [ LMC.users.by_login(opts.current_user) ]

		include_id_lists = [
			(opts.login, LMC.users.by_login),
			(opts.uid, LMC.users.by_uid)
		]

		exclude_id_lists = [
			(opts.exclude, LMC.users.guess_one),
			(opts.exclude_login, LMC.users.by_login),
			(opts.exclude_uid, LMC.users.by_uid)
		]

		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
					opts.non_interactive and opts.force) or opts.batch
				or (opts.non_interactive and logging.ask_for_repair(
					_(u'Are you sure you want to check all users?'),
					auto_answer=opts.auto_answer) or not opts.non_interactive)
			):
				include_id_lists.extend([
					(LMC.users.select(filters.STD), lambda x: x),
					(LMC.users.select(filters.SYSUNRSTR), lambda x: x)
					])

		users_to_chk = self.select(LMC.users, args, opts,
			include_id_lists = include_id_lists,
			exclude_id_lists = exclude_id_lists,
			default_selection = selection,
			all=opts.all)

		assert ltrace(TRACE_CHK, '> chk_user(%s)' % users_to_chk)

		if users_to_chk != []:
			if opts.force or opts.batch or opts.non_interactive:
				LMC.users.chk_Users(users_to_chk, minimal=opts.minimal,
					auto_answer=opts.auto_answer, batch=opts.batch)
			else:
				for user in users_to_chk:
					if logging.ask_for_repair(_(u'Check account %s?') %
							stylize(ST_LOGIN, user.login),
						auto_answer=opts.auto_answer):

						user.check(minimal=opts.minimal, batch=opts.batch,
							auto_answer=opts.auto_answer)

		assert ltrace(TRACE_CHK, '< chk_user()')
	def chk_group(self, opts, args):
		""" Check one or more group(s). """

		self.__setup_gettext()

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

		include_id_lists = [
			(opts.name, LMC.groups.by_name),
			(opts.gid, LMC.groups.by_gid)
		]

		exclude_id_lists = [
			(opts.exclude, LMC.groups.guess_one),
			(opts.exclude_group, LMC.groups.by_name),
			(opts.exclude_gid, LMC.groups.by_gid)
		]

		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
					opts.non_interactive and opts.force) or opts.batch
				or (opts.non_interactive and logging.ask_for_repair(
					_(u'Are you sure you want to check all groups?'),
					auto_answer=opts.auto_answer) or not opts.non_interactive)
			):
				include_id_lists.extend([
					(LMC.groups.select(filters.STD), lambda x: x),
					(LMC.groups.select(filters.SYSUNRSTR), lambda x: x)
					])

		groups_to_chk = self.select(LMC.groups, args, opts,
			include_id_lists = include_id_lists,
			exclude_id_lists = exclude_id_lists,
			default_selection = selection,
			all=opts.all)

		assert ltrace(TRACE_CHK, '> chk_group(%s)' % groups_to_chk)

		if groups_to_chk != []:
			if opts.force or opts.batch or opts.non_interactive:
				LMC.groups.check_groups(groups_to_chk,
					minimal=opts.minimal, batch=opts.batch,
					auto_answer=opts.auto_answer, force=opts.force)
			else:
				for group in groups_to_chk:
					if logging.ask_for_repair(_(u'Check group %s?') %
							stylize(ST_NAME, group.name),
						auto_answer=opts.auto_answer):

						group.check(minimal=opts.minimal, batch=opts.batch,
							auto_answer=opts.auto_answer, force=opts.force)

		assert ltrace(TRACE_CHK, '< chk_group()')
	def chk_profile(self, opts, args):
		""" TODO: to be implemented. """

		self.__setup_gettext()

		include_id_lists = [
			(opts.name, LMC.profiles.by_name),
			(opts.group, LMC.profiles.by_group)
		]
		exclude_id_lists = [
			(opts.exclude, LMC.profiles.guess_one)
		]

		if opts.all and (
			(
				# NOTE TO THE READER: don't event try to simplify these conditions,
				# or the order the tests: they just MATTER. Read the tests in pure
				# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch
				or (opts.non_interactive and logging.ask_for_repair(
					_(u'Are you sure you want to check all profiles?'),
					opts.auto_answer)
				or not opts.non_interactive)
			):
				include_id_lists.extend([
						(LMC.profiles.select(filters.ALL), lambda x: x)
					])

		profiles_to_del = self.select(LMC.profiles, args, opts,
				include_id_lists = include_id_lists,
				exclude_id_lists = exclude_id_lists)

		for p in profiles_to_del:
			if opts.non_interactive or opts.batch or opts.force or \
				logging.ask_for_repair(_(u'Check profile %s?') %
					stylize(ST_NAME, p.name),
				auto_answer=opts.auto_answer):
				raise NotImplementedError(_(u'Sorry, not yet.'))
	def chk_configuration(self, opts, args):
		""" TODO: to be implemented. """

		self.__setup_gettext()

		LMC.configuration.check(opts.minimal, batch=opts.batch,
			auto_answer=opts.auto_answer)
