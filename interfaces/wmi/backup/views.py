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

from licorn.interfaces.wmi.app             import wmi_event_app
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import *

# local backup data.
import wmi_data, forms

def return_for_request(request):
	if request.is_ajax():
		return HttpResponse('DONE.')

	else:
		return HttpResponseRedirect('/backup')

@staff_only
def run_dialog(request, volume=None, *args, **kwags):
	assert ltrace_func(TRACE_DJANGO)

	_d = wmi_data.base_data_dict()

	_d.update({ 'volume'          : volume,
				'form'            : forms.ForceBackupRunForm(),
				'last_backup_time': time.time() - _d['extension']._last_backup_time(volume),
				'backup_interval' : settings.backup.interval })

	return render(request, 'backup/rundialog.html', _d)

@staff_only
def run(request, *args, **kwargs):
	""" Run a backup from the WMI (from http://xxx/backup/run). Offer the
		user to force the operation if the last backup is less than the
		configured interval.

		.. note:: this method should probably migrate to a template someday.
	"""

	assert ltrace_func(TRACE_DJANGO)

	if request.method == 'POST':
		form = forms.ForceBackupRunForm(request.POST)

		if form.is_valid():
			try:
				wmi_data.base_data_dict()['extension'].backup(force=form.cleaned_data['force'])

			except Exception, e:
				pyutils.print_exception_if_verbose()
				wmi_event_app.enqueue_notification(_('Could not start backup on '
											'{0} (was: {1})').format(device, e))

	return return_for_request(request)
@staff_only
def enable(request, device, **kwargs):
	""" Eject a device, from the WMI. """

	device = '/dev/' + device
	volume = utils.select('volumes', [ device ])[0]

	try:
		volume.enable()

	except Exception, e:
		pyutils.print_exception_if_verbose()

		wmi_event_app.enqueue_notification(_('Could not enable volume '
									'{0} (was: {1})').format(device, e))

	return return_for_request(request)
@staff_only
def eject(request, device, **kwargs):
	""" Eject a device, from the WMI. """

	device = '/dev/' + device
	volume = utils.select('volumes', [ device ])[0]

	print dir(volume)

	try:
		volume.unmount()

	except Exception, e:
		logging.exception(_(u'Unhandled exception while unmounting volume {0}'),
							(ST_PATH, device))

		wmi_event_app.enqueue_notification(request, _('Could not eject volume '
										'{0} (was: {1})').format(device, e))

	return return_for_request(request)
@staff_only
def rescan(request, **kwargs):
	""" Rescan volumes, mount everything that needs to, and reload page. """

	# old, simplest implementation but expects the WMI to be *IN* the same
	# process as the daemon, which is not the case anymore.
	#LMC.extensions.volumes.rescan_volumes()
	#LMC.extensions.volumes.mount_volumes()

	# new (intermediate implementation); less beautiful, but fully remote!
	#LMC.rwi.generic_resolved_call('LMC.extensions.volumes', 'rescan_volumes')
	#LMC.rwi.generic_resolved_call('LMC.extensions.volumes', 'mount_volumes')

	# best version: get a proxy for remote extension, and call methods
	# the pythonic way.
	volext = utils.select('extensions', [ 'volumes' ])[0]
	volext.rescan_volumes()
	volext.mount_volumes()

	wmi_event_app.enqueue_notification(request, _('Volumes rescanned.'), 3000)

	return return_for_request(request)
@login_required
def index(request, sort="date", order="asc", **kwargs):
	""" Main backup list (integrates volumes). """

	return render(request, 'backup/index.html', wmi_data.base_data_dict())

