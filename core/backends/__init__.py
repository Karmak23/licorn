# -*- coding: utf-8 -*-
"""
Licorn core.backends autoload facility.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os

backends = []

for entry in os.listdir(__path__[0]):
	if entry == '__init__.py':
		continue
	if entry[-11:] == '_backend.py':
		modname = entry[:-3]		# minus '.py'
		backend_name = entry[:-11]	# minus '_backend.py'
		try :
			exec('from licorn.core.backends.%s import %s_controller as %s' % (
				modname, backend_name, backend_name))
			exec('backends.append(%s)' % backend_name)
		except ImportError:
			pass
