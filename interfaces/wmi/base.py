# -*- coding: utf-8 -*-

import time, re, socket

from subprocess            import Popen, PIPE

from licorn.foundations           import process
from licorn.foundations.base      import NamedObject
from licorn.foundations.constants import filters
from licorn.foundations.pyutils   import format_time_delta

from licorn.core import LMC

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi import utils as w

def ctxtnav(active=True):
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
def _flotr_pie_ram(progs, cache, buff, free):

	return '''<div id="flotr_memory" style="width:450px;height:300px;"></div>
	<script type="text/javascript">
	document.observe('dom:loaded', function(){
// Fill series.
var d1 = [[0, "%.2f"]];
var d2 = [[0, "%.2f"]];
var d3 = [[0, "%.2f"]];
var d4 = [[0, "%.2f"]];

//Draw the graph.
var f = Flotr.draw($('flotr_memory'), [
	{data:d1, label: '%s'},
	{data:d2, label: '%s'},
	{data:d3, label: '%s'},
	{data:d4, label: '%s', pie: {explode: 20}}
], {
colors: ['#FB8B00', '#EEC73E', '#C0D800', '#4DA74D' ],
title: "%s",
HtmlText: true,
grid: {
verticalLines: false,
horizontalLines: false,
outlineWidth: 0
},
xaxis: {showLabels: false},
yaxis: {showLabels: false},
pie: {show: true},
legend:{
position: 'ne',
backgroundColor: '#FFFFFF'
}
});
});
</script>
''' % (progs, cache, buff, free,
	_('Programs'), _('Cache'), _('Buffers'), _('Free'),
	_('Memory occupation')
	)
