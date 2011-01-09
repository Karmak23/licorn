# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

argparser - command-line argument parser library.
Contains all argument parsers for all licorn system tools (get, add, modify, delete, check)

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Copyright (C) 2005,2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""
import os, getpass

from optparse import OptionParser, OptionGroup, SUPPRESS_HELP

from licorn.foundations           import exceptions
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import LicornConfigObject
from licorn.foundations.pyutils   import add_or_dupe_obj
from licorn.foundations.argparser import build_version_string, \
	common_behaviour_group

from licorn.core import LMC, version

### General / common arguments ###
def common_filter_group(app, parser, tool, mode):
	"""Build Filter OptionGroup for all get variants."""

	big_help_string = (
		""" WARNING: filters are only partially cumulative. Order """
		"""of operations: %s %s """
		"""takes precedence on other inclusive filters (if it is """
		"""present, any other inclusive filter is purely discarded). In this """
		"""case, %s is equal to all %s. %s if %s is not used, other """
		"""inclusive filters are union'ed to construct the %s of """
		"""%s. %s Then all exclusive filters are union'ed in turn too, to """
		"""construct an %s of %s. %s The %s is """
		"""substracted from the %s, and the result is used in the """
		"""calling CLI tool to operate onto.""" % (
			stylize(ST_LIST_L1, '(1)'),
			stylize(ST_NOTICE, '--all'),
			stylize(ST_DEFAULT, 'include_list'),
			mode,
			stylize(ST_LIST_L1, '(2)'),
			stylize(ST_NOTICE, '--all'),
			stylize(ST_DEFAULT, 'include_list'),
			mode,
			stylize(ST_LIST_L1, '(3)'),
			stylize(ST_DEFAULT, 'exclude_list'),
			mode,
			stylize(ST_LIST_L1, '(4)'),
			stylize(ST_DEFAULT, 'exclude_list'),
			stylize(ST_DEFAULT, 'include_list')
			)
		)

	filtergroup = OptionGroup(parser,
		stylize(ST_OPTION, "Filter options"),
		"""Filter %s.%s""" % (mode,
			big_help_string if mode != 'configuration' else '')
		)

	if tool in ('get', 'mod', 'del') :
		if mode in ( 'users', 'groups', 'profiles', 'privileges', 'machines'):
			filtergroup.add_option('-a', '--all',
				action="store_true", dest="all", default=False,
				help="""Also select system data. I.e. """
					"""output system %s too.""" % mode)
			filtergroup.add_option('-X', '--not', '--exclude',
				action="store", dest="exclude", default=None,
				help='''exclude %s from the selection. Can be IDs or %s '''
					'''names. Separated by commas without spaces.''' % (mode,
					mode[:-1]))

	if tool is 'get':
		if mode in ('daemon_status', 'users', 'groups', 'machines'):
			filtergroup.add_option('-l', '--long', '--full',
				action="store_true", dest="long", default=False,
				help='''long output (all info, attributes, etc). '''
					'''NOT enabled by default.''')
		if mode == 'daemon_status':
			filtergroup.add_option('--detail', '--details',
				'-p', '--precision', '--precisions', '--pinpoint',
				action="store", dest="precision", default=None,
				help='''long output (all info, attributes, etc). '''
					'''NOT enabled by default.''')

	if tool is 'chk':
		if mode in ( 'users', 'groups', 'configuration', 'profiles'):
			filtergroup.add_option('-a', '--all',
				action="store_true", dest="all", default=False,
				help="""%s"""
					""" %s: this can be a very long operation"""
					"""%s""" % (
						"""Check *all* %s on the system.""" %
							stylize(ST_MODE, mode) \
							if mode != 'configuration' \
							else 'Check every bit of the configuration.',
						stylize(ST_IMPORTANT, "WARNING"),
						""", depending of the current number of %s.""" %
							mode if mode != 'configuration' else ''))
		if mode in ('users', 'groups', 'profiles'):
			filtergroup.add_option('-X', '--not', '--exclude',
				action="store", dest="exclude", default=None,
				help='''exclude %s from the selection. Can be IDs or %s '''
					'''names. Separated by commas without spaces.''' % (mode,
					mode[:-1]))

	if mode is 'users':
		filtergroup.add_option('--login', '--logins', '--username',
			'--usernames', '--name', '--names',
			action="store", type="string", dest="login", default=None,
			help="""Specify user(s) by their login (separated by commas """
				"""without spaces).""")
		filtergroup.add_option('--uid', '--uids',
			action="store", type="string", dest="uid", default=None,
			help="""Specify user(s) by their UID (separated by commas """
				"""without spaces).""")

	if mode is 'users' or (tool is 'mod' and mode is 'profiles'):
		filtergroup.add_option('--system', '--system-groups', '--sys',
			action="store_true", dest="system", default = False,
			help="Only select system user.")
		filtergroup.add_option('--no-sys', '--not-sys', '--no-system',
			'--not-system', '--exclude-sys','--exclude-system',
			action="store_true", dest="not_system", default = False,
			help="Only select non-system users.")
		filtergroup.add_option('--not-user',
			'--exclude-user', '--not-users',
			'--exclude-users', '--not-login',
			'--exclude-login', '--not-logins',
			'--exclude-logins',  '--not-username',
			'--exclude-username', '--not-usernames',
			'--exclude-usernames',
			action="store", type="string", dest="exclude_login", default=None,
			help='''Specify user(s) to exclude from current operation, by '''
				'''their *login* (separated by commas without spaces).''')
		filtergroup.add_option('--not-uid', '--exclude-uid',
			'--not-uids', '--exclude-uids',
			action="store", type="string", dest="exclude_uid", default=None,
			help='''Specify user(s) to exclude from current operation by '''
				'''their UID (separated by commas without spaces).''')

	if mode is 'groups':
		filtergroup.add_option('--name', '--names', '--group', '--groups',
			'--group-name', '--group-names',
			action="store", type="string", dest="name", default=None,
			help="""Specify group(s) by their name (separated by commas """
				"""without spaces).""")
		filtergroup.add_option('--gid', '--gids',
			action="store", type="string", dest="gid", default=None,
			help="""Specify group(s) by their GID (separated by commas """
				"""without spaces).""")

		if tool in ('get', 'mod', 'del', 'chk'):
			filtergroup.add_option('--system', '--system-groups', '--sys',
				action="store_true", dest="system", default = False,
				help="Only select system groups.")
			filtergroup.add_option('--no-sys', '--not-sys', '--no-system',
				'--not-system', '--exclude-sys','--exclude-system',
				action="store_true", dest="not_system", default = False,
				help="Only select non-system groups.")
			filtergroup.add_option('--privileged', '--priv', '--privs', '--pri',
				'--privileged-groups',
				action="store_true", dest="privileged", default = False,
				help="Only select privileged groups.")
			filtergroup.add_option('--no-priv', '--not-priv', '--no-privs',
				'--not-privs', '--no-privilege', '--not-privilege',
				'--no-privileges', '--not-privileges ', '--exclude-priv',
				'--exclude-privs','--exclude-privilege','--exclude-privileges',
				action="store_true", dest="not_privileged", default = False,
				help="Only select non-privileged groups.")
			filtergroup.add_option('--responsibles', '--rsp',
				'--responsible-groups',
				action="store_true", dest="responsibles", default = False,
				help="Only select responsibles groups.")
			filtergroup.add_option('--no-rsp', '--not-rsp', '--no-resp',
				'--not-resp', '--not-responsible', '--no-responsible',
				'--exclude-responsible', '--exclude-resp', '--exclude-rsp',
				action="store_true", dest="not_responsibles", default = False,
				help="Only select non-responsible groups.")
			filtergroup.add_option('--guests', '--gst', '--guest-groups',
				action="store_true", dest="guests", default = False,
				help="Only select guests groups.")
			filtergroup.add_option('--no-gst', '--not-gst', '--no-guest',
				'--not-guest', '--exclude-gst','--exclude-guest',
				action="store_true", dest="not_guests", default = False,
				help="Only select non-guest groups.")
			filtergroup.add_option('--empty', '--empty-groups',
				action="store_true", dest="empty", default = False,
				help="Only select empty groups.")



	if mode is 'groups' or (tool is 'mod' and mode is 'profiles'):
		filtergroup.add_option('--not-group',
			'--exclude-group', '--not-groups',
			'--exclude-groups', '--not-groupname',
			'--exclude-groupname', '--not-groupnames',
			'--exclude-groupnames',
			action="store", type="string", dest="exclude_group", default=None,
			help='''Specify group(s) to exclude from current operation, by '''
				'''their *name* (separated by commas without spaces).''')
		filtergroup.add_option('--not-gid', '--exclude-gid',
			'--not-gids', '--exclude-gids',
			action="store", type="string", dest="exclude_gid", default=None,
			help='''Specify group(s) to exclude from current operation by '''
				'''their *GID* (separated by commas without spaces).''')

	if mode is 'profiles':
		filtergroup.add_option('--profile', '--profiles', '--profile-name',
			'--profile-names', '--name', '--names',
			action="store", type="string", dest="name", default=None,
			help="""Specify profile by its common name (separated by commas """
				"""without spaces, when possible. If name contains spaces, """
				"""use --group instead). %s.""" %
				stylize(ST_IMPORTANT,
					"one of --name or --group is required"))
		filtergroup.add_option('--group', '--groups', '--profile-group',
			'--profile-groups',
			action="store", type="string", dest="group", default=None,
			help="""specify profile by its primary group (separated by """
				"""commas without spaces).""")

	if mode is 'machines':
		filtergroup.add_option('--hostname', '--hostnames', '--name', '--names',
			'--client-name', '--client-names',
			action="store", type="string", dest="hostname", default=None,
			help="""Specify machine(s) by their hostname (separated by """
				"""commas without spaces).""")
		filtergroup.add_option('--mid', '--mids', '--ip', '--ips',
			'--ip-address', '--ip-addresses',
			action="store", type="string", dest="mid", default=None,
			help="""Specify machine(s) by their IP address (separated by """
				"""commas without spaces).""")

		if tool in ('get', 'mod', 'del', 'chk'):
			filtergroup.add_option('--asleep', '--asleep-machines',
				action="store_true", dest="asleep", default = False,
				help="Only select asleep machines.")
			filtergroup.add_option('--idle', '--idle-machines',
				action="store_true", dest="idle", default = False,
				help="Only select idle machines.")
			filtergroup.add_option('--active', '--active-machines',
				action="store_true", dest="active", default = False,
				help="Only select active machines.")

	return filtergroup
