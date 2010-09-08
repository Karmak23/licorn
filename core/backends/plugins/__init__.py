# -*- coding: utf-8 -*-
"""
Licorn Core backends plugins.
These plugins are totally optionnal: they will be tryed (initialize()), and if
not usable, no error will be produced. It's up to the plugin to determine if
it can be used on a given system.

An academic example can be found in the dnsmasq_plugin.s

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os
from licorn.foundations.ltrace import ltrace
plugins = []

ltrace('plugins', '> __init__()')

for entry in os.listdir(__path__[0]):
	if entry == '__init__.py':
		continue
	if entry[-10:] == '_plugin.py':
		modname = entry[:-3]		# minus '.py'
		plugin_name = entry[:-10]	# minus '_plugin.py'
		try :
			exec('from licorn.core.backends.plugins.%s import %s_controller as %s' % (
				modname, plugin_name, plugin_name))
			exec('plugins.append(%s)' % plugin_name)
			ltrace('plugins', 'imported %s.' % plugin_name)

		except ImportError:
			ltrace('plugins', 'could not import %s.' % plugin_name)

ltrace('plugins', '< __init__()')
