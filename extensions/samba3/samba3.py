# -*- coding: utf-8 -*-
"""
Licorn extensions: samba3 - http://docs.licorn.org/extensions/samba3.html

:copyright:
	* 2011-2012 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2

"""

import os

from licorn.foundations           import settings, logging, events, process
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

		self.data = LicornConfigObject()

		self.groups              = LicornConfigObject()

		# The administrator can change groups names if desired.
		# Defaults are 'machines' and 'responsibles'.
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

			logging.info(_(u'{0}: extension enabled.').format(self.pretty_name))
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

		group_descrs = {
			self.groups.machines    : _('Windows® workstations members of the MS domain'),
			self.groups.responsibles: _('Users responsible of at least one group'),
			}
		for group in self.groups:
			if not LMC.groups.exists(name=group):
				if batch or logging.ask_for_repair(_(u'{0}: group {1} must be '
									u'created. Do it?').format(
									self.pretty_name,
									stylize(ST_NAME, self.group)),
								auto_answer=auto_answer):

					LMC.groups.add_Group(name=group,
										description=group_descrs[group],
										system=True, batch=batch)
				else:
					raise exceptions.LicornCheckError(_(u'{0}: group {1} must '
										u'exist before continuing.').format(
											self.pretty_name,
											stylize(ST_NAME, group)))

		self.__check_responsibles(batch=batch, auto_answer=auto_answer)

		# TODO:
		#	- check smb.conf
		#	- check groups (conf contents and inclusions)
		#	- check users

		return True
	def __check_responsibles(self, batch=False, auto_answer=None):

		allresps = LMC.groups.by_name(self.groups.responsibles)

		for group in LMC.groups.select(filters.RESPONSIBLE):
			allresps.add_Users(group.members)

	def is_enabled(self):
		""" Always return the value of :attr:`self.available`, because we make
			no difference between beiing available and beiing enable in this very
			simple samba3 extension. """
		assert ltrace_func(TRACE_SAMBA3)
		return self.available
	@events.handler_method
	@only_if_enabled
	def user_post_add(self, *args, **kwargs):
		""" Create a caldavd user account and the associated calendar resource,
			then write the configuration and release the associated lock.
		"""

		assert ltrace_func(TRACE_SAMBA3)

		user     = kwargs.pop('user')
		password = kwargs.pop('password')

		# we don't deal with system accounts, they don't get a samba account for free.
		if user.is_system:
			return True

		try:
			try:
				out, err = process.execute([ self.paths.smbpasswd, '-a', user.login, '-s' ],
											'%s\n%s\n' % (password, password))
				if out:
					logging.info('%s: %s' % (stylize(ST_NAME, self.name), out[:-1]))

				if err:
					logging.warning('%s: %s' % (stylize(ST_NAME, self.name), err[:-1]))

			except (IOError, OSError), e:
				if e.errno not in (2, 32):
					raise e

			return True

		except:
			logging.exception(_(u'{0}: Exception in user_post_add({1})'),
									self.pretty_name, (ST_LOGIN, user.login))
			return False
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
			try:
				out, err = process.execute([ self.paths.smbpasswd, user.login, '-s' ],
											"%s\n%s\n" % (password, password))
				if out:
					logging.info('%s: %s' % (stylize(ST_NAME, self.name), out[:-1]))

				if err:
					logging.warning('%s: %s' % (stylize(ST_NAME, self.name), err[:-1]))

			except (IOError, OSError), e:
				if e.errno not in (2, 32):
					raise e

			return True
		except:
			logging.exception(_(u'{0}: Exception in user_post_change_password({1})'),
									self.pretty_name, (ST_LOGIN, user.login))
			return False
	@events.handler_method
	@only_if_enabled
	def user_pre_del(self, *args, **kwargs):
		""" delete a user and its resource in the caldavd accounts file, then
			reload the service. """

		assert ltrace_func(TRACE_SAMBA3)

		user = kwargs.pop('user')

		if user.is_system:
			return True

		try:

			try:
				out, err = process.execute([ self.paths.smbpasswd, '-x', user.login ])

				if out:
					logging.info('%s: %s' % (stylize(ST_NAME, self.name), out[:-1]))

				if err:
					logging.warning('%s: %s' % (stylize(ST_NAME, self.name), err[:-1]))

			except (IOError, OSError), e:
				if e.errno not in (2, 32):
					raise e

			return True

		except:
			logging.exception(_(u'{0}: Exception in user_pre_del({1})'),
								c, (ST_LOGIN, user.login))
			return False
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

		#samba_params = dict(key.split('_', 1)[1], value
		#						for key, value in kwargs.iteritems()
		#							if key.startswith('smb_')
		#								or key.startswith('samba_'))

		netlogon.netlogon(*event.args, **event.kwargs)

__all__ = ('Samba3Extension', )
