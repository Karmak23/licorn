# -*- coding: utf-8 -*-
"""
Licorn Core LDAP backend.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import os

from licorn.foundations.objects import LicornConfigObject, UGBackend

from licorn.core.internals import readers

class ldap_backend(UGBackend) :
	""" LDAP Backend for users and groups.

		TODO: implement auto-setup part: if backends.ldap.enabled is forced to
		True in licorn.conf, we should auto-install packages, setup dirs, LDAP
		dn, etc.
		
		TODO: implement samba part.
	
	"""
	def __init__(self, configuration, users = None, groups = None) :
		UGBackend.__init__(self, configuration, users, groups)
		"""
			/etc/ldap.conf must use :
			
			base dc=licorn,dc=local
			uri ldapi:///127.0.0.1
			rootbinddn cn=admin,dc=licorn,dc=local

			/etc/ldap.secret must be present
		"""
		self.name    = "LDAP"
		self.enabled = False
		
		if os.path.exists('/etc/ldap.conf') :

			conf = readers.simple_conf_load_dict('/etc/ldap.conf')

			for key in conf.keys() :
				setattr(self, key, conf[key])

			if os.path.exists('/etc/ldap.secret') :
				try :
					self.__ldap_secret = \
						open('/etc/ldap.secret').read().strip()

				except (IOError, OSError), e :
					if e.errno != 13 :
						raise e

				self.enabled = True

	def get_defaults(self) :
		""" Return mandatory defaults needed for LDAP Backend.

		TODO: what the hell is good to set defaults if pam-ldap and libnss-ldap
		are not used ?
		If they are in use, everything is already set up in system files, no ?
		"""

		base_dn = 'dc=licorn,dc=local'

		if self.configuration.daemon.role == 'client' :
			waited = 0.1
			while self.configuration.server is None :
				#
				time.sleep(0.1)
				wait += 0.1
				if wait > 5 :
					# FIXME: this is not the best thing to do, but server
					# detection needs a little more love and thinking.
					raise exceptions.LicornRuntimeException(
						'No server detected, bailing out…' )
			server = self.configuration.server

		else :
			server = '127.0.0.1'

		return {
			'backends.ldap.base_dn'       : base_dn,
			'backends.ldap.uri'           : 'ldapi:///%s' % server,
			'backends.ldap.rootbinddn'    : 'cn=admin,%s' % base_dn,
			'backends.ldap.__ldap_secret' : '',
			'backends.ldap.enabled'       : False
			}
	def save_all(self, users, groups) :
		self.save_users(users)
		self.save_groups(groups)

	def save_users(self, users) :
		pass

	def save_groups(self, groups) :
		pass
