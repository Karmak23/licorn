# -*- coding: utf-8 -*-
"""
Licorn Shadow backend - http://docs.licorn.org/core/backends/shadow.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2.

.. versionadded:: 1.3
	This backend was previously known as **unix**, but has been
	renamed **shadow** during the 1.2 ⇢ 1.3 development cycle, to
	better match reality and avoid potential name conflicts.
"""

import os, crypt, tempfile

from threading  import Timer
from contextlib import nested

from licorn.foundations           import settings, logging, exceptions
from licorn.foundations           import readers, hlstr, fsapi
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import Singleton, BasicCounter
from licorn.foundations.classes   import FileLock
from licorn.foundations.constants import priorities
from licorn.core                  import LMC
from licorn.core.users            import User
from licorn.core.groups           import Group
from licorn.core.backends         import NSSBackend, UsersBackend, GroupsBackend

class ShadowBackend(Singleton, UsersBackend, GroupsBackend):
	""" A backend to cope with /etc/* UNIX shadow traditionnal files. """

	init_ok = False

	def __init__(self):

		assert ltrace(TRACE_SHADOW, '> __init__(%s)' % ShadowBackend.init_ok)

		if ShadowBackend.init_ok:
			return

		NSSBackend.__init__(self, name='shadow',
			nss_compat=('files', 'compat'), priority=1)

		# the UNIX backend is always enabled on a Linux system.
		# Any better and correctly configured backend should take
		# preference over this one, though.
		self.available = True
		self.enabled   = True

		ShadowBackend.init_ok = True
		assert ltrace(TRACE_SHADOW, '< __init__(%s)' % ShadowBackend.init_ok)
	def initialize(self):
		""" We have to be sure a human error didn't put
			``backends.shadow.enabled = False`` in the configuration, else this
			would lead to I-don't-want-to-know-about problems.

			This initialize method only checks that, because the shadow backend
			must be always enabled.
		"""

		assert ltrace_func(TRACE_SHADOW)

		try:
			if self.name in LMC.configuration.backends.ignore:
				LMC.configuration.backends.ignore.remove(self.name)

			del LMC.configuration.backends.shadow.ignore

		except AttributeError:
			pass
		else:
			logging.warning(_(u'{0} shadow backend (this is important, '
				u'please do not try to set {1} in {2}!').format(
						stylize(ST_IMPORTANT, _(u'RE-enabled')),
						stylize(ST_COMMENT, u'backends.shadow.enabled=False'),
						stylize(ST_PATH, settings.main_config_file)
					)
				)

		self.pslock = FileLock(LMC.configuration, '/etc/passwd')
		self.shlock = FileLock(LMC.configuration, '/etc/shadow')
		self.grlock = FileLock(LMC.configuration, '/etc/group')
		self.gslock = FileLock(LMC.configuration, '/etc/gshadow')
		self.gelock = FileLock(LMC.configuration,
								settings.backends.shadow.extended_group_file)

		# the inotifier hints, to avoid reloading when we write our own files.
		self.__hint_pwd = BasicCounter(1)
		self.__hint_shw = BasicCounter(1)
		self.__hint_grp = BasicCounter(1)
		self.__hint_gsh = BasicCounter(1)

		return self.available
	def load_User(self, user):
		assert ltrace_func(TRACE_SHADOW)

		# NOTE: which is totally ignored in this backend, we always load ALL
		# users, because we always read/write the entire files.

		return self.load_Users()
	def save_User(self, user, mode):
		assert ltrace_func(TRACE_SHADOW)
		return self.save_Users(LMC.users)
	def delete_User(self, user):
		assert ltrace_func(TRACE_SHADOW)
		return self.save_Users(LMC.users)
	def load_Group(self, group):
		""" Load an individual group.

			Default action is to call :meth:`load_Groups`. This is not what
			you want if your backend is able to load groups individually:
			you have to overload this method.

			:param gid: an integer, GID of the group to load (ignored in the
				default implementation which calls :meth:`load_Groups`).
		"""

		assert ltrace_func(TRACE_SHADOW)

		return self.load_Groups()
	def save_Group(self, group, mode):
		""" Save a group in system data.

			Default action is to call
			:meth:`save_Groups()`. This is perfect for backends which
			always rewrite all the data (typically
			:class:`~licorn.core.backends.shadow.ShadowBackend`), but
			it is much a waste or system resources for backends which have
			the ability to save an individual entry without the need to
			write them all (typically
			:class:`~licorn.core.backends.openldap.OpenldapBackend`). The later
			must therefore overload this methodto implement a more appropriate
			behaviour.

			:param gid: the GID of the group to save (ignored in this default
				version of the method.
			:param mode: a value coming from
				:obj:`~licorn.foundations.constants.backends_actions` to
				specify if the save operation is an update or a creation.
		"""

		assert ltrace_func(TRACE_SHADOW)

		return self.save_Groups(LMC.groups)
	def delete_Group(self, group):
		""" Delete an individual group. Default action (coming from abstract
			:class:`~licorn.core.backends.GroupsBackend`) is to call
			:meth:`save_Groups` to save all groups, assuming the group
			you want to delete has already been wiped out the
			:class:`~licorn.core.groups.GroupsController`.

			This behaviour works well for backends which rewrite all
			data everytime (typically
			:class:`~licorn.core.backends.shadow.ShadowBackend`), but won't
			work as expected for backends which must loop through all entries
			to save them individually (typically
			:class:`~licorn.core.backends.openldap.OpenldapBackend`). The later
			must therefore overload this method to implement a more appropriate
			behaviour.

			:param gid: the GID of teh group to delete (ignored in this default
				version of the method).
		"""
		assert ltrace_func(TRACE_SHADOW)
		return self.save_Groups(LMC.groups)
	def load_Users(self):
		""" Load user accounts from /etc/{passwd,shadow} """

		assert ltrace_func(TRACE_SHADOW)

		is_allowed = True
		need_rewriting = False

		with self.shlock:
			try:
				shadow = readers.ug_conf_load_list("/etc/shadow")
			except (OSError, IOError), e:
				if e.errno == 13:
					is_allowed = False
				else:
					raise e

		with self.pslock:
			passwd_data = readers.ug_conf_load_list("/etc/passwd")

		for entry in passwd_data:

			login = entry[0]
			uid   = int(entry[2])

			not_found=True

			for sentry in shadow:
				if sentry[0] == login:
					# "sentry" will remain, to be used in the main loop.
					not_found=False
					break

			if not_found:
				# create a fake shadow entry for the load() to work.
				# this will eventually allow the file to be automatically
				# corrected on next forced write.
				sentry = [ login, '', '0', '0', '99999', '7', '', '', '' ]

				logging.warning(_(u'{0}: added missing entry for user {1} '
					'in {2}.').format(self.pretty_name, stylize(ST_LOGIN, login),
						stylize(ST_PATH, '/etc/shadow')))

				need_rewriting = True

			yield uid, User(
					uidNumber=uid,
					login=login,
					gidNumber=int(entry[3]),
					gecos=entry[4],
					homeDirectory=entry[5],
					loginShell=entry[6],
					userPassword=sentry[1],
					shadowLastChange=int(sentry[2]) if sentry[2] != '' else 0,
					shadowMin=int(sentry[3]) if sentry[3] != '' else 0,
					shadowMax=int(sentry[4]) if sentry[4] != '' else 99999,
					shadowWarning=int(sentry[5]) if sentry[5] != '' else 7,
					shadowInactive=int(sentry[6]) if sentry[6] != '' else 0,
					shadowExpire=int(sentry[7]) if sentry[7] != '' else 0,
					shadowFlag=int(sentry[8]) if sentry[8] != '' else '',
					backend=self
				)

			assert ltrace(TRACE_SHADOW, 'loaded user %s' % entry[0])

		if need_rewriting and is_allowed:
			logging.notice(_(u'{0}: cleaned users data rewrite '
				'requested in the background.').format(self.pretty_name))

			workers.service_enqueue(priorities.NORMAL,
											self.save_Users, LMC.users,
											job_delay=4.0)

		assert ltrace_func(TRACE_SHADOW, True)
	def load_Groups(self):
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		assert ltrace_func(TRACE_SHADOW)

		with self.grlock:
			etc_group = readers.ug_conf_load_list("/etc/group")

		# if some inconsistency is detected during load and it can be corrected
		# automatically, do it now ! This flag is global for all groups, because
		# shadow-backend always rewrite everything (no need for more granularity).
		need_rewriting = False

		extras      = []
		etc_gshadow = []
		is_allowed  = True

		with self.gelock:
			try:
				extras = readers.ug_conf_load_list(
								settings.backends.shadow.extended_group_file)
			except IOError, e:
				if e.errno != 2:
					# other than no such file or directory
					raise e

		with self.gslock:
			try:
				etc_gshadow = readers.ug_conf_load_list("/etc/gshadow")
			except IOError, e:
				if e.errno == 13:
					# don't raise an exception or display a warning, this is
					# harmless if we are loading data for get, and any other
					# operation (add/mod/del) will fail anyway if we are not root
					# or group @admin.
					is_allowed = False
				else:
					raise e

		for entry in etc_group:
			if len(entry) != 4:
				# FIXME: should we really continue ?
				# why not raise CorruptFileError ??
				logging.warning(_(u'{0}: skipped line "{1}" from {2}, '
					'it seems corrupt.').format(self.name,
					stylize(ST_COMMENT, ':'.join(entry)),
					stylize(ST_PATH, '/etc/group')))
				continue

			name = entry[0]
			gid  = int(entry[2])

			if entry[3] == '':
				# the group has currently no members.
				members = []
			else:
				members = entry[3].split(',')

			# TODO: we could load the extras data in another structure before
			# loading groups from /etc/group to avoid this for() loop and just
			# get extras[LMC.groups[gid]['name']] directly. this could gain
			# some time on systems with many groups.
			description = ''
			groupSkel   = ''
			for extra_entry in extras:
				if name == extra_entry[0]:
					try:
						description = extra_entry[1]
						groupSkel   = extra_entry[2]

					except IndexError, e:
						raise exceptions.CorruptFileError(
							settings.backends.shadow.extended_group_file,
							'for group "%s" (was: %s).' %
								(extra_entry[0], str(e)))
					break

			# load data from /etc/gshadow
			not_found = True
			for gshadow_entry in etc_gshadow:
				if name ==  gshadow_entry[0]:
					try:
						userPassword = gshadow_entry[1]

					except IndexError, e:
						# TODO: set need_rewriting = True, construct a good
						# default entry and continue.
						raise exceptions.CorruptFileError("/etc/gshadow",
						'for group "%s" (was: %s).' %
							(gshadow_entry[0], str(e)))
					not_found = False
					break

			if not_found and is_allowed:
				# do some auto-correction stuff if we are able too.
				# this happens if debian tools were used between 2 Licorn CLI
				# calls, or on first call of CLI tools on a Debian system.
				logging.notice(_(u'{0}: added missing record '
					'for group {1} in {2}.').format(self.pretty_name,
						stylize(ST_NAME, name),
						stylize(ST_PATH, '/etc/gshadow')))
				need_rewriting = True

			yield gid, Group(
					gidNumber=gid,
					name=name,
					userPassword=userPassword,
					memberUid=members,
					description=description,
					groupSkel=groupSkel,
					backend=self)

			assert ltrace(TRACE_SHADOW, 'loaded group %s' % name)

		if need_rewriting and is_allowed:
			logging.notice(_(u'{0}: cleaned groups data rewrite '
				'requested in the background.').format(self.pretty_name))

			workers.service_enqueue(priorities.NORMAL,
										self.save_Groups, LMC.groups,
										job_delay=4.5)

		# used at saving time...
		self.__shadow_gid = LMC.groups.by_name('shadow').gidNumber
		assert ltrace_func(TRACE_SHADOW, True)
	def save_Users(self, users):
		""" Write /etc/passwd and /etc/shadow """

		# NOTE: users should already be sorted by UID.

		etcpasswd = []
		etcshadow = []

		# Ensure there are no parallel modifications of users during this
		# phase, take the lock (parallel alterations can occur at least during
		# daemon loading phase, where services are planned with same timers;
		# but there are probably other cases).
		with LMC.users.lock:
			for user in users:
				if user.backend.name != self.name:
					continue

				etcpasswd.append(":".join((
											user.login,
											'x',
											str(user.uidNumber),
											str(user.gidNumber),
											user.gecos,
											user.homeDirectory,
											user.loginShell
										))
								)

				etcshadow.append(":".join((
											user.login,
											user.userPassword,
											str(user.shadowLastChange),
											str(user.shadowMin),
											str(user.shadowMax),
											str(user.shadowWarning),
											'' if user.shadowInactive == 0
												else str(user.shadowInactive),
											'' if user.shadowExpire == 0
												else str(user.shadowExpire),
											str(user.shadowFlag)
										))
								)

		with nested(self.pslock, self.shlock):

			fsapi.backup_file('/etc/passwd')
			fsapi.backup_file('/etc/shadow')

			# for /etc/passwd
			ftempp, fpathp = tempfile.mkstemp(dir='/etc')
			os.write(ftempp, '%s\n' % '\n'.join(etcpasswd))
			os.fchmod(ftempp, 0644)
			os.fchown(ftempp, 0, 0)
			os.close(ftempp)
			self.__hint_pwd += 1
			os.rename(fpathp, '/etc/passwd')

			# for /etc/shadow
			ftemps, fpaths = tempfile.mkstemp(dir='/etc')
			os.write(ftemps, '%s\n' % '\n'.join(etcshadow))
			os.fchmod(ftemps, 0640)
			os.fchown(ftemps, 0, self.__shadow_gid)
			os.close(ftemps)
			self.__hint_shw += 1
			os.rename(fpaths, '/etc/shadow')

		logging.progress(_(u'{0}: saved users data to disk.').format(self.pretty_name))
	def save_Groups(self, groups):
		""" Write the groups data in appropriate system files."""

		assert ltrace_func(TRACE_SHADOW)

		# NOTE: groups should already be sorted on GIDs.

		etcgroup   = []
		etcgshadow = []
		extgroup   = []

		# See :meth:`self.save_Users` to know why we take this lock.
		with LMC.groups.lock:
			for group in groups:
				# don't know why 'group.backend != self' don't work as expected.
				# gotta find it some day.
				if group.backend.name != self.name:
					continue

				etcgroup.append(":".join((
											group.name,
											group.userPassword,
											str(group.gid),
											','.join(group.memberUid)
										))
								)
				etcgshadow.append(":".join((
											group.name,
											group.userPassword,
											'',
											','.join(group.memberUid)
										))
								)
				extgroup.append(':'.join((
											group.name,
											group.description,
											group.groupSkel
												if group.is_standard
												else ''
										))
								)

		with nested(self.grlock, self.gslock, self.gelock):

			ftempg, fpathg = tempfile.mkstemp(dir='/etc')
			os.write(ftempg, '%s\n' % '\n'.join(etcgroup))
			os.fchmod(ftempg, 0644)
			os.fchown(ftempg, 0, 0)
			os.close(ftempg)
			self.__hint_grp += 1
			os.rename(fpathg, '/etc/group')

			ftemps, fpaths = tempfile.mkstemp(dir='/etc')
			os.write(ftemps, '%s\n' % '\n'.join(etcgshadow))
			os.fchmod(ftemps, 0640)
			os.fchown(ftemps, 0, self.__shadow_gid)
			os.close(ftemps)
			self.__hint_gsh += 1
			os.rename(fpaths, '/etc/gshadow')

			ftempe, fpathe = tempfile.mkstemp(dir='/etc')
			os.write(ftempe, '%s\n' % '\n'.join(extgroup))
			os.fchmod(ftempe, 0644)
			os.fchown(ftempe, 0, 0)
			os.close(ftempe)
			os.rename(fpathe, settings.backends.shadow.extended_group_file)

		logging.progress(_(u'{0}: saved groups data to disk.').format(self.pretty_name))

		assert ltrace_func(TRACE_SHADOW, True)
	def compute_password(self, password, salt=None, ascii=False):

		assert ltrace_func(TRACE_SHADOW)

		# In the shadow backend there is no difference between 'ascii' and not.
		return crypt.crypt(password, '$6$%s' % hlstr.generate_salt()
												if salt is None else salt)
	def _inotifier_install_watches(self, inotifier):

		assert ltrace_func(TRACE_SHADOW)

		self.__conffiles_threads = {}

		for watched_file, controller, hint, callback_func in (
				('/etc/passwd',  LMC.users,  self.__hint_pwd, self.__event_on_passwd),
				('/etc/shadow',  LMC.users,  self.__hint_shw, self.__event_on_passwd),
				('/etc/group',   LMC.groups, self.__hint_grp, self.__event_on_group),
				('/etc/gshadow', LMC.groups, self.__hint_gsh, self.__event_on_group)
			):
			inotifier.watch_conf(watched_file, controller, callback_func, hint)
	def __reload_controller_unix(self, path, controller, *args, **kwargs):
		""" Timer() callback for watch threads.
		*args and **kwargs are not used. """

		assert ltrace_func(TRACE_SHADOW)

		logging.notice(_(u'{0}: configuration file {1} changed, '
			'reloading {2} controller.').format(self.pretty_name,
				stylize(ST_PATH, path),
				stylize(ST_NAME, controller.name)))

		controller.reload_backend(self)
	def __event_on_config_file(self, pathname, controller, index):
		""" We only watch GAMCreated events, because when
			{user,group}{add,mod,del} change their files, they create it
			from another, everytime (for atomic reasons). We, in licorn
			overwrite them, and this will generate a GAMChanged event,
			which permits us to distringuish between the different uses.
		"""
		assert ltrace(TRACE_INOTIFIER,
			'conf_file %s change -> reload controller %s (index %s)' % (
				pathname, controller.name, index))

		create_thread = False
		try:
			if self.__conffiles_threads[index].is_alive():
				self.__conffiles_threads[index].cancel()

			self.__conffiles_threads[index].join()
			del self.__conffiles_threads[index]
			create_thread = True

		except (KeyError, AttributeError):
			create_thread = True

		if create_thread:
			self.__conffiles_threads[index] = Timer(0.25,
				self.__reload_controller_unix, [ pathname, controller ])
			self.__conffiles_threads[index].start()
	def __event_on_passwd(self, pathname):
		return self.__event_on_config_file(pathname, LMC.users, 1)
	def __event_on_group(self, pathname):
		return self.__event_on_config_file(pathname, LMC.groups, 2)