def check_opts_and_args(parse_args):
	opts, args = parse_args

	if len(LMC.rwi.groups_backends()) <= 1:
		opts.in_backend = None
		opts.move_to_backend = None

	if opts.force and opts.batch:
		raise exceptions.BadArgumentError('''options --force and '''
		'''--batch are mutually exclusive''')
	else:
		return (opts, args)
def general_parse_arguments(app):
	"""Common options and arguments to all Licorn System Tools,
		with specialties."""

	# FIXME: 20100914 review this function, its contents seems outdated.

	usage_text = "\n\t%s [[%s] …] [[%s] …]\n\n\t%s is one of: " \
		% (	stylize(ST_APPNAME, "%prog"),
			stylize(ST_MODE, "mode"),
			stylize(ST_OPTION, "options"),
			stylize(ST_MODE, "mode"))

	if app["name"] == "licorn-get":
		usage_text +=  "[daemon_]status, "

	if app["name"] in ( "licorn-get", "licorn-modify", "licorn-check" ):
		usage_text +=  "conf[ig[uration]], "

	if app["name"] in ( "licorn-get", "licorn-check" ):
		usage_text += '''user[s]|group[s]|profile[s]|kw|keyword[s]|tag[s]''' \
			'''|priv[ilege][s]|machine[s]|client[s].'''

	else:
		usage_text += "user, "
		if app["name"] == "licorn-add":
			usage_text += "users (massive imports), "
		usage_text	+= "group, profile."

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	return parser.parse_args()

### Getent arguments ###
def __get_output_group(app, parser, mode):
	"""TODO"""

	outputgroup = OptionGroup(parser,
		stylize(ST_OPTION, "Output options "),
			"Modify how data is printed/exported.")

	if mode is 'configuration':
		outputgroup.add_option("-s", "--short",
			action="store_const", const = "short", dest="cli_format",
			default="short",
			help='''Like previous option, but export the configuration '''
				'''subset in the shortest form factor (only the values '''
				'''when possible ; %s).''' %
				stylize(ST_DEFAULT, "this is the default") )
		outputgroup.add_option("-b", "--bourne-shell",
			action="store_const", const = "bourne", dest="cli_format",
			default="short",
			help='''When using configuration %s to output a subset of the '''
				'''system configuration, export it in a useful way to be '''
				'''used in a bourne shell environment (i.e. export '''
				'''VAR=\"value\").''' %
					stylize(ST_OPTION, "sub-category"))
		outputgroup.add_option("-c", "--c-shell",
			action="store_const", const = "cshell", dest="cli_format",
			default="short",
			help='''Like previous option, but export the configuration '''
				'''subset in a useful way to be used in a C shell '''
				'''environment (i.e. setenv VAR \"value\").''')
		outputgroup.add_option("-p", "--php-code",
			action="store_const", const = "PHP", dest="cli_format",
			default="short",
			help='''Like previous option, but export the configuration '''
				'''subset in a usefull way to be included in PHP code (i.e. '''
				'''$VAR=\"value\", use it with eval(`…`)).''')
	else:
		outputgroup.add_option("-x", "--xml",
			action="store_true", dest="xml", default=False,
			help='''Output data as XML (no colors, no verbose). If not set, '''
				'''%s (for human beiings, but not easily parsable format).''' %
				stylize(ST_DEFAULT,
					"default is to output for CLI"))

		outputgroup.add_option('-d', "--dump",
			action="store_true", dest="dump", default=False,
			help='''Dump nearly RAW data on stdout. Used for debugging '''
				'''internal data structures.''')

	return outputgroup
def get_users_parse_arguments(app):
	""" Integrated help and options / arguments for « get user(s) »."""

	usage_text = "\n\t%s %s [[%s] …]" \
		% (
			stylize(ST_APPNAME, "%prog"),
			stylize(ST_MODE, "users"),
			stylize(ST_OPTION, "option")
		)

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(common_filter_group(app, parser, 'get', 'users'))
	parser.add_option_group(__get_output_group(app, parser,'users'))

	return parser.parse_args()
def get_privileges_parse_arguments(app):
	""" Integrated help and options / arguments for « get user(s) »."""

	usage_text = "\n\t%s %s" \
		% (
			stylize(ST_APPNAME, "%prog"),
			stylize(ST_MODE, "priv[ilege][s]")
		)

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	# no filter yet for privileges
	#parser.add_option_group(common_filter_group(app, parser, 'get', 'privileges'))
	parser.add_option_group(__get_output_group(app, parser,'privileges'))

	return parser.parse_args()
