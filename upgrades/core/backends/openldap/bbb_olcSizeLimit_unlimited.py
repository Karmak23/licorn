# -*- coding: utf-8 -*-

from licorn.foundations           import logging, settings
from licorn.foundations           import ldaputils, events
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.constants import roles

from licorn.core import LMC

try:
	import ldap as pyldap

except:
	# if ldap is not installed, just skip the current upgrade module.
	pass

else:

	@events.callback_function
	def backend_openldap_check_finished(*args, **kwargs):

		if settings.role != roles.SERVER:
			# Only servers will check / upgrade their local slapd installation.
			# On other roles, they have no local `slapd`, thus nothing to upgrade.
			return

		backend = LMC.backends.openldap

		backend.sasl_bind()

		try:
			dn, data = backend.openldap_conn.search_s(
									'olcDatabase={-1}frontend,cn=config',
									pyldap.SCOPE_SUBTREE,
									'(objectClass=*)'
								)[0]

		except pyldap.NO_SUCH_OBJECT:
			# Just don't halt on this error, the schema will be
			# automatically added later if not found.
			pass

		else:
			operation = None

			if 'olcSizeLimit' in data:
				if data['olcSizeLimit'] == ['500']:
					# 500 is the default OpenLDAP limit. We will replace only
					# this particular value, leaving the local admin the
					# ability to set any other value he wants.

					operation = 'modify'
					mod_list  = ldaputils.modifyModlist(data,
												{'olcSizeLimit': ['unlimited']},
												ignore_oldexistent=1)

			else:
				operation = 'add'
				add_list  = ldaputils.addModlist({'olcSizeLimit': ['unlimited']})


			if operation:
				# we need to bind as root via SASL to alter a schema.
				backend.sasl_bind()

				try:
					if operation == 'add':
						# NOTE: as of 20120828, this 'add' operation is
						# untested, because the conditions are not encountered
						# on any of our servers (tests/production).
						backend.openldap_conn.add_s(dn, add_list)

					else:
						backend.openldap_conn.modify_s(dn, mod_list)

				except:
					logging.exception(_(u'{0}: impossible to alter {1} '
						u'olcSizeLimit value!').format(backend.pretty_name,
							stylize(ST_NAME, 'slapd')))

				logging.notice(_(u'{0}: updated {1} value to {2}.').format(
									backend.pretty_name,
									stylize(ST_ATTR, 'olcSizeLimit'),
									stylize(ST_ATTRVALUE, 'unlimited')))

