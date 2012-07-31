# -*- coding: utf-8 -*-
"""
Licorn® netlogon helper:

- eventually overwrites the user's profile, depending on various parameters
- creates a netlogon .cmd scripts, depending on various parameters too.

For more informations, see http://docs.licorn.org/extensions/samba3


How to run the Licorn® netlogon script from :file:`/etc/samba/smb.conf` (or any included file)::

	root preexec = add event --name 'user_logged_in' --synchronous --kwargs '{ \
					"event_source": "samba3-netlogon", \
					"client_arch": "%a", \
					"client_smbname": "%m", \
					"client_hostname": "%M", \
					"client_ipaddr": "%I", \
					"user_login": "%u", \
					"user_group": "%g", \
					"user_session_name": "%U", \
					"user_session_group": "%G", \
					"user_domain": "%D", \
					"service_name": "%S", \
					"service_path": "%P", \
					"server_smbname": "%L", \
					"server_hostname": "%h", \
					"server_ipaddr": "%i", \
					}'

See smb.conf(5) `VARIABLE SUBSTITUTIONS` for the meanings of ``%`` codes, but you have a good starting point here. Not all variables are used, but in case they are, we pass them all.

.. note:: It doesn't matter if you write the whole command on one line or not
	in :file:`/etc/samba/smb.conf` (or any included file), as long as you use
	the backslashes '\' to mark the line continuation, like in any other good
	Unix script.

.. warning: in the default configuration, passing this::

		"winbind_separator": "%w",

	will make the whole thing fail, because the default
	winbind separator is '\' and this will confuse any
	standard parser on the planet, including the one used
	in Licorn®.

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/
:license: GNU GPL version 2
"""

import os, time, shutil, errno
from operator import attrgetter

from licorn.foundations        import settings, logging, exceptions
from licorn.foundations        import styles
from licorn.foundations.styles import *

from licorn.core               import LMC

# This is needed. See `licorn.foundations` for details.
stylize = styles.stylize

pretty_name = stylize(ST_NAME, 'samba3-netlogon')

def netlogon(*args, **kwargs):

	def script_base():
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
echo               {6}
echo.
echo.
echo.
echo.
echo   {7}

