# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

argparser - command-line argument parser library.
Contains all argument parsers for all licorn system tools (get, add, modify, delete, check)

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>,
Copyright (C) 2005,2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

from optparse import OptionParser, OptionGroup

from licorn.foundations        import styles
from licorn.core               import version
from licorn.core.configuration import LicornConfiguration
configuration = LicornConfiguration()

### General / common arguments ###
def __build_version_string(app):
	"""return a string ready to be displayed, containing app_name, version, authors..."""
	return "%s (%s) version %s\n(C) 2004-2008 %s\nlicensed under the terms of the GNU GPL v2. See %s for project details." \
		% ( styles.stylize(styles.ST_APPNAME, app["name"]), app["description"], version, app["author"], styles.stylize(styles.ST_URL, "http://dev.licorn.org/") )
def __common_behaviour_group(app, parser, mode = 'any'):
	""" This group is common to all Licorn System Tools."""
	behaviorgroup = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Behavior options "),
							"Modify decisions / apply filter(s) on data manipulated by program.")

	if mode != "get":
		if mode == "check":
			behaviorgroup.add_option("-e", "--extended",
				action="store_false", dest="minimal", default = True,
				help="Execute extended checks (%s, which is to make the bare minimum checks for the system to operate properly)." % styles.stylize(styles.ST_DEFAULT, "not the default") )
			behaviorgroup.add_option("-y", "--yes", "--auto-yes",
				action="store_true", dest="auto_answer", default = None,
				help="Automatically answer 'yes' to all repair questions (i.e. repair everything that can be) (default: %s, each question will be asked at one time)." % styles.stylize(styles.ST_DEFAULT, "no"))
			behaviorgroup.add_option("--no", "--auto-no",
				action="store_false", dest="auto_answer", default = None,
				help="Automatically answer 'no' to all repair questions (i.e. don't repair anything, just print the warnings)." )
			behaviorgroup.add_option("--batch", "-b",
				action="store_true", dest="batch", default = False,
				help="batch all operations (don't ask questions, automate everything).")

		behaviorgroup.add_option("-f", "--force",
			action="store_true", dest="force", default = False,
			help="forces the current action (if applicable).")

	behaviorgroup.add_option("-q", "--quiet",
		action="store_const", dest="verbose", const = 0,
		help="be quiet, don't display anything except on warnings/errors." )
	behaviorgroup.add_option("-v", "--verbose",
		action="count", dest="verbose", default = 1,
		help="be more verbose (in command-line mode) ; you can get more with -vv, -vvv, etc.%s, which is quite moderated. You will get information about auto-generated passwords and long-time actions, when you should expect to wait for them to complete."% styles.stylize(styles.ST_DEFAULT, "the default is INFO level of verbosity"))
	behaviorgroup.add_option("--no-colors",
		action="store_true", dest="no_colors", default = False,
		help="no colors in any messages (CLI mode only).")

	return behaviorgroup
def general_parse_arguments(app):
	"""Common options and arguments to all Licorn System Tools, with specialties."""

	usage_text = "\n\t%s [[%s] ...] [[%s] ...]\n\n\t%s is one of: " \
		% (styles.stylize(styles.ST_APPNAME, "%prog"), styles.stylize(styles.ST_MODE, "mode"), styles.stylize(styles.ST_OPTION, "options"), styles.stylize(styles.ST_MODE, "mode"))

	if app["name"] in ( "licorn-get", "licorn-modify", "licorn-check" ):
		usage_text +=  "config[uration], "

	if app["name"] in ( "licorn-get", "licorn-check" ):
		usage_text += "user[s], group[s], profile[s], kw|keyword[s]|tag[s], priv[ilege][s]."

	else:
		usage_text += "user, "
		if app["name"] == "licorn-add":
			usage_text += "users (massive imports), "
		usage_text	+= "group, profile."

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	return (parser.parse_args())

### Licorn daemon arguments ###
def licornd_parse_arguments(app):
	""" Integrated help and options / arguments for harvestd."""

	usage_text = "\n\t%s [-D|--no-daemon] [...]" \
		% ( styles.stylize(styles.ST_APPNAME, "%prog") )

	parser = OptionParser( usage = usage_text, version = __build_version_string(app))
	parser.add_option("-D", "--no-daemon",
		action="store_false", dest="daemon", default = True,
		help="Don't fork as a daemon, stay on the current terminal instead. Logs will be printed onscreen instead of going into the logfile.")

	parser.add_option_group(__common_behaviour_group(app, parser, 'harvestd'))

	return (parser.parse_args())

### Getent arguments ###
def __get_filter_group(app, parser, mode):
	"""Build Filter OptionGroup for all get variants."""

	filtergroup = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Filter options "),
					"Filter data displayed / exported (WARNING: filters are not cumulative ! Unexpected behaviour is to be expected if you use more than one filter option).")

	if mode in ( 'users', 'groups'):
		filtergroup.add_option("-a", "--all",
			action="store_true", dest="factory", default = False,
			help="also get factory and system data (rarely used), i.e. for users, output system accounts too, etc (%s: you can get huge output and easily flood your terminal)." % styles.stylize(styles.ST_BAD, "WARNING"))
		filtergroup.add_option("-l", "--long",
			action="store_true", dest="long", default = False,
			help="long output (all info, attributes, etc). NOT enabled by default.")

	if mode is 'users':
		filtergroup.add_option("--uid",
			action="store", type="int", dest="uid", default = None,
			help="Display only one user information (only valid for get users).")

	elif mode is 'groups':
		filtergroup.add_option("--privileged",
			action="store_true", dest="privileged", default = False,
			help="Only get privileged groups.")
		filtergroup.add_option("--responsibles",
			action="store_true", dest="responsibles", default = False,
			help="Only get responsibles groups.")
		filtergroup.add_option( "--guests",
			action="store_true", dest="guests", default = False,
			help="Only get guests groups.")
		filtergroup.add_option( "--empty",
			action="store_true", dest="empty", default = False,
			help="Only get empty groups.")
		filtergroup.add_option("--gid",
			action="store", type="int", dest="gid", default = None,
			help="Display only one group information, identified by its GID.")

	elif mode is 'profiles':
		filtergroup.add_option("--profile",
			action="store", type="string", dest="profile", default = None,
			help="Profile's primary group. Display only one profile information, given its primary group.")

	return filtergroup
