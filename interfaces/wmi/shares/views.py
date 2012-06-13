# -*- coding: utf-8 -*-
"""
Licorn WMI2 system views

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

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

from licorn.core                           import LMC
from licorn.interfaces.wmi.app             import wmi_event_app
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import *

import wmi_data

def return_for_request(request):
	""" This is not a view. """
	if request.is_ajax():
		return HttpResponse('DONE.')

	else:
		return HttpResponseRedirect('/shares')

def toggle_shares(request, state):

	login = request.user.username

	try:
		LMC.users.by_login(login).accepts_shares = state

	except Exception, e:
		logging.exception(_(u'Could not toggle simple shares status to '
										u'{0} for user {1}'), state, login)

		wmi_event_app.enqueue_notification(request, _(u'Could not toggle '
					u'shares status to {0} for user {1} (was: {2}).').format(
						_(unicode(state)), login, e))

	return return_for_request(request)

@login_required
def enable(request, *args, **kwargs):
	return toggle_shares(request,  True)

@login_required
def disable(request, *args, **kwargs):
	return toggle_shares(request, False)

@login_required
def index(request, sort="date", order="asc", **kwargs):
	""" Main backup list (integrates volumes). """

	return render(request, 'shares/index.html', wmi_data.base_data_dict(request))

# ================================================================ public views
# no login required for these, they are voluntarily public, to be able
# to serve shares to anonymous web visitors and make them download/upload them.
def serve(request, login, shname):
	""" Serve a share to web visitors. """

	user = LMC.users.by_login(login)

	if not user.accepts_shares:
		return HttpResponseForbidden(_('This user has no visible shares.'))

	wanted = '%s/%s' % (login, shname)
	_d     = wmi_data.base_data_dict(request)

	for share in user.list_shares():
		if share.name == wanted:
			_d.update({'share': share})
			return render(request, 'shares/serve-share.html',_d)

	return HttpResponseNotFound(_('No Web share at this URI, sorry.'))
def download(request, login, shname, filename):
	return HttpResponseNotFound(_('Not implemented yet, sorry.'))
def upload(request, login, shname, filename):
	return HttpResponseNotFound(_('Not implemented yet, sorry.'))
