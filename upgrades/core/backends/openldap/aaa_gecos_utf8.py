# -*- coding: utf-8 -*-

from licorn.foundations           import logging
from licorn.foundations           import events
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core import LMC

try:
	import ldap.schema

except:
	# if ldap is not installed, just skip the current upgrade module.
	pass

else:

	@events.handler_function
	def backend_openldap_check_finished(*args, **kwargs):
		""" TODO: please implement http://dev.licorn.org/ticket/327 here. """

		backend      = LMC.backends.openldap
		ssse, schema = ldap.schema.urlfetch('ldapi:///')
		schema_attr  = schema.get_obj(ldap.schema.AttributeType, 'gecos')

		if schema_attr.syntax == '1.3.6.1.4.1.1466.115.121.1.26':
			# The LDAP 'gecos' field is currently ascii only: we need to update the
			# schema to setup an utf8 field. See backends/openldap.py for more info.

			try:
				# we need to bind as root via SASL to replace a schema.
				backend.sasl_bind()

				backend.modify_schema('nis-utf8', batch=True, full_display=False)

			except:
				logging.exception(_(u'{0}: impossible to reload {1} schema '
					u'into {2}!').format(backend.pretty_name,
						stylize(ST_NAME, 'nis'), stylize(ST_NAME, 'slapd')))

			logging.notice(_(u'{0}: updated {1} schema to support utf-8 '
				u'gecos.').format(backend.pretty_name, stylize(ST_NAME, 'nis')))