def __get_output_group(app, parser, mode):
	"""TODO"""

	outputgroup = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Output options "),
							"Modify how data is printed/exported.")

	if mode is 'configuration':
		outputgroup.add_option("-s", "--short",
			action="store_const", const = "short", dest="cli_format", default = "short",
			help="Like previous option, but export the configuration subset in the shortest form factor (only the values when possible ; %s)." \
				% styles.stylize(styles.ST_DEFAULT, "this is the default") )
		outputgroup.add_option("-b", "--bourne-shell",
			action="store_const", const = "bourne", dest="cli_format", default = "short",
			help="When using configuration %s to output a subset of the system configuration, export it in a useful way to be used in a bourne shell environment (i.e. export VAR=\"value\")." % styles.stylize(styles.ST_OPTION, "sub-category"))
		outputgroup.add_option("-c", "--c-shell",
			action="store_const", const = "cshell", dest="cli_format", default = "short",
			help="Like previous option, but export the configuration subset in a useful way to be used in a C shell environment (i.e. setenv VAR \"value\").")
		outputgroup.add_option("-p", "--php-code",
			action="store_const", const = "PHP", dest="cli_format", default = "short",
			help="Like previous option, but export the configuration subset in a usefull way to be included in PHP code (i.e. $VAR=\"value\", use it with eval(`...`)).")
	else:
		outputgroup.add_option("-x", "--xml",
			action="store_true", dest="xml", default = False,
			help="Output data as XML (no colors, no verbose). If not set, %s (for human beiings, but not easily parsable format)." % styles.stylize(styles.ST_DEFAULT, "default is to output for CLI"))

	return outputgroup
