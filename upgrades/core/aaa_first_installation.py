# -*- coding: utf-8 -*-

import os

from licorn.foundations          import logging, settings
from licorn.foundations.events   import LicornEvent
from licorn.foundations.styles   import *
from licorn.foundations.contants import priorities

@events.handler_function
def configuration_loads(*args, **kwargs):
	""" Create the main configuration directory if it doesn't exist, and if we
		have permissions.

		.. note:: this callback will be run *before* core.configuration loads.
	"""

	for (directory, dtype) in (
					(settings.config_dir, _(u'configuration'))
					(settings.cache_dir, _(u'cache'))
					(settings.data_dir, _(u'data'))
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

		for uyp in fsapi.check_dirs_and_contents_perms_and_acls_new([
							fsapi.FsapiObject(name=dtype, path=directory,
								uid=0, gid=0, root_dir_perm=00750,
								dirs_perm=00750, files_perm=00640)
						], batch=True, full_display=True):
			# TODO: we could count modified entries and display a nice
			# information message. Not that usefull where we are, and
			# full_display is already `True`.
			pass

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
