# -*- coding: utf-8 -*-
"""
Licorn upgrades: a facility to ease internal updates - http://docs.licorn.org/upgrades/

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
:license: GNU GPL version 2
"""

import sys, os
from licorn.foundations           import styles, logging, options
from licorn.foundations.styles    import *
from licorn.foundations.constants import verbose

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

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

logging.progress(_(u'Looking for upgrade modules in {0}…').format(
											stylize(ST_PATH, upgrades_root)))

# Load upgrades callbacks from the upgrades tree. Any file not named
# :file:`__init__.py` will be evaluated. Just name them alphabetically
# to make the callback be run in the order you want.
for root, dirs, files in os.walk(upgrades_root):
	for filename in sorted(files):
		if filename.endswith('.py') and filename != '__init__.py':

			module_dir  = root[len(upgrades_root)+1:].replace('/', '.')
			module_name = filename[:-3]

			# Don't even try to import things from '.' like this,
			# they are not meant to be standard upgrades modules,
			# just helpers (like 'common.py').
			if module_dir:
				try:
					exec 'from licorn.upgrades.{0}.{1} import *'.format(
								module_dir, module_name) in globals(), locals()

					logging.progress(_(u'Successfully imported upgrade module '
									u'{0}.').format(
										stylize(ST_NAME, '{0}.{1}'.format(
												module_dir,module_name))))
				except:
					logging.warning(_(u'Upgrade module {0} is unusable.').format(
										stylize(ST_NAME, '{0}.{1}'.format(
												module_dir,module_name))))

					# Raising the verbose level to display a full stack trace.
					# No need to save / restore the previous level, we will die.
					options.SetVerbose(verbose.PROGRESS)

					logging.exception(_(u'Please fix it before continuing '
										u'{0}').format(stylize(ST_IMPORTANT,
											_(u'(killing myself -9 NOW)'))))

					# This is the only way to terminate "abruptly": as we are
					# in plain daemon bootstrapping phase, any try to
					# terminate(), raise SystemExit or sys.exit() will fail
					# with more errors and crashes than the one we just avoided.
					os.kill(os.getpid(), 9)

# clean up unused variables, for when EventManager runs `dir()`
# on the current Python module. This is easier than constructing
# an exhaustive ``__all__`` containing the callback names, IMHO.
del os, root, dirs, files, filename