def get_users_parse_arguments(app):
	""" Integrated help and options / arguments for « get user(s) »."""

	usage_text = "\n\t%s %s [[%s] ...]" \
		% ( styles.stylize(styles.ST_APPNAME, "%prog"), styles.stylize(styles.ST_MODE, "users"), styles.stylize(styles.ST_OPTION, "option") )

	parser = OptionParser( usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(__get_filter_group(app, parser, 'users'))
	parser.add_option_group(__get_output_group(app, parser,'users'))

	return (parser.parse_args())
def get_groups_parse_arguments(app):
	""" Integrated help and options / arguments for « get group(s) »."""

	usage_text = "\n\t%s %s [[%s] ...]" \
		% ( styles.stylize(styles.ST_APPNAME, "%prog"), styles.stylize(styles.ST_MODE, "groups"), styles.stylize(styles.ST_OPTION, "option") )

	parser = OptionParser( usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(__get_filter_group(app, parser, 'groups'))
	parser.add_option_group(__get_output_group(app, parser,'groups'))

	return (parser.parse_args())
def get_keywords_parse_arguments(app):
	""" Integrated help and options / arguments for « get keyword(s) »."""

	usage_text = "\n\t%s %s [[%s] ...]" \
		% ( styles.stylize(styles.ST_APPNAME, "%prog"), styles.stylize(styles.ST_MODE, "keywords"), styles.stylize(styles.ST_OPTION, "option") )

	parser = OptionParser( usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(__get_output_group(app, parser,'keywords'))

	return (parser.parse_args())
def get_profiles_parse_arguments(app):
	""" Integrated help and options / arguments for « get profile(s) »."""

	usage_text = "\n\t%s %s [[%s] ...]" \
		% ( styles.stylize(styles.ST_APPNAME, "%prog"), styles.stylize(styles.ST_MODE, "profiles"), styles.stylize(styles.ST_OPTION, "option") )

	parser = OptionParser( usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(__get_filter_group(app, parser, 'profiles'))
	parser.add_option_group(__get_output_group(app, parser,'profiles'))

	return (parser.parse_args())
def get_configuration_parse_arguments(app):
	""" Integrated help and options / arguments for « get »."""

	usage_text = "\n\t%s config [[%s] ...]\n" % (
		styles.stylize(styles.ST_APPNAME, "%prog"),
		styles.stylize(styles.ST_OPTION, "option")) \
		+ "\t%s config [[%s] ...] %s [--short|--bourne-shell|--c-shell|--php-code] ]\n" % (
		styles.stylize(styles.ST_APPNAME, "%prog"),
		styles.stylize(styles.ST_OPTION, "option"),
		styles.stylize(styles.ST_OPTION, "category")) \
		+ ('''%s is one of: app_name, names, shells, skels, '''
			'''priv|privs|privileges, config_dir, '''
			'''sysgroups|system_group|system-groups '''
			'''main_config_file, extendedgroup_data_file.''' % \
				styles.stylize(styles.ST_OPTION, "category"))

	parser = OptionParser( usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'get'))
	parser.add_option_group(__get_filter_group(app, parser,'configuration'))
	parser.add_option_group(__get_output_group(app, parser,'configuration'))

	return (parser.parse_args())

### Add arguments ###
def add_user_parse_arguments(app):
	"""Integrated help and options / arguments for « add user »."""

	usage_text = "\n\t%s user --login <login> [--primary-group <group>] ... \n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t%s user --firstname <prénom> --lastname <nom> [--password <mot de passe>]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--primary-group=<groupe primaire>|--profile=<profil>] [--login=<login>]\n" \
		+ "\t\t[--gecos=<commentaires>] [--skel <squelette>]"

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'add_user'))

	user = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Add user options "))

	user.add_option("--login", "--name",
		action="store", type="string", dest="login", default = None,
		help="Specify user's login (%s)." % styles.stylize(styles.ST_IMPORTANT, "one of login or firstname+lastname is required"))
	user.add_option("--firstname",
		action="store", type="string", dest="firstname", default = None,
		help="Specify user's first name.")
	user.add_option("--lastname",
		action="store", type="string", dest="lastname", default = None,
		help="Specify user's last name.")
	user.add_option("--password",
		action="store", type="string", dest="password", default = None,
		help="Specify user's password (else will be autogenerated, %d chars long)." % configuration.mAutoPasswdSize)
	user.add_option("--profile",
		action="store", type="string", dest="profile", default = None,
		help="Profile which will be applied to the user (override primary group).")
	user.add_option("--ingroup", "--primary-group",
		action="store", type="string", dest="primary_group", default = None,
		help="Specify user's primary group (overiden by profile).")
	user.add_option("--skel",
		action="store", type="string", dest="skel", default = None,
		help="Use this skel instead of profile or primary-group skel (default: %s)." % styles.stylize(styles.ST_DEFAULT, "the profile's skel"))
	user.add_option("--gecos",
		action="store", type="string", dest="gecos", default = None,
		help="Specify user's GECOS field (else autogenerated from first/last name, else from login).")

	user.add_option("--system",
		action="store_true", dest="system", default = False,
		help="Create a system account instead of a standard user (root only).")

	# adduser, useradd compatibility
	user.add_option("--home",
		action="store", type="string", dest="shell", default = False,
		help="")
	user.add_option("-s", "--shell",
		action="store", type="string", dest="shell", default = False,
		help="")
	user.add_option("--no-create-home",
		action="store_true", dest="no_create_home", default = False,
		help="")
	user.add_option("--uid",
		action="store", type="string", dest="uid", default = False,
		help="")
	user.add_option("--firstuid",
		action="store", type="string", dest="firstuid", default = False,
		help="")
	user.add_option("--lastuid",
		action="store", type="string", dest="lastuid", default = False,
		help="")
	user.add_option("--gid",
		action="store", type="string", dest="gid", default = False,
		help="")
	user.add_option("--disabled-password",
		action="store_true", dest="disabled_password", default = False,
		help="")
	user.add_option("--disabled-login",
		action="store_true", dest="disabled_login", default = False,
		help="")

	parser.add_option_group(user)

	return (parser.parse_args())
def add_group_parse_arguments(app):
	"""Integrated help and options / arguments for « add group »."""

	usage_text = "\n\t%s group --name=<nom_groupe> [--permissive] [--gid=<gid>]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--skel=<nom_squelette>] [--description=<description>]\n" \
		+ "\t\t[--system]"

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'add_group'))

	group = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Add group options "))

	group.add_option("--name",
		action="store", type="string", dest="name", default = "",
		help="Specify group's name (%s)." % styles.stylize(styles.ST_IMPORTANT, "required") )
	group.add_option("--permissive",
		action="store_true", dest="permissive", default = False,
		help="The shared group directory will be permissive (default is %s)." % styles.stylize(styles.ST_DEFAULT, "not permissive"))
	group.add_option("--gid",
		action="store", type="int", dest="gid", default=None,
		help="Specify the GID (root / @admin members only).")
	group.add_option("--description",
		action="store", type="string", dest="description", default = '',
		help="Description of the group (free text).")
	group.add_option("--skel",
		action="store", type="string", dest="skel", default = configuration.users.default_skel,
		help="skeleton directory for the group (default is %s)." %  styles.stylize(styles.ST_DEFAULT, configuration.users.default_skel))
	group.add_option("--system",
		action="store_true", dest="system", default = False,
		help="The group will be a system group (root / @admin members only).")

	parser.add_option_group(group)

	return (parser.parse_args())