def get_groups_parse_arguments(app):
	""" Integrated help and options / arguments for « get group(s) »."""

	usage_text = "\n\t%s %s [[%s] …]" \
		% (
			stylize(ST_APPNAME, "%prog"),
			stylize(ST_MODE, "groups"),
			stylize(ST_OPTION, "option")
		)

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(common_filter_group(app, parser, 'get', 'groups'))
	parser.add_option_group(__get_output_group(app, parser,'groups'))

	return parser.parse_args()
def get_keywords_parse_arguments(app):
	""" Integrated help and options / arguments for « get keyword(s) »."""

	usage_text = "\n\t%s %s [[%s] …]" \
		% (
			stylize(ST_APPNAME, "%prog"),
			stylize(ST_MODE, "keywords"),
			stylize(ST_OPTION, "option")
		)

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(__get_output_group(app, parser,'keywords'))

	return parser.parse_args()
def get_profiles_parse_arguments(app):
	""" Integrated help and options / arguments for « get profile(s) »."""

	usage_text = "\n\t%s %s [[%s] …]" \
		% (
			stylize(ST_APPNAME, "%prog"),
			stylize(ST_MODE, "profiles"),
			stylize(ST_OPTION, "option")
		)

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(common_filter_group(app, parser, 'get', 'profiles'))
	parser.add_option_group(__get_output_group(app, parser,'profiles'))

	return parser.parse_args()
def get_machines_parse_arguments(app):
	""" Integrated help and options / arguments for « get user(s) »."""

	usage_text = "\n\t%s %s [[%s] …]" \
		% (
			stylize(ST_APPNAME, "%prog"),
			stylize(ST_MODE,
				"client[s]|machine[s]|workstation[s]"),
			stylize(ST_OPTION, "option")
		)

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(common_filter_group(app, parser, 'get', 'machines'))
	parser.add_option_group(__get_output_group(app, parser,'machines'))

	return parser.parse_args()
def get_configuration_parse_arguments(app):
	""" Integrated help and options / arguments for « get »."""

	usage_text = "\n\t%s config [[%s] …]\n" % (
		stylize(ST_APPNAME, "%prog"),
		stylize(ST_OPTION, "option")) \
		+ "\t%s config [[%s] …] %s [--short|--bourne-shell|--c-shell|--php-code] ]\n" % (
		stylize(ST_APPNAME, "%prog"),
		stylize(ST_OPTION, "option"),
		stylize(ST_OPTION, "category")) \
		+ ('''%s is one of: app_name, names, shells, skels, '''
			'''priv|privs|privileges, config_dir, '''
			'''sysgroups|system_group|system-groups '''
			'''main_config_file, extendedgroup_data_file.''' % \
				stylize(ST_OPTION, "category"))

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(__get_output_group(app, parser, 'configuration'))

	return parser.parse_args()
def get_volumes_parse_arguments(app):
	""" Integrated help and options / arguments for « get »."""

	usage_text = "\n\t%s volumes\n" % (
		stylize(ST_APPNAME, "%prog"))

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(__get_output_group(app, parser, 'volumes'))

	return parser.parse_args()
def parse_daemon_precision(precision):
	""" split a precision string and build a precision bare pseudo object for
		detailled daemon status. """

	if precision is None:
		return None

	precision_obj = LicornConfigObject()
	values = precision.split(',')

	for value in values:
		vtype, vident = value.split(':')
		if vtype in ('g', 'grp', 'group'):
			vtype = 'groups'
		elif vtype in ('u', 'usr', 'user'):
			vtype = 'users'
		else:
			# unknown vtype, skip
			continue

		add_or_dupe_obj(precision_obj, vtype, vident)

	return precision_obj
def get_daemon_status_parse_arguments(app):
	""" Integrated help and options / arguments for « get »."""

	usage_text = "\n\t%s daemon_status [--full|--long]\n" % (
		stylize(ST_APPNAME, "%prog"))
	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(
		common_filter_group(app, parser, 'get', 'daemon_status'))
	parser.add_option_group(__get_output_group(app, parser, 'daemon_status'))

	opts, args = parser.parse_args()

	opts.precision = parse_daemon_precision(opts.precision)

	return opts, args
### Add arguments ###
def add_user_parse_arguments(app):
	"""Integrated help and options / arguments for « add user »."""

	assert ltrace('argparser', '> add_user_parse_arguments()')

	usage_text = """
	%s user [--login] <login>
	%s user [-s|--system] [-p|--password "<password>"]
		[-g|--gid=<primary_gid>] [-r|--profile=<profile>] [-K|--skel=<skel>]
		[-e|--gecos=<given name>] [-H|--home=<home_dir>] […]""" % (
			stylize(ST_APPNAME, "%prog"),
			stylize(ST_APPNAME, "%prog"))

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'add_user'))

	user = OptionGroup(parser,
		stylize(ST_OPTION, "Add user options "))

	user.add_option('-l', "--login", "--name",
		action="store", type="string", dest="login", default=None,
		help="""Specify user's login (%s).""" % stylize(
			ST_IMPORTANT,
			"one of login or firstname+lastname arguments is required"))
	user.add_option('-e', "--gecos",
		action="store", type="string", dest="gecos", default=None,
		help="""Specify user's GECOS field. If given, GECOS takes precedence """
			"""on --firstname and --lastname, which will be silently """
			"""discarded. Default: autogenerated from firstname & lastname """
			"""if given, else from login.""")
	user.add_option('-p', "--password",
		action="store", type="string", dest="password", default=None,
		help="""Specify user's password (else will be autogenerated, %d """
			"""chars long).""" % LMC.configuration.users.min_passwd_size)
	user.add_option('-g', '--in-group', '--primary-group', '--gid',
			'--primary-gid', '--group',
		action="store", type="string", dest="primary_gid", default=None,
		help="""Specify user's future primary group (at your preference as """
			"""a group name or a GID). This parameter is overriden by the """
			"""profile argument if you specify both. Default: %s.""" %
				LMC.configuration.users.default_gid)
	user.add_option('-G', '--in-groups', '--auxilliary-groups',
		'--add-to-groups', '--aux-groups', '--secondary-groups', '--groups',
		action="store", type="string", dest="in_groups", default=None,
		help='''Specify future user's auxilliary groups (at your preference '''
			'''as groupnames or GIDs, which can be mixed, and separated by '''
			'''commas without spaces). These supplemental groups are added '''
			'''to the list of groups defined by the profile, if you specify '''
			'''both. Default: None.''')
	user.add_option('-s', "--system",
		action="store_true", dest="system", default = False,
		help="Create a system account instead of a standard user (root only).")

	user.add_option('-r', "--profile",
		action="store", type="string", dest="profile", default=None,
		help="""Profile which will be applied to the user. Default: None, """
			"""overrides primary group / GID.""")

	user.add_option('-u', "--uid", '--desired-uid',
		action="store", type="int", dest="uid", default=None,
		help="""manually specify an UID for the new user. This UID must be """
			"""free and inside the range %s - %s for a standard user, and """
			"""outside the range for a system account, else it will be """
			"""rejected and the user account won't be created. Default: """
			"""next free UID in the selected range.""" % (
			stylize(ST_DEFAULT, LMC.configuration.users.uid_min),
			stylize(ST_DEFAULT, LMC.configuration.users.uid_max)))
	user.add_option('-H', "--home",
		action="store", type="string", dest="home", default=None,
		help="""Specify the user's home directory. Only valid for a system """
			"""account, else discarded because standard accounts have a """
			"""fixed home dir %s/<login>""" % LMC.configuration.users.base_path)
	user.add_option("-S", "--shell",
		action="store", type="string", dest="shell", default=None,
		help="""Specify user's shell, from the ones given by command """
			"""`get config shells`. Default: %s""" %
			LMC.configuration.users.default_shell)
	user.add_option('-K', "--skel",
		action="store", type="string", dest="skel", default=None,
		help="""Specify a particular skeleton to apply to home dir after """
			"""creation, instead of the profile or the primary-group """
			"""implicit skel. Default: the profile skel if profile given, """
			"""else %s.""" % LMC.configuration.users.default_skel)
	user.add_option("--firstname",
		action="store", type="string", dest="firstname", default=None,
		help="""Specify user's first name (required if --lastname is given,"""
			"""overriden by GECOS).""")
	user.add_option("--lastname",
		action="store", type="string", dest="lastname", default=None,
		help="""Specify user's last name (required if --firstname is given, """
			"""overriden by GECOS).""")
	user.add_option("--no-create-home",
		action="store_true", dest="no_create_home", default = False,
		help="")
	user.add_option("--disabled-password",
		action="store_true", dest="disabled_password", default = False,
		help="")
	user.add_option("--disabled-login",
		action="store_true", dest="disabled_login", default = False,
		help="")

	parser.add_option_group(user)

	assert ltrace('argparser', '< add_user_parse_arguments()')

	return parser.parse_args()
