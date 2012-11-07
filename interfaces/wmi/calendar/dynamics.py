# -*- coding: utf-8 -*-
"""
Licorn WMI3 calendar dynamics

:copyright:
	* 2012 Robin Lucbernet <robin@meta-it.fr>

:license: GNU GPL version 2
"""

from django.template.loader     import render_to_string

from licorn.foundations         import pyutils, cache
from licorn.core                import LMC
from licorn.interfaces.wmi.libs import utils

from licorn.foundations.constants import filters
from licorn.interfaces.wmi.groups.views import generate_tab_content

from calendarserver.tools.principals   import principalForPrincipalID, getProxies




@cache.cached(cache.five_minutes)
def enabled():

	try:
		return LMC.extensions.caldavd.enabled

	except AttributeError:
		return False

def dynamic_sidebar(request):
	if enabled():
		return render_to_string('calendar/parts/sidebar.html', {})

	return ''


def get_users_principals(do_not_include):

	print ">>get_users_principals",  do_not_include

	up = []

	for u in LMC.users.select(filters.STANDARD):
		if u.login not in do_not_include:
			p = principalForPrincipalID('users:'+u.login)
			if p:
				up.append(p)

	return up

def dynamic_users_tab(users, mode):

	if mode not in ('new', "massiv"):

		user = users[0]
		
		from licorn.interfaces.wmi.users.views import generate_tab_content
		from django.template.loader         import render_to_string



		#( tid, sort, title, content )
		#self.setup_calendarserver_environement()
		

		# get user principal 
		principal_user = principalForPrincipalID('users:'+user.login)
		# get its proxies
		proxies = utils.my_deferred_blocker(getProxies(principal_user))

		read_proxies = [ principalForPrincipalID(p) for p in proxies[0] ]
		write_proxies = [ principalForPrincipalID(p) for p in proxies[1] ]

		do_not_include = [ user.login ]
		for t in [ str(p).split(')')[1] for p in read_proxies ]:
			do_not_include.append(t)

		for t in [ str(p).split(')')[1] for p in write_proxies ]:
			do_not_include.append(t)
		
		content = render_to_string('/calendar/parts/user_calendar_content.html', {
				'user' : user,
				'read_proxies' : read_proxies,
				'write_proxies' : write_proxies,
				'users_principals' : get_users_principals(do_not_include=do_not_include),
				'base_url_action': "/calendar/users/"+str(user.uidNumber),
				})
		

		return [{ 'id' : 'calendar', 'sort':10, 'title': 'Calendar options',
			'content': generate_tab_content('calendar', content)}]

	else:
		return []


def dynamic_groups_tab(groups, mode):

	if mode not in ('new', "massiv"):

		group = groups[0]
	
		# get group principal 
		principal_group = principalForPrincipalID('resources:resource_'+group.name)
		# get its proxies
		proxies = utils.my_deferred_blocker(getProxies(principal_group))

		read_proxies = [ principalForPrincipalID(p) for p in proxies[0] ]
		write_proxies = [ principalForPrincipalID(p) for p in proxies[1] ]

		do_not_include = [ ]
		for t in [ str(p).split(')')[1] for p in read_proxies ]:
			do_not_include.append(t)

		for t in [ str(p).split(')')[1] for p in write_proxies ]:
			do_not_include.append(t)
		
		content = render_to_string('/calendar/parts/group_calendar_content.html', {
				'group' : group,
				'read_proxies' : read_proxies,
				'write_proxies' : write_proxies,
				'users_principals' : get_users_principals(do_not_include=do_not_include),
				'base_url_action': "/calendar/groups/"+str(group.gidNumber),
				})
		

		return [{ 'id' : 'calendar', 'sort':10, 'title': 'Calendar options',
			'content': generate_tab_content('calendar', content)}]

	else:
		return []