def add_profile_parse_arguments(app):
	"""Integrated help and options / arguments for « add profile »."""


	usage_text = "\n\t%s profile --name=<nom> --group=<groupe> [--comment=<commentaire>]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--shell=<shell>] [--quota=<quota>] [--skel=<nom_squelette>]\n" \
		+ "\t\t[--groups=<groupe1>[[,groupe2][,...]] [--force-existing]"

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'add_profile'))

	profile = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Add profile options "))

	profile.add_option("--name",
		action="store", type="string", dest="name", default = None,
		help="The profile's name (ie: «Administrator», «Power user», «Webmaster», «Guest»). It should be a singular word and %s." % styles.stylize(styles.ST_IMPORTANT, "it is required"))
	profile.add_option("--group",
		action="store", type="string", dest="group", default = None,
		help="Group name identifying the profile on the system (ie: «administrators», «power-users», «webmasters», «guests»). It should be a plural world and will become a system group. %s." % styles.stylize(styles.ST_IMPORTANT, "It is required"))
	profile.add_option("--comment",
		action="store", type="string", dest="comment", default = '',
		help="Description of the profile (free text).")
	profile.add_option("--shell",
		action="store", type="string", dest="shell", default = configuration.users.default_shell,
		help="Default shell for this profile (defaults to %s)." % styles.stylize(styles.ST_DEFAULT, configuration.users.default_shell))
	profile.add_option("--quota",
		action="store", type="int", dest="quota", default = 1024,
		help="User data quota in Mb (soft quota, defaults to %s)." % styles.stylize(styles.ST_DEFAULT, "1024"))
	profile.add_option("--groups",
		action="store", type="string", dest="groups", default = [],
		help="Groups users of this profile will become members of. Separated by commas without spaces.")
	profile.add_option("--skel",
		action="store", type="string", dest="skeldir", default = configuration.users.default_skel,
		help="skeleton dir for this profile (must be an absolute path, defaults to %s)." % styles.stylize(styles.ST_DEFAULT, configuration.users.default_skel))
	profile.add_option("--force-existing",
		action="store_true", dest="force_existing", default = False,
		help="Confirm the use of a previously created system group for the profile. %s, but in some cases (where the group is created by another package or script) this is OK." % styles.stylize(styles.ST_IMPORTANT, "This is risky"))

	parser.add_option_group(profile)

	return (parser.parse_args())
def add_keyword_parse_arguments(app):
	"""Integrated help and options / arguments for « add keyword »."""


	usage_text = "\n\t%s kw|tag|keyword|keywords --name=<keyword> [--parent=<parent_keyword> --description=<description>]\n" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'add_keyword'))

	keyword = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Add keyword options "))

	keyword.add_option("--name",
		action="store", type="string", dest="name", default = None,
		help="The keyword's name. It should be a singular word and %s." % styles.stylize(styles.ST_IMPORTANT, "it is required"))
	keyword.add_option("--parent",
		action="store", type="string", dest="parent", default = "",
		help="Keyword's parent name.")
	keyword.add_option("--description",
		action="store", type="string", dest="description", default = "",
		help="Description of the keyword (free text).")

	parser.add_option_group(keyword)

	return (parser.parse_args())
def add_privilege_parse_arguments(app):
	"""Integrated help and options / arguments for « add keyword »."""

	usage_text = "\n\t%s priv|privs|privilege|privileges [--name|--names=]privilege1[[,privilege2],...]\n" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'add_privilege'))

	priv = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Add privilege options "))

	priv.add_option("--name", "--names",
		action="store", type="string", dest="privileges_to_add", default = None,
		help="The privilege's name(s). %s and can be a single word or multiple ones, separated by commas." % styles.stylize(styles.ST_IMPORTANT, "it is required"))

	parser.add_option_group(priv)

	return (parser.parse_args())
def addimport_parse_arguments(app):
	"""Integrated help and options / arguments for « import users »."""

	usage_text = "\n\t%s users --filename=<fichier> --profile=<profil>\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--lastname-column=<COL>] [--firstname-column=<COL>]\n" \
		+ "\t\t[--group-column=<COL>] [--login-column=<COL>] [--password-column=<COL>]\n" \
		+ "\t\t[--separator=<SEP>] [--confirm-import] [--no-sync]"

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'add_import'))

	addimport = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Import users and groups options "))

	addimport.add_option("--filename",
		action="store", type="string", dest="filename", default = None,
		help="name of the file you want to import accounts from (must point to a valid CSV file and %s)." % styles.stylize(styles.ST_IMPORTANT, "is required"))
	addimport.add_option("--profile",
		action="store", type="string", dest="profile", default = None,
		help="profile the accounts will be affected upon creation (%s)." % styles.stylize(styles.ST_IMPORTANT, "required"))
	addimport.add_option("--lastname-column",
		action="store", type="int", dest="lastname_col", default = 0,
		help="lastname column number (default is %s)." % styles.stylize(styles.ST_DEFAULT, "0"))
	addimport.add_option("--firstname-column",
		action="store", type="int", dest="firstname_col", default = 1,
		help="firstname column number (default is %s)." % styles.stylize(styles.ST_DEFAULT, "1"))
	addimport.add_option("--group-column",
		action="store", type="int", dest="group_col", default = 2,
		help="%s column number (default is %s)." % (styles.stylize(styles.ST_SPECIAL, configuration.groups.names['plural']), styles.stylize(styles.ST_DEFAULT, "2")))
	addimport.add_option("--login-column",
		action="store", type="int", dest="login_col", default = None,
		help="%s column number (default is %s: login will be guessed from firstname and lastname)." \
			% (styles.stylize(styles.ST_SPECIAL, "login"), styles.stylize(styles.ST_DEFAULT, "None")))
	addimport.add_option("--password-column",
		action="store", type="int", dest="password_col", default = None,
		help="%s column number (default is %s: password will be randomly generated and %d chars long)." \
			% (styles.stylize(styles.ST_SPECIAL, "passwd"), styles.stylize(styles.ST_DEFAULT, "None"), configuration.mAutoPasswdSize))
	addimport.add_option("--separator",
		action="store", type="string", dest="separator", default = ";",
		help="separator for the CSV fields (default is %s by sniffing in the file)." % styles.stylize(styles.ST_DEFAULT, "determined automatically"))
	addimport.add_option("--confirm-import",
		action="store_true", dest="confirm_import", default = False,
		help="Really do the import. %s on the system, only give you an example of what will be done, which is useful to verify your file has been correctly parsed (fields order, separator...)." % styles.stylize(styles.ST_IMPORTANT, "Without this flag the program will do nothing"))
	addimport.add_option("--no-sync",
		action="store_true", dest="no_sync", default = False,
		help="Commit changes only after all modifications.")

	parser.add_option_group(addimport)

	return (parser.parse_args())

