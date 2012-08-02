# -*- coding: utf-8 -*-
"""
Licorn extensions: samba3 - http://docs.licorn.org/extensions/samba3.html

:copyright:
	* 2011-2012 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2

"""

import os, errno

from licorn.foundations           import settings, logging, events
from licorn.foundations           import process, fsapi
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, MixedDictObject, \
											LicornConfigObject
from licorn.foundations.constants import distros, services, svccmds, \
											priorities, filters

from licorn.core         import LMC
from licorn.core.classes import only_if_enabled
from licorn.extensions   import LicornExtension

import netlogon

class Samba3Extension(ObjectSingleton, LicornExtension):
	""" Handle Samba3 the minimal way: just ensure that user accounts are in
		sync with Samba via :program:`smbpasswd` calls. This implements the exact
		same

		.. versionadded:: 1.3

	"""
	def __init__(self):
		assert ltrace_func(TRACE_EXTENSIONS)
		LicornExtension.__init__(self, name='samba3')

		# nothing to do on the client side.
		self.server_only  = True

		# users and groups can get calendars.
		self.controllers_compat = [ 'users' ]

		# Path is the same on Ubuntu / Debian
		self.paths.smbpasswd  = '/usr/bin/smbpasswd'
		self.paths.smb_conf   = '/etc/samba/smb.conf'
		self.paths.smb_daemon = '/usr/sbin/smbd'

		self.paths.defaults   = LicornConfigObject()

		self.__build_default_paths()

		self.users               = LicornConfigObject()
		self.groups              = LicornConfigObject()

		self.users.data       = settings.get(
										'extensions.samba3.users.data',
										'samba-data')
		self.groups.data       = settings.get(
										'extensions.samba3.groups.data',
										'samba-data')
		self.groups.admins     = settings.get(
										'extensions.samba3.groups.admins',
										'samba-admins')
		self.groups.machines     = settings.get(
										'extensions.samba3.groups.machines',
										'machines')
		self.groups.responsibles = settings.get(
										'extensions.samba3.groups.responsibles',
										'responsibles')

		if LMC.configuration.distro in (distros.UBUNTU,
										distros.LICORN,
										distros.DEBIAN):
			# TODO: when this extension will be turned into a ServiceExtension,
			# we should check /etc/default/samba::RUN_MODE and don't do anything
			# if it is 'inetd'.
			self.paths.service_defaults = '/etc/default/samba'
	def users_load(self, *args, **kwargs):
		""" Nothing particular to do here. """
		pass
	def initialize(self):
		""" Set :attr:`self.available` to ``True`` if smbpasswd is
			found on the local system, else ``False``. """

		assert ltrace_func(TRACE_SAMBA3)

		if os.path.exists(self.paths.smbpasswd) or (
				os.path.exists(self.paths.smb_conf)
				and os.path.exists(self.paths.smb_daemon)):

			try:
				smb_version = process.execute(('smbclient', '-V')
											)[0].split(' ')[1].strip()

			except (OSError, IOError), e:
				if e.errno == errno.ENOENT:
					# This could be perfectly normal, while installing
					# the debian package: samba is a dependancy and will
					# be found later. On daemon restart, all will be fine.
					smb_version = u'<smbclient_not_found>'

				else:
					logging.exception(_(u'{0}: exception while running '
							u'{1}'), self.pretty_name, stylize(ST_COMMENT, 'smbclient -V'))
					smb_version = u'<smbclient_failed>'

			logging.info(_(u'{0}: extension enabled on top of {1} version '
				u'{2}.').format(self.pretty_name, stylize(ST_NAME, 'smbd'
					if os.path.exists(self.paths.smb_daemon)
					else 'smbpasswd'), stylize(ST_UGID, smb_version)))

			self.available = True

		else:
			logging.info(_(u'{0}: extension disabled because {1} '
							u' nor ({2} and {3}) not found.').format(
								self.pretty_name,
								stylize(ST_PATH, self.paths.smbpasswd),
								stylize(ST_PATH, self.paths.smb_conf),
								stylize(ST_PATH, self.paths.smb_daemon)))
			self.available = False

		return self.available
	def check(self, batch=False, auto_answer=None):
		""" Currently, this method does nothing: this extension is so simple
			that we don't do anything needing a check in it. """
		assert ltrace_func(TRACE_SAMBA3)

		descriptions = {
			self.users.data          : _('Samba/Windows® data holder'),
			self.groups.data         : _('Windows® data holder for shared programs directories'),
			self.groups.admins       : _('Windows®(-only) domain administrators'),
			self.groups.machines     : _('Windows® workstations members of the MS domain'),
			self.groups.responsibles : _('Users responsible of at least one group'),
			}

		for group in self.groups:
			if not LMC.groups.exists(name=group):
				if batch or logging.ask_for_repair(_(u'{0}: group {1} must be '
									u'created. Do it?').format(
									self.pretty_name,
									stylize(ST_NAME, group)),
								auto_answer=auto_answer):

					LMC.groups.add_Group(name=group,
										description=descriptions[group],
										system=True, batch=batch)
				else:
					raise exceptions.LicornCheckError(_(u'{0}: group {1} must '
										u'exist before continuing.').format(
											self.pretty_name,
											stylize(ST_NAME, group)))

		for user in self.users:
			if not LMC.users.exists(login=user):
				if batch or logging.ask_for_repair(_(u'{0}: user {1} must be '
									u'created. Do it?').format(
									self.pretty_name,
									stylize(ST_NAME, user)),
								auto_answer=auto_answer):

					LMC.users.add_User(login=user,
										gecos=descriptions[user],
										disabled_password=True,
										shell='/bin/false',
										primary_group=LMC.groups.by_name(self.groups.data),
										system=True, batch=batch, force=True)
				else:
					raise exceptions.LicornCheckError(_(u'{0}: group {1} must '
										u'exist before continuing.').format(
											self.pretty_name,
											stylize(ST_NAME, group)))

		self.__check_paths(batch=batch, auto_answer=auto_answer)
		self.__check_responsibles(batch=batch, auto_answer=auto_answer)

		# TODO:
		#	- check smb.conf
		#	- check groups (conf contents and inclusions)
		#	- check users

		return True
	def __build_default_paths(self):

		self.paths.windows_base_dir = settings.get(
									'extensions.samba3.paths.windows_base_dir',
									os.path.join(settings.defaults.home_base_path, 'windows'))

		# NETLOGON .CMD scripts
		self.paths.netlogon_base_dir = settings.get(
									'extensions.samba3.paths.netlogon_base_dir',
									os.path.join(self.paths.windows_base_dir, 'netlogon'))
		self.paths.netlogon_templates_dir =  settings.get(
									'extensions.samba3.paths.netlogon_templates_dir',
									os.path.join(self.paths.netlogon_base_dir, 'templates'))
		self.paths.netlogon_custom_dir = settings.get(
										'extensions.samba3.paths.netlogon_custom_dir',
										os.path.join(self.paths.netlogon_base_dir, 'local'))

		# By Machine profiles
		self.paths.profiles_base_dir = settings.get(
										'extensions.samba3.paths.profiles_base_dir',
										os.path.join(self.paths.windows_base_dir, 'profiles'))
		self.paths.profiles_current_dir = settings.get(
										'extensions.samba3.paths.profiles_current_dir',
										os.path.join(self.paths.profiles_base_dir, 'current'))

		# Profiles templates.
		self.paths.profiles_templates_base_dir = settings.get(
										'extensions.samba3.paths.profiles_templates_base_dir',
										os.path.join(self.paths.windows_base_dir, 'profiles', 'templates'))
		self.paths.profiles_templates_users_dir = settings.get(
										'extensions.samba3.paths.profiles_templates_users_dir',
										os.path.join(self.paths.windows_base_dir, 'profiles', 'templates', 'Users'))
		self.paths.profiles_templates_groups_dir   = settings.get(
										'extensions.samba3.paths.profiles_templates_groups_dir',
										os.path.join(self.paths.windows_base_dir, 'profiles', 'templates', 'Groups'))
		self.paths.profiles_templates_machines_dir = settings.get(
										'extensions.samba3.paths.profiles_templates_machines_dir',
										os.path.join(self.paths.windows_base_dir, 'profiles', 'templates', 'Machines'))
	def __check_responsibles(self, batch=False, auto_answer=None):

		allresps = LMC.groups.by_name(self.groups.responsibles)

		for group in LMC.groups.select(filters.RESPONSIBLE):
			allresps.add_Users(group.members)
	def __check_paths(self, batch=False, auto_answer=None):

		acls_conf      = LMC.configuration.acls
		users_group    = LMC.configuration.users.group
		dirs_to_verify = []

		for smb_path, users_access in (
					(self.paths.windows_base_dir,			'--x'),
					(self.paths.netlogon_base_dir,			'r-x'),
					(self.paths.netlogon_templates_dir,		'r-x'),
					(self.paths.netlogon_custom_dir,		'r-x'),

					(self.paths.profiles_base_dir,					'--x'),
					(self.paths.profiles_current_dir,				'--x'),
					(self.paths.profiles_templates_base_dir,		None),
					(self.paths.profiles_templates_users_dir,		None),
					(self.paths.profiles_templates_groups_dir,		None),
					(self.paths.profiles_templates_machines_dir,	None),
				):

			dirs_to_verify.append(
				fsapi.FsapiObject(name=smb_path.replace('/', '_'),
						path=smb_path,
						uid=0, gid=acls_conf.gid,
						root_dir_acl=True,
						root_dir_perm = '{0},{1},{2},{3}{4}'.format(
							acls_conf.acl_base,
							# Licorn® admins have full access, always.
							acls_conf.acl_admins_rw,
							# Windows / Samba admins have full access
							# too, to modify and customize scripts.
							acls_conf.acl_admins_rw.replace(
									settings.defaults.admin_group,
									self.groups.admins),
							# Users have limited or no access, given the share.
							('g:%s:%s,' % (users_group, users_access))
								if users_access else '',
							# There is always an ACL mask.
							acls_conf.acl_mask)))

		# The user profile 'rwx' permissions will be eventually restricted
		# by Samba itself with the fake_perms module. But without fake_perms
		# (which is the default), users need write access to their profile
		# for Windows to load and update it.

		for user in LMC.users.select(filters.STD):
			dir_info      = user.check_rules._default.copy()
			dir_info.name = user.login + '_windows_profile'
			dir_info.path = os.path.join(self.paths.profiles_current_dir, user.login)

			dirs_to_verify.append(dir_info)

		try:
			for uyp in fsapi.check_full(dirs_to_verify, batch=batch,
										auto_answer=auto_answer):
				pass

		except (IOError, OSError), e:
			if e.errno == errno.EOPNOTSUPP:
				# this is the *first* "not supported" error encountered (on
				# config load of first licorn command). Try to make the error
				# message kind of explicit and clear, to let administrator know
				# he/she should mount the partition with 'acl' option.
				raise exceptions.LicornRuntimeError(_(u'Filesystem must be '
								u'mounted with "acl" option:\n\t%s') % e)
			else:
				raise

		except TypeError:
			# nothing to check (fsapi.... returned None and yielded nothing).
			pass

	def is_enabled(self):
		""" Always return the value of :attr:`self.available`, because we make
			no difference between beiing available and beiing enable in this very
			simple samba3 extension. """
		assert ltrace_func(TRACE_SAMBA3)
		return self.available
	@events.handler_method
	@only_if_enabled
	def user_post_add(self, *args, **kwargs):
		""" Update Samba user database, mkdir the profile directory and give
			it to the user. """

		assert ltrace_func(TRACE_SAMBA3)

		user     = kwargs.pop('user')
		password = kwargs.pop('password')

		# we don't deal with system accounts, they don't get a samba account for free.
		if user.is_system:
			return True

		all_ok = True

		try:
			out, err = process.execute([ self.paths.smbpasswd, '-a', user.login, '-s' ],
										'%s\n%s\n' % (password, password))
			if out:
				logging.info('%s: %s' % (stylize(ST_NAME, self.name), out[:-1]))

			if err:
				logging.warning('%s: %s' % (stylize(ST_NAME, self.name), err[:-1]))

		except:
			logging.exception(_(u'{0}: Exception in user_post_add({1})'),
									self.pretty_name, (ST_LOGIN, user.login))
			all_ok = False

		dir_info      = user.check_rules._default.copy()
		dir_info.name = user.login + '_windows_profile'
		dir_info.path = os.path.join(self.paths.profiles_current_dir, user.login)

		try:
			for uyp in fsapi.check_full([ dir_info ], batch=True):
				pass

			logging.notice(_(u'{0}: created {1}\'s Windows® profile (empty) '
									u'in {2}.').format(self.pretty_name,
										stylize(ST_LOGIN, user.login),
										stylize(ST_PATH, dir_info.path)))

		except TypeError:
			# nothing to check (fsapi.... returned None and yielded nothing).
			pass

		return all_ok
	@events.handler_method
	@only_if_enabled
	def user_post_change_password(self, *args, **kwargs):
		""" Update the user's password in samba3. """

		assert ltrace_func(TRACE_SAMBA3)

		user     = kwargs.pop('user')
		password = kwargs.pop('password')

		# we don't deal with system accounts, they don't get a samba account for free.
		if user.is_system:
			return True

		try:
			out, err = process.execute([ self.paths.smbpasswd, user.login, '-s' ],
										"%s\n%s\n" % (password, password))
			if out:
				logging.info('%s: %s' % (stylize(ST_NAME, self.name), out[:-1]))

			if err:
				logging.warning('%s: %s' % (stylize(ST_NAME, self.name), err[:-1]))

		except:
			logging.exception(_(u'{0}: Exception in user_post_change_password({1})'),
									self.pretty_name, (ST_LOGIN, user.login))
			return False

		return True
	@events.handler_method
	@only_if_enabled
	def user_pre_del(self, *args, **kwargs):
		""" Remove user from Samba user database and archive the user profile
			if non-empty. """

		assert ltrace_func(TRACE_SAMBA3)

		user = kwargs.pop('user')

		if user.is_system:
			return True

		all_ok = True

		try:
			out, err = process.execute([ self.paths.smbpasswd, '-x', user.login ])

			if out:
				logging.info('%s: %s' % (stylize(ST_NAME, self.name), out[:-1]))

			if err:
				logging.warning('%s: %s' % (stylize(ST_NAME, self.name), err[:-1]))

		except:
			logging.exception(_(u'{0}: Exception in user_pre_del({1})'),
								c, (ST_LOGIN, user.login))
			all_ok = False

		profile_dir = os.path.join(self.paths.profiles_current_dir, user.login)

		try:
			os.rmdir(profile_dir)

		except (OSError, IOError):
			# Directory was not empty ?
			try:
				fsapi.archive_directory(profile_dir,
								orig_name='%s_windows_profile' % (user.login))

			except (IOError, OSError), e:
				# Nah, it was probably something else
				if e.errno != errno.ENOENT:
					raise

		return all_ok
	@events.handler_method
	@only_if_enabled
	def group_post_add_user(self, *args, **kwargs):
		""" Event handler that will add the user to the ``responsibles`` global
			group if he was just added to any responsible group of the
			system. """

		assert ltrace_func(TRACE_SAMBA3)

		group = kwargs.pop('group')
		user  = kwargs.pop('user')

		# We don't deal with system accounts.
		# We are only interested in rsp-* groups.
		if user.is_system or not group.is_responsible:
			return True

		allresps = LMC.groups.by_name(self.groups.responsibles)

		try:
			allresps.add_Users([user])

		except:
			logging.exception(_(u'{0}: Error while adding user {1} to '
				u'group {2}'), self.pretty_name, user.login, allresps.name)

			return False

		return True
	@events.handler_method
	@only_if_enabled
	def group_post_del_user(self, *args, **kwargs):
		""" Event handler that will remove the user from the ``responsibles``
			global group if he is not a member of any responsible group
			anymore. """

		assert ltrace_func(TRACE_SAMBA3)

		group = kwargs.pop('group')
		user  = kwargs.pop('user')

		# We don't deal with system accounts.
		# We are only interested in rsp-* groups.
		if user.is_system or not group.is_responsible:
			return True

		# If the user is still responsible of any other group,
		# he should be maintained as 'responsibles' member.
		if [ g for g in user.groups if g.is_responsible ]:
			return True

		allresps = LMC.groups.by_name(self.groups.responsibles)

		try:
			allresps.del_Users([user])

		except:
			logging.exception(_(u'{0}: Error while removing user {1} from '
				u'group {2}'), self.pretty_name, user.login, allresps.name)

			return False

		return True
	@events.handler_method
	@only_if_enabled
	def user_logged_in(self, event, *args, **kwargs):

		assert ltrace_func(TRACE_SAMBA3)

		if event.kwargs.get('event_source', None) == 'samba3-netlogon':
			netlogon.netlogon(*event.args, **event.kwargs)

__all__ = ('Samba3Extension', )