def add_group_parse_arguments(app):
	"""Integrated help and options / arguments for « add group »."""

	assert ltrace('argparser', '> add_group_parse_arguments()')

	usage_text = "\n\t%s group --name=<nom_groupe> [--permissive] [--gid=<gid>]\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t\t[--skel=<nom_squelette>] [--description=<description>]\n" \
		+ "\t\t[--system]"

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'add_group'))

	group = OptionGroup(parser,
		stylize(ST_OPTION, 'Add group options '))

	group.add_option('--name',
		action='store', type='string', dest='name', default=None,
		help="Specify group's name (%s)." %
			stylize(ST_IMPORTANT, 'required') )
	group.add_option('-p', '--permissive',
		action="store_true", dest="permissive", default=False,
		help="The shared group directory will be permissive (default is %s)." %
			stylize(ST_DEFAULT, "not permissive"))
	group.add_option('-g', '--gid',
		action="store", type="int", dest="gid", default=None,
		help="Specify the GID (root / @admin members only).")
	group.add_option('-d', '--description', '-c', '--comment',
		action="store", type="string", dest="description", default=None,
		help="Description of the group (free text).")
	group.add_option('-S', '--skel', '--skeleton',
		action='store', type='string', dest='skel',
		default=LMC.configuration.users.default_skel,
		help="skeleton directory for the group (default is %s)." %
		stylize(ST_DEFAULT, LMC.configuration.users.default_skel))
	group.add_option('-s', '--system', '--system-group', '--sysgroup',
		action='store_true', dest='system', default=False,
		help="The group will be a system group (root / @admin members only).")

	group.add_option('-u', '--users', '--add-users', '--members',
		action='store', dest='users_to_add', default=None,
		help="Users to make members of this group just after creation.")

	backends = LMC.rwi.groups_backends()
	if len(backends) > 1:
		group.add_option('-B', '--backend', '--in-backend',
			action='store', dest='in_backend',
			default=LMC.rwi.prefered_groups_backend(),
			help="specify backend in which to save the group (default:"
				" %s; possible choices: %s." % (
				stylize(ST_DEFAULT, LMC.rwi.prefered_groups_backend()),
					', '.join(backends)))

	parser.add_option_group(group)

	assert ltrace('argparser', '< add_group_parse_arguments()')

	return check_opts_and_args(parser.parse_args())
def add_profile_parse_arguments(app):
	"""Integrated help and options / arguments for « add profile »."""

	usage_text = "\n\t%s profile [--name=]<name> [-g|--group=<groupName>] [--description=<descr>]\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t\t[--shell=<shell>] [--quota=<quota>] [--skel=<nom_squelette>]\n" \
		+ "\t\t[-a|--[add-]groups=<groupe1>[[,groupe2][,…]] [--force-existing]"

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'add_profile'))

	profile = OptionGroup(parser, stylize(ST_OPTION, "Add profile options "))

	profile.add_option("--name", '--profile-name', '--profile',
		action="store", type="string", dest="name", default=None,
		help="The profile's name (ie: «Administrator», «Power user», «Webmaster», «Guest»). It should be a singular word and %s." % stylize(ST_IMPORTANT, "it is required"))
	profile.add_option('-g', "--group", '--profile-group',
		action="store", type="string", dest="group", default=None,
		help="Group name identifying the profile on the system (ie: «administrators», «power-users», «webmasters», «guests»). It should be a plural world and will become a system group. %s." % stylize(ST_IMPORTANT, "It is required"))
	profile.add_option("--description",
		action="store", type="string", dest="description", default = '',
		help="Description of the profile (free text).")
	profile.add_option("--shell",
		action="store", type="string", dest="shell", default = LMC.configuration.users.default_shell,
		help="Default shell for this profile (defaults to %s)." % stylize(ST_DEFAULT, LMC.configuration.users.default_shell))
	profile.add_option("--quota",
		action="store", type="int", dest="quota", default = 1024,
		help="User data quota in Mb (soft quota, defaults to %s)." % stylize(ST_DEFAULT, "1024"))
	profile.add_option('-a', "--groups", "--add-groups",
		action="store", type="string", dest="groups", default = [],
		help="Groups users of this profile will become members of. Separated by commas without spaces.")
	profile.add_option("--skel",
		action="store", type="string", dest="skeldir", default = LMC.configuration.users.default_skel,
		help="skeleton dir for this profile (must be an absolute path, defaults to %s)." % stylize(ST_DEFAULT, LMC.configuration.users.default_skel))
	profile.add_option("--force-existing", '--use-existing',
		action="store_true", dest="force_existing", default = False,
		help="Confirm the use of a previously created system group for the profile. %s, but in some cases (where the group is created by another package or script) this is OK." % stylize(ST_IMPORTANT, "This is risky"))

	parser.add_option_group(profile)

	return parser.parse_args()
def add_keyword_parse_arguments(app):
	"""Integrated help and options / arguments for « add keyword »."""

	usage_text = "\n\t%s kw|tag|keyword|keywords --name=<keyword> [--parent=<parent_keyword> --description=<description>]\n" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'add_keyword'))

	keyword = OptionGroup(parser, stylize(ST_OPTION, "Add keyword options "))

	keyword.add_option("--name",
		action="store", type="string", dest="name", default=None,
		help="The keyword's name. It should be a singular word and %s." % stylize(ST_IMPORTANT, "it is required"))
	keyword.add_option("--parent",
		action="store", type="string", dest="parent", default = "",
		help="Keyword's parent name.")
	keyword.add_option("--description",
		action="store", type="string", dest="description", default = "",
		help="Description of the keyword (free text).")

	parser.add_option_group(keyword)

	return parser.parse_args()