### Delete arguments ###
def delete_user_parse_arguments(app):
	"""Integrated help and options / arguments for « delete user »."""

	usage_text = "\n\t%s user < --login=<login> | --uid=UID > [--no-archive]" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'del_user'))

	user = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Delete user options "))

	user.add_option("--login", "--name",
		action="store", type="string", dest="login", default = None,
		help="Specify user to delete by login (login or uid %s)." % styles.stylize(styles.ST_IMPORTANT, "required"))
	user.add_option("--uid",
		action="store", type="int", dest="uid", default = None,
		help="Specify user to delete by UID.")
	user.add_option("--no-archive",
		action="store_true", dest="no_archive", default = False,
		help="Don't make a backup of user's home directory in %s (default is %s)." % \
			(styles.stylize(styles.ST_PATH, configuration.home_archive_dir), styles.stylize(styles.ST_DEFAULT, "to make a backup")))

	parser.add_option_group(user)

	return (parser.parse_args())
def delete_group_parse_arguments(app):
	"""Integrated help and options / arguments for « delete group »."""

	usage_text = "\n\t%s group < --name=<nom_groupe> | --uid=UID > [[--del-users] [--no-archive]]" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'del_group'))

	group = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Delete group options "))

	group.add_option("--name",
		action="store", type="string", dest="name", default = None,
		help="Specify group to delete by name (name or GID %s)." % styles.stylize(styles.ST_IMPORTANT, "required") )
	group.add_option("--gid",
		action="store", type="int", dest="gid", default = None,
		help="Specify group to delete by GID.")
	group.add_option("--del-users",
		action="store_true", dest="del_users", default = False,
		help="Delete the group members (user accounts) too (default is to %s, they will become members of %s)." % (styles.stylize(styles.ST_DEFAULT, "not delete members"), styles.stylize(styles.ST_DEFAULT, "nogroup")))
	group.add_option("--no-archive",
		action="store_true", dest="no_archive", default = False,
		help="Don't make a backup of users home directories in %s when deleting members (default is %s)" % (styles.stylize(styles.ST_PATH, configuration.home_archive_dir), styles.stylize(styles.ST_DEFAULT, "to make backups")))

	parser.add_option_group(group)

	return (parser.parse_args())
def delete_profile_parse_arguments(app):
	"""Integrated help and options / arguments for « delete profile »."""

	usage_text = "\n\t%s profile --group=<nom> [[--del-users] [--no-archive] [--no-sync]]" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'del_profile'))

	profile = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Delete profile options "))

	profile.add_option("--group",
		action="store", type="string", dest="group", default = None,
		help="specify profile to delete by its primary group")
	profile.add_option("--del-users",
		action="store_true", dest="del_users", default = False,
		help="the profile's users will be deleted.")
	profile.add_option("--no-archive",
		action="store_true", dest="no_archive", default = False,
		help="don't make a backup of user's home when deleting them.")
	profile.add_option("--no-sync",
		action="store_true", dest="no_sync", default = False,
		help="Commit changes only after all modifications.")

	parser.add_option_group(profile)

	return (parser.parse_args())
def delete_keyword_parse_arguments(app):
	"""Integrated help and options / arguments for « delete keyword »."""

	usage_text = "\n\t%s keyword --name=<nom>" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'del_keyword'))

	keyword = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Delete keyword options "))

	keyword.add_option("--name",
		action="store", type="string", dest="name", default = None,
		help="specify the keyword to delete.")
	keyword.add_option("--del-children",
		action="store_true", dest="del_children", default = False,
		help="delete the parent and his children.")

	parser.add_option_group(keyword)

	return (parser.parse_args())
def del_privilege_parse_arguments(app):
	"""Integrated help and options / arguments for « add keyword »."""

	usage_text = "\n\t%s priv|privs|privilege|privileges [--name|--names=]privilege1[[,privilege2],...]\n" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'del_privilege'))

	priv = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Delete privilege options "))

	priv.add_option("--name", "--names",
		action="store", type="string", dest="privileges_to_remove", default = None,
		help="The privilege's name(s). %s and can be a single word or multiple ones, separated by commas." % styles.stylize(styles.ST_IMPORTANT, "it is required"))

	parser.add_option_group(priv)

	return (parser.parse_args())
def delimport_parse_arguments(app):

	usage_text = "\n\t%s --filename=<fichier> [--no-archive]" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'del_import'))

	delimport = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Un-import users and groups options "))

	delimport.add_option("--filename",
		action="store", type="string", dest="filename", default = None,
		help="")
	delimport.add_option("--no-archive",
		action="store_true", dest="no_archive", default = False,
		help="don't make a backup of user's home when deleting them.")

	parser.add_option_group(delimport)

	return (parser.parse_args())

