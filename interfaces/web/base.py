# -*- coding: utf-8 -*-

import os, time, re

from subprocess            import Popen, PIPE
from licorn.core           import users, configuration
from licorn.foundations    import logging
from licorn.interfaces.web import utils as w

#remove this after testing
reload(w)

def ctxtnav() :
	return '''
	<div id="ctxtnav" class="nav">
        <h2>Context Navigation</h2>
		<ul>
		<li><a href="/server/reboot" title="%s" class="lightwindow"><div class="ctxt-icon" id="icon-reboot">%s</div></a></li>
		<li><a href="/server/halt" title="%s" class="lightwindow"><div class="ctxt-icon" id="icon-shutdown">%s</div></a></li>
		</ul>
        <hr />
	</div>
	''' % (
		_('Restart server.'),
		_('Restart server'),
		_('Shutdown server.'),
		_('Shutdown server'))

def system_load() :
	loads = open('/proc/loadavg').read().split(" ")
	
	allusers  = users
	allusers.Select(allusers.FILTER_STANDARD)
	nbusers = len(allusers.filtered_users)

	cxusers = len(Popen('who', shell = True, stdin = PIPE, stdout = PIPE, close_fds = True).stdout.read().split('\n'))
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
		#logging.debug(line[0:-1] + " -> " + re.split('\W+', line)[1])

		split = re.split('[\W\(\)]+', line)

		if split[0] == x :
			try:
				return { x : float(split[1]) / 1048576.0 }
			except:
				# skip "Active(xxx)" and other mixed entries from /proc/meminfo.
				return {}
		else :
			return {}

	for line in open('/proc/meminfo') :
		for x in ( 'MemTotal', 'Active', 'Inactive', 'MemFree', 'Buffers', 'Cached', 'SwapTotal', 'SwapFree' ) :
			mem.update(compute_mem(line, x))

	return _('''
Processor%s: %d x <strong>%s</strong><br /><br />
Physical memory: <strong>%.2fGb</strong> total,<br />
%.2f Gb for programs, %.2f Gb for cache, %.2f Gb for buffers.<br /><br />
Virtual memory: %.2f Gb total, <strong>%.0f%% free<strong>.
''') % (s, cpus, model, mem['MemTotal'], (mem['Inactive'] + mem['Active']), mem['Cached'], mem['Buffers'], mem['SwapTotal'], (mem['SwapFree'] * 100.0 / mem['SwapTotal']) )
	
def reboot(uri, http_user, sure = False) :
	if sure :
		return w.minipage(w.lbox('''<div class="vspacer"></div>%s''' % _('Rebooting…')))
	else :
		return w.minipage(w.lbox('''%s
		<div class="vspacer"></div>
		<table class="lbox-table">
			<tr>
				<td>
					<form name="reboot_form" id="reboot_form" action="/server/reboot/sure" method="get">
						<a href="/server/reboot/sure"  params="lightwindow_form=reboot_form,lightwindow_width=320,lightwindow_height=140" class="lightwindow_action" rel="submitForm">
							<button>%s</button>
						</a>
					</form>
				</td>
				<td>
					<a href="#" class="lightwindow_action" rel="deactivate"><button>%s</button></a>
				</td>
			</tr>
		</table>
		''' % (
		_('Sure you want to reboot the %s server?') % configuration.app_name,
		_('YES'),
		_('NO'))))
def halt(uri, http_user, sure = False) :
	if sure :
		return w.minipage(w.lbox('''<div class="vspacer"></div>%s''' % _('Shutting down…')))
	else :
		return w.minipage(w.lbox('''%s<div class="vspacer"></div>
		<table class="lbox-table">
			<tr>
				<td>
					<form name="shutdown_form" id="shutdown_form" action="/server/halt/sure" method="get">
						<a href="/server/halt/sure"  params="lightwindow_form=shutdown_form,lightwindow_width=320,lightwindow_height=140" class="lightwindow_action" rel="submitForm">
							<button>%s</button>
						</a>
					</form>
				</td>
				<td>
					<a href="#" class="lightwindow_action" rel="deactivate"><button>%s</button></a>
				</td>
			</tr>
		</table>''' % (
		_('Sure you want to shutdown the %s server?') % configuration.app_name,
		_('YES'),
		_('NO'))))
def index(uri, http_user) :
		
	start = time.time()

	title = _("Server status")
	data  = '<div id="banner">\n%s\n%s\n%s\n</div><!-- banner -->\n<div id="main">\n%s\n<div id="content">' % (w.backto(), w.metanav(http_user), w.menu(uri), ctxtnav()) 

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
</div><!-- content -->
%s
</div><!-- main -->
	''' % (w.total_time(start, time.time()))

	return w.page(title, data)

