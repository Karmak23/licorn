# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

# this @@-tag will be replaced by the package release version.
# this is left to the package maintainer, don't alter it here.
__version__ = '@@VERSION@@'
version     = __version__

__all__ = [
	# DEBUG / process tracing
	'ltrace',
	# basic output (CLI colors, verbose / quiet, etc)
	'options',
	'styles',
	'logging',

	# internal workflows mechanisms
	'exceptions',
	'hooks',
	'transactions',

	# classes, objects, very low-level utility functions
	'objects',
	'fsapi',
	'process',
	'hlstr',
	'pyutils'
	]

from _options import LicornOptions
options = LicornOptions()
