# -*- coding: utf-8 -*-
"""
Licorn extensions: SimpleSharing - http://docs.licorn.org/extensions/

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/

:license: GNU GPL version 2

"""

import os, stat, time, mimetypes, random, errno

from licorn.foundations           import exceptions, logging, settings, events
from licorn.foundations           import json, cache, fsapi, hlstr, pyutils
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.classes   import PicklableObject
from licorn.foundations.constants import services, svccmds, distros, priorities

from licorn.core                  import LMC
from licorn.core.users            import User
from licorn.core.classes          import only_if_enabled
from licorn.extensions            import LicornExtension

from licorn.extensions.mylicorn   import constants
from django.core.urlresolvers     import reverse as url_for

LicornEvent = events.LicornEvent

# Just to be sure it is done.
mimetypes.init()

class SimpleShare(PicklableObject):
	""" Object representing a share. It count contents, change password, shows
		external sharing URL, and the like.

		Minimal testsuite:

		mkdir -p ~/Public/test{1,_passwd,_uploads,_expire}
		mkdir ~/Public/test_uploads/uploads

		# put some files in the dirs you want, including uploads/

		get in

		u = LMC.users.by_login('olive')
		s = u.find_share('test_passwd')
		s.password = 'testp'

		s = u.find_share('test_uploads')
		s.password = 'testup'


		.. versionadded::
			* 1.4 as official feature (still incomplete)
			* 1.3.1 and later as experimental feature (incomplete)
	"""
	share_file  = '.lshare.conf'
	uploads_dir = 'uploads'

	def __init__(self, directory, coreobj):

		if not os.path.isdir(directory):
			raise exceptions.BadArgumentError(_(u'{0}: "{1}" must be a '
					u'directory!').format(self.__class__.__name__, directory))

		self.__path    = directory
		self.__coreobj = coreobj.weakref
		self.__name    = os.path.basename(directory)

		# We've got to create an ID which is somewhat unique, but non-moving
		# when re-instanciating the share over time. The ctime makes a good
		# canditate to help the name, which can collide if used alone.
		self.__shid = hlstr.validate_name(self.__name) + str(int(os.stat(directory).st_ctime))

		# a method used to encrypt passwords
		self.compute_password = coreobj.backend.compute_password

		self.__load_share_configuration()
	def __str__(self):
		return 'share %s' % (stylize(ST_UGID, self.__shid))
	def __load_share_configuration(self):

		# defaults parameters for a share.
		defaults = {'password': None, 'uri': None, 'expire': None}
		data = defaults.copy()

		if os.path.exists(self.share_configuration_file):
			try:
				data.update(json.load(open(self.share_configuration_file)))

			except:
				logging.warning(_(u'{0}: configuration file {1} seems '
								u'corrupt; removing it.').format(self,
							stylize(ST_PATH, self.share_configuration_file)))
				try:
					os.unlink(self.share_configuration_file)

				except:
					pass

		klass = self.__class__.__name__

		# only take in data the parameters we know, avoiding collisions.
		for key in defaults:
			setattr(self, '_%s__%s' % (klass, key), data[key])
	@property
	def shid(self):
		""" Obviously, ID is read-only. """
		return self.__shid
	@property
	def expired(self):
		return self.__expire != None and time.time() > self.__expire
	@property
	def valid(self):
		return not self.expired
	@property
	def expire(self):
		return self.__expire
	@expire.setter
	def expire(self, newexpire):
		""" None == "never"
			< 0   == 'already expired' => deactivate immediately.
			> 0   == delta, starting from now
		"""
		if expire != None:
			if expire > 0:
				expire += time.time()

			else:
				expire = -1

		self.__expire = newexpire
		self.__save_share_configuration(expire=newexpire)
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
	def public_url(self):
		""" Wow! Django's `url_for()` works like a charm from outside the WMI. """
		return url_for('wmi.shares.views.serve',
									args=(self.coreobj.name, self.name))
	@property
	def share_configuration_file(self):
		return os.path.join(self.__path, self.__class__.share_file)
	@property
	def uploads_directory(self):
		return os.path.join(self.__path, self.__class__.uploads_dir)
	@property
	def accepts_uploads(self):
		""" No password means no uploads. Security matters. No anonymous
			uploaded porn/warez in world-open web shares! """

		return self.__password != None and (
								os.path.isdir(self.uploads_directory)
								or not os.path.exists(self.uploads_directory))
	@accepts_uploads.setter
	def accepts_uploads(self, accepts):

		if accepts:
			if self.__password is None:
				raise exceptions.LicornRuntimeException(_(u'Please set a '
										u'password on the share first.'))

			try:
				os.makedirs(self.uploads_directory)

			except (OSError, IOError), e:
				if e.errno != errno.EEXIST:
					raise
		else:
			try:
				# Archive the uploads/ directory only if non-empty.
				if os.listdir(self.uploads_directory) != []:
					fsapi.archive_directory(self.uploads_directory,
							orig_name='share_%s_%s_uploads' % (
										self.coreobj.name, self.name))

			except (IOError, OSError), e:
				if e.errno != errno.ENOENT:
					raise

		LicornEvent('share_uploads_state_changed', share=self).emit()
	@property
	def password(self):
		return self.__password
	@password.setter
	def password(self, newpass):
		""" Sets the password. It can be ``None``, but only if the share
			doesn't accept uploads. Then the share is not protected, but this
			is a non-issue security-wise because shares are always read-only.

			It can be an issue if the user places sensitive data in the share,
			but then we can do nothing if the user is dumb or makes mistakes.
		"""
		self.__password = self.compute_password(newpass) if newpass else None

		self.__save_share_configuration(password=self.__password)

		if newpass is None:
			# remove the upload directory if no password.
			self.accepts_uploads = False
	@property
	def uri(self):
		""" Return the public short URI. If the share hasn't any,
			the method will return ``None``. """
		return self.__uri
	@uri.setter
	def uri(self, newuri):

		if not newuri.startswith('http') and newuri != None:
			raise exceptions.BadArgumentError(_('Bad URI {0}').format(newuri))

		self.__uri = newuri
		self.__save_share_configuration(uri=newuri)
	def __save_share_configuration(self, **kwargs):

		basedict = {}

		if os.path.exists(self.share_configuration_file):
			basedict.update(json.load(open(self.share_configuration_file, 'r')))

		basedict.update(kwargs)

		json.dump(basedict, open(self.share_configuration_file, 'w'))

		LicornEvent('share_configuration_changed', share=self, **kwargs).emit()
	@cache.cached(cache.one_hour)
	def contents(self, with_paths=False, *args, **kwargs):
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

		dirs    = []
		files   = []
		uploads = []

		uploads_dir = os.path.join(self.path, self.__class__.uploads_dir)

		for subent, typ in fsapi.minifind(self.path, mindepth=1, yield_type=True):
			if os.path.basename(subent)[0] == '.':
				# this avoids counting config file and hidden things.
				continue

			if typ == stat.S_IFREG:
				if fsapi.is_backup_file(subent):
					continue

				if subent.startswith(uploads_dir):
					uploads.append(subent)

				else:
					files.append(subent)

			else:
				dirs.append(subent)

		if with_paths:
			return {	'directories' : dirs,
						'files'       : files,
						'uploads'     : uploads
										if self.accepts_uploads else None }
		else:
			return {	'directories' : len(dirs),
						'files'       : len(files),
						'uploads'     : len(uploads)
										if self.accepts_uploads else None }
	def file_informations(self, filename):
		if not filename.startswith(self.path):
			raise exceptions.BadArgument(_(u'Not a file from that share.'))

		if not os.path.abspath(os.path.realpath(filename)).startswith(
										settings.defaults.home_base_path):
			raise exceptions.LicornSecurityError(_(u'Unsafe absolute path '
										u'for file "{0}"!').format(filename))

		# We follow symlinks
		fstat   = os.stat(filename)
		curtime = time.time()

		return {
			'size'     : fstat.st_size,
			# not yet ready.
			'mimetype' : mimetypes.guess_type(filename)[0] or _('Unknown'),
			'mtime'    : fstat.st_mtime - curtime,
			'ctime'    : fstat.st_ctime - curtime,
		}
	def check_password(self, pw_to_check):
		""" Returns ``True`` if ``pw_to_check`` (a string) is equal to the
			stored password, after having run the necessary ``crypt()``
			mechanisms because the current password is always stored
			encrypted. """
		return self.__password == self.compute_password(pw_to_check, self.__password)
	def __request_short_url(self):
		""" request a short URL (http://lsha.re/xxxxxxxx) from the central
			server.

			.. note:: Running this operation multiple time is not a problem
				because the central server will re-send us the URL for a
				given path as many times as we ask for it.

		"""

		m = LMC.extensions.mylicorn

		retrigger = False

		if m.connected:
			logging.progress(_(u'{0}: requesting short URL…').format(self))

			try:
				# This will automatically emit an event to update GUIs.
				result = m.service.shorten_url(self.public_url)

			except:
				logging.exception(_(u'{0}: short URL request failed, '
							u'deferring next try.'), self, m.pretty_name)
				retrigger = True

			else:
				if result['result'] > 0:
					self.uri = result['message']

					logging.info(_(u'{0}: short URL successfully set '
										u'to {1}.').format(self, self.uri))

				else:
					logging.warning(_(u'{0}: short URL request failed, '
							u'deferring next try (was: code={1}, '
							u'message={2}).').format(self,
								constants.shorten_url[result['result']],
														result['message']))
					retrigger = True

		else:
			logging.warning(_(u'{0}: {1} is not connected, deferring short '
					u'URL request.').format(self, m.pretty_name))
			retrigger = True

		if retrigger:
			# Random the job delay to avoid doing all next calls at once,
			# in case the problem was OVERQUOTA and we need a lot of URLs.
			workers.network_enqueue(priorities.LOW, self.__request_short_url,
								job_delay=float(random.randint(1800, 5400)))
	def check(self, batch=False, auto_answer=None, full_display=True):
		""" Check the share parameters. For the moment, it just makes sure
			the share has a short URL, else it will request one.

			.. warning:: If the MY Licorn® central server changes (eg. from
				development to production or vice-versa), the URLs will not
				be updated. This is not a bug, just worth noting. """

		if self.uri in (None, ''):
			workers.network_enqueue(priorities.LOW, self.__request_short_url)
