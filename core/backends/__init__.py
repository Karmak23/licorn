# -*- coding: utf-8 -*-
"""
Licorn Daemon backend abstract class.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os

backends = []

for entry in os.listdir(__path__[0]) :
	if entry == '__init__.py' : continue
	if entry[-3:] == '.py' :
		modname = entry[:-3]
		exec('from licorn.core.backends.%s import %s_backend' % (modname, modname))

l = locals()
for modname in l.keys() :
	if modname[-8:] == '_backend' :
		backends.append(l[modname])
