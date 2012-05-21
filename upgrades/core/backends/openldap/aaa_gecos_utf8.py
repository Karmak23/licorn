# -*- coding: utf-8 -*-



import ldap      as pyldap
import ldap.sasl as pyldapsasl

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

	try:
		# Load all config objects from the daemon;
		# there may be none (on a fresh install).
		#
		openldap_result = backend.openldap_conn.search_s(
								'cn={2}nis,cn=schema,cn=config',
								pyldap.SCOPE_SUBTREE,
								'(objectClass=*)',
								['dn', 'cn']
							)

	except pyldap.NO_SUCH_OBJECT:
		openldap_result = []

	# Keep them handy, they will be checked later.
	dn_already_present = [ x for x, y in openldap_result ]

	if False:
		logging.info(_(u'{0}: updating slapd schemata…').format(pname))