class SimpleSharingUser(object):
	""" A mix-in for :class:`~licorn.core.users.User` which add simple file
		sharing support. See http://dev.licorn.org/wiki/ExternalFileSharing
		for more details and specification.

		.. versionadded::
			* 1.4 as official feature
			* 1.3.1 as experimental feature (incomplete)
	"""

	# a comfort shortcut to the SimpleSharingExtension,
	# to avoid looking it via LMC everytime we need it.
	ssext = None

	@property
	def accepts_shares(self):
		""" System users never accept shares. Standard users accept them,
			unless they have created the :file:`~/.licorn/noshares.please`
			empty file. """

		with self.lock:
			if self.is_standard:
				return not os.path.exists(self.shares_disabler)
			return False
	@accepts_shares.setter
	def accepts_shares(self, accepts):

		with self.lock:
			if not self.is_standard:
				raise exceptions.LicornRuntimeException(_(u'Someone tried to '
					u'switch simple shares on a non-standard user account!'))

			if self.accepts_shares == accepts:
				logging.info(_('{0}: shares status unchanged.').format(self.pretty_name))
				return

			if accepts:
				os.unlink(self.shares_disabler)

			else:
				fsapi.touch(self.shares_disabler)

		LicornEvent('shares_status_changed', user=self)

		logging.notice(_('{0}: simple shares status switched to {1}.').format(
			self.pretty_name, _(u'activated') if accepts else _(u'deactivated')))
	@property
	def shares_disabler(self):
		return os.path.join(self.homeDirectory,
							LMC.configuration.users.config_dir,
							self.ssext.paths.disabler)
	@property
	def shares_directory(self):
		if self.is_standard:
			return os.path.join(self.homeDirectory,
								self.ssext.paths.user_share_dir)

		return None
	def check_shares(self, batch=False, auto_answer=None, full_display=True):

		if self.accepts_shares:
			with self.lock:
				if os.path.exists(self.shares_directory):

					shares = self.list_shares()

					if shares:
						logging.progress(_(u'{0}: checking shares…').format(
															self.pretty_name))

						for share in shares:
							share.check(batch=batch, auto_answer=auto_answer,
										full_display=full_display)

						logging.progress(_(u'{0}: shares check finished.').format(
																self.pretty_name))

					else:
						logging.progress(_(u'{0}: no shares to check.').format(
															self.pretty_name))

				else:
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
		""" List a user shares, via a generator yielding every share found
			in the user shares directory. """

		shares = []

		with self.lock:
			try:
				for entry in os.listdir(self.shares_directory):
					try:
						shares.append(SimpleShare(directory=os.path.join(
												self.shares_directory, entry),
											coreobj=self))

					except exceptions.BadArgumentError, e:
						# probably and simply not a share directory.
						# don't bother with a polluting message.
						logging.warning2(e)

			except (OSError, IOError):
				if self.accepts_shares:
					logging.exception(_(u'{0}: error while listing shares, '
						u'launching a check in the background.'), self.pretty_name)
					workers.service_enqueue(priorities.LOW, self.check_shares, batch=True)

			return shares
	def find_share(self, share_name):
		for share in self.list_shares():
			if share.name == share_name:
				return share

		return None
	def create_share(self, name, password=None, uploads=False):

		# create dir
		# create uploads
		# get URI
		pass
