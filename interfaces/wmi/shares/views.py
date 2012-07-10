# -*- coding: utf-8 -*-
"""
Licorn WMI2 system views

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>, <olive@deep-ocean.net>

:license: GNU GPL version 2
"""

import os, json

from django.contrib.auth.decorators import login_required
from django.http					import HttpResponse, \
											HttpResponseForbidden, \
											HttpResponseNotFound, \
											HttpResponseRedirect, \
											HttpResponseServerError, \
											HttpResponseBadRequest
from django.core.handlers.wsgi import WSGIRequest

from django.shortcuts               import *
from django.utils.translation       import ugettext as _

from licorn.foundations             import logging, settings, fsapi
from licorn.foundations.constants   import priorities
from licorn.foundations.styles      import *
from licorn.foundations.ltrace      import *
from licorn.foundations.ltraces     import *

from licorn.core                           import LMC
from licorn.interfaces.wmi.app             import wmi_event_app
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import *

from django.template.loader                import render_to_string

from forms                                 import AskSharePasswordForm
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


	return HttpResponse(str(share.accepts_uploads))

@login_required
def password(request, shname, newpass, **kwargs):
	""" Change the password of a share. What comes next is decided by the
		password content, which will set the accepts_uploads status of the
		share, which will impact the client side via events. """

	login = request.user.username
	share = LMC.users.by_login(login).find_share(shname)

	try:
		share.password = newpass

		if share.password in ('', None):

			share.accepts_uploads = False
			wmi_event_app.enqueue_notification(request, _(u'Password unset and '
				u'uploads disabled for share <em>{0}</em>.').format(share.name))
		else:
			share.accepts_uploads = True

			wmi_event_app.enqueue_notification(request, _(u'Password set for '
				u'share <em>{0}</em>, uploads are now enabled.').format(share.name))

	except Exception, e:
		logging.exception(_(u'Could not change password of share {0} (user {1})'),
															share.name, login)

		wmi_event_app.enqueue_notification(request, _(u'Could not change '
			u'password of your share {0} (was: {1}).').format(share.name, e))

	return HttpResponse('PASSWORD')


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
	sh = user.find_share(shname)

	if 'can_access_share_{0}'.format(shname) not in request.session:
		request.session['can_access_share_{0}'.format(shname)] = False


	_d = wmi_data.base_data_dict(request)
	_d.update({'share': sh })

	# if it is a POST Resquest, the user is sending the share password
	if request.method == 'POST':

		form = AskSharePasswordForm(request.POST, share=sh)
		if form.is_valid():
			if sh.check_password(request.POST['password']) and \
				not request.session['can_access_share_{0}'.format(shname)]:

				request.session['can_access_share_{0}'.format(shname)] = True

				return HttpResponseRedirect(request.path)
		else:
			# render the form again
			return render(request, 'shares/parts/ask_password.html', {
						'form' : form,
						'shname' : sh.name
					})



	# this is now a GET Request

	# if no share, return a 404
	if not user.accepts_shares:
		return HttpResponseNotFound(_('This user has no visible shares.'))


	for share in user.list_shares():
		if share.name == shname:

			if share.expired:
				return HttpResponseForbidden(_('This share has expired. It '
													'is no more available.'))

			# if the share accept upload the user need a password to access it
			if share.accepts_uploads:
				if not request.session['can_access_share_{0}'.format(shname)]:
					return render(request, 'shares/parts/ask_password.html', {
						'form' : AskSharePasswordForm(share=share),
						'shname' : share.name
					})

			# finally, if everything is OK, render the regular view
			_d.update({
				'uploaded_files' : share.contents()['uploads'],
				'file_size_max' : 10240000,
			})
			return render(request, 'shares/serve-share.html', _d)

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
	""" upload action """
	share = LMC.users.by_login(login).find_share(shname)

	# make sure we can upload in this share
	if share.accepts_uploads:

		# make sure the public user can upload in this share
		if request.session['can_access_share_{0}'.format(shname)]:

			if request.method == 'POST':
				csv_file = request.FILES['file']

				destination = open(os.path.join(share.uploads_directory,
												str(csv_file)), 'wb+')
				t = ''
				for chunk in csv_file.chunks():
					destination.write(chunk)
					t += chunk
				destination.close()

				return HttpResponse(render_to_string(
					'shares/parts/uploaded_files.html', {
						# The contents are cached. to avoid messing the HDD.
						# We need to force expire them because we are sure
						# they changed (Howdy: we just uploaded a file!)
						'uploaded_files' : share.contents(cache_force_expire=True)['uploads']
					}))

		else:
			return HttpResponseForbidden(_(u'Incorrect password!'))

	else:
		return HttpResponse(_(u'Uploads disabled for this share!'))
