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
											HttpResponseRedirect, \
											HttpResponseServerError, \
											HttpResponseBadRequest
from django.shortcuts               import *
from django.template.loader         import render_to_string
from django.utils.translation       import ugettext_lazy as _

from licorn.foundations                    import logging, options, fsapi
from licorn.foundations.styles             import *
from licorn.foundations.ltrace             import *
from licorn.foundations.ltraces            import *
from licorn.foundations.constants          import priorities, relation, verbose
from licorn.core                           import LMC
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

def error_handler(request, *args, **kwargs):

	# we take the lock to be sure nobody will try to output something
	# while we modify the global verbose level. We can take it without
	# worrying because it's a `RLock` and the logging call will be
	# done in the same thread that we already are in.
	with logging.output_lock:
		old_level = options.verbose
		options.SetVerbose(verbose.PROGRESS)
		logging.exception(_('Unhandled exception in Django WMI code for request {0}'), str(request))
		options.SetVerbose(old_level)

	return render(request, '500.html')

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
def main(request, *args, **kwargs):

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

		lists = [
					{
						'title'  : _('Responsibilities'),
						'name'   : relation.RESPONSIBLE,
						'kind'   : _('responsible'),
						'groups' : resps
					},
					{
						'title'  : _('Memberships'),
						'name'   : relation.MEMBER,
						'kind'   : _('member'),
						'groups' : stdgroups
					},
					{
						'title'  : _('Invitations'),
						'name'   : relation.GUEST,
						'kind'   : _('guest'),
						'groups' : guests
					},
					{
						'title'  : _('Privileges'),
						'name'   : relation.PRIVILEGE,
						'kind'   : _('privileged member'),
						'groups' : privs
					},
					{
						'title'  : _('Other system groups'),
						'name'   : relation.SYSMEMBER,
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
				'groups_lists'          : lists
		})

	return render(request, 'system/index.html', _dict)

@staff_only
def status(request, *args, **kwargs):
	""" TODO: daemon status. """

	# request, session,
	return render_to_response('system/status.html')

@login_required
def download(request, filename, *args, **kwargs):
	""" download a file, can only be in '/tmp' else download is refused
	from : http://djangosnippets.org/snippets/365/

		.. todo:: merge this view with shares.views.download(), if url
			merging is possible.
	"""

	# check_file_path() will return a cleaned path, or `None` if insecure.
	filename = fsapi.check_file_path(filename, ('/tmp/', ))

	if filename:
		try:
			return utils.download_response(filename)

		except:
			logging.exception(_(u'Error while sending file {0}'), (ST_PATH, filename))

			return HttpResponseServerError(_(u'Problem occured while sending '
											u'file. Please try again later.'))

	else:
		return HttpResponseBadRequest(_(u'Bad file specification or path.'))

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
@login_required
def view_groups(request):
	""" return the html table groups for the currently logged in user """
	user = LMC.users.by_login(str(request.user))

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

	lists = [
				{
					'title'  : _('Responsibilities'),
					'name'   : relation.RESPONSIBLE,
					'kind'   : _('responsible'),
					'groups' : resps
				},
				{
					'title'  : _('Memberships'),
					'name'   : relation.MEMBER,
					'kind'   : _('member'),
					'groups' : stdgroups
				},
				{
					'title'  : _('Invitations'),
					'name'   : relation.GUEST,
					'kind'   : _('guest'),
					'groups' : guests
				},
				{
					'title'  : _('Privileges'),
					'name'   : relation.PRIVILEGE,
					'kind'   : _('privileged member'),
					'groups' : privs
				},
				{
					'title'  : _('Other system groups'),
					'name'   : relation.SYSMEMBER,
					'kind'   : _('system member'),
					'groups' : sysgroups
				},

		]

	return render_to_string('/users/view_groups_template.html', {
		'groups_lists' : lists
	})
