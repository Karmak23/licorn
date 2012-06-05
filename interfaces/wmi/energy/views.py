# -*- coding: utf-8 -*-

import os, time, json
from urllib import unquote_plus

from django.contrib.auth.decorators     import login_required
from django.shortcuts                   import *
from django.template.loader             import render_to_string

from licorn.foundations           import exceptions, hlstr, logging, settings, \
										pyutils
from licorn.foundations.constants import filters, relation, priorities, \
										host_status
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.workers   import workers

from licorn.core import LMC
from licorn.interfaces.wmi.libs.old_decorators import check_groups

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi.libs.utils       import notify

from licorn.interfaces.wmi.libs             import utils
from licorn.interfaces.wmi.machines         import wmi_data
from licorn.interfaces.wmi.libs.decorators  import *


from licorn.interfaces.wmi.app              import wmi_event_app

from licorn.core.tasks                      import TaskExtinction



days= {
	'0' : _('Monday'), 
	'1' : _('Tuesday'),
	'2' : _('Wednesday'),
	'3' : _('Thursday'),
	'4' : _('Friday'),
	'5' : _('Satursday'),
	'6' : _('Sunday'),
	'*': 'ALL' }



@login_required
@staff_only
def policies(request, *args, **kwargs):
	""" policies view """
	return render(request, 'energy/policies.html', { 
		'data_separators' : get_calendar_data(request, ret=False)})


@staff_only
def add_rule(request, new=None, who=None, hour=None, minute=None, day=None):
	try:
		# add the task
		LMC.tasks.add_task("_extinction-cal_{0}".format(
			LMC.tasks.get_next_unset_id()),	'LMC.machines.shutdown', 
						args=[who], hour=str(hour), minute=str(minute),
						week_day=str(day))

		return HttpResponse('add rule')
	except exceptions.BadArgumentError, e:
		wmi_event_app.queue(request).put(notify((_(u'Error while adding task for machines {0} on {1} at {2} : {3}.').format(
			who, ", ".join([ days[str(d) if d !='*' else d] for d in day.split(',')]), '{0}:{1}'.format(hour, minute), e))))
		return HttpResponse(_('BadArgumentError while adding rule'))
	except:
		logging.exception(_('Unknown error while adding extinction task'))
		return HttpResponse(_('Unknown error while adding rule'))
		
@staff_only
def del_rule(request, tid):
	# del the task
	LMC.tasks.del_task(tid)
	return HttpResponse(_('DEL OK.'))

def generate_machine_html(request, mid):
	try:
		m       = utils.select('machines', [ mid ])[0]
		mtype   = machine_type(m.system_type)
		mstatus = machine_status(m.status)
		mname   = m.name
	except:
		mtype   = ''
		mstatus = machine_status(host_status.OFFLINE)
		mname   = mid
		
		 
	_new  = '<span class="lmachine" id=''>'
	_new += 	'<span class="lmachine_type">{0}</span>'.format(mtype)
	_new +=		'<span>{0}</span>'.format(mname)
	_new += 	'<span class="lmachine_status">{0}</span>'.format(mstatus)
	_new += '</span>'

	return HttpResponse(_new)
def machine_type(_type):
			return ('<img src="/media/images/16x16/'
				'{0}" alt="'
				'{1}" width="16" '
				'height="16" />'.format(
					wmi_data.get_host_type_html(_type)[0],
					wmi_data.get_host_type_html(_type)[1]))
def machine_status(status):
	return ('<img src="/media/images/16x16/{0}"'
		'alt="{1}" width="16" height="16" />'.format(
			wmi_data.get_host_status_html[status][0],
			wmi_data.get_host_status_html[status][1]))
def get_machine_list(request):
	ret = []
	for m in utils.select('machines', default_selection=host_status.ALL):
		ret.append({'mid': str(m.mid), 'mname':str(m.name)})

	# add a 'ALL' shortcut
	ret.append({'mid': 'LMC.machines.select(default_selection=host_status.ALIVE)', 'mname': 'ALL'})
	return HttpResponse(json.dumps(ret))

@staff_only
def get_calendar_data(request, ret=True):
	""" return a List object containing extinction rules regrouped by time """
	data_sep = []
	
	#TODO check minute too !!
	for rule in LMC.tasks:
		if isinstance(rule, TaskExtinction):
			already_added = False
			for r in data_sep:
				if r == rule:
					#same, pass
					continue
				

				elif str(r['day']) in rule.week_day.split(',') and r['hour'] == rule.hour and r['minute'] == rule.minute:
					already_added = True;
					r['who'] = '{0},{1}'.format(r['who'], rule.args)

			if not already_added:
				days = rule.week_day.split(',') if rule.week_day != '*' else range(0,7)
				for d in days:
					data_sep.append({ 'day': d, 'who':rule.args, 
						'hour':rule.hour, 'minute': rule.minute })
	if ret:
		return HttpResponse(json.dumps(data_sep))
	else: 
		return json.dumps(data_sep)
@staff_only
def get_recap(request):
	""" return an html table containing all extinction rules """

	extinction_tasks = [ t for t in LMC.tasks if isinstance(t, 
		TaskExtinction)]

	if len(extinction_tasks) == 0:
		return HttpResponse("No extinction task created yet")

	html = '<table class="table table-striped" id="extinction_recap_table">'
	
	html += '<thead>'
	html += '<th>{0}</th>'.format(_("Week day"))
	html += '<th>{0}</th>'.format(_("Hour"))
	html += '<th>{0}</th>'.format(_("Machines"))
	html += '</thead>'
	
	from operator import attrgetter
	for rule in sorted(extinction_tasks, key=attrgetter('week_day')):
		
		machines = ''
		for m in rule.args:
			m = m.strip()
			if m.lower() == 'all':
				machines  += "<span>{0}</span>".format(_("All machines"))
			else:
				machines += ("<span class='licorn_machine' id='{0}'>"
					"</span>".format(m))


		wd = rule.week_day
		if wd == '*':
			wd='0,1,2,3,4,5,6'

		html +=	'<tr>'
		html +=	'<td width="20%"> {0} </td>'.format(', '.join([ days[d] for d in wd.split(',')]) )
		html +=	'<td width="10%"> {0}:{1} </td>'.format(rule.hour, rule.minute)
		html +=	'<td width="60%"> {0} </td>'.format(machines)

		del_func = "del_rule({0})".format(rule.id)

		html +=	('<td width="10%"> '
			'<span onClick="{0}">'
				'<img src="/media/images/16x16/delete.png" '
				'alt="{1}" width="16" height="16" /> <span> '
				'</td>'.format(del_func, _("Delete rule")))
		html +=	'</tr>'
	

	html +=	'</table>'

	return HttpResponse(html)