### Modify arguments ###
def modify_user_parse_arguments(app):

	usage_text = "\n\t%s user --login=<login> [--gecos=<new GECOS>] [--password=<new passwd> | --auto-password] [--password-size=<size>]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ '\t\t[--lock|--unlock] [--add-groups=<group1[[,group2][,...]]>] [--del-groups=<group1[[,group2][,...]]>]\n' \
		+ '\t\t[--shell=<new shell>]\n'  \
		"\t%s user --login=<login> --apply-skel=<squelette>" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser( usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'mod_user'))

	user = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Modify user options "))

	user.add_option("--login", "--name",
		dest="login", default = None,
		help="specify user's login (%s)." % styles.stylize(styles.ST_IMPORTANT, "required"))
	user.add_option("--password", '-p',
		dest="newpassword", default = None,
		help="specify user's new password.")
	user.add_option("--auto-password", '-P',
		action="store_true", dest="auto_passwd",
		help="let the system generate a random password for this user.")
	user.add_option("--password-size", '-S',
		type='int', dest="passwd_size", default = configuration.mAutoPasswdSize,
		help="choose the new password length.")
	user.add_option("--gecos",
		dest="newgecos", default = None,
		help="specify user's new GECOS string (generaly first and last names).")
	user.add_option("--shell",
		dest="newshell", default = None,
		help="specify user's shell (generaly /bin/something).")

	user.add_option("--lock",
		action="store_true", dest="lock", default = None,
		help="lock the account (user wn't be able to login under Linux and Windows/MAC until unlocked).")
	user.add_option("--unlock",
		action="store_false", dest="lock", default = None,
		help="unlock the user account and restore login ability.")

	user.add_option("--add-groups",
		dest="groups_to_add", default = None,
		help="make user member of these groups.")
	user.add_option("--del-groups",
		dest="groups_to_del", default = None,
		help="remove user from these groups.")
	user.add_option("--apply-skel",
		action="store", type="string", dest="apply_skel", default = None,
		help="re-apply the user's skel (use with caution, it will overwrite the dirs/files belonging to the skel in the user's home dir.")

	parser.add_option_group(user)

	return (parser.parse_args())
def modify_group_parse_arguments(app):

	usage_text = "\n\t%s group --name=<nom_actuel> [--rename=<nouveau_nom>]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--add-users=<user1[[,user2][,...]]>] [--del-users=<user1[[,user2][,...]]>]\n" \
		+ "\t\t[--add-resps=<user1[[,user2][,...]]>] [--delete-resps=<user1[[,user2][,...]]>]\n" \
		+ "\t\t[--add-guests=<user1[[,user2][,...]]>] [--delete-guests=<user1[[,user2][,...]]>]\n" \
		+ "\t\t[--permissive|--not-permissive] [--skel=<new skel>] [--description=<new description>]"

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'mod_group'))

	group = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Modify group options "))

	group.add_option("--name",
		action="store", type="string", dest="name", default = None,
		help="specify group's name to modify (%s)." % styles.stylize(styles.ST_IMPORTANT, "required"))
	group.add_option("--rename",
		action="store", type="string", dest="newname", default = None,
		help="specify group's new name (not yet implemented).")
	group.add_option("--skel",
		action="store", type="string", dest="newskel", default = None,
		help="specify group's new skel dir.")
	group.add_option("--description",
		action="store", type="string", dest="newdescription", default = None,
		help="specify new group's description")
	group.add_option("-p", "--permissive", "--set-permissive",
		action="store_true", dest="permissive", default = None,
		help="set the shared directory of the group permissive.")
	group.add_option("-P", "--not-permissive", "--set-not-permissive",
		action="store_false", dest="permissive", default = None,
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
		action="store", type="string", dest="granted_profiles_to_add", default = None,
		help="Add the profiles which the users can access to the group's shared directory. The profiles are separated by commas without spaces.")
	group.add_option("--del-granted-profiles",
		action="store", type="string", dest="granted_profiles_to_del", default = None,
		help="Delete the profiles which the users can access to the group's shared directory. The profiles are separated by commas without spaces.")
	parser.add_option_group(group)

	return (parser.parse_args())
