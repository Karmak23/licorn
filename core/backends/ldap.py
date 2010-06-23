# -*- coding: utf-8 -*-
"""
Licorn Core LDAP backend.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import os
import re

from licorn.foundations         import logging, exceptions, styles, pyutils
from licorn.foundations         import objects, readers, process
from licorn.foundations.objects import LicornConfigObject, UGBackend

class ldap_backend(UGBackend):
	""" LDAP Backend for users and groups.

		TODO: implement auto-setup part: if backends.ldap.enabled is forced to
		True in licorn.conf, we should auto-install packages, setup dirs, LDAP
		dn, etc.
	"""
	def __init__(self, configuration, users = None, groups = None):
		UGBackend.__init__(self, configuration, users, groups)
		"""
			/etc/ldap.conf must use:

			base dc=licorn,dc=local
			uri ldapi:///127.0.0.1
			rootbinddn cn=admin,dc=licorn,dc=local

			/etc/ldap.secret must be present
		"""
		self.name    = "LDAP"
		self.enabled = False
		self.files   = LicornConfigObject()
		self.files.ldap_conf      = "/etc/ldap.conf"
		self.files.ldap_secret    = '/etc/ldap.secret'
		self.files.ldap_ldap_conf = '/etc/ldap/ldap.conf'


		if self.check_system(minimal=True):

			self.bind_as_manager = False

			try:
				# if we have access to ldap.secret, we are root.
				# we will bind as manager.

				self.secret = open(self.files.ldap_secret).read().strip()

				self.bind_dn = self.rootbinddn
				self.bind_as_manager = True

			except (IOError, OSError), e:
				if e.errno == 13:
					# permission denied.
					# we will bind as current user.
					self.bind_dn = 'uid=%s,%s' % (process.whoami(), self.base)

				else:
					raise e

			logging.info('%s: binding as %s.' % (
			self.__class__, styles.stylize(styles.ST_LOGIN, self.bind_dn)))

			# finally, if we reach here, the LDAP backend can be used !
			self.enabled = True

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
				% styles.stylize(styles.ST_SECRET, ldap_secret), auto_answer):

				try:
					from licorn.foundations import hlstr
					genpass = hlstr.generate_password(
					self.configuration.mAutoPasswdSize)

					logging.notice(logging.SYSU_AUTOGEN_PASSWD % (
						styles.stylize(styles.ST_LOGIN, 'manager'),
						styles.stylize(styles.ST_SECRET, password)))

					open(ldap_secret, 'w').write(genpass + '\n')

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
				ldap_secret, self.configuration.app_name))
		except (OSError, IOError), e :
			if e.errno != 13:
				raise e

		#pyutils.check_file_against_dict(self.files.ldap_ldap_conf,
		#	(('BASE', self.base), ('URI', self.uri)), self.configuration)

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
			'backends.ldap.base_dn'      : base_dn,
			'backends.ldap.uri'          : 'ldapi:///%s' % server,
			'backends.ldap.rootbinddn'   : 'cn=admin,%s' % base_dn,
			'backends.ldap.__ldap_secret': '',
			'backends.ldap.enabled'      : False
			}
	def save_users(self, users):
		pass
	def save_groups(self, groups):
		pass
