# -*- coding: utf-8 -*-
"""
Licorn Core LDAP backend.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

from licorn.foundations         import logging, exceptions, styles, file_locks
from licorn.core.internals      import readers
from licorn.foundations.objects import UGBackend

class unix_backend(UGBackend) :
	def __init__(self, configuration, users = None, groups = None) :
		UGBackend.__init__(self, configuration, users, groups)
		self.enabled = True
		self.name    = "Unix"
	def load_users(self, groups = None) :
		""" Load user accounts from /etc/{passwd,shadow} """
		users       = {}
		login_cache = {}

		for entry in readers.ug_conf_load_list("/etc/passwd") :
			temp_user_dict	= {
				'login'         : entry[0],
				'uid'           : int(entry[2]) ,
				'gid'           : int(entry[3]) ,
				'gecos'         : entry[4],
				'homeDirectory' : entry[5],
				'loginShell'    : entry[6],
				'groups'        : set()              # a cache which will eventually be filled by groups.__init__() and others.
				}

			# populate ['groups'] ; this code is duplicated in groups.__init__, in case users/groups are loaded in different orders.
			if groups is not None :
				for g in groups.groups :
					for member in groups.groups[g]['members'] :
						if member == entry[0] :
							temp_user_dict['groups'].add(groups.groups[g]['name'])

			# implicitly index accounts on « int(uid) »
			users[ temp_user_dict['uid'] ] = temp_user_dict
			
			# this will be used as a cache for login_to_uid()
			login_cache[ entry[0] ] = temp_user_dict['uid']
		
		try :
			for entry in readers.ug_conf_load_list("/etc/shadow") :
				if login_cache.has_key(entry[0]) :
					uid = login_cache[entry[0]]
					users[uid]['crypted_password'] = entry[1]
					if entry[1][0] == '!' :
						users[uid]['locked'] = True
						# the shell could be /bin/bash (or else), this is valid for system accounts,
						# and for a standard account this means it is not strictly locked because SSHd
						# will bypass password check if using keypairs...
						# don't bork with a warning, this doesn't concern us (Licorn work 99% of time on
						# standard accounts).
					else :
						users[uid]['locked'] = False
					
					if entry[2] == "" :
						entry[2] = 0
					users[uid]['passwd_last_change']  = int(entry[2])
					if entry[3] == "" :
						entry[3] = 99999
					users[uid]['passwd_expire_delay'] = int(entry[3])
					if entry[4] == "" :
						users[uid]['passwd_expire_warn']  = entry[4]
					else :
						users[uid]['passwd_expire_warn']  = int(entry[4])
					if entry[5] == "" :
						users[uid]['passwd_account_lock'] = entry[5]
					else :
						users[uid]['passwd_account_lock'] = int(entry[5])

					# Note: 
					# the 7th field doesn't seem to be used by passwd(1) nor by usermod(8)
					# and thus raises en exception because it's empty in 100% of cases.
					# → temporarily disabled until we use it internally.
					#
					#users[uid]['last_lock_date']      = int(entry[6])
				else :
					logging.warning("non-existing user '%s' referenced in /etc/shadow." % entry[0])
				
		except (OSError,IOError), e :
			if e.errno != 13 :
				raise e
				# don't raise an exception or display a warning, this is harmless if we
				# are loading data for getent, and any other operation (add/mod/del) will
				# fail anyway if we are not root or @admin.

		return users, login_cache

	def load_groups(self) :
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		groups     = {}
		name_cache = {}
		etc_group = readers.ug_conf_load_list("/etc/group")

		# if some inconsistency is detected during load and it can be corrected automatically, do it !
		need_rewriting = False

		extras      = []
		etc_gshadow = []
		is_allowed  = True
		try :
			extras      = readers.ug_conf_load_list(self.configuration.extendedgroup_data_file)
		except IOError, e :
			if e.errno != 2 : raise e # no such file
		try :
			etc_gshadow = readers.ug_conf_load_list("/etc/gshadow")
		except IOError, e :
			if e.errno == 13 :
				# don't raise an exception or display a warning, this is harmless if we
				# are loading data for getent, and any other operation (add/mod/del) will
				# fail anyway if we are not root or @admin.
				is_allowed = False
			else : raise e 

		if self.users :
			l2u   = self.users.login_to_uid
			users = self.users.users

		# TODO: transform this in 'for (gname, gid, gpass, gmembers) in etc_group :'

		for entry in etc_group :
			if len(entry) != 4 : continue # why continue ? why not raise CorruptFileError ??
			
			# implicitly index accounts on « int(gid) »
			gid = int(entry[2])
			
			if entry[3] == '' :
				# this happends when the group has no members.
				members = []
			else :
				members   = entry[3].split(',')
				to_remove = []
				
				# update the cache to avoid massive CPU load in getent users --long
				# this code is also present in users.__init__, to cope with users/groups load
				# in different orders.
				if self.users :
					for member in members :
						if self.users.login_cache.has_key(member) :
							self.users.users[l2u(member)]['groups'].add(entry[0])
						else :
							if self.warnings :
								logging.warning("User %s is referenced in members of group %s but doesn't really exist on the system, removing it." % (styles.stylize(styles.ST_BAD, member), styles.stylize(styles.ST_NAME,entry[0])))
							# don't directly remove member from members, 
							# it will immediately stop the for_loop.
							to_remove.append(member)

					if to_remove != [] :
						need_rewriting = True
						for member in to_remove :
							members.remove(member)

			groups[gid] = 	{
				'name' 			 : entry[0],
				'passwd'		 : entry[1],
				'gid'			 : gid,
				'members'		 : members,
				'description'	 :  "" ,
				'skel'			 :  "" ,
				'permissive'     : None
				}
			
			# this will be used as a cache by name_to_gid()
			name_cache[ entry[0] ] = gid

			try :
				groups[gid]['permissive'] = self.groups.is_permissive(name = groups[gid]['name'], gid = gid)
			except exceptions.InsufficientPermissionsError :
				#logging.warning("You don't have enough permissions to display permissive states.", once = True)
				pass

			#
			# TODO : we could load the extras data in another structure before loading groups from /etc/group
			# to avoid this for() loop and just get extras[self.groups[gid]['name']] directly. this could
			# gain some time on systems with many groups.
			#

			extra_found = False
			for extra_entry in extras :
				if groups[gid]['name'] ==  extra_entry[0] :
					try :
						groups[gid]['description'] = extra_entry[1]
						groups[gid]['skel']        = extra_entry[2]
					except IndexError, e :
						raise exceptions.CorruptFileError(self.configuration.extendedgroup_data_file, '''for group "%s" (was: %s).''' % (extra_entry[0], str(e)))
					extra_found = True
					break

			if not extra_found :
				logging.warning('added missing %s record for group %s.' % (styles.stylize(styles.ST_PATH, self.configuration.extendedgroup_data_file), styles.stylize(styles.ST_NAME, groups[gid]['name'])))
				need_rewriting = True
				groups[gid]['description'] = ""
				groups[gid]['skel']        = ""
					
			gshadow_found = False
			for gshadow_entry in etc_gshadow :
				if groups[gid]['name'] ==  gshadow_entry[0] :
					try :
						groups[gid]['crypted_password'] = gshadow_entry[1]
					except IndexError, e :
						raise exceptions.CorruptFileError("/etc/gshadow", '''for group "%s" (was: %s).''' % (extra_entry[0], str(e)))
					gshadow_found = True
					break

			if not gshadow_found and is_allowed : 
				# do some auto-correction stuff if we are able too.
				# this happens if debian tools were used between 2 Licorn CLI calls, 
				# or on first call of CLI tools on a Debian/Ubuntu system.
				logging.warning('added missing %s record for group %s.' 
					% ( styles.stylize(styles.ST_PATH, '/etc/gshadow'), 
						styles.stylize(styles.ST_NAME, groups[gid]['name'])))
				need_rewriting = True
				groups[gid]['crypted_password'] = 'x'

		if need_rewriting and is_allowed :
			try :
				self.save_groups(groups)
			except (OSError, IOError), e :
				if self.warnings :
					logging.warning("licorn.core.groups: can't correct inconsistencies (was: %s)." % e)

		return groups, name_cache

	def save_all(self, users, groups) :
		self.save_users(users)
		self.save_groups(groups)

	def save_users(self, users) :
		""" Write /etc/passwd and /etc/shadow """

		lock_etc_passwd = file_locks.FileLock(self.configuration, "/etc/passwd")
		lock_etc_shadow = file_locks.FileLock(self.configuration, "/etc/shadow")
		
		etcpasswd = []
		etcshadow = []
		uids = users.keys()
		uids.sort()

		if not users[0].has_key('crypted_password') :
			logging.error('Insufficient permissions to write system configuration files.')

		for uid in uids :
			etcpasswd.append(":".join((
										users[uid]['login'],
										"x",
										str(uid),
										str(users[uid]['gid']),
										users[uid]['gecos'],
										users[uid]['homeDirectory'],
										users[uid]['loginShell']
									))
							)
							
			etcshadow.append(":".join((
										users[uid]['login'],
										users[uid]['crypted_password'],
										str(users[uid]['passwd_last_change']),
										str(users[uid]['passwd_expire_delay']),
										str(users[uid]['passwd_expire_warn']),
										str(users[uid]['passwd_account_lock']),
										"","",""
									))
							)
		
		lock_etc_passwd.Lock()
		open("/etc/passwd" , "w").write("%s\n" % "\n".join(etcpasswd))
		lock_etc_passwd.Unlock()
		
		lock_etc_shadow.Lock()
		open("/etc/shadow" , "w").write("%s\n" % "\n".join(etcshadow))
		lock_etc_shadow.Unlock()

	def save_groups(self, groups) :
		""" Write the groups data in appropriate system files."""

		if not groups[0].has_key('crypted_password') :
			logging.error("You are not root or member of the shadow group, can't write configuration data.")
		
		lock_etc_group   = file_locks.FileLock(self.configuration, "/etc/group")
		lock_etc_gshadow = file_locks.FileLock(self.configuration, "/etc/gshadow")
		lock_ext_group   = file_locks.FileLock(self.configuration,
			self.configuration.extendedgroup_data_file)

		logging.progress("Writing groups configuration to disk...")
		
		etcgroup   = []
		etcgshadow = []
		extgroup   = []

		gids = groups.keys()
		gids.sort()

		for gid in gids :
			#logging.debug2("Writing group %s (%s)." % (groups[gid]['name'], groups[gid]))

			etcgroup.append(":".join((
										groups[gid]['name'],
										groups[gid]['passwd'],
										str(gid),
										','.join(groups[gid]['members'])
									))
							)
			etcgshadow.append(":".join((
										groups[gid]['name'],
										groups[gid]['crypted_password'],
										"",
										','.join(groups[gid]['members'])
									))
							)
			extgroup.append(':'.join((
										groups[gid]['name'],
										groups[gid]['description'],
										groups[gid]['skel']
									))
							)

		lock_etc_group.Lock()
		open("/etc/group", "w").write("\n".join(etcgroup) + "\n")
		lock_etc_group.Unlock()

		lock_etc_gshadow.Lock()
		open("/etc/gshadow", "w").write("\n".join(etcgshadow) + "\n")
		lock_etc_gshadow.Unlock()

		lock_ext_group.Lock()
		open(self.configuration.extendedgroup_data_file, "w").write("\n".join(extgroup) + "\n")
		lock_ext_group.Unlock()

		logging.progress("Done writing groups configuration.")