def modify_profile_parse_arguments(app):

	usage_text = "\n\t%s profile --group=<nom> [--name=<nouveau_nom>] [--rename-group=<nouveau_nom>]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--comment=<nouveau_commentaire>] [--shell=<nouveau_shell>] [--skel=<nouveau_skel>]\n" \
		+ "\t\t[--quota=<nouveau_quota>] [--add-groups=<groupes>] [--del-groups=<groupes>]\n" \
		+ "\t%s profile <--apply-groups|--apply-skel|--apply-all> [--force]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--to-users=<user1[[,user2][,...]]>] [--to-groups=<group1[[,group2][,...]]>]\n" \
		+ "\t\t[--to-all] [--to-members] [--no-instant-apply] [--no-sync]"

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'mod_profile'))

	profile = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Modify profile options "))

	profile.add_option("--group", "--name",
		action="store", type="string", dest="group", default = None,
		help="specify profile to modify by its primary group (%s)." % styles.stylize(styles.ST_IMPORTANT, "required"))
	profile.add_option("--rename",
		action="store", type="string", dest="newname", default = None,
		help="specify profile's name")
	profile.add_option("--rename-group",
		action="store", type="string", dest="newgroup", default = None,
		help="Rename primary group.")
	profile.add_option("--comment",
		action="store", type="string", dest="newcomment", default = None,
		help="Change profile's comment.")
	profile.add_option("--shell",
		action="store", type="string", dest="newshell", default = configuration.users.default_shell,
		help="Change profile shell (defaults to %s if you specify --shell without argument)" % styles.stylize(styles.ST_DEFAULT, configuration.users.default_shell))
	profile.add_option("--quota",
		action="store", type="int", dest="newquota", default = 1024,
		help="Change profile's user quota (in Mb, defaults to %s if you specify --quota without argument)." % styles.stylize(styles.ST_DEFAULT, "1024"))
	profile.add_option("--skel",
		action="store", type="string", dest="newskel", default = configuration.users.default_skel,
		help="Change profile skel (specify a skel dir as an absolute pathname, defaults to %s if you give --skel without argument)." % styles.stylize(styles.ST_DEFAULT, configuration.users.default_skel))
	profile.add_option("--add-groups",
		action="store", type="string", dest="groups_to_add", default = None,
		help="Add one or more group(s) to default memberships of profile (separate groups with commas without spaces).")
	profile.add_option("--del-groups",
		action="store", type="string", dest="groups_to_del", default = None,
		help="Delete one or more group(s) from default memberships of profile (separate groups with commas without spaces).")
	profile.add_option("--apply-groups",
		action="store_true", dest="apply_groups", default = False,
		help="Re-apply only the default group memberships of the profile.")
	profile.add_option("--apply-skel",
		action="store_true", dest="apply_skel", default = False,
		help="Re-apply only the skel of the profile.")
	profile.add_option("--apply-all",
		action="store_true", dest="apply_all_attributes", default = False,
		help="Re-apply all the profile's attributes (groups and skel).")
	profile.add_option("--to-users",
		action="store", type="string", dest="apply_to_users", default = None,
		help="Re-apply to specific users accounts (separate them with commas without spaces).")
	profile.add_option("--to-groups",
		action="store", type="string", dest="apply_to_groups", default = None,
		help="Re-apply to all members of one or more groups (separate groups with commas without spaces). You can mix --to-users and --to-groups.")
	profile.add_option("--to-members",
		action="store_true", dest="apply_to_members", default = False,
		help="Re-apply to all users members of the profile.")
	profile.add_option("--to-all",
		action="store_true", dest="apply_to_all_accounts", default = None,
		help="Re-apply to all user accounts on the system (LENGHTY operation !).")
	profile.add_option("--no-instant-apply",
		action="store_false", dest="instant_apply", default = True,
		help="Don't apply group addition/deletion instantly to all members of the modified profile (%s; use this only if you know what you're doing)." % styles.stylize(styles.ST_IMPORTANT, "this is not recommended"))
	profile.add_option("--no-sync",
		action="store_true", dest="no_sync", default = False,
		help="Commit changes only after all modifications.")

	parser.add_option_group(profile)

	return (parser.parse_args())
def modify_keyword_parse_arguments(app):

	usage_text = "\n\t%s keyword --name=<nom> [--rename=<nouveau_nom>] [--parent=<nouveau_parent>]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--remove-parent] [--recursive]"

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'mod_profile'))

	keyword = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Modify keyword options "))

	keyword.add_option("--name",
		action="store", type="string", dest="name", default = None,
		help="specify keyword to modify (%s)." % styles.stylize(styles.ST_IMPORTANT, "required"))
	keyword.add_option("--rename",
		action="store", type="string", dest="newname", default = None,
		help="Rename keyword")
	keyword.add_option("--parent",
		action="store", type="string", dest="parent", default = None,
		help="Change keyword's parent.")
	keyword.add_option("--remove-parent",
		action="store_true", dest="remove_parent", default = False,
		help="Remove parent.")
	keyword.add_option("--recursive",
		action="store_true", dest="recursive", default = False,
		help="Modify all file in all subdirs.")
	keyword.add_option("--description",
		action="store", type="string", dest="description", default = None,
		help="Remove parent.")

	parser.add_option_group(keyword)

	return (parser.parse_args())
