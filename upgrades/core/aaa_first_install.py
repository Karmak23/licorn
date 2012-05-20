# -*- coding: utf-8 -*-

import os, re, posix1e, tempfile

from licorn.foundations        import logging, settings, process, fsapi, events
from licorn.foundations.styles import *

@events.handler_function
def configuration_loads(*args, **kwargs):
	""" Create the main configuration directory if it doesn't exist, and if we
		have permissions.

		.. note:: this callback will be run *before* core.configuration loads.
	"""

	if not os.path.exists(settings.config_dir):
		try:
			os.makedirs(settings.config_dir)

			logging.info(_(u'Created configuration directory {0}.').format(
							stylize(ST_PATH, settings.config_dir)))

		except (IOError, OSError):
			logging.exception(_(u'Cannot create configuration directory {0}!'),
								(ST_PATH, settings.config_dir))
@events.handler_function
def configuration_loaded(*args, **kwargs):
	""" Check if /home (or surrounding mount point) supports ``acls`` and
		``user_xattr`` or needs to be remounted with these options.

		Alters :path:`/etc/fstab` accordingly.

		.. note:: this callback will be run *after* core.configuration loads.
	"""

	# get LMC.configuration directly
	# config = kwargs.pop('configuration')

	try:
		fd, name = tempfile.mkstemp(dir=settings.defaults.home_base_path)

		try:
			posix1e.ACL(text="u:bin:rw,g:daemon:rw:m::rwx").applyto(fd)

		except:
			mount_point = fsapi.find_mount_point(settings.defaults.home_base_path)
			if fsapi.check_needed_fstab_options(mount_point, ('acl', 'user_xattr', )):
				fsapi.remount(mount_point)

	finally:
		os.close(fd)
		os.unlink(name)

__all__ =  ('configuration_loads', 'configuration_loaded', )
