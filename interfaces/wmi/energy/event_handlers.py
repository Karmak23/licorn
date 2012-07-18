# -*- coding: utf-8 -*-

from django.utils.translation     import ugettext as _
from licorn.interfaces.wmi.libs   import utils
from licorn.interfaces.wmi.energy.views import get_days

from licorn.core                  import LMC

from licorn.interfaces.wmi.energy.views import ALL_MACHINES
def task_extinction_added_handler(request, event):

	task = utils.select('tasks', [ event.kwargs['task'].id ])[0]

	machines = []
	for m in task.args:
		if m == ALL_MACHINES:
			machines.append(_('All machines'))
		else:
			machines.append(LMC.machines.guess_one(m).hostname)

	
	yield utils.format_RPC_JS('update_recap')
	yield utils.format_RPC_JS('update_calendar')
	yield utils.notify(_(u'Task "{0}" added on the system for machines {1} on {2} at {3}:{4}.').format(
		task.name, ','.join(machines), 
		get_days(task.week_day), task.hour.zfill(2), task.minute.zfill(2)))
	
def task_extinction_deleted_handler(request, event):
	
	name = event.kwargs['name']
	
	yield utils.format_RPC_JS('update_recap')
	yield utils.format_RPC_JS('update_calendar')
	yield utils.notify(_(u'Task "{0}" deleted.').format(name))
	