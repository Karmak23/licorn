# -*- coding: utf-8 -*-
"""
Licorn extensions: SimpleSharing - http://docs.licorn.org/extensions/

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/

:license: GNU GPL version 2

"""

import os

from licorn.foundations           import exceptions, logging, settings
from licorn.foundations           import json, cache, fsapi, events
from licorn.foundations.events    import LicornEvent
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.classes   import PicklableObject
from licorn.foundations.constants import services, svccmds, distros

from licorn.core                  import LMC
from licorn.core.users            import User
from licorn.extensions            import LicornExtension

class SimpleShare(PicklableObject):
	share_file  = '.lshare.conf'
	uploads_dir = 'uploads'

	def __init__(self, directory, coreobj):

		if not os.path.isdir(directory):
			raise exceptions.BadArgumentError(_(u'{0}: "{1}" must be a '
				u'directory!').format(self.__class__.__name__, directory))

		if not os.path.exists(self.config_file):
			raise exceptions.BadArgumentError(_(u'{0}: "{1}" must hold the '
				u'special {2} file!').format(self.__class__.__name__,
					directory, self.__class__.share_file))

		self.__path    = directory
		self.__coreobj = coreobj.weakref
		self.__name    = u'%s/%s' % (coreobj.name, os.path.basename(directory))

		for key, value in json.load(open(self.configuration_file)).iteritems():
			setattr(self, '__%s' % key, value)

		for attr_name in ('password', 'uri'):
			if not hasattr(self, attr_name):
				raise exceptions.CorruptFileError(
						filename=self.configuration_file,
						reason=_('it lacks the {0} directive').format(attr_name))

		self.compute_password = coreobj.backend.compute_password
	@property
	def coreobj(self):
		return self.__coreobj()
	@property
	def path(self):
		return self.__path
	id = path
	@property
	def name(self):
		return self.__name
	@property
	def configuration_file(self):
		return os.path.join(self.__path, self.__class__.share_file)
	@property
	def uploads_directory(self):
		return os.path.join(self.__path, self.__class__.uploads_dir)
	@property
	def accepts_uploads(self):
		return os.path.exists(self.uploads_directory) \
					and os.path.isdir(self.uploads_directory)
	@accepts_uploads.setter
	def accepts_uploads(self, accepts):

		with self.lock:
			if self.accepts_uploads == accepts:
				logging.info(_(u'{0}: simple share state unchanged.').format(
																self.pretty_name))
				return

			if accepts:
				os.makedirs(self.uploads_directory)

			else:
				# Archive the uploads/ directory only if non-empty.
				if os.listdir(self.uploads_directory) != []:
					fsapi.archive_directory(self.uploads_directory,
								orig_name='share_%s_uploads' % self.name)
	@property
	def password(self):
		return self.__password
	@password.setter
	def password(self, newpass):
		self.__password = self.compute_password(newpass)
		self.save_configuration()
	@property
	def uri(self):
		""" There is no setter for the URI attribute. Once assigned, the URI
			will not change. """
		return self.__uri
	def save_configuration(self):
		json.dump({
				'password' : self.__password,
				'uri'      : self.__uri,
			}, open(self.configuration_file))
	@cache.cached(cache.one_hour)
	def contents(self, *args, **kwargs):
		""" Return a dict({'directories', 'files', 'uploads'}) counting the
			subentries (recursively) of the current share. What the contents
			really are doesn't matter.

			The `uploads` item will be ``None`` if the current share doesn't
			accept, them; it will be ``0`` if it accepts them but there are
			none yet.

			.. note::
				* configuration and hidden files are not counted.
				* the result is cached for one hour, to avoid too much hits.
				  But as always the cache can be manually expired.
		"""

		dirs    = 0
		files   = 0
		uploads = 0

		uploads_dir = self.__class__.uploads_dir

		for subent, typ in fsapi.minifind(entry, mindepth=1, yield_type=True):

			if os.path.basename(subent)[0] == '.':
				# this avoids counting config file and hidden things.
				continue

			if uploads_dir in subent:
				uploads += 1
				continue

			if typ == stat.S_IFREG:
				files += 1

			else:
				dirs += 1

		return {
				'directories' : dirs,
				'files'       : files,
				'uploads'     : uploads if self.accepts_uploads else None
			}
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
	def check_shares(self, batch=False, auto_answer=None, full_display=True):

		if self.accepts_shares():
			with self.lock:
				if not os.path.exists(self.shares_directory):
					if batch or logging.ask_for_repair(_(u'User {0} home '
										u'lacks the {1} directory to hold '
										u'simple shares. Create it?').format(
											stylize(ST_LOGIN, self.login),
											stylize(ST_PATH,
													self.shares_directory))):

						os.makedirs(self.shares_directory)

						logging.info(_(u'Created directory {1} in user {0}\'s '
										u'home.').format(
											stylize(ST_LOGIN, self.login),
											stylize(ST_PATH,
													self.shares_directory)))
		else:
			if self.is_standard:
				logging.warning(_(u'User {0} does not accept simple '
									u'shares, check skipped.').format(
										stylize(ST_LOGIN, self.login)))
	def list_shares(self):

		with self.lock:
			try:
				for entry in os.listdir(self.shares_directory):
					try:
						yield SimpleShare(directory=os.path.join(
												self.shares_directory, entry),
											coreobj=self, loading=True)

					except CorruptFileError, e:
						# the share configuration file is imcomplete.
						logging.warning(e)

					except BadArgumentError, e:
						# probably and simply not a share directory.
						# don't bother with a polluting message.
						logging.warning2(e)

			except (OSError, IOError):
				logging.exception(_(u'{0}: error while listing shares, '
					u'launching a check in the background.'), self.pretty_name)
				workers.service_enqueue(priorities.LOW, self.check_shares, batch=True)
	def create_share(self, name, password=None, uploads=False):

		# create dir
		# create uploads
		# get URI
		pass
class SimplesharingExtension(ObjectSingleton, LicornExtension):
	""" Provide local users the ability to share files publicly via their
		:file:`${HOME}/Public/` directory, on the Web.

		.. versionadded:: 1.4
	"""
	module_depends = [ 'mylicorn' ]

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

		logging.info(_(u'{0}: extension always enabled unless manually '
							u'ignored in {1}.').format(self.pretty_name,
								stylize(ST_PATH, settings.main_config_file)))

		# Enhance the core user with simple_sharing extensions.
		User.__bases__ += (SimpleSharingUser, )

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
