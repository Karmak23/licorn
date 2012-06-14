# -*- coding: utf-8 -*-

import os

from licorn.foundations        import logging, events
from licorn.foundations.styles import *

@events.handler_function
def extension_squid_loads(*args, **kwargs):
	""" This callback will be run *before* extension loads. """

	old_file = '/etc/apt/apt.conf.d/00-proxy'
	new_file = '/etc/apt/apt.conf.d/00proxy'

	if os.path.exists(old_file):

		try:
			# NOTE: the new file should not exist. If it is, the old already
			# takes precedence alphabetically, thus the new isn't taken in
			# account; no-one will notice the change.
			os.rename(old_file, new_file)

		except (IOError, OSError):
			logging.exception(_(u'{0}: could not rename {1} to {2}'),
									(ST_NAME, os.path.basename(__file__)),
									(ST_PATH, old_file), (ST_PATH, new_file))

		else:
			logging.notice(_(u'{0}: renamed {1} to {2}.').format(
					stylize(ST_NAME, os.path.basename(__file__)),
					stylize(ST_PATH, old_file), stylize(ST_PATH, new_file)))


__all__ =  ('extension_squid_loads', )
