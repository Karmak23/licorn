# -*- coding: utf-8 -*-

import os

from licorn.foundations           import logging, settings, events, fsapi
from licorn.foundations.events    import LicornEvent
from licorn.foundations.styles    import *
from licorn.foundations.constants import priorities
from licorn.core                  import LMC

@events.handler_function
def configuration_initialises(*args, **kwargs):
	""" Create the main directories if they don't exist.

		.. note:: this callback will be run *before*
			`core.configuration` loads (this is a handler,
			not a callback). It will only *create* the directories
			and won't check permissions on them, which must be done
			later when `users` and `groups` have loaded (this is
			handled by :func:`groups_loaded` later).
	"""

	for directory, dtype in (
					(settings.config_dir, _(u'configuration')),
					(settings.cache_dir, _(u'cache')),
					(settings.data_dir, _(u'data')),
				):

		if not os.path.exists(directory):
			try:
				os.makedirs(directory)

				logging.info(_(u'Created {1} directory {0}.').format(
								stylize(ST_PATH, directory), dtype))

			except (IOError, OSError):
				logging.exception(_(u'Could not create {1} directory {0}! This '
						u'is mandatory, exiting'), (ST_PATH, directory), dtype)
				LicornEvent('need_terminate').emit(priorities.HIGH)

@events.handler_function
def groups_loaded(*args, **kwargs):
	""" Check system directories permissions. We need to wait for `groups`
		loaded to do it, because fsapi needs ACLs base and users/groups
		resolution to be operational to work.

		.. note:: we give the dirs to group `admins`, for admins to be able
			launch `licornd` on demand (it needs access to
			:file:`/etc/licorn/licorn.conf`).

	"""

	LMC.configuration.check_system_dirs(batch=True, minimal=False)

__all__ =  ('configuration_initialises', 'groups_loaded')