def add_privilege_parse_arguments(app):
	"""Integrated help and options / arguments for « add keyword »."""

	usage_text = "\n\t%s priv|privs|privilege|privileges [--name|--names=]privilege1[[,privilege2],…]\n" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'add_privilege'))

	priv = OptionGroup(parser, stylize(ST_OPTION, "Add privilege options "))

	priv.add_option("--name", "--names",
		action="store", type="string", dest="privileges_to_add", default=None,
		help="The privilege's name(s). %s and can be a single word or multiple ones, separated by commas." % stylize(ST_IMPORTANT, "it is required"))

	parser.add_option_group(priv)

	return parser.parse_args()
def addimport_parse_arguments(app):
	"""Integrated help and options / arguments for « import users »."""

	usage_text = "\n\t%s users --filename=<fichier> --profile=<profil>\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t\t[--lastname-column=<COL>] [--firstname-column=<COL>]\n" \
		+ "\t\t[--group-column=<COL>] [--login-column=<COL>] [--password-column=<COL>]\n" \
		+ "\t\t[--separator=<SEP>] [--confirm-import] [--no-sync]"

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'add_import'))

	addimport = OptionGroup(parser, stylize(ST_OPTION, "Import users and groups options "))

	addimport.add_option("--filename",
		action="store", type="string", dest="filename", default=None,
		help="name of the file you want to import accounts from (must point to "
			"a valid CSV file and %s)." % stylize(ST_IMPORTANT, "is required"))
	addimport.add_option("--profile",
		action="store", type="string", dest="profile", default=None,
		help="profile the accounts will be affected upon creation (%s)." %
			stylize(ST_IMPORTANT, "required"))
	addimport.add_option("--lastname-column",
		action="store", type="int", dest="lastname_col", default = 0,
		help="lastname column number (default is %s)." % stylize(ST_DEFAULT, "0"))
	addimport.add_option("--firstname-column",
		action="store", type="int", dest="firstname_col", default = 1,
		help="firstname column number (default is %s)." % stylize(ST_DEFAULT, "1"))
	addimport.add_option("--group-column",
		action="store", type="int", dest="group_col", default = 2,
		help="%s column number (default is %s)." % (
			stylize(ST_SPECIAL, LMC.configuration.groups.names.plural),
			stylize(ST_DEFAULT, "2")))
	addimport.add_option("--login-column",
		action="store", type="int", dest="login_col", default=None,
		help="%s column number (default is %s: login will be guessed from firstname and lastname)." \
			% (stylize(ST_SPECIAL, "login"), stylize(ST_DEFAULT, "None")))
	addimport.add_option("--password-column",
		action="store", type="int", dest="password_col", default=None,
		help="%s column number (default is %s: password will be randomly generated and %d chars long)." \
			% (stylize(ST_SPECIAL, "passwd"), stylize(ST_DEFAULT, "None"), LMC.configuration.users.min_passwd_size))
	addimport.add_option("--separator",
		action="store", type="string", dest="separator", default = ";",
		help="separator for the CSV fields (default is %s by sniffing in the file)." % stylize(ST_DEFAULT, "determined automatically"))
	addimport.add_option("--confirm-import",
		action="store_true", dest="confirm_import", default = False,
		help="Really do the import. %s on the system, only give you an example of what will be done, which is useful to verify your file has been correctly parsed (fields order, separator…)." % stylize(ST_IMPORTANT, "Without this flag the program will do nothing"))
	addimport.add_option("--no-sync",
		action="store_true", dest="no_sync", default = False,
		help="Commit changes only after all modifications.")

	parser.add_option_group(addimport)

	opts, args = parser.parse_args()

	if opts.filename:
		# resolve the complete filename, else the daemon won't find it because
		# it doesn't have the same CWD as the calling user.
		opts.filename = os.path.abspath(opts.filename)

	return opts, args
def add_machine_parse_arguments(app):
	"""Integrated help and options / arguments for « add user »."""

	usage_text = """
	%s user [--login] <login>
	%s user --firstname <firstname> --lastname <lastname>
		[--system] [--password "<password>"]
		[--gid=<primary_gid>] [--profile=<profile>] [--skel=<skel>]
		[--gecos=<given name>] [--home=<home_dir>] […]""" % (
			stylize(ST_APPNAME, "%prog"),
			stylize(ST_APPNAME, "%prog"))

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'add_machine'))

	machine = OptionGroup(parser,
		stylize(ST_OPTION, "Add machine options "))

	machine.add_option("--discover", '--scan', '--scan-network',
		action="store", dest="discover", default=None,
		help="Scan a network for online hosts and attach them to the "
			"system. Syntax: 192.168.0.0/24 or 10.0.0.0/8 and the like.")

	machine.add_option('-a', '--auto-discover', '--auto-scan',
		action='store_true', dest='auto_scan', default=False,
		help="Scan the local area network(s), looking for unattached hosts.")

	parser.add_option_group(machine)

	opts,args = parser.parse_args()

	"""
	TODO: TO BE ACTIVATED
	if opts.discover and opts.anything:
		raise exceptions.BadArgumentError('discovering network is a '
			'self-running task, no other options allowed, sorry.')
	"""

	return opts, args
### Delete arguments ###
def del_user_parse_arguments(app):
	"""Integrated help and options / arguments for « delete user »."""

	usage_text = "\n\t%s user < --login=<login> | --uid=UID > [--no-archive]" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'del_user'))
	parser.add_option_group(common_filter_group(app, parser, 'del', 'users'))

	user = OptionGroup(parser, stylize(ST_OPTION, "Delete user options "))

	user.add_option("--no-archive",
		action="store_true", dest="no_archive", default = False,
		help="Don't make a backup of user's home directory in %s (default is %s)." % \
			(stylize(ST_PATH, LMC.configuration.home_archive_dir), stylize(ST_DEFAULT, "to make a backup")))

	parser.add_option_group(user)
	return check_opts_and_args(parser.parse_args())
def del_group_parse_arguments(app):
	"""Integrated help and options / arguments for « delete group »."""

	usage_text = "\n\t%s group < --name=<nom_groupe> | --uid=UID > [[--del-users] [--no-archive]]" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'del_group'))
	parser.add_option_group(common_filter_group(app, parser, 'del', 'groups'))

	group = OptionGroup(parser, stylize(ST_OPTION, "Delete group options "))

	group.add_option("--del-users",
		action="store_true", dest="del_users", default = False,
		help="Delete the group members (user accounts) too (default is to %s, they will become members of %s)." % (stylize(ST_DEFAULT, "not delete members"), stylize(ST_DEFAULT, "nogroup")))
	group.add_option("--no-archive",
		action="store_true", dest="no_archive", default = False,
		help="Don't make a backup of users home directories in %s when deleting members (default is %s)" % (stylize(ST_PATH, LMC.configuration.home_archive_dir), stylize(ST_DEFAULT, "to make backups")))
	parser.add_option_group(group)

	return check_opts_and_args(parser.parse_args())
def del_profile_parse_arguments(app):
	"""Integrated help and options / arguments for « delete profile »."""

	usage_text = "\n\t%s profile --group=<nom> [[--del-users] [--no-archive] [--no-sync]]" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(
		common_behaviour_group(app, parser, 'del_profile'))
	parser.add_option_group(common_filter_group(app, parser, 'del', 'profiles'))

	profile = OptionGroup(parser, stylize(ST_OPTION,
		"Delete profile options "))

	profile.add_option("--del-users",
		action="store_true", dest="del_users", default = False,
		help="the profile's users will be deleted.")
	profile.add_option("--no-archive",
		action="store_true", dest="no_archive", default = False,
		help="don't make a backup of user's home when deleting them.")

	parser.add_option_group(profile)

	return check_opts_and_args(parser.parse_args())
