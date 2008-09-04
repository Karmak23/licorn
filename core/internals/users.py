# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2007 Olivier Cortès <oc@5sys.fr>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""

import os, crypt, sys
from time import time, strftime, gmtime

from licorn.foundations    import logging, exceptions, process, hlstr, pyutils, file_locks, styles, fsapi
from licorn.core.internals import readers

class UsersList :

	users        = None # (dictionary)
	login_cache  = None # (dictionary)

	# cross-references to other common objects
	configuration = None # (LicornConfiguration)
	profiles      = None # (ProfilesList)
	groups        = None # (GroupsList)

	# Filters for Select() method.
	FILTER_STANDARD = 1
	FILTER_SYSTEM   = 2

	def __init__(self, configuration) :
		""" Create the user accounts list from the underlying system.
			The arguments are None only for getent (ie Export and ExportXml)
		"""

		if UsersList.configuration is None :
			UsersList.configuration = configuration

		# see Select()
		self.filter_applied = False
		
		if UsersList.users is None :
			self.reload()
	def reload(self) :
		""" Load (or reload) the data structures from the system files. """
		UsersList.users       = {}
		UsersList.login_cache = {}

		def import_user_from_etc_passwd(entry) :
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
			if UsersList.groups :
				for g in UsersList.groups.groups :
					for member in UsersList.groups.groups[g]['members'] :
						if member == entry[0] :
							temp_user_dict['groups'].add(UsersList.groups.groups[g]['name'])

			# implicitly index accounts on « int(uid) »
			UsersList.users[ temp_user_dict['uid'] ] = temp_user_dict
			# this will be used as a cache for login_to_uid()
			UsersList.login_cache[ entry[0] ] = temp_user_dict['uid']
		def import_user_from_etc_shadow(entry) :
			try :
				uid = UsersList.login_to_uid(entry[0])
			except exceptions.LicornException, e :
				logging.warning("/etc/shadow seems to be corrupted: %s." % e)
				return
			
			UsersList.users[uid]['crypted_password']    = entry[1]
			if entry[1][0] == '!' :
				UsersList.users[uid]['locked'] = True
				# the shell could be /bin/bash (or else), this is valid for system accounts,
				# and for a standard account this means it is not strictly locked because SSHd
				# will bypass password check if using keypairs...
				# don't bork with a warning, this doesn't concern us (Licorn work 99% of time on
				# standard accounts).
			else :
				UsersList.users[uid]['locked'] = False
			
			if entry[2] == "" :
				entry[2] = 0
			UsersList.users[uid]['passwd_last_change']  = int(entry[2])
			if entry[3] == "" :
				entry[3] = 99999
			UsersList.users[uid]['passwd_expire_delay'] = int(entry[3])
			if entry[4] == "" :
				UsersList.users[uid]['passwd_expire_warn']  = entry[4]
			else :
				UsersList.users[uid]['passwd_expire_warn']  = int(entry[4])
			if entry[5] == "" :
				UsersList.users[uid]['passwd_account_lock'] = entry[5]
			else :
				UsersList.users[uid]['passwd_account_lock'] = int(entry[5])

			# Note: 
			# the 7th field doesn't seem to be used by passwd(1) nor by usermod(8)
			# and thus raises en exception because it's empty in 100% of cases.
			# → temporarily disabled until we use it internally.
			#
			#UsersList.users[uid]['last_lock_date']      = int(entry[6])

		map(import_user_from_etc_passwd, readers.ug_conf_load_list("/etc/passwd"))

		try :
			map(import_user_from_etc_shadow, readers.ug_conf_load_list("/etc/shadow"))
		except (OSError,IOError), e :
			if e.errno == 13 :
				# don't raise an exception or display a warning, this is harmless if we
				# are loading data for getent, and any other operation (add/mod/del) will
				# fail anyway if we are not root or @admin.
				pass
			else : raise
	def SetProfiles(self, profiles) :
		UsersList.profiles = profiles
	def SetGroups(self, groups) :
		UsersList.groups = groups
	def WriteConf(self) :
		""" Write the user data in appropriate system files.""" 
		#
		# Write /etc/passwd and /etc/shadow
		#
		lock_etc_passwd = file_locks.FileLock(self.configuration, "/etc/passwd")
		lock_etc_shadow = file_locks.FileLock(self.configuration, "/etc/shadow")
		etcpasswd = []
		etcshadow = []
		uids = self.users.keys()
		uids.sort()
		for uid in uids:
			etcpasswd.append(":".join((
										self.users[uid]['login'],
										"x",
										str(uid),
										str(self.users[uid]['gid']),
										self.users[uid]['gecos'],
										self.users[uid]['homeDirectory'],
										self.users[uid]['loginShell']
									))
							)
							
			etcshadow.append(":".join((
										self.users[uid]['login'],
										self.users[uid]['crypted_password'],
										str(self.users[uid]['passwd_last_change']),
										str(self.users[uid]['passwd_expire_delay']),
										str(self.users[uid]['passwd_expire_warn']),
										str(self.users[uid]['passwd_account_lock']),
										"","",""
									))
							)
		lock_etc_passwd.Lock()
		open("/etc/passwd" , "w").write("%s\n" % "\n".join(etcpasswd))
		lock_etc_passwd.Unlock()
		
		lock_etc_shadow.Lock()
		open("/etc/shadow" , "w").write("%s\n" % "\n".join(etcshadow))
		lock_etc_shadow.Unlock()
		
	def Select( self, filter_string ) :
		""" Filter user accounts on different criteria.
		Criteria are :
			- 'system users' : show only «system» users (root, bin, daemon, apache...),
				not normal user account.
			- 'normal users' : keep only «normal» users, which includes Licorn administrators
			- more to come...
		"""

		#
		# filter_applied is used to note if something has been selected (or tried to).
		# without this, «getent users» on a system with no users returns all system accounts,
		# but it should return nothing, except when given --all of course.
		# even if nothing match the filter given we must note that a filter has been applied,
		# in order to output a coherent result.
		#
		self.filter_applied = True
		self.filtered_users = []
		
		uids = UsersList.users.keys()
		uids.sort()

		if UsersList.FILTER_STANDARD == filter_string :
			def keep_uid_if_not_system(uid) :
				if not UsersList.is_system_uid(uid) :
					self.filtered_users.append(uid)

			map(keep_uid_if_not_system, uids)
			
		elif UsersList.FILTER_SYSTEM == filter_string :
			def keep_uid_if_system(uid) :
				if UsersList.is_system_uid(uid) :
					self.filtered_users.append(uid)

			map(keep_uid_if_system, uids)
		
		else :
			import re
			uid_re = re.compile("^uid=(?P<uid>\d+)")
			uid = uid_re.match(filter_string)
			if uid is not None:
				uid = int(uid.group('uid'))
				self.filtered_users.append(uid)
	def AddUser(self, lastname = None, firstname = None, password = None, primary_group=None, profile=None, skel=None, login=None, gecos=None, system = False, batch=False) :
		"""Add a user and return his/her (uid, login, pass)."""

		logging.debug("Going to create a user...")

		if login is None :
			if firstname is None or lastname is None :
				raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LGN_FST_LST)
			else :
				login_autogenerated = True
				login = UsersList.make_login(lastname, firstname)
		else :
			login_autogenerated = False

		if gecos is None :
			gecos_autogenerated = True

			if firstname is None or lastname is None :
				gecos = "Compte %s" % login
			else :
				gecos = "%s %s" % (firstname, lastname.upper())
		else :
			gecos_autogenerated = False

			if firstname and lastname :
				raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LF_OR_GECOS)
			# else : all is OK, we have a login and a GECOS field	

		# TODO: in some corner cases, we could discard some user data:
		# ex: it we have a GECOS and *only* a firstname, the firstname will be discarded.

		if not hlstr.cregex['login'].match(login) :
			if login_autogenerated :
				raise exceptions.LicornRuntimeError("Can't build a valid login (%s) with the firstname/lastname (%s/%s) you provided." 
					% (login, firstname, lastname))
			else :
				raise exceptions.BadArgumentError(logging.SYSU_MALFORMED_LOGIN % (login, styles.stylize(styles.ST_REGEX, hlstr.regex['login'])))
		
		if not login_autogenerated and len(login) > UsersList.configuration.users.login_maxlenght :
			raise exceptions.LicornRuntimeError("Login too long (%d characters, but must be shorter or equal than %d)." 
				% (len(login),UsersList.configuration.users.login_maxlenght) )
		
		if not hlstr.cregex['description'].match(gecos) :
			if gecos_autogenerated :
				raise exceptions.LicornRuntimeError("Can't build a valid GECOS (%s) with the firstname/lastname (%s/%s) or login you provided." 
					% (gecos, firstname, lastname))
			else :
				raise exceptions.BadArgumentError(logging.SYSU_MALFORMED_GECOS % (gecos, styles.stylize(styles.ST_REGEX, hlstr.regex['description'])))
			
		if primary_group :
			pg_gid = UsersList.groups.name_to_gid(primary_group)

		if skel and skel not in UsersList.configuration.users.skels :
				raise exceptions.BadArgumentError("The skel you specified doesn't exist on this system. Valid skels are : %s." 
					% UsersList.configuration.users.skels)

		tmp_user_dict = {}

		# Verify existance of user
		for uid in UsersList.users :
			if UsersList.users[uid]['login'] == login :
				raise exceptions.AlreadyExistsException, "A user named « %s » already exists !" % login
				#
				# TODO ? continue creation if not a system account, to verify everything is OK
				# in the homedir, in the ACLs, etc.
				#
				# FIXME : verify everything besides the login before shooting the user already exists.
				
		# Due to a bug of adduser/deluser perl script, we must check that there is no group which the same name than the login.
		# There should not already be a system group with the same name (we are just going to create it...), but it
		# could be a system inconsistency, so go on to recover from it.
		#
		# {add,del}user logic is : 
		#	- a system account must always have a system group as primary group, else if will be «nogroup» if not 
		#		specified.
		#   - when deleting a system account, a corresponding system group will be deleted if existing.
		#	- no restrictions for a standard account
		#
		# the bug is that in case 2, deluser will delete the group even if this is a standard group (which is bad).
		# this could happen with :
		#	addgroup toto
		#	adduser --system toto --ingroup root
		#	deluser --system toto
		#	(group toto is deleted but it shouldn't be ! And it is deleted without *any* message !!)
		for gid in UsersList.groups.groups :
			if UsersList.groups.groups[gid]['name'] == login :
				raise exceptions.UpstreamBugException, "A group named `%s' exists on the system, this could eventually conflict in Debian/Ubuntu system tools. Please choose another user's login." % login
		
		if password is None :
			# TODO : call cracklib2 to verify passwd strenght.
			password = hlstr.generate_password(UsersList.configuration.mAutoPasswdSize)
			logging.notice(logging.SYSU_AUTOGEN_PASSWD % (styles.stylize(styles.ST_LOGIN, login), styles.stylize(styles.ST_SECRET, password)))

		groups_to_add_user_to = []
		
		skel_to_apply = "/etc/skel"
		# 3 cases :
		if profile is not None :
			# Apply the profile after having created the home dir.
			try :
				tmp_user_dict['loginShell']    = UsersList.profiles.profiles[profile]['shell']
				tmp_user_dict['gid']           = UsersList.groups.name_to_gid(UsersList.profiles.profiles[profile]['primary_group'])
				tmp_user_dict['homeDirectory'] = ("%s/%s/%s" 
					% (UsersList.configuration.users.home_base_path, UsersList.profiles.profiles[profile]['primary_group'], login))

				if UsersList.profiles.profiles[profile]['groups'] != [] :
					groups_to_add_user_to = UsersList.profiles.profiles[profile]['groups']

					# don't directly add the user to the groups. prepare the groups to
					# use the Licorn API later, to create the groups symlinks while adding
					# user to them.
					#useradd_options.append("-G " + ",".join(UsersList.profiles.profiles[profile]['groups']))
				if skel is None :
					skel_to_apply = UsersList.profiles.profiles[profile]['skel_dir']
			except KeyError, e :
				# fix #292
				raise exceptions.LicornRuntimeError("The profile %s does not exist on this system (was: %s) !" % (profile, e))
		elif primary_group is not None :

			tmp_user_dict['gid']           = pg_gid
			tmp_user_dict['loginShell']    = UsersList.configuration.users.default_shell
			tmp_user_dict['homeDirectory'] = "%s/%s" % (UsersList.configuration.users.home_base_path, login)
			
			# FIXME : use is_valid_skel() ?
			if skel is None and os.path.isdir(UsersList.groups.groups[pg_gid]['skel']) :
				skel_to_apply = UsersList.groups.groups[pg_gid]['skel']

		else : 

			tmp_user_dict['gid']           = UsersList.configuration.users.default_gid
			tmp_user_dict['loginShell']    = UsersList.configuration.users.default_shell
			tmp_user_dict['homeDirectory'] = "%s/%s" % (UsersList.configuration.users.home_base_path, login)
			# if skel is None, system default skel will be applied
		
		# FIXME : is this necessary here ? not done before ?
		if skel is not None :
			skel_to_apply = skel
		
		if system :
			uid = pyutils.next_free(self.users.keys(), self.configuration.users.system_uid_min, self.configuration.users.system_uid_max)
		else :
			uid = pyutils.next_free(self.users.keys(), self.configuration.users.uid_min, self.configuration.users.uid_max)

		tmp_user_dict['crypted_password']   = crypt.crypt(password, "$1$%s" % hlstr.generate_password())
		tmp_user_dict['passwd_last_change'] = str(int(time()/86400))
		
		# create home directory and apply skel
		if not os.path.exists(tmp_user_dict['homeDirectory']) :
			import shutil
			shutil.copytree(skel_to_apply, tmp_user_dict['homeDirectory']) # copytree create tmp_user_dict['homeDirectory']
		#else, the home directory already exists, we don't overwrite it

		tmp_user_dict['uid']    = uid
		tmp_user_dict['gecos']  = gecos
		tmp_user_dict['login']  = login
		# prepare the groups cache.
		tmp_user_dict['groups'] = []
		tmp_user_dict['passwd_expire_delay'] = 99999
		tmp_user_dict['passwd_expire_warn']  = ""
		tmp_user_dict['passwd_account_lock'] = ""

		# Add user in list and in cache
		UsersList.users[uid]         = tmp_user_dict
		UsersList.login_cache[login] = uid
		
		# can't do this, it will break Samba stuff : Samba needs Unix account to be present in /etc/* before creating 
		# Samba account. We thus can't delay the WriteConf() call, even if we are in batch / import users mode.
		#if not batch :

		self.WriteConf()

		# Samba: add Samba user account.
		# TODO: put this into a module.
		try :
			sys.stderr.write(process.pipecmd('%s\n%s\n' % (password, password), ['smbpasswd', '-a', login, '-s']))
		except (IOError, OSError), e :
			if e.errno != 32 :
				raise e

		if groups_to_add_user_to != [] :

			logging.debug("user %s is going to be added to %s." % (styles.stylize(styles.ST_LOGIN, login), groups_to_add_user_to))

			for group in groups_to_add_user_to :
				UsersList.groups.AddUsersInGroup(group, [ login ])
		
		# Set quota
		if profile is not None :
			try :
				pass
				#os.popen2( [ 'quotatool', '-u', str(uid), '-b', UsersList.configuration.defaults.quota_device, '-l' '%sMB' % UsersList.profiles.profiles[profile]['quota'] ] )[1].read()
				#logging.warning("quotas are disabled !")
				# FIXME : Quotatool can return 2 without apparent reason (the quota is etablished) !
			except exceptions.LicornException, e :
				logging.warning( "ROLLBACK because " + str(e))
				# Rollback
				self.DeleteUser(login, True)

		self.CheckUsers([ login ], batch = True)

		logging.info(logging.SYSU_CREATED_USER % (styles.stylize(styles.ST_LOGIN, login), styles.stylize(styles.ST_UGID, uid)))

		return (uid, login, password)
	def DeleteUser(self, login=None, no_archive=False, uid=None, batch=False) :
		""" Delete a user """
		if login is None and uid is None :
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LGN_OR_UID)
			
		if uid is None :
			uid = UsersList.login_to_uid(login)

		elif login is None :
			# «login» is needed for deluser system command.
			login = UsersList.users[uid]["login"] 

		logging.progress("Going to remove user %s(%s), groups %s." % (login, str(uid), UsersList.users[uid]['groups']) )

		# Delete user from his groups 
		# '[:]' to fix #14, see http://docs.python.org/tut/node6.html#SECTION006200000000000000000
		for group in UsersList.users[uid]['groups'].copy() :
			UsersList.groups.RemoveUsersFromGroup(group, [ login ], batch=True)


		try :
			# samba stuff
			os.popen2([ 'smbpasswd', '-x', login ])[1].read()
		except (IOError, OSError), e :
			if e.errno != 32 :
				raise e
			
		# keep the homedir path, to backup it if requested.
		homedir = UsersList.users[uid]["homeDirectory"]

		if no_archive :
			import shutil
			try :
				shutil.rmtree(homedir)
			except OSError, e :
				logging.warning("Home dir %s does not exist, can't delete it !" % styles.stylize(styles.ST_PATH, homedir))
		
		if not no_archive :
			UsersList.configuration.CheckBaseDirs(minimal = True, batch = True)
			user_archive_dir = "%s/%s.deleted.%s" % (UsersList.configuration.home_archive_dir, login, strftime("%Y%m%d-%H%M%S", gmtime()))
			try :
				os.rename(homedir, user_archive_dir)
				logging.info(logging.SYSU_ARCHIVED_USER % (homedir, styles.stylize(styles.ST_PATH, user_archive_dir)))
			except OSError, e :
				if e.errno == 2 :
					logging.warning("Home dir %s does not exist, can't archive it !" % styles.stylize(styles.ST_PATH, homedir))
				else :
					raise e

		# Delete user from users list
		del(UsersList.login_cache[login])
		del(UsersList.users[uid])
		logging.info(logging.SYSU_DELETED_USER % styles.stylize(styles.ST_LOGIN, login))
		
		if not batch :
			self.WriteConf()

	def ChangeUserPassword(self, login, password = None, display = False) :
		""" Change the password of a user
		"""
		if login is None :
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)
		if password is None :
			password = hlstr.generate_password(UsersList.configuration.mAutoPasswdSize)
		elif password == "" :
			logging.warning(logging.SYSU_SET_EMPTY_PASSWD % styles.stylize(styles.ST_LOGIN, login))
			# TODO : automatically remove user from remotessh ?

		uid = UsersList.login_to_uid(login)

		# use real MD5 passwd, and generate a good salt (fixes #58).
		UsersList.users[uid]['crypted_password']   = crypt.crypt(password, "$1$%s" % hlstr.generate_password())

		# 3600*24 to have the number of days since epoch (fixes #57).
		UsersList.users[uid]['passwd_last_change'] = str(int(time()/86400))

		self.WriteConf()

		if display :
			logging.notice("Set user %s's password to %s." % (styles.stylize(styles.ST_NAME, login), styles.stylize(styles.ST_IMPORTANT, password)))
		else :
			logging.info('Changed password for user %s.' % styles.stylize(styles.ST_NAME, login))
		
		try :
			# samba stuff
			sys.stderr.write(process.pipecmd("%s\n%s\n" % (password, password), ['smbpasswd', login, '-s']))
		except (IOError, OSError), e :
			if e.errno != 32 :
				raise e
	def ChangeUserGecos(self, login, gecos = "") :
		""" Change the gecos of a user
		"""
		if login is None :
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)

		if not hlstr.cregex['description'].match(gecos) :
			raise exceptions.BadArgumentError(logging.SYSU_MALFORMED_GECOS % (gecos, styles.stylize(styles.ST_REGEX, hlstr.regex['description'])))
			
		uid = UsersList.login_to_uid(login)
		UsersList.users[uid]['gecos'] = gecos
		self.WriteConf()
	def ChangeUserShell(self, login, shell = "") :
		""" Change the shell of a user. """
		if login is None :
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)
			
		uid = UsersList.login_to_uid(login)

		if shell not in UsersList.configuration.users.shells :
			raise exceptions.LicornRuntimeError("Invalid shell ! valid shells are %s." % UsersList.configuration.users.shells)

		UsersList.users[uid]['loginShell'] = shell
		self.WriteConf()
		
	def LockAccount(self, login, lock = True) :
		"""(Un)Lock a user account."""
		if login is None :
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)


		if lock :
			# we must set /bin/false, else remote SSH connections with keys
			# would still succeed.
			lockarg = '-L'
		else :
			# we cannot know what the last shell was, we arbitrary put back
			# /bin/bash.
			lockarg = '-U'

		# update internal data structures.
		uid = UsersList.login_to_uid(login)
		if lock :
			UsersList.users[uid]['crypted_password'] = '!' + UsersList.users[uid]['crypted_password']
			logging.info('Locked user account %s.' % styles.stylize(styles.ST_LOGIN, login))
		else :
			UsersList.users[uid]['crypted_password'] = UsersList.users[uid]['crypted_password'][1:]
			logging.info('Unlocked user account %s.' % styles.stylize(styles.ST_LOGIN, login))
		UsersList.users[uid]['locked'] = lock
		
		self.WriteConf()
	def ApplyUserSkel(self, login, skel) :
		""" Apply a skel on a user
		"""
		if login is None :
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)
		if skel is None :
			raise exceptions.BadArgumentError, "You must specify a skel"
		if not os.path.isabs(skel) or not os.path.isdir(skel) :
				raise exceptions.AbsolutePathError(skel)
				
		uid = UsersList.login_to_uid(login)
		# not force option with shutil.copytree
		process.syscmd("cp -r %s/* %s/.??* %s"    % (skel, skel, UsersList.users[uid]['homeDirectory']) )
		
		# set permission (because root)
		for fileordir in os.listdir(skel) :
			try :
				# FIXME : do this with os.chmod()... and map() it.
				process.syscmd("chown %s %s/%s" % (UsersList.users[uid]['login'], UsersList.users[uid]['homeDirectory'], fileordir) )
			except Exception, e :
				logging.warning(str(e))

	def ExportCLI( self, longOutput = False) :
		""" Export the user accounts list to human readable («passwd») form.
		"""
		if self.filter_applied :
			uids = self.filtered_users
		else :
			uids = UsersList.users.keys()

		uids.sort()

		def build_cli_output_user_data(uid, users = UsersList.users) :
			account = [	users[uid]['login'],
						"x",
						str(uid),
						str(users[uid]['gid']),
						users[uid]['gecos'],
						users[uid]['homeDirectory'],
						users[uid]['loginShell'],
						]
			if longOutput :
				account.append(','.join(UsersList.users[uid]['groups']))
			return ':'.join(account)
		
		data = '\n'.join(map(build_cli_output_user_data, uids)) + '\n'

		return data
	def ExportCSV( self, longOutput = False) :
		"""Export the user accounts list to CSV."""

		if self.filter_applied :
			uids = self.filtered_users
		else :
			uids = UsersList.users.keys()

		uids.sort()

		def build_csv_output_licorn(uid) :
			return ';'.join(
				[	UsersList.users[uid]['gecos'],
					UsersList.users[uid]['login'],
					str(UsersList.users[uid]['gid']),
					','.join(UsersList.users[uid]['groups']) ]
				)
		
		data = '\n'.join(map(build_csv_output_licorn, uids)) +'\n'

		return data
	def ExportXML( self, longOutput = False) :
		""" Export the user accounts list to XML. """

		if self.filter_applied :
			uids = self.filtered_users
		else :
			uids = UsersList.users.keys()

		uids.sort()

		def build_xml_output_user_data(uid) :
			data = '''
	<user>
		<login>%s</login>
		<uid>%d</uid>
		<gid>%d</gid>
		<gecos>%s</gecos>
		<homeDirectory>%s</homeDirectory>
		<loginShell>%s</loginShell>\n''' % (
					UsersList.users[uid]['login'],
					uid,
					UsersList.users[uid]['gid'], 
					UsersList.users[uid]['gecos'], 
					UsersList.users[uid]['homeDirectory'], 
					UsersList.users[uid]['loginShell']
				)
			if longOutput :
				data += "		<groups>%s</groups>\n" % ','.join(UsersList.users[uid]['groups'])

			return data + "	</user>"

		data = "<?xml version='1.0' encoding=\"UTF-8\"?>\n<users-list>\n" \
			+ '\n'.join(map(build_xml_output_user_data, uids)) \
			+ "\n</users-list>\n"
		
		return data

	def CheckUsers(self, users_to_check = [], minimal = True, batch = False, auto_answer = None) :
		"""Check user accounts and account data consistency."""

		if users_to_check == [] :
			users_to_check = UsersList.login_cache.keys()

		# dependancy : base dirs must be OK before checking users's homes.
		UsersList.configuration.CheckBaseDirs(minimal, batch, auto_answer)

		def check_user(user, minimal = minimal, batch = batch, auto_answer = auto_answer) :

			all_went_ok = True
			uid         = UsersList.login_to_uid(user)

			if not UsersList.is_system_uid(uid) :
				logging.progress("Checking user %s..." % styles.stylize(styles.ST_LOGIN, user))

				gid       = self.users[uid]['gid']
				group     = self.groups.groups[gid]['name']
				user_home = self.users[uid]['homeDirectory']

				logging.progress("Checking user account %s..." % styles.stylize(styles.ST_NAME, user))

				acl_base                  = "u::rwx,g::---,o:---"
				file_acl_base             = "u::rw@UE,g::---,o:---"
				acl_mask                  = "m:rwx"
				acl_restrictive_mask      = "m:r-x"
				file_acl_mask             = "m:rw@GE"
				file_acl_restrictive_mask = "m:rw@GE"

				# first build a list of dirs (located in ~/) to be excluded from the home dir check,
				# because they must have restrictive permission (for confidentiality reasons) and
				# don't need any ACLs.
				# in the same time (for space optimization reasons), append them to special_dirs[]
				# (which will be checked *after* home dir).
				home_exclude_list = [ '.ssh', '.gnupg', '.gnome2_private', '.gvfs' ]
				special_dirs      = []

				special_dirs.extend([ {
							'path'         : "%s/%s" % (user_home, dir),
							'user'         : user,
							'group'        : group,
							'mode'         : 00700,
							'content_mode' : 00600
						} for dir in home_exclude_list if os.path.exists('%s/%s' % (user_home, dir)) ])

				if os.path.exists('%s/public_html' % user_home) :

					home_exclude_list.append('public_html')

					special_dirs.append ( {
							'path'        : "%s/public_html" % user_home,
							'user'        : user,
							'group'       : 'acl',
							'access_acl'  : "%s,g:%s:r-x,g:www-data:r-x,%s" % (acl_base,
								UsersList.configuration.defaults.admin_group, acl_restrictive_mask),
							'default_acl' : "%s,g:%s:rwx,g:www-data:r-x,%s" % (acl_base,
								UsersList.configuration.defaults.admin_group, acl_mask),
							'content_acl' : "%s,g:%s:rw-,g:www-data:r--,%s" % (file_acl_base,
								UsersList.configuration.defaults.admin_group, file_acl_mask),
						} )

				# if we are in charge of building the user's mailbox, do it and check it.
				# This is particularly important for ~/Maildir because courier-imap will crash
				# and eat CPU time if the Maildir doesn't exist prior to the daemon launch...
				if UsersList.configuration.users.mailbox_auto_create and \
					UsersList.configuration.users.mailbox_type == UsersList.configuration.MAIL_TYPE_HOME_MAILDIR :

					maildir_base = '%s/%s' % (user_home, UsersList.configuration.users.mailbox)

					# Warning : "configuration.users.mailbox" is assumed to have a trailing slash if
					# it is a Maildir, because that's the way it is in postfix/main.cf
					# and other MTA configuration. Without the "/", the mailbox is assumed to
					# be an mbox or an MH. So we use [:-1] to skip the trailing "/", else
					# fsapi.minifind() won't match the dir name properly in the exclusion list.

					home_exclude_list.append(UsersList.configuration.users.mailbox[:-1])

					for dir in ( maildir_base, '%stmp' % maildir_base, '%scur' % maildir_base,'%snew' % maildir_base ) :
						special_dirs.append ( {
							'path'         : dir,
							'user'         : user,
							'group'        : group,
							'mode'         : 00700,
							'content_mode' : 00600
						} )

				
				# this will be handled in another manner later in this function.
				# .procmailrc : fix #589
				home_exclude_file_list = [ ".dmrc", ".procmailrc" ]
				for file in home_exclude_file_list :
					if os.path.exists('%s/%s' % (user_home, file)) :
						home_exclude_list.append(file)
						all_went_ok &= fsapi.check_posix_ugid_and_perms('%s/%s' % (user_home, file),
							uid, gid, 00600, batch, auto_answer, self.groups, self)
				# now that the exclusion list is complete, we can check the base home dir.

				home_dir_info = {
						'path'        : UsersList.users[uid]['homeDirectory'],
						'user'        : user,
						'group'       : 'acl',
						'access_acl'  : "%s,g:%s:r-x,g:www-data:--x,%s" % (acl_base,
							UsersList.configuration.defaults.admin_group, acl_restrictive_mask),
						'default_acl' : "%s,g:%s:rwx,%s" % (acl_base,
							UsersList.configuration.defaults.admin_group, acl_mask),
						'content_acl' : "%s,g:%s:rw@GE,%s" % (file_acl_base,
							UsersList.configuration.defaults.admin_group, file_acl_mask),
						'exclude'     : home_exclude_list
						}

				if not batch :
					logging.progress("Checking user home dir %s contents, this can take a while..." % styles.stylize(styles.ST_PATH, user_home))

				try :
					all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls( [ home_dir_info ], batch, auto_answer, UsersList.groups, self)
				except exceptions.LicornCheckError :
					logging.warning("User home dir %s is missing, please repair this first." % styles.stylize(styles.ST_PATH, user_home))
					return False


				all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls( special_dirs, batch, auto_answer, UsersList.groups, self)

				if not minimal :
					logging.warning("Extended checks are not yet implemented for users.")
					# TODO :
					#	logging.progress("Checking symlinks in user's home dir, this can take a while..." % styles.stylize(styles.ST_NAME, user))
					#	if not self.CleanUserHome(login, batch, auto_answer) :
					#		all_went_ok = False

					# TODO : tous les groupes de cet utilisateur existent et sont OK (CheckGroups recursif)
					# WARNING : Forcer minimal = True pour éviter les checks récursifs avec CheckGroups()

				return all_went_ok

		if reduce(pyutils.keep_false, map(check_user, users_to_check)) is False :
			# don't test just "if reduce() :", the result could be None and everything is OK when None
			raise exceptions.LicornCheckError("Some user(s) check(s) didn't pass, or weren't corrected.")

	@staticmethod
	def user_exists(uid = None, login = None) :
		if uid :
			return UsersList.users.has_key(uid)
		if login :
			return UsersList.login_cache.has_key(login)
		return False

	@staticmethod
	def check_password(login, password) :
		crypted_passwd = UsersList.users[UsersList.login_cache[login]]['crypted_password']
		return (crypted_passwd == crypt.crypt(password, crypted_passwd))

	@staticmethod
	def login_to_uid(login) :
		""" Return the uid of the user 'login'
		"""
		try :
			# use the cache, Luke !
			return UsersList.login_cache[login]
		except KeyError :
			try :
				int(login)
				logging.warning("You passed an uid to login_to_uid() : %d (guess its login is « %s » )." % (login, UsersList.users[login]['login']))
			except ValueError :
				pass
			raise exceptions.LicornRuntimeException(logging.SYSU_USER_DOESNT_EXIST % login)

	@staticmethod
	def is_system_uid(uid) :
		""" Return true if uid is system."""
		return uid < UsersList.configuration.users.uid_min or uid > UsersList.configuration.users.uid_max

	@staticmethod
	def is_system_login(login) :
		""" return true if login is system. """
		try :
			return UsersList.is_system_uid(UsersList.login_cache[login])
		except KeyError :
			raise exceptions.LicornRuntimeException(logging.SYSU_USER_DOESNT_EXIST % login)

	@staticmethod
	def make_login(lastname = "", firstname = "", inputlogin = "") :
		""" Make a valid login from  user's firstname and lastname."""

		if inputlogin == "" :
			# login = hlstr.validate_name(str(firstname + '.' + lastname), aggressive = True, maxlenght = UsersList.configuration.users.login_maxlenght)
			login = hlstr.validate_name(str(firstname + '.' + lastname), maxlenght = UsersList.configuration.users.login_maxlenght)
		else :
			# use provided login and verify it.
			# login = hlstr.validate_name(str(inputlogin), aggressive = True, maxlenght = UsersList.configuration.users.login_maxlenght)
			login = hlstr.validate_name(str(inputlogin), maxlenght = UsersList.configuration.users.login_maxlenght)
			
		if not hlstr.cregex['login'].match(login) :
			raise exceptions.LicornRuntimeError("Can't build a valid login (got %s, which doesn't verify %s) with the firstname/lastname you provided (%s %s)." % (login, hlstr.regex['login'], firstname, lastname) )

		return login

		# TODO : verify if the login doesn't already exist.
		#while potential in UsersList.users :
