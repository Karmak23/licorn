# -*- coding: utf-8 -*-
"""
Licorn core: users - http://docs.licorn.org/core/users.html

:copyright:
	* 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	* partial 2010 Robin Lucbernet <robinlucbernet@gmail.com>
	* partial 2006 Régis Cobrun <reg53fr@yahoo.fr>

:license: GNU GPL version 2
"""

import os, sys, time, re, weakref, gc

from threading  import current_thread, Event
from operator   import attrgetter

from licorn.foundations           import logging, exceptions, hlstr
from licorn.foundations           import pyutils, fsapi, process
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, Enumeration, FsapiObject
from licorn.foundations.constants import filters, backend_actions

from licorn.core                import LMC
from licorn.core.groups         import Group
from licorn.core.classes        import CoreFSController, CoreStoredObject, CoreFSUnitObject
from licorn.daemon              import priorities, roles, InternalEvent

class User(CoreStoredObject, CoreFSUnitObject):
	""" The User unit-object. """

	_locked_colors = {
			None: ST_NAME,
			True: ST_BAD,
			False: ST_OK
		}

	# reverse mapping on logins and an alias to it
	by_login = {}
	by_name  = by_login

	#: cli width helpers to build beautiful CLI outputs.
	_cw_login = 10

	@staticmethod
	def _cli_invalidate_all():
		for user in User.by_login.itervalues():
			user()._cli_invalidate()
	@staticmethod
	def _cli_compute_label_width():

		_cw_login = 10

		for login in User.by_login:
			lenght = len(login) + 2

			if lenght > _cw_login:
				_cw_login = lenght

		if User._cw_login != _cw_login:
			User._cw_login = _cw_login
			User._cli_invalidate_all()

	@staticmethod
	def is_restricted_system_uid(uid):
		""" Return true if uid is system, but outside the range of Licorn®
			controlled UIDs."""
		return uid < LMC.configuration.users.system_uid_min \
			or uid > LMC.configuration.users.uid_max
	@staticmethod
	def is_unrestricted_system_uid(uid):
		""" Return true if uid is system, but inside the range of Licorn®
			controlled UIDs."""
		return uid >= LMC.configuration.users.system_uid_min \
			and uid <= LMC.configuration.users.system_uid_max
	@staticmethod
	def is_system_uid(uid):
		""" Return true if uid is system."""
		return uid < LMC.configuration.users.uid_min \
			or uid > LMC.configuration.users.uid_max
	@staticmethod
	def is_standard_uid(uid):
		""" Return true if gid is standard (not system). """
		return uid >= LMC.configuration.users.uid_min \
			and uid <= LMC.configuration.users.uid_max
	@staticmethod
	def make_login(lastname='', firstname='', inputlogin=''):
		""" Make a valid login from  user's firstname and lastname."""

		if inputlogin == '':
			login = hlstr.validate_name(str(firstname + '.' + lastname),
				maxlenght = LMC.configuration.users.login_maxlenght)
		else:
			# use provided login and verify it.
			login = hlstr.validate_name(str(inputlogin),
				maxlenght = LMC.configuration.users.login_maxlenght)

		if not hlstr.cregex['login'].match(login):
			raise exceptions.BadArgumentError(_(u'Cannot build a valid login '
				'(got "{0}", which does not verify {1}) with the '
				'firstname/lastname you provided ("{2}" and "{3}").').format(
					stylize(ST_LOGIN, login),
					stylize(ST_REGEX, hlstr.regex['login']),
					stylize(ST_NAME, firstname), stylize(ST_NAME, lastname)))

		return login

	def __init__(self, uidNumber, login, password=None, userPassword=None,
		gidNumber=None, gecos=None, homeDirectory=None, loginShell=None,
		shadowLastChange=None, shadowInactive=None, shadowWarning=None,
		shadowExpire=None, shadowMin=None, shadowMax=None, shadowFlag=None,
		initialyLocked=False, backend=None,
		# this one is  used only in creation mode, to speed up links between
		# Licorn® objects.
		primaryGroup=None):

		CoreStoredObject.__init__(self, controller=LMC.users, backend=backend)

		assert ltrace('objects', '| User.__init__(%s, %s)' % (uidNumber, login))

		# use private attributes for properties.
		self.__uidNumber        = uidNumber
		self.__login            = login
		self.__gecos            = gecos
		self.__loginShell       = loginShell

		# see properties for description, or shadow(5) for full details.
		self.__shadowLastChange = shadowLastChange or 0
		self.__shadowInactive   = shadowInactive or 0
		self.__shadowWarning    = shadowWarning or 7
		self.__shadowExpire     = shadowExpire or 0
		self.__shadowMin        = shadowMin or 0
		self.__shadowMax        = shadowMax or 99999
		self.__shadowFlag       = shadowFlag or ''

		if primaryGroup is None:
			self.__gidNumber = gidNumber
			# We are in loading phase (reading informations from the backends),
			# where only the GID number is known. The rest of the informations
			# will be linked later by the GroupsController, when it loads.
			self.__primaryGroup = None
		else:
			# We are in user creation mode. All controllers are up and running
			# thus we get a direct Group instance. get info from it and link
			# everything needed.

			self.__primaryGroup = primaryGroup.weakref
			self.__gidNumber    = primaryGroup.gidNumber
			primaryGroup.link_gidMember(self)

		if userPassword:
			# we are loading from backend, use the crypted password 'as-is' and
			# feed the private attribute (feeding the property would trigger a
			# recrypt, which is not what we need at all).
			self.__userPassword    = userPassword
			self.__locked          = self.__resolve_locked_state()
			self.__already_created = True
		else:
			# we are in creation mode. Set the password, but don't save it.
			# The save will be handled by the caller (typically UsersController).
			self.__userPassword = None
			self.__locked       = initialyLocked

			self.__already_created = False
			self.userPassword      = password
			self.__already_created = True

		# Reverse map the current object from its name (it is indexed on GID
		# in the Groups Controller), but only a weakref to be sure it will be
		# delete by the controller.
		User.by_login[login] = self.weakref

		# useful booleans, must exist before __resolve* methods are called.
		self.__is_system   = User.is_system_uid(uidNumber)
		self.__is_standard = not self.__is_system

		if self.__is_system:
			self.__is_system_restricted   = User.is_restricted_system_uid(uidNumber)
			self.__is_system_unrestricted = not self.__is_system_restricted
		else:
			self.__is_system_restricted   = False
			self.__is_system_unrestricted = False

		self.__homeDirectory = self._resolve_home_directory(homeDirectory)

		# Internal links to real Licorn® groups, to be able to find them
		# quickly when we need. It will be filled when GroupsController loads.
		self.__groups = []

		CoreFSUnitObject.__init__(self, '%s/%s' % (self.__homeDirectory,
									LMC.configuration.users.check_config_file),
						Enumeration(
								home=self.__homeDirectory,
								user_uid=self.__uidNumber,
								user_gid=self.__gidNumber))
		# CLI output pre-calculations.
		if len(login) + 2 > User._cw_login:
			User._cw_login = len(login) + 2
			User._cli_invalidate_all()
	def __str__(self):
		return '%s(%s‣%s) = {\n\t%s\n\t}\n' % (
			self.__class__,
			stylize(ST_UGID, self.__uidNumber),
			stylize(ST_NAME, self.__login),
			'\n\t'.join([ '%s: %s' % (attr_name, getattr(self, attr_name))
					for attr_name in dir(self) ])
			)
	def __repr__(self):
		return '%s(%s‣%s)' % (
			self.__class__,
			stylize(ST_UGID, self.__uidNumber),
			stylize(ST_NAME, self.__login))
	def __del__(self):

		assert ltrace('gc', '| User %s.__del__()' % self.__login)

		self.__primaryGroup().unlink_gidMember(self)

		del self.__primaryGroup

		# NOTE: we don't delete the user from the groups, the controller
		# already did that.

		del self.__groups

		# avoid deleting a reference to another user with the same login (which
		# will exist on backend reloads).
		if User.by_login[self.__login] == self.weakref:
			del User.by_login[self.__login]

		if len(self.__login) + 2 == User._cw_login:
			User._cli_compute_label_width()
	@property
	def uidNumber(self):
		""" Read-only UID attribute. """
		return self.__uidNumber
	@property
	def gidNumber(self):
		""" Read-only GID attribute. """
		return self.__gidNumber
	@gidNumber.setter
	def gidNumber(self, gidNumber):
		#
		# change the gidNumber
		# change the primaryGroup
		#
		# eventually apply the new profile (skel ? shell ?)
		#
		# check the user's home in the background, to give evything to u:g
		#
		print '>> please implement User.gidNumber.setter'
	@property
	def primaryGroup(self):
		""" The real Licorn® group of the current user, assigned at the end
			of GroupsController load, by the property setter. It will check
			that the gidNumber of the assigned group is equal to the current
			user read-only value gidNumber. """

		try:
			# convert the weakref into a real before returning it to caller.
			return self.__primaryGroup()
		except TypeError:
			return None
	@primaryGroup.setter
	def primaryGroup(self, group):

		if self.__gidNumber == group.gidNumber:
			self.__primaryGroup = group.weakref
			group.link_gidMember(self)
		else:
			raise exceptions.LicornRuntimeError(_(u'{0}: tried to set {1} '
				'as {2} primary group, whose GID is not the same '
				'({3} vs. {4}).').format('users', group.name, self.__login,
					group.gidNumber, self.__gidNumber))
	@property
	def profile(self):
		""" R/O: return the profile of the current user, via the primaryGroup
			attribute. The profile can be None, and it particularly useless
			for system accounts, because we don't apply profiles on them. """
		return self.__primaryGroup().profile
	@property
	def groups(self):
		# turn the weak ref into real objects before returning.
		return [group() for group in self.__groups]
	@property
	def login(self):
		""" the user login (indexed in a reverse mapping dict). There is no
			setter, because the login of a given user never changes. """
		return self.__login
	@property
	def gecos(self):
		""" Change the description of a group. """
		return self.__gecos
	@gecos.setter
	def gecos(self, gecos=None):
		""" Change the gecos of a user. """

		if gecos is None:
			raise exceptions.BadArgumentError(
				_(u'You must specify a gecos'))

		with self.lock:
			if not hlstr.cregex['description'].match(gecos):
				raise exceptions.BadArgumentError(_(u'Malformed GECOS field '
					'"{0}", must match /{1}/i.').format(
					stylize(ST_COMMENT, gecos),
					stylize(ST_REGEX, hlstr.regex['description'])))

			self.__gecos = gecos
			self.serialize()
			self._cli_invalidate()
			logging.notice(_(u'Changed user {0} gecos '
				'to "{1}".').format(stylize(ST_NAME, self.__login),
				stylize(ST_COMMENT, gecos)))
	@property
	def loginShell(self):
		""" the user's shell. """
		return self.__loginShell
	@loginShell.setter
	def loginShell(self, shell=None):
		""" Change the shell of a user. """

		if shell is None:
			raise exceptions.BadArgumentError(
				_(u'You must specify a shell'))

		if shell not in LMC.configuration.users.shells:
				raise exceptions.BadArgumentError(_(u'Invalid shell "{0}". '
					'Valid shells are {1}.').format(stylize(ST_BAD, shell),
					', '.join(stylize(ST_COMMENT, shell)
						for shell in LMC.configuration.users.shells)))

		with self.lock:
			self.__loginShell = shell
			self.serialize()

			logging.notice(_(u'Changed user {0} shell to {1}.').format(
				stylize(ST_NAME, self.__login), stylize(ST_COMMENT, shell)))
	@property
	def userPassword(self):
		""" return the user's crypted password. The :meth:`locked` property
			can update it. """

		return self.__userPassword
	@userPassword.setter
	def userPassword(self, password=None):
		""" Change the password of a user.

			This needs to not be a property setter, because we want a display
			argument, in case the password creation/change needs to be
			displayed, which is not compatible with a standard property
			behaviour.

			.. note:: TODO: we currently do not use the ``shadow*`` fields to
				enforce/disallow the password change. This will be subject to
				change in the near future.

			.. versionadded:: 1.2.5
				added the ability to change a password even if the account is
					locked: the new password is stored, but the account stays
					locked and the user cannot log in.
		"""

		display = False

		if password is None:
			display  = True
			password = hlstr.generate_password(
								LMC.configuration.users.min_passwd_size)
		elif password == '':
			logging.warning(_(u'Setting an empty password for user {0}. '
				'This is dangerous and totally insecure!').format(
					stylize(ST_LOGIN, self.__login)))

		with self.lock:
			if self.__already_created:
				L_event_run(InternalEvent('user_pre_change_password', self, password))

			prefix = '!' if self.__locked else ''

			if password == '':
				self.__userPassword = prefix
			else:
				self.__userPassword = '%s%s' % (prefix,
									self.backend.compute_password(password))

			# 3600*24 get us to the number of days since epoch.
			self.__shadowLastChange = int(time.time() / 86400)

			if self.__already_created:
				self.serialize()
				L_event_run(InternalEvent('user_post_change_password', self, password))

			if display:
				logging.notice(_(u'Set password for user {0} to {1}.').format(
					stylize(ST_NAME, self.__login),
					stylize(ST_IMPORTANT, password)),
					# don't display the clear-text password in the daemon's log.
					to_local=False)
			else:
				if self.__already_created:
					logging.notice(_(u'Changed password for user {0}.').format(
											stylize(ST_NAME, self.__login)))
			try:
				# samba stuff
				# TODO: forward output to listener…
				sys.stderr.write(process.execute(['smbpasswd', self.__login, '-s'],
					"%s\n%s\n" % (password, password))[1])
			except (IOError, OSError), e:
				if e.errno != 32:
					raise e
	@property
	def shadowLastChange(self):
		""" The last time the password was changed (in days, since the epoch).

			:attr:`shadowLastChange` has no setter because it is handled by
			:attr:`self.userPassword` setter, which updates it. It must not be
			touched outside of this process. """
		return self.__shadowLastChange
	@property
	def shadowInactive(self):
		""" When shadowMax has passed, the old password can still be accepted
			during :attr:`shadowInactive` days, but the user will be enforced
			to change it immediately after login.

			no setter yet, this attribute is currently ignored in Licorn®.
		"""
		return self.__shadowInactive
	@property
	def shadowWarning(self):
		""" Number of days before expiration, on when the user will be warned
			that he/she must change his/her password.

			no setter yet, this attribute is currently ignored in Licorn®.
		"""
		return self.__shadowWarning
	@property
	def shadowExpire(self):
		""" Expiration date for the user account (in days since the epoch).
			After this time, the account is totally disabled (until an
			administrator re-enables it).

			no setter yet, this attribute is currently ignored in Licorn®.
		"""
		return self.__shadowExpire
	@property
	def shadowMin(self):
		""" Minimum age of the password: the time the user will have to wait,
			after last change, before beiing able to change it again.

			no setter yet, this attribute is currently ignored in Licorn®.
		"""
		return self.__shadowMin
	@property
	def shadowMax(self):
		""" Maximum lifetime of the user's password after a new setting.

			no setter yet, this attribute is currently ignored in Licorn®.
		"""
		return self.__shadowMax
	@property
	def shadowFlag(self):
		""" Reserved field, not used at all for now (thus no setter). """
		return self.__shadowFlag
	@property
	def locked(self):
		""" A R/W boolean property indicating that the account is currently
			password-locked.

			Setting this property to ``True`` or ``False`` locks or unlocks
			the account, by prepending a '!' to the crypted password field
			and saving the account data in the backend.
		"""
		return self.__locked
	@locked.setter
	def locked(self, lock):
		"""(Un)Lock a user account. """

		with self.lock:
			if lock:
				if self.__locked:
					logging.info(_(u'Account {0} already locked.').format(
											stylize(ST_NAME, self.__login)))
				else:
					L_event_run(InternalEvent('user_pre_lock', self))

					self.__userPassword = '!' + self.__userPassword

					L_event_run(InternalEvent('user_post_lock', self))

					logging.notice(_(u'Locked user account {0}.').format(
											stylize(ST_LOGIN, self.__login)))

					self._cli_invalidate()
			else:
				if self.__locked:

					L_event_run(InternalEvent('user_pre_unlock', self))

					self.__userPassword = self.__userPassword[1:]

					L_event_run(InternalEvent('user_post_unlock', self))

					logging.notice(_(u'Unlocked user account {0}.').format(
											stylize(ST_LOGIN, self.__login)))

					self._cli_invalidate()
				else:
					logging.info(_(u'Account {0} already unlocked.').format(
											stylize(ST_NAME, self.__login)))

			self.__locked = lock
			self.serialize()
	@property
	def homeDirectory(self):
		""" Read-write attribute, the path to the home directory of a standard
			user (which holds shared content). Only standard users have home
			directories.

			Note that when setting it, the value given is totally ignored: the
			'set' mechanism only triggers the :meth:`_resolve_home_directory`
			method, which will construct and find the dire itself.
		"""
		return self.__homeDirectory
	@homeDirectory.setter
	def homeDirectory(self, ignored_value):
		self.__homeDirectory = self._resolve_home_directory()
	@property
	def is_system(self):
		""" Read-only boolean indicating if the current user is a system one. """
		return self.__is_system
	@property
	def is_system_restricted(self):
		""" Read-only boolean indicating if the current user is a restricted
			system one. Restricted accounts are not touched by Licorn® (they
			are usually managed by the distro maintainers). """
		return self.__is_system_restricted
	@property
	def is_system_unrestricted(self):
		""" Read-only boolean indicating if the current user account is an
			unrestricted system one. Unrestricted system accounts are handled
			by Licorn®. """
		return self.__is_system_unrestricted
	@property
	def is_standard(self):
		""" Read-only boolean, exact inverse of :attr:`is_system`. """
		return self.__is_standard

	@property
	def _wmi_protected(self):
		return self.__is_system

	# comfort properties aliases
	uid         = uidNumber
	gid         = gidNumber
	name        = login
	description = gecos
	password    = userPassword
	is_locked   = locked
	shell       = loginShell
	#group       = primaryGroup
	memberships = groups

	def _cli_invalidate(self):
		# invalidate the CLI view
		try:
			del self.__cg_precalc_full
		except:
			pass
		try:
			del self.__cg_precalc_small
		except:
			pass
	def serialize(self, backend_action=backend_actions.UPDATE):
		""" Save group data to originating backend. """

		with self.lock:
			assert ltrace('users', '| %s.serialize(%s → %s)' % (
											stylize(ST_NAME, self.__login),
											self.backend.name,
											backend_actions[backend_action]))

			self.backend.save_User(self, backend_action)
	def move_to_backend_to_be_rewritten(self, new_backend, force=False,
												internal_operation=False):
		""" Move a group from a backend to another, with extreme care. Any
			occurring exception will cancel the operation.

			Moving a standard group will begin by moving

			Moving a restricted system group will fail if argument ``force``
			is ``False``. This is not recommended anyway, groups <= 300 are
			handled by distros maintainer, you'd better not touch them.

		"""
		if new_backend.name not in LMC.backends.keys():
			raise exceptions.DoesntExistException(_(u'Backend %s does not '
				'exist or is not enabled.') % new_backend.name)

		old_backend = self.backend

		if old_backend.name == new_backend.name:
			logging.info(_(u'Skipped move of group {0}, '
				'already stored in backend {1}.').format(
					stylize(ST_NAME, self.name),
					stylize(ST_NAME, new_backend)))
			return True

		if self.is_restricted_system and not force:
			logging.warning(_(u'Skipped move of restricted system group {0} '
				'(please use {1} if you really want to do this, '
				'but it is strongly not recommended).').format(
					stylize(ST_NAME, self.name),
					stylize(ST_DEFAULT, '--force')))
			return

		if (self.is_responsible or self.is_guest) and not internal_operation:
			raise exceptions.BadArgumentError(_(u'Cannot move an '
				'associated system group without moving its standard '
				' group too. Please move the standard group instead, '
				'if this is what you meant.'))

		if self.is_standard:

			if not self.responsible_group.move_to_backend(new_backend,
													internal_operation=True):
				logging.warning(_(u'Skipped move of group {0} to backend {1} '
					'because move of associated responsible system group '
						'failed.').format(self.name, new_backend))
				return

			if not self.guest_group.move_to_backend(new_backend,
													internal_operation=True):

				# pray this works, else we're in big trouble, a shoot in a
				# foot and a golden shoe on the other.
				self.responsible_group.move_to_backend(old_backend,
													internal_operation=True)

				logging.warning(_(u'Skipped move of group {0} to backend {1} '
					'because move of associated system guest group '
						'failed.').format(self.name, new_backend))
				return

		try:
			self.backend = new_backend
			self.serialize(backend_actions.CREATE)

		except KeyboardInterrupt, e:
			logging.warning(_(u'Exception {0} happened while trying to '
				'move group {1} from {2} to {3}, aborting (group left '
				'unchanged).').format(e, group_name, old_backend, new_backend))
			print_exc()

			try:
				# try to restore old situation as much as possible.
				self.backend = old_backend

				# Delete the group in the new backend. It is still in the old,
				# we must avoid duplicates, because better priorized backends
				# overwrite others.
				new_backend.delete_Group(self)

				# restore associated groups in the same backend as the
				# standard group. They must stay together.
				self.responsible_group.move_to_backend(old_backend,
													internal_operation=True)
				self.guest_group.move_to_backend(old_backend,
													internal_operation=True)

			except Exception, e:
				logging.warning(_(u'Exception {0} happened while trying to '
					'restore a stable situation during group {1} move, we '
					'could be in big trouble.').format(e, self.name))
				print_exc()

			return False
		else:
			# the copy operation is successfull, make it a real move.
			old_backend.delete_Group(self.name)

			logging.notice(_(u'Moved group {0} from backend '
				'{1} to {2}.').format(stylize(ST_NAME, self.name),
					stylize(ST_NAME, old_backend),
					stylize(ST_NAME, new_backend)))
			return True
	def check_password(self, password):
		""" check if a given password is the same as the current user password.
			This needs computations to first encrypt the given password,
			because we only have the crypted form of it to our disposal.
		"""

		with self.lock:
			assert ltrace('users', 'comparing 2 crypted passwords:\n%s\n%s' % (
				self.__userPassword,
				self.backend.compute_password(password, self.__userPassword)))

			return self.__userPassword == self.backend.compute_password(
												password, self.__userPassword)
	def apply_skel(self, skel=None):
		""" Apply a skel on a user's home. """

		# FIXME: 1 reimplement this cleanly, without shell subcommands

		#import shutil
		# copytree automatically creates tmp_user_dict['homeDirectory']
		#shutil.copytree(skel_to_apply, tmp_user_dict['homeDirectory'])

		if skel is None or skel not in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError(_(u'Invalid skel "{0}". '
				'Valid skels are {1}.').format(stylize(ST_BAD, skel),
					', '.join(stylize(ST_COMMENT, skel)
						for skel in LMC.configuration.users.skels)))

		with self.lock:
			self._checking.set()

			# no force option with shutil.copytree(),
			# thus we use cp to force overwrite.
			process.syscmd('cp -r {0}/* {0}/.??* {1}'.format(
											skel, self.__homeDirectory))

			# set permission (because we are root)
			# FIXME: this should have already been covered by the inotifier.
			for fileordir in os.listdir(skel):
				try:
					# FIXME: do this with minifind(), os.chmod()… and map() it.
					process.syscmd("chown -R %s: %s/%s" % (
						self.__login, self.__homeDirectory, fileordir))

				except Exception, e:
					logging.warning(str(e))

			try:
				os.mkdir('%s/%s' % (self.__homeDirectory, LMC.configuration.users.config_dir))
			except (IOError, OSError), e:
				if e.errno != 17:
					# don't bork if already exists, else bork.
					raise

			self._checking.clear()
	def link_Group(self, group, sort=True):
		""" add a group in my double-link cache, and invalidate my CLI view.
			This is costy because we sort the group after the append(). """

		# avoid rare but eventual double user entries in /etc/group or another
		# backend, when edited outside of Licorn®.
		if group not in self.__groups:
			self.__groups.append(group.weakref)
			group.link_User(self)
			self._cli_invalidate()
	def unlink_Group(self, group):
		""" remove a group from my double-link cache, and invalidate my CLI view. """
		self.__groups.remove(group.weakref)
		self._cli_invalidate()
	def clear_Groups(self):
		""" Empty the user's groups weakrefs. Used when GroupsController reloads
			one or more backend. If we don't clear the groups first, the user
			gets groups referenced twice (or more). """

		self.__groups[:] = []
	def _build_standard_home(self):
		return '%s/%s/%s' % (LMC.configuration.defaults.home_base_path,
							LMC.configuration.users.names.plural,
							self.__login)
	def _build_system_home(self, directory):
		""" A system user has a home, which can be anywhere. """
		return directory
	def __resolve_locked_state(self):
		""" see if a given user accound is initially locked or not. """
		if self.__userPassword not in (None, '') \
			and self.__userPassword[0] == '!':
				return True

		return False

	def check(self, minimal=True, batch=False, auto_answer=None,
														full_display=True):
		"""Check current user account data consistency."""

		assert ltrace('users', '> %s.check()' % self.__login)

		with self.lock:
			# Refering to #322, we should avoid checking system users under uid
			# 100, they are all very special, have strange home dirs which must
			# NEVER been checked the licorn way, else this renders the system
			# totally unusable.
			# Generally speaking, to avoid future bugs with predefined system
			# accounts, we will avoid checking system users which we didn't
			# create (everything under uid 300 by default).
			# Sanely enough, we will do the same and avoid checking reserved
			# uids > 65000, like nobody. Just stick to adduser or licorn created
			# system uids.
			if self.is_system_unrestricted:
				return self.__check_system_user(batch=batch,
							auto_answer=auto_answer, full_display=full_display)

			elif self.is_standard:
				return self.__check_standard_user(minimal=minimal, batch=batch,
							auto_answer=auto_answer, full_display=full_display)
			else:
				# not system account between 300 < 999, not standard account.
				# the account is thus a special (reserved) system account, below
				# uid 300 or above uid 65000. Just don't do anything.
				logging.info(_(u'Skipped reserved system account %s '
					'(we do not check them at all).') %
						stylize(ST_NAME, self.__login))
				return True

	# aliases to CoreFSUnitObject methods
	__check_standard_user = CoreFSUnitObject._standard_check

	def __check_system_user(self, minimal=True, batch=False, auto_answer=None,
														full_display=True):
		""" Check the home dir and its contents, if it exists (this is not
			mandatory for a system account). If it does not exist, it will not
			be created. """
		logging.progress(_(u'Checking system account %s…') %
											stylize(ST_NAME, self.__login))

		if self._checking.is_set():
			logging.warning(_(u'account {0} already beiing ckecked, '
				'aborting.').format(stylize(ST_LOGIN, self.__login)))
			return

		with self.lock:

			self._checking.set()

			if os.path.exists(self.__homeDirectory):

				checked = set()

				for event in fsapi.check_dirs_and_contents_perms_and_acls_new(
						[ FsapiObject(name='%s_home' % self.__login,
									path = self.__homeDirectory,
									uid = self.__uidNumber,
									gid = self.__gidNumber,
									# these ones are already False by default.
									#root_dir_acl = False
									#content_acl = False
									root_dir_perm = 00700,
									files_perm = 00600,
									dirs_perm = 00700)
						],
						batch=batch, auto_answer=auto_answer,
						full_display=full_display):
					checked.add(event)

				del checked

			self._checking.clear()
	def _cli_get(self, long_output=False, no_colors=False):
		""" return a beautifull view for the current User object. """
		try:
			return self.__cg_precalc_full

		except AttributeError:
			# NOTE: 5 = len(str(65535)) == len(max_uid) == len(max_gid)
			label_width    = User._cw_login
			uid_label_rest = 5 - len(str(self.__uidNumber))
			gid_label_rest = (Group._cw_name + 5
								- len(self.__primaryGroup().name)
								- len(str(self.__gidNumber)))

			accountdata = [ '{login}: ✎{uid} ✐{pri_group} '
							'{backend}	{gecos}'.format(
								login=stylize(
									User._locked_colors[self.__locked],
									(self.__login).rjust(label_width)),
								#id_type=_(u'uid'),
								uid=stylize(ST_UGID, self.__uidNumber)
										+ ' ' * uid_label_rest,
								pri_group='%s%s' % (
										self.__primaryGroup()._cli_get_small(),
										' ' * gid_label_rest),
								backend=stylize(ST_BACKEND, self.backend.name),
								gecos=stylize(ST_COMMENT,
									self.__gecos) if self.__gecos != '' else '') ]

			if len(self.__groups) > 0:

				groups = [ g() for g in self.__groups ]

				accountdata.append('%s%s' % (
					# align the first group on the "uid" label,
					# thus the '+ 2' for ': ' compensation.
					' ' * (label_width + 2),
					', '.join(group._cli_get_small()
							for group in sorted(groups,
									key=attrgetter('sortName')))))
			else:
				accountdata.append(stylize(ST_EMPTY,
							' ' * (label_width + 1) + _(u'— no membership —')))

			self.__cg_precalc_full = '\n'.join(accountdata)
			return self.__cg_precalc_full
	def _cli_get_small(self):
		try:
			return self.__cg_precalc_small
		except AttributeError:
			self.__cg_precalc_small = '%s(%s)' % (
				stylize(User._locked_colors[self.__locked], self.__login),
				stylize(ST_UGID, self.__uidNumber))

			return self.__cg_precalc_small
	def _wmi_protected(self):
		return self.__is_system

	def to_XML(self):

		return '''		<user>
			<login>%s</login>
			<uidNumber>%d</uidNumber>
			<gidNumber>%d</gidNumber>
			<gecos>%s</gecos>
			<homeDirectory>%s</homeDirectory>
			<loginShell>%s</loginShell>
			<backend>%s</backend>
		</user>''' % (
						self.__login,
						self.__uidNumber,
						self.__gidNumber,
						self.__gecos,
						self.__homeDirectory,
						self.__loginShell,
						self.backend.name
					)