def del_keyword_parse_arguments(app):
	"""Integrated help and options / arguments for « delete keyword »."""

	usage_text = "\n\t%s keyword --name=<nom>" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'del_keyword'))

	keyword = OptionGroup(parser, stylize(ST_OPTION, "Delete keyword options "))

	keyword.add_option("--name",
		action="store", type="string", dest="name", default=None,
		help="specify the keyword to delete.")
	keyword.add_option("--del-children",
		action="store_true", dest="del_children", default = False,
		help="delete the parent and his children.")

	parser.add_option_group(keyword)

	return parser.parse_args()
def del_privilege_parse_arguments(app):
	"""Integrated help and options / arguments for « add keyword »."""

	usage_text = "\n\t%s priv|privs|privilege|privileges [--name|--names=]privilege1[[,privilege2],…]\n" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'del_privilege'))
	parser.add_option_group(common_filter_group(app, parser, 'del', 'privileges'))


	priv = OptionGroup(parser, stylize(ST_OPTION, "Delete privilege options "))

	priv.add_option("--name", "--names",
		action="store", type="string", dest="privileges_to_remove", default=None,
		help="The privilege's name(s). %s and can be a single word or multiple ones, separated by commas." % stylize(ST_IMPORTANT, "it is required"))

	parser.add_option_group(priv)

	return check_opts_and_args(parser.parse_args())
def delimport_parse_arguments(app):

	usage_text = "\n\t%s --filename=<fichier> [--no-archive]" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'del_import'))

	delimport = OptionGroup(parser, stylize(ST_OPTION, "Un-import users and groups options "))

	delimport.add_option("--filename",
		action="store", type="string", dest="filename", default=None,
		help="")
	delimport.add_option("--no-archive",
		action="store_true", dest="no_archive", default = False,
		help="don't make a backup of user's home when deleting them.")

	parser.add_option_group(delimport)

	opts, args = parser.parse_args()

	if opts.filename:
		# resolve the complete filename, else the daemon won't find it because
		# it doesn't have the same CWD as the calling user.
		opts.filename = os.path.abspath(opts.filename)

	return opts, args

### Modify arguments ###
def mod_user_parse_arguments(app):

	usage_text = "\n\t%s user --login=<login> [--gecos=<new GECOS>] [--password=<new passwd> | --auto-password] [--password-size=<size>]\n" % stylize(ST_APPNAME, "%prog") \
		+ '\t\t[--lock|--unlock] [--add-groups=<group1[[,group2][,…]]>] [--del-groups=<group1[[,group2][,…]]>]\n' \
		+ '\t\t[--shell=<new shell>]\n'  \
		"\t%s user --login=<login> --apply-skel=<squelette>" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'mod_user'))
	parser.add_option_group(common_filter_group(app, parser, 'mod', 'users'))

	user = OptionGroup(parser, stylize(ST_OPTION, "Modify user options "))

	user.add_option("--password", '-p',
		dest="newpassword", default=None,
		help="Specify user's new password on the command line (%s, it can be"
			"written in system logs and your shell history file)." %
				stylize(ST_IMPORTANT, 'insecure'))
	user.add_option("--change-password", '-C', '--interactive-password',
		action="store_true", dest="interactive_password", default=False,
		help="Ask for a new password for the user. If changing your own "
			"password, you will be asked for the old, too.")
	user.add_option("--auto-password", '-P', '--random-password',
		action="store_true", dest="auto_passwd", default=False,
		help="let the system generate a random password for this user.")
	user.add_option("--password-size", '-S',
		type='int', dest="passwd_size",
		default=LMC.configuration.users.min_passwd_size,
		help="choose the new password length (default %s)." %
			LMC.configuration.users.min_passwd_size)
	user.add_option('-e', "--gecos",
		dest="newgecos", default=None,
		help="specify user's new GECOS string (generaly first and last names).")
	user.add_option('-s', "--shell",
		dest="newshell", default=None,
		help="specify user's shell (generaly /bin/something).")

	user.add_option('-l', "--lock",
		action="store_true", dest="lock", default=None,
		help="lock the account (user wn't be able to login under Linux "
			"and Windows/MAC until unlocked).")
	user.add_option('-L', "--unlock",
		action="store_false", dest="lock", default=None,
		help="unlock the user account and restore login ability.")

	user.add_option("--add-groups",
		dest="groups_to_add", default=None,
		help="make user member of these groups.")
	user.add_option("--del-groups",
		dest="groups_to_del", default=None,
		help="remove user from these groups.")
	user.add_option("--apply-skel",
		action="store", type="string", dest="apply_skel", default=None,
		help="re-apply the user's skel (use with caution, it will overwrite "
			"the dirs/files belonging to the skel in the user's home dir.")

	parser.add_option_group(user)
	try:
		opts, args = parser.parse_args()
	except Exception, e:
		print e
	if opts.newpassword is None and not opts.non_interactive:
		pass

	# note the current user for diverses mod_user operations
	opts.current_user = getpass.getuser()

	return opts, args
def mod_machine_parse_arguments(app):

	usage_text = "\n\t%s machine[s] [--shutdown] [--warn-users] " % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'mod_machine'))
	parser.add_option_group(common_filter_group(app, parser, 'mod', 'machines'))

	user = OptionGroup(parser, stylize(ST_OPTION, "Modify machine(s) options "))

	user.add_option('--shutdown', '-s',
		action='store_true', dest="shutdown", default=False,
		help="remotely shutdown specified machine(s).")
	user.add_option('--warn-user', '--warn-users', '-w',
		action="store_false", dest="warn_users", default=True,
		help='''Display a warning message to connected user(s) before '''
			'''shutting system(s) down.''')

	parser.add_option_group(user)

	return check_opts_and_args(parser.parse_args())
def mod_volume_parse_arguments(app):

	usage_text = ("\n\t%s volume[s] [--enable|--disable] <vol1[,vol2[,…]]>" %
		stylize(ST_APPNAME, "%prog"))

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'mod_volume'))
	#parser.add_option_group(common_filter_group(app, parser, 'mod', 'volumes'))

	volume = OptionGroup(parser, stylize(ST_OPTION, "Modify volume(s) options "))

	volume.add_option('--enable', '-e',
		action='store', dest="add_volumes", default=None,
		help="specify one or more volume(s) to enable (mark as available and "
			"reserved for Licorn® internal use), either by giving its "
			"device path or mount point.")
	volume.add_option('--disable', '-d',
		action="store", dest="del_volumes", default=None,
		help="specify one or more volume(s) to disable(mark as available and "
			"reserved for Licorn® internal use), either by giving its "
			"device path or mount point.")

	# rescan /proc/mounts for new mounted or removed filesystems, to maintain an
	# up-to-date list of volumes. This is meant to be called by udev only, thus
	# we suppress help.
	volume.add_option('--rescan', '-r', action="store_true", dest="rescan",
		default=False, help=SUPPRESS_HELP)

	parser.add_option_group(volume)

	return check_opts_and_args(parser.parse_args())
