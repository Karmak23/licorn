# -*- coding: utf-8 -*-
"""
Licorn® WMI - energy views

:copyright:
	* 2012 Robin Lucbernet <robinlucbernet@gmail.com>
:license: GNU GPL version 2
"""

import json, types

from django.contrib.auth.decorators import login_required
from django.shortcuts               import *

from licorn.foundations             import exceptions, hlstr, logging, \
										settings, pyutils
from licorn.foundations.constants import filters, relation, priorities,\
										host_status
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core import LMC

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi.libs.utils       import notify

from licorn.interfaces.wmi.libs             import utils
from licorn.interfaces.wmi.machines         import wmi_data
from licorn.interfaces.wmi.libs.decorators  import *
from licorn.interfaces.wmi.app              import wmi_event_app

from licorn.core.tasks                      import TaskExtinction

from django.template.loader                 import render_to_string

from operator import attrgetter

days= {
	'0' : _('Monday'), 
	'1' : _('Tuesday'),
	'2' : _('Wednesday'),
	'3' : _('Thursday'),
	'4' : _('Friday'),
	'5' : _('Satursday'),
	'6' : _('Sunday'),
	'*' : _('ALL'),}

ALL_MACHINES = "LMC.machines.select(default_selection=host_status.ACTIVE)"

def get_days(wd):
	""" return an human readable string representings days """
	
	tab = wd.split(',')

	# if the rule has to be apply on 7 days, it is ALL days
	if type(tab) == types.ListType and len(tab) == 7:
		return _('ALL')
	
	# if > 4 days, represent "ALL except x,y"
	if type(tab) == types.ListType and len(tab) > 4:	
		# who is not present ?
		not_present = []
		for k, v in days.iteritems():
			if k not in tab:
				not_present.append(k)

		return "ALL except {0}".format(', '.join(
						[ days[d] for d in not_present if d != '*' ]))
	
	else:
		dayz = []
		for d in wd.split(','):
			dayz.append(days[str(d)])
	
		return ', '.join(dayz)


@login_required
@staff_only
def policies(request, *args, **kwargs):
	""" policies view """
	return render(request, 'energy/policies.html', { 
		'data_separators' : get_calendar_data(request, ret=False)})
		
def get_next_unset_id():
	# get the next unsed id in order to generate the task name
	max_num = 0
	for task in [ t for t in LMC.tasks if isinstance(t, TaskExtinction)]:
		try:
			num=int(task.name[16:])
			if num > max_num:
				max_num = num
		except ValueError,e :
			# can be raised if an TaskExtinction has not the name we expect
			pass
	return int(max_num) + 1
	
@staff_only
def add_rule(request, new=None, who=None, hour=None, minute=None, 
	day=None):
	"""  add an extinction task in the TaskController """
	try:
		

		name = "_extinction-cal_" + str(get_next_unset_id())

		# we have to translate each machine into its main IP address
		# (accessible from the server)
		machines_to_shutdown = []
		for m in who.split(','):
			if m.lower() == 'all':
				machines_to_shutdown.append(ALL_MACHINES)
			else:
				try:
					mach = LMC.machines.guess_one(
											LMC.machines.word_match(m))
				except KeyError:
					wmi_event_app.queue(request).put(notify((
						_(u'Error while adding task for machines {0} on'
							u' {1} at {2} : One machine cannot be '
							u'resolved : {3}.').format(
								who,
								", ".join(
									[ days[str(d) if d !='*' else d] \
										for d in day.split(',')]), 
								'{0}:{1}'.format(hour, minute), e))))

				if mach.master_machine is not None:
					machines_to_shutdown.append(mach.master_machine.mid)
				else:
					machines_to_shutdown.append(mach.mid)

		# guess days too:
		_day = []
		for d in day.split(','):
			try:
				t = int(d)
			except:
				for k,v in days.iteritems():
					if v == d:
						t = k
			
			_day.append(t)

		# add the task
		LMC.tasks.add_task(name, 'LMC.machines.shutdown', 
						args=machines_to_shutdown, hour=str(hour), 
						minute=str(minute),
						week_day=','.join([ str(d) for d in _day]))
		
		return HttpResponse('add rule')
	except exceptions.BadArgumentError, e:
		wmi_event_app.queue(request).put(notify((
			_(u'Error while adding task for machines {0} on {1} at {2} '
				u': {3}.').format(
					who, 
					", ".join([ days[str(d)] \
						for d in day.split(',') if d != '']), 
					'{0}:{1}'.format(hour, minute), e))))
		return HttpResponse(_('BadArgumentError while adding rule'))		
	except:
		logging.exception(_('Unknown error while adding extinction task'))
		return HttpResponse(_('Unknown error while adding rule'))
		
@staff_only
def del_rule(request, tid):
	# del the task
	LMC.tasks.del_task(tid)
	return HttpResponse(_('DEL OK.'))

def generate_machine_html(mid, minimum=False):
	if mid == ALL_MACHINES:
		machine = { 'mtype': '', 'mname': "ALL", 'mstatus': '' }
	else:
		try:
			m       = utils.select('machines', [ mid ])[0]
			machine = { 'mtype': wmi_data.get_host_type_html(m.system_type) \
														if not minimum else '', 
						'mname': m.name, 
						'mstatus': wmi_data.get_host_status_html[int(m.status)]\
														if not minimum else ''
					}
		except:
			machine = { 
				'mtype': '',
				'mname': mid, 
				'mstatus': wmi_data.get_host_status_html[host_status.OFFLINE] \
														if not minimum else '' }
			
	return render_to_string('/energy/machine.html', { 
		'machine'  : machine,
		})
	


def get_machine_list(request):
	""" return a list of all ACTIVE machines. 
		To be displayed in the machine autocompleter """
	ret = []
	for m in utils.select('machines', default_selection=host_status.ACTIVE):
		ret.append({'mid': str(m.mid), 'mname':str(m.name)})

	# add a 'ALL' shortcut
	ret.append({'mid': ALL_MACHINES, 'mname': 'ALL'})
	return HttpResponse(json.dumps(ret))

@staff_only
def get_calendar_data(request, ret=True):
	""" return a List object containing extinction rules regrouped by time. """
	data_sep = []
	
	#TODO check minute too !!
	for rule in LMC.tasks:
		if isinstance(rule, TaskExtinction):
			already_added = False
			for r in data_sep:
				if r == rule:
					#same, pass
					continue
				

				elif str(r['day']) in rule.week_day.split(',') and \
						r['hour'] == rule.hour and r['minute'] == rule.minute:
					
					already_added = True;
					r['who'] = '{0},{1}'.format(r['who'], rule.args)

			if not already_added:
				days = rule.week_day.split(',') if rule.week_day != '*' \
																else range(0,7)
				for d in days:
					data_sep.append({ 'day': d, 
						'who':rule.args, 
						'who_html': ', '.join(
							[ generate_machine_html(m, minimum=True) \
														 for m in rule.args]),
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

	

	return HttpResponse(render_to_string('energy/recap_policies.html', {
				'tasks'    : sorted(extinction_tasks, key=attrgetter('week_day')),
				'get_days' : get_days,
				'generate_machine_html' : generate_machine_html,
			}))

