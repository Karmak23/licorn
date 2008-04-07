# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2007 Olivier Cortès <oc@5sys.fr>
Licensed under the terms of the GNU GPL version 2

"""

# this @@-tag will be replaced by the package release version.
# this is left to the package maintainer, don't alter it here.
__version__ = '@@VERSION@@'
version     = __version__

__all__ = [
	# TODO: move this elsewhere ? interfaces/cli ? 
	#		pull this out of 'foundations". see ROADMAP.
	'styles',
	'logging',       
	'options',

	# internal workflows mechanisms
	'exceptions',
	'hooks',
	'transactions',
	
	# classes, objects, very low-level utility functions
	'objects',
	'file_locks',
	'fsapi',
	'process',
	'hlstr',
	'pyutils'
	]

from _options import LicornOptions
options = LicornOptions()
