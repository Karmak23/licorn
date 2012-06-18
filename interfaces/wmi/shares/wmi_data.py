# -*- coding: utf-8 -*-
"""
:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/

:license: GNU GPL version 2
"""

from licorn.core import LMC

def base_data_dict(request):
	""" data common to many views and event handlers, thus centralized here. """

	d = {
			'extension'      : LMC.extensions.simplesharing,
			'myext'          : LMC.extensions.mylicorn,
		}

	try:
		d.update({
			'user' : LMC.users.by_login(request.user.username)
			})
	except KeyError:
		# This fails when the shares are viewed by an anonymous external
		# visitor. This is not a problem, because the public views don't
		# rely on the user: the login is passed as argument of
		# `request.path` and the user is looked up from there.
		pass

	return d
