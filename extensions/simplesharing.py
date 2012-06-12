# -*- coding: utf-8 -*-
"""
Licorn extensions: SimpleSharing - http://docs.licorn.org/extensions/

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/

:license: GNU GPL version 2

"""

import os

from licorn.foundations           import exceptions, logging
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.constants import services, svccmds, distros

from licorn.core                  import LMC
from licorn.extensions            import LicornExtension

class SimpleSharingUser(object):
	""" A mix-in for :class:`~licorn.core.users.User` which add simple file
		sharing support. See http://dev.licorn.org/wiki/ExternalFileSharing
		for more details and specification. """

	# a comfort shortcut to the SimpleSharingExtension,
	# to avoid looking it via LMC everytime we need it.
	ssext = None

	def accepts_shares(self):
		""" System users never accept shares. Standard users accept them,
			unless they have created the :file:`~/.licorn/noshares.please`
			empty file. """

		if self.is_standard:
			return not os.path.exists(os.path.join(self.homeDirectory,
											LMC.configuration.users.config_dir,
											self.ssext.paths.disabler))
		return False
	@property
	def shares_directory(self):
		if self.is_standard:
			return os.path.join(user.homeDirectory,
								self.ssext.paths.user_share_dir)

		return None
	def check_shares(self, batch=False, auto_answer=None):

		if self.accepts_shares():
			if not os.path.exists(self.shares_directory):
				if batch or logging.ask_for_repair():
					os.makedirs(self.shares_directory)

		else:
			if self.is_standard:
				logging.warning(_(u'User {1} does not accept simple '
									u'shares, check skipped.').format(
										stylize(ST_LOGIN, self.login)))


class SimpleSharingExtension(ObjectSingleton, LicornExtension):
	""" Provide local users the ability to share files publicly via their
		:file:`${HOME}/Public/` directory, on the Web.

		.. versionadded:: 1.4
	"""
	def __init__(self):
		assert ltrace_func(TRACE_SIMPLESHARING)

		LicornExtension.__init__(self, name='simplesharing')

		# these paths are relative to ${HOME}; They will be localized.
		self.paths.user_share_dir  = 'Public'
		# NOT YET FOR GROUPS
		#self.paths.group_share_dir = 'Public'
		self.paths.disabler        = 'noshares.please'

		# a comfort shortcut
		SimpleSharingUser.ssext = self

		assert ltrace_func(TRACE_SIMPLESHARING, 1)
	def initialize(self):
		""" Return True if :program:`dbus-daemon` is installed on the system
			and if the configuration file exists where it should be.
		"""

		assert ltrace_func(TRACE_SIMPLESHARING)

		self.available = True

		return self.available
	def is_enabled(self):
		""" Dbus is always enabled if available. This method will **start**
			the dbus/gobject mainloop (not just instanciate it), in a
			separate thread (which will be collected later by the daemon).

			.. note:: Dbus is too important on a Linux system to be disabled
			if present. I've never seen a linux system where it is installed
			but not used (apart from maintenance mode, but Licorn® should not
			have been started in this case).
		"""

		logging.info(_(u'{0}: extension always enabled.').format(
										stylize(ST_NAME, self.name)))

		# Enhance the core user with simple_sharing extensions.
		User.__bases__ += SimpleSharingUser

		return True
	@events.handler_method
	def user_post_add(self, *args, **kwargs):
		""" Create a caldavd user account and the associated calendar resource,
			then write the configuration and release the associated lock.
		"""

		assert ltrace_func(TRACE_SIMPLESHARING)

		user = kwargs.pop('user')

		try:
				user.check_shares(batch=True)
				return True

		except Exception:
			logging.exception(_(u'{0}: Exception while setting up user {1}'),
								self.pretty_name, (ST_LOGIN, user.login))
			return False
