# -*- coding: utf-8 -*-

from django.template.loader       import render_to_string
from django.utils.translation     import ugettext as _

from licorn.foundations.ltrace    import *
from licorn.foundations.constants import relation, filters
from licorn.interfaces.wmi.libs   import utils

from licorn.core import LMC

from licorn.interfaces.wmi.energy.views import get_days

def task_extinction_added_handler(request, event):

	task = utils.select('tasks', [ event.kwargs['task'].id ])[0]
	
	yield utils.format_RPC_JS('update_recap')
	yield utils.format_RPC_JS('update_calendar')
	yield utils.notify(_(u'Task "{0}" added on the system for machines {1} on {2} at {3}:{4}.').format(
		task.name, task.args, get_days(task.week_day), task.hour.zfill(2), task.minute.zfill(2)))
	
def task_extinction_deleted_handler(request, event):
	
	name = event.kwargs['name']
	
	yield utils.format_RPC_JS('update_recap')
	yield utils.format_RPC_JS('update_calendar')
	yield utils.notify(_(u'Task "{0}" deleted.').format(name))
	