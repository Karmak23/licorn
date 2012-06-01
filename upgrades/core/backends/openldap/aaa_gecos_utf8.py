# -*- coding: utf-8 -*-



import ldap.schema

from licorn.foundations           import logging, exceptions, settings
from licorn.foundations           import ldaputils, hlstr, pyutils, events
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core import LMC

@events.handler_function
def backend_openldap_check_finished(*args, **kwargs):
	""" TODO: please implement http://dev.licorn.org/ticket/327 here. """

	pname = stylize(ST_NAME, 'upgrades')

	backend = LMC.backends.openldap

	# The old searching way:
	#~ try:
		#~ openldap_result = backend.openldap_conn.search_s(
								#~ 'cn={2}nis,cn=schema,cn=config',
								#~ pyldap.SCOPE_SUBTREE,
								#~ '(objectClass=*)',
								#~ ['dn', 'cn']
							#~ )
	#~ except pyldap.NO_SUCH_OBJECT:
		#~ openldap_result = []
	# Keep them handy, they will be checked later.
	#~ dn_already_present = [ x for x, y in openldap_result ]

	# The new simpler way:
	ssse, schema = ldap.schema.urlfetch('ldapi:///')
	sa = schema.get_obj(ldap.schema.AttributeType, 'gecos')

	if sa.syntax == '1.3.6.1.4.1.1466.115.121.1.26':
		# The LDAP 'gecos' field is ascii only: we need to load our schema
		# which sets up an utf8 field. See backends/openldap.py for more info.

		try:
			# we need to bind as root via SASL to replace a schema.
			backend.sasl_bind()

			backend.modify_schema('nis-utf8', batch=True, full_display=False)

		except:
			logging.exception(_(u'{0}: impossible to reload {1} schema '
				u'into {2}!').format(backend.pretty_name,
					stylize(ST_NAME, 'nis'), stylize(ST_NAME, 'slapd')))

		logging.notice(_(u'{0}: reloaded {1} schema to support utf-8 '
			u'gecos.').format(backend.pretty_name, stylize(ST_NAME, 'nis')))

