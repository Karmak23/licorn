# -*- coding: utf-8 -*-
"""
Licorn WMI2 system views

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

import os

from django.contrib.auth.decorators import login_required
from django.http					import HttpResponse, \
											HttpResponseForbidden, \
											HttpResponseNotFound, \
											HttpResponseRedirect, \
											HttpResponseServerError, \
											HttpResponseBadRequest

from django.shortcuts               import *
from django.utils.translation       import ugettext as _

from licorn.foundations             import settings, fsapi
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
	""" This is not a view, only an helper function.
		No need to @login_required. """

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
def enable(request, **kwargs):
	return toggle_shares(request,  True)

@login_required
def disable(request, **kwargs):
	return toggle_shares(request, False)

@login_required
def accepts_uploads(request, shname, **kwargs):

	login = request.user.username
	share = LMC.users.by_login(login).find_share(shname)


	if request.is_ajax():
		pass
	else:
		return HttpResponse(str(share.accepts_uploads))

@login_required
def password(request, shname, newpass, **kwargs):
	""" Change the password of a share. What comes next is decided by the
		password content, which will set the accepts_uploads status of the
		share, which will impact the client side via events. """

	login = request.user.username

	try:
		LMC.users.by_login(login).find_share(shname).password = newpass

	except Exception, e:
		logging.exception(_(u'Could not change password of share {0} (user {1})'),
															share.name, login)

		wmi_event_app.enqueue_notification(request, _(u'Could not change the '
			u'password of you share {0} (was: {1}).').format(share.name, e))


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
		return HttpResponseNotFound(_('This user has no visible shares.'))

	_d = wmi_data.base_data_dict(request)

	for share in user.list_shares():
		if share.name == shname:

			if share.expired:
				return HttpResponseForbidden(_('This share has expired. It '
													'is no more available.'))

			_d.update({'share': share})
			return render(request, 'shares/serve-share.html',_d)

	return HttpResponseNotFound(_('No Web share at this URI, sorry.'))
def download(request, login, shname, filename):
	"""
		.. todo:: merge this view with system.views.download() (see there).
	"""

	share = LMC.users.by_login(login).find_share(shname)

	# NOTE: we cannot use `LMC.configuration.users.base_path` to test all
	# download file paths, because some (standard) users have their home
	# outside of it. Notably the ones created before Licorn® is installed.
	# Thus, we use the user's homeDirectory, which seems even more secure.
	filename = fsapi.check_file_path(os.path.join(share.path, filename),
										(share.coreobj.homeDirectory, ))

	if filename.startswith(share.uploads_directory):
		return HttpResponseForbidden(_(u'Uploaded files are not downloadable.'))

	if filename:
		try:
			return utils.download_response(filename)

		except:
			logging.exception(_(u'Error while sending file {0}'), (ST_PATH, filename))

			return HttpResponseServerError(_(u'Problem occured while sending '
											u'file. Please try again later.'))

	else:
		return HttpResponseBadRequest(_(u'Bad file specification or path.'))

def upload(request, login, shname, filename):
	return HttpResponseNotFound(_('Not implemented yet, sorry.'))
