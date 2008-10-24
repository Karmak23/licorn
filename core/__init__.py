# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

core - The Core API of a Licorn system.

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>,
Licensed under the terms of the GNU GPL version 2

"""

# this @@VERSION@@ will be replaced by package maintainers, don't alter it here.
version = '@@VERSION@@'

__all__ = [
	'version',
	'users',
	'groups',
	'profiles',
	'keywords',
	'configuration',
	'options'
	]

from licorn.foundations      import exceptions, logging

from internals.configuration import LicornConfiguration
from internals.users         import UsersList
from internals.groups        import GroupsList
from internals.profiles      import ProfilesList
from internals.keywords      import KeywordsList

try :

	configuration = LicornConfiguration()
	users         = UsersList(configuration)
	groups        = GroupsList(configuration, users)
	profiles      = ProfilesList(configuration, groups, users)
	keywords      = KeywordsList(configuration)

except exceptions.LicornException, e :
	logging.error("Licorn core initialization failed:\n\t%s" % e)
