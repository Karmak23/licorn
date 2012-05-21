# -*- coding: utf-8 -*-

import os, time, json
from urllib import unquote_plus

from django.contrib.auth.decorators     import login_required
from django.shortcuts                   import *
from django.template.loader             import render_to_string

from licorn.foundations           import exceptions, hlstr, logging, settings, pyutils
from licorn.foundations.constants import filters, relation, priorities, host_status
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.workers   import workers

from licorn.core import LMC
from licorn.interfaces.wmi.libs.old_decorators import check_groups

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi.libs import old_utils as w

from licorn.interfaces.wmi.app              import wmi_event_app
from licorn.interfaces.wmi.libs             import  utils, perms_decorators
from licorn.interfaces.wmi.machines         import wmi_data
from licorn.interfaces.wmi.libs.decorators  import *

from operator import itemgetter


class ExtinctionCalendar(ObjectSingleton):
	""" Calendar object keeping trace of extinction rules """
	def __init__(self):
		# our calendar
		self.calendar = []

		self.days=[_('monday'), _('tuesday'), _('wednesday'), _('thursday'), 
			_('friday'), _('satursday'), _('sunday') ]
	def get_recap(self):
		""" return a recap of all extinction rules as an html table """

		html = '<table class="table table-striped" id="extinction_recap_table">'
		
		html += '<thead>'
		html += '<th>{0}</th>'.format(_("Week day"))
		html += '<th>{0}</th>'.format(_("Hour"))
		html += '<th>{0}</th>'.format(_("Machines"))
		html += '</thead>'
		
		sorted_list = sorted(sorted(self.calendar, key=itemgetter('hour')), key=itemgetter('day'))
		for rule in sorted_list:
			
			machines = ''
			for m in rule['who'].split(','):
				m = m.strip()
				if m.lower() == 'all':
					machines  += "<span> ALL MACHINES </span>"
				else:
					machines += "<span class='licorn_machine' id='{0}'></span>".format(m)
					
			html +=	'<tr>'
			html +=	'<td width="20%"> {0} </td>'.format(self.days[int(rule['day'])])
			html +=	'<td width="10%"> {0} </td>'.format(rule['hour'])
			html +=	'<td width="60%"> {0} </td>'.format(machines)

			del_func = "del_rule('{0}','{1}','{2}')".format(rule['who'], rule['hour'],
				rule['day'])

			html +=	('<td width="10%"> '
				'<span onClick="{0}">'
					'<img src="/media/images/16x16/delete.png" '
					'alt="Delete rule" width="16" height="16" /> <span> '
					'</td>'.format(del_func))
			html +=	'</tr>'
		

		html +=	'</table>'

		return html
	def add_rule(self, request, who=None, hour=None, day=None, load=False):
		
		if self.check_new_rule(request, group=who, hour=hour, day=day):
			
			# save the new rule
			self.calendar.append({'who': who, "hour": hour,	"day": day})
			
			if not load:
				# create the Licorn Task
				tname = '_extinction-calendar_{0}-{1}-{2}'.format(who, hour, 
					day)

				if who.lower() == 'all':
					who = 'LMC.machines.select(host_status.ACTIVE)'
				else:
					who = [ str(t).strip() for t in  str(who).split(',') ]

				LMC.tasks.add_task(tname, 'LMC.machines.shutdown', 
					args=[who], hour=str(hour), minute='0',
					week_day=str(day))
				
				# display notifications when not load
				wmi_event_app.queue(request).put(
					utils.notify(_('New rule added for group {0} at {1} ' \
					 'on {2}').format(who, hour, self.days[int(day)])))	
	def get_data_separators(self):
		""" return a List object containing extinction rules """
		data_sep = []
		
		for rule in self.calendar:
			already_added = False
			for r in data_sep:
				if r == rule:
					#same, pass
					pass
				elif r['day'] == rule['day'] and r['hour'] == rule['hour']:
					already_added = True
					r['who'] = '{0},{1}'.format(r['who'], rule['who'])

			if not already_added:
				data_sep.append({ 'day': rule['day'], 'who':rule['who'], 'hour':rule['hour']})
		
		return data_sep
	def get_data_on_off(self):
		""" return List object containing "on" and "off" period for each day """
		data_on_off = [
			{'on': 6, 'off':6}, #monday
			{'on': 6, 'off':6}, #tuesday
			{'on': 6, 'off':6}, #wednesday
			{'on': 6, 'off':6}, #thrusday
			{'on': 6, 'off':6}, #friday
			{'on': 6, 'off':6}, #satursday
			{'on': 6, 'off':6}, #sunday
		]
		for rule in self.calendar:
			if int(rule['hour']) >= int(data_on_off[int(rule['day'])]['off']):
				data_on_off[int(rule['day'])]['off'] = int(rule['hour']) 
				
		return data_on_off 
	def del_rule(self, request, who, hour, day):
		""" delete an extinction rule """
		#delete the task
		LMC.tasks.del_task(LMC.tasks.by_name('_extinction-calendar_{0}-{1}-{2}'
			.format(who.replace(" ", ""), hour, day)).id)

		# delete its reference
		for i, v in enumerate(self.calendar):
			if v['who'] == who and v['hour']==hour and v['day'] == day:
				del self.calendar[i]
	def load_rules(self, request):
		""" load the extinction calendar rules """
		# reinit the calendar
		self.calendar = []

		rules = []
		for task in LMC.tasks:
			if task.name.startswith('_extinction-calendar_'):
				args = task.args
				for i, a in enumerate(args):
					if 'host_status.ACTIVE' in a:
						args[i] = ['all']

				rules.append({'who':', '.join(task.args[0]), 'hour': task.hour, 
					'day': task.week_day})

		for rule in rules:
			self.add_rule(request, who=rule['who'], hour=rule['hour'], 
				day=rule['day'], load=True)			
	def check_new_rule(self, request, group=None, hour=None, day=None, _id=None):
		""" check a rule, return True if the rule is correct, else False """
		for rule in self.calendar:
			if rule != {}:
				
				for w in rule['who'].split(","):
					if str(rule['day']).strip() == str(day).strip() and \
						w.lower().strip() == str(group).lower().strip():

						wmi_event_app.queue(request).put(
							utils.notify(_('Another rule already exists for the '
								'group {0} on day {1}, please delete it first.'
								).format(group,	self.days[int(day)])))
						return False

				
				# if a rule for 'all' is already existing before in the day, 
				# reject it
				if day == rule['day'] and rule['who'].lower()=='all':
					if int(hour) >= int(rule['hour']):
						# "all" rule is before, reject it
						wmi_event_app.queue(request).put(
						utils.notify(_('An extinction rule for group "ALL" '
							'is already defined before on {0}, '
							'delete it first.'.format(self.days[int(day)]))))
						return False

		return True

@login_required
@staff_only
def policies(request, *args, **kwargs):
	""" policies view """
	return render(request, 'energy/policies.html')
# our extinction calendar object
calendar = ExtinctionCalendar()
@staff_only
def add_rule(request, new=None, who=None, hour=None, day=None):
	calendar.add_rule(request, who=who, hour=hour, day=day)
	return HttpResponse('add rule')
@staff_only
def del_rule(request, who, hour, day):
	calendar.del_rule(request, who=who, hour=hour, day=day)
	return HttpResponse('DEL OK.')
@staff_only
def load_calendar(request):
	calendar.load_rules(request)
	return HttpResponse("LOAD CALENDAR")
@staff_only
def get_recap(request):
	""" return an html table containing all extinction rules """
	return HttpResponse(calendar.get_recap())
@staff_only
def get_calendar_data(request):
	return HttpResponse(json.dumps({
		'data_separators' : calendar.get_data_separators(),
		'data_on_off'     : calendar.get_data_on_off(),
	}))
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
	ret.append({'mid': 'all', 'mname': 'ALL'})
	return HttpResponse(json.dumps(ret))