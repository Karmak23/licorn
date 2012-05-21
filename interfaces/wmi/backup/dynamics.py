# -*- coding: utf-8 -*-
"""
Licorn WMI2 rdiffbackup dynamic sidebar

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

from django.template.loader     import render_to_string

from licorn.foundations         import pyutils, cache
from licorn.core                import LMC
from licorn.interfaces.wmi.libs import utils

@cache.cached(cache.five_minutes)
def enabled():

	try:
		return LMC.extensions.rdiffbackup.enabled

	except AttributeError:
		return False

def dynamic_sidebar(request):

	if enabled():
		return render_to_string('backup/parts/sidebar.html', {
				'extension' : LMC.extensions.rdiffbackup,
				'request'   : request
			})

	return ''

def dynamic_status(request):

	if enabled():
		return (None,
				render_to_string('backup/parts/status.html', {
						'extension' : LMC.extensions.rdiffbackup,
						'request'   : request
					}),
				None)