def mod_group_parse_arguments(app):

	usage_text = "\n\t%s group --name=<nom_actuel> [--rename=<nouveau_nom>]\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t\t[--add-users=<user1[[,user2][,…]]>] [--del-users=<user1[[,user2][,…]]>]\n" \
		+ "\t\t[--add-resps=<user1[[,user2][,…]]>] [--delete-resps=<user1[[,user2][,…]]>]\n" \
		+ "\t\t[--add-guests=<user1[[,user2][,…]]>] [--delete-guests=<user1[[,user2][,…]]>]\n" \
		+ "\t\t[--permissive|--not-permissive] [--skel=<new skel>] [--description=<new description>]"

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'mod_group'))
	parser.add_option_group(common_filter_group(app, parser, 'mod', 'groups'))

	group = OptionGroup(parser, stylize(ST_OPTION, "Modify group options"))

	group.add_option("--rename",
		action="store", type="string", dest="newname", default=None,
		help="specify group's new name (not yet implemented).")
	group.add_option("--skel",
		action="store", type="string", dest="newskel", default=None,
		help="specify group's new skel dir.")
	group.add_option("--description",
		action="store", type="string", dest="newdescription", default=None,
		help="specify new group's description")
	group.add_option("-p", "--permissive", "--set-permissive",
		action="store_true", dest="permissive", default=None,
		help="set the shared directory of the group permissive.")
	group.add_option("-P", "--not-permissive", "--set-not-permissive",
		action="store_false", dest="permissive", default=None,
		help="set the shared directory of the group not permissive.")
	group.add_option("--add-users",
		action="store", type="string", dest="users_to_add", default = [],
		help="Add users to the group. The users are separated by commas without spaces.")
	group.add_option("--del-users",
		action="store", type="string", dest="users_to_del", default = [],
		help="Delete users from the group. The users are separated by commas without spaces.")
	group.add_option("--add-resps",
		action="store", type="string", dest="resps_to_add", default = [],
		help="Add responsibles to the group. The responsibles are separated by commas without spaces.")
	group.add_option("--del-resps",
		action="store", type="string", dest="resps_to_del", default = [],
		help="Delete responsibles from the group. The responsibles are separated by commas without spaces.")
	group.add_option("--add-guests",
		action="store", type="string", dest="guests_to_add", default = [],
		help="Add guests to the group. The guests are separated by commas without spaces.")
	group.add_option("--del-guests",
		action="store", type="string", dest="guests_to_del", default = [],
		help="Delete guests from the group. The guests are separated by commas without spaces.")
	group.add_option("--add-granted-profiles",
		action="store", type="string", dest="granted_profiles_to_add", default=None,
		help="Add the profiles which the users can access to the group's shared directory. The profiles are separated by commas without spaces.")
	group.add_option("--del-granted-profiles",
		action="store", type="string", dest="granted_profiles_to_del", default=None,
		help="Delete the profiles which the users can access to the group's shared directory. The profiles are separated by commas without spaces.")

	backends = LMC.rwi.groups_backends()
	if len(backends) > 1:
		group.add_option('--move-to-backend', '--change-backend', '--move-backend',
			action="store", type="string", dest="move_to_backend", default=None,
			help="move the group from its current backend to another, where it will"
				" definitely stored (specify new backend name as argument, from "
				"%s)." % LMC.rwi.backends())

	parser.add_option_group(group)

	return check_opts_and_args(parser.parse_args())
def mod_profile_parse_arguments(app):

	usage_text = "\n\t%s profile --group=<nom> [--name=<nouveau_nom>] [--rename-group=<nouveau_nom>]\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t\t[--comment=<nouveau_commentaire>] [--shell=<nouveau_shell>] [--skel=<nouveau_skel>]\n" \
		+ "\t\t[--quota=<nouveau_quota>] [--add-groups=<groupes>] [--del-groups=<groupes>]\n" \
		+ "\t%s profile <--apply-groups|--apply-skel|--apply-all> [--force]\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t\t[--to-users=<user1[[,user2][,…]]>] [--to-groups=<group1[[,group2][,…]]>]\n" \
		+ "\t\t[--to-all] [--to-members] [--no-instant-apply] [--no-sync]"

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(
		common_behaviour_group(app, parser, 'mod_profile'))
	parser.add_option_group(common_filter_group(app, parser, 'mod', 'profiles'))

	profile = OptionGroup(parser, stylize(ST_OPTION, "Modify profile options "))

	profile.add_option("--rename", '--new-name',
		action="store", type="string", dest="newname", default=None,
		help="specify profile's name")
	profile.add_option("--rename-group", '--new-group-name',
		action="store", type="string", dest="newgroup", default=None,
		help="Rename primary group.")
	profile.add_option("--description",
		action="store", type="string", dest="description", default=None,
		help="Change profile's description.")
	profile.add_option("--shell",
		action="store", type="string", dest="newshell", default=None,
		help="Change profile shell (defaults to %s if you specify --shell without argument)" % stylize(ST_DEFAULT, LMC.configuration.users.default_shell))
	profile.add_option("--quota",
		action="store", type="int", dest="newquota", default=None,
		help="Change profile's user quota (in Mb, defaults to %s if you specify --quota without argument)." % stylize(ST_DEFAULT, "1024"))
	profile.add_option("--skel",
		action="store", type="string", dest="newskel", default=None,
		help="Change profile skel (specify a skel dir as an absolute pathname, defaults to %s if you give --skel without argument)." % stylize(ST_DEFAULT, LMC.configuration.users.default_skel))
	profile.add_option("--add-groups",
		action="store", type="string", dest="groups_to_add", default=None,
		help="Add one or more group(s) to default memberships of profile (separate groups with commas without spaces).")
	profile.add_option("--del-groups",
		action="store", type="string", dest="groups_to_del", default=None,
		help="Delete one or more group(s) from default memberships of profile (separate groups with commas without spaces).")
	profile.add_option("--apply-groups",
		action="store_true", dest="apply_groups", default = False,
		help="Re-apply only the default group memberships of the profile.")
	profile.add_option("--apply-skel",
		action="store_true", dest="apply_skel", default = False,
		help="Re-apply only the skel of the profile.")
	profile.add_option("--apply-all",
		action="store_true", dest="apply_all_attributes", default=False,
		help="Re-apply all the profile's attributes (groups and skel).")
	profile.add_option("--to-users",
		action="store", type="string", dest="apply_to_users", default=None,
		help="Re-apply to specific users accounts (separate them with commas without spaces).")
	profile.add_option("--to-groups",
		action="store", type="string", dest="apply_to_groups", default=None,
		help="Re-apply to all members of one or more groups (separate groups with commas without spaces). You can mix --to-users and --to-groups.")
	profile.add_option("--to-members",
		action="store_true", dest="apply_to_members", default = False,
		help="Re-apply to all users members of the profile.")
	profile.add_option("--to-all",
		action="store_true", dest="apply_to_all_accounts", default=None,
		help="Re-apply to all user accounts on the system (LENGHTY operation !).")
	profile.add_option("--no-instant-apply",
		action="store_false", dest="instant_apply", default = True,
		help="Don't apply group addition/deletion instantly to all members of the modified profile (%s; use this only if you know what you're doing)." % stylize(ST_IMPORTANT, "this is not recommended"))
	profile.add_option("--no-sync",
		action="store_true", dest="no_sync", default = False,
		help="Commit changes only after all modifications.")

	parser.add_option_group(profile)

	(opts, args) = check_opts_and_args(parser.parse_args())

	if opts.apply_all_attributes:
		opts.apply_skel = True
		opts.apply_groups = True

	return opts, args
