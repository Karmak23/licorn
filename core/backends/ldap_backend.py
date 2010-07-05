# -*- coding: utf-8 -*-
"""
Licorn Core LDAP backend.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import os
import re
import ldap
import string

from licorn.foundations         import logging, exceptions, styles, pyutils
from licorn.foundations         import objects, readers, process
from licorn.foundations.ltrace  import ltrace
from licorn.foundations.objects import LicornConfigObject, UGBackend

def list_dict(l):
	"""
	return a dictionary with all items of l being the keys of the dictionary
	"""
	d = {}
	for i in l:
		d[i]=None
	return d
def addModlist(entry, ignore_attr_types=None):
	"""Build modify list for call of method LDAPObject.add().

	This is rougly a copy of ldap.modlist.addModlist() version 2.3.10,
	modified to handle non iterable attributes. This is to avoid parsing our
	entries twice (once for creating iterable attributes, once for addModlist).
	"""
	ignore_attr_types = list_dict(map(string.lower, (ignore_attr_types or [])))
	modlist = []
	for attrtype in entry.keys():
		if ignore_attr_types.has_key(string.lower(attrtype)):
			continue

		# first, see if the object is iterable or not. If it is, remove
		# empty values, and completely remove empty iterable objects. Else,
		# remove empty non iterable objects, and if they are not empty,
		# convert them to an iterable because LDAP assumes they are.
		if hasattr(entry[attrtype],'__iter__'):

			# this is a bit over-enginiered because everything is already
			# verified to be not None at load time, and *Controllers never
			# produce empty attributes (as far as I remember). But verifying
			# one more time just before recording change is a sane behavior.
			attrvaluelist = filter(lambda x: x!=None, entry[attrtype])
			if attrvaluelist:
				modlist.append((attrtype, entry[attrtype]))
		elif entry[attrtype]:
			modlist.append((attrtype, [ str(entry[attrtype]) ]))
	return modlist
def modifyModlist(old_entry, new_entry, ignore_attr_types=None,
	ignore_oldexistent=0):
	"""
	Build differential modify list for calling
		LDAPObject.modify()/modify_s()

	This is rougly a copy of ldap.modlist.addModlist() version 2.3.10,
	modified to handle non iterable attributes. This is to avoid parsing our
	entries twice (once for creating iterable attributes, once for
	modifyModlist).

	old_entry
			Dictionary holding the old entry
	new_entry
			Dictionary holding what the new entry should be
	ignore_attr_types
			List of attribute type names to be ignored completely
	ignore_oldexistent
			If non-zero attribute type names which are in old_entry
			but are not found in new_entry at all are not deleted.
			This is handy for situations where your application
			sets attribute value to '' for deleting an attribute.
			In most cases leave zero.
	"""
	ignore_attr_types = list_dict(map(string.lower,(ignore_attr_types or [])))
	modlist = []
	attrtype_lower_map = {}
	for a in old_entry.keys():
		attrtype_lower_map[string.lower(a)] = a
	for attrtype in new_entry.keys():
		attrtype_lower = string.lower(attrtype)
		if ignore_attr_types.has_key(attrtype_lower):
			# This attribute type is ignored
			continue

		# convert all attributes to iterable objects (the rest of the
		# function assumes it is).
		if not hasattr(new_entry[attrtype], '__iter__'):
			new_entry[attrtype] = [ str(new_entry[attrtype]) ]

		# Filter away null-strings
		new_value = filter(lambda x: x!=None, new_entry[attrtype])
		if attrtype_lower_map.has_key(attrtype_lower):
			old_value = old_entry.get(attrtype_lower_map[attrtype_lower], [])
			old_value = filter(lambda x: x!=None, old_value)
			del attrtype_lower_map[attrtype_lower]
		else:
			old_value = []
		if not old_value and new_value:
			# Add a new attribute to entry
			modlist.append((ldap.MOD_ADD, attrtype, new_value))
		elif old_value and new_value:
			# Replace existing attribute
			replace_attr_value = len(old_value)!=len(new_value)
			if not replace_attr_value:
				old_value_dict=list_dict(old_value)
				new_value_dict=list_dict(new_value)
				delete_values = []
				for v in old_value:
					if not new_value_dict.has_key(v):
						replace_attr_value = 1
						break
				add_values = []
				if not replace_attr_value:
					for v in new_value:
						if not old_value_dict.has_key(v):
							replace_attr_value = 1
							break
			if replace_attr_value:
				modlist.append((ldap.MOD_DELETE, attrtype, None))
				modlist.append((ldap.MOD_ADD, attrtype, new_value))
		elif old_value and not new_value:
			# Completely delete an existing attribute
			modlist.append((ldap.MOD_DELETE, attrtype, None))
	if not ignore_oldexistent:
		# Remove all attributes of old_entry which are not present
		# in new_entry at all
		for a in attrtype_lower_map.keys():
			if ignore_attr_types.has_key(a):
				# This attribute type is ignored
				continue
			attrtype = attrtype_lower_map[a]
			modlist.append((ldap.MOD_DELETE, attrtype, None))
	return modlist # modifyModlist()

class ldap_controller(UGBackend):
	""" LDAP Backend for users and groups.

		TODO: implement auto-setup part: if backends.ldap.enabled is forced to
		True in licorn.conf, we should auto-install packages, setup dirs, LDAP
		dn, etc.
	"""
	def __init__(self, configuration, users = None, groups = None):
		"""
			Initialize the LDAP backend.

			if manually disabled in configuration, exit immediately.
			else, try to start it without any tests (it should work if it's
			installed) and get enabled.
			If that fails, try to guess a little and help user resolving issue.
			else, just fail miserably.
		"""

		UGBackend.__init__(self, configuration, users, groups)

		ltrace('ldap', '| __init__().')

		self.name	  = "LDAP"

		# nsswitch compatibility
		self.compat   = ('ldap')
		self.priority = 5
	def __del__(self):
		self.ldap_conn.unbind_s()

	def load_defaults(self):
		""" Return mandatory defaults needed for LDAP Backend.

		TODO: what the hell is good to set defaults if pam-ldap and libnss-ldap
		are not used ? If they are in use, everything is already set up in
		system files, no ? This needs to be rethought, to avoid doing the job
		twice.
		"""

		ltrace('ldap', '| load_defaults().')

		base = 'dc=licorn,dc=local'

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

		self.base       = base
		self.uri        = 'ldapi:///%s' % server
		self.rootbinddn = 'cn=admin,%s' % base
		self.secret     = ''

	def initialize(self):

		self.load_defaults()

		ltrace('ldap', '> initialize().')

		self.files   = LicornConfigObject()
		self.files.ldap_conf   = '/etc/ldap.conf'
		self.files.ldap_secret = '/etc/ldap.secret'

		try:
			for (key, value) in readers.simple_conf_load_dict(
					self.files.ldap_conf).iteritems():
				setattr(self, key, value)

			# add self.base to self.nss_* if not present
			for attr in (
				'nss_base_group',
				'nss_base_passwd',
				'nss_base_shadow'):
				value = getattr(self, attr)
				try:
					i = value.index(self.base)
				except ValueError:
					setattr(self, attr, '%s,%s' % (value, self.base))
				finally:
					del i

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
					#
					# TODO: ask the user for his/her password, because the
					# server will refuse a binding without a password.
					#

				else:
					raise e

			self.check_defaults()

			self.ldap_conn = ldap.initialize(self.uri)

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

		ltrace('ldap', '< initialize() %s.' % self.enabled)
		return self.enabled

	def check_defaults(self):
		""" create defaults if they don't exist in current configuration. """

		ltrace('ldap', '| check_defaults()')

		defaults = (
			('nss_base_passwd', 'ou=People'),
			('nss_base_shadow', 'ou=People'),
			('nss_base_group', 'ou=Groups'),
			('nss_base_hosts', 'ou=Hosts')
			)

		for (key, value) in defaults :
			if not hasattr(self, key):
				setattr(self, key, value)

	def check_database(self, minimal=True, batch=False, auto_answer=None):

		ltrace('ldap', '> check_database()')

		if minimal:
			#
			# TODO: check frontend only
			#
			ltrace('ldap', '< check_database() minimal %s.' % styles.stylize(
				styles.ST_OK, 'True'))
			return True

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
			ltrace('ldap', '< check_database() %s.' % styles.stylize(
				styles.ST_OK, 'True'))
			return True
		else:
			ltrace('ldap', '< check_database() %s.' % styles.stylize(
				styles.ST_BAD, 'False'))
			return False


	def check_database_frontend(self, minimal=True, batch=False,
		auto_answer=None):
		""" Check the LDAP database frontend (high-level check). """

		ltrace('ldap', '| check_database_frontend()')

		def check_people():
			pass
		if minimal:
			pass
		else:
			return False
	def check_system(self, minimal=True, batch=False, auto_answer=None):
		""" Check that the underlying system is ready to go LDAP. """

		ltrace('ldap', '> check_system()')

		if not os.path.exists(self.files.ldap_conf):
			# if this file exists, libpam-ldap is installed. It is fine to
			# assume that we have to use it, so start to check it. Else,
			# just discard the current module.
			ltrace('ldap', '< check_database() %s.' % styles.stylize(
				styles.ST_BAD, 'False'))
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

		ltrace('ldap', '< check_system() %s.' % styles.stylize(
			styles.ST_OK, 'True'))
		return True
	def load_users(self, groups = None):
		""" Load user accounts from /etc/{passwd,shadow} """
		users       = {}
		login_cache = {}

		ltrace('ldap', '> load_users() %s' % self.nss_base_shadow)
		try:
			ldap_result = self.ldap_conn.search_s(
				self.nss_base_shadow,
				ldap.SCOPE_SUBTREE,
				'(objectClass=shadowAccount)')
		except ldap.NO_SUCH_OBJECT:
			return users, login_cache

		for dn, entry in ldap_result:

			temp_user_dict	= {
				# Get the cn from the dn here, else we could end in a situation
				# where the user could not be deleted if it was created manually
				# and the cn is inconsistent.
				#'login'        : entry['uid'][0],
				'login'         : dn.split(',')[0][4:],     # rip out uid=
				'uidNumber'           : int(entry['uidNumber'][0]),
				'gidNumber'           : int(entry['gidNumber'][0]),
				'homeDirectory' : entry['homeDirectory'][0],
				'groups'        : set(),
					# a cache which will eventually be filled by
					# groups.__init__() and others in this set().
				'backend'      : self.name,
				'action'       : None
				}

			def account_lock(value, tmp_entry=temp_user_dict):
				if value[0] == '!':
					tmp_entry['locked'] = True
					# the shell could be /bin/bash (or else), this is valid
					# for system accounts, and for a standard account this
					# means it is not strictly locked because SSHd will
					# bypass password check if using keypairs...
					# don't bork with a warning, this doesn't concern us
					# (Licorn work 99% of time on standard accounts).
				else:
					tmp_entry['locked'] = False

				return value

			for key, func in (
				('loginShell', str),
				('gecos', str),
 				('userPassword', account_lock),
				('shadowLastChange', int),
				('shadowMin', int),
				('shadowMax', int),
				('shadowWarning', int),
				('shadowInactive', int),
				('shadowExpire', int),
				('shadowFlag', str),
				('description', str)
				):
				if entry.has_key(key):
					temp_user_dict[key] = func(entry[key][0])

			if groups is not None:
				for g in groups.groups:
					for member in groups.groups[g]['members']:
						if member == entry[0]:
							temp_user_dict['groups'].add(
								groups.groups[g]['name'])

			# implicitly index accounts on « int(uidNumber) »
			users[ temp_user_dict['uidNumber'] ] = temp_user_dict

			# this will be used as a cache for login_to_uid()
			login_cache[ temp_user_dict['login'] ] = temp_user_dict['uidNumber']

		ltrace('ldap', '< load_users()')
		return users, login_cache
	def load_groups(self):
		""" Load groups from /etc/{group,gshadow} and /etc/licorn/group. """

		groups     = {}
		name_cache = {}

		ltrace('ldap', '> load_groups() %s' % self.nss_base_group)

		is_allowed  = True

		if UGBackend.users:
			l2u = UGBackend.users.login_to_uid
			u   = UGBackend.users.users

		try:
			ldap_result = self.ldap_conn.search_s(
				self.nss_base_group,
				ldap.SCOPE_SUBTREE,
				'(objectClass=posixGroup)')
		except ldap.NO_SUCH_OBJECT:
			return groups, name_cache

		for dn, entry in ldap_result:

			# Get the cn from the dn here, else we could end in a situation
			# where the group could not be deleted if it was created manually
			# and the cn is inconsistent.
			#'name'       : entry['cn'][0],
			name = dn.split(',')[0][3:]   # rip out 'cn=' and self.base
			gid  = int(entry['gidNumber'][0])

			# unlike unix_backend, this flag is related to one group, because
			# in ldap_backend, every change will be recorded one-by-one (no
			# global rewriting, it costs too much and is useless when we can do
			# only what really matters).
			need_rewriting = False

			if entry.has_key('memberUid'):
				members = set(entry['memberUid'])

				#ltrace('ldap', 'members of %s are:\n%s\n%s' % (
				#	name, members, entry['memberUid']))

				#
				# 2 things to do if a group has members:
				#	- populate the cache in users, to speed up future lookups
				#		in 'get users --long'. This code is also present in
				# 		users.__init__, to cope with users/groups loaded in
				#		different orders.
				#	- check all members really exist, else remove them.
				#

				to_remove = set()

				if UGBackend.users:
					for member in members:
						if UGBackend.users.login_cache.has_key(member):
							u[l2u(member)]['groups'].add(name)
						else:
							if self.warnings:
								logging.warning("User %s is referenced in " \
									"members of group %s but doesn't really " \
									"exist on the system, removing it." % \
									(styles.stylize(styles.ST_BAD, member),
									styles.stylize(styles.ST_NAME, name)))
							# don't directly remove member from members,
							# it will immediately stop the for_loop.
							to_remove.append(member)

					if to_remove != set():
						need_rewriting = True
						for member in to_remove:
							members.remove(member)

			else:
				members = set()

			temp_group_dict = {
				'name'       : name,
				'gidNumber'  : gid,
				'memberUid'  : members,
				'permissive' : None,
				'backend'    : self.name,
				'action'     : 'update' if need_rewriting else None
				}

			for key, func in (
				('userPassword', str),
				('groupSkel', str),
				('description', str)
				):
				if entry.has_key(key):
					temp_group_dict[key] = func(entry[key][0])

			# index groups on GID (an int)
			groups[gid] = temp_group_dict

			# this will be used as a cache by name_to_gid()
			name_cache[ temp_group_dict['name'] ] = gid

			try:
				groups[gid]['permissive'] = \
					UGBackend.groups.is_permissive(
					name=groups[gid]['name'], gid = gid)
			except exceptions.InsufficientPermissionsError:
				# don't bother with a warning, the user is not an admin.
				# logging.warning("You don't have enough permissions to " \
				#	"display permissive states.", once = True)
				pass

			if need_rewriting:
				self.save_group(gid)

		ltrace('ldap', '< load_groups()')
		return groups, name_cache
	def save_users(self):
		""" save users into LDAP, but only those who need it. """

		users = UGBackend.users

		for uid in users.keys():
			if users[uid]['backend'] != self.name \
				or users[uid]['action'] is None:
				continue

			self.save_user(uid)

	def save_groups(self):
		""" Save groups into LDAP, but only those who need it. """

		groups = UGBackend.groups

		for gid in groups.keys():
			if groups[gid]['backend'] != self.name \
				or groups[gid]['action'] is None:
				continue

			self.save_group(gid)

	def bind(self):
		""" Bind as admin or user, when LDAP needs a stronger authentication."""
		ltrace('ldap','binding as %s.' % (
			styles.stylize(styles.ST_LOGIN, self.bind_dn)))

		if self.bind_as_admin:
			self.ldap_conn.bind_s(self.bind_dn, self.secret, ldap.AUTH_SIMPLE)
		else:
			# TODO: ask for password, then bind.
			pass

	def save_user(self, uid):
		""" Save one user in the LDAP backend.
			If updating, the entry will be dropped prior of insertion. """

		users  = UGBackend.users
		action = users[uid]['action']
		login  = users[uid]['login']

		if action is None:
			return

		import ldap.modlist

		#
		# see http://www.python-ldap.org/doc/html/ldap-modlist.html#module-ldap.modlist
		# for details.
		#
		ignore_list = (
			'login',    # duplicate of cn, used internaly
			'action',   # API internal information
			'backend',  # internal information
			'locked',   # representation of userPassword, not stored
			'groups'    # internal cache, not stored
			)

		try:
			self.bind()

			if action == 'update':

				ltrace('ldap','updating user %s.' % (
					styles.stylize(styles.ST_LOGIN, login)))

				(dn, old_entry) = self.ldap_conn.search_s(self.nss_base_shadow,
				ldap.SCOPE_SUBTREE, '(uid=%s)' % login)[0]

				#print str(users[uid])  + '\n'
				#print str(old_entry) + '\n'
				#print str(modifyModlist(old_entry, users[uid], ignore_list,ignore_oldexistent=1)) + '\n'

				self.ldap_conn.modify_s(dn, modifyModlist(
					old_entry, users[uid], ignore_list, ignore_oldexistent=1))

			elif action == 'create':

				ltrace('ldap','creating user %s.' % (
					styles.stylize(styles.ST_LOGIN, login)))

				#
				# prepare the LDAP entry like the LDAP daemon assumes it will
				# be.
				#
				users[uid]['cn'] = login
				users[uid]['objectClass'] = [
					'inetOrgPerson', 'posixAccount', 'shadowAccount']
				users[uid]['sn'] = users[uid]['gecos']

				self.ldap_conn.add_s(
					'uid=%s,%s' % (login, self.nss_base_shadow),
					addModlist(users[uid], ignore_list))
			else:
				logging.warning('%s: unknown action %s for user %s(uid=%s).' % (
					self.name, action, login, uid))
		except (
			ldap.NO_SUCH_OBJECT,
			ldap.INVALID_CREDENTIALS,
			ldap.STRONG_AUTH_REQUIRED
			), e:
			logging.warning(e[0]['desc'])

		users[uid]['action'] = None

	def save_group(self, gid):
		""" Save one group in the LDAP backend.
			If updating, the entry will be dropped prior of insertion. """

		groups = UGBackend.groups
		action = groups[gid]['action']
		name   = groups[gid]['name']

		if action is None:
			return

		import ldap.modlist

		#
		# see http://www.python-ldap.org/doc/html/ldap-modlist.html#module-ldap.modlist
		# for details.
		#
		ignore_list = (
			'name',       # duplicate of cn, used internaly
			'action',     # API internal information
			'backend',    # internal information
			'permissive'  # representation of on-disk ACL, not stored
			)

		try:
			self.bind()

			if action == 'update':

				(dn, old_entry) = self.ldap_conn.search_s(self.nss_base_group,
				ldap.SCOPE_SUBTREE, '(cn=%s)' % name)[0]

				ltrace('ldap','updating group %s.' % \
					styles.stylize(styles.ST_LOGIN, name))

				""": \n%s\n%s\n%s.' % (
					styles.stylize(styles.ST_LOGIN, name),
					groups[gid],
					old_entry,
					modifyModlist(
					old_entry, groups[gid], ignore_list, ignore_oldexistent=1)))
				"""
				self.ldap_conn.modify_s(dn, modifyModlist(
					old_entry, groups[gid], ignore_list, ignore_oldexistent=1))
			elif action == 'create':

				ltrace('ldap','creating group %s.' % (
					styles.stylize(styles.ST_LOGIN, name)))

				#
				# prepare the LDAP entry like the LDAP daemon assumes it will
				# be.
				#
				groups[gid]['cn'] = name
				groups[gid]['objectClass'] = [
					'posixGroup', 'licornGroup']

				self.ldap_conn.add_s(
					'cn=%s,%s' % (name, self.nss_base_group),
					addModlist(groups[gid], ignore_list))
			else:
				logging.warning('%s: unknown action %s for group %s(gid=%s).' % (
					self.name, action, name, gid))
		except (
 			ldap.NO_SUCH_OBJECT,
			ldap.INVALID_CREDENTIALS,
			ldap.STRONG_AUTH_REQUIRED
			), e:
			# there is also e['info'] on ldap.STRONG_AUTH_REQUIRED, but
			# it is just repeat.
			logging.warning(e[0]['desc'])

		groups[gid]['action'] = None

	def delete_user(self, login):
		""" Delete one user from the LDAP backend. """

		try:
			self.bind()
			self.ldap_conn.delete_s('uid=%s,%s' % (login, self.nss_base_shadow))

		except ldap.NO_SUCH_OBJECT:
			pass
		# except BAD_BIND:
		#	pass
	def delete_group(self, name):
		""" Delete one group from the LDAP backend. """

		try:
			self.bind()
			self.ldap_conn.delete_s('cn=%s,%s' % (name, self.nss_base_group))

		except ldap.NO_SUCH_OBJECT:
			pass
		# except BAD_BIND:
		#	pass
