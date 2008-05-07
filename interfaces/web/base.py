# -*- coding: utf-8 -*-

import os, time, re

from licorn.core           import users
from licorn.interfaces.web import utils as w

def __status_actions() :
	return '''
<div id="actions">
	<div class="action">
		<a href="/server/reboot" title="%s"><img src="/images/32x32/reboot.png" alt="%s" /><br />%s</a>
	</div>
	<div class="action">
		<a href="/server/halt" title="%s"><img src="/images/32x32/shutdown.png" alt="%s" /><br />%s</a>
	</div>
</div>
	''' % (
		_('Restart server.'),
		_('Restart server.'),
		_('Restart server'),
		_('Shutdown server.'),
		_('Shutdown server.'),
		_('Shutdown server'))

def system_load() :
	loads = open('/proc/loadavg').read().split(" ")
	
	allusers  = users
	allusers.Select(allusers.FILTER_STANDARD)
	nbusers = len(allusers.filtered_users)

	cxusers = len(os.popen2('who')[1].read().split('\n'))
	if cxusers > 1 :
		s_users = 's'
	else :
		s_users = ''

	uptime_sec  = int(float(open('/proc/uptime').read().split(" ")[0]))
	uptime_min  = 0
	uptime_hour = 0
	uptime_day  = 0
	s_day  = ''
	s_hour = ''
	s_sec  = ''
	s_min  = ''
	uptime_string = ''
	if uptime_sec > 60 :
		uptime_min = uptime_sec / 60
		uptime_sec -= (uptime_min * 60)
		if uptime_sec > 1 :
			s_sec = 's'
		if uptime_min > 60 :
			uptime_hour = uptime_min / 60
			uptime_min -= (uptime_hour * 60)
			if uptime_min > 1 :
				s_min = 's'
			if uptime_hour > 24 :
				uptime_day = uptime_hour / 24
				uptime_hour -= (uptime_day * 24)
				if uptime_hour > 1 :
					s_hour = 's'
				if uptime_day > 1 :
					s_day = 's'
				uptime_string += _('%d day%s, ') % (uptime_day, s_day)
			uptime_string += _('%d hour%s, ') % (uptime_hour, s_hour)
		uptime_string += _('%d min%s, ') % (uptime_min, s_min)
	uptime_string += _('%d sec%s') % (uptime_sec, s_sec)				
			
	return _('''Up and running since <strong>%s</strong>.<br /><br />
Users: <strong>%d</strong> total, <strong>%d currently connected</strong>.<br /><br />
1, 5, and 15 last minutes load average: <strong>%s</strong>, %s, %s''') % (uptime_string, nbusers, cxusers, loads[0], loads[1], loads[2]) 

def system_info() :

	cpus  = 0
	model = ''

	for line in open('/proc/cpuinfo') :
		if line[0:9] == 'processor' : cpus += 1
		if line[0:10] == 'model name' : model = line.split(': ')[1]

	if cpus > 1 :
		s = 's'
	else :
		s = ''

	mem = {}

	def compute_mem(line, x) :
		#logging.debug(line[0:-1])

		if line[0:len(x)] == x :
			#print 'ok'
			return { x : float(re.split('\W+', line)[1]) / 1024000.0 }
		else :
			return {}

	for line in open('/proc/meminfo') :
		for x in ( 'MemTotal', 'Active', 'Inactive', 'MemFree', 'Buffers', 'Cached', 'SwapTotal', 'SwapFree' ) :
			mem.update(compute_mem(line, x))

	return _('''
Processor%s: %d x <strong>%s</strong><br /><br />
Physical memory: <strong>%.2fGib</strong> total,<br />
%.2f Gib for programs, %.2f Gib for cache, %.2f Gib for buffers.<br /><br />
Virtual memory: %.2f Gib total, <strong>%.0f%% free<strong>.
''') % (s, cpus, model, mem['MemTotal'], (mem['Inactive'] + mem['Active']), mem['Cached'], mem['Buffers'], mem['SwapTotal'], (mem['SwapFree'] * 100.0 / mem['SwapTotal']) )
	
def index(uri) :
		
	start = time.time()

	title = _("Server status")
	data  = '%s\n%s\n%s\n<div id="content">' % (w.backto(), __status_actions(), w.menu(uri)) 

	data += '''<table>
	<tr>
		<td><h1>%s</h1><br />%s</td>
		<td><h1>%s</h1>%s</td>
	</tr>
''' % (_('System information'), system_info(), _('System status'), system_load())

	data += '''
	<tr>
		<td colspan="2">&#160;</td></tr>
	</tr>
</table>
</div>
%s
	''' % (w.total_time(start, time.time()))

	return w.page(title, data)

