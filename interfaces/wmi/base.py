# -*- coding: utf-8 -*-

import time, re, CairoPlot, os

from subprocess import Popen, PIPE

from licorn.foundations           import process
from licorn.foundations.base      import NamedObject
from licorn.foundations.constants import filters
from licorn.foundations.pyutils   import format_time_delta

from licorn.core import LMC

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi import utils as w

load_references = [None, None, None]

def index(uri, http_user, **kwargs):

	import licorn.interfaces.wmi as wmi
	from licorn.daemon import priorities

	start = time.time()

	title = _("Server status")
	data  = w.page_body_start(uri, http_user, None, title)

	loads   = open('/proc/loadavg').read().split(" ")

	nbusers = len(LMC.users.select(filters.STANDARD))

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

	if mem['SwapTotal'] == 0:
		# no swap on this system. Weird, but possible. fixes #40
		swap_message = _("no virtual memory installed.")
	else:
		swap_message = (_("virtual memory: <strong>%.2f</strong> Mb total.")
															% mem['SwapTotal'])

	def load_picture(index):
		r = load_references[index]
		l = loads[index]
		if r is None:
			#print "None"
			return_data = 'bla'
		if l < r:
			return_data = '<img src="/images/12x12/loads_desc.png"/>'
		elif l > r:
			return_data = '<img src="/images/12x12/loads_asc.png"/>'
		elif l == r:
			return_data = '<img src="/images/12x12/loads_equal.png"/>'

		load_references[index] = l
		return return_data


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

	for obj in wmi.__dict__.itervalues():
		if isinstance(obj, NamedObject):
			if hasattr(obj, '_status'):
				for msgtuple in getattr(obj, '_status')():
					status_messages[msgtuple[0]] += msgtuple[1] + '\n'
			if hasattr(obj, '_info'):
				for msgtuple in getattr(obj, '_info')():
					info_messages[msgtuple[0]] += msgtuple[1] + '\n'


	main_content = '''
	<div>
		<h1>{system_info_title}</h1>
		{info_messages[0]}
		<p>{system_info}</p>
		{info_messages[10]}
	</div>
	<div>
		<h1>{system_status_title}</h1>
		{status_messages[0]}
		<p>{system_status}<br /><br /></p>
		{status_messages[10]}
		{status_messages[20]}

	</div> '''.format(
		status_messages=status_messages,
		system_status_title=_('System status'),
		system_status=_('Up and running since <strong>{uptime}</strong>.<br /><br />'
			'Users: <strong>{accounts}</strong> {account_word}, '
			'<strong>{connected} {open_session_word}</strong>.<br /><br />'
			'<div class="stat_line">Last minute load average : <strong>{load_average_last_value}</strong> {load_average_last_picture}</div>'
			'<div class="stat_line">Last 5 minutes load average : <strong>{load_average_five_value}</strong> {load_average_five_picture}</div>'
			'<div class="stat_line">Last 15 minutes load average : <strong>{load_average_fifteen_value}</strong> {load_average_fifteen_picture}</div>'
			).format(
			uptime=uptime_string, accounts=nbusers, connected=cxusers,
			account_word=_('user accounts')
				if nbusers > 1 else _('user account'),
			open_session_word=_('open sessions')
				if cxusers > 1 else _('open session'),
			load_average_last_value = loads[0],
			load_average_last_picture = load_picture(0),
			load_average_five_value = loads[1],
			load_average_five_picture = load_picture(1),
			load_average_fifteen_value = loads[2],
			load_average_fifteen_picture = load_picture(2),
			),
		system_info_title=_('System information'),
		system_info=_('Processor{s_cpu}: {nb_cpu} x <strong>{cpu_model}</strong>'
			'<br /><br />'
			'Physical memory: <strong>{ram:.2f}Mb</strong> total.<br />'
			'{swap_total}').format(
				s_cpu=s_cpu, nb_cpu=cpus, cpu_model=model,
				ram=mem['MemTotal'],
				swap_total=swap_message),
		info_messages=info_messages)

	data += w.main_content(main_content)


	# sub content
	chart_folder = os.path.realpath(__file__).rsplit('/', 1)[0] + "/images"
	background = (1, 1, 1)
	inner_radius = 0.90
	height = 230
	width = 370

	# memory pie chart
	mem_pie_data = {
			_(u'Apps') + ' (%d%%)' % ((mem['Inactive'] + mem['Active']) *
										100.0 / mem['MemTotal']) : mem['Inactive'] + mem['Active'],
			_(u'Cache') + ' (%d%%)' % (mem['Cached'] * 100.0 / mem['MemTotal']) : mem['Cached'],
			_(u'Buffers') + ' (%d%%)' % (mem['Buffers'] * 100.0 / mem['MemTotal']): mem['Buffers'],
			_(u'Free') + ' (%d%%)' % (mem['MemFree'] * 100.0 / mem['MemTotal']): mem['MemFree']
		}
	mem_pie_colors = [
			(255.0/255, 0.0/255, 102.0/255),
			(106.0/255, 0.0/255, 43.0/255),
			(86.0/255, 220.0/255, 255.0/255),
			(100.0/255, 102.0/255, 64.0/255)
		]

	CairoPlot.donut_plot("%s/mem_pie_donnut.png" % chart_folder,
		mem_pie_data, width, height, colors = mem_pie_colors,
		inner_radius=inner_radius, background= background,
		radius=100)

	# Swap pie chart
	swap_pie_data = {
			_(u'Free') + ' (%d%%)' % (mem['SwapFree'] * 100.0 / mem['SwapTotal']): mem['SwapFree'],
			_(u'Used') + ' (%d%%)' % ((mem['SwapTotal'] - mem['SwapFree']) *
										100.0 / mem['SwapTotal']): mem['SwapTotal']-mem['SwapFree']
		}
	swap_pie_colors = [
			(255.0/255, 0.0/255, 102.0/255),
			(106.0/255, 0.0/255, 43.0/255)
		]

	CairoPlot.donut_plot("%s/swap_pie_donnut.png" % chart_folder,
		swap_pie_data, width, height, colors=swap_pie_colors,
		inner_radius=inner_radius, background=background,
		radius=100)

	sub_content = '''
	<div id='charts'>
		<h1>{title}</h1>
		<div id="ram_usage_content" class="donut_content">
			<h2>{mem_title}</h2>
			<div class="pie_chart" title="%s">
				<img src='/images/mem_pie_donnut.png'/>
			</div>
		</div>
		<div id="swap_usage_content" class="donut_content">
			<h2>{swap_title}</h2>
			<div class="pie_chart" title="%s">
				<img src='/images/swap_pie_donnut.png'/>
			</div>
		</div>
	</div>
	{info_messages[20]}
'''.format(
			title=_('System resources usage'),
			mem_title=_('Physical memory'),
			swap_title=_('Virtual (swap) memory'),
			info_messages=info_messages
		)

	data += w.sub_content(sub_content)

	page = w.page(title,
		data + w.page_body_end(w.total_time(start, time.time())))

	return (w.HTTP_TYPE_TEXT, page)



	"""
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
			system_status=_('Up and running since <strong>{uptime}</strong>.<br /><br />'
				'Users: <strong>{accounts}</strong> {account_word}, '
				'<strong>{connected} {open_session_words}</strong>.<br /><br />'
				'1, 5, and 15 last minutes load average: '
				'<span class="small_indicator {load_back1}">{load1}</span> '
				'<span class="small_indicator {load_back5}">{load5}</span> '
				'<span class="small_indicator {load_back15}">{load15}</span>').format(
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

			swap_pie=_flotr_pie_swap(mem['SwapTotal']-mem['SwapFree'], mem['SwapFree'])
				if swap_message != '' else '',

			status_messages=status_messages,
			info_messages=info_messages
		)

	return (w.HTTP_TYPE_TEXT, w.page(title,
		data + w.page_body_end(w.total_time(start, time.time()))))"""
