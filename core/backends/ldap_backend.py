# -*- coding: utf-8 -*-
"""
Licorn Core LDAP backend.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import os
import re
import ldap

from licorn.foundations         import logging, exceptions, styles, pyutils
from licorn.foundations         import objects, readers, process
from licorn.foundations.objects import LicornConfigObject, UGBackend

class ldap_controller(UGBackend):
	""" LDAP Backend for users and groups.

		TODO: implement auto-setup part: if backends.ldap.enabled is forced to
		True in licorn.conf, we should auto-install packages, setup dirs, LDAP
		dn, etc.
	"""
	def __init__(self, configuration, users = None, groups = None):
		UGBackend.__init__(self, configuration, users, groups)
		"""
			Initialize the LDAP backend.

			if manually disabled in configuration, exit immediately.
			else, try to start it without any tests (it should work if it's
			installed) and get enabled.
			If that fails, try to guess a little and help user resolving issue.
			else, just fail miserably.
		"""
		self.name    = "LDAP"
		self.enabled = False
		self.files   = LicornConfigObject()
		self.files.ldap_conf   = '/etc/ldap.conf'
		self.files.ldap_secret = '/etc/ldap.secret'

		if not configuration.backends.ldap.enabled:
			return

		try:
			for (key, value) in readers.simple_conf_load_dict(
					self.files.ldap_conf).iteritems():
				setattr(self, key, value)

			self.bind_as_admin = False

			try:
				# if we have access to /etc/ldap.secret, we are root. Bind as admin.

				self.secret = open(self.files.ldap_secret).read().strip()
				self.bind_dn = self.rootbinddn
				self.bind_as_admin = True

			except (IOError, OSError), e:
				if e.errno == 13:
					# permission denied.
					# we will bind as current user.
					self.bind_dn = 'uid=%s,%s' % (process.whoami(), self.base)

				else:
					raise e

			self.check_defaults()

			logging.info('%s: binding as %s.' % (
			self.name, styles.stylize(styles.ST_LOGIN, self.bind_dn)))

			dir(ldap)

			self.ldap_conn = ldap.initialize(self.uri)

			self.ldap_conn.bind_s(self.bind_dn, self.secret, ldap.AUTH_SIMPLE)

			self.enabled = True

		except (IOError, OSError), e:
			if e.errno != 2:
				if os.path.exists(self.files.ldap_conf):
					logging.warning('''Problem initializing the LDAP backend. '''
					'''LDAP seems installed but not configured or unusable. '''
					'''Please run 'sudo chk config -evb' to correct. '''
					'''(was: %s)''' % e)
				#else:
				# just discard the LDAP backend completely.
			else:
				raise e
	def check_defaults(self):
		""" create defaults if they don't exist in current configuration. """

		defaults = (
			('nss_base_passwd', 'ou=People'),
			('nss_base_group', 'ou=Group'),
			('nss_base_hosts', 'ou=Hosts')
			)

		for (key, value) in defaults :
			if not hasattr(self, key):
				setattr(self, key, value)

	def check_database(self, minimal=True, batch=False, auto_answer=None):

		if minimal:
			#
			# TODO: check frontend only
			#
			return False
		else:
			return False

		if self.check_system(minimal, batch, auto_answer):
			#
			# TODO:

			# cosine
			# nis
			# inetorgperson
			# samba
			#
			# backend
			# frontend
			pass
		else:
			return False
	def check_database_frontend(self, minimal=True, batch=False,
		auto_answer=None):
		""" Check the LDAP database frontend (high-level check). """

		def chk_people():
			pass
		if minimal:
			pass
		else:
			return False
	def check_system(self, minimal=True, batch=False, auto_answer=None):
		""" Check that the underlying system is ready to go LDAP. """

		if not os.path.exists(self.files.ldap_conf):
			# if this file exists, libpam-ldap is installed. It is fine to
			# assume that we have to use it, so start to check it. Else,
			# just discard the current module.
			return False

		if pyutils.check_file_against_dict(self.files.ldap_conf,
				(
					('base',         None),
					('uri',          None),
					('rootbinddn',   None),
					('pam_password', 'md5'),
					('ldap_version', 3)
				),
				self.configuration):

			# keep the values inside ourselves, to use afterwards.
			for (key, value) in readers.simple_conf_load_dict(
				self.files.ldap_conf).iteritems():
				setattr(self, key, value)

			#
			# TODO: check superfluous and custom directives.
			#

		try:
			if (not os.path.exists(self.files.ldap_secret) or \
				open(self.files.ldap_secret).read().strip() == '') and \
				batch or logging.ask_for_repair(
				'''%s is empty, but should not.''' \
				% styles.stylize(styles.ST_SECRET, self.files.ldap_secret)):

				try:
					from licorn.foundations import hlstr
					genpass = hlstr.generate_password(
					self.configuration.mAutoPasswdSize)

					logging.notice(logging.SYSU_AUTOGEN_PASSWD % (
						styles.stylize(styles.ST_LOGIN, 'manager'),
						styles.stylize(styles.ST_SECRET, genpass)))

					open(self.files.ldap_secret, 'w').write(genpass + '\n')

					#
					# TODO: update the LDAP database... Without this point, the
					# purpose of this method is pretty pointless.
					#
				except (IOError, OSError), e:
					if e.errno == 13:
						raise exceptions.LicornRuntimeError(
							'''Insufficient permissions. '''
							'''Are you root?\n\t%s''' % e)
					else:
						raise e
			else:
				raise exceptions.LicornRuntimeError(
				'''%s is mandatory for %s to work '''
				'''properly. Can't continue without this, sorry!''' % (
				self.files.ldap_secret, self.configuration.app_name))
		except (OSError, IOError), e :
			if e.errno != 13:
				raise e

		#
		# TODO: check ldap_ldap_conf, or verify it is useless.
		#

		return True

	def get_defaults(self):
		""" Return mandatory defaults needed for LDAP Backend.

		TODO: what the hell is good to set defaults if pam-ldap and libnss-ldap
		are not used ?
		If they are in use, everything is already set up in system files, no ?
		"""

		base_dn = 'dc=licorn,dc=local'

		if self.configuration.daemon.role == 'client':
			waited = 0.1
			while self.configuration.server is None:
				#
				time.sleep(0.1)
				wait += 0.1
				if wait > 5:
					# FIXME: this is not the best thing to do, but server
					# detection needs a little more love and thinking.
					raise exceptions.LicornRuntimeException(
						'No server detected, bailing out…' )
			server = self.configuration.server

		else:
			server = '127.0.0.1'

		return {
			'backends.ldap.base_dn'    : base_dn,
			'backends.ldap.uri'        : 'ldapi:///%s' % server,
			'backends.ldap.rootbinddn' : 'cn=admin,%s' % base_dn,
			'backends.ldap.secret'     : '',
			'backends.ldap.enabled'    : False
			}
	def load_users(self, groups = None):
		""" Load user accounts from /etc/{passwd,shadow} """
		users       = {}
		login_cache = {}

		for entry in readers.ug_conf_load_list("/etc/passwd"):
			temp_user_dict	= {
				'login'        : entry[0],
				'uid'          : int(entry[2]) ,
				'gid'          : int(entry[3]) ,
				'gecos'        : entry[4],
				'homeDirectory': entry[5],
				'loginShell'   : entry[6],
				'groups'       : set()		# a cache which will
											# eventually be filled by
											# groups.__init__() and others.
				}

			# populate ['groups'] ; this code is duplicated in groups.__init__,
			# in case users/groups are loaded in different orders.
			if groups is not None:
				for g in groups.groups:
					for member in groups.groups[g]['members']:
						if member == entry[0]:
							temp_user_dict['groups'].add(
								groups.groups[g]['name'])

			# implicitly index accounts on « int(uid) »
			users[ temp_user_dict['uid'] ] = temp_user_dict

			# this will be used as a cache for login_to_uid()
			login_cache[ entry[0] ] = temp_user_dict['uid']

		try:
			for entry in readers.ug_conf_load_list("/etc/shadow"):
				if login_cache.has_key(entry[0]):
					uid = login_cache[entry[0]]
					users[uid]['crypted_password'] = entry[1]
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
						users[uid]['passwd_last_change']  = 0
					else:
						users[uid]['passwd_last_change']  = int(entry[2])

					if entry[3] == "":
						users[uid]['passwd_expire_delay'] = 99999
					else:
						users[uid]['passwd_expire_delay'] = int(entry[3])

					if entry[4] == "":
						users[uid]['passwd_expire_warn']  = entry[4]
					else:
						users[uid]['passwd_expire_warn']  = int(entry[4])

					if entry[5] == "":
						users[uid]['passwd_account_lock'] = entry[5]
					else:
						users[uid]['passwd_account_lock'] = int(entry[5])

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
				# harmless if we are loading data for getent, and any other
				# operation (add/mod/del) will fail anyway if we are not root
				# or group @admin.

		return users, login_cache
	def load_groups(self):
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		groups     = {}
		name_cache = {}
		extras      = []

		ldap_result = self.ldap_conn.search(
			'%s,%s' % (self.nss_base_group, self.base_dn),
			ldap.SCOPE_SUBTREE,
			'(objectClass=posixGroup)')

		result = self.ldap_conn.result(ldap_result)
		print result
		while result != ():


			result = self.ldap_conn.result(ldap_result)

		is_allowed  = True
		try:
			#
			# TODO: convert this to readers.ug_conf_load_dict_lists() to
			# get the groups sorted and indexed. This will speed up next
			# operations.
			#
			extras = readers.ug_conf_load_list(
				UGBackend.configuration.extendedgroup_data_file)
		except IOError, e:
			if e.errno != 2:
				# other than no such file or directory
				raise e

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
				members = []
			else:
				members   = entry[3].split(',')
				to_remove = []

				# update the cache to avoid massive CPU load in 'getent users
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

					if to_remove != []:
						need_rewriting = True
						for member in to_remove:
							members.remove(member)

			groups[gid] = 	{
				'name' 			: entry[0],
				'passwd'		: entry[1],
				'gid'			: gid,
				'members'		: members,
				'description'	:  "" ,
				'skel'			:  "" ,
				'permissive'    : None
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
						groups[gid]['skel']        = extra_entry[2]
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
				groups[gid]['skel']        = ""

			gshadow_found = False
			for gshadow_entry in etc_gshadow:
				if groups[gid]['name'] ==  gshadow_entry[0]:
					try:
						groups[gid]['crypted_password'] = gshadow_entry[1]
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
				groups[gid]['crypted_password'] = 'x'

		if need_rewriting and is_allowed:
			try:
				self.save_groups(groups)
			except (OSError, IOError), e:
				if self.warnings:
					logging.warning("licorn.core.groups: can't correct" \
					" inconsistencies (was: %s)." % e)

		return groups, name_cache
	def save_users(self, users):
		pass
	def save_groups(self, groups):
		pass
