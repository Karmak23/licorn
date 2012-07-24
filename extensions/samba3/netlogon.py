# -*- coding: utf-8 -*-
"""
Licorn® netlogon helper:

- eventually overwrites the user's profile, depending on various parameters
- creates a netlogon .cmd scripts, depending on various parameters too.

For more informations, see http://docs.licorn.org/extensions/samba3

#
# smb.conf call:
# see smb.conf(5) > VARIABLE SUBSTITUTIONS
#
#	root preexec = add event --name 'user_logged_in' --kwargs '{ \
#					"client_arch": "%a", \
#					"client_smbname": "%m", \
#					"client_hostname": "%M", \
#					"client_ipaddr": "%I", \
#					"user_login": "%u", \
#					"user_group": "%g", \
#					"user_session_name": "%U", \
#					"user_session_group": "%G", \
#					"user_domain": "%D", \
#					"service_name": "%S", \
#					"service_path": "%P", \
#					"winbind_separator": "%w", \
#					"server_smbname": "%L", \
#					"server_hostname": "%h", \
#					"server_ipaddr": "%i", \
#					}'
#

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/
:license: GNU GPL version 2
"""

import os
from operator import attrgetter

from licorn.foundations        import settings, logging, exceptions
from licorn.foundations        import styles
from licorn.foundations.styles import *

from licorn.core               import LMC

# This is needed. See `licorn.foundations` for details.
stylize = styles.stylize

pretty_name = stylize(ST_NAME, 'netlogon')

MS_BASE_DIR           = os.path.join(settings.defaults.home_base_path, 'windows')
NETLOGON_BASE_DIR     = os.path.join(MS_BASE_DIR, 'netlogon')
TEMPLATES_BASE_DIR    = os.path.join(NETLOGON_BASE_DIR, 'templates')
CUSTOM_BASE_DIR       = os.path.join(NETLOGON_BASE_DIR, 'local')
USERS_PROFILES_DIR    = os.path.join(MS_BASE_DIR, 'profiles', 'Users')
GROUPS_PROFILES_DIR   = os.path.join(MS_BASE_DIR, 'profiles', 'Groups')
MACHINES_PROFILES_DIR = os.path.join(MS_BASE_DIR, 'profiles', 'Machines')


