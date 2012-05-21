# -*- coding: utf-8 -*-

def django_setup():
	""" Set the Django environment up, that's to say alter `sys.path` and
		set the `DJANGO_SETTINGS_MODULE` environment variable. """
	import sys, os

	# Django needs the PYTHONPATH to be correctly set to start the app.
	sys.path.insert(0, '/usr/share/licorn')
	sys.path.insert(0, '/usr/share/licorn/wmi')
	os.environ['DJANGO_SETTINGS_MODULE'] = 'wmi.settings'

# Get a local reference to the `wmi_event_app` singleton, to allow a single
# import statement in `daemon/wmi.py`. This is just for comfort.
from app import wmi_event_app
