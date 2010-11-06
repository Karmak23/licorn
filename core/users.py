# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2
"""

import os, sys
import Pyro.core
from time import time, strftime, gmtime
from threading import RLock

from licorn.foundations           import logging, exceptions, process, hlstr
from licorn.foundations           import pyutils, styles, fsapi
from licorn.foundations.objects   import Singleton
from licorn.foundations.constants import filters
from licorn.foundations.ltrace    import ltrace

class UsersController(Singleton, Pyro.core.ObjBase):

	init_ok = False

	def __init__(self, configuration):
		""" Create the user accounts list from the underlying system. """

		assert ltrace('users', '> UsersController.__init__(%s)' %
			UsersController.init_ok)

		if UsersController.init_ok:
			return

		Pyro.core.ObjBase.__init__(self)

		self.lock = RLock()

		# cross-references to other common objects
		self.configuration = configuration
		configuration.set_controller('users', self)
		self.backends = self.configuration.backends
		self.profiles = None # (ProfilesController)
		self.groups = None # (GroupsController)

		self.reload(full=False)

		UsersController.init_ok = True
		assert ltrace('users', '> UsersController.__init__(%s)' %
			UsersController.init_ok)
	def __getitem__(self, item):
		return self.users[item]
	def __setitem__(self, item, value):
		self.users[item]=value
	def keys(self):
		return self.users.keys()
	def has_key(self, key):
		return self.users.has_key(key)
	def reload(self, full=True):
		""" Load (or reload) the data structures from the system data. """

		assert ltrace('users', '| reload()')

		with self.lock:
			self.users       = {}
			self.login_cache = {}

			for bkey in self.backends.keys():
				if bkey=='prefered':
					continue
				self.backends[bkey].set_users_controller(self)
				u, c = self.backends[bkey].load_users()
				self.users.update(u)
				self.login_cache.update(c)

		if full:
			# needed when reload is trigerred by /etc/* change in the inotifier.
			self.groups.reload()
	def reload_backend(self, backend_name):
		""" Reload only one backend data (called from inotifier). """

		assert ltrace('users', '| reload_backend(%s)' % backend_name)

		with self.lock:
			u, c = self.backends[backend_name].load_users()
			self.users.update(u)
			self.login_cache.update(c)
	def set_profiles_controller(self, profiles):
		self.profiles = profiles
	def set_groups_controller(self, groups):
		self.groups = groups
	def WriteConf(self, uid=None):
		""" Write the user data in appropriate system files."""

		assert ltrace('users', '| WriteConf()')

		with self.lock:
			if uid:
				self.backends[
					self.users[uid]['backend']
					].save_one_user(uid)
			else:
				for bkey in self.backends.keys():
					if bkey=='prefered':
						continue
					self.backends[bkey].save_users()
	def Select(self, filter_string):
		""" Filter user accounts on different criteria.
		Criteria are:
			- 'system users': show only «system» users (root, bin, daemon,
				apache…), not normal user account.
			- 'normal users': keep only «normal» users, which includes Licorn
				administrators
			- more to come…
		"""

		with self.lock:
			uids = self.users.keys()
			uids.sort()

			filtered_users = []

			if filters.NONE == filter_string:
				filtered_users = []

			elif filters.STANDARD == filter_string:
				def keep_uid_if_not_system(uid):
					if not self.is_system_uid(uid):
						filtered_users.append(uid)

				map(keep_uid_if_not_system, uids)

			elif filters.SYSTEM == filter_string:
				def keep_uid_if_system(uid):
					if self.is_system_uid(uid):
						filtered_users.append(uid)

				map(keep_uid_if_system, uids)

			elif filters.SYSTEM_RESTRICTED == filter_string:
				def keep_uid_if_system_restricted(uid):
					if self.is_restricted_system_uid(uid):
						filtered_users.append(uid)

				map(keep_uid_if_system_restricted, uids)

			elif filters.SYSTEM_UNRESTRICTED == filter_string:
				def keep_uid_if_system_unrestricted(uid):
					if self.is_unrestricted_system_uid(uid):
						filtered_users.append(uid)

				map(keep_uid_if_system_unrestricted, uids)

			elif type(filter_string) == type([]):
				filtered_users = filter_string

			else:
				import re
				uid_re = re.compile("^uid=(?P<uid>\d+)")
				uid = uid_re.match(filter_string)
				if uid is not None:
					uid = int(uid.group('uid'))
					if self.users.has_key(uid):
						filtered_users.append(uid)
					else:
						raise exceptions.DoesntExistsException(
							'UID %d does not exist.' % uid)
			return filtered_users
	def _validate_home_dir(self, home, login, system, force, listener=None):
		""" Do some basic but sane tests on the home dir provided. """

		if system:
			if home:
				if os.path.exists(home) and not force:
					raise exceptions.BadArgumentError(
						'''Directory specified %s for system user %s '''
						'''already exists. If you really want to use '''
						'''it, please specify --force argument.''' % (
						styles.stylize(styles.ST_PATH, home),
						styles.stylize(styles.ST_NAME,login)))

				if not home.startswith(
					self.configuration.defaults.home_base_path) \
					and not home.startswith('/var') \
					or home.startswith('%s/%s' %(
						self.configuration.defaults.home_base_path,
						self.configuration.groups.names.plural)) \
					or home.find('/tmp') != -1:

					raise exceptions.BadArgumentError(
						'''Specified home directory %s for system user '''
						'''%s is outside %s and /var, or inside %s/%s '''
						'''and a temporary directory (/var/tmp, /tmp). '''
						'''This is unsupported, '''
						'''sorry. Aborting.''' % (
						styles.stylize(styles.ST_PATH, home),
						styles.stylize(styles.ST_NAME,login),
						self.configuration.defaults.home_base_path,
						self.configuration.defaults.home_base_path,
						self.configuration.groups.names.plural))

				if home in [ self.users[uid]['homeDirectory'] for uid in
					self.users ]:
					raise exceptions.BadArgumentError(
						'''Specified home directory %s for system user '''
						'''%s is already owned by another user. It can't '''
						'''be used, sorry.''' % (
						styles.stylize(styles.ST_PATH, home),
						styles.stylize(styles.ST_NAME,login)))

				return home
		else: # not system
			if home:
				logging.warning('''Specify an alternative home '''
				'''directory is not allowed for standard users. Using '''
				'''standard home path %s instead.''' % (
				styles.stylize(styles.ST_PATH, '%s/%s' % (
					self.configuration.users.base_path, login))),
				listener=listener)

		return "%s/%s" % (self.configuration.users.base_path, login)
	def _validate_basic_fields(self, login, firstname, lastname, gecos, shell,
		skel, listener=None):
		# to create a user account, we must have a login. autogenerate it
		# if not given as argument.
		if login is None:
			if firstname is None or lastname is None:
				raise exceptions.BadArgumentError(
					logging.SYSU_SPECIFY_LGN_FST_LST)
			else:
				login_autogenerated = True
				login = self.make_login(lastname, firstname)
		else:
			login_autogenerated = False

		if gecos is None:
			gecos_autogenerated = True

			if firstname is None or lastname is None:
				gecos = "Compte %s" % login
			else:
				gecos = "%s %s" % (firstname, lastname.upper())
		else:
			gecos_autogenerated = False

			if firstname and lastname:
				raise exceptions.BadArgumentError(
					logging.SYSU_SPECIFY_LF_OR_GECOS)
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
				raise exceptions.BadArgumentError(
					logging.SYSU_MALFORMED_LOGIN % (
						login, styles.stylize(styles.ST_REGEX,
						hlstr.regex['login'])))

		if not login_autogenerated and \
			len(login) > self.configuration.users.login_maxlenght:
			raise exceptions.LicornRuntimeError(
				"Login %s too long (currently %d characters," \
				" but must be shorter or equal than %d)." % (
					login, len(login),
					self.configuration.users.login_maxlenght) )

		# then, verify that other arguments match the system constraints.
		if not hlstr.cregex['description'].match(gecos):
			if gecos_autogenerated:
				raise exceptions.LicornRuntimeError(
					"Can't build a valid GECOS (%s) with the" \
					" firstname/lastname (%s/%s) or login you provided." % (
						gecos, firstname, lastname) )
			else:
				raise exceptions.BadArgumentError(
					logging.SYSU_MALFORMED_GECOS % (
						gecos, styles.stylize(styles.ST_REGEX,
						hlstr.regex['description'])))

		if shell is not None and shell not in self.configuration.users.shells:
			raise exceptions.BadArgumentError(
				"Invalid shell %s. Valid shells are: %s." % (shell,
					self.configuration.users.shells))

		if skel is not None \
			and skel not in self.configuration.users.skels:
			raise exceptions.BadArgumentError(
				"The skel you specified doesn't exist on this system." \
				" Valid skels are: %s." % \
					self.configuration.users.skels)

		return login, firstname, lastname, gecos, shell, skel
	def _validate_important_fields(self, desired_uid, login, system, force,
		listener=None):
		# if an UID is given, it must be free. The lock ensure is will *stay*
		# free.
		# FIXME: this is not really exact, if someone adds / removes a user from
		# outside Licorn®. we should lock the backend too, before looking at the
		# UIDs.
		if self.users.has_key(desired_uid):
			raise exceptions.AlreadyExistsError('''The UID you want (%s) '''
				'''is already taken by another user (%s). Please choose '''
				'''another one.''' % (
					styles.stylize(styles.ST_UGID, desired_uid),
					styles.stylize(styles.ST_NAME,
						self.users[desired_uid]['login'])))

		# Verify prior existence of user account
		if login in self.login_cache:
			if (system and self.is_system_login(login)) \
				or (not system and self.is_standard_login(login)):
				raise exceptions.AlreadyExistsException(
					"User account %s already exists !" % login)
			else:
				raise exceptions.AlreadyExistsError(
					'''A user account %s already exists but has not the same '''
					'''type. Please choose another login for your user.'''
					% styles.stylize(styles.ST_NAME, login))

		# Due to a bug of adduser/deluser perl script, we must check that there
		# is no group which the same name than the login. There should not
		# already be a system group with the same name (we are just going to
		# create it…), but it could be a system inconsistency, so go on to
		# recover from it.
		#
		# {add,del}user logic is:
		#	- a system account must always have a system group as primary group,
		# 		else if will be «nogroup» if not specified.
		#   - when deleting a system account, a corresponding system group will
		#		be deleted if existing.
		#	- no restrictions for a standard account
		#
		# the bug is that in case 2, deluser will delete the group even if this
		#  is a standard group (which is bad). This could happen with:
		#	addgroup toto
		#	adduser --system toto --ingroup root
		#	deluser --system toto
		#	(group toto is deleted but it shouldn't be ! And it is deleted
		#	without *any* message !!)
		#
		if login in self.groups.name_cache and not force:
			raise exceptions.UpstreamBugException, \
				"A group named `%s' exists on the system," \
				" this could eventually conflict in Debian/Ubuntu system" \
				" tools. Please choose another user's login, or use " \
				"--force argument if you really want to add this user " \
				"on the system." % login
	def _generate_uid(self, login, desired_uid, system, listener=None):
		# generate an UID if None given, else verify it matches constraints.
		if desired_uid is None:
			if system:
				uid = pyutils.next_free(self.users.keys(),
					self.configuration.users.system_uid_min,
					self.configuration.users.system_uid_max)
			else:
				uid = pyutils.next_free(self.users.keys(),
					self.configuration.users.uid_min,
					self.configuration.users.uid_max)

			logging.progress('Autogenerated UID for user %s: %s.' % (
				styles.stylize(styles.ST_LOGIN, login),
				styles.stylize(styles.ST_SECRET, uid)), listener=listener)
		else:
			if (system and self.is_system_uid(desired_uid)) \
				or (not system and self.is_standard_uid(
					desired_uid)):
					uid = desired_uid
			else:
				raise exceptions.BadArgumentError('''UID out of range '''
					'''for the kind of user account you specified. System '''
					'''UID must be between %d and %d, standard UID must be '''
					'''between %d and %d.''' % (
						self.configuration.users.system_uid_min,
						self.configuration.users.system_uid_max,
						self.configuration.users.uid_min,
						self.configuration.users.uid_max)
					)
		return uid
	def AddUser(self, login=None, system=False, password=None, gecos=None,
		desired_uid=None, primary_gid=None, profile=None, skel=None, shell=None,
		home=None, lastname=None, firstname=None, in_groups=[], batch=False,
		force=False, listener=None):
		"""Add a user and return his/her (uid, login, pass)."""

		assert ltrace('users', '''> AddUser(login=%s, system=%s, pass=%s, '''
			'''uid=%s, gid=%s, profile=%s, skel=%s, gecos=%s, first=%s, '''
			'''last=%s, home=%s, shell=%s)''' % (login, system, password,
			desired_uid, primary_gid, profile, skel, gecos, firstname, lastname,
			home, shell))

		assert type(in_groups) == type([])

		login, firstname, lastname, gecos, shell, skel = \
			self._validate_basic_fields(login, firstname, lastname,
				gecos, shell, skel, listener=listener)

		if primary_gid:
			# this will raise a DoesntExistException if bad.
			pg_gid = self.groups.guess_identifier(primary_gid)

		#self.lock_backends()
		with self.lock:

			self._validate_important_fields(desired_uid, login, system, force,
				listener=listener)

			uid = self._generate_uid(login, desired_uid, system,
				listener=listener)

			skel_to_apply = "/etc/skel"
			groups_to_add_user_to = in_groups

			tmp_user_dict = {}

			# 3 cases:
			if profile is not None:
				# Apply the profile after having created the home dir.
				try:
					tmp_user_dict['loginShell'] = shell if shell else \
						self.profiles.profiles[profile]['profileShell']
					tmp_user_dict['gidNumber'] = \
						self.groups.name_to_gid(
							self.profiles.guess_identifier(profile))

					tmp_user_dict['homeDirectory'] = self._validate_home_dir(
						home, login, system, force, listener)

					if self.profiles[profile]['memberGid'] != []:
						groups_to_add_user_to.extend([
							self.groups.name_to_gid(x) for x in
							self.profiles[profile]['memberGid']])

					if skel is None:
						skel_to_apply = \
							self.profiles.profiles[profile]['profileSkel']
				except KeyError, e:
					# fix #292
					raise exceptions.DoesntExistsError('''The profile %s '''
						'''doesn't exist (was: %s) !''' % (profile, e))
			elif primary_gid is not None:
				tmp_user_dict['gidNumber']     = pg_gid
				tmp_user_dict['loginShell']    = shell if shell else \
					self.configuration.users.default_shell

				tmp_user_dict['homeDirectory'] = self._validate_home_dir(home,
					login, system, force, listener)

				# FIXME: use is_valid_skel() ?
				if skel is None and \
					os.path.isdir(
						self.groups.groups[pg_gid]['groupSkel']):
					skel_to_apply = \
						self.groups.groups[pg_gid]['groupSkel']
			else:
				tmp_user_dict['gidNumber'] = \
					self.configuration.users.default_gid
				tmp_user_dict['loginShell'] = shell if shell else \
					self.configuration.users.default_shell

				tmp_user_dict['homeDirectory'] = self._validate_home_dir(home,
					login, system, force, listener)

				# if skel is None, system default skel will be applied

			# FIXME: is this necessary here ? not done before ?
			if skel is not None:
				skel_to_apply = skel

			# autogenerate password if not given.
			if password is None:
				# TODO: call cracklib2 to verify passwd strenght.
				password = hlstr.generate_password(
					self.configuration.users.min_passwd_size)

				logging.notice(logging.SYSU_AUTOGEN_PASSWD % (
					styles.stylize(styles.ST_LOGIN, login),
					styles.stylize(styles.ST_UGID, uid),
					styles.stylize(styles.ST_SECRET, password)),
					listener=listener)

			tmp_user_dict['userPassword'] = \
				self.backends['prefered'].compute_password(password)

			tmp_user_dict['shadowLastChange'] = str(int(time()/86400))

			# start unlocked, now that we got a brand new password.
			tmp_user_dict['locked'] = False

			# create home directory and apply skel
			if os.path.exists(tmp_user_dict['homeDirectory']):
				logging.info('home dir %s already exists, not overwritting.' %
					styles.stylize(styles.ST_PATH,
						tmp_user_dict['homeDirectory']))
			else:
				import shutil
				# copytree automatically creates tmp_user_dict['homeDirectory']
				shutil.copytree(skel_to_apply, tmp_user_dict['homeDirectory'])

			tmp_user_dict['uidNumber']      = uid
			tmp_user_dict['gecos']          = gecos
			tmp_user_dict['login']          = login
			# prepare the groups cache.
			tmp_user_dict['groups']         = []
			tmp_user_dict['shadowInactive'] = ''
			tmp_user_dict['shadowWarning']  = 7
			tmp_user_dict['shadowExpire']   = ''
			tmp_user_dict['shadowMin']      = 0
			tmp_user_dict['shadowMax']      = 99999
			tmp_user_dict['shadowFlag']     = ''
			tmp_user_dict['backend']        = \
				self.backends['prefered'].name

			# Add user in internal list and in the cache
			self.users[uid]         = tmp_user_dict
			self.login_cache[login] = uid

			# we can't skip the WriteConf(), because this would break Samba
			# stuff, and AddUsersInGroup stuff too:
			# Samba needs Unix account to be present in /etc/* before creating
			# the Samba account. We thus can't delay the WriteConf() call, even
			# if we are in batch / import users mode.
			#
			# DO NOT UNCOMMENT -- if not batch:
			self.users[uid]['action'] = 'create'
			self.backends[
				self.users[uid]['backend']
				].save_user(uid)

			# Samba: add Samba user account.
			# TODO: put this into a module.
			# TODO: find a way to get the output back to the listener…
			try:
				sys.stderr.write(process.execute(
					['smbpasswd', '-a', login, '-s'],
					'%s\n%s\n' % (password, password))[1])
			except (IOError, OSError), e:
				if e.errno not in (2, 32):
					raise e

		logging.info(logging.SYSU_CREATED_USER % (
			'system ' if system else '',
			styles.stylize(styles.ST_LOGIN, login),
			styles.stylize(styles.ST_UGID, uid)),
			listener=listener)

		self.CheckUsers([ uid ], batch=True, listener=listener)

		if groups_to_add_user_to != []:
			for gid_to_add in groups_to_add_user_to:
				self.groups.AddUsersInGroup(gid=gid_to_add,
					users_to_add=[uid], listener=listener)

		# Set quota
		if profile is not None:
			try:
				pass
				#os.popen2( [ 'quotatool', '-u', str(uid), '-b', self.configuration.defaults.quota_device, '-l' '%sMB' % self.profiles.profiles[profile]['quota'] ] )[1].read()
				#logging.warning("quotas are disabled !")
				# XXX: Quotatool can return 2 without apparent reason
				# (the quota is etablished) !
			except exceptions.LicornException, e:
				logging.warning( "ROLLBACK create user because '%s'." % str(e),
					listener=listener)
				self.DeleteUser(login, True, listener=listener)
				return (False, False, False)

		assert ltrace('users', '< AddUser()')
		return (uid, login, password)
	def DeleteUser(self, login=None, uid=None, no_archive=False, batch=False,
		listener=None):
		""" Delete a user """

		uid, login = self.resolve_uid_or_login(uid, login)

		assert ltrace('users', "| DeleteUser() %s(%s), groups %s." % (
			login, str(uid), self.users[uid]['groups']) )

		# Delete user from his groups
		# '[:]' to fix #14, see
		# http://docs.python.org/tut/node6.html#SECTION006200000000000000000
		for group in self.users[uid]['groups'][:]:
			self.groups.DeleteUsersFromGroup(name=group,
				users_to_del=[ uid ], batch=True)

		try:
			# samba stuff
			# TODO: forward output to listener…
			sys.stderr.write(process.execute(['smbpasswd', '-x', login])[1])
		except (IOError, OSError), e:
			if e.errno not in (2, 32):
				raise e

		# keep the homedir path, to backup it if requested.
		homedir = self.users[uid]["homeDirectory"]

		# keep the backend, to notice the deletion
		backend = self.users[uid]['backend']


		with self.lock:
			# Delete user from users list
			del(self.login_cache[login])
			del(self.users[uid])
		logging.info(logging.SYSU_DELETED_USER % \
			styles.stylize(styles.ST_LOGIN, login), listener=listener)

		# TODO: try/except and reload the user if unable to delete it
		# delete the user in the backend after deleting it locally, else
		# Unix backend will not know what to delete (this is quite a hack).
		self.backends[backend].delete_user(login)

		# user is now wiped out from the system.
		# Last thing to do is to delete or archive the HOME dir.

		if no_archive:
			import shutil
			try:
				shutil.rmtree(homedir)
			except OSError, e:
				logging.warning("Problem deleting home dir %s (was: %s)" % (
					styles.stylize(styles.ST_PATH, homedir), e),
					listener=listener)

		else:
			# /home/archives must be OK befor moving
			self.configuration.check_base_dirs(minimal=True,
				batch=True, listener=listener)

			user_archive_dir = "%s/%s.deleted.%s" % (
				self.configuration.home_archive_dir,
				login, strftime("%Y%m%d-%H%M%S", gmtime()))
			try:
				os.rename(homedir, user_archive_dir)

				logging.info(logging.SYSU_ARCHIVED_USER % (homedir,
					styles.stylize(styles.ST_PATH, user_archive_dir)),
					listener=listener)

				self.configuration.check_archive_dir(
					user_archive_dir, batch=True, listener=listener)

			except OSError, e:
				if e.errno == 2:
					logging.warning(
						"Home dir %s doesn't exist, thus not archived." % \
							styles.stylize(styles.ST_PATH, homedir),
							listener=listener)
				else:
					raise e
	def ChangeUserPassword(self, login=None, uid=None, password=None,
		display=False, listener=None):
		""" Change the password of a user. """

		with self.lock:
			uid, login = self.resolve_uid_or_login(uid, login)

			if password is None:
				password = hlstr.generate_password(
					self.configuration.users.min_passwd_size)
			elif password == "":
				logging.warning(logging.SYSU_SET_EMPTY_PASSWD % \
					styles.stylize(styles.ST_LOGIN, login), listener=listener)
				#
				# SECURITY concern: if password is empty, shouldn't we
				# automatically remove user from remotessh ?
				#

			self.users[uid]['userPassword'] = \
			self.backends[
				self.users[uid]['backend']
				].compute_password(password)

			# 3600*24 to have the number of days since epoch (fixes #57).
			self.users[uid]['shadowLastChange'] = str(
				int(time()/86400) )

			self.users[uid]['action'] = 'update'
			self.backends[
				self.users[uid]['backend']
				].save_user(uid)

			if display:
				logging.notice("Set password for user %s(%s) to %s." % (
					styles.stylize(styles.ST_NAME, login),
					styles.stylize(styles.ST_UGID, uid),
					styles.stylize(styles.ST_IMPORTANT, password)),
					listener=listener)
			else:
				logging.info('Changed password for user %s(%s).' % (
					styles.stylize(styles.ST_NAME, login),
					styles.stylize(styles.ST_UGID, uid)),
					listener=listener)

			try:
				# samba stuff
				# TODO: forward output to listener…
				sys.stderr.write(process.execute(['smbpasswd', login, '-s'],
					"%s\n%s\n" % (password, password))[1])
			except (IOError, OSError), e:
				if e.errno != 32:
					raise e
	def ChangeUserGecos(self, login=None, uid=None, gecos="", listener=None):
		""" Change the gecos of a user. """

		with self.lock:
			uid, login = self.resolve_uid_or_login(uid, login)

			if not hlstr.cregex['description'].match(gecos):
				raise exceptions.BadArgumentError(logging.SYSU_MALFORMED_GECOS % (
					gecos,
					styles.stylize(styles.ST_REGEX, hlstr.regex['description'])))

			self.users[uid]['gecos'] = gecos

			self.users[uid]['action'] = 'update'
			self.backends[
				self.users[uid]['backend']
				].save_user(uid)

			logging.info('Changed GECOS for user %s(%s) to %s.' % (
				styles.stylize(styles.ST_NAME, login),
				styles.stylize(styles.ST_UGID, uid),
				styles.stylize(styles.ST_COMMENT, gecos)),
				listener=listener)
	def ChangeUserShell(self, login=None, uid=None, shell=None, listener=None):
		""" Change the shell of a user. """

		with self.lock:
			uid, login = self.resolve_uid_or_login(uid, login)

			if shell is None or shell not in self.configuration.users.shells:
				raise exceptions.BadArgumentError(
					"Invalid shell %s. Valid shells are %s." % (
						shell, self.configuration.users.shells)
					)

			self.users[uid]['loginShell'] = shell

			self.users[uid]['action'] = 'update'
			self.backends[
				self.users[uid]['backend']
				].save_user(uid)

			logging.info('Changed shell for user %s(%s) to %s.' % (
				styles.stylize(styles.ST_NAME, login),
				styles.stylize(styles.ST_UGID, uid),
				styles.stylize(styles.ST_COMMENT, shell)),
				listener=listener)
	def LockAccount(self, login=None, uid=None, lock=True, listener=None):
		"""(Un)Lock a user account. """

		with self.lock:
			uid, login = self.resolve_uid_or_login(uid, login)

			if lock:
				if self.users[uid]['locked']:
					logging.info('account %s already locked.' %
						styles.stylize(styles.ST_NAME, login), listener=listener)
				else:
					self.users[uid]['userPassword'] = '!' + \
						self.users[uid]['userPassword']
					logging.info('Locked user account %s.' % \
						styles.stylize(styles.ST_LOGIN, login), listener=listener)
			else:
				if self.users[uid]['locked']:
					self.users[uid]['userPassword'] = \
						self.users[uid]['userPassword'][1:]
					logging.info('Unlocked user account %s.' % \
						styles.stylize(styles.ST_LOGIN, login), listener=listener)
				else:
					logging.info('account %s already unlocked.' %
						styles.stylize(styles.ST_NAME, login), listener=listener)

			self.users[uid]['locked'] = lock

			self.users[uid]['action'] = 'update'
			self.backends[
				self.users[uid]['backend']
				].save_user(uid)
	def ApplyUserSkel(self, login=None, uid=None, skel=None, listener=None):
		""" Apply a skel on a user. """

		# FIXME: 1 reimplement this cleanly, without shell subcommands
		# FIXME: 2 use fine-grained file-locking to avoid applying skel onto
		# another skel-apply process.
		# FIXME:  3 use with self.lock to avoid user beiing deleted while skel
		# applies ?

		uid, login = self.resolve_uid_or_login(uid, login)

		if skel is None or skel not in self.configuration.defaults.skels:
			raise exceptions.BadArgumentError(
				"Invalid skel %s. Valid shells are %s." % (
					skel, self.configuration.users.skels)
				)

		# no force option with shutil.copytree(), thus use cp to force overwrite
		process.syscmd("cp -r %s/* %s/.??* %s" % (skel, skel,
			self.users[uid]['homeDirectory']) )

		# set permission (because root)
		for fileordir in os.listdir(skel):
			try:
				# FIXME: do this with minifind(), os.chmod()… and map() it.
				process.syscmd("chown -R %s %s/%s" % (
					self.users[uid]['login'],
					self.users[uid]['homeDirectory'], fileordir) )
			except Exception, e:
				logging.warning(str(e), listener=listener)
	def ExportCLI(self, selected=None, long_output=False):
		""" Export the user accounts list to human readable («passwd») form. """

		with self.lock:

			if selected is None:
				uids = self.users.keys()
			else:
				uids = selected
			uids.sort()

			assert ltrace('users', '| ExportCLI(%s)' % uids)

			def build_cli_output_user_data(uid, users=self.users):
				#
				# If we don't have access to 'locked', we are not root and cannot
				# display locked status of account. don't bother and don't display
				# anything about it, admin won't bother knowing he/she is not root.
				#
				#ltrace('users', 'building cli output for user %s(%s), locked=%s' % (
				#	uid, users[uid]['login'], users[uid]['locked'] \
				#		if users[uid].has_key('locked') else 'None'))
				if users[uid].has_key('locked'):
					if users[uid]['locked']:
						user_login = "%s" % styles.stylize(styles.ST_BAD,
							users[uid]['login'])
					else:
						user_login = styles.stylize(styles.ST_OK,
							users[uid]['login'])
				else:
					user_login = styles.stylize(styles.ST_NAME,
							users[uid]['login'])

				account = [	user_login,
							str(uid),
							str(users[uid]['gidNumber']),
							users[uid]['gecos'],
							users[uid]['homeDirectory'],
							users[uid]['loginShell'],
							]
				if long_output:
					account.append(','.join(self.users[uid]['groups']))
					account.append('[%s]' % styles.stylize(
						styles.ST_LINK, users[uid]['backend']))

				return ':'.join(account)

			data = '\n'.join(map(build_cli_output_user_data, uids)) + '\n'

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
	def ExportXML(self, selected=None, long_output=False):
		""" Export the user accounts list to XML. """

		with self.lock:
			if selected is None:
				uids = self.users.keys()
			else:
				uids = selected
			uids.sort()

			assert ltrace('users', '| ExportXML(%s)' % uids)

			def build_xml_output_user_data(uid):
				data = '''
		<user>
			<login>%s</login>
			<uid>%d</uid>
			<gid>%d</gid>
			<gecos>%s</gecos>
			<homeDirectory>%s</homeDirectory>
			<loginShell>%s</loginShell>\n''' % (
						self.users[uid]['login'],
						uid,
						self.users[uid]['gidNumber'],
						self.users[uid]['gecos'],
						self.users[uid]['homeDirectory'],
						self.users[uid]['loginShell']
					)
				if long_output:
					data += '''		<groups>%s</groups>
			<backend>%s</backend>\n''' % (
						','.join(self.users[uid]['groups']),
						self.users[uid]['backend'])

				return data + "	</user>"

			data = "<?xml version='1.0' encoding=\"UTF-8\"?>\n<users-list>\n" \
				+ '\n'.join(map(build_xml_output_user_data, uids)) \
				+ "\n</users-list>\n"

			return data
	def CheckUsers(self, uids_to_check = [], minimal=True, batch=False,
		auto_answer=None, listener=None):
		"""Check user accounts and account data consistency."""

		assert ltrace('users', '> CheckUsers(uids_to_check=%s, minimal=%s, batch=%s)' %
			(uids_to_check, minimal, batch))

		# FIXME: should we crash if the user's home we are checking is removed
		# during the check ? what happens ?

		# dependancy: base dirs must be OK before checking users's homes.
		self.configuration.check_base_dirs(minimal=minimal,
			batch=batch, auto_answer=auto_answer, listener=listener)

		def check_uid(uid, minimal=minimal, batch=batch,
			auto_answer=auto_answer, listener=listener):

			assert ltrace('users', '> CheckUsers.check_uid(uid=%s)' % uid)

			with self.lock:
				login = self.uid_to_login(uid)
				all_went_ok = True

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
				if self.is_unrestricted_system_uid(uid):

					logging.progress("Checking system account %s..." % \
						styles.stylize(styles.ST_NAME, login), listener=listener)

					if os.path.exists(self.users[uid]['homeDirectory']):
						home_dir_info = [ {
							'path'       : self.users[uid]['homeDirectory'],
							'user'       : login,
							'group'      : self.groups.groups[
								self.users[uid]['gidNumber']]['name'],
							'mode'       : 00700,
							'content_mode': 00600
							} ]

						all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
							home_dir_info, batch=batch, auto_answer=auto_answer,
							allgroups=self.groups, allusers=self,
							listener=listener)
				elif self.is_standard_uid(uid):
					logging.progress("Checking standard account %s…" % \
						styles.stylize(styles.ST_LOGIN, login), listener=listener)

					gid       = self.users[uid]['gidNumber']
					group     = self.groups.groups[gid]['name']
					user_home = self.users[uid]['homeDirectory']

					logging.progress("Checking user account %s…" % \
						styles.stylize(styles.ST_NAME, login), listener=listener)

					acl_base                  = "u::rwx,g::---,o:---"
					file_acl_base             = "u::rw@UE,g::---,o:---"
					acl_mask                  = "m:rwx"
					acl_restrictive_mask      = "m:r-x"
					file_acl_mask             = "m:rw@GE"
					file_acl_restrictive_mask = "m:rw@GE"

					#
					# first build a list of dirs (located in ~/) to be excluded
					# from the home dir check, because they must have restrictive
					# permission (for confidentiality reasons) and don't need any
					# ACLs. In the same time (for space optimization reasons),
					# append them to special_dirs[] (which will be checked *after*
					# home dir).
					#
					home_exclude_list = [ '.ssh', '.gnupg', '.gnome2_private',
											'.gvfs', 'Dropbox' ]
					special_dirs      = []

					special_dirs.extend([ {
						'path'       : "%s/%s" % (user_home, dir),
						'user'       : login,
						'group'      : group,
						'mode'       : 00700,
						'content_mode': 00600
						} for dir in home_exclude_list if \
							os.path.exists('%s/%s' % (user_home, dir)) ])

					if os.path.exists('%s/public_html' % user_home):

						home_exclude_list.append('public_html')

						special_dirs.append ( {
							'path'      : "%s/public_html" % user_home,
							'user'      : login,
							'group'     : 'acl',
							'access_acl': "%s,g:%s:r-x,g:www-data:r-x,%s" % (
								acl_base,
								self.configuration.defaults.admin_group,
								acl_restrictive_mask),
							'default_acl': "%s,g:%s:rwx,g:www-data:r-x,%s" % (
								acl_base,
								self.configuration.defaults.admin_group,
								acl_mask),
							'content_acl': "%s,g:%s:rw-,g:www-data:r--,%s" % (
								file_acl_base,
								self.configuration.defaults.admin_group,
								file_acl_mask),
							} )

					# if we are in charge of building the user's mailbox, do it and
					# check it. This is particularly important for ~/Maildir
					# because courier-imap will hog CPU time if the Maildir doesn't
					# exist prior to the daemon launch…
					if self.configuration.users.mailbox_auto_create and \
						self.configuration.users.mailbox_type == \
						self.configuration.MAIL_TYPE_HOME_MAILDIR:

						maildir_base = '%s/%s' % (user_home,
							self.configuration.users.mailbox)

						# WARNING: "configuration.users.mailbox" is assumed to have
						# a trailing slash if it is a Maildir, because that's the
						# way it is in postfix/main.cf and other MTA configuration.
						# Without the "/", the mailbox is assumed to be an mbox or
						# an MH. So we use [:-1] to skip the trailing "/", else
						# fsapi.minifind() won't match the dir name properly in the
						# exclusion list.

						home_exclude_list.append(
							self.configuration.users.mailbox[:-1])

						for dir in ( maildir_base, '%stmp' % maildir_base,
							'%scur' % maildir_base,'%snew' % maildir_base ):
							special_dirs.append ( {
								'path'       : dir,
								'user'       : login,
								'group'      : group,
								'mode'       : 00700,
								'content_mode': 00600
							} )

					# this will be handled in another manner later in this function.
					home_exclude_file_list = [ ".dmrc", ".procmailrc" ]
					for file in home_exclude_file_list:
						if os.path.exists('%s/%s' % (user_home, file)):
							home_exclude_list.append(file)
							all_went_ok &= fsapi.check_posix_ugid_and_perms(
								'%s/%s' % (user_home, file), uid, gid, 00600,
									batch=batch, auto_answer=auto_answer,
									allgroups=self.groups, allusers=self,
									listener=listener)

					# Now that the exclusion list is complete, we can check the home
					# dir. For that we need a dir_info with the correct information.

					home_dir_info = {
						'path'      : self.users[uid]['homeDirectory'],
						'user'      : login,
						'group'     : 'acl',
						'access_acl': "%s,g:%s:r-x,g:www-data:--x,%s" % (
							acl_base,
							self.configuration.defaults.admin_group,
							acl_restrictive_mask),
						'default_acl': "%s,g:%s:rwx,%s" % (acl_base,
							self.configuration.defaults.admin_group,
							acl_mask),
						'content_acl': "%s,g:%s:rw@GE,%s" % (file_acl_base,
							self.configuration.defaults.admin_group,
							file_acl_mask),
						'exclude'   : home_exclude_list
						}

					if not batch:
						logging.progress("Checking user home dir %s contents,"
							" this can take a while…" % styles.stylize(
							styles.ST_PATH, user_home), listener=listener)

					try:
						all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
							[ home_dir_info ], batch=batch, auto_answer=auto_answer,
							allgroups=self.groups, allusers=self,
							listener=listener)
					except exceptions.LicornCheckError:
						logging.warning("User home dir %s is missing,"
							" please repair this first." % styles.stylize(
							styles.ST_PATH, user_home), listener=listener)
						return False

					if special_dirs != []:
						all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
							special_dirs, batch=batch, auto_answer=auto_answer,
							allgroups=self.groups, allusers=self,
							listener=listener)

					if not minimal:
						logging.warning(
							"Extended checks are not yet implemented for users.",
							listener=listener)
						# TODO:
						#	logging.progress("Checking symlinks in user's home dir,
						# this can take a while…" % styles.stylize(
						# styles.ST_NAME, user))
						#	if not self.CleanUserHome(login, batch, auto_answer):
						#		all_went_ok = False

						# TODO: tous les groupes de cet utilisateur existent et
						# sont OK (CheckGroups recursif) WARNING: Forcer
						# minimal = True pour éviter les checks récursifs avec
						# CheckGroups().

					assert ltrace('users', '> CheckUsers.check_uid(all_went_ok=%s)' %
						all_went_ok)
				else:
					login = self.uid_to_login(uid)
					# not system account between 300 < 999, not standard account.
					# the account is thus a special (reserved) system account, below
					# uid 300 or above uid 65000. Just don't do anything.
					logging.info('''Skipped reserved system account %s '''
						'''(we don't check them at all).''' %
							styles.stylize(styles.ST_NAME, login),
							listener=listener)
				return all_went_ok

		all_went_ok=reduce(pyutils.keep_false, map(check_uid, uids_to_check))
		if all_went_ok is False:
			# NOTICE: don't test just "if reduce():", the result could be None
			# and everything is OK when None…
			raise exceptions.LicornCheckError(
				"Some user(s) check(s) didn't pass, or weren't corrected.")

		assert ltrace('users', '< CheckUsers(%s)' % all_went_ok)
		return all_went_ok
	def confirm_uid(self, uid):
		""" return a UID if it exists in the database. """
		try:
			return self.users[uid]['uidNumber']
		except KeyError:
			try:
				# try to int(), in case this is a call from cli_select(), which
				# gets only strings.
				return self.users[int(uid)]['uidNumber']
			except ValueError:
				raise exceptions.DoesntExistsException(
					"UID %s doesn't exist" % uid)
	def resolve_uid_or_login(self, uid, login):
		""" method used every where to get uid / login of a user object to
			do something onto. a non existing user / uid will raise an
			exception from the uid_to_login() / login_to_uid() methods."""

		if login is None and uid is None:
			raise exceptions.BadArgumentError(
				"You must specify a login or an UID to resolve from.")

		# we cannot just test "if uid:" because with root(0) this doesn't work.
		if uid is not None:
			login = self.uid_to_login(uid)
		else:
			uid = self.login_to_uid(login)
		return (uid, login)
	def guess_identifier(self, value):
		""" Try to guess everything of a user from a
			single and unknonw-typed info. """
		try:
			uid = int(value)
			self.uid_to_login(uid)
		except ValueError, e:
			uid = self.login_to_uid(value)
		return uid
	def guess_identifiers(self, value_list, listener=None):
		valid_ids=set()
		for value in value_list:
			try:
				valid_ids.add(self.guess_identifier(value))
			except exceptions.DoesntExistsException:
				logging.notice('Skipped non-existing login or UID %s' % value,
					listener=listener)
		return list(valid_ids)
	def exists(self, uid=None, login=None):
		if uid:
			return self.users.has_key(uid)
		if login:
			return self.login_cache.has_key(login)

		raise exceptions.BadArgumentError(
			"You must specify an UID or a login to test existence of.")
	def check_password(self, login, password):
		crypted_passwd1 = self.users[
			self.login_cache[login]]['userPassword']
		crypted_passwd2 = self.backends[
			self.users[self.login_cache[login]
				]['backend']].compute_password(password, crypted_passwd1)
		assert ltrace('users', 'comparing 2 crypted passwords:\n%s\n%s' % (
			crypted_passwd1, crypted_passwd2))
		return (crypted_passwd1 == crypted_passwd2)
	def login_to_uid(self, login):
		""" Return the uid of the user 'login' """
		try:
			# use the cache, Luke !
			return self.login_cache[login]
		except KeyError:
			raise exceptions.DoesntExistsException(
				"User %s doesn't exist" % login)
	def uid_to_login(self, uid):
		""" Return the login for an UID, or raise Doesn't exists. """
		try:
			return self.users[uid]['login']
		except KeyError:
			raise exceptions.DoesntExistsException(
				"UID %s doesn't exist" % uid)
	def is_restricted_system_uid(self, uid):
		""" Return true if uid is system, but outside the range of Licorn®
			controlled UIDs."""
		return uid < UsersController.configuration.users.system_uid_min \
			and uid > self.configuration.users.uid_max
	def is_restricted_system_login(self, login):
		""" return true if login is system, but outside the range of Licorn®
			controlled UIDs. """
		try:
			return self.is_restricted_system_uid(
				self.login_cache[login])
		except KeyError:
			raise exceptions.DoesntExistsException(
				logging.SYSU_USER_DOESNT_EXIST % login)
	def is_unrestricted_system_uid(self, uid):
		""" Return true if uid is system, but inside the range of Licorn®
			controlled UIDs."""
		return uid >= self.configuration.users.system_uid_min \
			and uid <= self.configuration.users.system_uid_max
	def is_unrestricted_system_login(self, login):
		""" return true if login is system, but inside the range of Licorn®
			controlled UIDs. """
		try:
			return self.is_unrestricted_system_uid(
				self.login_cache[login])
		except KeyError:
			raise exceptions.DoesntExistsException(
				logging.SYSU_USER_DOESNT_EXIST % login)
	def is_system_uid(self, uid):
		""" Return true if uid is system."""
		return uid < self.configuration.users.uid_min or \
			uid > self.configuration.users.uid_max
	def is_standard_uid(self, uid):
		""" Return true if gid is standard (not system). """
		return uid >= self.configuration.users.uid_min \
			and uid <= self.configuration.users.uid_max
	def is_system_login(self, login):
		""" return true if login is system. """
		try:
			return self.is_system_uid(
				self.login_cache[login])
		except KeyError:
			raise exceptions.DoesntExistsException(
				logging.SYSU_USER_DOESNT_EXIST % login)
	def is_standard_login(self, login):
		""" Return true if login is standard (not system). """
		try:
			return self.is_standard_uid(
				self.login_cache[login])
		except KeyError:
			raise exceptions.DoesntExistsException(
				logging.SYSU_USER_DOESNT_EXIST % login)
	def make_login(self, lastname="", firstname="", inputlogin=""):
		""" Make a valid login from  user's firstname and lastname."""

		if inputlogin == "":
			login = hlstr.validate_name(str(firstname + '.' + lastname),
				maxlenght = self.configuration.users.login_maxlenght)
		else:
			# use provided login and verify it.
			login = hlstr.validate_name(str(inputlogin),
				maxlenght = self.configuration.users.login_maxlenght)

		if not hlstr.cregex['login'].match(login):
			raise exceptions.BadArgumentError(
				"Can't build a valid login (got %s, which doesn't verify %s)"
				" with the firstname/lastname you provided (%s %s)." % (
					login, hlstr.regex['login'], firstname, lastname) )

		# TODO: verify if the login doesn't already exist.
		#while potential in self.users:
		return login
	def primary_gid(self, login=None, uid=None):
		if login:
			return self.users[
				self.login_cache[login]]['primary_gid']
		if uid:
			return self.users[uid]['primary_gid']

		raise exceptions.BadArgumentError(
			"You must specify an UID or a login to get primary_gid of.")
