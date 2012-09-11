# -*- coding: utf-8 -*-
"""
Licorn Daemon Real World Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The RWI wraps calls from interfaces (WMI, CLI) to the core, and operates
arguments transformation (e.g. numeric IDs and string names to real Core
objects) and checking. It is a common entry point, thus the name "Real
World Interface" ;-)

The RWI Methods are technically called via the Pyro `CommandListener` Thread.
All interfaces connect to the Licorn® daemon via the Pyro channel.

:copyright:
	* 2010-2012 Olivier Cortès <olive@deep-ocean.net>
	* partial 2011-2012 META IT http://meta-it.fr/
	* partial 2010, 2011 Robin Lucbernet <robinlucbernet@gmail.com>
:license:
	* GNU GPL version 2.
"""

try: import simplejson as json
except: import json

import types, Pyro.core, itertools, gc, tempfile, time

from operator  import attrgetter
from threading import current_thread

from licorn.foundations           import options, exceptions, logging, settings
from licorn.foundations           import fsapi, hlstr, pyutils, events, styles
from licorn.foundations.events    import LicornEvent
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import NamedObject, pyro_protected_attrs
from licorn.foundations.messaging import LicornMessage, ListenerObject, remote_output
from licorn.foundations.constants import filters, interactions, host_status, \
											priorities, reasons, verbose

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

