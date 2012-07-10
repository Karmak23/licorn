# -*- coding: utf-8 -*-
"""
	Pre-install steps for the WMI2.

	- `Django`: at least version *1.3* (neded for some `shortcuts` and features).
	- `Jinja2`: at least version *2.6* (needed for sort(attribute='...') argument).
	- `Djinja`: at least version *0.7* (because version 0.6 doesn't display any valuable template debugging output).

:copyright:
	* Olivier Cortès <olive@licorn.org>
	* META IT - Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2
"""
import sys, os, re, shutil, glob

from licorn.foundations           import logging, settings, process
from licorn.foundations           import packaging, fsapi, events, network
from licorn.foundations.styles    import *
from licorn.foundations.constants import distros

from licorn.core import LMC
def move_django_wmi_database():
	""" This function fixes http://dev.licorn.org/ticket/812 """

	# we rename the Django settings to `djsettings` not to
	# clash with `licorn.foundations.settings`.
	import licorn.interfaces.wmi.settings as djsettings

	defdb = djsettings.DATABASES.get('default')

	# Don't try to prepare anything more complicated than SQLite, this is beyond
	# the scope of the current script.
	if 'sqlite3' in defdb.get('ENGINE'):
		dbfile = defdb.get('NAME')

		if dbfile.startswith(settings.cache_dir):

			basename   = os.path.basename(dbfile)
			dirname    = os.path.dirname(dbfile)
			final_dest = os.path.join(settings.data_dir, basename)

			if not os.path.exists(dbfile) or os.path.exists(final_dest):
				logging.die(_(u'Unrecoverable situation while trying to move '
								u'the WMI db to its final and proper location: '
								u'either the old is already moved, or the '
								u'Django settings are not up-to-date; there '
								u'could be another cause. Please fix the '
								u'situation manually'))

			shutil.move(dbfile, final_dest)

			settings_path = djsettings.__file__

			# Settings will certainly be loaded from a compiled python file.
			if not settings_path.endswith('.py'):
				settings_path = settings_path[:-1]

				# be sure the compiled file are not re-used
				# after alteration of the original `.py`.
				for compiled_path in glob.glob('%s?' % settings_path):
					try:
						os.unlink(compiled_path)

					except:
						logging.exception(_(u'Could not delete {0}, continuing'),
											(ST_PATH, compiled_path))

			# Alter the django settings, for the Django
			# engine to find the DB at the new location.
			raw_settings = open(settings_path).read()
			new_raw = re.sub(r'''["']{0}["']'''.format(dbfile),
								r"'{0}'".format(final_dest),
								raw_settings)

			with open(settings_path, 'w') as f:
				f.write(new_raw)

			# The container directory should now be empty.
			# we don't use shutil to avoid accidentaly deleting
			# unwanted things.
			try:
				os.rmdir(dirname)

			except:
				logging.exception(_(u'Could not delete {0}, which should now '
									u'have been empty.'), (ST_PATH, dirname))

			# Be sure anyone else gets the change, else the WMI could
			# fail starting if it looks for the old path.
			reload(djsettings)

			logging.notice(_(u'Successfully moved Django WMI database to '
								u'{0} and updated Django settings.').format(
									stylize(ST_PATH, final_dest)))

@events.handler_function
def wmi_starts(*args, **kwargs):
	""" This function fixes http://dev.licorn.org/ticket/812

		.. note:: this callback will be run *before* the WMI is really started,
			and after the WMI setup (upgrade named 'aaa_*').

		.. versionadded:: 1.4.2
	"""

	move_django_wmi_database()

__all__ =  ('wmi_starts', )
