# -*- coding: utf-8 -*-
"""
Licorn WMI3 calendar views

:copyright:
	* 2012 Robin Lucbernet <robin@meta-it.fr>

:license: GNU GPL version 2
"""


import time


from django.contrib.auth.decorators import login_required
from django.http					import HttpResponse, \
											HttpResponseForbidden, \
											HttpResponseNotFound, \
											HttpResponseRedirect

from django.shortcuts               import *
from django.utils.translation       import ugettext as _


from licorn.foundations             import settings
from licorn.foundations.constants   import priorities
from licorn.foundations.styles      import *
from licorn.foundations.ltrace      import *
from licorn.foundations.ltraces     import *

from licorn.interfaces.wmi.app             import wmi_event_app
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import *


from licorn.core                    import LMC

from calendarserver.tools.principals   import principalForPrincipalID, action_addProxy, action_removeProxy
from twistedcaldav.config              import config as caldav_config



from licorn.interfaces.wmi.libs   import utils

from licorn.foundations.events    import LicornEvent

def home(request):

	wmi_user = LMC.users.guess_one(request.user.username)

	r, w = get_user_proxies(wmi_user)

	calendars = []

	for principal in r:
		calendars.append({
			'principal_type' : principal.record.recordType,
			'proxy_type'     : "read",
			'name'           : principal.record.shortNames[0],
			'url'            : "http://%s:%s%scalendar/" % (caldav_config.ServerHostName, caldav_config.HTTPPort, principal.calendarHomeURLs()[0]),
			'desc'           : principal.record.fullName
		})
	for principal in w:
		calendars.append({
			'principal_type' : principal.record.recordType,
			'proxy_type'     : "write",
			'name'           : principal.record.shortNames[0],
			'url'            : "http://%s:%s%scalendar/" % (caldav_config.ServerHostName, caldav_config.HTTPPort, principal.calendarHomeURLs()[0]),
			'desc'           : principal.record.fullName
		})

	print "CALENDARSSSSZ", calendars

	return render(request, 'calendar/index.html', { 'calendars' : calendars })

def action(request, uid, action, value, option):

	user           = LMC.users.guess_one(uid)
	user_principal = principalForPrincipalID('users:'+user.login)

	nu       = value
	new_user = LMC.users.guess_one(nu)

	if action == 'add':
		if option == 'read':
			action_addProxy(user_principal, 'read', ('users:'+new_user.login))
		elif option == 'write':
			action_addProxy(user_principal, 'write', ('users:'+new_user.login))

		LicornEvent('calendar_add_proxie', user=user, user_proxy=new_user,
				proxy_type=option).emit()

	elif action == 'del':
		action_removeProxy(user_principal, 'users:'+new_user.login)
		LicornEvent('calendar_del_proxie', user=user, user_proxy=new_user,
			proxy_type=option).emit()

	return HttpResponse('OK')

def get_user_proxies(user):

	principals = []

	user_read_proxies  = []
	user_write_proxies = []

	principal_user = principalForPrincipalID('users:'+user.login)


	user_read_proxies  = [ x for x in utils.my_deferred_blocker(principal_user.proxyFor(False)) ]
	user_write_proxies = [ x for x in utils.my_deferred_blocker(principal_user.proxyFor(True)) ]
	
	return user_read_proxies, user_write_proxies