from licorn.core         import LMC, version
from licorn.core.classes import SelectableController

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

	# ================================================== Generic access methods
	#
	# Used massively in the :class:`~licorn.interfaces.wmi.libs.utils.WmiProxy`
	# instances for real-time in-core interaction.
	#
	# They are all surrounded by the exception catcher, because any problem
	# will be hardly represented by the Pyro tunnel, and can be very hard to
	# debug if not catched before.
	@pyutils.catch_exception
	def generic_controller_method_call(self, controller_name, method_name, *args, **kwargs):
		return getattr(SelectableController.instances[controller_name], method_name)(*args, **kwargs)
	@pyutils.catch_exception
	def generic_core_object_method_call(self, controller_name, object_id, method_name, *args, **kwargs):
		return getattr(SelectableController.instances[controller_name].by_key(object_id), method_name)(*args, **kwargs)
	@pyutils.catch_exception
	def generic_core_object_property_set(self, controller_name, object_id, property_name, property_value):
		setattr(SelectableController.instances[controller_name].by_key(object_id), property_name, property_value)
	@pyutils.catch_exception
	def generic_core_object_property_get(self, controller_name, object_id, property_name):
		return getattr(getattr(LMC, controller_name).by_key(object_id), property_name)
	@pyutils.catch_exception
	def generic_resolved_call(self, object_name, method_name, *args, **kwargs):
		return getattr(pyutils.resolve_attr(object_name, { "LMC": LMC }), method_name)(*args, **kwargs)
	@pyutils.catch_exception
	def configuration_get(self, attr_name):
		""" R/O access to configuration for external callers. R/W access might
			come if we need it someday.

			.. versionadded:: 1.3
		"""
		result = pyutils.resolve_attr("LMC.configuration.%s" % attr_name, { "LMC": LMC })

		return result() if callable(result) else result
	@pyutils.catch_exception
	def setting_get(self, attr_name):
		""" R/O access to settings for external callers. R/W access might
			come if we need it someday.

			.. versionadded:: 1.3
		"""
		return pyutils.resolve_attr("settings.%s" % attr_name, {'settings': settings})
	def register_event_collector(self, collector):
		events.register_collector(collector)
	def unregister_event_collector(self, collector):
		events.unregister_collector(collector)

	# ============================================== WMI and CLI access methods

	@pyutils.catch_exception
	def select(self, controller, args=None, opts=None, include_id_lists=None,
		exclude_id_lists=None, default_selection=filters.NONE, all=False):

		if type(controller) in (types.StringType, types.UnicodeType):
			controller = SelectableController.instances[controller]

		assert ltrace_func(TRACE_CLI)

		# use a set() to avoid duplicates during selections. This will allow us,
		# later in implementation to do more complex selections (unions,
		# differences, intersections and al.

		if include_id_lists is None:
			include_id_lists = []

		if exclude_id_lists is None:
			exclude_id_lists = []

		if args is None:
			args = ()

		xids = set()

		if all:
			# if --all, manually included IDs (with --login, --group, --uid,
			# --gid…) will be totally discarded: --all gets precedence. But
			# excluded items will still be excluded, to allow
			# "--all --exclude-login toto" semi-complex selections.
			ids = set(controller)

		else:
			ids = set()

			something_tried = False

			if len(args) > 0:
				for arg in args:
					if arg == '':
						continue

					include_id_lists.append((arg, controller.guess_one))

			if hasattr(opts, 'word_match'):
				for arg in opts.word_match.split(','):
					if arg == '':
						continue

					include_id_lists.append((controller.word_match(arg),
												controller.guess_one))

			# select included IDs
			for id_arg, resolver in include_id_lists:

				if type(resolver) == types.StringType:
					resolver = getattr(controller, resolver)

				if id_arg is None:
					continue

				for oid in id_arg.split(',') if hasattr(id_arg, 'split') else (
					(id_arg, ) if type(id_arg) == types.IntType else id_arg):
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

				exclude_id_lists.append((controller.word_match(arg),
											controller.guess_one))

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

	# ========================================= CLI "GET" interactive functions

	def get_daemon_status(self, opts=None, args=None, cli_output=True):
		""" This method is called from CLI tools. """

		try:
			if cli_output:
				self.setup_listener_gettext()
				remote_output(LMC.licornd.dump_status(opts.long_output,
								opts.precision), clear_terminal=opts.monitor_clear)
			else:
				return LMC.licornd.dump_status(as_string=False)
		except Exception:
			# When the daemon is restarting, the CommandListener thread
			# shutdowns the Pyro daemon, and its reference attribute is
			# deleted, producing an AttributeError, forwarded to the
			# client-side caller. We catch any other 'Exception' to avoid
			# borking the client side.
			#
			# We just avoid forwarding it, this nothing to care about. As
			# the current method is called many times in a 'while 1' loop
			# on the client side, only one iteration of the loop will not
			# produce any output, which will get totally un-noticed and
			# is harmless.
			logging.exception(_('Harmless Exception encountered in RWI.get_daemon_status()'))
	def get_volumes(self, opts, args):

		self.setup_listener_gettext()

		remote_output(LMC.extensions.volumes.get_CLI(opts, args))
	def get_users(self, opts, args):
		""" Get the list of POSIX user accounts (Samba / LDAP included). """

		self.setup_listener_gettext()

		if opts.dump:
			remote_output(LMC.users.dump())
			return

		assert ltrace(TRACE_GET, '> get_users(%s,%s)' % (opts, args))

		include_id_lists, exclude_id_lists = self.__default_users_includes_excludes(opts)

		users_to_get = self.select(LMC.users, args[1:], opts,
					include_id_lists = [
						(opts.login, LMC.users.by_login),
						(opts.uid, LMC.users.by_uid)
					],
					exclude_id_lists = [
						(opts.exclude, LMC.users.guess_one),
						(opts.exclude_login, LMC.users.by_login),
						(opts.exclude_uid, LMC.users.by_uid)
					],
					default_selection = self.__default_users_selection(opts, for_get=True),
					all=opts.all)

		if opts.to_script:
			data = LMC.users.to_script(selected=users_to_get,
										script_format=opts.to_script,
										script_separator=opts.script_sep)

		elif opts.xml:
			data = LMC.users.to_XML(selected=users_to_get,
										long_output=opts.long_output)
		else:
			data = LMC.users._cli_get(selected=users_to_get,
										long_output=opts.long_output)

		if data and data != '\n':
			remote_output(data)

		assert ltrace(TRACE_GET, '< get_users()')
	def get_groups(self, opts, args):
		""" Get the list of POSIX LMC.groups (can be LDAP). """

		self.setup_listener_gettext()

		if opts.dump:
			remote_output(LMC.groups.dump())
			return

		assert ltrace(TRACE_GET, '> get_groups(%s,%s)' % (opts, args))

		include_id_lists, exclude_id_lists = self.__default_groups_includes_excludes(opts)

		groups_to_get = self.select(LMC.groups,	args[1:], opts,
				include_id_lists = include_id_lists,
				exclude_id_lists = exclude_id_lists,
				default_selection=self.__default_groups_selection(opts),
				all=opts.all)

		if opts.to_script:
			data = LMC.groups.to_script(selected=groups_to_get,
										script_format=opts.to_script,
										script_separator=opts.script_sep)

		elif opts.xml:
			data = LMC.groups.to_XML(selected=groups_to_get,
										long_output=opts.long_output)
		else:
			data = LMC.groups._cli_get(selected=groups_to_get,
										long_output=opts.long_output,
										no_colors=opts.no_colors)

		if data and data != '\n':
			remote_output(data)

		assert ltrace(TRACE_GET, '< get_groups()')
	def get_profiles(self, opts, args):
		""" Get the list of user profiles. """

		self.setup_listener_gettext()

		assert ltrace(TRACE_GET, '> get_profiles(%s,%s)' % (opts, args))

		profiles_to_get = self.select(LMC.profiles, args[1:], opts,
				include_id_lists = [
					(opts.name, LMC.profiles.by_name),
					(opts.group, LMC.profiles.by_group)
				],
				default_selection=filters.ALL)

		if opts.to_script:
			data = LMC.profiles.to_script(selected=profiles_to_get,
										script_format=opts.to_script,
										script_separator=opts.script_sep)

		elif opts.xml:
			data = LMC.profiles.to_XML(profiles_to_get)

		else:
			data = LMC.profiles._cli_get(profiles_to_get)

		if data and data != '\n':
			remote_output(data)

		assert ltrace(TRACE_GET, '< get_profiles()')
	def get_keywords(self, opts, args):
		""" Get the list of keywords. """

		self.setup_listener_gettext()

		assert ltrace(TRACE_GET, '> get_keywords(%s,%s)' % (opts, args))

		if opts.xml:
			data = LMC.keywords.ExportXML()

		else:
			data = LMC.keywords.Export()

		if data and data != '\n':
			remote_output(data)

		assert ltrace(TRACE_GET, '< get_keywords()')
	def get_privileges(self, opts, args):
		""" Return the current privileges whitelist, one priv by line. """

		self.setup_listener_gettext()

		assert ltrace(TRACE_GET, '> get_privileges(%s,%s)' % (opts, args))

		if opts.to_script:
			data = LMC.privileges.to_script(script_format=opts.to_script,
											script_separator=opts.script_sep)

		elif opts.xml:
			data = LMC.privileges.ExportXML()

		else:
			data = LMC.privileges.ExportCLI()

		remote_output(data)

		assert ltrace(TRACE_GET, '< get_privileges()')
	def get_machines(self, opts, args):
		""" Get the list of machines known from the server (attached or not). """

		self.setup_listener_gettext()

		if opts.dump:
			remote_output(LMC.machines.dump())
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

		if opts.to_script:
			data = LMC.machines.to_script(selected=machines_to_get,
											script_format=opts.to_script,
											script_separator=opts.script_sep)

		elif opts.xml:
			data = LMC.machines.ExportXML(selected=machines_to_get,
											long_output=opts.long_output)
		else:
			data = LMC.machines.ExportCLI(selected=machines_to_get,
											long_output=opts.long_output)

		if data and data != '\n':
			remote_output(data)

		assert ltrace(TRACE_GET, '< get_machines()')

	def get_tasks(self, opts, args):
		""" Get the list of tasks. """

		self.setup_listener_gettext()
		assert ltrace(TRACE_GET, '> get_tasks(%s,%s)' % (opts, args))

		if opts.all is False and len(args) == 1:
			opts.all = True
		if opts.all is False and len(args) == 2:
			try:
				tid = int(args[1])
			except:
				tid = LMC.tasks.by_name(args[1]).id

			selection = tid

		if opts.all:
			selection = filters.ALL

		if opts.extinction:
			selection = filters.EXTINCTION_TASK

		else:
			# Running, finished
			pass

		tasks_to_get = LMC.tasks.select(selection)

		if opts.to_script:
			data = LMC.tasks.to_script(selected=tasks_to_get,
											script_format=opts.to_script,
											script_separator=opts.script_sep)
		else:
			data = LMC.tasks._cli_get(selected=tasks_to_get,
										long_output=opts.long_output)

		if data and data != '\n':
			remote_output(data)

		assert ltrace(TRACE_GET, '< get_tasks()')
	def get_configuration(self, opts, args):
		""" Output th current Licorn system configuration. """

		self.setup_listener_gettext()

		assert ltrace(TRACE_GET, '> get_configuration(%s,%s)' % (opts, args))

		if len(args) > 1:
			remote_output(LMC.configuration.Export(args=args[1:],
												cli_format=opts.cli_format))
		else:
			remote_output(LMC.configuration.Export())

		assert ltrace(TRACE_GET, '< get_configuration()')
	def get_events_list(self, opts, args):
		""" Output the list of internal events. """

		self.setup_listener_gettext()

		# we need to merge, because some events have only
		# handlers, and others have only callbacks.
		events_names = set(events.events_handlers.keys()
							+ events.events_callbacks.keys())
		max_name_len = max(len(x) for x in events_names)

		if opts.verbose >= verbose.INFO:
			remote_output(_(u'{0} distinct event(s), {1} handler(s) '
					u'and {2} callback(s)').format(len(events_names),
					sum(len(x) for x in events.events_handlers.itervalues()),
					sum(len(x) for x in events.events_callbacks.itervalues())
					) + u'\n')
			for event_name in events_names:
				handlers  = events.events_handlers.get(event_name, ())
				callbacks = events.events_callbacks.get(event_name, ())

				remote_output(_(u'Event: {0}\n\tHandlers:{1}{2}\n'
						u'\tCallbacks:{3}{4}\n').format(
					stylize(ST_NAME, event_name),
					u'\n\t\t' if len(handlers) else u'',
					u'\n\t\t'.join(_(u'{0} in module {1}').format(
						stylize(ST_NAME, h.__name__),
						stylize(ST_COMMENT, h.__module__)) for h
							in handlers),
					u'\n\t\t' if len(callbacks) else u'',
					u'\n\t\t'.join(_(u'{0} in module {1}').format(
						stylize(ST_NAME, c.__name__),
						stylize(ST_COMMENT, c.__module__)) for c
							in callbacks),
				))
		else:
			for event_name in events_names:
				remote_output(_(u'{0}: {1} handler(s), {2} callback(s).\n').format(
							stylize(ST_NAME, event_name.rjust(max_name_len)),
							len(events.events_handlers.get(event_name, ())),
							len(events.events_callbacks.get(event_name, ())),
						))

	def get_webfilters(self, opts, args):
		""" Get the list of webfilter databases and entries.
			This function wraps SquidGuard configuration files.
		"""

		self.setup_listener_gettext()

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
	def import_users(self, opts, args=None, background=False):
		if background:
			workers.service_enqueue(priorities.NORMAL, self._import_users, opts, args, background)

		else:
			return self._import_users(opts, args, background)
	def _import_users(self, opts, args=None, wmi_output=False):
		try:
			self.__import_users__(opts, args, wmi_output)

		except Exception, e:
			if wmi_output:
				# Let the web user know something went wrong.
				LicornEvent('users_import_failed', error=str(e)).emit(priorities.HIGH)

			# In any case, raise, for the exception
			# to be fully dumped in the daemon's log.
			raise
	def __import_users__(self, opts, args=None, wmi_output=False):
		""" Massively import user accounts from a CSV file."""

		# already done in dispatch_*
		#self.setup_listener_gettext()

		assert ltrace(TRACE_ADD, '> import_user(%s,%s)' % (opts, args))

		if wmi_output:
			wmi_buffer = []

			def _wmi_output(mesg, _wmi_display=False, end=False):
				if end:
					return ''.join(wmi_buffer)

				if _wmi_display:
					wmi_buffer.append(mesg)

			fct_output = _wmi_output

		else:
			fct_output = remote_output


		def clean_csv_field(field):
			return field.replace("'", "").replace('"', '')

		if opts.filename is None:
			raise exceptions.BadArgumentError(
									_(u'You must specify an import filename.'))
		else:
			import_filename = opts.filename

		# a global profile or the profile column has to be set
		if opts.profile is None and opts.profile_col is None:
			raise exceptions.BadArgumentError(_(u'You must specify a profile.'))

		if opts.profile_col is not None:
			profile = None
			profile_col = opts.profile_col
		elif opts.profile is not None:
			profile = opts.profile
			profile_col = None

		# The gecos or the firstname AND lastname has to be set
		if (opts.firstname_col is None or opts.lastname_col is None) and \
			opts.gecos_col is None:
				raise exceptions.BadArgumentError(
						_(u'You must specify the gecos column or the '\
							'lastname column and the firstname column '))

		if opts.gecos_col is not None:
			gecos_col = opts.gecos_col
			firstname_col = None
			lastname_col = None
		else:
			firstname_col = opts.firstname_col
			lastname_col = opts.lastname_col
			gecos_col = None


		# The group column can be unset
		group_col = opts.group_col

		"""if (firstname_col == lastname_col
			or firstname_col == group_col
			or lastname_col == group_col):
			raise exceptions.BadArgumentError(_(u'Two columns have the same '
				'number (lastname={0}, firstname={1}, group={2})').format(
				lastname_col, firstname_col, group_col))"""


		# check the number of columns
		maxval = 0
		columns_dict = []

		if lastname_col is not None:
			columns_dict.append(lastname_col)

		if firstname_col is not None:
			columns_dict.append(firstname_col)

		if gecos_col is not None:
			columns_dict.append(gecos_col)

		if profile_col is not None:
			columns_dict.append(profile_col)

		if group_col is not None:
			columns_dict.append(group_col)

		for number in columns_dict:
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

		if profile is not None:
			try:
				profile = LMC.profiles.guess_one(profile)

				"""self.select(LMC.profiles,
					include_id_lists=[ (profile, LMC.profiles.guess_one) ])[0]"""
			except KeyError:
				raise exceptions.LicornRuntimeException(_(u'The profile "%s" does '
									u'not exist.') % stylize(ST_NAME, profile))

		import math, csv
		from licorn.core.users  import User
		from licorn.core.groups import Group

		# try to detect the separator
		firstline  = open(import_filename).readline()
		lcndialect = csv.Sniffer().sniff(firstline)

		# if a delimiter has been set, use it
		if lcndialect.delimiter != opts.separator and opts.separator != None:
			separator = opts.separator
		else:
			separator = lcndialect.delimiter

		# open the file
		try:
			import_fd = open(import_filename, 'rb')
		except (OSError, IOError), e:
			raise exceptions.LicornRuntimeException(
					_(u'Cannot load CSV file (was: %s).') % e)

		if opts.confirm_import:
			LicornEvent('users_import_started').emit()

		groups_to_add = []
		users_to_add  = []
		fct_output(_(u'Reading input file: '))

		i = 0
		for fdline in import_fd:

			line = fdline[:-1].split(separator)

			columns_ = [('group', group_col),
						('login', opts.login_col),
						('password', opts.password_col)
					]

			# GECOS *always* takes precedence on first/last names. This is
			# arbitrary but documented at 
			# http://docs.licorn.org/cli/add.en.html#massive-accounts-imports-from-files
			if opts.gecos_col is not None:
				columns_.append(('gecos', opts.gecos_col))
			else:
				columns_.append(('firstname', firstname_col))
				columns_.append(('lastname', lastname_col))

			if opts.profile_col is not None:
				columns_.append(('profile', profile_col))

			user = {}
			for (column, number) in columns_:

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

							# depending on the encoding, sometimes we cannot
							# convert unicode into unicode, so check if it is 
							# already unicode.

							if type(line[number]) == types.UnicodeType:
								user[column] = hlstr.validate_name(
										line[number], True)
							else:
								user[column] = hlstr.validate_name(
										unicode(line[number], encoding), True)
						else:
							cleaned_field = clean_csv_field(line[number])
							if not isinstance(cleaned_field, unicode):
								cleaned_field = unicode(cleaned_field, encoding)
							user[column] = cleaned_field

				except IndexError, e:
					raise exceptions.LicornRuntimeError(_(u'Import error on '
							u'line {0}: no {1} specified or bad separator used'
							u'(was: {2}).').format(i + 1, column, e))

				except UnicodeEncodeError, e:
					raise exceptions.LicornRuntimeError(_(u'Encoding not '
						u'supported for input filename (was: %s).') % str(e))

			try:
				if opts.gecos_col is not None:
					user['firstname'] = user['gecos'].split(' ')[0]
					user['lastname']  = " ".join(user['gecos'].split(' ')[1:])

				if opts.login_col is None:
					user['login'] = User.make_login(
										firstname=str(user['firstname']).lower(),
										lastname=str(user['lastname']).lower())
				else:
					user['login'] =	User.make_login(
										inputlogin=user['login'])
			except IndexError, e:
				raise exceptions.LicornRuntimeError(_(u'Import error '
					u'on line {0}: no group specified or bad {2} data '
					u'(was: {1}).').format(i+1, e, (_(u'firstname or lastname')
						if opts.login_col is None else _(u'login'))))

			except exceptions.LicornRuntimeError, e:
				raise exceptions.LicornRuntimeError(_(u'Import error '
								u'on line {0} (was: {1}).').format(i+1, e))

			try:
				if user['group'] is not None:
					user['group'] = [Group.make_name(g) for g in \
						user['group'].split(',') if g != '']

			except IndexError, e:
				raise exceptions.LicornRuntimeError(_(u'Import error '
					u'on line {0}: no group specified or bad {2} data '
					u'(was: {1}).').format(i+1, e, (_(u'firstname or lastname')
						if opts.login_col is None else _(u'login'))))

			except exceptions.LicornRuntimeError, e:
				raise exceptions.LicornRuntimeError(_(u'Import error '
								u'on line {0} (was: {1}).').format(i+1, e))

			if user['group'] is not None:
				groups_to_add.extend([g for g in user['group'] if g not in groups_to_add])

			users_to_add.append(user)

			if not (i % 100):
				fct_output('.')
				# FIXME: how do we force a flush on the client side?
				#sys.stderr.flush()
			i += 1
			user['linenumber'] = i

		assert ltrace(TRACE_ADD,
			'  import_users: users_to_add=%s,\ngroups_to_add=%s' % (
			users_to_add, groups_to_add))

		import_fd.close()

		if profile is not None:
			for u in users_to_add:
				u['profile'] = profile.name

		else:
			all_profiles = []
			print  users_to_add
			for u in users_to_add:
				if u['profile'] not in all_profiles:
					all_profiles.append(u['profile'])

		fct_output(_(u' done.') + '\n')

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

				except exceptions.AlreadyExistsError, e:
					# Error is when a group already exist BUT not the same kind
					logging.warning(str(e), to_local=False)
					progression += delta

				except exceptions.AlreadyExistsException, e:
					# Error is when a group already exist WITH the same kind
					progression += delta

				except exceptions.LicornException, e:
					# FIXME: flush the listener??
					#sys.stdout.flush()
					raise e

				data_to_export_to_html[g]= {}

				# FIXME: flush the listener??
				#sys.stdout.flush()

			if not groups_to_add:
				if profile is None:
					print all_profiles
					for p in all_profiles:
						data_to_export_to_html[p] = {}
				else:
					data_to_export_to_html[profile.group.name] = {}

		else:
			if wmi_output:
				fct_output(_(u'Fields order:'), _wmi_display=True)
				fct_output(_(u'<table>'), _wmi_display=True)
				fct_output(_(u'<tr>'), _wmi_display=True)

				for (header_title, header_width) in [
						(_('FIRSTname'), col_width),
						(_('LASTname'), col_width),
						(_('login'), col_width),
						(_('group'), col_width),
						(_('password'), '') ]:

					fct_output(_(u'<th width="{0}">{1}</th>').format(header_width, header_title), _wmi_display=True)
				fct_output(_(u'</tr>'), _wmi_display=True)

			else:
				import string
				fct_output('\n%s\n%s%s%s%s%s\n' % (
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
					in_groups = [LMC.groups.guess_one(g) for g in u['group']] \
						if u['group'] is not None else []

					_kwargs = {}
					if u.get('gecos', None) is not None:
						_kwargs.update({'gecos' : u['gecos']})
					else:
						_kwargs.update({'firstname' : u['firstname'],
							'lastname' : u['lastname']})



					user, password = LMC.users.add_User(
											login=u['login'],
											password=u['password'],
											profile=LMC.profiles.guess_one(u['profile']),
											in_groups=in_groups,
											batch=opts.no_sync, **_kwargs)

					logging.progress('\r' + _(u'Added user {0} {1} '
						'[login={2}, uid={3}, passwd={4}] ({5}/{6}); '
						'progress: {7}%').format(u['firstname'], u['lastname'],
						user.login, user.uidNumber, u['password'], i,
						length_users, math.ceil(progression)), to_local=False)

					# Get a chance for events to be forwarded,
					# force thread switch in the interpreter.
					time.sleep(0)

					# the dictionnary key is forged to have something that is sortable.
					# like this, the user accounts will be sorted in their group.
					for _group in in_groups:
						data_to_export_to_html[ _group.name ][
								'%s%s' % (u['lastname'], u['firstname'])
							] = [ u['firstname'], u['lastname'],
									user.login, password ]

					if not in_groups:
						if profile is None:
							_profile = u['profile']
						else:
							_profile = profile.group.name

						data_to_export_to_html[_profile][
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
											u'error on line {0}.\n{1}').format(
												u['linenumber'], e))
					if wmi_output:
						fct_output(_(u'<tr>'), _wmi_display=True)

						for text in [
								u['firstname'],
								u['lastname'],
								login,
								u['group'],
								u['password']
									if u['password']
									else _(u'(autogenerated upon creation)')
							]:

							fct_output(_(u'<td>{0}</td>').format(text), _wmi_display=True)
						fct_output(_(u'</tr>'), _wmi_display=True)

					else:
						fct_output("%s%s%s%s%s\n" % (
							string.ljust(u['firstname'], col_width),
							string.ljust(u['lastname'], col_width),
							string.ljust(login, col_width),
							string.ljust(','.join(u['group']), col_width),
							u['password']
								if u['password']
								else _(u'(autogenerated upon creation)')),
							_wmi_display=True)

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

			fct_output(_(u'Finished importing, creating summary HTML file: '))

			groups = data_to_export_to_html.keys()
			groups.sort()

			date_time = time.strftime(_(u'%d %m %Y at %H:%M:%S'), time.gmtime())

			if profile is None:
				# final name of the file contains all impacted profiles
				_profile_ = '_'.join(all_profiles)
			else:
				_profile_ = profile.groupName

			html_file_filename = '%s/import_%s-%s.html' % (
								settings.home_archive_dir,
								# don't take the name, it could have spaces in it.
								_profile_,
								hlstr.validate_name(date_time))

			html_file = open(html_file_filename, 'w')
			if wmi_output:
				dl_lnk = _('''This repport is available on the server '''
					'''at "<code>{0}</code>", you can '''
					'''<a href="/system/download/{0}">'''
					'''download it</a> for easier access''').format(html_file_filename)
			else:
				dl_lnk = ''
				html_file.write('''<html>
					<head>
						<meta http-equiv="content-type" content="text/html; charset=utf-8" />
						<style type="text/css">
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
						</style>
					</head>
					<body>''')

			html_file.write('''
					<h1>{title}</h1>
					<h2>{import_on_date}</h2>
					{download_link}
					<div class="secflaw">{security_flaw}</div>
					<div>{direct_access}'''.format(
					title=_(u'{0} accounts and passwords').format(_profile_),
					import_on_date=_(u'Import made on {0}.').format(date_time),
					security_flaw=_(u'Keeping passwords in any written form '
						'is a major security flaw for you information system.'
						'<br />Please be sure obliterate this file and any '
						'printed version after having transmitted their '
						'password to your users.'),
					download_link= dl_lnk,
					direct_access=_(u'Direct access to {0}:').format(
						LMC.configuration.groups._plural)))

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

				fct_output('.')

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
						fct_output('.')

				html_file.write('</table>\n')

			if not wmi_output:
				html_file.write('</body>\n</html>\n')

			html_file.close()

			fct_output(' %s\n%s %s\n' %(_(u'done.'), _(u'report:'),
					html_file.name))

		if opts.no_sync:
			LMC.groups.serialize()
			LMC.users.serialize()
			LMC.profiles.serialize()

		if opts.confirm_import:
			LicornEvent('users_import_finished',
									result_filename=html_file.name).emit()

		else:
			if wmi_output:
				LicornEvent('users_import_tested',
							import_preview=fct_output('', end=True)).emit()

		gc.collect()
	def add_user(self, opts, args):
		""" Add a user account on the system. """

		# already done in dispatch_*
		#self.setup_listener_gettext()

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
			opts.in_groups = LMC.groups.guess_list(opts.in_groups.split(','), True)
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
						inotified=opts.set_inotified,
						skel=opts.skel,
						batch=opts.batch, force=opts.force,
						shell='/bin/false'
							if opts.disabled_login else opts.shell,
						lastname=lastname, firstname=firstname,
						in_groups=opts.in_groups,
						force_badname=opts.force_badname,
						disabled_password=opts.disabled_password)
				except (exceptions.AlreadyExistsException,
						exceptions.BadArgumentError), e:
					logging.warning(str(e), to_local=False)
		gc.collect()
		assert ltrace(TRACE_ADD, '< add_user()')
	def add_user_in_groups(self, opts, args):

		# already done in dispatch_*
		#self.setup_listener_gettext()

		assert ltrace(TRACE_ADD, '> add_user_in_group().')

		users_to_add = self.select(LMC.users, args[1:], opts,
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

		self.setup_listener_gettext()

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

		self.setup_listener_gettext()

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
						inotified=opts.set_inotified,
						members_to_add=self.select(LMC.users,
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

		self.setup_listener_gettext()

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
						include_id_lists=[(opts.groups, guess_one_group)])
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

		self.setup_listener_gettext()

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		LMC.keywords.AddKeyword(unicode(opts.name), unicode(opts.parent),
			unicode(opts.description))
	def add_privilege(self, opts, args):

		self.setup_listener_gettext()

		if opts.privileges_to_add is None and len(args) == 2:
			opts.privileges_to_add = args[1]
			del args[1]

		include_priv_lists = [
			(opts.privileges_to_add, LMC.groups.guess_one),
		]

		privs_to_add = self.select(LMC.privileges, args[1:], opts,
				include_id_lists=include_priv_lists)

		LMC.privileges.add(privs_to_add)
	def add_machine(self, opts, args):

		self.setup_listener_gettext()

		if opts.auto_scan or opts.discover:
			LMC.machines.scan_network(
				network_to_scan=None if opts.auto_scan else [ opts.discover ])
	def add_task(self, opts, args):

		self.setup_listener_gettext()

		task_name   = opts.name
		task_action = opts.action

		task_year     = opts.year
		task_month    = opts.month
		task_day      = opts.day
		task_hour     = opts.hour
		task_minute   = opts.minute
		task_second   = opts.second
		task_week_day = opts.week_day

		task_defer_resolution   = opts.defer_resolution

		task_delay_until_year   = opts.delay_until_year
		task_delay_until_month  = opts.delay_until_month
		task_delay_until_day    = opts.delay_until_day
		task_delay_until_hour   = opts.delay_until_hour
		task_delay_until_minute = opts.delay_until_minute
		task_delay_until_second = opts.delay_until_second

		if opts.args == '':
			task_args = []

		else:
			# if the task is an extinction_task, guess machines
			if task_action == 'LMC.machines.shutdown':
				try:
					if ';' in opts.args:
						task_args = [ LMC.machines.guess_one(
										LMC.machines.word_match(m)).mid
											for m in opts.args.split(';') ]
					else:
						task_args = [ LMC.machines.guess_one(
										LMC.machines.word_match(opts.args)).mid ]

				except KeyError, e:
					raise exceptions.BadArgumentError(_(u'Unable to resolve '
													u'machine: {0}').format(e))

				except:
					raise exceptions.BadArgumentError(_(u'Error unpacking task '
												u'args {0}'.format(opts.args)))

			else:
				task_args = opts.args.split(';')

		task_kwargs = {}

		if opts.kwargs != '':
			try:
				for kw in opts.kwargs.split(';'):
					_kw = kw.split('=')
					task_kwargs.update({_kw[0]: _kw[1]})

			except Exception, e:
				raise exceptions.BadArgumentError(_(u'Error unpacking task kwarg '
						u'{0} from {1} (was: {2})').format(kw, 	opts.kwargs))

		LMC.tasks.add_task(task_name, task_action,
			year=task_year, month=task_month, day=task_day, hour=task_hour,
			minute=task_minute, second=task_second, week_day=task_week_day,
			delay_until_year=task_delay_until_year,
			delay_until_month=task_delay_until_month,
			delay_until_day=task_delay_until_day,
			delay_until_hour=task_delay_until_hour,
			delay_until_minute=task_delay_until_minute,
			delay_until_second=task_delay_until_second,
			args=task_args, kwargs=task_kwargs,
			defer_resolution=task_defer_resolution)

	def add_volume(self, opts, args):
		""" Modify volumes. """

		self.setup_listener_gettext()

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
	def add_event(self, opts, args):
		""" Modify volumes. """

		self.setup_listener_gettext()

		if opts.event_name is None:
			opts.event_name = args[1]

		events_names = set(events.events_handlers.keys()
							+ events.events_callbacks.keys())

		if opts.event_name not in events_names:
			raise exceptions.BadArgumentError(_(u'Bad event name "{0}". Use '
				u'`get events` to display a list of valid event names.').format(
					opts.event_name))

		if opts.event_args is None:
			opts.event_args = ()

		else:
			opts.event_args = json.loads(opts.event_args)


		if opts.event_kwargs is None:
			opts.event_kwargs = {}

		else:
			opts.event_kwargs = json.loads(opts.event_kwargs)

		if opts.event_priority != None:
			try:
				opts.event_priority = getattr(priorities, opts.event_priority)

			except:
				raise exceptions.BadArgumentError(_(u'Bad priority '
										u'"{0}"').format(opts.event_priority))

		# if 'synchronous' is present in kwargs, the event will be,
		# else it will be backgrounded like any other event.
		LicornEvent(opts.event_name, *opts.event_args,
								**opts.event_kwargs).emit(
										priority=opts.event_priority,
										synchronous=opts.event_synchronous)
	def add_backup(self, opts, args):
		""" Add a backup from CLI. TODO: make this code provided directly
			by the extension. """

		self.setup_listener_gettext()

		match_volname = LMC.extensions.volumes.word_match
		guess_volobj  = LMC.extensions.volumes.guess_one

		something_done = False

		# `args[0]` is 'backup' from 'add backup …' command, we skip it.
		for volname in itertools.chain(*[arg.split(',') if hasattr(arg, 'split')
											else (arg, ) for arg in args[1:]]):
			if volname == '':
				continue

			something_done = True

			try:
				volume = guess_volobj(match_volname(volname))

			except KeyError:
				logging.notice(_(u'No volume matched "{0}". Volume attributes '
					u'are case sensitive.').format(stylize(ST_COMMENT, volname)))

			else:
				try:
					LMC.extensions.rdiffbackup.backup(volume=volume, force=opts.force)

				except exceptions.BadArgumentError, e:
					logging.warning(e)

				except:
					logging.exception(_(u'Exception happened while launching '
								u'backup on volume {0}'), (ST_NAME, volname),
									to_listener=True)
		if not something_done:
			# ask for autodetection of first available volume.
			LMC.extensions.rdiffbackup.backup(force=opts.force)

	### DEL
	def del_user(self, opts, args):
		""" delete one or more user account(s). """

		# already done in dispatch_*
		#self.setup_listener_gettext()

		include_id_lists, exclude_id_lists = self.__default_users_includes_excludes(opts)

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

		users_to_del = self.select(LMC.users, args[1:], opts,
						include_id_lists = include_id_lists,
						exclude_id_lists = exclude_id_lists,
						default_selection = self.__default_users_selection(opts, for_delete=True)
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
		#self.setup_listener_gettext()

		assert ltrace(TRACE_DEL, '> del_users_from_group(%s, %s)' % (opts, args))

		users_to_del = self.select(LMC.users, args[1:], opts,
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

		self.setup_listener_gettext()

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

		self.setup_listener_gettext()

		if opts.filename:
			self.desimport_groups(opts, args)
		else:
			self.del_group(opts, args)
	def desimport_groups(self, opts, args):
		""" Delete the groups (and theyr members) present in a import file.	"""

		# already done in dispatch_*
		#self.setup_listener_gettext()

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
				remote_output('\r' + _(u'Deleting groups ({0}/{1}), '
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
		#self.setup_listener_gettext()

		include_id_lists, exclude_id_lists = self.__default_groups_includes_excludes(opts)

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

		groups_to_del = self.select(LMC.groups, args[1:], opts,
						include_id_lists = include_id_lists,
						exclude_id_lists = exclude_id_lists,
						default_selection=self.__default_groups_selection(opts,
															for_delete=True))

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
	def del_task(self, opts, args):
		self.setup_listener_gettext()
		tasks_to_del = []

		if opts.name is None and len(args) == 2:
			for t in args[1].split(','):
				try:
					tasks_to_del.append(LMC.tasks.guess_one(t))
				except exceptions.DoesntExistException:
					logging.notice("{0} : Unknown task {1}, invalid or "
						"non-existing".format(
						stylize(ST_NAME, LMC.tasks.name),
						stylize(ST_PATH, t)))

			del args[1]

		elif opts.all:
			tasks_to_del = LMC.tasks.select(filters.ALL)
		else:
			if opts.name == None and opts.id == 0:
				logging.warning("{0} : One of the required argument '{1}' or "
					"'{2}' is missing.".format(
					stylize(ST_NAME, LMC.tasks.name),
					stylize(ST_PATH, 'name'),
					stylize(ST_PATH, 'id')), to_local=False)
			elif opts.name != None:
				tasks_to_del = [ LMC.tasks.by_name(opts.name) ]
			elif opts.id != 0:
				try:
					_id = LMC.tasks.by_id(opts.id)
				except exception.DoesntExistException:
					logging.exception('{0} : no task with id {1}'.format(
						stylize(ST_NAME, LMC.tasks.name), stylize(ST_PATH, t_id)))

				tasks_to_del = [ _id ]


		for task in tasks_to_del:
			LMC.tasks.del_task(task.id)
	def del_profile(self, opts, args):
		""" Delete a system wide User profile. """

		self.setup_listener_gettext()

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

		profiles_to_del = self.select(LMC.profiles, args[1:], opts,
				include_id_lists = include_id_lists,
				exclude_id_lists = exclude_id_lists)

		if profiles_to_del is not None:

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

		self.setup_listener_gettext()

		if opts.name is None and len(args) == 2:
			opts.name = args[1]
			del args[1]

		LMC.keywords.DeleteKeyword(opts.name, opts.del_children)
	def del_privilege(self, opts, args):

		self.setup_listener_gettext()

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

		privs_to_del = self.select(LMC.privileges, args[1:], opts,
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

		self.setup_listener_gettext()

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

		self.setup_listener_gettext()

		include_id_lists, exclude_id_lists = self.__default_users_includes_excludes(opts)

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

		users_to_mod = self.select(LMC.users, args[1:], opts,
				include_id_lists = include_id_lists,
				exclude_id_lists = exclude_id_lists,
				default_selection = self.__default_users_selection(opts))

		assert ltrace(TRACE_MOD, '> mod_user(%s)' % ', '.join(user.login for user in users_to_mod))

		something_done = False

		for user in users_to_mod:
			try:
				if opts.non_interactive or opts.batch or opts.force or \
					logging.ask_for_repair(_(u'Modify user %s?') % stylize(
						ST_LOGIN, user.login),
					auto_answer=opts.auto_answer):

					if opts.restore_watch:
						if user.inotified:
							something_done = True
							user._inotifier_add_watch(force_reload=True)

					if opts.newgecos is not None:
						something_done = True
						user.gecos = unicode(opts.newgecos)

					if opts.newshell is not None:
						something_done = True
						user.loginShell = opts.newshell

					if opts.newpassword is not None:
						something_done = True
						user.password = opts.newpassword

					if opts.set_inotified is not None:
						something_done = True
						user.inotified = opts.set_inotified

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
										u'(current) password: ')
								message=_(u'Please enter your new password: ')
								confirm=_(u'Please confirm your new password: ')

							else:
								old_message = _(u"Please enter %s's OLD "
									u"(current) password: ") % stylize(ST_LOGIN, login)

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
								u'do not match, leaving the old one in place.'))

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
										u'user {0} from group {1} '
										u'(was: {2}).').format(
											stylize(ST_LOGIN, user.login),
											stylize(ST_NAME, group.name),
											str(e)), to_local=False)
								except exceptions.LicornException, e:
									raise exceptions.LicornRuntimeError(
										_(u'Unable to remove '
										u'user {0} from group {1} '
										u'(was: {2}).').format(
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
										u'{0} in group {1} (was: {2}).').format(
											stylize(ST_LOGIN, user.login),
											stylize(ST_NAME, group.name),
											str(e)), to_local=False)
								except exceptions.LicornException, e:
									raise exceptions.LicornRuntimeError(
										_(u'Unable to add user '
										u'{0} in group {1} (was: {2}).').format(
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
				u'about user(s) %s ?') % ', '.join(stylize(ST_LOGIN, user.login)
					for user in users_to_mod))
	def __default_users_selection(self, opts, for_get=False, for_delete=False):

		#
		# Default selection when nothing is specified
		# depends on the calling CLI program.
		#
		if for_get:
			selection = filters.STANDARD

		elif for_delete:
			# users must be explicitely selected for del operations.
			selection = filters.NONE

		else:
			# For CHK / MOD, we select the current user by default,
			# this is a comfort option when no name is given on the CLI.
			selection = [ LMC.users.by_login(opts.current_user) ]

		#
		# Then, if something is specified, it takes
		# precedence over the default selection.
		#

		if opts.system:
			selection = filters.SYSTEM

		elif opts.not_system:
			selection = filters.NOT_SYSTEM

		elif opts.inotified:
			selection = filters.INOTIFIED

		elif opts.not_inotified:
			selection = filters.NOT_INOTIFIED

		return selection
	def __default_groups_selection(self, opts, for_delete=False):

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

		elif opts.inotified:
			selection = filters.INOTIFIED

		elif opts.not_inotified:
			selection = filters.NOT_INOTIFIED

		elif not opts.all:
			if not for_delete:
				# by default, we select only standard groups,
				# this is the most common case; except for a delete
				# operation where we select NONE to avoid human errors.
				selection = filters.STANDARD

		return selection
	def __default_users_includes_excludes(self, opts):
		return ([
			(opts.login, lambda x: LMC.users.by_login(x, strong=True)),
			(opts.uid, lambda x: LMC.users.by_uid(x, strong=True))
		], [
			(opts.exclude, lambda x: LMC.users.guess_one(x, strong=True)),
			(opts.exclude_login, lambda x: LMC.users.by_login(x, strong=True)),
			(opts.exclude_uid, lambda x: LMC.users.by_uid(x, strong=True))
		])
	def __default_groups_includes_excludes(self, opts):
		return ([
			(opts.name, lambda x: LMC.groups.by_name(x, strong=True)),
			(opts.gid, lambda x: LMC.groups.by_gid(x, strong=True))
		], [
			(opts.exclude, lambda x: LMC.groups.guess_one(x, strong=True)),
			(opts.exclude_group, lambda x: LMC.groups.by_name(x, strong=True)),
			(opts.exclude_gid, lambda x: LMC.groups.by_gid(x, strong=True))
		])
	def mod_group(self, opts, args):
		""" Modify a group. """

		self.setup_listener_gettext()

		include_id_lists, exclude_id_lists = self.__default_groups_includes_excludes(opts)

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

		groups_to_mod = self.select(LMC.groups, args[1:], opts,
					include_id_lists = include_id_lists,
					exclude_id_lists = exclude_id_lists,
					default_selection = self.__default_groups_selection(opts))

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
							u'handled automatically by standard group move.') %
								stylize(ST_NAME, gname), to_local=False)
					else:
						something_done = True
						group.move_to_backend(opts.move_to_backend,	opts.force)

				if opts.permissive is not None:
					something_done   = True
					group.permissive = opts.permissive

				if opts.set_inotified is not None:
					something_done  = True
					group.inotified = opts.set_inotified

				if opts.restore_watch:
					if group.inotified:
						something_done = True
						group._inotifier_add_watch(force_reload=True)

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
							u'on non-standard group {1}.').format(resps_to_add,
								group.name), to_local=False)

				if opts.resps_to_del:
					if group.is_standard:
						something_done = True
						group.responsible_group.del_Users(
							guess_users_list(sorted(opts.resps_to_del.split(','))),
							force=opts.force)
					else:
						logging.warning(_(u'Skipped responsible(s) {0} deletion '
							u'on non-standard group {1}.').format(resps_to_del,
								group.name), to_local=False)

				if opts.guests_to_add:
					if group.is_standard:
						something_done = True
						group.guest_group.add_Users(
							guess_users_list(sorted(opts.guests_to_add.split(','))),
							force=opts.force)
					else:
						logging.warning(_(u'Skipped guest(s) {0} addition '
							u'on non-standard group {1}.').format(guests_to_add,
								group.name), to_local=False)

				if opts.guests_to_del:
					if group.is_standard:
						something_done = True
						group.guest_group.del_Users(
							guess_users_list(sorted(opts.guests_to_del.split(','))),
							force=opts.force)
					else:
						logging.warning(_(u'Skipped guest(s) {0} deletion '
							u'on non-standard group {1}.').format(guests_to_del,
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
				u'about group(s) %s?') % ', '.join(stylize(ST_NAME, group.name)
					for group in groups_to_mod))
	def mod_profile(self, opts, args):
		""" Modify a system wide User profile. """

		self.setup_listener_gettext()

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

		profiles_to_mod = self.select(LMC.profiles, args[1:], opts,
				include_id_lists = include_id_lists,
				exclude_id_lists = exclude_id_lists)

		assert ltrace(TRACE_MOD, '> mod_profile(%s)' % profiles_to_mod)

		ggi = LMC.groups.guess_list
		def gui(x):
			return LMC.users.guess_one(x, True)

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
					profile.del_Groups(ggi(sorted(opts.groups_to_del.split(',')), True),
										instant_apply=opts.instant_apply)

				if opts.groups_to_add is not None:
					something_done = True
					profile.add_Groups(ggi(sorted(opts.groups_to_add.split(',')), True),
										instant_apply=opts.instant_apply)

				local_include_id_lists = []

				if opts.apply_to_members:
					something_done = True
					local_include_id_lists.append((profile.group.gidMembers, lambda x: x))

				if opts.apply_to_users is not None:
					local_include_id_lists.append(
						(opts.apply_to_users.split(','), gui))

				if opts.apply_to_groups is not None:
					for group in ggi(sorted(opts.apply_to_groups.split(','))):
						local_include_id_lists.append(
							(group.all_members, lambda x: x))

				if opts.apply_all_attributes or opts.apply_skel or opts.apply_groups:

					_users = self.select(LMC.users,
							include_id_lists = local_include_id_lists,
							exclude_id_lists = [
								(opts.exclude, gui),
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

		self.setup_listener_gettext()

		if opts.all:
			selection = host_status.ALL
		else:
			selection = host_status.ONLINE

			if opts.idle:
				selection |= host_status.IDLE

			if opts.asleep:
				selection |= host_status.ASLEEP

			if opts.active:
				selection |= host_status.ACTIVE

		mids_to_mod = self.select(LMC.machines, args[1:], opts,
				include_id_lists = [
					(opts.hostname, LMC.machines.by_hostname),
					(opts.mid, LMC.machines.has_key)
				],
				default_selection=selection)

		for machine in mids_to_mod:
			try:
				if opts.shutdown:
					machine.shutdown(warn_users=opts.warn_users)
				if opts.do_upgrade:
					machine.do_upgrade()
			except:
				logging.exception('Failed to operate on machine {0}.', (ST_NAME, machine.hostname))
	def mod_task(self, opts, args):
		""" Modify a machine. """

		self.setup_listener_gettext()

		remote_output("{0}, please delete the task you want to modify and "
		"create a new one. \n\t {1} : You can easily modify the configuration "
		"file to change few arguments of a task.\n".format(
			stylize(ST_BAD, 'Not implemented'), stylize(ST_OK, "TIP")))
	def mod_keyword(self, opts, args):
		""" Modify a keyword. """

		self.setup_listener_gettext()

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

		self.setup_listener_gettext()

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

		self.setup_listener_gettext()


		if opts.setup_shared_dirs:
			LMC.configuration.check_base_dirs(minimal=False, batch=True)

		if opts.set_hostname:
			LMC.configuration.ModifyHostname(opts.set_hostname)

		if opts.set_ip_address:
			raise exceptions.NotImplementedError(
				"changing server IP address is not yet implemented.")

		if opts.privileges_to_add:
			LMC.privileges.add(sorted(opts.privileges_to_add.split(',')))

		if opts.privileges_to_remove:
			LMC.privileges.delete(sorted(opts.privileges_to_remove.split(',')))

		if opts.hidden_groups != None:
			LMC.configuration.SetHiddenGroups(opts.hidden_groups)

		#FIXME: refactor the next 4 blocks
		# don't sort the backends, the order is probably important.

		if opts.disable_backends != None:
			for backend in opts.disable_backends.split(','):
				try:
					LMC.backends.disable_backend(LMC.backends.word_match(backend))

				except exceptions.DoesntExistException:
					logging.warning(_(u'Skipped non-existing backend %s.') %
						stylize(ST_NAME, backend), to_local=False)

		if opts.enable_backends != None:
			for backend in opts.enable_backends.split(','):
				try:
					LMC.backends.enable_backend(LMC.backends.word_match(backend))

				except exceptions.DoesntExistException:
					logging.warning(_(u'Skipped non-existing backend %s.') %
						stylize(ST_NAME, backend), to_local=False)

		if opts.disable_extensions != None:
			for extension in opts.disable_extensions.split(','):
				try:
					LMC.extensions.disable_extension(LMC.extensions.word_match(extension))

				except exceptions.DoesntExistException:
					logging.warning(_(u'Skipped non-existing extension %s.') %
						stylize(ST_NAME, extension), to_local=False)

		if opts.enable_extensions != None:
			for extension in opts.enable_extensions.split(','):
				try:
					LMC.extensions.enable_extension(LMC.extensions.word_match(extension))

				except exceptions.DoesntExistException:
					logging.warning(_(u'Skipped non-existing extension %s.') %
						stylize(ST_NAME, extension), to_local=False)
	def mod_volume(self, opts, args):
		""" Modify volumes. """

		self.setup_listener_gettext()

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

		assert ltrace_func(TRACE_CHK)

		self.setup_listener_gettext()

		include_id_lists, exclude_id_lists = self.__default_users_includes_excludes(opts)

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

		users_to_chk = self.select(LMC.users, args[1:], opts,
			include_id_lists = include_id_lists,
			exclude_id_lists = exclude_id_lists,
			default_selection = self.__default_users_selection(opts),
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

		self.setup_listener_gettext()

		include_id_lists, exclude_id_lists = self.__default_groups_includes_excludes(opts)

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

		groups_to_chk = self.select(LMC.groups, args[1:], opts,
			include_id_lists = include_id_lists,
			exclude_id_lists = exclude_id_lists,
			default_selection = self.__default_groups_selection(opts),
			all=opts.all)

		assert ltrace(TRACE_CHK, '> chk_group(%s)' % groups_to_chk)

		if groups_to_chk != []:
			if opts.force or opts.batch or opts.non_interactive:
				LMC.groups.chk_Groups(groups_to_chk,
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

		self.setup_listener_gettext()

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

		profiles_to_del = self.select(LMC.profiles, args[1:], opts,
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

		self.setup_listener_gettext()

		LMC.configuration.check(opts.minimal, batch=opts.batch,
									auto_answer=opts.auto_answer)

		if not opts.minimal:
			from licorn.upgrades import common as upgrades_common

			upgrades_common.check_pip_perms(batch=opts.batch,
											auto_answer=opts.auto_answer)
	def chk_system(self, opts, args):

		self.setup_listener_gettext()

		if opts.wmi_test_apps:
			self.chk_system_wmi_tests([app for app in opts.wmi_test_apps.split(',') if app != ''])
	def chk_system_wmi_tests(self, apps):
		""" Launch one or more DJango WMI testsuite in the daemon.

			this
		"""

		if not settings.experimental.enabled:
			logging.warning(_(u'Django WMI tests are not meant to be run on a '
						u'production system. If you really want to, set {0} in '
						u'{1}, and prepare to see your daemon restart after '
						u'each run.').format(
							stylize(ST_COMMENT, 'experimental.enabled = True'),
							stylize(ST_PATH, settings.main_configuration_file)
						)
					)

			return

		self.setup_listener_gettext()

		# `execute_manager` will fail without the PYTHONPATH including our
		# project. But this should have already been done when the WMI launched.
		#sys.path.extend(['licorn.interfaces', 'licorn.interfaces.wmi'])

		# avoid unittest setting up signal handlers, this won't work.
		from licorn.foundations.testutils import monkey_patch_unittest; monkey_patch_unittest()

		# we rename the Django settings to `djsettings` not to
		# clash with `licorn.foundations.settings`.
		from licorn.interfaces.wmi  import wmi_event_app, django_setup, settings as djsettings
		from django.core.management import execute_manager

		verbose_equivalent_levels = {
				# We use '-v0' as a starting point, not '-v1', to not pollute
				# the output with dots or whatever, there is enough from the
				# CLI messages in the daemon and locally.
				verbose.NOTICE:		0,
				verbose.INFO:		1,
				verbose.PROGRESS: 	2,
				verbose.DEBUG:		3,
				# 3 is the max. level in Django / unittest.
				verbose.DEBUG2:		3,
			}

		django_setup()

		if apps in ([], [ 'all' ]):
			apps = wmi_event_app.django_apps_list()

		for app in apps:
			logging.notice(_(u'Running WMI Django tests for app {0}, '
					u'this may take a while…').format(stylize(ST_NAME, app)))

			something_done = False

			try:
				# we must put 'manage.py' in the arguments for Django
				# to lookup correctly the commands set for this utility.
				#
				execute_manager(djsettings, [ 'manage.py', 'test', '-v%s' %
					verbose_equivalent_levels[current_thread().listener.verbose], app ])

				something_done = True

			except SystemExit:
				# We won't exit, this is not the point when running this
				# testsuite *in the daemon*. But can't tell `execute_manager`
				# to avoid it, thus we must trap it and ignore it.
				pass

			except:
				logging.exception(_(u'Could not run tests for app {0}.'), (ST_NAME, app))
				continue

			logging.notice(_(u'Successfully ran Django WMI tests '
							u'for app {0}.').format(stylize(ST_NAME, app)))

		#
		# TODO: remove this 'restart' when #769 is fixed.
		#
		#if something_done and ('users' in apps or 'groups' in apps):
			# Until http://dev.licorn.org/ticket/769 is fixed, running the
			# Django WMI testsuite triggers the bug, we must restart.
			#LicornEvent('need_restart',
			#			reason=reasons.INTERNAL_LEAK).emit(priorities.HIGH)