class SimplesharingExtension(ObjectSingleton, LicornExtension):
	""" Provide local users the ability to share files publicly via their
		:file:`${HOME}/Public/` directory, on the Web. For more details see
		the `file sharing specification <http://dev.licorn.org/wiki/ExternalFileSharing>`_.

		.. versionadded::
			* 1.4 as official feature
			* 1.3.1 as experimental feature (incomplete)
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

		# Nothing to do in client mode. Anyway the WMI is not started on the
		# clients and this extension is mostly all about the WMI part, but
		# in any case we do not activate it on the clients, this will lower
		# memory footprint :-)
		self.server_only = True

		# a comfort shortcut
		SimpleSharingUser.ssext = self

		assert ltrace_func(TRACE_SIMPLESHARING, 1)
	def initialize(self):
		""" Return ``True`` inconditionnaly. This extension is always available
			unless manually ignored in the main configuration file. """

		assert ltrace_func(TRACE_SIMPLESHARING)

		self.available = True

		return self.available
	def is_enabled(self):
		""" Simple shares are always enabled if available. """

		if self.available:
			logging.info(_(u'{0}: extension always enabled unless manually '
								u'ignored in {1}.').format(self.pretty_name,
									stylize(ST_PATH, settings.main_config_file)))

			# Enhance the core user with simple_sharing extensions.
			User.__bases__ += (SimpleSharingUser, )

		self.__load_factory_settings()

		return self.available
	def __load_factory_settings(self):

		for setting_name, setting_value in (
					('settings.extensions.simplesharing.max_upload_size', 10485760),
				):
			try:
				pyutils.resolve_attr(setting_name, {'settings': settings})

			except AttributeError:
				settings.merge_settings({setting_name: setting_value})

	@events.handler_method
	@only_if_enabled
	def user_post_add(self, *args, **kwargs):
		""" On user creation, check its shares directory, this will create it
			if needed.

			.. note:: no need for a `user_post_del()` method, the share dir
				will be archived like any other home directory contents.
		"""

		assert ltrace_func(TRACE_SIMPLESHARING)

		user = kwargs.pop('user')

		try:
			user.check_shares(batch=True)
			return True

		except Exception:
			logging.exception(_(u'{0}: Exception while setting up shares for '
						u'user {1}'), self.pretty_name, (ST_LOGIN, user.login))
			return False
	@events.handler_method
	@only_if_enabled
	def extension_mylicorn_authenticated(self, *args, **kwargs):
		""" When the daemon has reached ``cruising`` state, we can start to
			check shares, request short URLs, etc. """

		logging.progress(_(u'{0}: checking all users\' shares…').format(self.pretty_name))

		for user in LMC.users:
			user.check_shares(batch=True)

		logging.progress(_(u'{0}: shares checks finished.').format(self.pretty_name))