def mod_keyword_parse_arguments(app):

	usage_text = "\n\t%s keyword --name=<nom> [--rename=<nouveau_nom>] [--parent=<nouveau_parent>]\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t\t[--remove-parent] [--recursive]"

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'mod_profile'))

	keyword = OptionGroup(parser, stylize(ST_OPTION, "Modify keyword options "))

	keyword.add_option("--name",
		action="store", type="string", dest="name", default=None,
		help="specify keyword to modify (%s)." % stylize(ST_IMPORTANT, "required"))
	keyword.add_option("--rename",
		action="store", type="string", dest="newname", default=None,
		help="Rename keyword")
	keyword.add_option("--parent",
		action="store", type="string", dest="parent", default=None,
		help="Change keyword's parent.")
	keyword.add_option("--remove-parent",
		action="store_true", dest="remove_parent", default = False,
		help="Remove parent.")
	keyword.add_option("--recursive",
		action="store_true", dest="recursive", default = False,
		help="Modify all file in all subdirs.")
	keyword.add_option("--description",
		action="store", type="string", dest="description", default=None,
		help="Remove parent.")

	parser.add_option_group(keyword)

	return parser.parse_args()
def mod_path_parse_arguments(app):

	usage_text = "\n\t%s path [--path=]<fichier_ou_repertoire> [--add-keywords=<kw1[,kw1,…]>] [--del-keywords=<kw1[,kw1,…]>]\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t\t[--clear-keywords] [--recursive]"

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# common behaviour group
	parser.add_option_group(common_behaviour_group(app, parser, 'mod_path'))

	path = OptionGroup(parser, stylize(ST_OPTION, "Modify keyword options "))

	path.add_option("--path",
		action="store", type="string", dest="path", default=None,
		help="specify path of the file/directory to tag (%s)." %
			stylize(ST_IMPORTANT, "required"))
	path.add_option("--add-keywords",
		action="store", type="string", dest="keywords_to_add", default=None,
		help="Add keywords.")
	path.add_option("--del-keywords",
		action="store", type="string", dest="keywords_to_del", default=None,
		help="Remove keywords.")
	path.add_option("--clear-keywords",
		action="store_true", dest="clear_keywords", default = False,
		help="Remove all keywords.")
	path.add_option("--recursive",
		action="store_true", dest="recursive", default = False,
		help="Set modifications to all subdirs.")
	path.add_option("--description",
		action="store", type="string", dest="description", default = False,
		help="Remove parent.")

	parser.add_option_group(path)

	return parser.parse_args()
def mod_configuration_parse_arguments(app):

	usage_text = "\n\t%s config[uration] [--hide-groups|--set-hidden-groups|--unhide-groups|-u|-U] [--set-hostname <new hostname>] [--restrictive] [--set-ip-address <NEW.ETH0.IP.ADDR>]" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	# FIXME: review common_behaviour_group to set eventual special options
	# (for modify config ?).
	parser.add_option_group(common_behaviour_group(app, parser, 'mod_config'))

	configuration_group = OptionGroup(parser, stylize(ST_OPTION,
		"Modify configuration options "))

	configuration_group.add_option("--setup-shared-dirs",
		action="store_true", dest="setup_shared_dirs", default=False,
		help='''create system groups, directories and settings from system '''
			'''configuration (PARTIALLY OBSOLETED, TOTALLY UNSUPPORTED AND '''
			'''VERY DANGEROUS, USE WITH CAUTION).''')

	configuration_group.add_option("-r", "--restrictive", "--set-restrictive",
		action="store_true", dest="restrictive", default=False,
		help='''when creating system groups and directories, apply '''
			'''restrictive perms (710) on shared dirs instead of relaxed '''
			'''ones (750).''')

	configuration_group.add_option("-u", "--hide-groups", "--set-groups-hidden",
		action="store_true", dest="hidden_groups", default=None,
		help="Set restrictive perms (710) on %s." %
			stylize(ST_PATH,
				"%s/%s" % (LMC.configuration.defaults.home_base_path,
					LMC.configuration.groups.names.plural)))

	configuration_group.add_option("-U", "--unhide-groups",
		"--set-groups-visible",
		action="store_false", dest="hidden_groups", default=None,
		help="Set relaxed perms (750) on %s." % stylize(ST_PATH,
		"%s/%s" % (LMC.configuration.defaults.home_base_path,
			LMC.configuration.groups.names.plural)))

	configuration_group.add_option('-b', "--enable-backends",
		action="store", dest="enable_backends", default=None,
		help='''enable given backend(s) on the current system (separated '''
			'''by commas without spaces). List of available backends with '''
			'''`%s`.''' % stylize(ST_MODE, 'get config backends'))

	configuration_group.add_option('-B', "--disable-backends",
		action="store", dest="disable_backends", default=None,
		help='''disable given backend(s) on the current system (separated '''
			'''by commas without spaces). List of available backends with '''
			'''`%s`.''' % stylize(ST_MODE, 'get config backends'))

	configuration_group.add_option('-e', "--enable-extensions",
		action="store", dest="enable_extensions", default=None,
		help='''enable given extension(s) on the current system (separated '''
			'''by commas without spaces). List of available extensions with '''
			'''`%s`.''' % stylize(ST_MODE, 'get config extensions'))

	configuration_group.add_option('-E', "--disable-extensions",
		action="store", dest="disable_extensions", default=None,
		help='''disable given extension(s) on the current system (separated '''
			'''by commas without spaces). List of available extensions with '''
			'''`%s`.''' % stylize(ST_MODE, 'get config extensions'))

	configuration_group.add_option( "--set-hostname",
		action="store", type="string", dest="set_hostname", default=None,
		help="change machine hostname.")

	configuration_group.add_option("-i", "--set-ip-address",
		action="store", type="string", dest="set_ip_address", default=None,
		help="change machine's IP (for eth0 only).")

	configuration_group.add_option("--add-privileges",
		action="store", type="string", dest="privileges_to_add", default=None,
		help="add privileges (system groups) to privileges whitelist.")

	configuration_group.add_option("--remove-privileges",
		action="store", type="string", dest="privileges_to_remove",
		default=None,
		help="remove privileges (system groups) from privileges whitelist.")

	parser.add_option_group(configuration_group)

	return parser.parse_args()

### Check arguments ###

def chk_user_parse_arguments(app):
	"""Integrated help and options / arguments for « check user(s) »."""

	usage_text = "\n\t%s user[s] --login login1[[,login2][…]] [--minimal] [--yes|--no]\n" % stylize(ST_APPNAME, "%prog") \
		+ "\t%s user[s] --uid uid1[[,uid2][…]] [--minimal] [--yes|--no]" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'check'))
	parser.add_option_group(common_filter_group(app, parser, 'chk', 'users'))

	return check_opts_and_args(parser.parse_args())
def chk_group_parse_arguments(app):
	"""Integrated help and options / arguments for « check group(s) »."""

	usage_text = "\n\t%s group[s] --name group1[[,group2][…]]" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'check'))
	parser.add_option_group(common_filter_group(app, parser, 'chk', 'groups'))

	return check_opts_and_args(parser.parse_args())
def chk_profile_parse_arguments(app):
	"""Integrated help and options / arguments for « check profile(s) »."""

	usage_text = "\n\t%s profile[s] --name profile1[[,profile2][…]]" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'check'))
	parser.add_option_group(common_filter_group(app, parser, 'chk', 'profiles'))

	return check_opts_and_args(parser.parse_args())
def chk_configuration_parse_arguments(app):
	"""TODO"""

	usage_text = "\n\t%s config[uration] -a | (names|hostname)" % stylize(ST_APPNAME, "%prog")

	parser = OptionParser(usage=usage_text,
		version=build_version_string(app, version))

	parser.add_option_group(common_behaviour_group(app, parser, 'check'))
	parser.add_option_group(common_filter_group(app, parser, 'chk', 'configuration'))

	return parser.parse_args()