set servname={8}
'''.format(
			_(u'Licorn® netlogon script'),
			_(u'WARNING: do not modify this script directly:'),
			_(u'it has been auto-generated, and will be overwritten next time the user logs in.'),
			_(u'If you would like to customize it, use templates from {0}').format(paths.netlogon_templates_dir),
			_(u'for inspiration, and create new scripts in {0}.').format(paths.netlogon_custom_dir),
			_(u'For more information, visit http://docs.licorn.org/extensions/samba3'),
			_('Hello {0} and welcome to {1}!').format(user_session_name, server_smbname),
			_(u'{0} generated on {1}').format(script_filename, time.strftime('%c')),
			server_smbname
		).replace('\n', '\r\n')
	def script_build_levels():
		""" Build a list of different script base names that we will try to
			construct the user's final netlogon script. """

		levels = [ '__header', client_smbname, server_smbname, user_domain ]

		# The 3 first could be automatically done if the user is member of
		# the groups, but they need to be sourced *in that order* for
		# permissions (registry files) to be applied up-bottom, else even
		# administrators could be locked down if done in the wrong order.

		if user in admins:
			levels.append('admins')

		if user in samba_admins:
			levels.append('samba-admins')

		if user in responsibles:
			levels.append('responsibles')

		else:
			levels.append('users')

		# Groups will be sorted by quasi importance: at
		# least system groups come before standard ones.
		levels.extend(g.name for g in sorted(user.groups, key=attrgetter('gid'))
													if g.name not in levels)

		levels.append(user.login)

		return levels

	smb3ext               = LMC.extensions.samba3
	paths                 = smb3ext.paths

	# Samba variables used in Licorn® netlogon
	user                  = LMC.users.by_login(kwargs.pop('user_login'))
	user_session_name     = kwargs.pop('user_session_name')
	user_domain           = kwargs.pop('user_domain')
	client_arch           = kwargs.pop('client_arch')
	client_smbname        = kwargs.pop('client_smbname')
	server_smbname        = kwargs.pop('server_smbname')

	# Licorn® core objects used for various checks.
	admins                = LMC.groups.by_name(settings.defaults.admin_group)
	samba_admins          = LMC.groups.by_name(smb3ext.groups.admins)
	responsibles          = LMC.groups.by_name(smb3ext.groups.responsibles)

	# The final netlogon script
	script_filename       = os.path.join(paths.netlogon_base_dir, client_smbname + '.cmd')
	script_levels         = script_build_levels()
	script_buffer         = script_base()

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
					(paths.profiles_templates_machines_dir, client_smbname),
					(paths.profiles_templates_groups_dir, user.primaryGroup.name),
					(paths.profiles_templates_users_dir, user.login),
				):

				potential_overwriter = os.path.join(profile_path, profile_name)

				if os.path.exists(potential_overwriter):
					overwriter_profile = potential_overwriter

					# the first one found takes precedence
					break

		if overwriter_profile:
			# WARNING: the `samba3` or `samba4` extension should be enabled,
			# and Samba fully configured for this to work properly.

			# user.sambaHomeDirectory should be something
			# like ~user/.samba/windows/ or ~user/windows

			logging.progress(_(u'{0}: Windows® profile rewrite for user {1} '
								u'based on {2}…').format(pretty_name,
									stylize(ST_LOGIN, user.login),
									stylize(ST_PATH, potential_overwriter)))

			for thing_to_overwrite, remove_first in (
													# TODO: localize the names
													('Programmes', True),
													('Menu Démarrer', True),
													('Bureau', False)
												):

				source      = os.path.join(potential_overwriter, thing_to_overwrite)
				destination = os.path.join(paths.profiles_current_dir,
											user.login, thing_to_overwrite)

				if remove_first:
					try:
						shutil.rmtree(destination)

					except (IOError, OSError), e:
						if e.errno != errno.ENOENT:
							logging.exception(_(u'{0}: exception while '
												u'removing {1}, this could '
												u'lead to inconsistencies in '
												u'{2}\'s Windows® profile.'),
													pretty_name,
													(ST_PATH, destination),
													(ST_NAME, user.login))

				try:
					shutil.copy(source, destination)

				except (OSError, IOError), e:
					logging.exception(_(u'{0}: exception while copying {1} to '
										u'{2}, this could lead to '
										u'inconsistencies in {3}\'s Windows® '
										u'profile.'), pretty_name,
											(ST_PATH, source),
											(ST_PATH, destination),
											(ST_NAME, user.login))

				# NOTE: we don't enqueue this as a job, because permissions
				# must be OK *before* the user logs in, else Windows® could
				# fail to log him in if it can't access some dirs.
				user._fast_aclcheck(destination, expiry_check=True)

			logging.info(_(u'{0}: user {1} Windows® profile overwritten '
								u'by {2}.').format(pretty_name,
									stylize(ST_LOGIN, user.login),
									stylize(ST_PATH, potential_overwriter)))

	def script_out(msg=None):
		return '%s\r\n' % (msg or '')
	def netlogon_script(script_buffer=script_buffer):

		assert ltrace_func(TRACE_SAMBA3)

		try:
			# A user script is always rewritten from scratch at every user login,
			# to always be up-to-date regarding factory and customized scripts.
			os.unlink(script_filename)

		except (OSError, IOError), e:
			if e.errno != errno.ENOENT:
				logging.exception(_(u'{0}: exception while removing old '
									u'script {1}, this will probably lead to '
									u'inconsistencies in {2}\'s Windows® session.'),
										pretty_name, (ST_PATH, script_filename),
										(ST_NAME, user.login))


		logging.progress(_(u'{0}: creating netlogon script for '
							u'user {1} with levels {2}…').format(pretty_name,
								stylize(ST_LOGIN, user.login),
								u','.join(stylize(ST_ATTRVALUE, x)
									for x in script_levels)))

		for script_part in script_levels:

			to_add = None

			for script, var_prefix in (
					# local customized script
					(os.path.join(paths.netlogon_custom_dir, script_part + '.cmd'), script_part),

					# idem, but backward compatible
					(os.path.join(paths.netlogon_templates_dir, script_part + '-local.cmd'), script_part + '-local'),

					# last resort, a factory-shipped script
					(os.path.join(paths.netlogon_templates_dir, script_part + '.cmd'), script_part),
				):
				if os.path.exists(script):
					to_add = script

					# the first found takes precedence, others are not tested.
					break

			if to_add:
				assert logging.debug(_(u'{0}: user {1}, adding {2}.').format(
									pretty_name, stylize(ST_NAME, user.login),
									stylize(ST_PROG, to_add)))

				script_buffer += script_out('setlocal')
				script_buffer += script_out()
				script_buffer += script_out('set {0}_osver={0}_{1}'.format(
								# CMD variables can't have '-' in their name.
								var_prefix.replace('-', '_'), client_arch))
				script_buffer += script_out()
				script_buffer += open(script).read().replace('\n', '\r\n')
				script_buffer += script_out('endlocal')
				script_buffer += script_out()

		with open(script_filename, 'wb') as f:
			f.write(script_buffer)
			f.flush()

		logging.info(_('{0}: written {1}\' netlogon script {2}.').format(
									pretty_name, stylize(ST_LOGIN, user.login),
										stylize(ST_PATH, script_filename)))

		assert ltrace_func(TRACE_SAMBA3, 1)

	netlogon_profile()
	netlogon_script()

__all__ = ('netlogon', )
