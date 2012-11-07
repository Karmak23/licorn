# -*- coding: utf-8 -*-

import sys, json, time

from threading import Thread, Event, current_thread
from Queue     import Queue, Empty

from django.template.loader       import render_to_string
from django.utils.translation     import ugettext as _
from licorn.foundations           import logging, options, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.messaging import MessageProcessor

from licorn.core                import LMC
from licorn.interfaces.wmi.libs import utils


def calendar_add_proxie_handler(request, event):
	try:
		user  = event.kwargs['user']
	except KeyError:
		user  = None
		group = event.kwargs['group']


	proxy = event.kwargs['user_proxy']
	mode = event.kwargs['proxy_type']

	if user is not None:
		yield utils.notify(_("User {0} is now a proxie of {1}'s calendar".format(
			proxy.login,
			user.login)))
	else:
		yield utils.notify(_("User {0} is now a proxie of {1}'s calendar".format(
			proxy.login,
			group.name)))


	# add the new proxy to the correct list
	yield utils.format_RPC_JS('update_instance',
							'readers_proxy' if mode=='read' else 'writers_proxy',
							proxy.login,
							render_to_string('/calendar/parts/table_row.html', {
								'proxy'          : proxy,
								'mode'           : mode,
								'avalaible_list' : False,
								}),
							'setup_calendar_row'
							)
	# remove the proxy from avalaible proxies
	yield utils.format_RPC_JS('remove_instance',
						'avalaible_proxies',
						proxy.login,
						"<tr class='no-data'><td><em>No <strong>avalaible</strong> proxy for the moment</em></td></tr>"
						)


def calendar_del_proxie_handler(request, event):
	try:
		user  = event.kwargs['user']
	except KeyError:
		user  = None
		group = event.kwargs['group']

	proxy = event.kwargs['user_proxy']
	mode = event.kwargs['proxy_type']


	if user is not None:
		yield utils.notify(_("User {0} is no more proxie of {1}'s calendar").format(
													proxy.login, user.login))
	else:
		yield utils.notify(_("User {0} is no more proxie of {1}'s calendar").format(
													proxy.login, group.name))

	yield utils.format_RPC_JS('remove_instance',
								'readers_proxy' if mode=='read' else 'writers_proxy',
								proxy.login,
		"<tr class='no-data'><td><em>{0}</em></td></tr>".format(_('No <strong>{0}</strong> proxy for the moment').format(mode))
								)

	# add the proxy to the avalaible proxies list
	yield utils.format_RPC_JS('update_instance',
							'avalaible_proxies',
							proxy.login,
							render_to_string('/calendar/parts/table_row.html', {
								'proxy'          : proxy,
								'mode'           : mode,
								'avalaible_list' : True,
								}),
							"setup_avalaible_proxies"
							)

