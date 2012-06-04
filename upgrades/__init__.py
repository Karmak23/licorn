# -*- coding: utf-8 -*-
"""
Licorn upgrades: a facility to ease internal updates - http://docs.licorn.org/upgrades/

:copyright: 
	* 2012 Olivier Cortès <olive@deep-ocean.net>
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
:license: GNU GPL version 2
"""

import os

# `module.name` is looked up by event manager in logging messages.
# This is just a "fake" variable to make the current module behave 
# more or less like any other Licorn® object, which all have a 
# `name` attribute.
name = 'upgrades'

# this is just a variable to avoid hardcoding the path everywhere.
upgrades_root = '/usr/share/licorn/upgrades'

# Create :file:`upgrades_root` symlink if it doesn't exist, by 
# guessing the path from the :program:`licornd` binary real 
# (resolved) path.
if not os.path.exists(upgrades_root):
	from licorn.foundations import fsapi
	os.symlink(os.path.join(fsapi.licorn_python_path, 'upgrades'), 
				upgrades_root)

# Load upgrades callbacks from the upgrades tree. Any file not named
# :file:`__init__.py` will be evaluated. Just name them alphabetically
# to make the callback be run in the order you want.
for root, dirs, files in os.walk(upgrades_root):
	for filename in sorted(files):
		if filename.endswith('.py') and filename != '__init__.py':
			exec 'from licorn.upgrades.{0}.{1} import *'.format(
				root[len(upgrades_root)+1:].replace('/', '.'),
					filename[:-3]) in globals(), locals()

# clean up unused variables, for when EventManager runs `dir()`
# on the current Python module. This is easier than constructing
# an exhaustive ``__all__`` containing the callback names, IMHO.
del os, root, dirs, files, filename