def _flotr_pie_swap(used, free):

	return '''<div id="flotr_swap" style="width:450px;height:300px;"></div>
	<script type="text/javascript">
	document.observe('dom:loaded', function(){
// Fill series.
var d1 = [[0, "%.2f"]];
var d2 = [[0, "%.2f"]];

//Draw the graph.
var f = Flotr.draw($('flotr_swap'), [
	{data:d1, label: '%s'},
	{data:d2, label: '%s'}
], {
colors: ['#cb4b4b', '#4da74d' ],
title: "%s",
HtmlText: true,
grid: {
verticalLines: false,
horizontalLines: false,
outlineWidth: 0
},
xaxis: {showLabels: false},
yaxis: {showLabels: false},
pie: {show: true},
legend:{
position: 'ne',
backgroundColor: '#FFFFFF'
}
});
});
</script>
''' % (used, free, _('Used'), _('Free'), _('Swap occupation'))
def index(uri, http_user, **kwargs):

	import licorn.interfaces.wmi as wmi
	from licorn.daemon import priorities

	start = time.time()

	title = _("Server status")
	data  = w.page_body_start(uri, http_user, ctxtnav, title)

	loads   = open('/proc/loadavg').read().split(" ")
	nbusers = len(LMC.users.Select(filters.STANDARD))

	cxusers = len(process.execute(['who'])[0].split('\n'))
	if cxusers > 1:
		s_users = 's'
	else:
		s_users = ''

	uptime_string = wmi.WMIObject.countdown('uptime',
		float(open('/proc/uptime').read().split(" ")[0]),
		uri='/', limit=99999999.0)

	cpus  = 0
	model = ''

	for line in open('/proc/cpuinfo'):
		if line[0:9] == 'processor': cpus += 1
		if line[0:10] == 'model name': model = line.split(': ')[1]

	if cpus > 1:
		s_cpu = 's'
	else:
		s_cpu = ''

	mem = {}

	def compute_mem(line, x):
		#assert logging.debug(line[0:-1] + " -> " + re.split('\W+', line)[1])

		split = re.split('[\W\(\)]+', line)

		if split[0] == x:
			try:
				return { x: float(split[1]) / 1000.0 }
			except:
				# skip "Active(xxx)" and other mixed entries from /proc/meminfo.
				return {}
		else:
			return {}

	for line in open('/proc/meminfo'):
		for x in ( 'MemTotal', 'Active', 'Inactive', 'MemFree', 'Buffers',
			'Cached', 'SwapTotal', 'SwapFree' ):
			mem.update(compute_mem(line, x))

	status_messages = {
		priorities.LOW: '',
		priorities.NORMAL: '',
		priorities.HIGH: ''
		}

	info_messages = {
		priorities.LOW:
				'<p class="light_indicator low_priority">%s</p>' % (
					_(u'automatic update of this page in %s.') %
					wmi.WMIObject.countdown('update', 28, uri='/')),
		priorities.NORMAL: '',
		priorities.HIGH: ''
		}

	if mem['SwapTotal'] == 0:
		# no swap on this system. Weird, but possible. fixes #40
		swap_message = '&nbsp;'
		swap_pie = '&nbsp;'
		info_messages[priorities.HIGH] += (
					'<p class="light_indicator high_priority">'
					'<img src="/images/16x16/emblem-important.png" '
					'alt="Important emblem" width="16" height="16" '
					'style="margin-top: -5px" />'
					'&nbsp;%s</p>' % _(u"No virtual memory configured!"))
	else:
		swap_message = (_("virtual memory: <strong>%.2f</strong> Mb total.")
															% mem['SwapTotal'])
		swap_pie = _flotr_pie_swap(mem['SwapTotal'] - mem['SwapFree'],
									mem['SwapFree'])

	def load_background(load):
		if load <= 0.5:
			return 'load_avg_level1'
		elif load <= 1.0:
			return 'load_avg_level2'
		elif load <= 1.5:
			return 'load_avg_level3'
		elif load <= 2.0:
			return 'load_avg_level4'
		elif load <= 3.0:
			return 'load_avg_level5'

	try:
		hostname = socket.gethostname()
	except Exception, e:
		logging.warning('WMI: cannot get hostname (was: %s)' % e)
		hostname = ''

	if hostname in ('', 'localhost', 'localhost6', 'localhost.localdomain',
					'localhost6.localdomain6'):
		hostname = ''
	else:
		hostname = _(u'“<strong>{hostname}</strong>” ').format(hostname=hostname)

	for obj in wmi.__dict__.itervalues():
		if isinstance(obj, NamedObject):
			if hasattr(obj, '_status'):
				for msgtuple in getattr(obj, '_status')():
					status_messages[msgtuple[0]] += msgtuple[1] + '\n'
			if hasattr(obj, '_info'):
				for msgtuple in getattr(obj, '_info')():
					info_messages[msgtuple[0]] += msgtuple[1] + '\n'

	data += '''
	<table style="margin-top: -40px">
	<tr>
		<td style="vertical-align: top; padding-bottom:20px;">
			<h1>{system_status_title}</h1>
			{status_messages[0]}
			<p>{system_status}<br /><br /></p>
			{status_messages[10]}
		</td>
		<td style="vertical-align: top; padding-bottom:20px;">
			<h1>{system_info_title}</h1>
			{info_messages[0]}
			<p>{system_info}</p>
			{info_messages[10]}
		</td>
	</tr>
	<tr>
		<td style="vertical-align: top;">

				{mem_pie}
			<br />
			{status_messages[20]}
		</td>
		<td style="vertical-align: top;">

				{swap_pie}
			<br />
			{info_messages[20]}
		</td>
	</tr>
	</table>
	'''.format(
			system_status_title=_('System status'),
			system_status=_('{hostname}{up_and_running} since <strong>{uptime}</strong>.<br /><br />'
				'Users: <strong>{accounts}</strong> {account_word}, '
				'<strong>{connected} {open_session_words}</strong>.<br /><br />'
				'1, 5, and 15 last minutes load average: '
				'<span class="small_indicator {load_back1}">{load1}</span> '
				'<span class="small_indicator {load_back5}">{load5}</span> '
				'<span class="small_indicator {load_back15}">{load15}</span>'
				).format(hostname=hostname, up_and_running=_(u'up and running')
					if hostname else _(u'Up and running'),
				uptime=uptime_string, accounts=nbusers, connected=cxusers,
				account_word=_('user accounts')
					if nbusers > 1 else _('user account'),
				open_session_words=_('open sessions')
					if cxusers > 1 else _('open session'),
				load1=loads[0], load5=loads[1], load15=loads[2],
				load_back1=load_background(float(loads[0])),
				load_back5=load_background(float(loads[1])),
				load_back15=load_background(float(loads[2]))),

			system_info_title=_('System information'),
			system_info=_('Processor{s_cpu}: {nb_cpu} x <strong>{cpu_model}</strong>'
				'<br /><br />'
				'Physical memory: <strong>{ram:.2f}Mb</strong> total.<br />'
				'{swap_total}').format(
					s_cpu=s_cpu, nb_cpu=cpus, cpu_model=model,
					ram=mem['MemTotal'],
					swap_total=swap_message),

			mem_pie=_flotr_pie_ram(
				mem['Inactive'] + mem['Active'],
				mem['Cached'],
				mem['Buffers'],
				mem['MemFree']
			),

			swap_pie=swap_pie,

			status_messages=status_messages,
			info_messages=info_messages
		)

	return (w.HTTP_TYPE_TEXT, w.page(title,
		data + w.page_body_end(w.total_time(start, time.time()))))