def netlogon(*args, **kwargs):

	def script_start():
		return '''
	@echo off
	rem
	rem {0}
	rem
	rem {1}
	rem {2}
	rem
	rem {3}
	rem {4}
	rem
	rem {5}
	echo.
	echo.
	echo.
	echo.
	echo       {6}
	echo.
	echo.
	echo.
	echo.
	echo {7}

	set servname={8}
	'''.format(
			_(u'Licorn® netlogon script'),
			_(u'WARNING: do not modify this script directly:'),
			_(u'it has been auto-generated, and will be overwritten next time the user logs in.'),
			_(u'If you would like to customize it, use templates from {0}').format(TEMPLATES_BASE_DIR),
			_(u'for inspiration, and create new scripts in {0}.').format(CUSTOM_BASE_DIR),
			_(u'For more information, visit http://docs.licorn.org/extensions/samba3'),
			_('Hello {0} and welcome to {1}!').format(user_session_name, server_smbname),
			_(u'{0} generated on {1}').format(script_filename, time.strftime('%c')),
			server_smbname
		).replace('\n', '\r')
	def script_build_levels():
		""" Build a list of different script base names that we will try to
			construct the user's final netlogon script. """

		levels = [ '_base', client_smbname, server_smbname, user_domain ]

		if user in admins:
			levels.append('_admins')

		if is_responsible:
			levels.append('_responsibles')

		else:
			levels.append('_users')

		# Groups will be sorted by quasi importance:
		# at least system groups come before standard ones
		levels.extend(g.name for g in sorted(user.groups, key=attrgetter('gid')))

		levels.append(user.login)

		return levels
	def script_out(msg):
		# this function will write the script in a Windows-friendly way
		script_buffer += '%s\r' % msg
	def netlogon_profile():

		# Windows® profiles priorities:
		#
		# - if the user is an administrator, his profile will be left untouched
		# - else:
		#	- if the machine has a fixed profile, use it
		#	- if not, if the group has a fixed profile, use it
		#	- if not, if the user has a fixed profile, use it
		#	- else, let Windows do whatever it wants

		overwriter_profile = None

		if user not in admins:
			for profile_path, profile_name in (
									(MACHINES_PROFILES_DIR, machine)
									(GROUPS_PROFILES_DIR, user.primaryGroup.name)
									(USERS_PROFILES_DIR, user.login)
				):

				potential_overwriter = os.path.join(profile_path, profile_name)

				if os.path.exists(potential_overwriter):
					overwriter_profile = potential_overwriter

					# the first one found takes precedence
					break

		if potential_overwriter:
			# WARNING: the `samba3` or `samba4` extension should be enabled,
			# and Samba fully configured for this to work properly.

			# user.sambaHomeDirectory should be something
			# like ~user/.samba/windows/ or ~user/windows

			assert ltrace(TRACE_SAMBA3, '  Profile rewrite for user {0}, based on {1}',
													user.login, potential_overwriter)

			for thing_to_overwrite, remove_first in (
													# TODO: localize the names
													('Programmes', True),
													('Menu Démarrer', True),
													('Bureau', False)
												):

				source      = os.path.join(potential_overwriter, thing_to_overwrite)
				destination = os.path.join(user.sambaHomeDirectory, thing_to_overwrite)

				if remove_first:
					try:
						shutil.rmtree(destination)

					except (IOError, OSError), e:
						if e.errno != errno.ENOENT:
							logging.exception(_(u'{0}: exception while removing {1}, this '
								u'could lead to inconsistencies in {2}\'s profile.'),
									pretty_name, (ST_PATH, destination),
									(ST_NAME, user.login))

				try:
					shutil.copy(source, destination)

				except (OSError, IOError), e:
					logging.exception(_(u'{0}: exception while copying {1} to {2}, '
								u'this could lead to inconsistencies in {3}\'s profile.'),
									pretty_name, (ST_PATH, source),
									(ST_PATH, destination), (ST_NAME, user.login))

				# NOTE: we don't enqueue this as a job, because permissions
				# must be OK *before* the user logs in, else Windows® could
				# fail to log him in if it can't access some dirs.
				user._fast_aclcheck(destination, expiry_check=True)

	def netlogon_script():

		assert ltrace_func(TRACE_SAMBA3)

		try:
			# A user script is always rewritten from scratch at every user login,
			# to always be up-to-date regarding factory and customized scripts.
			os.unlink(script_filename)

		except (OSError, IOError), e:
			if e.errno != errno.ENOENT:
				logging.exception(_(u'{0}: exception while removing old script {1}, '
								u'this could lead to inconsistencies in {2}\'s profile.'),
									pretty_name, (ST_PATH, script_filename),
									(ST_NAME, user.login))

		assert ltrace(TRACE_SAMBA3, '  Netlogon script {0} build start', script_filename)

		for script_part in script_levels:

			to_add = None

			for script, var_prefix in (
					# local customized script
					(os.path.join(CUSTOM_BASE_DIR, script_part + '.cmd'), script_part),

					# idem, but backward compatible
					(os.path.join(TEMPLATES_BASE_DIR, script_part + '-local.cmd'), script_part + '-local'),

					# last resort, a factory-shipped script
					(os.path.join(TEMPLATES_BASE_DIR, script_part + '.cmd'), script_part),
				):
				if os.path.exists(script):
					to_add = script

					# the first found takes precedence, others are not tested.
					break

			if to_add:
				assert ltrace(TRACE_SAMBA3, '	Netlogon build script add {1}', script)

				script_out('set {0}_osver={0}_{1}'.format(var_prefix, client_arch))
				script_out()
				script_out('setlocal')
				script_buffer += open(script).read().replace('\n', '\r')
				script_out('endlocal')

		assert ltrace(TRACE_SAMBA3, '  Netlogon script {0} build end', script_filename)
		assert ltrace_func(TRACE_SAMBA3, 1)

	user                  = LMC.users.by_login(kwargs.pop('user_login'))
	user_session_name     = kwargs.pop('user_session_name')
	user_domain           = kwargs.pop('user_domain')
	admins                = LMC.groups.by_name(settings.defaults.admin_group)
	licorn_wmi            = LMC.groups.by_name(settings.licornd.wmi.group)

	# The user is considered "responsible" of something if he is a member of
	# the licorn-wmi group, or if he is responsible of any standard group.
	is_responsible        = bool(user in licorn_wmi or [g for g in user.groups if g.is_responsible])

	machine               = kwargs.pop('client_smbname')
	server_smbname        = kwargs.pop('server_smbname')

	script_filename       = os.path.join(NETLOGON_BASE_DIR, machine + '.cmd')
	script_levels         = script_build_levels()
	script_buffer         = script_start()

	netlogon_profile()
	netlogon_script()

__all__ = (
	'netlogon',
	'MS_BASE_DIR',
	'NETLOGON_BASE_DIR',
	'TEMPLATES_BASE_DIR',
	'CUSTOM_BASE_DIR',
	'USERS_PROFILES_DIR',
	'GROUPS_PROFILES_DIR',
	'MACHINES_PROFILES_DIR',
	)
