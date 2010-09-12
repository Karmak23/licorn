# -*- coding: utf-8 -*-
"""
Licorn Core LDAP backend.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import os
import re
import ldap
import hashlib
from base64 import encodestring, decodestring

from licorn.foundations           import logging, exceptions, styles, pyutils
from licorn.foundations           import readers, process
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.objects   import LicornConfigObject, UGMBackend, Singleton
from licorn.foundations.ldaputils import addModlist, modifyModlist, LicornSmallLDIFParser

class ldap_controller(UGMBackend, Singleton):
	""" LDAP Backend for users and groups.

		TODO: implement auto-setup part: if backends.ldap.available is forced to
		True in licorn.conf, we should auto-install packages, setup dirs, LDAP
		dn, etc.
	"""

	init_ok = False

	def __init__(self, configuration, users=None, groups=None, warnings=True):
		""" Init the LDAP backend instance. """

		if ldap_controller.init_ok:
			return

		UGMBackend.__init__(self, configuration, users, groups)

		ltrace('ldap', '| __init__().')
		self.name     = "ldap"
		self.compat   = ('ldap')
		self.priority = 5
		self.files             = LicornConfigObject()
		self.files.ldap_conf   = '/etc/ldap.conf'
		self.files.ldap_secret = '/etc/ldap.secret'

		ldap_controller.init_ok = True

	def __del__(self):
		try:
			self.ldap_conn.unbind_s()
		except:
			pass
	def load_defaults(self):
		""" Return mandatory defaults needed for LDAP Backend.

		TODO: what the hell is good to set defaults if pam-ldap and libnss-ldap
		are not used ? If they are in use, everything is already set up in
		system files, no ? This needs to be rethought, to avoid doing the job
		twice.
		"""

		ltrace('ldap', '| load_defaults().')

		if UGMBackend.configuration.daemon.role == 'client':
			waited = 0.1
			while UGMBackend.configuration.server is None:
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

		# Stay local (unix socket) for nows
		# if server is None:
		self.uri             = 'ldapi:///'
		self.base            = 'dc=meta-it,dc=local'
		self.rootbinddn      = 'cn=admin,%s' % self.base
		self.secret          = 'metasecret'
		self.nss_base_group  = 'ou=Groups'
		self.nss_base_passwd = 'ou=People'
		self.nss_base_shadow = 'ou=People'
	def initialize(self, enabled=True):
		"""	try to start it without any tests (it should work if it's
			installed) and become available.
			If that fails, try to guess a little and help user resolving issue.
			else, just fail miserably.

		setup the backend, by gathering LDAP related configuration in system
		files. """

		self.load_defaults()

		ltrace('ldap', '> initialize().')

		try:
			for (key, value) in readers.simple_conf_load_dict(
					self.files.ldap_conf).iteritems():
				setattr(self, key, value)

			# add the self.base extension to self.nss_* if not present.
			for attr in (
				'nss_base_group',
				'nss_base_passwd',
				'nss_base_shadow'):
				value = getattr(self, attr)
				try:
					i = value.index(self.base)
				except ValueError:
					setattr(self, attr, '%s,%s' % (value, self.base))

			# assume we are not admin, then see if we are.
			self.bind_as_admin = False

			try:
				# if we have access to /etc/ldap.secret, we are root.

				self.secret = open(self.files.ldap_secret).read().strip()
				self.bind_dn = self.rootbinddn
				self.bind_as_admin = True

			except (IOError, OSError), e:
				if e.errno == 13:
					# permission denied.
					# we will bind as current user.
					self.bind_dn = 'uid=%s,%s' % (process.whoami(), self.base)
					#
					# NOTE 1: ask the user for his/her password, because the
					# server will refuse a binding without a password.
					#
					# NOTE 2: if the current user is not in the LDAP tree, we
					# must bind with external SASL, which will likely not work
					# because any other user than root / cn=admin has no right
					# on the LDAP tree.
					#
					# CONCLUSION: this case is not handled yet, because on
					# a regular LDAP-enabled Licorn system, the user:
					#	- is either root, thus cn=admin
					#	- is a LDAP user, and thus can bind correctly.

				elif e.errno == 2:
					# no such file or directory. Assume we are root and fill
					# the default password in the file. This will make
					# everything go smoother.

					logging.notice('''seting up default password in %s. You '''
						'''can change it later if you want by running '''
						'''FIXME_COMMAND_HERE.''' % (
						styles.stylize(styles.ST_PATH, self.files.ldap_secret)))

					open(self.files.ldap_secret, 'w').write(self.secret)
					self.bind_dn = self.rootbinddn
					self.bind_as_admin = True

				else:
					raise e

			self.check_defaults()

			self.ldap_conn = ldap.initialize(self.uri)

			self.available = True

		except (IOError, OSError), e:
			if e.errno != 2:
				if os.path.exists(self.files.ldap_conf):
					logging.warning('''Problem initializing the LDAP backend.'''
					''' LDAP seems installed but not configured or unusable. '''
					'''Please run 'sudo chk config -evb' to correct. '''
					'''(was: %s)''' % e)
			elif e.errno == 2:
				# ldap.conf not present -> pam-ldap not installed -> just
				# discard the LDAP backend completely.
				pass
			else:
				# another problem worth noticing.
				raise e

		ltrace('ldap', '< initialize() %s.' % self.available)
		return self.available
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
	def enable(self):
		""" Do whatever is needed on the underlying system for the LDAP backend
		to be fully operational (this is really a "force_enable" method).
		This includes:
			- verify everything is installed
			- setup PAM-LDAP system files (the system must follow the licorn
				configuration and vice-versa)
			- setup slapd
			- setup nsswitch.conf

		-> raise an exception at any level if anything goes wrong.
		-> return True if succeed (this is probably useless due to to previous
		point).
		"""

		ltrace('ldap', '| enable_backend()')

		if not ('ldap' in self.configuration.nsswitch['passwd'] and \
			'ldap' in self.configuration.nsswitch['shadow'] and \
			'ldap' in self.configuration.nsswitch['group']) :

			self.configuration.nsswitch['passwd'].append('ldap')
			self.configuration.nsswitch['shadow'].append('ldap')
			self.configuration.nsswitch['group'].append('ldap')
			self.configuration.save_nsswitch()

		self.check_system_files(batch=True)

		self.check(batch=True)

		"""
		for expression in (
			('passwd:.*ldap.*', ''),
			('passwd:.*ldap.*', ''),
			('passwd:.*ldap.*', ''),
		re.susbt(r'')
		"""
		return True
	def disable(self):
		""" make the LDAP backend inoperant. The receipe is simple, and follows
		what the system sees: just modify nsswitch.conf, and neither licorn nor
		PAM nor anything will use LDAP anymore.

		We don't "unsetup" slapd nor PAM-ldap because we think this is a bad
		thing thing to empty them if they have been in use. It is left to the
		system administrator to clean them up if wanted.
		"""

		ltrace('ldap', '| disable_backend()')

		for key in ('passwd', 'shadow', 'group'):
			try:
				self.configuration.nsswitch[key].remove('ldap')
			except KeyError:
				pass

		self.configuration.save_nsswitch()

		return True
	def check(self, batch=False, auto_answer=None):
		""" check the OpenLDAP daemon configuration and set it up if needed. """
		ltrace('ldap', '> check()')

		if process.whoami() != 'root' and not self.bind_as_admin:
			logging.warning('''%s: you must be root or have cn=admin access'''
			''' to continue.''' % self.name)
			return

		self.sasl_bind()

		try:
			# load all config objects from the daemon.
			# there may be none, eg on a fresh install.
			#
			ldap_result = self.ldap_conn.search_s(
				'cn=config',
				ldap.SCOPE_SUBTREE,
				'(objectClass=*)',
				['dn', 'cn'])

			# they will be checked later, extract them and keep them hot.
			dn_already_present = [ x for x,y in ldap_result ]

		except ldap.NO_SUCH_OBJECT:
			dn_already_present = []

		try:
			# search for the frontend, which is not in cn=config
			ldap_result = self.ldap_conn.search_s(
				self.base,
				ldap.SCOPE_SUBTREE,
				'(objectClass=*)',
				['dn', 'cn'])

			dn_already_present.extend([ x for x,y in ldap_result ])
		except ldap.NO_SUCH_OBJECT:
			# just forget this error, the schema will be automatically added
			# if not found.
			pass

		# DEVEL DEBUG
		#
		#print dn_already_present
		#for dn, entry in ldap_result:
		#	ltrace('ldap', '%s -> %s' % (dn, entry))

		# Here follows a list of which DN to check for presence, associated to
		# which ldap_schema to load if the corresponding DN is not present in
		# slapd configuration.
		defaults = (
			# SKIP dn: cn=config (should be already there at fresh install)
			# SKIP dn: cn=schema,cn=config (filled by followers)
			('cn={0}core,cn=schema,cn=config', 'core'),
			('cn={1}cosine,cn=schema,cn=config', 'cosine'),
			('cn={2}nis,cn=schema,cn=config', 'nis'),
			('cn={3}inetorgperson,cn=schema,cn=config', 'inetorgperson'),
			('cn={4}samba,cn=schema,cn=config', 'samba'),
			('cn={5}licorn,cn=schema,cn=config', 'licorn'),
			('cn=module{0},cn=config', 'backend.module'),
			('olcDatabase={1}hdb,cn=config', 'backend.hdb'),
			# ALREADY INCLUDED olcDatabase={-1}frontend,cn=config
			# ALREADY INCLUDED olcDatabase={0}config,cn=config
			# and don't forget the frontend, handled in a special way (not with
			# root user, but LDAP cn=admin).
			(self.base, 'frontend')
			)

		to_load = []

		for dn, schema in defaults:

			if not dn in dn_already_present:
				if batch or logging.ask_for_repair('''%s: %s lacks '''
						'''mandatory schema %s.''' % (
							self.name,
							styles.stylize(styles.ST_PATH, 'slapd'),
							schema),
						auto_answer):

					# circumvent https://bugs.launchpad.net/ubuntu/+source/openldap/+bug/612525
					if schema == 'backend.hdb':
						try:
							logging.notice('disabling AppArmor profile for slapd.')
							os.system('echo -n /usr/sbin/slapd > /sys/kernel/security/apparmor/.remove')
						except Exception, e:
							logging.warning(e)

					if schema == 'frontend':
						# the frontend is a special case which can't be filled by root.
						# We have to bind as cn=admin, else it will fail with
						# "Insufficient privileges" error.
						self.bind()

					logging.info('%s: loading schema %s into slapd.' % (
						self.name, schema))

					for (dn, entry) in LicornSmallLDIFParser(schema).get():
						try:
							logging.progress('''adding %s -> %s into '''
								'''schema %s.''' % (dn, entry, schema))

							self.ldap_conn.add_s(dn, addModlist(entry))
						except ldap.ALREADY_EXISTS:
							logging.notice('skipping already present dn %s.' \
								% dn)

					# circumvent https://bugs.launchpad.net/ubuntu/+source/openldap/+bug/612525
					if schema == 'backend.hdb':
						try:
							logging.notice('enabling AppArmor profile for slapd.')
							os.system('/sbin/apparmor_parser --write-cache --replace -- /etc/apparmor.d/usr.sbin.slapd')
						except Exception, e:
							logging.warning(e)

				else:
					# all these schemas are mandatory for Licorn to work,
					# we should not reach here.
					raise exceptions.LicornRuntimeError(
						'''Can't continue without altering slapd '''
						'''configuration.''')

		ltrace('ldap', '< check()')
	def check_system_files(self, batch=False, auto_answer=None):
		""" Check that the underlying system is ready to go LDAP. """

		ltrace('ldap', '> check_system_files()')

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
			if not os.path.exists(self.files.ldap_secret) or \
				open(self.files.ldap_secret).read().strip() == '':
				if batch or logging.ask_for_repair(
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
		# TODO: check ldap_ldap_conf contents, or verify by researcu that it is
		# useless nowadays.
		#

		ltrace('ldap', '< check_system() %s.' % styles.stylize(
			styles.ST_OK, 'True'))
		return True
	def is_available(self):
		""" Check if pam-ldap and slapd are installed.
		This function fo not check if they are *configured*. We must assume
		they are, else this would cost too much. There are dedicated functions
		to check and alter the configuration. """

		if os.path.exists(self.files.ldap_conf) \
			and os.path.exists("/etc/ldap/slapd.d"):
			# if all of these exist, libpam-ldap and slapd are installed. It
			# is fine to assume that we can use them to handle the backend data.
			# Else, just forget about it.
			return True

		return False
	def load_users(self):
		""" Load user accounts from /etc/{passwd,shadow} """
		users       = {}
		login_cache = {}

		ltrace('ldap', '> load_users() %s' % self.nss_base_shadow)

		if process.whoami() == 'root':
			self.bind(False)

		try:
			ldap_result = self.ldap_conn.search_s(
				self.nss_base_shadow,
				ldap.SCOPE_SUBTREE,
				'(objectClass=shadowAccount)')
		except ldap.NO_SUCH_OBJECT:
			return users, login_cache

		for dn, entry in ldap_result:

			ltrace('ldap', '  load_user(%s)' % entry)

			temp_user_dict	= {
				# Get the cn from the dn here, else we could end in a situation
				# where the user could not be deleted if it was created manually
				# and the cn is inconsistent.
				#'login'        : entry['uid'][0],
				'login'         : dn.split(',')[0][4:],     # rip out uid=
				'uidNumber'     : int(entry['uidNumber'][0]),
				'gidNumber'     : int(entry['gidNumber'][0]),
				'homeDirectory' : entry['homeDirectory'][0],
				'groups'        : set(),
					# a cache which will eventually be filled by
					# groups.__init__() and others in this set().
				'backend'      : self.name,
				'action'       : None
				}

			def account_lock(value, tmp_entry=temp_user_dict):
				try:
					# get around an error where password is not base64 encoded.
					password = decodestring(value.split('}',1)[1])
				except Exception:
					password = value

				if password[0] == '!':
					tmp_entry['locked'] = True
					# the shell could be /bin/bash (or else), this is valid
					# for system accounts, and for a standard account this
					# means it is not strictly locked because SSHd will
					# bypass password check if using keypairs...
					# don't bork with a warning, this doesn't concern us
					# (Licorn work 99% of time on standard accounts).
				else:
					tmp_entry['locked'] = False

				return password
			def gecos_decode(value):
				try:
					# get around an error where password is not base64 encoded.
					gecos = decodestring(value)
				except:
					gecos = value

				return gecos

			for key, func in (
				('loginShell', str),
				('gecos', gecos_decode),
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

			#ltrace('ldap', 'userPassword: %s' % temp_user_dict['userPassword'])

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

		if UGMBackend.users:
			l2u = UGMBackend.users.login_to_uid
			u   = UGMBackend.users.users

		try:
			ldap_result = self.ldap_conn.search_s(
				self.nss_base_group,
				ldap.SCOPE_SUBTREE,
				'(objectClass=posixGroup)')
		except ldap.NO_SUCH_OBJECT:
			return groups, name_cache

		for dn, entry in ldap_result:

			ltrace('ldap', '  load_group(%s).' % entry)

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
				# Here we populate the cache in users, to speed up future
				# lookups in 'get users --long'.

				if UGMBackend.users:
					for member in members:
						if UGMBackend.users.login_cache.has_key(member):
							u[l2u(member)]['groups'].add(name)
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
					UGMBackend.groups.is_permissive(
					name=groups[gid]['name'], gid = gid)
			except exceptions.InsufficientPermissionsError:
				# don't bother with a warning, the user is not an admin.
				# logging.warning("You don't have enough permissions to " \
				#	"display permissive states.", once = True)
				pass

		ltrace('ldap', '< load_groups()')
		return groups, name_cache
	def save_users(self):
		""" save users into LDAP, but only those who need it. """

		users = UGMBackend.users

		for uid in users.keys():
			if users[uid]['backend'] != self.name \
				or users[uid]['action'] is None:
				continue

			self.save_user(uid)

	def save_groups(self):
		""" Save groups into LDAP, but only those who need it. """

		groups = UGMBackend.groups

		for gid in groups.keys():
			if groups[gid]['backend'] != self.name \
				or groups[gid]['action'] is None:
				continue

			self.save_group(gid)


	def sasl_bind(self):
		"""
		Gain superadmin access to the OpenLDAP server.
		This is far more than simple "cn=admin,*" access.
		We are going to navigate the configuration and setup
		the server if needed.

		by the way, fix #133.
		"""

		ltrace('ldap', 'binding as root in SASL/external mode.')

		import ldap.sasl
		auth=ldap.sasl.external()
		self.ldap_conn.sasl_interactive_bind_s('', auth)

	def bind(self, need_write_access=True):
		""" Bind as admin or user, when LDAP needs a stronger authentication."""
		ltrace('ldap','binding as %s.' % (
			styles.stylize(styles.ST_LOGIN, self.bind_dn)))

		if self.bind_as_admin:
			try:
				self.ldap_conn.bind_s(self.bind_dn, self.secret, ldap.AUTH_SIMPLE)
			except ldap.INVALID_CREDENTIALS:
				# in rare cases, the error could raise because the LDAP DB is
				# totally empty.
				# try to bind as root as a last resort, in case we can correct
				# the problem (we are probably in the first intialization of the
				# backend, checking for everything).
				self.sasl_bind()
		else:
			if process.whoami() == 'root':
				self.sasl_bind()
			else:
				if need_write_access:
					#
					# this will lamentably fail if current user is not in LDAP tree,
					# eg any system non-root user, any shadow user, etc. see
					# self.initialize() for details.
					#
					import getpass
					self.ldap_conn.bind_s(self.bind_dn,
						getpass.getpass('Please enter your LDAP password: '),
						ldap.AUTH_SIMPLE)
				#else:
				# do nothing. We hit this case in all "get" commands, which
				# don't need write access to the LDAP tree. With this, standard
				# users can query the LDAP tree, without beiing bothered by a
				# password-ask; they will get back only the data they have read
				# access to, which seems quite fine.

	def save_user(self, uid):
		""" Save one user in the LDAP backend.
			If updating, the entry will be dropped prior of insertion. """

		# we have to duplicate the data, to avoid #206
		user  = UGMBackend.users[uid].copy()

		action = user['action']
		login  = user['login']

		if action is None:
			return


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

		# prepare this field in the form slapd expects it.
		user['userPassword'] = \
			'{SHA}' + encodestring(user['userPassword']).strip()

		try:
			self.bind()

			if action == 'update':

				(dn, old_entry) = self.ldap_conn.search_s(self.nss_base_shadow,
				ldap.SCOPE_SUBTREE, '(uid=%s)' % login)[0]

				# update these fields to match the eventual new value.
				user['cn'] = user['gecos']
				user['sn'] = user['gecos']
				user['givenName'] = user['gecos']

				# reencode this field, for slapd not to whym.
				user['gecos'] = encodestring(user['gecos']).strip()

				ltrace('ldap', 'update user %s: %s\n%s' % (
					styles.stylize(styles.ST_LOGIN, login),
					old_entry,
					modifyModlist(old_entry, user,
						ignore_list, ignore_oldexistent=1)))

				self.ldap_conn.modify_s(dn, modifyModlist(
					old_entry, user, ignore_list, ignore_oldexistent=1))

			elif action == 'create':

				# prepare the LDAP entry like the LDAP daemon assumes it will
				# be : add or change necessary fields.
				user['objectClass'] = [
					'inetOrgPerson', 'posixAccount', 'shadowAccount']

				# we should Split these, but we don't have any reliable manner
				# to do it (think of multi firstnames, composite lastnames, etc)
				user['cn'] = user['gecos']
				user['sn'] = user['gecos']
				user['givenName'] = user['gecos']

				# GECOS is IA5 only (ASCII 7bit). Anyway, it seems not used
				# nowadays, and CN is prefered. We fill it for [put anything
				# usefull here] purposes only
				user['gecos'] = encodestring(user['gecos']).strip()

				ltrace('ldap', 'add user %s: %s' % (
					styles.stylize(styles.ST_LOGIN, login),
					addModlist(user, ignore_list)))

				self.ldap_conn.add_s(
					'uid=%s,%s' % (login, self.nss_base_shadow),
					addModlist(user, ignore_list))
			else:
				logging.warning('%s: unknown action %s for user %s(uid=%s).' %(
					self.name, action, login, uid))
		except (
			ldap.NO_SUCH_OBJECT,
			ldap.INVALID_CREDENTIALS,
			ldap.STRONG_AUTH_REQUIRED
			), e:
			logging.warning(e[0]['desc'])

		# reset the action
		UGMBackend.users[uid]['action'] = None

	def save_group(self, gid):
		""" Save one group in the LDAP backend.
			If updating, the entry will be dropped prior of insertion. """

		# we have to duplicate the data, to avoid #206
		group = UGMBackend.groups[gid].copy()
		action = group['action']
		name   = group['name']

		if action is None:
			return

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
					old_entry, group, ignore_list, ignore_oldexistent=1))
			elif action == 'create':

				ltrace('ldap','creating group %s.' % (
					styles.stylize(styles.ST_LOGIN, name)))

				#
				# prepare the LDAP entry like the LDAP daemon assumes it will
				# be.
				#
				group['cn'] = name
				group['objectClass'] = [
					'posixGroup', 'licornGroup']

				self.ldap_conn.add_s(
					'cn=%s,%s' % (name, self.nss_base_group),
					addModlist(group, ignore_list))
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

		# reset the action
		UGMBackend.groups[gid]['action'] = None

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
	def compute_password(self, password, salt=None):
		return hashlib.sha1(password).digest()
