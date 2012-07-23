# -*- coding: utf-8 -*-
"""
Licorn extensions: samba3 - http://docs.licorn.org/extensions/samba3.html

:copyright:
	* 2011-2012 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2

"""

import os

from licorn.foundations           import logging, process, events
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, MixedDictObject, LicornConfigObject
from licorn.foundations.constants import distros, services, svccmds, priorities

from licorn.core       import LMC
from licorn.extensions import LicornExtension

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
		self.paths.smbpasswd = '/usr/bin/smbpasswd'

		self.data = LicornConfigObject()

		if LMC.configuration.distro in (distros.UBUNTU,
										distros.LICORN,
										distros.DEBIAN):
			self.paths.service_defaults = '/etc/default/samba'
	def initialize(self):
		""" Set :attr:`self.available` to ``True`` if smbpasswd is
			found on the local system, else ``False``. """

		assert ltrace_func(TRACE_SAMBA3)

		if os.path.exists(self.paths.smbpasswd):
			logging.info(_(u'{0}: extension enabled.').format(
				stylize(ST_NAME, self.name)))

			self.available = True
		else:
			logging.info(_(u'{0}: extension disabled because {1} '
					'not found.').format(stylize(ST_NAME, self.name),
					stylize(ST_PATH, self.paths.smbpasswd)))
			self.available = False

		return self.available
	def check(self, batch=False, auto_answer=None):
		""" Currently, this method does nothing: this extension is so simple
			that we don't do anything needing a check in it. """
		assert ltrace_func(TRACE_SAMBA3)
		return True
	def is_enabled(self):
		""" Always return the value of :attr:`self.available`, because we make
			no difference between beiing available and beiing enable in this very
			simple samba3 extension. """
		assert ltrace_func(TRACE_SAMBA3)
		return self.available
	def users_load(self):
		""" This method does nothing for now: nothing particular is necessary. """
		assert ltrace_func(TRACE_SAMBA3)
		return True
	@events.handler_method
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
			logging.exception(_(u'{0}: Exception in user_post_add({1})'), (ST_NAME, self.name), (ST_LOGIN, user.login))
			return False
	@events.handler_method
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
			logging.exception(_(u'{0}: Exception in user_post_change_password({1})'), (ST_NAME, self.name), (ST_LOGIN, user.login))
			return False
	@events.handler_method
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
			logging.exception(_(u'{0}: Exception in user_pre_del({1})'), (ST_NAME, self.name), (ST_LOGIN, user.login))
			return False
	@events.handler_method
	def user_logged_in(self, *args, **kwargs):

		user = kwargs.pop('user')

		samba_params = dict(key.split('_', 1)[1], value
								for key, value in kwargs.iteritems()
									if key.startswith('smb_')
										or key.startswith('samba_'))

		print '>> SMB USER LOGGED IN:', user
