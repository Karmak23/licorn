# -*- coding: utf-8 -*-

import time, re
from gettext import gettext as _

from subprocess            import Popen, PIPE

from licorn.foundations           import process
from licorn.foundations.constants import filters
from licorn.foundations.pyutils   import format_time_delta

from licorn.interfaces.wmi import utils as w

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

def system_load(users):
	loads = open('/proc/loadavg').read().split(" ")
	nbusers = len(users.Select(filters.STANDARD))

	cxusers = len(process.execute(['who'])[0].split('\n'))
	if cxusers > 1:
		s_users = 's'
	else:
		s_users = ''

	uptime_string = format_time_delta(
		int(float(open('/proc/uptime').read().split(" ")[0])))

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
		#assert logging.debug(line[0:-1] + " -> " + re.split('\W+', line)[1])

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
def index(uri, http_user, LMC=None, *args, **kwargs):

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
		_('System status'), system_load(LMC.users))

	return (w.HTTP_TYPE_TEXT, w.page(title,
		data + w.page_body_end(w.total_time(start, time.time()))))