class UsersController(Singleton, CoreFSController):
	""" Handle global operations on unit User objects,
		from a system-wide perspective.
	"""
	init_ok = False
	load_ok = False

	#: used in RWI.
	@property
	def object_type_str(self):
		return _(u'user')
	@property
	def object_id_str(self):
		return _(u'UID')
	@property
	def sort_key(self):
		""" The key (attribute or property) used to sort
			User objects from RWI.select(). """
		return 'login'

	def __init__(self):
		""" Create the user accounts list from the underlying system. """

		assert ltrace('users', '> UsersController.__init__(%s)' %
			UsersController.init_ok)

		if UsersController.init_ok:
			return

		CoreFSController.__init__(self, 'users')

		UsersController.init_ok = True
		assert ltrace('users', '< UsersController.__init__(%s)' %
			UsersController.init_ok)
	def by_login(self, login):
		# Call the thing before returning it, because it's a weakref.
		return User.by_login[login]()
	@property
	def logins(self):
		return (login for login in User.by_login)
	def by_uid(self, uid):
		# we need to be sure we get an int(), because the 'uid' comes from RWI
		# and is often a string.
		return self[int(uid)]
	def load(self):
		if UsersController.load_ok:
			return

		assert ltrace('users', '| load()')
		self.reload()

		UsersController.load_ok = True
	def reload(self):
		""" Load (or reload) the data structures from the system data. """
		assert ltrace('users', '| reload()')

		with self.lock:
			for backend in self.backends:
				for uid, user in backend.load_Users():
					self[uid] = user

		# CoreFSController must be initialized *after* users and
		# groups are loaded, because it needs resolution to set
		# rules contents.
		CoreFSController.reload(self)
	def reload_backend(self, backend):
		""" Reload only one backend data (called from inotifier). """

		assert ltrace('users', '| reload_backend(%s)' % backend.name)

		loaded = []

		assert ltrace('locks', '| users.reload_backend enter %s' % self.lock)

		with self.lock:
			for uid, user in backend.load_Users():
				if uid in self:
					logging.warning2(_(u'{0}.reload: Overwritten uid {1}.').format(
						stylize(ST_NAME, self.name), uid))
				self[uid] = user
				loaded.append(uid)

			for uid, user in self.items():
				if user.backend.name == backend.name:
					if uid in loaded:
						loaded.remove(uid)

					else:
						logging.progress(_(u'{0}: removing disapeared user '
							'{1}.').format(stylize(ST_NAME, self.name),
								stylize(ST_LOGIN, user.login)))

						self.del_User(user, batch=True, force=True)

			# needed to reload the group cache.
			logging.notice('reloading %s controller too.' %
				stylize(ST_NAME, LMC.groups.name))

			LMC.groups.reload_backend(backend)

		assert ltrace('locks', '| users.reload_backend exit %s' % self.lock)
	def serialize(self, user=None):
		""" Write the user data in appropriate system files."""

		assert ltrace('users', '| serialize()')

		with self.lock:
			if user:
				user.serialize()

			else:
				for backend in self.backends:
					backend.save_Users(self)
	def select(self, filter_string):
		""" Filter user accounts on different criteria.
		Criteria are:
			- 'system users': show only «system» users (root, bin, daemon,
				apache…), not normal user account.
			- 'normal users': keep only «normal» users, which includes Licorn
				administrators
			- more to come…
		"""

		with self.lock:
			if filters.ALL == filter_string:
				filtered_users = self.values()

			elif filters.NONE & filter_string:
				filtered_users = []

			elif type(filter_string) == type([]):
				filtered_users = filter_string

			elif type(filter_string) == type(1):
				filtered_users = []

				if filter_string & filters.NOT_SYSTEM \
						or filter_string & filters.STANDARD:
					filtered_users.extend(user for user in self if user.is_standard)

				if filters.SYSTEM == filter_string:
					filtered_users.extend(user for user in self if user.is_system)

				if filters.SYSTEM_RESTRICTED & filter_string:
					filtered_users.extend(user for user in self if user.is_system_restricted)

				if filters.SYSTEM_UNRESTRICTED & filter_string:
					filtered_users.extend(user for user in self if user.is_system_unrestricted)
			else:
					uid_re = re.compile("^uid=(?P<uid>\d+)")
					uid = uid_re.match(filter_string)
					if uid is not None:
						if int(uid.group('uid')) in self.iterkeys():
							filtered_users.append(self[uid])
						else:
							raise exceptions.DoesntExistException(
								'UID %d does not exist.' % uid)
			return filtered_users
	def __validate_home_dir(self, home, login, system, force):
		""" Do some basic but sane tests on the home dir provided. """

		if system:
			if home:
				if os.path.exists(home) and not force:
					raise exceptions.BadArgumentError(_(u'Specified directory '
						'{0} for system user {1} already exists. If you '
						'really want to use it, please use the --force '
						'argument.').format(stylize(ST_PATH, home),
						stylize(ST_NAME,login)))

				if not home.startswith(
					LMC.configuration.defaults.home_base_path) \
					and not home.startswith('/var') \
					or home.startswith('%s/%s' % (
						LMC.configuration.defaults.home_base_path,
						LMC.configuration.groups.names.plural)) \
					or home.find('/tmp') != -1:

					raise exceptions.BadArgumentError(_(u'Specified home '
						'directory {0} for system user {1} is outside {2} '
						'and /var, or inside {3}/{4} or a temporary '
						'directory (/var/tmp, /tmp). This is unsupported, '
						'Aborting.').format(
						stylize(ST_PATH, home),
						stylize(ST_NAME,login),
						LMC.configuration.defaults.home_base_path,
						LMC.configuration.defaults.home_base_path,
						LMC.configuration.groups.names.plural))

				if home in (user.homeDirectory for user in self):
					raise exceptions.BadArgumentError(_(u'Specified home '
						'directory {0} for system user {1} is already owned '
						'by another user. Please choose another one.').format(
						stylize(ST_PATH, home),
						stylize(ST_NAME, login)))

				return home
		else: # not system
			if home:
				logging.warning(_(u'Specifying an alternative home directory '
					'is not allowed for standard users. Using standard home '
					'path {0} instead.').format(
						stylize(ST_PATH, '%s/%s' % (
							LMC.configuration.users.base_path, login))))

		return "%s/%s" % (LMC.configuration.users.base_path, login)
	def __validate_basic_fields(self, login, firstname, lastname, gecos, shell,
		skel):
		# to create a user account, we must have a login. autogenerate it
		# if not given as argument.
		if login is None:
			if (firstname is None or lastname is None) and gecos is None:
				raise exceptions.BadArgumentError(_(u'You must specify a '
					'login, a firstname *and* lastname couple, or a GECOS '
					'(login will be built from them).'))
			else:
				login_autogenerated = True
				if gecos is None:
					login = User.make_login(lastname, firstname)
				else:
					login = hlstr.validate_name(gecos,
						maxlenght=LMC.configuration.users.login_maxlenght)
		else:
			login_autogenerated = False

		if gecos is None:
			gecos_autogenerated = True

			if firstname is None or lastname is None:
				gecos = _(u'User account %s') % login
			else:
				gecos = '%s %s' % (firstname, lastname.upper())
		else:
			gecos_autogenerated = False

			if firstname and lastname:
				raise exceptions.BadArgumentError(_(u'You must specify a '
					'lastname and a firstname *or* a GECOS. If you specify '
					'the GECOS, do not specify firstname/lastname.'))
			# else: all is OK, we have a login and a GECOS field

		# then verify that the login match all requisites and all constraints.
		# it can be wrong, even if autogenerated with internal tools, in rare
		# cases, so check it without conditions.
		if not hlstr.cregex['login'].match(login):
			if login_autogenerated:
				raise exceptions.LicornRuntimeError(
					"Can't build a valid login (%s) with the " \
					"firstname/lastname (%s/%s) you provided." % (
					login, firstname, lastname))
			else:
				raise exceptions.BadArgumentError(_(u'Malformed login "{0}", '
					'must match /{1}/.').format(stylize(ST_COMMENT,login),
						stylize(ST_REGEX, hlstr.regex['login'])))

		if not login_autogenerated and \
			len(login) > LMC.configuration.users.login_maxlenght:
			raise exceptions.LicornRuntimeError(
				"Login %s too long (currently %d characters," \
				" but must be shorter or equal than %d)." % (
					login, len(login),
					LMC.configuration.users.login_maxlenght) )

		# then, verify that other arguments match the system constraints.
		if not hlstr.cregex['description'].match(gecos):
			if gecos_autogenerated:
				raise exceptions.LicornRuntimeError(
					"Can't build a valid GECOS (%s) with the" \
					" firstname/lastname (%s/%s) or login you provided." % (
						gecos, firstname, lastname) )
			else:
				raise exceptions.BadArgumentError(_(u'Malformed GECOS field '
					'"{0}", must match /{1}/i.').format(
					stylize(ST_COMMENT, gecos),
					stylize(ST_REGEX, hlstr.regex['description'])))

		if shell is not None and shell not in LMC.configuration.users.shells:
			raise exceptions.BadArgumentError(_(u'Invalid shell "{0}". '
				'Valid shells are: {1}.').format(stylize(ST_BAD, shell),
					', '.join(stylize(ST_COMMENT, shell)
						for shell in LMC.configuration.users.shells)))

		if skel is not None \
			and skel not in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError(_(u'Invalid skel "{0}". '
				'Valid skels are: {1}.').format(stylize(ST_BAD, skel),
					', '.join(stylize(ST_COMMENT, skel)
						for skel in LMC.configuration.users.skels)))

		return login, firstname, lastname, gecos, shell, skel
	def __validate_important_fields(self, desired_uid, login, system, force):
		# if an UID is given, it must be free. The lock ensure is will *stay*
		# free.
		# FIXME: this is not really exact, if someone adds / removes a user from
		# outside Licorn®. we should lock the backend too, before looking at the
		# UIDs.
		if desired_uid in self.iterkeys():
			raise exceptions.AlreadyExistsError(_(u'UID {0} is already '
				'taken by user {1}. Please choose another one.').format(
					stylize(ST_UGID, desired_uid),
					stylize(ST_NAME, self[desired_uid].login)))

		# Verify prior existence of user account
		if login in self.logins:
			if ( system and self.by_login(login).is_system ) \
				or ( not system and self.by_login(login).is_standard ):
				raise exceptions.AlreadyExistsException(_(u'User account '
					'{0} already exists!').format(login))
			else:
				raise exceptions.AlreadyExistsError(_(u'A user account {0} '
					'already exists but has not the same type. Please '
					'choose another login for your user.').format(
						stylize(ST_NAME, login)))

		# Due to a bug of adduser/deluser perl script, we must check
		# that there is no group which the same name than the login.
		# There should not already be a system group with the same name
		# (we are just going to create it…), but it could be a system
		# inconsistency, so go on to recover from it.
		#
		# {add,del}user logic is:
		#	- a system account must always have a system group as primary
		#		group, else if will be «nogroup» if not specified.
		#   - when deleting a system account, a corresponding system group
		#		will be deleted if existing.
		#	- no restrictions for a standard account
		#
		# the bug is that in case 2, deluser will delete the group even
		# if this is a standard group (which is bad). This could happen
		# with::
		#	addgroup toto
		#	adduser --system toto --ingroup root
		#	deluser --system toto
		#	(group toto is deleted but it shouldn't be! And it is deleted
		#	without *any* message !!)
		if login in LMC.groups.names and not force:
			raise exceptions.UpstreamBugException(_(u'A group named {0} '
				'exists on the system. This could eventually conflict in '
				'Debian/Ubuntu system tools. Please choose another '
				'login, or use the --force argument if you really want '
				'to add this user on the system.').format(
					stylize(ST_LOGIN, login)))
	def _generate_uid(self, login, desired_uid, system):
		# generate an UID if None given, else verify it matches constraints.
		if desired_uid is None:
			if system:
				uid = pyutils.next_free(self.keys(),
					LMC.configuration.users.system_uid_min,
					LMC.configuration.users.system_uid_max)
			else:
				uid = pyutils.next_free(self.keys(),
					LMC.configuration.users.uid_min,
					LMC.configuration.users.uid_max)

			logging.progress(_(u'Autogenerated UID for user {0}: {1}.').format(
				stylize(ST_LOGIN, login),
				stylize(ST_SECRET, uid)))
		else:
			if (system and User.is_system_uid(desired_uid)) \
				or (not system and User.is_standard_uid(desired_uid)):
					uid = desired_uid
			else:
				raise exceptions.BadArgumentError(_(u'UID out of range for '
					'the kind of user account you specified. System UIDs '
					'must be between {0} and {1}, standard UIDs must be '
					'between {2} and {3}.').format(
						LMC.configuration.users.system_uid_min,
						LMC.configuration.users.system_uid_max,
						LMC.configuration.users.uid_min,
						LMC.configuration.users.uid_max))
		return uid
	def add_User(self, login=None, system=False, password=None, gecos=None,
		desired_uid=None, primary_group=None, profile=None, backend=None,
		skel=None, shell=None, home=None, lastname=None, firstname=None,
		in_groups=None, batch=False, force=False):
		"""Add a user and return his/her (uid, login, pass)."""

		assert ltrace('users', '''> add_User(login=%s, system=%s, pass=%s, '''
			'''uid=%s, gid=%s, profile=%s, skel=%s, gecos=%s, first=%s, '''
			'''last=%s, home=%s, shell=%s)''' % (login, system, password,
			desired_uid, repr(primary_group), repr(profile),
			skel, gecos, firstname, lastname, home, shell))

		assert type(in_groups) == type([])

		login, firstname, lastname, gecos, shell, skel = \
			self.__validate_basic_fields(login, firstname, lastname,
				gecos, shell, skel)

		# Everything seems basically OK, we can now lock and go on.
		with self.lock:
			self.__validate_important_fields(desired_uid, login, system, force)

			uid = self._generate_uid(login, desired_uid, system)

			L_event_run(InternalEvent('user_pre_add', uid=uid, login=login,
								system=system, password=password))

			groups_to_add_user_to = in_groups

			skel_to_apply = LMC.configuration.users.default_skel or None
			homeDirectory = self.__validate_home_dir(home, login, system, force)

			if profile is not None:
				loginShell    = profile.profileShell
				skel_to_apply = profile.profileSkel
				primary_group = profile.group

				groups_to_add_user_to.extend(LMC.groups.by_name(g)
												for g in profile.memberGid)
			else:
				logging.warning2('>> FIXME: UsersController.add_User: skel for '
					'standard group ? system group ?', to_listener=False, to_local=True)

				loginShell = LMC.configuration.users.default_shell

				if primary_group and primary_group.is_standard:
					skel_to_apply = primary_group.groupSkel

				else:
					# get the primary group real object anyway, we need to
					# link the user to it.
					primary_group = LMC.groups.by_gid(
									LMC.configuration.users.default_gid)

			# overwrite default data with command-line specified ones.
			if shell is not None:
				loginShell = shell

			if skel is not None:
				skel_to_apply = skel

			# create home directory and apply skel
			if os.path.exists(homeDirectory):
				logging.info(_(u'Home directory {0} already exists.').format(
											stylize(ST_PATH, homeDirectory)))
			else:
				os.makedirs(homeDirectory)
				logging.info(_(u'Created home directory {0}.').format(
											stylize(ST_PATH, homeDirectory)))

			# Autogenerate password if not given.
			# NOTE: this must be done *HERE*, and not in the User class,
			# else we can't forward the cleartext password to extensions,
			# and can't return it to caller (massive imports need to know it).
			if password is None:
				# TODO: call cracklib2 to verify passwd strenght.
				password = hlstr.generate_password(
				LMC.configuration.users.min_passwd_size)
				gen_pass = True
			else:
				gen_pass = False

			user = self[uid] = User(
								uidNumber=uid,
								login=login,
								gecos=gecos,
								primaryGroup=primary_group,
								password=password,
								loginShell=loginShell,
								homeDirectory=homeDirectory,
								backend=self._prefered_backend
									if backend is None else backend,
								initialyLocked=False)

			# we can't delay the serialization, because this would break Samba
			# (and possibly others) stuff, and the add_user_in_group stuff too:
			# they need the data to be already written to disk to operate.
			#
			# thus, DO NOT UNCOMMENT -- if not batch:
			user.serialize(backend_actions.CREATE)

			L_event_run(InternalEvent('user_post_add', user, password))

			user.apply_skel(skel_to_apply)

			# this will implicitely load the check_rules for the user.
			user.check(minimal=True, batch=True)

			if user.is_standard:
				user._inotifier_add_watch(self.licornd)

			# Samba: add Samba user account.
			# TODO: put this into a module.
			# TODO: find a way to get the output back to the listener…
			try:
				sys.stderr.write(process.execute(
					['smbpasswd', '-a', user.login, '-s'],
					'%s\n%s\n' % (password, password))[1])
			except (IOError, OSError), e:
				if e.errno not in (2, 32):
					raise e

		# we needed to delay this display until *after* account creation, to
		# know the login (it could have been autogenerated by the User class).
		if gen_pass:
			logging.notice(_(u'Autogenerated password for user {0} '
					'(uid={1}): {2}.').format(
						stylize(ST_LOGIN, user.login),
						stylize(ST_UGID, user.uidNumber),
						stylize(ST_SECRET, password)),
					to_local=False)


		logging.notice(_(u'Created {accttype} user {login} (uid={uid}).').format(
			accttype=_(u'system') if system else _(u'standard'),
			login=stylize(ST_LOGIN, login),
			uid=stylize(ST_UGID, uid)))

		for group in groups_to_add_user_to:
			group.add_Users([ user ])

		# FIXME: Set quota
		if profile is not None:
			pass
			#os.popen2( [ 'quotatool', '-u', str(uid), '-b',
			#	LMC.configuration.defaults.quota_device, '-l' '%sMB'
			#	% LMC.profiles[profile]['quota'] ] )[1].read()
			#logging.warning("quotas are disabled !")
			# XXX: Quotatool can return 2 without apparent reason
			# (the quota is etablished) !

		assert ltrace('users', '< add_User(%r)' % user)

		# We *need* to return the password, in case it was autogenerated.
		# This is the only way we can know it, in massive imports.
		return user, password
	def del_User(self, user, no_archive=False, force=False, batch=False):
		""" Delete a user. """

		assert ltrace('users', "| del_User(%r)" % user)

		if user.is_system_restricted and not force:
			raise exceptions.BadArgumentError(_(u'Cannot delete '
				'restricted system account %s without the --force '
				'argument, this is too dangerous.') %
					stylize(ST_NAME, user.login))

		# Delete user from his groups
		# '[:]' to fix #14, see
		# http://docs.python.org/tut/node6.html#SECTION006200000000000000000
		for group in user.groups[:]:
			group.del_Users([ user ], batch=True)

		L_event_run(InternalEvent('user_pre_del', user))

		try:
			# samba stuff
			# TODO: forward output to listener…
			sys.stderr.write(process.execute(['smbpasswd', '-x', user.login])[1])
		except (IOError, OSError), e:
			if e.errno not in (2, 32):
				raise e

		# keep the homedir path, to backup it if requested.
		homedir = user.homeDirectory
		# keep infos to use them in deletion notice
		login   = user.login
		uid     = user.uidNumber

		with self.lock:
			if uid in self:
				del self[uid]
			else:
				logging.warning2(_(u'{0}: account {1} already not referenced in '
					'controller!').format(stylize(ST_NAME, self.name),
						stylize(ST_LOGIN, login)))

			if user.is_standard:
				user._inotifier_del_watch(self.licornd)

			# NOTE: this must be done *after* having deleted the data from self,
			# else mono-maniac backends (like shadow) don't see the change and
			# save everything, including the user we want to delete.
			user.backend.delete_User(user)

			assert ltrace('gc', '  user ref count before del: %d %s' % (
					sys.getrefcount(user), gc.get_referrers(user)))

			del user

		# checkpoint, needed for multi-delete (users-groups-profile) operation,
		# to avoid collecting the deleted users at the end of the run, making
		# throw false-negative operation about non-existing groups.
		gc.collect()

		logging.notice(_(u'Deleted user account {0}.').format(
			stylize(ST_LOGIN, login)))

		L_event_run(InternalEvent('user_post_del', uid=uid, login=login,
														no_archive=no_archive))

		# user is now wiped out from the system.
		# Last thing to do is to delete or archive the HOME dir.
		if no_archive:
			L_service_enqueue(priorities.LOW, fsapi.remove_directory, homedir)
		else:
			L_service_enqueue(priorities.LOW, fsapi.archive_directory, homedir, login)
	def dump(self):
		""" Dump the internal data structures (debug and development use). """

		with self.lock:

			assert ltrace('users', '| dump()')

			uids = self.users.keys()
			uids.sort()

			logins = self.login_cache.keys()
			logins.sort()

			def dump_user(uid):
				return 'users[%s] (%s) = %s ' % (
					stylize(ST_UGID, uid),
					stylize(ST_NAME, self.users[uid]['login']),
					str(self.users[uid]).replace(
					', ', '\n\t').replace('{', '{\n\t').replace('}','\n}'))

			data = '%s:\n%s\n%s:\n%s\n' % (
				stylize(ST_IMPORTANT, 'core.users'),
				'\n'.join(map(dump_user, uids)),
				stylize(ST_IMPORTANT, 'core.login_cache'),
				'\n'.join(['\t%s: %s' % (key, self.login_cache[key]) \
					for key in logins ])
				)

			return data
	def ExportCSV(self, selected=None, long_output=False):
		""" Export the user accounts list to CSV. """

		with self.lock:
			if selected is None:
				uids = self.users.keys()
			else:
				uids = selected
			uids.sort()

			assert ltrace('users', '| ExportCSV(%s)' % uids)

			def build_csv_output_licorn(uid):
				return ';'.join(
					[
						self.users[uid]['gecos'],
						self.users[uid]['login'],
						str(self.users[uid]['gidNumber']),
						','.join(self.users[uid]['groups']),
						self.users[uid]['backend']
					]
					)

			data = '\n'.join(map(build_csv_output_licorn, uids)) +'\n'

			return data
	def to_XML(self, selected=None, long_output=False):
		""" Export the user accounts list to XML. """

		with self.lock:
			if selected is None:
				users = self
			else:
				users = selected

			assert ltrace('users', '| to_XML(%r)' % users)

			return ('<?xml version="1.0" encoding="UTF-8"?>\n'
					'<users-list>\n'
					'%s\n'
					'</users-list>\n') % '\n'.join(
						user.to_XML() for user in users)
	def chk_Users(self, users_to_check=[], minimal=True, batch=False,
		auto_answer=None):
		"""Check user accounts and account data consistency."""

		assert ltrace('users', '> chk_Users(%r)' % users_to_check)

		# FIXME: should we crash if the user's home we are checking is removed
		# during the check ? what happens ?

		# dependancy: base dirs must be OK before checking users's homes.
		LMC.configuration.check_base_dirs(minimal=minimal,
			batch=batch, auto_answer=auto_answer)

		def my_check_user(user, minimal=minimal,
					batch=batch, auto_answer=auto_answer):
			return user.check(minimal, batch, auto_answer)

		all_went_ok=reduce(pyutils.keep_false, map(my_check_user, users_to_check))

		if all_went_ok is False:
			# NOTICE: don't test just "if reduce():", the result could be None
			# and everything is OK when None…
			raise exceptions.LicornCheckError(_(u'Some user(s) check(s) did '
				'not pass, or were not corrected.'))

		assert ltrace('users', '< chk_Users(%s)' % all_went_ok)
		return all_went_ok
	def guess_one(self, value):
		""" Try to guess everything of a user from a
			single and unknonw-typed info. """
		try:
			user = self.by_uid(int(value))
		except (TypeError, ValueError):
				user = self.by_login(value)
		return user
	def guess_list(self, value_list):
		users = []

		for value in value_list:
			try:
				user = self.guess_one(value)

			except (KeyError, exceptions.DoesntExistException):
				logging.notice(_(u'Skipped non-existing login or UID %s.')
																	% value)
			else:
				if user in users:
					pass
				else:
					users.append(user)

		return users
	def exists(self, uid=None, login=None):
		if uid:
			return uid in self.iterkeys()
		if login:
			return login in self.logins

		raise exceptions.BadArgumentError(_(u'You must specify an UID or a '
			'login to test existence of.'))
	def login_to_uid(self, login):
		""" Return the uid of the user 'login' """
		try:
			# use the cache, Luke !
			return self.by_login(login).uid
		except KeyError:
			raise exceptions.DoesntExistException(_(u'User %s does not exist')
																	% login)
	def uid_to_login(self, uid):
		""" Return the login for an UID, or raise Doesn't exists. """
		try:
			return self[uid].login
		except KeyError:
			raise exceptions.DoesntExistException(_(u'UID %s does not exist') % uid)

	def _cli_get(self, selected=None, long_output=False, no_colors=False):
		""" Export the user accounts list to human readable («passwd») form. """

		with self.lock:

			if selected is None:
				users = self.values()
			else:
				users = selected

			users.sort()

			assert ltrace('users', '| _cli_get(%r)' % users)

			# FIXME: forward long_output, or remove it.
			return '%s\n' % '\n'.join((user._cli_get()
							for user in sorted(users, key=attrgetter('uid'))))
