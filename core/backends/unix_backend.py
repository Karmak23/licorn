# -*- coding: utf-8 -*-
"""
Licorn Core LDAP backend.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

from licorn.foundations         import logging, exceptions, styles
from licorn.foundations         import objects, readers
from licorn.foundations.ltrace  import ltrace
from licorn.foundations.objects import UGBackend


class unix_controller(UGBackend):
	""" A backend to cope with /etc/`UNIX traditionnal files (shadow system)."""
	def __init__(self, configuration, users=None, groups=None, warnings=True):
		UGBackend.__init__(self, configuration, users, groups)

		# the UNIX backend is always enabled on a Linux system.
		# Any better and correctly configured backend should take
		# preference over this one, though.
		self.name     = "Unix"
		self.enabled  = True

		# nsswitch compatibility
		self.compat   = ('compat', 'files')
		self.priority = 1

		self.warnings = warnings
	def load_users(self, groups = None):
		""" Load user accounts from /etc/{passwd,shadow} """
		users       = {}
		login_cache = {}

		for entry in readers.ug_conf_load_list("/etc/passwd"):
			temp_user_dict	= {
				'login'        : entry[0],
				'uidNumber'          : int(entry[2]) ,
				'gidNumber'          : int(entry[3]) ,
				'gecos'        : entry[4],
				'homeDirectory': entry[5],
				'loginShell'   : entry[6],
				'groups'       : set(),		# a cache which will
											# eventually be filled by
											# groups.__init__() and others.
				'backend'      : self.name
				}

			# populate ['groups'] ; this code is duplicated in groups.__init__,
			# in case users/groups are loaded in different orders.
			if groups is not None:
				for g in groups.groups:
					for member in groups.groups[g]['memberUid']:
						if member == entry[0]:
							temp_user_dict['groups'].add(
								groups.groups[g]['name'])

			# implicitly index accounts on « int(uidNumber) »
			users[ temp_user_dict['uidNumber'] ] = temp_user_dict

			# this will be used as a cache for login_to_uid()
			login_cache[ entry[0] ] = temp_user_dict['uidNumber']

		try:
			for entry in readers.ug_conf_load_list("/etc/shadow"):
				if login_cache.has_key(entry[0]):
					uid = login_cache[entry[0]]
					users[uid]['userPassword'] = entry[1]
					if entry[1][0] == '!':
						users[uid]['locked'] = True
						# the shell could be /bin/bash (or else), this is valid
						# for system accounts, and for a standard account this
						# means it is not strictly locked because SSHd will
						# bypass password check if using keypairs...
						# don't bork with a warning, this doesn't concern us
						# (Licorn work 99% of time on standard accounts).
					else:
						users[uid]['locked'] = False

					if entry[2] == "":
						users[uid]['shadowLastChange']  = 0
					else:
						users[uid]['shadowLastChange']  = int(entry[2])

					if entry[3] == "":
						users[uid]['shadowInactive'] = 99999
					else:
						users[uid]['shadowInactive'] = int(entry[3])

					if entry[4] == "":
						users[uid]['shadowWarning']  = entry[4]
					else:
						users[uid]['shadowWarning']  = int(entry[4])

					if entry[5] == "":
						users[uid]['shadowExpire'] = entry[5]
					else:
						users[uid]['shadowExpire'] = int(entry[5])

					# Note:
					# the 7th field doesn't seem to be used by passwd(1) nor by
					# usermod(8) and thus raises en exception because it's empty
					# in 100% of cases.
					# → temporarily disabled until we use it internally.
					#
					#     users[uid]['last_lock_date']      = int(entry[6])
				else:
					logging.warning(
					"non-existing user '%s' referenced in /etc/shadow." % \
						entry[0])

		except (OSError, IOError), e:
			if e.errno != 13:
				raise e
				# don't raise an exception or display a warning, this is
				# harmless if we are loading data for get, and any other
				# operation (add/mod/del) will fail anyway if we are not root
				# or group @admin.

		return users, login_cache
	def load_groups(self):
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		ltrace('unix', '> load_groups()')

		groups     = {}
		name_cache = {}
		etc_group = readers.ug_conf_load_list("/etc/group")

		# if some inconsistency is detected during load and it can be corrected
		# automatically, do it now ! This flag is global for all groups, because
		# unix-backend always rewrite everything (no need for more granularity).
		need_rewriting = False

		extras      = []
		etc_gshadow = []
		is_allowed  = True
		try:
			extras = readers.ug_conf_load_list(
				UGBackend.configuration.extendedgroup_data_file)
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

		if UGBackend.users:
			l2u = UGBackend.users.login_to_uid
			u   = UGBackend.users.users

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
				members = set()
			else:
				members   = set(entry[3].split(','))
				to_remove = set()

				# update the cache to avoid massive CPU load in 'get users
				# --long'. This code is also present in users.__init__, to cope
				# with users/groups load in different orders.
				if UGBackend.users:
					for member in members:
						if UGBackend.users.login_cache.has_key(member):
							u[l2u(member)]['groups'].add(entry[0])
						else:
							if self.warnings:
								logging.warning("User %s is referenced in " \
									"members of group %s but doesn't really " \
									"exist on the system, removing it." % \
									(styles.stylize(styles.ST_BAD, member),
									styles.stylize(styles.ST_NAME, entry[0])))
							# don't directly remove member from members,
							# it will immediately stop the for_loop.
							to_remove.append(member)

					if to_remove != set():
						need_rewriting = True
						for member in to_remove:
							members.remove(member)

			groups[gid] = 	{
				'name'        : entry[0],
				'passwd'      : entry[1],
				'gidNumber'   : gid,
				'memberUid'   : members,
				'description' :  "" ,
				'groupSkel'   :  "" ,
				'permissive'  : None,
				'backend'     : self.name
				}

			# this will be used as a cache by name_to_gid()
			name_cache[ entry[0] ] = gid

			try:
				groups[gid]['permissive'] = UGBackend.groups.is_permissive(
					name=groups[gid]['name'], gid = gid)
			except exceptions.InsufficientPermissionsError:
				# don't bother the user with a warning, he/she probably already
				# knows that :
				# logging.warning("You don't have enough permissions to " \
				#	"display permissive states.", once = True)
				pass

			# TODO: we could load the extras data in another structure before
			# loading groups from /etc/group to avoid this for() loop and just
			# get extras[self.groups[gid]['name']] directly. this could gain
			# some time on systems with many groups.

			extra_found = False
			for extra_entry in extras:
				if groups[gid]['name'] ==  extra_entry[0]:
					try:
						groups[gid]['description'] = extra_entry[1]
						groups[gid]['groupSkel']        = extra_entry[2]
					except IndexError, e:
						raise exceptions.CorruptFileError(
							UGBackend.configuration.extendedgroup_data_file, \
							'''for group "%s" (was: %s).''' % \
							(extra_entry[0], str(e)))
					extra_found = True
					break

			if not extra_found:
				logging.notice('added missing record for group %s in %s.' % \
					(
					styles.stylize(styles.ST_NAME, groups[gid]['name']),
					styles.stylize(styles.ST_PATH,
					UGBackend.configuration.extendedgroup_data_file)
					))
				need_rewriting = True
				groups[gid]['description'] = ""
				groups[gid]['groupSkel']        = ""

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
						styles.stylize(styles.ST_NAME, groups[gid]['name']),
						styles.stylize(styles.ST_PATH, '/etc/gshadow')
					))
				need_rewriting = True
				groups[gid]['userPassword'] = 'x'

		if need_rewriting and is_allowed:
			try:
				self.save_groups()
			except (OSError, IOError), e:
				if self.warnings:
					logging.warning("licorn.core.groups: can't correct" \
					" inconsistencies (was: %s)." % e)

		return groups, name_cache
	def save_users(self):
		""" Write /etc/passwd and /etc/shadow """

		lock_etc_passwd = objects.FileLock(
			UGBackend.configuration, "/etc/passwd")
		lock_etc_shadow = objects.FileLock(
			UGBackend.configuration, "/etc/shadow")

		etcpasswd = []
		etcshadow = []
		users = UGBackend.users
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
										str(users[uid]['shadowInactive']),
										str(users[uid]['shadowWarning']),
										str(users[uid]['shadowExpire']),
										"","",""
									))
							)

		lock_etc_passwd.Lock()
		open("/etc/passwd" , "w").write("%s\n" % "\n".join(etcpasswd))
		lock_etc_passwd.Unlock()

		lock_etc_shadow.Lock()
		open("/etc/shadow" , "w").write("%s\n" % "\n".join(etcshadow))
		lock_etc_shadow.Unlock()
	def save_groups(self):
		""" Write the groups data in appropriate system files."""

		groups = UGBackend.groups

		#
		# FIXME: this will generate a false positive if groups[0] comes from LDAP...
		#
		if not groups[0].has_key('userPassword'):
			raise exceptions.InsufficientPermissionsError("You are not root" \
				" or member of the shadow group," \
				" can't write configuration data.")

		lock_etc_group   = objects.FileLock(UGBackend.configuration,
												"/etc/group")
		lock_etc_gshadow = objects.FileLock(UGBackend.configuration,
												"/etc/gshadow")
		lock_ext_group   = objects.FileLock(UGBackend.configuration,
								UGBackend.configuration.extendedgroup_data_file)

		logging.progress("Writing groups configuration to disk...")

		etcgroup   = []
		etcgshadow = []
		extgroup   = []

		gids = groups.keys()
		gids.sort()

		for gid in gids:
			if groups[gid]['backend'] != self.name:
				continue
			# logging.debug2("Writing group %s (%s)." % (groups[gid]['name'],
			#  groups[gid]))

			etcgroup.append(":".join((
										groups[gid]['name'],
										groups[gid]['passwd'],
										str(gid),
										','.join(groups[gid]['memberUid'])
									))
							)
			etcgshadow.append(":".join((
										groups[gid]['name'],
										groups[gid]['userPassword'],
										"",
										','.join(groups[gid]['memberUid'])
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
		open(UGBackend.configuration.extendedgroup_data_file, "w").write(
			"\n".join(extgroup) + "\n")
		lock_ext_group.Unlock()

		logging.progress("Done writing groups configuration.")
	def save_user(self, uid):
		""" Just a wrapper. Saving one user in Unix backend is not significantly
		faster than saving all of them. """
		self.save_users()
	def save_group(self, gid):
		""" Just a wrapper. Saving one group in Unix backend is not
		significantly faster than saving all of them. """
		self.save_groups()
	def delete_user(self, uid):
		""" Just a wrapper. Deleting one user in Unix backend is not significantly
		faster than saving all of them. """
		self.save_users()
	def delete_group(self, gid):
		""" Just a wrapper. Deleting one group in Unix backend is not
		significantly faster than saving all of them. """
		self.save_groups()
