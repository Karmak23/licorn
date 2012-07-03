# -*- coding: utf-8 -*-

import os

from licorn.foundations           import logging, settings, events, fsapi
from licorn.foundations.events    import LicornEvent
from licorn.foundations.styles    import *
from licorn.foundations.constants import priorities
from licorn.core                  import LMC

@events.handler_function
def configuration_loads(*args, **kwargs):
	""" Create the main directories if they don't exist.

		.. note:: this callback will be run *before*
			`core.configuration` loads (this is a handler,
			not a callback). It will only *create* the directories
			and won't check permissions on them, which must be done
			later when `users` and `groups` have loaded.
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

	for directory in (settings.config_dir, settings.cache_dir, settings.data_dir):

		for uyp in fsapi.check_dirs_and_contents_perms_and_acls_new([
							fsapi.FsapiObject(name='sys_dir_check',
								path=directory, uid=0, gid=LMC.groups.by_name(
									settings.defaults.admin_group).gidNumber,
								root_dir_perm=0750,
								dirs_perm=0750, files_perm=0640)
						], batch=True, full_display=True):
			# TODO: we could count modified entries and display a nice
			# information message. Not that usefull where we are, and
			# full_display is already `True`.
			pass

__all__ =  ('configuration_loads', 'groups_loaded')
