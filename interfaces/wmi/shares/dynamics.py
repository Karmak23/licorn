# -*- coding: utf-8 -*-
"""
Licorn WMI2 shares dynamic sidebar

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/

:license: GNU GPL version 2
"""

from django.template.loader     import render_to_string

from licorn.foundations         import cache
from licorn.core                import LMC

@cache.cached(cache.five_minutes)
def enabled(*args, **kwargs):
	return 'simplesharing' in LMC.extensions.keys() \
							and LMC.extensions.simplesharing.enabled

@cache.cached(cache.five_minutes)
def my_enabled(*args, **kwargs):
	return 'mylicorn' in LMC.extensions.keys() \
							and LMC.extensions.simplesharing.enabled


def dynamic_sidebar(request):

	if enabled():
		return render_to_string('shares/parts/sidebar.html', {
				'extension' : LMC.extensions.simplesharing,
				'request'   : request
			})

	return ''

def dynamic_status(request):

	pri1 = ''
	pri2 = ''
	pri3 = ''

	if my_enabled():
		m = LMC.extensions.mylicorn

		if not m.connected:
			pri1 = render_to_string('shares/parts/disconnected.html', {
				'extension' : m,
				'request'   : request
			})

		elif not m.reachable:

			pri1 += render_to_string('shares/parts/unreachable.html', {
				'extension'      : m,
				'request'        : request,
			})

	return (pri1 or None, pri2 or None, pri3 or None)
