# -*- coding: utf-8 -*-
"""
Licorn WMI2 shares dynamic sidebar

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/

:license: GNU GPL version 2
"""

from django.template.loader     import render_to_string

from licorn.foundations         import pyutils, cache
from licorn.core                import LMC
from licorn.interfaces.wmi.libs import utils

@cache.cached(cache.five_minutes)
def enabled(*args, **kwargs):
	return 'simplesharing' in LMC.extensions.keys() \
							and LMC.extensions.simplesharing.enabled

def dynamic_sidebar(request):

	if enabled():
		return render_to_string('shares/parts/sidebar.html', {
				'extension' : LMC.extensions.simplesharing,
				'request'   : request
			})

	return ''

def dynamic_status(request):
	pass
