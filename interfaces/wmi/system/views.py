# -*- coding: utf-8 -*-
"""
Licorn WMI2 system views

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

import sys, os, time, re, itertools, urlparse

from django.conf                    import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth			import REDIRECT_FIELD_NAME, \
											login as django_login, \
											logout as django_logout
from django.http					import HttpResponse, \
											HttpResponseForbidden, \
											HttpResponseNotFound, \
											HttpResponseRedirect
from django.shortcuts               import *
from django.utils.translation       import ugettext_lazy as _

from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.constants import priorities
from licorn.core                  import LMC

# local wmi.system.collectors, used in index()
from licorn.interfaces.wmi                 import collectors
from licorn.interfaces.wmi.app             import wmi_event_app
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import *

from users.forms import UserForm

def __gather_wmi_messages(request):
	""" .. todo:: this method should be wiped away, and its content
		implemented with :class:`LicornEvent`. """
	status_messages = {
		priorities.LOW: '',
		priorities.NORMAL: '',
		priorities.HIGH: ''
		}

	info_messages = {
		priorities.LOW: '',
		priorities.NORMAL: '',
		priorities.HIGH: ''
		}

	for obj in itertools.chain(LMC.itervalues(), LMC.extensions.itervalues()):

		if hasattr(obj, '_wmi_status'):
			for msgtuple in getattr(obj, '_wmi_status')():
				status_messages[msgtuple[0]] += msgtuple[1] + '\n'

		if hasattr(obj, '_wmi_info'):
			for msgtuple in getattr(obj, '_wmi_info')():
				info_messages[msgtuple[0]] += msgtuple[1] + '\n'

	return status_messages, info_messages


def __cpu_infos():
	cpus = 0
	model = _(u'unknown')

	for line in open('/proc/cpuinfo'):
		if line[0:9] == 'processor': cpus += 1
		if line[0:10] == 'model name': model = line.split(': ')[1]

	return cpus, model
def __uptime():
	return float(open('/proc/uptime').read().split(" ")[0])

@superuser_only
def configuration(request, *args, **kwargs):
	pass

@superuser_only
def daemon_status(request, *args, **kwargs):

	_dict = {
			'main_content_template': 'system/daemon_status_main.html',
			'sub_content_template' : 'system/daemon_status_sub.html',
			'daemon_status'        : collectors.daemon_status(),
			'uptime'               : __uptime(),
		}

	if request.is_ajax():
		return render(request, 'content.html', _dict)

	else:
		return render(request, 'system/index.html', _dict)

@login_required
def index(request, *args, **kwargs):

	_dict = {
		'uptime'  : __uptime(),
	}

	if request.user.is_staff:
		cpus, cpu_model                = __cpu_infos()
		status_messages, info_messages = __gather_wmi_messages(request)

		_dict.update({
				'status_messages'       : status_messages,
				'main_content_template' : 'system/index_main.html',
				'cpus'                  : cpus,
				'cpu_model'             : cpu_model,
				'info_messages'         : info_messages,
				'ram'                   : collectors.ramswap(),
				'avg_loads'             : collectors.avg_loads(),
				'connected'             : collectors.connected_users(),
				'sub_content_template'  : 'system/index_sub.html',
		})

	else:
		try:
			user = utils.select_one('users', [ request.user.username ])

		except IndexError:
			user = None

		edit_mod = True
		title    = _('Edit user {0}').format(user.login)
		action   = 'edit'
		user_id  = user.uidNumber

		f = UserForm(edit_mod, user)

		resps     = []
		guests    = []
		stdgroups = []
		privs     = []
		sysgroups = []

		for group in user.groups:
			if group.is_responsible:
				resps.append(group.standard_group)

			elif group.is_guest:
				guests.append(group.standard_group)

			elif group.is_standard:
				stdgroups.append(group)

			elif group.is_privilege:
				privs.append(group)

			else:
				sysgroups.append(group)

		groups_lists = [
				{
					'title'  : _('Responsibilities'),
					'kind'   : _('responsible'),
					'groups' : resps
				},
				{
					'title'  : _('Memberships'),
					'kind'   : _('member'),
					'groups' : stdgroups
				},
				{
					'title'  : _('Invitations'),
					'kind'   : _('guest'),
					'groups' : guests
				},
				{
					'title'  : _('Privileges'),
					'kind'   : _('privileged member'),
					'groups' : privs
				},
				{
					'title'  : _('Other system groups'),
					'kind'   : _('system member'),
					'groups' : sysgroups
				},

		]

		_dict.update({
				'main_content_template' : 'system/index_main_nostaff.html',
				'sub_content_template'  : 'system/index_sub_nostaff.html',
				'user_uid'              : user_id,
				'action'                : action,
				'edit_mod'              : edit_mod,
				'title'                 : title,
				'form'                  : f,
				'groups_lists'          : groups_lists
		})

	return render(request, 'system/index.html', _dict)

@staff_only
def status(request, *args, **kwargs):
	""" TODO: daemon status. """

	# request, session,
	return render_to_response('system/status.html')

@login_required
def test(request):

	if not settings.DEBUG:
		return HttpResponseForbidden('TESTS DISABLED.')

	# notice the utils.select() instead of LMC.rwi.select().
	# arguments are *exactly* the same (they are mapped via *a and **kw).
	user = LMC.select('users', args=[ 1001 ])[0]

	# store it locally to 'see' the change. attributes are read remotely.
	g = user.gecos

	# this should be done remotelly, and will imply a notification feedback from licornd.
	user.gecos = 'test'

	users = LMC.select('users', default_selection = filters.STANDARD)

	# a small HttpResponse to "see" the change.
	response = ''
	for user in users:
		g = user.gecos
		response += 'gecos = %s -> %s <br /> profile: %s <br />groups: %s' % (
			g, user.gecos, user.profile,
			', '.join(x.name for x in user.groups))

	return HttpResponse(response)

@staff_only
def main(request, sort="name", order="asc", select=None, **kwargs):

	extensions = [e for e in LMC.extensions ]

	system_users_list = LMC.users.select(filters.SYSTEM)

	return render(request, 'users/index.html', {
			'users_list'        : users_list,
			'system_users_list' : system_users_list,
			'is_super_user'     : request.user.is_superuser,
		})

@staff_only
def shutdown(request, reboot=False):
	LMC.system.shutdown(reboot=reboot)

	return HttpResponse('Shutdown OK (reboot=%s)!' % reboot)
@staff_only
def shutdown_all(request, reboot=False):

	wmi_event_app.notify_not_implemented('shutdown_all')

	# TODO:
	#wmi_event_app.enqueue_operation(request, 'LMC.system.shutdown_all', reboot=reboot)

	return HttpResponse('Shutdown (ALL) OK (reboot=%s)!' % reboot)
@staff_only
def shutdown_cancel(request):

	LMC.system.shutdown_cancel()

	return HttpResponse('Shutdown CANCEL!')
@staff_only
def shutdown_all_cancel(request):

	wmi_event_app.notify_not_implemented('shutdown_all_cancel')

	# TODO:
	#wmi_event_app.enqueue_operation(request, 'LMC.system.shutdown_all_cancel')

	return HttpResponse('Shutdown CANCEL!')
