# -*- coding: utf-8 -*-

import os, time, re
from gettext import gettext as _

from subprocess            import Popen, PIPE

from licorn.foundations    import logging

from licorn.core.configuration  import LicornConfiguration
from licorn.core.users          import UsersController
from licorn.core.groups         import GroupsController
from licorn.core.profiles       import ProfilesController

from licorn.interfaces.wmi import utils as w

configuration = LicornConfiguration()
users = UsersController(configuration)
groups = GroupsController(configuration, users)
profiles = ProfilesController(configuration, groups, users)

def ctxtnav():
	return '''
	<div id="ctxtnav" class="nav">
        <h2>Context Navigation</h2>
		<ul>
		<li><a href="/server/reboot" title="%s" class="lightwindow">
		<div class="ctxt-icon" id="icon-reboot">%s</div></a></li>
		<li><a href="/server/halt" title="%s" class="lightwindow">
		<div class="ctxt-icon" id="icon-shutdown">%s</div></a></li>
		</ul>
        <hr />
	</div>
	''' % (
		_('Restart server.'),
		_('Restart server'),
		_('Shutdown server.'),
		_('Shutdown server'))

def system_load():
	loads = open('/proc/loadavg').read().split(" ")

	allusers  = users
	allusers.Select(filters.STANDARD)
	nbusers = len(allusers.filtered_users)

	cxusers = len(Popen('who', shell = True, stdin = PIPE, stdout = PIPE,
		close_fds = True).stdout.read().split('\n'))
	if cxusers > 1:
		s_users = 's'
	else:
		s_users = ''

	uptime_sec  = int(float(open('/proc/uptime').read().split(" ")[0]))
	uptime_min  = 0
	uptime_hour = 0
	uptime_day  = 0
	uptime_year = 0
	s_year = ''
	s_day  = ''
	s_hour = ''
	s_sec  = ''
	s_min  = ''
	uptime_string = ''
	if uptime_sec > 60:
		uptime_min = uptime_sec / 60
		uptime_sec -= (uptime_min * 60)

		if uptime_min > 60:
			uptime_hour = uptime_min / 60
			uptime_min -= (uptime_hour * 60)
			if uptime_hour > 24:
				uptime_day = uptime_hour / 24
				uptime_hour -= (uptime_day * 24)
				if uptime_day > 365:
					uptime_year = uptime_day / 365
					uptime_day -= (uptime_year * 365)
					if uptime_year > 1:
						s_year = 's'
					uptime_string += _('%d year%s, ') % (uptime_year, s_year)
				if uptime_day > 1:
					s_day = 's'
				uptime_string += _('%d day%s, ') % (uptime_day, s_day)
			if uptime_hour > 1:
				s_hour = 's'
			uptime_string += _('%d hour%s, ') % (uptime_hour, s_hour)
		if uptime_min > 1:
			s_min = 's'
		uptime_string += _('%d min%s, ') % (uptime_min, s_min)
	if uptime_sec > 1:
		s_sec = 's'
	uptime_string += _('%d sec%s') % (uptime_sec, s_sec)

	return _('''Up and running since <strong>%s</strong>.<br /><br />
Users: <strong>%d</strong> total, <strong>%d currently connected</strong>.
<br /><br />
1, 5, and 15 last minutes load average: <strong>%s</strong>, %s, %s''') % (
	uptime_string, nbusers, cxusers, loads[0], loads[1], loads[2])

def system_info():

	cpus  = 0
	model = ''

	for line in open('/proc/cpuinfo'):
		if line[0:9] == 'processor': cpus += 1
		if line[0:10] == 'model name': model = line.split(': ')[1]

	if cpus > 1:
		s = 's'
	else:
		s = ''

	mem = {}

	def compute_mem(line, x):
		#logging.debug(line[0:-1] + " -> " + re.split('\W+', line)[1])

		split = re.split('[\W\(\)]+', line)

		if split[0] == x:
			try:
				return { x: float(split[1]) / 1048576.0 }
			except:
				# skip "Active(xxx)" and other mixed entries from /proc/meminfo.
				return {}
		else:
			return {}

	for line in open('/proc/meminfo'):
		for x in ( 'MemTotal', 'Active', 'Inactive', 'MemFree', 'Buffers',
			'Cached', 'SwapTotal', 'SwapFree' ):
			mem.update(compute_mem(line, x))

	if mem['SwapTotal'] == 0:
		# no swap on this system. Weird, but possible. fixes #40
		swap_message = _("no virtual memory installed.")
	else:
		swap_message = \
			_("Virtual memory: %.2f Gb total, <strong>%.0f%% free<strong>.") % \
				(mem['SwapTotal'], (mem['SwapFree'] * 100.0 / mem['SwapTotal']))

	return  _('''
Processor%s: %d x <strong>%s</strong><br /><br />
Physical memory: <strong>%.2fGb</strong> total,<br />
%.2f Gb for programs, %.2f Gb for cache, %.2f Gb for buffers.<br /><br />
%s''') % (s, cpus, model, mem['MemTotal'], (mem['Inactive'] + mem['Active']),
	mem['Cached'], mem['Buffers'], swap_message)

def index(uri, http_user):

	start = time.time()

	title = _("Server status")
	data  = '''<div id="banner">\n%s\n%s\n%s\n</div><!-- banner -->
		<div id="main">\n%s\n<div id="content">''' % (
			w.backto(), w.metanav(http_user), w.menu(uri), ctxtnav())

	data += '''
	<table>
	<tr>
		<td><h1>%s</h1><br />%s</td>
		<td><h1>%s</h1>%s</td>
	</tr>
	</table>
	''' % (_('System information'), system_info(),
		_('System status'), system_load())

	return (w.HTTP_TYPE_TEXT, w.page(title,
		data + w.page_body_end(w.total_time(start, time.time()))))