def modify_path_parse_arguments(app):

	usage_text = "\n\t%s path [--path=]<fichier_ou_repertoire> [--add-keywords=<kw1[,kw1,...]>] [--del-keywords=<kw1[,kw1,...]>]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t\t[--clear-keywords] [--recursive]"

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# common behaviour group
	parser.add_option_group(__common_behaviour_group(app, parser, 'mod_path'))

	path = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Modify keyword options "))

	path.add_option("--path",
		action="store", type="string", dest="path", default = None,
		help="specify path of the file/directory to tag (%s)." % styles.stylize(styles.ST_IMPORTANT, "required"))
	path.add_option("--add-keywords",
		action="store", type="string", dest="keywords_to_add", default = None,
		help="Add keywords.")
	path.add_option("--del-keywords",
		action="store", type="string", dest="keywords_to_del", default = None,
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

	return (parser.parse_args())
def modify_configuration_parse_arguments(app):

	usage_text = "\n\t%s config[uration] [--hide-groups|--set-hidden-groups|--unhide-groups|-u|-U] [--set-hostname <new hostname>] [--restrictive] [--set-ip-address <NEW.ETH0.IP.ADDR>]" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	# FIXME: review __common_behaviour_group to set eventual special options (for modify config ?).
	parser.add_option_group(__common_behaviour_group(app, parser, 'mod_config'))

	configuration_group = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Modify configuration options "))

	configuration_group.add_option("--setup-shared-dirs",
		action="store_true", dest="setup_shared_dirs", default=False,
		help='''create system groups, directories and settings from system '''
			'''configuration (PARTIALLY OBSOLETED, TOTALLY UNSUPPORTED AND '''
			'''VERY DANGEROUS, USE WITH CAUTION).''')

	configuration_group.add_option("-r", "--restrictive", "--set-restrictive",
		action="store_true", dest="restrictive", default=False,
		help="when creating system groups and directories, apply restrictive perms (710) on shared dirs instead of relaxed ones (750).")

	configuration_group.add_option("-u", "--hide-groups", "--set-groups-hidden",
		action="store_true", dest="hidden_groups", default=None,
		help="Set restrictive perms (710) on %s." % styles.stylize(styles.ST_PATH,
		"%s/%s" % (configuration.defaults.home_base_path,
			configuration.groups.names['plural'])))

	configuration_group.add_option("-U", "--unhide-groups", "--set-groups-visible",
		action="store_false", dest="hidden_groups", default=None,
		help="Set relaxed perms (750) on %s." % styles.stylize(styles.ST_PATH,
		"%s/%s" % (configuration.defaults.home_base_path,
			configuration.groups.names['plural'])))

	configuration_group.add_option('-b', "--enable-backends",
		action="store", dest="enable_backends", default=None,
		help='''enable given backend(s) on the current system (separated '''
			'''by commas without spaces). List of available backends with '''
			'''`%s`.''' % styles.stylize(styles.ST_MODE,
				'get config backends'))

	configuration_group.add_option('-B', "--disable-backends",
		action="store", dest="disable_backends", default=None,
		help='''disable given backend(s) on the current system (separated '''
			'''by commas without spaces). List of available backends with '''
			'''`%s`.''' % styles.stylize(styles.ST_MODE,
				'get config backends'))

	configuration_group.add_option("-e", "--set-hostname",
		action="store", type="string", dest="set_hostname", default=None,
		help="change machine hostname.")

	configuration_group.add_option("-i", "--set-ip-address",
		action="store", type="string", dest="set_ip_address", default=None,
		help="change machine's IP (for eth0 only).")

	configuration_group.add_option("--add-privileges",
		action="store", type="string", dest="privileges_to_add", default=None,
		help="add privileges (system groups) to privileges whitelist.")

	configuration_group.add_option("--remove-privileges",
		action="store", type="string", dest="privileges_to_remove", default=None,
		help="remove privileges (system groups) from privileges whitelist.")

	parser.add_option_group(configuration_group)

	return (parser.parse_args())

### Check arguments ###
def __check_filter_group(app, parser, mode):
	"""Build Filter OptionGroup for all check variants."""

	filtergroup = OptionGroup(parser, styles.stylize(styles.ST_OPTION, "Filter options "), "Filter data displayed / exported.")

	if mode in ( 'users', 'groups', 'config', 'configuration'):
		filtergroup.add_option("-a", "--all",
			action="store_true", dest="all", default = False,
			help="check *all* %s. %s: this can be a very long operation, depending of the number of %s on your system." % (styles.stylize(styles.ST_MODE, mode), styles.stylize(styles.ST_IMPORTANT, "WARNING"), mode))

	if mode is 'users':
		filtergroup.add_option("--login", "--name",
			action="store", type="string", dest="users", default = None,
			help="Specify user account(s) to check by their login (%s if --all not specified, separated by commas without spaces)." % styles.stylize(styles.ST_IMPORTANT, "required") )

	elif mode is 'groups':
		filtergroup.add_option("--name",
			action="store", type="string", dest="groups", default = None,
			help="Specify group(s) to check by their name (%s if --all not specified, separated by commas without spaces)." % styles.stylize(styles.ST_IMPORTANT, "required") )
		"""

		# TODO: add these one day or not ?

		filtergroup.add_option("--privileged",
			action="store_true", dest="privileged", default = False,
			help="Only get privileged groups.")
		filtergroup.add_option("--responsibles",
			action="store_true", dest="responsibles", default = False,
			help="Only get responsibles groups.")
		filtergroup.add_option( "--guests",
			action="store_true", dest="guests", default = False,
			help="Only get guests groups.")
		filtergroup.add_option("--gid",
			action="store", type="int", dest="gid", default = None,
			help="Display only one group information, identified by its GID.")
		"""
	elif mode is 'profiles':
		filtergroup.add_option("--profile",
			action="store", type="string", dest="profile", default = None,
			help="TODO")

	return filtergroup
def check_users_parse_arguments(app):
	"""Integrated help and options / arguments for « check user(s) »."""

	usage_text = "\n\t%s user[s] --login login1[[,login2][...]] [--minimal] [--yes|--no]\n" % styles.stylize(styles.ST_APPNAME, "%prog") \
		+ "\t%s user[s] --uid uid1[[,uid2][...]] [--minimal] [--yes|--no]" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'check'))
	parser.add_option_group(__check_filter_group(app, parser, 'users'))

	return (parser.parse_args())
def check_groups_parse_arguments(app):
	"""Integrated help and options / arguments for « check group(s) »."""

	usage_text = "\n\t%s group[s] --name group1[[,group2][...]]" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'check'))
	parser.add_option_group(__check_filter_group(app, parser, 'groups'))

	return (parser.parse_args())
def check_profiles_parse_arguments(app):
	"""Integrated help and options / arguments for « check profile(s) »."""

	usage_text = "\n\t%s profile[s] --name profile1[[,profile2][...]]" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'check'))
	parser.add_option_group(__check_filter_group(app, parser, 'profiles'))

	return (parser.parse_args())
def check_configuration_parse_arguments(app):
	"""TODO"""

	usage_text = "\n\t%s config[uration] -a | (names|hostname)" % styles.stylize(styles.ST_APPNAME, "%prog")

	parser = OptionParser(usage = usage_text, version = __build_version_string(app))

	parser.add_option_group(__common_behaviour_group(app, parser, 'check'))
	parser.add_option_group(__check_filter_group(app, parser, 'configuration'))

	return (parser.parse_args())
