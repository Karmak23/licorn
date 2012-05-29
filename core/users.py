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

from licorn.foundations           import logging, exceptions, hlstr, settings
from licorn.foundations           import pyutils, fsapi, process
from licorn.foundations.events    import LicornEvent
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import DictSingleton, Enumeration
from licorn.foundations.constants import filters, backend_actions, distros, priorities, roles, relation

from licorn.core                import LMC
from licorn.core.groups         import Group
from licorn.core.classes        import SelectableController, CoreFSController, \
										CoreStoredObject, CoreFSUnitObject

import types

_locked_colors = {
		None: ST_NAME,
		True: ST_BAD,
		False: ST_OK
	}

class User(CoreStoredObject, CoreFSUnitObject):
	""" The User unit-object. """

	_id_field = 'uidNumber'

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
	def __getstate__(self):
		d = {
			'login'                : self.__login,
			'uidNumber'            : self.__uidNumber,
			'gidNumber'            : self.__gidNumber,
			'gecos'                : self.__gecos,
			'homeDirectory'        : self.__homeDirectory,
			'loginShell'           : self.__loginShell,
			'locked'               : self.__locked,
			'shadowLastChange'     : self.__shadowLastChange,
			'shadowInactive'       : self.__shadowInactive,
			'shadowWarning'        : self.__shadowWarning,
			'shadowExpire'         : self.__shadowExpire,
			'shadowMin'            : self.__shadowMin,
			'shadowMax'            : self.__shadowMax,
			'shadowFlag'           : self.__shadowFlag,
			'is_system'            : self.__is_system,
			'is_system_restricted' : self.__is_system_restricted,
			'profile'              : self.profile
			 }
		d.update(super(User, self).__getstate__())
		return d
	def __setstate__(self, data_dict):
		""" TODO: this pickle-friendly implementation is incomplete:
			self.weakref is still unset, so is `self.backend`, etc. """

		super(User, self).__setstate__(data_dict)

		cname = self.__class__.__name__

		for key, value in data_dict.iteritems():
			# tricky hack to re-construct the private attributes
			# while unpickling on the Pyro remote side.
			self.__dict__['_%s__%s' %(cname, key)] = value

		self.__is_standard            = not self.__is_system
		self.__is_system_unrestricted = not self.__is_system_restricted

		# when unpicking on the remote-side, no groups are present...
		self.__primaryGroup = None

		self.__pickled = True
	def get_relationship(self, group):

		if type(group) == types.IntType:
			group = LMC.groups.by_gid(group)

		if group in self.groups:
			return relation.MEMBER

		elif group.guest_group in self.groups:
			return relation.GUEST

		elif group.responsible_group in self.groups:
			return relation.RESPONSIBLE

		else:
			return relation.NO_MEMBERSHIP

	def __init__(self, uidNumber, login, password=None, userPassword=None,
		gidNumber=None, gecos=None, homeDirectory=None, loginShell=None,
		shadowLastChange=None, shadowInactive=None, shadowWarning=None,
		shadowExpire=None, shadowMin=None, shadowMax=None, shadowFlag=None,
		initialyLocked=False, backend=None, inotified=None,
		# this one is used only in creation mode, to speed up links between
		# Licorn® objects.
		primaryGroup=None):

		assert ltrace(TRACE_OBJECTS, '| User.__init__(%s, %s)' % (uidNumber, login))

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

		super(User, self).__init__(
				controller=LMC.users,
				backend=backend,
				inotified=inotified,
				check_file='%s/%s' % (self.__homeDirectory,
					LMC.configuration.users.check_config_file),
				object_info=Enumeration(
					home=self.__homeDirectory,
					user_uid=self.__uidNumber,
					user_gid=self.__gidNumber)
			)

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

		if primaryGroup:
			# must be called after super(), else 'no weakref yet'.
			primaryGroup.link_gidMember(self)

		# Reverse map the current object from its name (it is indexed on GID
		# in the Groups Controller), but only a weakref to be sure it will be
		# delete by the controller.
		#
		# NOTE: must be called after super(), depends on CoreStoredObject
		User.by_login[login] = self.weakref

		# CLI output pre-calculations.
		if len(login) + 2 > User._cw_login:
			User._cw_login = len(login) + 2
			User._cli_invalidate_all()

		self.__pickled = False
	def __str__(self):
		return '<%s(%s: %s) at 0x%x>' % (
			self.__class__.__name__,
			stylize(ST_UGID, self.__uidNumber),
			stylize(ST_NAME, self.__login),
			id(self)
		)
		#  = {\n\t%s\n\t}\n' % (
		#'\n\t'.join([ '%s: %s' % (attr_name, getattr(self, attr_name))
		#		for attr_name in dir(self) ])
		#)
	def __del__(self):

		if self.__pickled:
			# avoid useless exception on the WMI remote side.
			return

		assert ltrace(TRACE_GC, '| User %s.__del__()' % self.__login)

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
		'>> please implement User.gidNumber.setter'
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

			LicornEvent('user_primaryGroup_changed', user=self).emit(priorities.LOW)
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
		if self.__primaryGroup is not None:
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

			LicornEvent('user_gecos_changed', user=self).emit(priorities.LOW)

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

			LicornEvent('user_loginShell_changed', user=self).emit(priorities.LOW)

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
				LicornEvent('user_pre_change_password', user=self, password=password, synchronous=True).emit()

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
				LicornEvent('user_post_change_password', user=self, password=password, synchronous=True).emit()

				if self.__already_created:
					# don't forward this event on user creation, because we
					# already have the "user_added" for this case.
					LicornEvent('user_userPassword_changed', user=self).emit(priorities.LOW)

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
					return
				else:
					LicornEvent('user_pre_lock', user=self, synchronous=True).emit()

					self.__userPassword = '!' + self.__userPassword

					LicornEvent('user_post_lock', user=self, synchronous=True).emit()

					logging.notice(_(u'Locked user account {0}.').format(
											stylize(ST_LOGIN, self.__login)))

					self._cli_invalidate()
			else:
				if self.__locked:

					LicornEvent('user_pre_unlock', user=self, synchronous=True).emit()

					self.__userPassword = self.__userPassword[1:]

					LicornEvent('user_post_unlock', user=self, synchronous=True).emit()

					logging.notice(_(u'Unlocked user account {0}.').format(
											stylize(ST_LOGIN, self.__login)))

					self._cli_invalidate()
				else:
					logging.info(_(u'Account {0} already unlocked.').format(
											stylize(ST_NAME, self.__login)))
					return

			self.__locked = lock
			self.serialize()

			LicornEvent('user_locked_changed', user=self).emit(priorities.LOW)
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
		""" Home directory can't be changed yet.

			.. todo:: we should be able to change it for system users, at least.
		"""
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
			assert ltrace(TRACE_USERS, '| %s.serialize(%s → %s)' % (
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
			assert ltrace(TRACE_USERS, 'comparing 2 crypted passwords:\n%s\n%s' % (
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
			try:
				process.syscmd('cp -rf {0}/* {0}/.??* {1}'.format(
							skel, self.__homeDirectory))

			except exceptions.SystemCommandError, e:
				logging.warning(e)
				pyutils.print_exception_if_verbose()

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

			LicornEvent('user_skel_applyed', user=self).emit(priorities.LOW)

			logging.notice(_(u'Applyed skel {0} for user {1}').format(
										skel, stylize(ST_LOGIN, self.__login)))
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
		return '%s/%s' % (LMC.configuration.users.base_path, self.__login)
	def _build_system_home(self, directory):
		""" A system user has a home, which can be anywhere. """
		return directory
	def __resolve_locked_state(self):
		""" see if a given user accound is initially locked or not. """
		if self.__userPassword not in (None, '') \
			and self.__userPassword[0] == '!':
				return True

		return False
	def check(self, minimal=True, skel_to_apply=None, batch=False,
										auto_answer=None, full_display=True):
		"""Check current user account data consistency."""

		assert ltrace_func(TRACE_CHECKS)

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
				return self.__check_unrestricted_system_user(batch=batch,
												skel_to_apply=skel_to_apply,
												auto_answer=auto_answer,
												full_display=full_display)

			elif self.is_standard:
				return self.__check_standard_user(minimal=minimal,
												skel_to_apply=skel_to_apply,
												batch=batch,
												auto_answer=auto_answer,
												full_display=full_display)
			else:
				return self.__check_restricted_system_user(batch=batch,
													auto_answer=auto_answer,
													full_display=full_display)

	# aliases to CoreFSUnitObject methods
	__check_standard_user = CoreFSUnitObject._standard_check
	def __check_common_system_user(self, minimal=True, batch=False,
										auto_answer=None, full_display=True):

		assert ltrace_func(TRACE_CHECKS)

		my_gecos = self.__gecos

		if my_gecos != my_gecos.strip():
			my_gecos = my_gecos.strip()

		something_done = False

		if my_gecos.endswith(',,,'):
			something_done = True
			my_gecos = my_gecos[:-3]

		if my_gecos.endswith(',,'):
			something_done = True
			my_gecos = my_gecos[:-2]

		if my_gecos.endswith(','):
			something_done = True
			my_gecos = my_gecos[:-1]

		my_gecos = my_gecos.strip()

		if something_done:
			logging.notice(_(u"Auto-cleaned {0}'s gecos to \"{1}\".").format(
								stylize(ST_LOGIN, self.__login),
								stylize(ST_COMMENT, my_gecos)))

		for login, meaningless_gecoses, replacement_gecos in (
					('backup', ('backup'), _(u'%s Automatic Backup System') % distros[LMC.configuration.distro].title()),
					('bin', ('bin'), _(u'Special Executable Restrictor Account')),
					('bind', ('bind'), _(u'ISC Domain Name Service daemon')),
					('caldavd', ('calendarserver daemon'), _(u'Apple Calendar Server Daemon')),
					('daemon', ('daemon'), _(u'Generic System Daemon')),
					('dhcpd', ('dhcpd'), _(u'DHCP Daemon')),
					('dnsmasq', ('dnsmasq'), _(u'DNSmasq (DHCP & DNS) Daemon')),
					('ftp', ('ftp'), _(u'FTP Daemon / restricted account')),
					('games', ('games'), _(u'Games Specific Account')),
					('haldaemon', ('Hardware abstraction layer'), _(u'Hardware Abstraction Layer Daemon')),
					('hplip', ('HPLIP system user'), _(u'Hewlett-Packard Linux Imaging & Printing Daemon')),
					('irc', ('ircd'), _(u'Internet Relay Chats Daemon')),
					('kernoops', ('Kernel Oops Tracking Daemon'), _(u'Kernel OOPs Tracking Daemon')),
					('landscape', (''), _(u'Canonical\'s Lanscape Remote Administration account')),
					('libuuid', (''), _(u'UUID Library Account')),
					('lp', ('lp'), _('Line Printer Daemon')),
					('mail', ('mail'), _(u'Local E-Mail System Account')),
					('man', ('man'), _(u'Unix Manual Pages Generator')),
					('memcache', ('Memcached'), _(u'Memory Cache Daemon')),
					('messagebus', (''), _(u'System Message Bus (D-BUS)')),
					('motion', ('motion'), _(u'Video Motion Detection daemon')),
					('news', ('news'), _(u'Very unprivileged System Account')),
					('nobody', ('nobody'), _(u'Very unprivileged System Account')),
					('messagebus', (''), _(u'System Message Bus (D-BUS)')),
					('postfix', (''), _(u'Postfix® Mail System')),
					('proxy', ('proxy'), _(u'Web (& possibly more) Proxy Server')),
					('root', ('root'), _(u'John Root, System Administrator (BOFH)')),
					('saned', (''), _(u'Scanner Access Now Easy daemon')),
					('sshd', (''), _(u'Secure SHell Daemon')),
					('sync', ('sync'), _(u'Generic Synchronization Account')),
					('sys', ('sys'), _(u'Generic System Account')),
					('syslog', ('syslog'), _(u'System Logger Daemon')),
					('uucp', ('uucp'), _(u'Unix to Unix Copy Protocol daemon')),
					('www-data', ('www-data'), _(u'Web Server unprivileged Account')),
					('ntp', (''), _(u'Network Time Protocol Daemon')),
				):
			if self.__login == login and self.is_system:
				if my_gecos in meaningless_gecoses:
					if batch or logging.ask_for_repair(_(u'{0}\'s GECOS "{1}" '
						u'is currently meaningless, or we have a far better '
						u'and hypish value "{2}" ready to enhance it. Would '
						u'you like to use it?').format(
							stylize(ST_LOGIN, self.__login),
							stylize(ST_COMMENT, my_gecos),
							stylize(ST_OK, replacement_gecos))):
						my_gecos = replacement_gecos

			if my_gecos != self.__gecos:
				self.gecos = my_gecos
	def __check_unrestricted_system_user(self, minimal=True, skel_to_apply=None,
							batch=False, auto_answer=None, full_display=True):
		""" Check the home dir and its contents, if it exists (this is not
			mandatory for a system account). If it does not exist, it will not
			be created. """
		logging.progress(_(u'Checking system account %s…') %
											stylize(ST_NAME, self.__login))

		if self._checking.is_set():
			logging.warning(_(u'Account {0} already beiing ckecked, '
							u'aborting.').format(stylize(ST_LOGIN, self.__login)))
			return

		with self.lock:

			self._checking.set()

			result = self.__check_common_system_user(minimal=minimal,
													batch=batch,
													auto_answer=auto_answer,
													full_display=full_display)

			if os.path.exists(self.__homeDirectory):

				checked = set()

				for event in fsapi.check_dirs_and_contents_perms_and_acls_new(
						[ fsapi.FsapiObject(name='%s_home' % self.__login,
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

			return result
	def __check_restricted_system_user(self, minimal=True, batch=False,
										auto_answer=None, full_display=True):
		""" Check the home dir and its contents, if it exists (this is not
			mandatory for a system account). If it does not exist, it will not
			be created. """

		assert ltrace_func(TRACE_CHECKS)

		logging.progress(_(u'Checking restricted system account %s…') %
											stylize(ST_NAME, self.__login))

		if self._checking.is_set():
			logging.warning(_(u'account {0} already beiing ckecked, '
							u'aborting.').format(stylize(ST_LOGIN, self.__login)))
			return

		with self.lock:
			self._checking.set()
			result = self.__check_common_system_user(minimal=minimal,
													batch=batch,
													auto_answer=auto_answer,
													full_display=full_display)
			self._checking.clear()
			return result
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
							'{backend}	{gecos} {inotified}'.format(
								login=stylize(
									_locked_colors[self.__locked],
									(self.__login).rjust(label_width)),
								#id_type=_(u'uid'),
								uid=stylize(ST_UGID, self.__uidNumber)
										+ ' ' * uid_label_rest,
								pri_group='%s%s' % (
										self.__primaryGroup()._cli_get_small(),
										' ' * gid_label_rest),
								backend=stylize(ST_BACKEND, self.backend.name),
								gecos=stylize(ST_COMMENT,
									self.__gecos) if self.__gecos != '' else '',
								inotified='' if self.is_system or self.inotified
												else stylize(ST_BAD,
													_('(not watched)'))) ]

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
				stylize(_locked_colors[self.__locked], self.__login),
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
	def to_WMI(self):
		""" A simplified version of the current object, suitable to be
			forwarded via Pyro. """
		d = self.__getstate__()
		d.update({
			'profile'       : self.__primaryGroup().name
									if self.__is_standard else '',
			'backend'       : self.backend.name,

			'search_fields' : [ 'uidNumber', 'gecos', 'login', 'profile']
		})
		return d
	def to_JSON(self):
			return json.dumps(self.to_WMI())
class UsersController(DictSingleton, CoreFSController, SelectableController):
	""" Handle global operations on unit User objects,
		from a system-wide perspective.
	"""
	init_ok = False
	load_ok = False

	#: used in `RWI.select()`
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

	# local and specific implementations of SelectableController methods.
	def by_uid(self, uid):
		# we need to be sure we get an int(), because the 'uid' comes from RWI
		# and is often a string.
		return self[int(uid)]
	def by_login(self, login):
		# Call the thing before returning it, because it's a weakref.
		return User.by_login[login]()

	# the generic way (called by SelectableController)
	by_key  = by_uid
	by_id   = by_uid
	by_name = by_login
	# end SelectableController

	def __init__(self, *args, **kwargs):
		""" Create the user accounts list from the underlying system. """

		assert ltrace(TRACE_USERS, '> UsersController.__init__(%s)' %
			UsersController.init_ok)

		if UsersController.init_ok:
			return

		super(self.__class__, self).__init__(name='users')

		UsersController.init_ok = True
		assert ltrace(TRACE_USERS, '< UsersController.__init__(%s)' %
			UsersController.init_ok)
	@property
	def logins(self):
		return (login for login in User.by_login)
	def word_match(self, word):
		return hlstr.multi_word_match(word, self.logins)
	def load(self):
		if UsersController.load_ok:
			return

		LicornEvent('users_loading', users=self, synchronous=True).emit()

		assert ltrace(TRACE_USERS, '| load()')
		self.reload(send_event=False)

		LicornEvent('users_loaded', users=self, synchronous=True).emit()

		UsersController.load_ok = True
	def reload(self, send_event=True):
		""" Load (or reload) the data structures from the system data. """
		assert ltrace(TRACE_USERS, '| reload()')

		if send_event:
			LicornEvent('users_reloading', users=self, synchronous=True).emit()

		with self.lock:
			for backend in self.backends:
				for uid, user in backend.load_Users():
					self[uid] = user

		# CoreFSController must be initialized *after* users and
		# groups are loaded, because it needs resolution to set
		# rules contents.
		CoreFSController.reload(self)

		if send_event:
			LicornEvent('users_reloaded', users=self, synchronous=True).emit()
	def reload_backend(self, backend):
		""" Reload only one backend data (called from inotifier). """

		assert ltrace(TRACE_USERS, '| reload_backend(%s)' % backend.name)

		loaded = []

		assert ltrace(TRACE_LOCKS, '| users.reload_backend enter %s' % self.lock)

		with self.lock:
			for uid, user in backend.load_Users():
				if uid in self:
					logging.warning2(_(u'{0}.reload: Overwritten uid {1}.').format(
											stylize(ST_NAME, self.name), uid))
				self[uid] = user
				loaded.append(uid)

				LicornEvent('user_changed', user=user).emit(priorities.LOW)

			for uid, user in self.items():
				if user.backend.name == backend.name:
					if uid in loaded:
						loaded.remove(uid)

					else:
						logging.progress(_(u'{0}: removing disapeared user '
							u'{1}.').format(stylize(ST_NAME, self.name),
								stylize(ST_LOGIN, user.login)))

						self.del_User(user, batch=True, force=True)

			# needed to reload the group cache.
			logging.notice(_(u'Reloading {0} controller too.').format(stylize(ST_NAME, LMC.groups.name)))

			LMC.groups.reload_backend(backend)

		assert ltrace(TRACE_LOCKS, '| users.reload_backend exit %s' % self.lock)
	def serialize(self, user=None):
		""" Write the user data in appropriate system files."""

		assert ltrace(TRACE_USERS, '| serialize()')

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

			elif filters.NONE == filter_string:
				filtered_users = []

			elif type(filter_string) == type([]):
				filtered_users = filter_string

			elif type(filter_string) == type(1):
				filtered_users = []

				if filters.WATCHED == filter_string:
					filtered_users.extend(user for user in self
														if user.inotified)

				elif filters.NOT_WATCHED == filter_string:
					filtered_users.extend(user for user in self
														if user.is_standard and not user.inotified)


				elif filter_string & filters.NOT_SYSTEM \
						or filter_string & filters.STANDARD:
					filtered_users.extend(user for user in self if user.is_standard)

				elif filters.SYSTEM == filter_string:
					filtered_users.extend(user for user in self if user.is_system)

				elif filters.SYSTEM_RESTRICTED & filter_string:
					filtered_users.extend(user for user in self if user.is_system_restricted)

				elif filters.SYSTEM_UNRESTRICTED & filter_string:
					filtered_users.extend(user for user in self if user.is_system_unrestricted)

			else:
					uid_re = re.compile("^uid=(?P<uid>\d+)")
					uid = uid_re.match(filter_string)
					if uid is not None:
						if int(uid.group('uid')) in self.iterkeys():
							filtered_users.append(self[uid])
						else:
							raise exceptions.DoesntExistException(
								_(u'UID {0} does not exist.').format(uid))

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
					settings.defaults.home_base_path) \
					and not home.startswith('/var') \
					or home.startswith(LMC.configuration.groups.base_path) \
					or home.find('/tmp') != -1:

					raise exceptions.BadArgumentError(_(u'Specified home '
						'directory {0} for system user {1} is outside {2} '
						'and /var, or inside {3} or a temporary '
						'directory (/var/tmp, /tmp). This is unsupported, '
						'Aborting.').format(
						stylize(ST_PATH, home),
						stylize(ST_NAME,login),
						settings.defaults.home_base_path,
						LMC.configuration.groups.base_path))

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

		if gecos in (None, ''):
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
		in_groups=None, inotified=True, batch=False, force=False):
		"""Add a user and return his/her (uid, login, pass)."""

		assert ltrace(TRACE_USERS, '''> add_User(login=%s, system=%s, pass=%s, '''
			'''uid=%s, gid=%s, profile=%s, skel=%s, gecos=%s, first=%s, '''
			'''last=%s, home=%s, shell=%s, in_groups=%s)''' % (login, system, password,
			desired_uid, repr(primary_group), repr(profile),
			skel, gecos, firstname, lastname, home, shell, in_groups))

		assert type(in_groups) == type([])

		login, firstname, lastname, gecos, shell, skel = \
			self.__validate_basic_fields(login, firstname, lastname,
				gecos, shell, skel)

		# Everything seems basically OK, we can now lock and go on.
		with self.lock:
			self.__validate_important_fields(desired_uid, login, system, force)
			uid = self._generate_uid(login, desired_uid, system)

			LicornEvent('user_pre_add', uid=uid, login=login,
								system=system, password=password, synchronous=True).emit()

			groups_to_add_user_to = in_groups

			skel_to_apply = LMC.configuration.users.default_skel or None
			homeDirectory = self.__validate_home_dir(home, login, system, force)

			if profile is not None:

				if type(profile) == types.IntType:
					profile = LMC.profiles.by_gid(profile)

				loginShell    = profile.profileShell
				skel_to_apply = profile.profileSkel
				primary_group = profile.group

				groups_to_add_user_to.extend(profile.groups)
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
								inotified=inotified,
								backend=self._prefered_backend
									if backend is None else backend,
								initialyLocked=False)

			# we can't delay the serialization, because this would break Samba
			# (and possibly others) stuff, and the add_user_in_group stuff too:
			# they need the data to be already written to disk to operate.
			#
			# thus, DO NOT UNCOMMENT -- if not batch:
			user.serialize(backend_actions.CREATE)

			LicornEvent('user_post_add', user=user, password=password, synchronous=True).emit()

			# this will implicitely load the check_rules for the user.
			user.check(skel_to_apply=skel_to_apply, minimal=True, batch=True)

		# we needed to delay this display until *after* account creation, to
		# know the login (it could have been autogenerated by the User class).
		if gen_pass:
			logging.notice(_(u'Autogenerated password for user {0} '
								u'(uid={1}): {2}.').format(
								stylize(ST_LOGIN, user.login),
								stylize(ST_UGID, user.uidNumber),
								stylize(ST_SECRET, password)),
							# avoid printing the password in clear-text in
							# the daemon's log... This would be dumb.
							to_local=False)

		logging.notice(_(u'Created {accttype} user {login} (uid={uid}).').format(
			accttype=_(u'system') if system else _(u'standard'),
			login=stylize(ST_LOGIN, login),
			uid=stylize(ST_UGID, uid)))

		for group in groups_to_add_user_to:

			if type(group) == types.IntType:
				group = LMC.groups.by_gid(group)

			group.add_Users([ user ], emit_event=False)

		# FIXME: Set quota
		if profile is not None:
			#os.popen2( [ 'quotatool', '-u', str(uid), '-b',
			#	settings.defaults.quota_device, '-l' '%sMB'
			#	% LMC.profiles[profile]['quota'] ] )[1].read()
			#logging.warning("quotas are disabled !")
			# XXX: Quotatool can return 2 without apparent reason
			# (the quota is etablished) !
			pass

		# Now that the user is created and member of its initial groups,
		# it's time to advertise the good news to everyone. Do not emit()
		# this event too early in the method, other parts of Licorn® assume
		# the home dir created and groups to be already setup when they
		# receive this event.
		LicornEvent('user_added', user=user).emit(priorities.LOW)

		assert ltrace(TRACE_USERS, '< add_User(%r)' % user)

		# We *need* to return the password, in case it was autogenerated.
		# This is the only way we can know it, in massive imports.
		return user, password
	def del_User(self, user, no_archive=False, force=False, batch=False):
		""" Delete a user. """

		assert ltrace_func(TRACE_USERS)

		if type(user) == types.IntType:
			user = self.by_uid(user)

		if user.is_system_restricted and not force:
			raise exceptions.BadArgumentError(_(u'Cannot delete '
				'restricted system account %s without the --force '
				'argument, this is too dangerous.') %
					stylize(ST_NAME, user.login))

		# Delete user from his groups
		# '[:]' to fix #14, see
		# http://docs.python.org/tut/node6.html#SECTION006200000000000000000
		for group in user.groups[:]:
			group.del_Users([ user ], batch=True, emit_event=False)

		LicornEvent('user_pre_del', user=user, synchronous=True).emit()

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

			# forward the bad news to anyone interested.
			LicornEvent('user_deleted', user=user).emit(priorities.LOW)

			if user.is_standard:
				user.inotified_toggle(False, full_display=False)

			# NOTE: this must be done *after* having deleted the data from self,
			# else mono-maniac backends (like shadow) don't see the change and
			# save everything, including the user we want to delete.
			user.backend.delete_User(user)

			assert ltrace(TRACE_GC, '  user ref count before del: %d %s' % (
					sys.getrefcount(user), gc.get_referrers(user)))

			del user

		# checkpoint, needed for multi-delete (users-groups-profile) operation,
		# to avoid collecting the deleted users at the end of the run, making
		# throw false-negative operation about non-existing groups.
		gc.collect()

		logging.notice(_(u'Deleted user account {0}.').format(
			stylize(ST_LOGIN, login)))

		LicornEvent('user_post_del', uid=uid, login=login,
						no_archive=no_archive, synchronous=True).emit()

		# The user account is now wiped out from the system.
		# Last thing to do is to delete or archive the HOME dir.
		# NOTE: altering homeDir while inotifier is removing watches can
		# produce warnings on the inotify side ("vanished directory ...").
		# These warnings are harmless.
		if no_archive:
			workers.service_enqueue(priorities.LOW, fsapi.remove_directory, homedir)
		else:
			workers.service_enqueue(priorities.LOW, fsapi.archive_directory, homedir, login)
	def dump(self):
		""" Dump the internal data structures (debug and development use). """

		with self.lock:

			assert ltrace(TRACE_USERS, '| dump()')

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

			assert ltrace(TRACE_USERS, '| ExportCSV(%s)' % uids)

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

			assert ltrace(TRACE_USERS, '| to_XML(%r)' % users)

			return ('<?xml version="1.0" encoding="UTF-8"?>\n'
					'<users-list>\n'
					'%s\n'
					'</users-list>\n') % '\n'.join(
						user.to_XML() for user in users)
	def to_JSON(self, selected=None):
		""" Export the user accounts list to XML. """

		with self.lock:
			if selected is None:
				users = self
			else:
				users = selected

			assert ltrace(TRACE_USERS, '| to_JSON(%r)' % users)

			return '[ %s ]' % ','.join(user.to_JSON() for user in users)
	def chk_Users(self, users_to_check=[], minimal=True, batch=False,
														auto_answer=None):
		"""Check user accounts and account data consistency."""

		assert ltrace(TRACE_USERS, '> chk_Users(%r)' % users_to_check)

		# FIXME: should we crash if the user's home we are checking is removed
		# during the check ? what happens ?

		# dependancy: base dirs must be OK before checking users's homes.
		LMC.configuration.check_base_dirs(minimal=minimal,
			batch=batch, auto_answer=auto_answer)

		def my_check_user(user, minimal=minimal, batch=batch, auto_answer=auto_answer):
			return user.check(minimal=minimal, batch=batch, auto_answer=auto_answer)

		all_went_ok = reduce(pyutils.keep_false, map(my_check_user, users_to_check))

		if all_went_ok is False:
			# NOTICE: don't test just "if reduce():", the result could be None
			# and everything is OK when None…
			raise exceptions.LicornCheckError(_(u'Some user(s) check(s) did '
				'not pass, or were not corrected.'))

		assert ltrace(TRACE_USERS, '< chk_Users(%s)' % all_went_ok)
		return all_went_ok
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

			assert ltrace(TRACE_USERS, '| _cli_get(%r)' % users)

			# FIXME: forward long_output, or remove it.
			return '%s\n' % '\n'.join((user._cli_get()
							for user in sorted(users, key=attrgetter('uid'))))
