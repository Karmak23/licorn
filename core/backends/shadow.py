# -*- coding: utf-8 -*-
"""
Licorn Shadow backend - http://docs.licorn.org/core/backends/shadow.html

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import crypt

from licorn.foundations         import logging, exceptions
from licorn.foundations         import readers, hlstr
from licorn.foundations.styles  import *
from licorn.foundations.ltrace  import ltrace
from licorn.foundations.base    import Singleton
from licorn.foundations.classes import FileLock

from licorn.core                import LMC
from licorn.core.backends       import NSSBackend, UsersBackend, GroupsBackend

class ShadowBackend(Singleton, UsersBackend, GroupsBackend):
	""" A backend to cope with /etc/* UNIX shadow traditionnal files.

		.. versionadded:: 1.3
			This backend was previously known as **unix**, but has been
			renamed **shadow** during the 1.2 ⇢ 1.3 development cycle, to
			better match reality and avoid potential name conflicts.

	"""

	init_ok = False

	def __init__(self):

		assert ltrace('shadow', '> __init__(%s)' % ShadowBackend.init_ok)

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
		assert ltrace('shadow', '< __init__(%s)' % ShadowBackend.init_ok)
	def load_Users(self):
		""" Load user accounts from /etc/{passwd,shadow} """

		assert ltrace('shadow', '> load_Users()')

		users       = {}
		login_cache = {}

		for entry in readers.ug_conf_load_list("/etc/passwd"):
			temp_user_dict	= {
				'login'        : entry[0],
				'uidNumber'    : int(entry[2]) ,
				'gidNumber'    : int(entry[3]) ,
				'gecos'        : entry[4],
				'homeDirectory': entry[5],
				'loginShell'   : entry[6],
				'groups'       : [],		# a cache which will
											# eventually be filled by
											# load_groups().
				'backend'      : self.name
				}

			# implicitly index accounts on « int(uidNumber) »
			users[ temp_user_dict['uidNumber'] ] = temp_user_dict

			# this will be used as a cache for login_to_uid()
			login_cache[ entry[0] ] = temp_user_dict['uidNumber']

			assert ltrace('shadow', 'loaded user %s' %
				users[temp_user_dict['uidNumber']])

		try:
			for entry in readers.ug_conf_load_list("/etc/shadow"):
				if login_cache.has_key(entry[0]):
					uid = login_cache[entry[0]]
					users[uid]['userPassword'] = entry[1]
					if entry[1] != "":
						if entry[1][0] == '!':
							users[uid]['locked'] = True
							# the shell could be /bin/bash (or else), this is valid
							# for system accounts, and for a standard account this
							# means it is not strictly locked because SSHd will
							# bypass password check if using keypairs…
							# don't bork with a warning, this doesn't concern us
							# (Licorn work 99% of time on standard accounts).
						else:
							users[uid]['locked'] = False

					users[uid]['shadowLastChange']  = int(entry[2]) \
						if entry[2] != '' else 0

					users[uid]['shadowMin'] = int(entry[3]) \
						if entry[3] != '' else 0

					users[uid]['shadowMax'] = int(entry[4]) \
						if entry[4] != '' else 99999

					users[uid]['shadowWarning']  = int(entry[5]) \
						if entry[5] != '' else 7

					users[uid]['shadowInactive'] = int(entry[6]) \
						if entry[6] != '' else ''

					users[uid]['shadowExpire'] = int(entry[7]) \
						if entry[7] != '' else ''

					# reserved field, not used yet
					users[uid]['shadowFlag'] = int(entry[8]) \
						if entry[8] != '' else ''

				else:
					logging.warning(
					"non-existing user '%s' referenced in /etc/shadow." % \
						entry[0])

		except (OSError, IOError), e:
			if e.errno == 13:
				# don't display a warning on error 13 (permission denied), this
				# is harmless if we are loading data for get, and any other
				# operation (add/mod/del) will fail anyway if we are not root
				# or group @admins/@shadow.
				assert ltrace('shadow', '''can't load /etc/shadow (perhaps you are '''
					'''not root or a member of group shadow.''')
			else:
				raise e

		assert ltrace('shadow', '< load_users()')
		return users, login_cache
	def load_Groups(self):
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		assert ltrace('shadow', '> load_Group()')

		groups     = {}
		name_cache = {}
		etc_group = readers.ug_conf_load_list("/etc/group")

		# if some inconsistency is detected during load and it can be corrected
		# automatically, do it now ! This flag is global for all groups, because
		# shadow-backend always rewrite everything (no need for more granularity).
		need_rewriting = False

		extras      = []
		etc_gshadow = []
		is_allowed  = True
		try:
			extras = readers.ug_conf_load_list(
				LMC.configuration.extendedgroup_data_file)
		except IOError, e:
			if e.errno != 2:
				# other than no such file or directory
				raise e
		try:
			etc_gshadow = readers.ug_conf_load_list("/etc/gshadow")
		except IOError, e:
			if e.errno == 13:
				# don't raise an exception or display a warning, this is
				# harmless if we are loading data for get, and any other
				# operation (add/mod/del) will fail anyway if we are not root
				# or group @admin.
				is_allowed = False
			else: raise e

		l2u = LMC.users.login_to_uid
		u   = LMC.users

		# TODO: move this to 'for(gname, gid, gpass, gmembers) in etc_group:'

		for entry in etc_group:
			if len(entry) != 4:
				# FIXME: should we really continue ?
				# why not raise CorruptFileError ??
				continue

			# implicitly index accounts on « int(gid) »
			gid = int(entry[2])

			if entry[3] == '':
				# this happends when the group has no members.
				members = []
			else:
				members   = entry[3].split(',')
				members.sort() # catch users modifications outside Licorn

				# update the cache to avoid brute double loops when calling
				# 'get users --long'.
				uids_to_sort=[]
				for member in members:
					if LMC.users.login_cache.has_key(member):
						cache_uid=l2u(member)
						if entry[0] not in u[cache_uid]['groups']:
							u[cache_uid]['groups'].append(entry[0])
							uids_to_sort.append(cache_uid)
				for cache_uid in uids_to_sort:
					# sort the users, but one time only for each.
					u[cache_uid]['groups'].sort()
				del uids_to_sort

			groups[gid] = 	{
				'name'         : entry[0],
				'userPassword' : entry[1],
				'gidNumber'    : gid,
				'memberUid'    : members,
				'description'  : "",
				'groupSkel'    : "",
				'permissive'   : None,
				'backend'      : self.name
				}

			assert ltrace('shadow', 'loaded group %s' % groups[gid])

			# this will be used as a cache by name_to_gid()
			name_cache[entry[0]] = gid

			try:
				groups[gid]['permissive'] = LMC.groups.is_permissive(
					gid=gid, name=entry[0])
			except exceptions.InsufficientPermissionsError:
				# don't bother the user with a warning, he/she probably already
				# knows that :
				# logging.warning("You don't have enough permissions to " \
				#	"display permissive states.", once = True)
				pass

			# TODO: we could load the extras data in another structure before
			# loading groups from /etc/group to avoid this for() loop and just
			# get extras[LMC.groups[gid]['name']] directly. this could gain
			# some time on systems with many groups.

			for extra_entry in extras:
				if groups[gid]['name'] ==  extra_entry[0]:
					try:
						groups[gid]['description'] = extra_entry[1]
						groups[gid]['groupSkel']   = extra_entry[2]
					except IndexError, e:
						raise exceptions.CorruptFileError(
							LMC.configuration.extendedgroup_data_file, \
							'''for group "%s" (was: %s).''' % \
							(extra_entry[0], str(e)))
					break

			gshadow_found = False
			for gshadow_entry in etc_gshadow:
				if groups[gid]['name'] ==  gshadow_entry[0]:
					try:
						groups[gid]['userPassword'] = gshadow_entry[1]
					except IndexError, e:
						raise exceptions.CorruptFileError("/etc/gshadow",
						'''for group "%s" (was: %s).''' % \
						(gshadow_entry[0], str(e)))
					gshadow_found = True
					break

			if not gshadow_found and is_allowed:
				# do some auto-correction stuff if we are able too.
				# this happens if debian tools were used between 2 Licorn CLI
				# calls, or on first call of CLI tools on a Debian system.
				logging.notice('added missing record for group %s in %s.'
					% (
						stylize(ST_NAME, groups[gid]['name']),
						stylize(ST_PATH, '/etc/gshadow')
					))
				need_rewriting = True

		if need_rewriting and is_allowed:
			try:
				self.save_Groups()
			except (OSError, IOError), e:
				logging.warning("licorn.core.groups: can't correct" \
					" inconsistencies (was: %s)." % e)

		return groups, name_cache
	def save_Users(self):
		""" Write /etc/passwd and /etc/shadow """

		lock_etc_passwd = FileLock(
			LMC.configuration, "/etc/passwd")
		lock_etc_shadow = FileLock(
			LMC.configuration, "/etc/shadow")

		etcpasswd = []
		etcshadow = []
		users = LMC.users
		uids = users.keys()
		uids.sort()

		if not users[0].has_key('userPassword'):
			logging.warning('Insufficient permissions to write config files.')
			return

		for uid in uids:
			if users[uid]['backend'] != self.name:
				continue

			etcpasswd.append(":".join((
										users[uid]['login'],
										"x",
										str(uid),
										str(users[uid]['gidNumber']),
										users[uid]['gecos'],
										users[uid]['homeDirectory'],
										users[uid]['loginShell']
									))
							)

			etcshadow.append(":".join((
										users[uid]['login'],
										users[uid]['userPassword'],
										str(users[uid]['shadowLastChange']),
										str(users[uid]['shadowMin']),
										str(users[uid]['shadowMax']),
										str(users[uid]['shadowWarning']),
										str(users[uid]['shadowInactive']),
										str(users[uid]['shadowExpire']),
										str(users[uid]['shadowFlag'])
									))
							)

		lock_etc_passwd.Lock()
		open("/etc/passwd" , "w").write("%s\n" % "\n".join(etcpasswd))
		lock_etc_passwd.Unlock()

		lock_etc_shadow.Lock()
		open("/etc/shadow" , "w").write("%s\n" % "\n".join(etcshadow))
		lock_etc_shadow.Unlock()

		logging.progress("Saved shadow users data to disk.")

	def save_Groups(self):
		""" Write the groups data in appropriate system files."""

		assert ltrace('shadow', '> save_groups()')

		groups = LMC.groups

		#
		# FIXME: this will generate a false positive if groups[0] comes from LDAP…
		#
		if not groups[0].has_key('userPassword'):
			raise exceptions.InsufficientPermissionsError("You are not root" \
				" or member of the shadow group," \
				" can't write configuration data.")

		lock_etc_group   = FileLock(LMC.configuration,
												"/etc/group")
		lock_etc_gshadow = FileLock(LMC.configuration,
												"/etc/gshadow")
		lock_ext_group   = FileLock(LMC.configuration,
								LMC.configuration.extendedgroup_data_file)

		etcgroup   = []
		etcgshadow = []
		extgroup   = []

		gids = groups.keys()
		gids.sort()

		for gid in gids:
			if groups[gid]['backend'] != self.name:
				continue
			# assert logging.debug2("Writing group %s (%s)." % (groups[gid]['name'],
			#  groups[gid]))

			members = [ x for x in groups[gid]['memberUid']]
			members.sort()

			etcgroup.append(":".join((
										groups[gid]['name'],
										groups[gid]['userPassword'],
										str(gid),
										','.join(members)
									))
							)
			etcgshadow.append(":".join((
										groups[gid]['name'],
										groups[gid]['userPassword'],
										"",
										','.join(members)
									))
							)
			extgroup.append(':'.join((
										groups[gid]['name'],
										groups[gid]['description'],
										groups[gid]['groupSkel']
									))
							)

		lock_etc_group.Lock()
		open("/etc/group", "w").write("\n".join(etcgroup) + "\n")
		lock_etc_group.Unlock()

		lock_etc_gshadow.Lock()
		open("/etc/gshadow", "w").write("\n".join(etcgshadow) + "\n")
		lock_etc_gshadow.Unlock()

		lock_ext_group.Lock()
		open(LMC.configuration.extendedgroup_data_file, "w").write(
			"\n".join(extgroup) + "\n")
		lock_ext_group.Unlock()

		logging.progress("Saved shadow groups data to disk.")

		assert ltrace('shadow', '< save_groups()')
	def compute_password(self, password, salt=None):
		assert ltrace('shadow', '| compute_password(%s, %s)' % (password, salt))
		return crypt.crypt(password, '$6$%s' % hlstr.generate_salt() \
			if salt is None else salt)
		#return '$6$' + hashlib.sha512(password).hexdigest()
