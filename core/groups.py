# -*- coding: utf-8 -*-
"""
Licorn core: groups - http://docs.licorn.org/core/groups.html

:copyright:
	* 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	* partial 2010 Robin Lucbernet <robinlucbernet@gmail.com>
	* partial 2006 Régis Cobrun <reg53fr@yahoo.fr>

:license: GNU GPL version 2

"""

import sys, os, stat, posix1e, re, time, weakref, gc

from traceback  import print_exc
from threading  import current_thread, Event
from contextlib import nested
from operator   import attrgetter

from licorn.foundations           import logging, exceptions
from licorn.foundations           import fsapi, pyutils, hlstr
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, Enumeration
from licorn.foundations.constants import filters, backend_actions, distros

from licorn.core                import LMC
from licorn.core.classes        import CoreFSController, CoreStoredObject, CoreFSUnitObject
from licorn.daemon              import priorities, roles, InternalEvent

class Group(CoreStoredObject, CoreFSUnitObject):
	""" a Licorn® group object.

		.. versionadded:: 1.2.5
	"""
	_permissive_colors = {
			None: ST_NAME,
			True: ST_RUNNING,
			False: ST_STOPPED
		}

	#: cli width helpers to build beautiful CLI outputs.
	_cw_name = 10

	# reverse mapping on group names
	by_name = {}

	@staticmethod
	def _cli_invalidate_all():
		for group_ref in Group.by_name.itervalues():
			group_ref()._cli_invalidate()
	@staticmethod
	def _cli_compute_label_width(avoid=None):

		_cw_name = 10

		for name in Group.by_name:
			lenght = len(name) + 2

			if lenght > _cw_name:
				_cw_name = lenght

		if Group._cw_name != _cw_name:
			Group._cw_name = _cw_name
			Group._cli_invalidate_all()
	@staticmethod
	def is_system_gid(gid):
		""" Return true if gid is system. """
		return gid < LMC.configuration.groups.gid_min \
			or gid > LMC.configuration.groups.gid_max
	@staticmethod
	def is_standard_gid(gid):
		""" Return true if gid is standard (not system). """
		return gid >= LMC.configuration.groups.gid_min \
			and gid <= LMC.configuration.groups.gid_max
	@staticmethod
	def is_restricted_system_gid(gid):
		""" Return True if gid is outside of
			Licorn® controlled system gids boundaries. """
		return gid < LMC.configuration.groups.system_gid_min \
					or gid > LMC.configuration.groups.gid_max
	@staticmethod
	def make_name(inputname=None):
		""" Make a valid login from  user's firstname and lastname."""

		#TODO: make this a static meth of :class:`Group` ?

		groupname = hlstr.validate_name(inputname,
						maxlenght=LMC.configuration.groups.name_maxlenght,
						custom_keep='-._')

		if not hlstr.cregex['group_name'].match(groupname):
			raise exceptions.BadArgumentError(_(u'Cannot build '
							u'a valid UNIX group name (got {0}, which does '
							u'not verify {1}) with the string you provided '
							u'"{2}".').format(groupname,
								hlstr.regex['group_name'], inputname))

		# TODO: verify if the group doesn't already exist.
		#while potential in UsersController.users:
		return groupname
	@staticmethod
	def special_sort(groups):
		""" Sort a list of group to display them in alphabetical order. *But*,
			if there are guest or responsible groups in there, sort on the
			corresponding standard group name, because it's always the standard
			group name that gets displayed in :program:`get` outputs.
		"""

		# Thus, a special cpm() method.
		#groups.sort(cmp=lambda x,y: cmp(
		#				x.standard_group.name
		#					if x.is_responsible or x.is_guest else x.name,
		#				y.standard_group.name
		#					if y.is_responsible or y.is_guest else y.name))

		# Thus, a special key func.
		groups.sort(key=lambda x: x.standard_group.name
									if x.is_helper else x.name)

	def __init__(self, gidNumber, name, memberUid=None,
		homeDirectory=None, permissive=None, description=None,
		groupSkel=None, userPassword=None, backend=None):

		CoreStoredObject.__init__(self,	LMC.groups, backend)

		assert ltrace('objects', '| Group.__init__(%s, %s)' % (gidNumber, name))

		# use private attributes, made public via the property behaviour
		self.__gidNumber    = gidNumber
		self.__name         = name
		self.__description  = description
		self.__groupSkel    = groupSkel
		self.__userPassword = userPassword

		# The weakref is used to link me to other core objects. My Controller
		# will get a real reference anyway.

		if memberUid:
			# Transient variable that will be wiped by _setup_initial_links()
			# after use. it contains logins, that will be expanded to real user
			# objects.
			self.__memberUid = memberUid

		# These two will be filled by _setup_initial_links(), trigerred by
		# the controller, after all backends have loaded.
		self.__gidMembers = []
		self.__members    = []

		# These will be initialy filled when ProfilesController loads,
		# and updated by [un]link_Profile() and the profile property after that.
		# Only enforced thing, as of 20110215:
		#					__profile not in __profiles

		# the profile corresponding to this group (if any)
		self.__profile = None

		# the list of profiles the group is in.
		self.__profiles = []

		# Reverse map the current object from its name (it is indexed on GID
		# in the Groups Controller), but only with a weak ref, to be sure the
		# object gets deleted from the controller.
		Group.by_name[name] = self.weakref

		# useful booleans, must exist before __resolve* methods are called.
		self.__is_system   = Group.is_system_gid(gidNumber)
		self.__is_standard = not self.__is_system

		if self.__is_system:
			self.__is_system_restricted   = Group.is_restricted_system_gid(gidNumber)
			self.__is_system_unrestricted = not self.__is_system_restricted
		else:
			self.__is_system_restricted   = False
			self.__is_system_unrestricted = False

		# is_privilege will be set by PrivilegesWhiteList on load.
		# for now, we need to set it to whatever value. I choose "False".
		self.__is_privilege = False

		# self.__is_system must already be set (to whatever value) for this
		# to work, because system group don't have homedirs.
		self.__homeDirectory = self._resolve_home_directory(homeDirectory)

		#: this must be done *after* the home dire resolution, else it
		# will fail (this is enforced anyway in the method).
		self.__permissive = self.__resolve_permissive_state(permissive)

		self.__is_responsible = self.__is_system and self.__name.startswith(
										LMC.configuration.groups.resp_prefix)

		self.__is_guest = self.__is_system and self.__name.startswith(
										LMC.configuration.groups.guest_prefix)

		self.__is_helper = self.__is_responsible or self.__is_guest

		# these will be filled later by the controller,
		# which has the global view.
		self.__standard_group    = None
		self.__responsible_group = None
		self.__guest_group       = None

		CoreFSUnitObject.__init__(self, '%s%s' % (self.__homeDirectory,
							LMC.configuration.groups.check_config_file_suffix),
							Enumeration(
									home=self.homeDirectory,
									user_uid=-1,
									# we force the GID to be 'acl'.
									user_gid=LMC.configuration.acls.gid),
							(('@GROUP', self.__name),
								('@GW', 'w' if self.__permissive else '-')))

		# CLI output pre-calculations.
		if len(name) + 2 > Group._cw_name:
			Group._cw_name = len(name) + 2
			Group._cli_invalidate_all()
	def __del__(self):

		assert ltrace('gc', '| Group %s.__del__()' % self.__name)

		del self.__profile

		del self.__profiles

		for user in self.__members:
			try:
				user().unlink_Group(self)
			except (ValueError, AttributeError):
				# "ValueError('list.remove(x): x not in list',)" happens on
				# backends reload, when an "old" Group tries to remove itself
				# from it's members __groups cache, but the GroupsController
				# already called `user.clear_Groups()` and the user doesn't
				# hold the reference to the current group anymore.
				#
				# The AttributeError happens when Users are backends-reloaded
				# before groups: the old Users are GC'ed, and the user() weakref
				# call returns None, which can't do 'unlink_Group()'.
				#
				# In either case, the problem is totally harmless.
				pass

		del self.__members

		# avoid removing a reference to a new instance: clean it only if it
		# points to us.
		if Group.by_name[self.__name] == self.weakref:
			del Group.by_name[self.__name]

		if len(self.__name) + 2 == Group._cw_name:
			Group._cli_compute_label_width()
	def __str__(self):
		return '%s(%s‣%s) = {\n\t%s\n\t}\n' % (
			self.__class__,
			stylize(ST_UGID, self.__gidNumber),
			stylize(ST_NAME, self.__name),
			'\n\t'.join('%s: %s' % (attr_name, str(attr))
					for attr_name, attr in self.__dict__.items()
						if not callable(attr)))
	def __repr__(self):
		return '%s(%s‣%s)' % (
			self.__class__,
			stylize(ST_UGID, self.__gidNumber),
			stylize(ST_NAME, self.__name))

	@property
	def sortName(self):
		try:
			return self.__sortname
		except AttributeError:
			self.__sortname = self.__standard_group().name \
								if self.__is_helper else self.__name
			return self.__sortname
	@property
	def standard_group(self):
		""" turn the weakref into an object before returning it for use. """
		return self.__standard_group() if self.__standard_group else None
	@standard_group.setter
	def standard_group(self, group):
		self.__standard_group = group.weakref
	@property
	def responsible_group(self):
		""" turn the weakref into an object before returning it for use. """
		return self.__responsible_group() if self.__responsible_group else None
	@responsible_group.setter
	def responsible_group(self, group):
		self.__responsible_group = group.weakref
	@property
	def guest_group(self):
		""" turn the weakref into an object before returning it for use. """
		return self.__guest_group() if self.__guest_group else None
	@guest_group.setter
	def guest_group(self, group):
		self.__guest_group = group.weakref
	@property
	def memberUid(self):
		""" R/O member UIDs (which are really logins, not UIDs). This property
			returns a generator of the current group's members. It is a
			compatibility property, used in backends at save time. """
		return (user().login for user in self.__members)
	@property
	def gidNumber(self):
		""" Read-only GID attribute. """
		return self.__gidNumber
	@property
	def name(self):
		""" the group name (indexed in a reverse mapping dict). There is no
			setter, because the name of a given group never changes. """
		return self.__name
	@property
	def profile(self):
		""" Return the profile linked to this group. Only system group used
			as primary profile group return something useful. All others return
			``None``. """

		# call() the __profile to turn the weakref into an object before
		# returning it to caller.
		return self.__profile() if self.__profile else None
	@profile.setter
	def profile(self, profile):
		if profile.gidNumber == self.__gidNumber:
			self.__profile = profile.weakref
		else:
			raise exceptions.LicornRuntimeError(_(u'group {0}: Cannot set a '
				u'profile ({1}) which has not the same GID as me '
				u'({2} != {3})!').format(stylize(ST_NAME, self.__name),
					profile.name,
					self.__gidNumber, profile.gidNumber))
	@property
	def permissive(self):
		""" Permissive state of the group shared directory.
		See http://docs.licorn.org/groups/permissions.en.html
		For more details and meanings explanation.

		LOCKED during setter because we don't want a group to
		be deleted / modified during this operation, which is
		very quick.

		"""
		return self.__permissive
	@permissive.setter
	def permissive(self, permissive):

		if self.__is_system:
			return

		assert isbool(permissive)

		if self.__permissive == permissive:
			logging.notice(_(u'Permissive state {0} '
							u'for group {1}.').format(
								stylize(ST_COMMENT, _(u'unchanged')),
								stylize(ST_NAME, self.name)))
			return

		with self.lock:

			if permissive:
				qualif = ''
				value  = _(u'activated')
				color  = ST_OK
			else:
				qualif = _(u'not ')
				value  = _(u'deactivated')
				color  = ST_BAD

			self.__permissive = permissive

			self.reload_check_rules((('@GROUP', self.__name),
								('@GW', 'w' if self.__permissive else '-')))

			# auto-apply the new permissiveness
			L_service_enqueue(priorities.HIGH, self.check, batch=True)

			logging.notice(_(u'Switched group {0} permissive '
							u'state to {1} (Shared content permissions are '
							u'beiing checked in the background, this can '
							u'take a while…)').format(
								stylize(ST_NAME, self.name),
								stylize(color, value)))
	@property
	def userPassword(self):
		""" Change the password of a group. """
		return self.__userPassword
	@property
	def description(self):
		""" Change the description of a group. """
		return self.__description
	@description.setter
	def description(self, description=None):

		if description is None:
			raise exceptions.BadArgumentError(
				_(u'You must specify a description'))

		with self.lock:
			if not hlstr.cregex['description'].match(description):
				raise exceptions.BadArgumentError(_(u'Malformed description '
					u'"{0}", must match /{1}/i.').format(
					stylize(ST_COMMENT, description),
					stylize(ST_REGEX, hlstr.regex['description'])))

			self.__description = description
			self.serialize()
			self._cli_invalidate()

			logging.notice(_(u'Changed group {0} description '
				u'to "{1}".').format(stylize(ST_NAME, self.__name),
				stylize(ST_COMMENT, description)))
	@property
	def groupSkel(self):
		""" Change the description of a group. """
		return self.__groupSkel
	@groupSkel.setter
	def groupSkel(self, groupSkel=None):

		if groupSkel is None:
			raise exceptions.BadArgumentError(
				_(u'You must specify a groupSkel'))

		if groupSkel not in LMC.configuration.users.skels:
			raise exceptions.DoesntExistError(_(u'Invalid skel {0}. '
							u'Valid skels are: {1}.').format(
					groupSkel, ', '.join(LMC.configuration.users.skels)))

		with self.lock:
			self.__groupSkel = groupSkel
			self.serialize()

			logging.notice(_(u'Changed group {0} skel to {1}.').format(
					stylize(ST_NAME, self.name),
					stylize(ST_COMMENT, groupSkel)))
	@property
	def homeDirectory(self):
		""" Read-write attribute, the path to the home directory of a standard
			group (which holds shared content). Only standard group have home
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
		""" Read-only boolean indicating if the current group is system or not. """
		return self.__is_system
	@property
	def is_system_restricted(self):
		""" Read-only boolean indicating if the current group is a restricted
			system one. Restricted group are not touched by Licorn® (they are
			usually managed by the distro maintainers). """
		return self.__is_system_restricted
	@property
	def is_system_unrestricted(self):
		""" Read-only boolean indicating if the current group is an
			unrestricted system one. Unrestricted system groups are handled
			by Licorn®. """
		return self.__is_system_unrestricted
	@property
	def is_standard(self):
		""" Read-only boolean, exact inverse of :attr:`is_system`. """
		return self.__is_standard
	@property
	def is_helper(self):
		""" True if responsible or guest. """
		return self.__is_helper
	@property
	def is_responsible(self):
		""" Read-only boolean indicating if the current object is a responsible
			group (= a Licorn® system group, associated with a standard group).
		"""
		return self.__is_responsible
	@property
	def is_guest(self):
		""" Read-only boolean indicating if the current object is a guest group
			(= a Licorn® system group, associated with a standard group). """
		return self.__is_guest
	@property
	def is_empty(self):
		""" Return emptyness (no members), for **standard groups** (if you are
		looking for an universal `empty` property, just test if
		:meth:`all_members` returns ``[]``. """
		return self.is_standard and self.__members == []
	@property
	def is_privilege(self):
		return self.__is_privilege
	@is_privilege.setter
	def is_privilege(self, is_privilege):
		self.__is_privilege = is_privilege
		# wipe the cache to force recomputation
		try: del self.__cg_precalc_small
		except: pass
	@property
	def gidMembers(self):
		# turn the weakrefs into real objects before returning them.
		return [ m() for m in self.__gidMembers ]
	@property
	def members(self):
		""" Return all members (as objects) of a group, which are not
			members of this group in their primary group. """

		# TODO: really verify, for each user, that their member ship is not
		# duplicated between primary and auxilliary groups.

		return [ m() for m in self.__members ]
	@property
	def all_members(self):
		""" Return all members of a given group name (primary and auxilliary).

			.. note:: This method will **never** return duplicates, because
				a user cannot be added to auxilliary members if it is already
				a primary member.
		"""

		return self.gidMembers + self.members
	@property
	def profiles(self):
		""" the profiles the group is recorded in. Stored internally as
			weakrefs, returned as objects. """
		return [ profile() for profile in self.__profiles ]

	# properties comfort aliases
	gid                = gidNumber
	is_permissive      = permissive
	privilege          = is_privilege
	primaryMembers     = gidMembers
	primary_members    = gidMembers
	auxilliary_members = members

	@property
	def watches(self):
		""" R/O property, containing the current group inotifier watches,
			in the form of a dictionnary of path -> WD. """

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
	def _setup_initial_links(self):
		""" Transient and self-destructing method that will link users to
			to the current group.

			This method exists to be called by the controller after *all*
			backends have loaded. If we run the contents of this method too
			early, a group referencing users or groups located in another
			backend won't see them, and falsely consider them as non-existing.

			If an attribute :attr:`__memberUid` exists, it will be deleted.
			This method will self-destruct too after first use, because in
			normal conditions links are setup dynamically and maintained by
			other methods.

			The method returns a list of users, whose groups must be sorted.
			The controller will merge all lists into a set() at the end of
			the setup of all groups, and sort users groups only once.

		"""

		# collect our primary members.

		for user in LMC.users:
			if user.gidNumber == self.__gidNumber:

				# link the other side to us.
				user.primaryGroup = self

		# now collect our auxilliary members, if any.

		try:
			memberUid = self.__memberUid
			del self.__memberUid
		except AttributeError:
			return

		# reconcile manual changes eventually made outside of licorn.
		# this will avoid sorting them after the collection, with a more
		# CPU intensive approach.
		memberUid.sort()

		rewrite = False

		for member in memberUid:

			try:
				user = LMC.users.by_login(member)
			except KeyError:
				rewrite = True
				logging.warning(_(u'group {0}: removed relationship for '
									u'non-existing user {1}.').format(
										stylize(ST_NAME, self.__name),
										stylize(ST_LOGIN, member)))

			else:
				if user.weakref in self.__members:
					rewrite = True
					logging.warning(_(u'group {0}: removed duplicate '
									u'relationship for member {1}.').format(
										stylize(ST_NAME, self.__name),
										stylize(ST_LOGIN, member)))

				elif user.weakref in self.__gidMembers:
					rewrite = True
					logging.warning(_(u'group {0}: removed primary member {1} '
									u'from auxilliary members list.').format(
										stylize(ST_NAME, self.__name),
										stylize(ST_LOGIN, member)))

				else:
					# this is an automated load procedure, not an administrative
					# command. Don't display any notice nor information.

					# don't sort the groups, this will be done one time for all
					# in the controller method.
					user.link_Group(self)

		if rewrite:
			yield self
	def serialize(self, backend_action=backend_actions.UPDATE):
		""" Save group data to originating backend. """

		assert ltrace('groups', '| %s.serialize(%s → %s)' % (
											stylize(ST_NAME, self.name),
											self.backend.name,
											backend_actions[backend_action]))

		self.backend.save_Group(self, backend_action)
	def add_Users(self, users_to_add=None, force=False, batch=False):
		""" Add a user list in the group 'name'. """

		caller = current_thread().name

		assert ltrace('groups', '> %s: %s.add_Users(%s)' % (
								caller, self.__name,
								', '.join(user.login for user in users_to_add)))

		if users_to_add is None:
			raise exceptions.BadArgumentError(
						_(u'You must specify a users list'))

		assert ltrace('locks', '  %s %s' % (LMC.groups.lock, LMC.users.lock))

		# we need to lock users to be sure they don't dissapear during this phase.
		with nested(LMC.groups.lock, LMC.users.lock):

			work_done = False

			for user in users_to_add:

				if user.weakref in self.__members \
									or user.gidNumber == self.__gidNumber:

					if self.__name != LMC.configuration.users.group:
						log = logging.info

					else:
						# Adding the user to 'users' is mandatory, but will
						# occur automatically when we add it to any std or
						# helper group. Don't annoy the user with a useless
						# and polluting message.
						log = logging.progress

						log(_(u'User {0} is already a member '
							u'of {1} (primary or not), skipped.').format(
								stylize(ST_LOGIN, user.login),
								stylize(ST_NAME, self.__name)))
				else:
					self.__check_mutual_exclusions(user, force)

					if self.__is_standard or self.__is_helper:
						# Adding the user to group 'users' is mandatory for
						# any user to be able to walk /home/groups without
						# errors, at least on Debian and derivatives.
						# Do this in the background, though.
						#
						#if LMC.LMC.configuration.users.group not in user.groups:
						Group.by_name[
							LMC.configuration.users.group]().add_Users(
								[ user ], batch=True)

					L_event_run(InternalEvent('group_pre_add_user', self, user))


					# the ADD operation, per se.
					self.__members.append(user.weakref)
					user._cli_invalidate()

					# update the user reverse link.
					# the user will call link_User() in response,
					# with its weakref, so as we don't hold a strong ref to it.
					user.link_Group(self)

					if self.__is_helper:
						self.standard_group._cli_invalidate()
					else:
						self._cli_invalidate()

					logging.notice(_(u'Added user {0} to members '
									u'of group {1}.').format(
										stylize(ST_LOGIN, user.login),
										stylize(ST_NAME, self.__name)))

					if batch:
						work_done = True
					else:
						self.serialize()

					L_event_run(InternalEvent('group_post_add_user', self, user))

					# THINKING: shouldn't we turn this into an extension?
					L_service_enqueue(priorities.LOW,
								self.__add_group_symlink, user, batch=True)

			if batch and work_done:
				# save the group after having added all users.
				# This seems finer than saving between each addition.
				self.serialize()

				# FIXME: what to do if extensions *need* the group to
				# be written to disk and batch was True ?

		assert ltrace('locks', '  %s %s' % (LMC.groups.lock, LMC.users.lock))

		assert ltrace('groups', '< %s.add_Users()' % self.__name)
	def del_Users(self, users_to_del=None, batch=False):
		""" Delete a users list from the current group. """

		caller = current_thread().name

		assert ltrace('groups', '> %s: %s.del_Users(%s)' % (
								caller, self.__name,
								', '.join(user.login for user in users_to_del)))

		if users_to_del is None:
			raise exceptions.BadArgumentError(
						_(u'You must specify a users list'))

		# we need to lock users to be sure they don't dissapear during this phase.
		with nested(LMC.groups.lock, LMC.users.lock):

			work_done = False

			for user in users_to_del:

				if user.weakref in self.__members:

					L_event_run(InternalEvent('group_pre_del_user', self, user))

					self.__members.remove(user.weakref)

					# Update the user's reverse link.
					user.unlink_Group(self)

					if self.__is_helper:
						self.__standard_group()._cli_invalidate()
					else:
						self._cli_invalidate()

					logging.notice(_(u'Removed user {0} from members '
										u'of group {1}.').format(
											stylize(ST_LOGIN, user.login),
											stylize(ST_NAME, self.name)))

					if batch:
						work_done = True
					else:
						self.serialize()

					L_event_run(InternalEvent('group_post_del_user', self, user))

					# THINKING: shouldn't we turn this into an extension?
					L_service_enqueue(priorities.LOW,
									self.__del_group_symlink, user, batch=True)
				else:
					logging.info(_(u'Skipped user {0}, already not '
									u'a member of group {1}').format(
										stylize(ST_LOGIN, user.login),
										stylize(ST_NAME, self.name)))

			if batch and work_done:
				self.serialize()

		assert ltrace('groups', '< %s.del_Users()' % self.name)
	def link_User(self, user):
		""" This method is some sort of callback, called by the
			:class:`~licorn.core.users.User` instance when we first call its
			:meth:`~licorn.core.users.User.link_Group` method (the "add user in
			group" process always originates from the
			:class:`~licorn.core.groups.Group`. There is no ``unlink_User`
			method, because the group always know how to unlink a user from
			itself in the "del user from group" process. """
		if user.weakref not in self.__members:
			self.__members.append(user.weakref)
	def link_gidMember(self, user):
		if user.weakref not in self.__gidMembers:
			self.__gidMembers.append(user.weakref)
	def unlink_gidMember(self, user):
		self.__gidMembers.remove(user.weakref)
	def link_Profile(self, profile):
		if profile.weakref not in self.__profiles:
			self.__profiles.append(profile.weakref)
	def unlink_Profile(self, profile):
		self.__profiles.remove(profile.weakref)

	def move_to_backend(self, new_backend, force=False,
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
							u'exist or is not enabled.') % new_backend.name)

		old_backend = self.backend

		if old_backend.name == new_backend.name:
			logging.info(_(u'Skipped move of group {0}, '
				u'already stored in backend {1}.').format(
					stylize(ST_NAME, self.name),
					stylize(ST_NAME, new_backend)))
			return True

		if self.__is_system_restricted and not force:
			logging.warning(_(u'Skipped move of restricted system group {0} '
				u'(please use {1} if you really want to do this, '
				u'but it is strongly not recommended).').format(
					stylize(ST_NAME, self.name),
					stylize(ST_DEFAULT, '--force')))
			return

		if self.__is_helper and not internal_operation:
			raise exceptions.BadArgumentError(_(u'Cannot move an '
				u'associated system group without moving its standard '
				u'group too. Please move the standard group instead, '
				u'if this is what you meant.'))

		if self.__is_standard:

			if not self.responsible_group.move_to_backend(new_backend,
													internal_operation=True):
				logging.warning(_(u'Skipped move of group {0} to backend {1} '
					u'because move of associated responsible system group '
					u'failed.').format(self.name, new_backend))
				return

			if not self.guest_group.move_to_backend(new_backend,
													internal_operation=True):

				# pray this works, else we're in big trouble, a shoot in a
				# foot and a golden shoe on the other.
				self.responsible_group.move_to_backend(old_backend,
													internal_operation=True)

				logging.warning(_(u'Skipped move of group {0} to backend {1} '
					u'because move of associated system guest group '
					u'failed.').format(self.name, new_backend))
				return

		try:
			self.backend = new_backend
			self.serialize(backend_actions.CREATE)

		except KeyboardInterrupt, e:
			logging.warning(_(u'Exception {0} happened while trying to '
				u'move group {1} from {2} to {3}, aborting (group left '
				u'unchanged).').format(e, group_name, old_backend, new_backend))
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
					u'restore a stable situation during group {1} move, we '
					u'could be in big trouble.').format(e, self.name))
				print_exc()

			return False
		else:
			# the copy operation is successfull, make it a real move.
			old_backend.delete_Group(self.name)

			logging.notice(_(u'Moved group {0} from backend '
							u'{1} to {2}.').format(stylize(ST_NAME, self.name),
					stylize(ST_NAME, old_backend),
					stylize(ST_NAME, new_backend)))
			return True
	def check(self, minimal=True, force=False, batch=False, auto_answer=None, full_display=True):
		""" Check a group.
			Will verify the various needed
			conditions for a Licorn® group to be valid, and then check all
			entries in the shared group directory.

			PARTIALLY locked, because very long to run (depending on the shared
			group dir size). Harmless if the unlocked part fails.

			:param minimal: don't check member's symlinks to shared group dir if True
			:param force: not used directly in this method, but forwarded to called
				methods which can use it.
			:param batch: correct all errors without prompting.
			:param auto_answer: an eventual pre-typed answer to a preceding question
				asked outside of this method, forwarded to apply same answer to
				all questions.
		"""

		assert ltrace('groups', '> %s.check()' % stylize(ST_NAME, self.name))

		#NOTE: don't self.lock here, it would block the inotifier event dispatcher.

		if self.is_system:
			return self.__check_system_group(minimal, force,
											batch, auto_answer, full_display)
		else:
			return self.__check_standard_group(minimal, force,
											batch, auto_answer, full_display)
	def check_symlinks(self, oldname=None, delete=False,
						batch=False, auto_answer=None, *args, **kwargs):
		""" For each member of a group, verify member has a symlink to the
			shared group dir inside his home (or under level 2 directory). If
			not, create the link. Eventually delete links pointing to an old
			group name (if it is set).

			NOT locked because can be long, and harmless if fails.
		"""

		logging.progress(_(u'Checking %s symlinks in members homes, '
						u'this can be long…')  % stylize(ST_NAME, self.name))

		all_went_ok = True

		for user in self.__members:

			user = user()

			link_not_found = True

			if self.is_standard:
				link_basename = self.name

			elif self.__is_helper:
				link_basename = self.standard_group.name

			else:
				# symlinks at all for other type of system groups
				return

			link_src = os.path.join(LMC.configuration.groups.base_path,
									link_basename)

			if oldname is None:
				link_src_old = None
			else:
				link_src_old = os.path.join(LMC.configuration.groups.base_path,
								oldname)

			for link in fsapi.minifind(user.homeDirectory, maxdepth=2,
										type=stat.S_IFLNK):
				try:
					link_src_abs = os.path.abspath(os.readlink(link))

					if link_src_abs == link_src:
						if delete:
							try:
								os.unlink(link)

								logging.info(_(u'Deleted symlink %s.') %
												stylize(ST_LINK, link))
							except (IOError, OSError), e:
								if e.errno != 2:
									raise exceptions.LicornRuntimeError(
									_(u'Unable to delete symlink {0} '
										u'(was: {1}).').format(
										stylize(ST_LINK, link), e))
						else:
							link_not_found = False

				except (IOError, OSError), e:
					# TODO: verify there's no bug in this logic ? pida (my IDE)
					# signaled an error I didn't previously notice.
					if e.errno == 2 and link_src_old \
						and link_src_old == os.readlink(link):
						# delete links to old group name.
						os.unlink(link)
						logging.info(_(u'Deleted old symlink %s.') %
							stylize(ST_LINK, link))
					else:
						# errno == 2 is a broken link, don't bother.
						raise exceptions.LicornRuntimeError(_(u'Unable to '
							u'read symlink {0} (was: {1}).').format(
								link, str(e)))

			if link_not_found and not delete:

				link_dst = os.path.join(user.homeDirectory, link_basename)

				if batch or logging.ask_for_repair(_(u'User {0} lacks the '
								u'symlink to group shared dir {1}. '
								u'Create it?').format(
									stylize(ST_LOGIN, user.login),
									stylize(ST_NAME, link_basename)),
								auto_answer):

					fsapi.make_symlink(link_src, link_dst, batch=batch,
												auto_answer=auto_answer)
				else:
					logging.warning(_(u'User {0} lacks the '
								u'symlink to group shared dir {1}.').format(
									stylize(ST_LOGIN, user.login),
									stylize(ST_NAME, link_basename)))
					all_went_ok = False

		return all_went_ok

	# TODO: to be refreshed
	def AddGrantedProfiles(self, name=None, gid=None, users=None,
		profiles=None):
		""" Allow the users of the profiles given to access to the shared dir
			Warning: Don't give [] for profiles, but [""]
		"""

		raise NotImplementedError('to be refreshed.')

		# FIXME: with self.lock
		gid, name = self.resolve_gid_or_name(gid, name)

		# The profiles exist ? Delete bad profiles
		for p in profiles:
			if p in LMC.profiles:
				# Add the group in groups list of profiles
				if name in LMC.profiles[p]['memberGid']:
					logging.info(_(u'Group {0} already in the list '
						u'of profile {1}.').format(stylize(ST_NAME, name),
						stylize(ST_NAME, p)))
				else:
					controllers.profiles.AddGroupsInProfile([name])
					logging.notice(
						u"Added group %s in the groups list of profile %s." % (
						stylize(ST_NAME, name),
						stylize(ST_NAME, p)))
					# Add all 'p''s users in the group 'name'
					_users_to_add = self.__find_group_members(users,
						LMC.profiles[p]['groupName'])
					self.AddUsersInGroup(name, _users_to_add, users)
			else:
				logging.warning(u"Profile %s doesn't exist, ignored." %
					stylize(ST_NAME, p))

		# FIXME: is it needed to save() here ? isn't it already done by the
		# profile() and the AddUsersInGroup() calls ?
		LMC.backends[
			self.groups[gid]['backend']
			].save_Group(gid, backend_actions.UPDATE)
	def DeleteGrantedProfiles(self, name=None, gid=None, users=None,
		profiles=None):
		""" Disallow the users of the profiles given
			to access to the shared dir. """

		raise NotImplementedError('to be refreshed.')

		# FIXME: with self.lock
		gid, name = self.resolve_gid_or_name(gid, name)

		# The profiles exist ?
		for p in profiles:
			# Delete the group from groups list of profiles
			if name in controllers.profiles[p]['memberGid']:
				logging.progress(_(u'Deleting group {0} from '
					u'profile {1}.').format(stylize(ST_NAME, name),
						stylize(ST_NAME, p)))

				LMC.profiles.DeleteGroupsFromProfile([name])
				# Delete all 'p''s users from the group 'name'
				_users_to_del = self.__find_group_members(users,
					LMC.profiles[p]['groupName'])
				self.DeleteUsersFromGroup(name, _users_to_del, users)
			else:
				logging.info(_(u'Group {0} already absent from '
					u'profile {1}.').format(
					stylize(ST_NAME, name),
					stylize(ST_NAME, p)))

		# FIXME: not already done ??
		self.serialize()

	def _build_standard_home(self):
		return '%s/%s' % (LMC.configuration.groups.base_path, self.__name)
	def _build_system_home(self, ignored_value):
		""" A system group doesn't have a home. """
		return None
	def __resolve_permissive_state(self, permissive=None):
		""" If the shared group directory exists, return its current
			permissive state.

			It if doesn't, the result depends on the ``permissive``
			argument value:

			- if it's ``None`` (default value), we assume that the caller
			  really wanted to know the current permissive state of the
			  directory. There is thus a problem because the directory is
			  not here any more.

			- if it's anything other, return the argument: we are in creation
			  mode, and the abscence of the directory is normal, it is not
			  yet created. The argument will be used on creation to set the
			  initial permissive state.

			:param permissive: a boolean, which can be ``None`` (see above).
		"""

		with self.lock:

			if self.__is_system:
				# system groups don't handle the permisse attribute.
				return None

			try:
				# only check the default ACLs, where the permissiveness
				# is stored, as rwx (True) or r-x (False) for the group
				# standard members.
				for line in posix1e.ACL(filedef=self.__homeDirectory):
					if line.tag_type & posix1e.ACL_GROUP:
						if line.qualifier == self.__gidNumber:
							return line.permset.write

			except IOError, e:
				if e.errno == 13:
					raise exceptions.InsufficientPermissionsError(str(e))

				elif e.errno == 2:
					if permissive is None:
						# if permissive is None, we assume that the caller
						# wanted to know the permissive state, thus there
						# is a problem.
						logging.warning(_(u'Shared dir {0} does not exist, '
							u'please run "chk group {1}" to fix.').format(
								stylize(ST_PATH, self.__homeDirectory),
								stylize(ST_NAME, self.__name)))
					else:
						# if given an argument, we assume the caller was
						# in group creation context, thus the non existing
						# directory is normal: it will be created shortly
						# after. Return the given argument, which must be
						# stored in group attributes: it will be used during
						# the directory creation to assign the wanted
						# permissive state.
						return permissive
				else:
					raise e
	def __check_mutual_exclusions(self, user, force):
		""" Verify a given user is not a member of two or more groups, from
			the tuple (group, resp_group, guest_group).

			In some cases, this is not a problem and user will be promoted
			from one group to another automatically.

			In other cases, the demotion can't be done without the
			:option:`--force` argument.
		"""

		if self.__is_system:
			if self.__is_responsible:

				if user in self.__standard_group().members:
					# we are promoting a standard member to
					# responsible, no need to --force. Simply
					# delete from standard group first, to
					# avoid ACLs conflicts.
					self.standard_group.del_Users([ user ])

				elif user in self.__guest_group().members:
					# Trying to promote a guest to responsible,
					# just delete him/her from guest group
					# to avoid ACLs conflicts.

					self.__guest_group().del_Users([ user ])

			elif self.__is_guest:

				if user in self.__standard_group().members:
					# user is standard member, we need to demote
					# him/her, thus need the --force flag.

					if force:
						# demote user from std to gst
						self.__standard_group().del_Users([ user ])
					else:
						raise exceptions.BadArgumentError(_(u'Cannot demote '
								u'user %s from standard membership to guest '
								u'without --force flag.') %
									stylize(ST_LOGIN, user.login))

				elif user in self.__responsible_group().members:
					# user is currently responsible. Demoting
					# to guest is an unusual situation, we need
					# to --force.

					if force:
						# demote user from rsp to gst
						self.__responsible_group().del_Users([ user ])
					else:
						raise exceptions.BadArgumentError(_(u'Cannot demote '
							u'user %s from responsible to guest without '
							u'--force flag.') %
									stylize(ST_LOGIN, user.login))

			#else:
			# this is a system group, but not affialiated to
			# any standard group, thus no particular condition
			# applies: nothing to do.

		else:
			# standard group, check rsp & gst memberships

			if user in self.__guest_group().members:
				# we are promoting a guest to standard
				# membership, no need to --force. Simply
				# delete from guest group first, to
				# avoid ACLs conflicts.
				self.__guest_group().del_Users([ user ])

			elif user in self.__responsible_group().members:
				# we are trying to demote a responsible to
				# standard membership, we need to --force.

				if force:
					# --force is given: demote user!
					# Delete the user from standard group to
					# avoid ACLs conflicts.

					self.__responsible_group().del_Users([ user ])
				else:
					raise exceptions.BadArgumentError(_(u'Cannot demote user '
						u'%s from responsible to standard membership without '
						u'--force flag.') %
								stylize(ST_LOGIN, user.login))
			#else:
			#
			# user is not a guest or responsible of the group,
			# just a brand new member. Nothing to check.
		assert ltrace('groups', ' | %s.__check_mutual_exclusions() → %s' % (
				self.name, stylize(ST_OK, 'OK')))
	def check_associated_groups(self, minimal=True, force=False,
							batch=False, auto_answer=None, full_display=True):
		"""	Check the system groups that a standard group needs to be valid.
			For
			example, a group "MountainBoard" needs 2 system groups,
			rsp-MountainBoard and gst-MountainBoard for its ACLs on the group
			shared dir.

			NOT locked because called from already locked methods.

			:param name:
			:param gid: the standard group to verify depended upon system groups.
			:param minimal: if True, only the system groups are checked. Else,
							symlinks in the homes of standard group members and
							responsibles are also checked (can be long,
							depending on the number of members).
			:param batch: correct all errors without prompting.
			:param auto_answer: an eventual pre-typed answer to a preceding
								question asked outside of this method, forwarded
								to apply same answer to all questions.
			:param force: not used directly in this method, but forwarded to
							called methods which can use it.
		"""

		all_went_ok = True

		if not self.__is_standard:
			return

		with self.lock:

			for (group_ref, attrname, prefix, title) in (
				(self.__responsible_group, 'responsible_group',
					LMC.configuration.groups.resp_prefix,
					_(u'responsibles')),
				(self.__guest_group, 'guest_group',
					LMC.configuration.groups.guest_prefix,
					_(u'guests'))
				):

				group_name = prefix + self.__name

				if full_display:
					logging.progress(_(u'Checking system group %s…') %
												stylize(ST_NAME, group_name))

				if group_ref is None:
					if batch or logging.ask_for_repair(_(u'The system group '
									u'{0} is required for the group {1} to be '
									u'fully operationnal. Create it?').format(
										stylize(ST_NAME, group_name),
										stylize(ST_NAME, self.__name)),
									auto_answer):

						try:
							# create the missing group
							group = self.controller.add_Group(
											name=group_name,
											system=True,
											description=_(u'{0} of group '
												u'“{1}”').format(
													title.title(), self.name),
											backend=self.backend,
											batch=batch,
											force=force)

							# connect it one way, the low-level way.
							setattr(self, attrname, group)

							# connect it the other way.
							group.standard_group = self

							# if the home dir or helper groups get corrected,
							# we need to update the CLI view.
							self._cli_invalidate()

							#logging.notice(_(u'Created system group {0}'
							#	'(gid={1}).').format(
							#		stylize(ST_NAME, group.name),
							#		stylize(ST_UGID, group.gid)))

						except exceptions.AlreadyExistsException, e:
							logging.warning(e)
							print_exc()
					else:
						logging.warning(_(u'The system group '
									u'{0} is required for the group {1} to be '
									u'fully operationnal.').format(
										stylize(ST_NAME, group_name),
										stylize(ST_NAME, self.__name)))
						all_went_ok &= False
				else:
					if not minimal:
						all_went_ok &= group_ref().check_symlinks(
														batch=batch,
														auto_answer=auto_answer)
			# cross-link everyone.
			self.__responsible_group().guest_group = self.__guest_group()
			self.__guest_group().responsible_group = self.__responsible_group()

		return all_went_ok
	def __check_system_group(self, minimal=True, force=False,
							batch=False, auto_answer=None, full_display=True):
		""" Check superflous and mandatory attributes of a system group. """

		assert ltrace(self.name, '| %s.__check_system_group()' % self.name)

		all_went_ok = True

		logging.progress(_(u'Checking system specific attributes '
				u'for group {0}…').format(stylize(ST_NAME, self.name))
			)

		update = False

		# any system group should not have a skel, this is particularly useless.
		if hasattr(self, '__groupSkel') and self.__groupSkel != '':
			update = True
			del self.__groupSkel

			logging.info(_(u'Removed superfluous attribute {0} '
							u'of system group {1}').format(
								stylize(ST_ATTR, 'groupSkel'),
								stylize(ST_NAME, self.name))
				)
		# Licorn® system groups should have at least a default description.
		# restricted system groups are not enforced on that point.
		if not self.__is_system_restricted:
			if not hasattr(self, 'description') or self.description == '':
				update = True
				self.description = _('Members of group “%s”') % self.name

				logging.info(_(u'Added missing {0} attribute with a '
								u'default value for system group {1}.').format(
									stylize(ST_ATTR, 'description'),
									stylize(ST_NAME, self.name))
					)

		if update:
			if batch or logging.ask_for_repair(_(u'Do you want to commit '
				u'these changes to the system (highly recommended)?'),
				auto_answer=auto_answer):

				self.serialize()
				self._cli_invalidate()

				return True
			else:
				logging.warning(_(u'Corrections of system group '
					u'{0} not commited').format(self.name))
				return False
		return True

	# alias CoreFSUnitObject methods to us
	__check_standard_group          = CoreFSUnitObject._standard_check
	_pre_standard_check_method      = check_associated_groups
	_extended_standard_check_method = check_symlinks

	def __add_group_symlink(self, user, batch=False, auto_answer=None):
		""" Create a symlink to the group shared dir in the user's home. """

		if self.is_standard:
			link_basename = self.__name

		elif self.__is_helper:
			link_basename = self.standard_group.name

		else:
			return

		assert ltrace('groups',
					'| %s.__add_group_symlink(%s)' % (self.name, user.login))

		link_src = os.path.join(LMC.configuration.groups.base_path,
								link_basename)

		link_dst = os.path.join(user.homeDirectory, link_basename)

		try:
			fsapi.make_symlink(link_src, link_dst, batch=batch)

		except Exception, e:
			raise exceptions.LicornRuntimeError(_(u'Unable to create symlink '
												u'{0} (was: {1}).').format(
												stylize(ST_LINK, link_dst), e))
	def __del_group_symlink(self, user, batch=False, auto_answer=None):
		""" Remove the group symlink from the user's home. Exactly, from
			anywhere in the user's home (with maxdepth=2 limitation). """

		if self.is_standard:
			# delete the symlink to the shared group dir
			# in the user's home dir.
			link_basename = self.__name

		elif self.__is_helper:
			link_basename = self.standard_group.name

		else:
			return

		assert ltrace('groups',
					'| %s.__del_group_symlink(%s)' % (self.name, user.login))

		link_src = os.path.join(LMC.configuration.groups.base_path,
								link_basename)

		for link in fsapi.minifind(user.homeDirectory,
									maxdepth=2, type=stat.S_IFLNK):
			try:
				if os.path.abspath(os.readlink(link)) == link_src:
					os.unlink(link)

					logging.info(_(u'Deleted symlink %s.') %
													stylize(ST_LINK, link))
			except (IOError, OSError), e:
				if e.errno != 2:
					raise exceptions.LicornRuntimeError(_(u'Unable to delete '
										u'symlink {0} (was: {1}).').format(
											stylize(ST_LINK, link), e))

	def _cli_get(self, long_output=False, no_colors=False):
		""" FIXME: make long_output a dedicated precalc variable... """
		try:
			return self.__cg_precalc_full
		except AttributeError:

			# NOTE: 5 = len(str(65535)) == len(max_uid) == len(max_gid)
			label_width    = Group._cw_name
			align_space    = ' ' * (label_width + 2)
			gid_label_rest = 5 - len(str(self.__gidNumber))

			accountdata = [ '{group_name}: ✎{gid} {backend}	'
								'{descr}'.format(
								group_name=stylize(
									Group._permissive_colors[self.__permissive]
										if self.is_standard
										else (ST_COMMENT
											if self.__is_privilege
											else ST_NAME),
									self.__name.rjust(label_width)),
								#id_type=_(u'gid='),
								gid='%s%s' % (
									stylize(ST_UGID, self.__gidNumber),
									' ' * gid_label_rest),
								backend=stylize(ST_BACKEND, self.backend.name),
								descr= stylize(ST_COMMENT, self.__description)
									if self.__description != '' else '') ]

			if long_output:
				if hasattr(self, '__userPassword'):
					accountdata.append(_(u'password:').rjust(label_width)
								+ ' ' + self.__userPassword)

				if self.is_standard:
					accountdata.append(stylize(ST_EMPTY, _(u'skel:').rjust(label_width))
							+ ' ' + self.__groupSkel)

					if no_colors:
						# if --no-colors is set, we have to display if the group
						# is permissive or not in real words, else user don't get
						# the information because normally it is encoded simply with
						# colors..
						if self.__is_permissive is None:
							accountdata.append(_(u"UNKNOWN"))
						elif self.__is_permissive:
							accountdata.append(_(u"permissive"))
						else:
							accountdata.append(_(u"NOT permissive"))

				if len(self.__members) > 0:
					accountdata.append('%s%s' % (
						align_space,
						', '.join((user()._cli_get_small()
							for user in self.__members))))
				else:
					accountdata.append('%s%s' % (
						align_space,
						stylize(ST_EMPTY, _(u'— no member —'))))
			else:
				if self.__is_standard:

					members = []
					try:
						members.extend([ (user.login, '%s%s' % (
									stylize(ST_COMMENT, '✍'),
									user._cli_get_small()))
									for user in self.__responsible_group().members ])
					except Exception, e:
						logging.warning(_(u'Cannot collect responsibles '
							u'for group {0} (was: {1}).').format(self.name, e))

					try:
						members.extend([ (user.login, '%s%s' % (
									stylize(ST_BAD, '×'),
									user._cli_get_small()))
									for user in self.__guest_group().members ])
					except Exception, e:
						logging.warning(_(u'Cannot collect guests '
							u'for group {0} (was: {1}).').format(self.name, e))

					members.extend([ (user.login, user._cli_get_small())
								for user in self.members if user ])

					if len(members) > 0:
						accountdata.append('%s%s' % (
							align_space,
							', '.join(user for login, user in sorted(members))))
					else:
						accountdata.append('%s%s' % (
							align_space,
							stylize(ST_EMPTY, _(u'— no member —'))))

				elif self.__is_helper:
					# resps and guest are combined with the std group, don't
					# display them at all.
					return ''
				else:
					if len(self.__members) > 0:
						accountdata.append('%s%s' % (
							align_space,
							', '.join((user._cli_get_small()
								for user in sorted(self.members,
									key=attrgetter('login'))))))
					else:
						accountdata.append('%s%s' % (
							align_space,
							stylize(ST_EMPTY, _(u'— no member —'))))

			self.__cg_precalc_full = '\n'.join(accountdata)
			return self.__cg_precalc_full
	def _cli_get_small(self):

		try:
			return self.__cg_precalc_small
		except AttributeError:

			is_priv = self.is_privilege

			if self.__is_helper:
				self.__cg_precalc_small = '%s%s(%s)' % (
					stylize(ST_COMMENT, '✍') if self.is_responsible
						else stylize(ST_BAD, '×'),
					stylize(
						Group._permissive_colors[self.standard_group.is_permissive],
						self.standard_group.name),
					stylize(ST_UGID, self.standard_group.gid))
			else:
				self.__cg_precalc_small = '%s(%s)' % (
					stylize(Group._permissive_colors[self.__permissive]
						if self.is_standard
						else (ST_COMMENT if is_priv else ST_NAME)
						, '%s%s' % ('⚑' if is_priv else '', self.__name)),
					stylize(ST_UGID, self.__gidNumber))
			return self.__cg_precalc_small
	def to_XML(self, selected=None, long_output=False):
		""" Export the groups list to XML. """

		with self.lock:
			return '''		<group>
			<name>%s</name>
			<gidNumber>%s</gidNumber>
			<userPassword>%s</userPassword>
			<description>%s</description>
			<permissive>%s</permissive>
			%s
			<memberUid>%s</memberUid>
			<backend>%s</backend>
		</group>''' % (
				self.__name,
				self.__gidNumber,
				self.__userPassword,
				self.__description,
				self.__permissive,
				'' if self.__is_system
					else '		<groupSkel>%s</groupSkel>\n' % self.__groupSkel,
				','.join(x().login for x in self.__members),
				self.backend.name
				)
	def to_JSON(self):
		#print self._members
		if hasattr(self, '_members'):
			members = '[%s]' % '"%s"' if self._members is not [] else '' % '","'.join(x().login for x in self.__members)
		else:
			members = ''
		return ('{"name" : "%s", '
			'"gidNumber" : "%s", '
			'"userPassword" : "%s", '
			'"description" : "%s", '
			'"permissive" : "%s", '
			'"groupSkel" : "%s", '
			'"memberUid" : "%s", '
			'"backend" : "%s", '
			'"is_priv" : "%s", '
			'"is_system" : "%s", '
			'"search_fields": [ "name", "gidNumber", "description", "permissive", "groupSkel"] }' % (
					self.__name,
					self.__gidNumber,
					self.__userPassword,
					self.__description,
					self.__permissive,
					'' if self.__is_system else self.__groupSkel,
					members,
					self.backend.name,
					self.__is_privilege,
					self.__is_system
				))
	def _wmi_protected(self, complete=True):
		""" return true if the current group must not be used/modified in WMI. """

		# FIXME: isn't this meant to be exactly the opposite?
		if complete:
			return self.__is_system and not self.__is_helper
		else:
			return self.__is_system and not self.__is_helper and not self.__is_privilege

class GroupsController(Singleton, CoreFSController):
	""" Manages the groups and the associated shared data on a Linux system.
	"""

	init_ok = False
	load_ok = False

	#: used in RWI.
	@property
	def object_type_str(self):
		return _(u'group')
	@property
	def object_id_str(self):
		return _(u'GID')
	@property
	def sort_key(self):
		""" The key (attribute or property) used to sort
			User objects from RWI.select(). """
		return 'name'

	def __init__ (self, warnings=True):

		assert ltrace('groups', '> GroupsController.__init__(%s)' %
			GroupsController.init_ok)

		if GroupsController.init_ok:
			return

		CoreFSController.__init__(self, 'groups')

		GroupsController.init_ok = True
		assert ltrace('groups', '< GroupsController.__init__(%s)' %
			GroupsController.init_ok)
	def by_name(self, name):
		return Group.by_name[name]()
	@property
	def names(self):
		return (name for name in Group.by_name)
	def word_match(self, word):
		return hlstr.multi_word_match(word, self.names)
	def by_gid(self, gid):
		# we need to be sure we get an int(), because the 'gid' comes from RWI
		# and is often a string.
		return self[int(gid)]
	def load(self):
		if GroupsController.load_ok:
			return

		assert ltrace('groups', '| load()')

		# be sure our depency is OK.
		LMC.users.load()

		L_event_run(InternalEvent('groups_loading', groups=self))

		# call the generic reload() method, but silently: this will avoid the
		# rest of the program believe we are reloading, which is not really the
		# case.
		self.reload(send_event=False)

		L_event_run(InternalEvent('groups_loaded', groups=self))

		GroupsController.load_ok = True
	def reload(self, send_event=True):
		""" load or reload internal data structures from backends data. """

		assert ltrace('groups', '| reload()')

		if send_event:
			L_event_run(InternalEvent('groups_reloading', groups=self))

		# lock users too, because we feed the members cache inside.
		with nested(self.lock, LMC.users.lock):
			for backend in self.backends:
				for gid, group in backend.load_Groups():
					self[gid] = group

			self.__connect_groups()
			self.__connect_users()

		if send_event:
			L_event_run(InternalEvent('groups_reloaded', groups=self))
	def reload_backend(self, backend):
		""" reload only one backend contents (used from inotifier). """

		assert ltrace('groups', '| reload_backend(%s)' % backend.name)
		assert ltrace('locks', '| locks %s %s' % (self.lock, LMC.users.lock))

		# lock users too, because we feed the members cache inside.
		with nested(self.lock, LMC.users.lock):

			loaded = []

			for gid, group in backend.load_Groups():
				if gid in self:
					logging.progress(_(u'{0}.reload: Overwritten gid {1}.').format(
							stylize(ST_NAME, self.name), gid))

				self[gid] = group
				loaded.append(gid)

			for gid, group in self.items():
				if group.backend.name == backend.name:
					if gid in loaded:
						loaded.remove(gid)

					else:
						logging.progress(_(u'{0}: removing disapeared group '
							u'{1}.').format(stylize(ST_NAME, self.name),
								stylize(ST_NAME, group.name)))

						self.del_Group(group, batch=True, force=True)

			self.__connect_groups()
			self.__connect_users(clear_first=True)

		assert ltrace('locks', '| locks %s %s' % (self.lock, LMC.users.lock))

		# we need to reload them, as they connect groups to them.
		LMC.privileges.reload()
		LMC.profiles.reload()
	def get_hidden_state(self):
		""" See if /home/groups is readable or not. """

		groups_home = LMC.configuration.groups.base_path

		try:
			users_gid = self.name_to_gid(LMC.configuration.users.group)

		except (AttributeError, KeyError):
			# we got AttributeError because by_name() fails,
			# because controller has not yet loaded any data. Get
			# the needed information by another mean.
			#
			# FIXME: verify this is still needed.
			import grp
			users_gid = grp.getgrnam(
						LMC.configuration.users.group).gr_gid
		try:

			for line in posix1e.ACL(file=groups_home):
				if line.tag_type & posix1e.ACL_GROUP:
						if line.qualifier == users_gid:
							return not line.permset.read

		except exceptions.DoesntExistException:
			# the group "users" doesn't exist, or is not yet created.
			return None
		except (IOError, OSError), e:
			if e.errno == 95:
				raise exceptions.LicornRuntimeError(_(u'File-system {0} must '
					u'be mounted with {1} option to continue!').format(
						stylize(ST_PATH, LMC.configuration.home_base_path),
						stylize(ST_ATTR, 'acl')))

			elif e.errno == 2:
				# /home/groups doesn't exist. At the very first launch of the
				# licorn daemon, this error is perfectly normal: the
				# directory will be created later. We cannot do it now because
				# GroupsController is not yet loaded, and calling
				# LMC.configuration.check_base_dirs(batch=True) would thus
				# fail. Just return the default hidden_state value, which will
				# in turn we used when the directory is created.
				logging.warning2(_(u'{0}: {1} does not exist and will be '
					u'created later in the process.').format(
						stylize(ST_NAME, self.name),
						stylize(ST_PATH, groups_home)))
				return LMC.configuration.groups.hidden_default

			else:
				raise
	def serialize(self, group=None):
		""" Save internal data structure to backends. """

		assert ltrace('groups', '> serialize(%s)' % group)

		with self.lock:
			if group:
				group.serialize()

			else:
				for backend in self.backends:
					backend.save_Groups(self)

		assert ltrace('groups', '< serialize()')
	def select(self, filter_string):
		""" Filter group accounts on different criteria.
		"""

		filtered_groups = []

		assert ltrace('groups', '> Select(%s)' % filter_string)

		with self.lock:
			if filters.NONE == filter_string:
				filtered_groups = []

			elif type(filter_string) == type([]):
				filtered_groups = filter_string

			elif filters.ALL == filter_string:
				assert ltrace('groups', '> Select(ALL:%s/%s)' % (
					filters.ALL, filter_string))

				filtered_groups = self.values()

			elif filters.STANDARD == filter_string:
				assert ltrace('groups', '> Select(STD:%s/%s)' % (
					filters.STD, filter_string))

				filtered_groups.extend(group for group in self
														if group.is_standard)

			elif filters.EMPTY == filter_string:
				assert ltrace('groups', '> Select(EMPTY:%s/%s)' % (
					filters.EMPTY, filter_string))

				filtered_groups.extend(group for group in self
															if group.is_empty)

			elif filters.SYSTEM & filter_string:

				if filters.GUEST == filter_string:
					assert ltrace('groups', '> Select(GST:%s/%s)' % (
						filters.GST, filter_string))

					filtered_groups.extend(group for group in self
															if group.is_guest)

				elif filters.NOT_GUEST == filter_string:
					assert ltrace('groups', '> Select(GST:%s/%s)' % (
						filters.NOT_GST, filter_string))

					filtered_groups.extend(group for group in self
													if not group.is_guest)

				elif filters.SYSTEM_RESTRICTED == filter_string:
					assert ltrace('groups', '> Select(SYSTEM_RESTRICTED:%s/%s)' % (
						filters.SYSTEM_RESTRICTED, filter_string))

					filtered_groups.extend(group for group in self
												if group.is_system_restricted)

				elif filters.SYSTEM_UNRESTRICTED == filter_string:
					assert ltrace('groups', '> Select(SYSTEM_UNRESTRICTED:%s/%s)' % (
						filters.SYSTEM_UNRESTRICTED, filter_string))

					filtered_groups.extend(group for group in self
										if group.is_system_unrestricted)

				elif filters.RESPONSIBLE == filter_string:
					assert ltrace('groups', '> Select(RSP:%s/%s)' % (
						filters.RSP, filter_string))

					filtered_groups.extend(group for group in self
												if group.is_responsible)

				elif filters.NOT_RESPONSIBLE == filter_string:
					assert ltrace('groups', '> Select(RSP:%s/%s)' % (
						filters.NOT_RSP, filter_string))

					filtered_groups.extend(group for group in self
												if not group.is_responsible)

				elif filters.PRIVILEGED == filter_string:
					assert ltrace('groups', '> Select(PRI:%s/%s)' % (
						filters.PRI, filter_string))

					filtered_groups.extend([ group for group in self
													if group.is_privilege ])

				elif filters.NOT_PRIVILEGED == filter_string:
					assert ltrace('groups', '> Select(PRI:%s/%s)' % (
						filters.NOT_PRI, filter_string))

					filtered_groups.extend([ group for group in self
												if not group.is_privilege ])

				else:
					assert ltrace('groups', '> Select(SYS:%s/%s)' % (
						filters.SYS, filter_string))

					filtered_groups.extend([ group for group in self
														if group.is_system ])

			elif filters.NOT_SYSTEM == filter_string:
				assert ltrace('groups', '> Select(PRI:%s/%s)' % (
					filters.NOT_SYS, filter_string))
				filtered_groups.extend(group for group in self if group.is_standard)

			else:
				gid_re    = re.compile("^gid=(?P<gid>\d+)")
				gid_match = gid_re.match(filter_string)
				if gid_match is not None:
					gid = int(gid_match.group('gid'))
					if gid in self.iterkeys():
						filtered_groups.append(gid)
					else:
						raise exceptions.DoesntExistException(_(u'GID %s does '
							u'not exist on the system.') % gid)

		assert ltrace('groups', '< Select(%s)' % filtered_groups)
		return filtered_groups
	def dump(self):
		""" Dump the internal data structures (debug and development use). """

		with self.lock:

			assert ltrace('groups', '| dump()')

			data = ''

			for group in sorted(self):
				data += str(group)

			return data
	def to_XML(self, selected=None, long_output=False):
		""" Export the groups list to XML. """

		with self.lock:
			if selected is None:
				groups = self
			else:
				groups = selected

			assert ltrace('groups', '| to_XML(%s)' % ','.join(
											group.name for group in groups))

		return (u'<?xml version="1.0" encoding="UTF-8"?>\n'
				u'<groups-list>\n'
				u'%s\n'
				u'</groups-list>\n') % u'\n'.join(
						group.to_XML() for group in groups)

	def to_JSON(self, selected=None):
		""" Export the user accounts list to XML. """

		with self.lock:
			if selected is None:
				groups = self
			else:
				groups = selected

			assert ltrace('groups', '| to_JSON(%r)' % groups)

			return '[ %s ]' % ','.join(group.to_JSON() for group in groups)
	def _validate_fields(self, name, description, groupSkel):
		""" apply sane tests on AddGroup needed arguments. """
		if name is None:
			raise exceptions.BadArgumentError(u"You must specify a group name.")

		if not hlstr.cregex['group_name'].match(name):
			raise exceptions.BadArgumentError(_(u'Malformed group name "{0}", '
				u'must match /{1}/i.').format(stylize(ST_NAME, name),
				stylize(ST_REGEX, hlstr.regex['group_name'])))

		if len(name) > LMC.configuration.groups.name_maxlenght:
			raise exceptions.LicornRuntimeError(_(u'Group name must be '
				u'smaller than {0} characters ("{1}" is {2} chars '
				u'long).').format(
					stylize(ST_ATTR, LMC.configuration.groups.name_maxlenght),
					stylize(ST_NAME, name), stylize(ST_BAD, len(name))))

		if description is None:
			description = _(u'Members of group “%s”') % name

		elif not hlstr.cregex['description'].match(description):
			raise exceptions.BadArgumentError(_(u'Malformed group description '
				u'"{0}", must match /{1}/i.').format(
					stylize(ST_COMMENT, description),
					stylize(ST_REGEX, hlstr.regex['description'])))

		if groupSkel is None:
			groupSkel = LMC.configuration.users.default_skel

		elif groupSkel not in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError(_(u'Invalid skel {0}. Valid '
				u'skels are: {1}.').format(stylize(ST_BAD, skel),
					', '.join(stylize(ST_PATH, x)
						for x in LMC.configuration.users.skels)))

		return name, description, groupSkel
	def add_Group(self, name, desired_gid=None, system=False, permissive=False,
											description=None, groupSkel=None,
											backend=None, users_to_add=None,
											batch=False, force=False,
											async=True):
		""" Add a Licorn group (the group + the guest/responsible group +
			the shared dir + permissions (ACL)). """

		assert ltrace('groups', '''> AddGroup(name=%s, system=%s, gid=%s, '''
			'''descr=%s, skel=%s, perm=%s)''' % (name, system, desired_gid,
				description, groupSkel, permissive))

		with self.lock:
			name, description, groupSkel = self._validate_fields(name,
													description, groupSkel)
			try:
				not_already_exists = True

				group = self.__add_group(name,
					manual_gid=desired_gid,
					system=system,
					description=description,
					groupSkel=groupSkel,
					permissive=permissive,
					backend=backend, batch=batch, force=force)

			except exceptions.AlreadyExistsException, e:
				# don't bork if the group already exists, just continue.
				# some things could be missing (resp- , guest- , shared dir or
				# ACLs), it is a good idea to verify everything is really OK by
				# continuing the creation procedure.
				logging.notice(str(e))
				group = self.by_name(name)
				not_already_exists = False

		# LOCKS: can be released, because everything after now is FS operations,
		# not needing the internal data structures. It can fail if someone
		# delete a group during the CheckGroups() phase (a little later in this
		# method), but this will be harmless.

		if system:
			if not_already_exists:

				if group.is_helper:
					log = logging.info
				else:
					log = logging.notice

				log(_(u'Created system group {0} '
					u'(gid={1}).').format(stylize(ST_NAME, name),
						stylize(ST_UGID, group.gid)))

			if users_to_add:
				group.add_Users(users_to_add)

			# system groups don't have shared group dir nor resp-
			# nor guest- nor special ACLs. We stop here.
			assert ltrace('groups', '< AddGroup(name=%s,gid=%d)' % (
							group.name, group.gid))
			return group

		# create group home dir and helper system groups.
		group.check(minimal=True, batch=True, force=force)

		if not_already_exists:
			group._inotifier_add_watch(self.licornd)

			logging.notice(_(u'Created {0} group {1} (gid={2}).').format(
								stylize(ST_OK, _(u'permissive'))
								if permissive else
								stylize(ST_BAD, _(u'not permissive')),
								stylize(ST_NAME, group.name),
								stylize(ST_UGID, group.gid)))

		if users_to_add:
			group.add_Users(users_to_add)

		assert ltrace('groups', '< AddGroup(%s): gid %d' % (
									group.name, group.gid))

		return group
	def __add_group(self, name, manual_gid=None, system=False, description=None,
						groupSkel=None, permissive=None, backend=None,
						batch=False, force=False):
		""" Add a POSIX group, write the system data files.
			Return the gid of the group created. """

		# LOCKS: No need to use self.lock, already encapsulated in AddGroup().

		assert ltrace('groups', '''> __add_group(name=%s, system=%s, gid=%s, '''
			'''descr=%s, skel=%s)''' % (name, system, manual_gid, description,
				groupSkel)
			)

		# first verify if GID is not already taken.
		if manual_gid in self.iterkeys():
			raise exceptions.AlreadyExistsError(_(u'GID {0} is already taken '
				u'by group {1}. Please choose another one.').format(
					stylize(ST_UGID, manual_gid),
					stylize(ST_NAME, self[manual_gid].name)))

		# Then verify if the name is not taken too.
		try:
			existing_group = self.by_name(name)

			if manual_gid is None:
				# automatic GID selection upon creation.
				if system and existing_group.is_system \
					or not system and existing_group.is_standard:
					raise exceptions.AlreadyExistsException(_(u'The group %s '
						u'already exists.') % stylize(ST_NAME, name))
				else:
					raise exceptions.AlreadyExistsError(_(u'The group %s '
						u'already exists but has not the same type. Please '
						u'choose another name for your group.') %
							stylize(ST_NAME, name))
			else:
				assert ltrace('groups', 'manual GID %d specified.' % manual_gid)

				# user has manually specified a GID to affect upon creation.
				if system and existing_group.is_system:
					if existing_group.gid == manual_gid:
						raise exceptions.AlreadyExistsException(_(u'The group '
							u'%s already exists.') % stylize(ST_NAME, name))
					else:
						raise exceptions.AlreadyExistsError(_(u'The group %s '
							u'already exists with a different GID. Please '
							u'check this is what you want, and make a decision.')
							% stylize(ST_NAME, name))
				else:
					raise exceptions.AlreadyExistsError(_(u'The group {0} '
						u'already exists but has not the same type. Please '
						u'choose another name for your group.').format(
							stylize(ST_NAME, name)))
		except KeyError:
			# name doesn't exist, path is clear.
			pass

		if (LMC.configuration.distro in (distros.UBUNTU, distros.LICORN)
			and LMC.configuration.distro_version < 9.04) or (
			LMC.configuration.distro == distros.DEBIAN and
			LMC.configuration.distro_version < 4.0):
			# Due to a bug of adduser perl script, we must check that there is
			# no user which has 'name' as login. For details, see
			# https://launchpad.net/distros/ubuntu/+source/adduser/+bug/45970
			if LMC.users.login_cache.has_key(name) and not force:
				raise exceptions.UpstreamBugException(_(u'A user account called '
					u'%s already exists, this could trigger a bug in the '
					u'Debian/Ubuntu adduser code when deleting the user. '
					u'Please choose another name for your group, or use the '
					u'--force argument if you really want to add this group '
					u'on the system.') % stylize(ST_NAME, name))

		# Find a new GID
		if manual_gid is None:
			if system:
				gid = pyutils.next_free(self.keys(),
					LMC.configuration.groups.system_gid_min,
					LMC.configuration.groups.system_gid_max)
			else:
				gid = pyutils.next_free(self.keys(),
					LMC.configuration.groups.gid_min,
					LMC.configuration.groups.gid_max)

			logging.progress(_(u'Autogenerated GID for group {0}: {1}.').format(
				stylize(ST_LOGIN, name), stylize(ST_UGID, gid)))
		else:
			if (system and Group.is_system_gid(manual_gid)) or (
						not system and Group.is_standard_gid(manual_gid)):
				gid = manual_gid
			else:
				raise exceptions.BadArgumentError(_(u'GID out of range '
					u'for the kind of group you specified. System GIDs '
					u'must be between {0} and {1}, standard GIDs must be '
					u'between {2} and {3}.').format(
						LMC.configuration.groups.system_gid_min,
						LMC.configuration.groups.system_gid_max,
						LMC.configuration.groups.gid_min,
						LMC.configuration.groups.gid_max))

		L_event_run(InternalEvent('group_pre_add', gid=manual_gid,
										name=name,
										system=system,
										description=description))

		assert ltrace('groups', '  __add_group in data structures: %s / %s' % (
																	gid, name))

		group = self[gid] = Group(gid, name,
						description=description,
						groupSkel=None
							if system else groupSkel,
						permissive=permissive,
						userPassword='x',
						backend=self._prefered_backend
							if backend is None else backend)

		# calling this *before* backend serialization ensures that:
		#	- helper groups will be created and serialized *before*
		#	- and thus, internal double-links are OK before we call the
		#		extensions post-add hooks.
		group.check_associated_groups(batch=True)

		# do not skip the write/save part, else future actions could fail. E.g.
		# when creating a group, skipping save() on rsp/gst group creation will
		# result in unaplicable ACLs because of (yet) non-existing groups in the
		# system files (or backends).
		# DO NOT UNCOMMENT: -- if not batch:
		group.serialize(backend_actions.CREATE)

		L_event_run(InternalEvent('group_post_add', group))

		assert ltrace('groups', '< __add_group(%s): gid %d.'% (name, gid))

		return group
	def del_Group(self, group, del_users=False, no_archive=False, force=False,
										check_profiles=True, batch=False):
		""" Delete a Licorn® group. """

		assert ltrace('groups', '| del_Group(%s,%s)' % (group.name, group.gid))
		assert ltrace('locks',  '> del_Group: %s %s %s' % (self.lock, LMC.privileges.lock, LMC.users.lock))

		# lock everything we *eventually* need, to be sure there are no errors.
		with nested(self.lock, LMC.privileges.lock, LMC.users.lock):

			if check_profiles and group.gid in LMC.profiles.iterkeys():
				raise exceptions.BadArgumentError(_(u'Cannot delete '
					u'group {0}, currently primary group of profile '
					u'{1}. Please delete the profile instead, and the '
					u'group will be deleted at the same time.').format(
					stylize(ST_NAME, group.name),
					stylize(ST_NAME, LMC.profiles.group_to_name(group.name))
					))

			prim_memb = group.primary_members

			if prim_memb != [] and not del_users:
				raise exceptions.BadArgumentError(_(u'The group still '
					u'has members. You must delete them first, or use '
					u'the --del-users argument. WARNING: this is '
					u'usually a bad idea; use with caution.'))

			if del_users:
				for user in prim_memb:
					LMC.users.del_User(user, no_archive, batch)

			if group.is_system:

				if group.is_helper and group.standard_group is not None:
					raise exceptions.BadArgumentError(_(u'Cannot delete a '
						u'helper group. Please delete the standard associated '
						u'group %s instead, and this group will be deleted in '
						u'the same time.') % stylize(ST_NAME,
						group.standard_group.name))

				elif group.is_system_restricted and not force:
					raise exceptions.BadArgumentError(_(u'Cannot delete '
						u'restricted system group %s without the --force '
						u'argument, this is too dangerous.') %
							stylize(ST_NAME, group.name))

				# wipe the group from the privileges if present there.
				if group.is_privilege:
					LMC.privileges.delete((group, ))

				# wipe cross-references to profiles where the group is recorded.
				for profile in group.profiles:
					# the profile.del_Groups() will call self.unlink_Profile()
					profile.del_Groups([ group ])

				# NOTE: no need to wipe cross-references in auxilliary members,
				# this is done in the Group.__del__ method.

				# a system group has no data on disk (no shared directory), just
				# delete its internal data and exit.
				self.__delete_group(group)

				# checkpoint, needed for multi-delete (users-groups-profile) operation,
				# to avoid collecting the deleted users at the end of the run, making
				# throw false-negative operation about non-existing groups.
				gc.collect()

				return

			# remove the inotifier watch before deleting the group, else
			# the call will fail, and before archiving group shared
			# data, else it will leave ghost notifies in our Inotifier thread,
			# which doesn't need that.
			group._inotifier_del_watch(self.licornd)

			# For a standard group, there are a few steps more :
			# 	- delete the responsible and guest groups (if exists),
			#	- then delete the symlinks and the group (if exists),
			#	- then the shared data.
			# For responsible and guests symlinks, don't do anything : all symlinks
			# point to <group_name>, not rsp-* / gst-*. No need to duplicate the
			# work.
			if group.responsible_group is not None:
				self.__delete_group(group.responsible_group)
			if group.guest_group is not None:
				self.__delete_group(group.guest_group)

			# delete all symlinks in other members homes.
			group.check_symlinks(delete=True, batch=True)

			# keep the home and name for later archiving or deletion
			home = group.homeDirectory
			name = group.name

			# finally, delete the group.
			self.__delete_group(group)

		# checkpoint, needed for multi-delete (users-groups-profile) operation,
		# to avoid collecting the deleted users at the end of the run, making
		# throw false-negative operation about non-existing groups.
		gc.collect()

		assert ltrace('locks', '< del_Group: %s %s %s' % (self.lock, LMC.privileges.lock, LMC.users.lock))

		# LOCKS: from here, everything is deleted in internal structures, we
		# don't need the locks anymore. The inotifier and the archiving parts
		# can be very long, releasing the locks is good idea.

		# the group information has been wiped out, remove or archive the shared
		# directory. If anything fails now, this is not a real problem, because
		# the system configuration data is safe. At worst, there is an orphaned
		# directory remaining in the arbo, which is harmless.
		if no_archive:
			L_service_enqueue(priorities.LOW, fsapi.remove_directory, home)
		else:
			L_service_enqueue(priorities.LOW, fsapi.archive_directory, home, name)
	def __delete_group(self, group):
		""" Delete a POSIX group."""

		# LOCKS: this method is never called directly, and must always be
		# encapsulated in another, which will acquire self.lock. This is the
		# case in DeleteGroup().

		assert ltrace('groups', '> __delete_group(%s)' % group.name)

		# keep informations for post-deletion hook
		backend = group.backend
		system  = group.is_system
		gid     = group.gidNumber
		name    = group.name

		L_event_run(InternalEvent('group_pre_del', group))

		if gid in self:
			del self[gid]
		else:
			logging.warning2(_(u'{0}: group {1} already not referenced in '
				u'controller!').format(stylize(ST_NAME, self.name),
					stylize(ST_NAME, name)))

		# FIXME: this is not very smart.
		# NOTE: this must be done *after* having deleted the data from self,
		# else mono-maniac backends (like shadow) don't see the change and
		# save everything, including the group we want to delete.
		group.backend.delete_Group(group)

		if group.is_helper:
			log = logging.info
		else:
			log = logging.notice

		# http://www.friday.com/bbum/2007/08/24/python-di/
		# http://mindtrove.info/python-weak-references/

		assert ltrace('gc', '  group ref count before del: %d %s' % (
				sys.getrefcount(group), gc.get_referrers(group)))

		del group

		L_event_run(InternalEvent('group_post_del', gid, name, system))

		log(_(u'Deleted {0}group {1}.').format(
			_(u'system ') if system else '', stylize(ST_NAME, name)))

		assert ltrace('groups', '< __delete_group(%s)' % name)
	def check_groups(self, groups_to_check=None, minimal=True, force=False,
											batch=False, auto_answer=None):
		""" Check a list of groups. All other parameters are forwarded to
			:meth:`Group.check` without any modification and are not used here.

			:param groups_to_check: a list of :class:`Group` objects.
		"""

		assert ltrace('groups', '| check_groups(%s, minimal=%s, force=%s,'
			'batch=%s, )' %	('None' if groups_to_check is None
				else ', '.join(g.name for g in groups_to_check),
				minimal, force, batch))

		if groups_to_check is None:
			# we have to duplicate the values, in case the check adds/remove
			# groups. Else, this will raise a RuntimeError.
			groups_to_check = self.values()

		for group in groups_to_check:
			group.check(minimal, force, batch, auto_answer)

		del groups_to_check
		self.licornd.clean_objects()
	def __connect_groups(self):
		""" Iterate all groups and connect standard/guest/responsible if they
			all exists, else print warnings about checks needing to be made.
		"""

		# we get a copy of groups list, whose size will decrease
		# while we connect them.
		stds    = self.select(filters.STD)
		resps   = self.select(filters.RESPONSIBLE)
		guests  = self.select(filters.GUEST)

		connected = 0

		for group in stds:
			connected1 = False
			connected2 = False

			gfound=None
			for guest in guests:
					if guest.name.endswith(group.name):
						guest.standard_group = group
						group.guest_group = guest
						connected1 = True
						gfound = guest
						break

			if gfound != None:
				guests.remove(guest)

			rfound=None
			for resp in resps:
					if resp.name.endswith(group.name):
						resp.standard_group = group
						group.responsible_group = resp
						connected2 = True
						rfound = resp

						# make the triangle complete; guests are
						# already connected, this should not fail;
						# except for missing guests.
						if group.guest_group:
							group.guest_group.responsible_group = resp
							resp.guest_group = group.guest_group

						break

			if rfound != None:
				resps.remove(resp)

			if connected1 and connected2:
				connected += 1

		if connected != len(stds):
			logging.warning(_(u'%s: inconsistency detected. '
				u'Automatic check requested in the background.') %
					stylize(ST_NAME, self.name))
			L_service_enqueue(priorities.HIGH,
						self.check_groups, batch=True, job_delay=5.0)

		if resps != [] or guests != []:
			logging.warning(_(u'%s: dangling helper group(s) detected. '
				u'Automatic removal requested in the background.') %
					stylize(ST_NAME, self.name))

			def remove_superfluous_groups(groups):
				""" Remove superflous guests and resps groups. """
				for group in groups:
					self.del_Group(group, force=True, batch=True)

			L_service_enqueue(priorities.LOW,
											remove_superfluous_groups,
											resps + guests, job_delay=3.0)

		del stds, resps, guests
	def __connect_users(self, clear_first=False):
		""" Iterate all users and connect their primary group to them, to speed
			up future lookups.

			:param clear_first: set to ``True`` only on a backend reload, else
				not used.
		"""

		if clear_first:
			for user in LMC.users:
				user.clear_Groups()

		# update the reverse mapping users -> groups to avoid brute
		# loops when searching by users instead of groups.
		#
		# WARNING: the following 2 things must be done in multiple passes
		# (collect groups to rewrite, then serialize them), because doing it
		# in one pass will make us lose some data for groups which have not
		# yet setup their initial links, if they are stored in backends which
		#  don't serialize groups one by one (typically shadow).
		to_rewrite = []

		for group in self:
			to_rewrite.extend(g for g in group._setup_initial_links())

		for group in to_rewrite:
			group.serialize()

		missing_gids = [ user for user in LMC.users
							if user.primaryGroup is None ]

		if len(missing_gids) > 0:
			logging.warning(_(u'{0}: primary group is missing for '
				u'user(s) {1}. This is harmless, but should be '
				u'corrected manually by re-creating groups with '
				u'fixed GIDs, or changing these users GIDs to other '
				u'values.').format(self.name, ', '.join(
					( _(u'{0}(gid={1})').format(
							stylize(ST_LOGIN, user.login),
							stylize(ST_UGID, user.gid))
								for user in missing_gids))))

		del missing_gids
	def guess_one(self, value):
		""" Try to guess everything of a group from a
			single and unknonw-typed info. """
		try:
			group = self.by_gid(int(value))

		except (TypeError, ValueError):
				group = self.by_name(value)

		return group
	def guess_list(self, value_list):
		""" yield valid groups, given a list of 'things'
		 to validate existence of (can be GIDs or names). """
		groups = []

		for value in value_list:
			try:
				group = self.guess_one(value)

			except (KeyError, exceptions.DoesntExistException):
				logging.info(_(u'Skipped non-existing group name or GID %s.') %
					stylize(ST_NAME,value))
			else:
				if group in groups:
					pass
				else:
					groups.append(group)

		return groups
	def exists(self, gid=None, name=None):
		"""Return true if the group or gid exists on the system. """

		assert ltrace('groups', '|  exists(name=%s, gid=%s)' % (name, gid))

		if name:
			#print name in Group.by_name
			return name in Group.by_name

		if gid:
			return gid in self.iterkeys()

		raise exceptions.BadArgumentError(
			_(u"You must specify a GID or a name to test existence of."))
	def gid_to_name(self, gid):
		""" Return the group name for a given GID."""
		try:
			return self[gid].name
		except KeyError:
			raise exceptions.DoesntExistException(
				_(u"GID %s doesn't exist") % gid)
	def name_to_gid(self, name):
		""" Return the gid of the group 'name'."""
		try:
			assert ltrace('groups', '| name_to_gid(%s) -> %s' % (
				name, self.by_name(name).gidNumber))
			# use the cache, Luke !
			return self.by_name(name).gidNumber
		except KeyError:
			raise exceptions.DoesntExistException(
				_(u"Group %s doesn't exist") % name)

	def _cli_get(self, selected=None, long_output=False, no_colors=False):
		""" Export the groups list to human readable (= « get group ») form. """

		with self.lock:
			if selected is None:
				groups = self.values()
			else:
				groups = selected

			# FIXME: forward long_output to _cli_get(), or remove it
			if long_output:
				return u'%s\n' % u'\n'.join((group._cli_get()
								for group in sorted(groups, key=attrgetter('gid'))))
			else:
				return u'%s\n' % u'\n'.join((group._cli_get()
								for group in sorted(groups, key=attrgetter('gid'))
									if not group.is_helper))
