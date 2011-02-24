# -*- coding: utf-8 -*-
"""
Licorn Fondations - http://dev.licorn.org/

argparser - command-line argument parser library.
Contains common argument parser for daemon, CLI, etc.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>,
Licensed under the terms of the GNU GPL version 2.
"""

from optparse import OptionGroup

from styles import *

def build_version_string(app, version):
	"""return a string ready to be displayed, containing app_name,
		version, authors…"""
	return ('''%s (%s) version %s\n(C) 2004-2010 %s\nlicensed under the '''
		'''terms of the GNU GPL v2. See %s for project details.''' % (
			stylize(ST_APPNAME, app["name"]),
			app["description"], version,
			app["author"],
			stylize(ST_URL, "http://dev.licorn.org/")
			)
		)
def common_behaviour_group(app, parser, mode='any'):
	""" This group is common to all Licorn System Tools."""
	behaviorgroup = OptionGroup(parser, stylize(ST_OPTION,
		"Behavior options"),
		"Modify decisions / output of program.")

	if mode != "get":
		if mode == "check":
			behaviorgroup.add_option("-e", "--extended",
				action="store_false", dest="minimal", default = True,
				help='''Execute extended checks (%s, which is to make the '''
				'''bare minimum checks for the system to operate properly).''' %
				stylize(ST_DEFAULT, "not the default") )

		if mode in ('check',
			'add_user', 'mod_user', 'del_user',
			'mod_group', 'del_group',
			'mod_profile', 'del_profile',
			'del_privilege'):
			behaviorgroup.add_option("-y", "--yes", "--auto-yes",
				action="store_true", dest="auto_answer", default = None,
				help="Automatically answer 'yes' to all repair questions (i.e. "
					"repair everything that can be) (default: %s, each question"
					" will be asked at one time)." %
						stylize(ST_DEFAULT, "None"))
			behaviorgroup.add_option("--no", "--auto-no",
				action="store_false", dest="auto_answer", default = None,
				help="Automatically answer 'no' to all repair questions (i.e. "
					"don't repair anything, just print the warnings)." )
			behaviorgroup.add_option("--batch", "-b",
				action="store_true", dest="batch", default = False,
				help="batch all operations (don't ask questions, automate "
					"everything).")
		if mode in ('check', 'del_user', 'del_group', 'del_profile',
			'del_privilege', 'mod_user', 'mod_group', 'mod_profile'):
			behaviorgroup.add_option('-i', "--interactive",
				action="store_false", dest="non_interactive", default = True,
				help='''Make the command interactive, ie. ask for '''
					'''confirmation at every important step (default: '''
					'''False).''')

		behaviorgroup.add_option("-f", "--force",
			action="store_true", dest="force", default = False,
			help="forces the current action (if applicable).")

	behaviorgroup.add_option("-q", "--quiet",
		action="store_const", dest="verbose", const = 0,
		help="be quiet, don't display anything except on warnings/errors." )
	behaviorgroup.add_option("-v", "--verbose",
		action="count", dest="verbose", default = 1,
		help="be more verbose (in command-line mode) ; you can get more with "
			"-vv, -vvv, etc.%s, which is quite moderated. You will get "
			"information about auto-generated passwords and long-time actions, "
			"when you should expect to wait for them to complete." %
				stylize(ST_DEFAULT, "the default level of verbosity is NOTICE"))
	behaviorgroup.add_option("--no-colors",
		action="store_true", dest="no_colors", default = False,
		help="no colors in any messages (CLI mode only).")

	return behaviorgroup
