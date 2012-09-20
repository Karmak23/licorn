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
from licorn.foundations.workers     import workers
from licorn.foundations.styles      import *
from licorn.foundations.ltrace      import *
from licorn.foundations.ltraces     import *

from licorn.core                           import LMC
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
	user  = LMC.users.by_login(login)

	try:
		user.accepts_shares = state

		if state:
			# Be sure all shares have a short URL, or will have soon.
			workers.network_enqueue(priorities.LOW, user.check_shares(batch=True))

	except Exception, e:
		logging.exception(_(u'Could not toggle simple shares status to '
										u'{0} for user {1}'), state, login)

		utils.notification(request, _(u'Could not toggle '
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
def check_share(request, shname, **kwargs):

	login = request.user.username
	share = LMC.users.by_login(login).find_share(shname)

	share.check()

	if request.is_ajax():
		utils.notification(request, _(u'Share <em>{0}</em> is beiing checked '
			u'in the background. Please reload this page in a few seconds.'))

	return HttpResponse('DONE')

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

			utils.notification(request, _(u'Password unset and uploads '
						u'disabled for share <em>{0}</em>.').format(share.name))
		else:
			share.accepts_uploads = True

			utils.notification(request, _(u'Password set for share '
				u'<em>{0}</em>, uploads are now enabled.').format(share.name))

	except Exception, e:
		logging.exception(_(u'Could not change password of share {0} (user {1})'),
															share.name, login)

		utils.notification(request, _(u'Could not change password of your '
							u'share {0} (was: {1}).').format(share.name, e))

	return HttpResponse('PASSWORD')

@login_required
def index(request, sort="date", order="asc", **kwargs):
	""" Main backup list (integrates volumes). """

	_data = wmi_data.base_data_dict(request)

	# Be sure all shares have a short URL, or will have soon.
	workers.network_enqueue(priorities.LOW, _data['user'].check_shares(batch=True))

	return render(request, 'shares/index.html', _data)

# ================================================================ public views
# no login required for these, they are voluntarily public, to be able
# to serve shares to anonymous web visitors and make them download/upload them.
def serve(request, login, shname):
	""" Serve a share to web visitors. """
	try:
		user  = LMC.users.by_login(login)

	except KeyError:
		return HttpResponseNotFound(_('No Web share for this user, sorry.'))

	share = user.find_share(shname)
	if share is None:
		return HttpResponseNotFound(_('No Web share at this URI, sorry.'))

	session_key = 'can_access_share_{0}'.format(share.shid)

	if session_key not in request.session:
		request.session[session_key] = False

	_d = wmi_data.base_data_dict(request)
	_d.update({ 'share': share })

	# if it is a POST Resquest, the user is sending the share password
	if request.method == 'POST':
		form = AskSharePasswordForm(request.POST, share=share)

		if form.is_valid():
			if share.check_password(request.POST['password']) and \
				not request.session[session_key]:

				request.session[session_key] = True

				return HttpResponseRedirect(request.path)
		else:
			# render the form again
			return render(request, 'shares/ask_password.html', {
						'form'   : form,
						'shname' : shname
					})

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
				if not request.session[session_key]:
					return render(request, 'shares/ask_password.html', {
						'form'   : AskSharePasswordForm(share=share),
						'shname' : shname,
					})

			# finally, if everything is OK, render the regular view
			_d.update({
				'uploaded_files' : share.contents()['uploads'],
				'file_size_max'  : settings.get(
					'extensions.simplesharing.max_upload_size',
						wmi_data.DEFAULT_MAX_UPLOAD_SIZE),
			})
			return render(request, 'shares/serve-share.html', _d)

def download(request, login, shname, filename):
	"""
		.. todo:: merge this view with system.views.download() (see there).
	"""

	share = LMC.users.by_login(login).find_share(shname)

	session_key = 'can_access_share_{0}'.format(share.shid)

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
			# TODO: protect downloads with the share password if it has one ?

			return utils.download_response(filename)

		except:
			logging.exception(_(u'Error while sending file {0}'), (ST_PATH, filename))

			return HttpResponseServerError(_(u'Problem occured while sending '
											u'file. Please try again later.'))

	else:
		return HttpResponseBadRequest(_(u'Bad file specification or path.'))
def upload(request, login, shname):
	""" upload action """
	share = LMC.users.by_login(login).find_share(shname)

	session_key = 'can_access_share_{0}'.format(share.shid)

	# make sure we can upload in this share
	if share.accepts_uploads:

		# make sure the public user can upload in this share
		if request.session[session_key]:

			if request.method == 'POST':
				uploaded_file = request.FILES['file']

				destination = open(os.path.join(share.uploads_directory,
												str(uploaded_file)), 'wb+')
				t = ''
				for chunk in uploaded_file.chunks():
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
