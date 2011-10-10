# -*- coding: utf-8 -*-

import time, re, CairoPlot, os, json

from subprocess import Popen, PIPE
from string     import Template

from licorn.foundations           import process
from licorn.foundations.base      import NamedObject
from licorn.foundations.constants import filters
from licorn.foundations.pyutils   import format_time_delta

from licorn.core import LMC

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi import utils as w

load_references = [None, None, None]

def _avg_loads():
	return open('/proc/loadavg').read().split(' ', 3)[0:3]
def JSON_avg_loads(uri, http_user, **kwargs):
	return (w.HTTP_TYPE_JSON, json.dumps(_avg_loads()))

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

	"""
	def templated(func):
		def deco1(tpath):
			func.template = Template(open(tpath).read())

			def deco2(**kwargs):
				return func(func.template, **kwargs)

			return deco2
		return deco1

	@templated('/usr/share/licorn/wmi/js/donut.js')
	def d3_donut(t, **kwargs):
		return t.substitute(**kwargs)
	"""
	def load_avg_chart(initial_data=None):
		if initial_data is None:
			#initial_data = [(0.0, 0.0, 0.0) * 9] + [_avg_loads()]
			initial_data = _avg_loads()
			initial_data.reverse()

		return u'''
<style type="text/css">
#load_avg_chart {{
	float: left;
	stroke: white;
	font: 10px sans-serif;
	color: black;
}}

.load_avg_chart_bar0 {{
	stroke: white;
	fill: red;
	text-align: center;
	padding: 3px;
	margin: 1px;
}}
.load_avg_chart_bar1 {{
	stroke: white;
	fill: orange;
	text-align: center;
	padding: 3px;
	margin: 1px;
}}
.load_avg_chart_bar2 {{
	stroke: white;
	fill: yellow;
	text-align: center;
	padding: 3px;
	margin: 1px;
}}
.rule, .label {{
	font: sans-serif;
	font-size: 10px;
	font-weight: lighter;
	stroke: #580d27;

}}
</style>
<script language="javascript">
	move_from_x = 0;

	avg_chart_data = {initial_data};

	var avg_chart_x = d3.scale.linear()
		.domain([0, Math.ceil(d3.max(avg_chart_data))])
		.range([0, 400]);

	// the limit where the avg label must be draw outside the bar, because
	// the bar is too small.
	var limit = avg_chart_x.domain()[1] * 0.07;

	var avg_chart_y = d3.scale.ordinal()
		.domain(avg_chart_data)
		.rangeBands([4, 75]);

	var avg_chart = d3.select('div#load_avg_chart')
					.append("svg:svg")
						.attr("id", "load_avg_chart")
						.attr("width", 430)
						.attr("height", 95)
						.append("svg:g")
						.attr("transform", "translate(10, 15)");

	avg_chart.selectAll("line.scaleline")
		.data(avg_chart_x.ticks(10))
		.enter().append("svg:line")
		.attr("class", "scaleline")
		.attr("x1", move_from_x)
		.attr("y1", 0)
		.attr("x2", move_from_x)
		.attr("y2", 75)
		.attr("stroke", "#ccc")
		.transition()
			.duration(1000)
		.attr("x1", avg_chart_x)
		.attr("x2", avg_chart_x);

	avg_chart.selectAll("rect.databar")
		.data(avg_chart_data)
		.enter().append("svg:rect")
		.attr("y", avg_chart_y)
		.attr("width", move_from_x)
		.attr("height", avg_chart_y.rangeBand() - 4)
		.attr("class", function (d, i) {{ return 'databar load_avg_chart_bar' + i; }})
		.transition()
			.duration(1000)
		.attr("width", avg_chart_x);

	avg_chart.selectAll("text.label")
		.data(avg_chart_data)
		.enter().append("svg:text")
		.attr("class", "label")
		.attr("x", move_from_x)
		.attr("text-anchor", "end") // text-align: right
		.attr("y", function(d) {{ return avg_chart_y(d) + (avg_chart_y.rangeBand()-4) / 2; }})
		.attr("dx", -3) // padding-right
		.attr("dy", ".35em") // vertical-align: middle
		.text(String)
		.transition()
			.duration(1000)
		.attr("x", function(d) {{ if (d > limit) {{
									return avg_chart_x(d);
								}} else {{
									return avg_chart_x(d) + avg_chart_x(limit);
								}} }});

	avg_chart.selectAll("text.rule")
		.data(avg_chart_x.ticks(10))
		.enter().append("svg:text")
		.attr("class", "rule")
		.attr("x", move_from_x)
		.attr("y", 0)
		.attr("dy", -3)
		.attr("text-anchor", "middle")
		.text(function(d){{ return d.toFixed(2); }})
		.transition()
			.duration(1000)
		.attr("x", avg_chart_x);

	avg_chart.append("svg:line")
		.attr("class", "baseline")
		.attr("y1", 0)
		.attr("y2", 75)
		.attr("stroke", "#000");

	function redraw_avg_chart(data) {{

		//console.log('redraw ' + data.toString() + ' max: ' + [0, (parseFloat(d3.max(data)) + 0.5)].toString());
		//console.log('old domain: ' + avg_chart_x.domain());

		transition_delay = 2500;
		transition_fast  = 1000;

		var avg_chart_old_max = avg_chart_x.domain()[1];
		var avg_chart_new_max = Math.ceil(d3.max(data));

		if ( avg_chart_new_max > avg_chart_old_max) {{
			changes = true;
			moving_up = true;
			moving_down = false;
			move_to_x = 0;
			move_from_x = 435;
			//console.log('scaling UP from ' + avg_chart_old_max + ' to ' + avg_chart_new_max);

		}} else if (avg_chart_new_max < avg_chart_old_max) {{
			changes = true;
			moving_up = false;
			moving_down = true;
			move_to_x = 435;
			move_from_x = 0;
			//console.log('scaling down from ' + avg_chart_old_max + ' to ' + avg_chart_new_max);

		}} else {{
			changes = false;
		}}

		if (changes) {{

			// recompute x scale, based on new values
			avg_chart_x.domain([0, avg_chart_new_max]);

			//console.log('new domain: ' + avg_chart_x.domain());

			new_ticks = avg_chart_x.ticks(10);

			updated_rules = avg_chart.selectAll("text.rule").data(new_ticks);
			updated_lines = avg_chart.selectAll("line.scaleline")
								.data(new_ticks);

			if (moving_down) {{
				// insert new ticks on the left

				updated_rules.enter()
					.insert("svg:text", "text.rule")
					.attr("class", "rule")
					.attr("x", move_from_x)
					.attr("y", 0)
					.attr("dy", -3)
					.attr("text-anchor", "middle")
					.text(function(d){{ return d.toFixed(2); }})
					.transition()
						.duration(transition_fast)
					.attr("x", avg_chart_x);

				updated_lines.enter()
					.insert("svg:line", 'line')
					.attr("class", "scaleline")
					.attr("x1", move_from_x)
					.attr("y1", 0)
					.attr("x2", move_from_x)
					.attr("y2", 75)
					.attr("stroke", "#ccc")
					.transition()
						.duration(transition_fast)
					.attr("x1", avg_chart_x)
					.attr("x2", avg_chart_x);

			}} else {{
				// append new ticks on the right

				updated_rules.enter()
					.append("svg:text")
					.attr("class", "rule")
					.attr("x", move_from_x)
					.attr("y", 0)
					.attr("dy", -3)
					.attr("text-anchor", "middle")
					.text(function(d){{ return d.toFixed(2); }})
					.transition()
						.duration(transition_fast)
					.attr("x", avg_chart_x);

				// we must insert them before the rects databars, else they get
				// printed above instead of below.
				updated_lines.enter()
					.insert("svg:line", "rect.databar")
					.attr("class", "scaleline")
					.attr("x1", move_from_x)
					.attr("y1", 0)
					.attr("x2", move_from_x)
					.attr("y2", 75)
					.attr("stroke", "#ccc")
					.transition()
						.duration(transition_fast)
					.attr("x1", avg_chart_x)
					.attr("x2", avg_chart_x);

			}}

			updated_rules
				.transition()
					.duration(transition_fast)
				.attr("x", avg_chart_x)
				.text(function(d){{ return d.toFixed(2); }});

			updated_rules.exit()
				.transition()
					.duration(transition_fast)
				.attr("x", move_to_x)
				.remove();

			updated_lines
				.transition()
					.duration(transition_fast)
				.attr("x1", avg_chart_x)
				.attr("x2", avg_chart_x);

			updated_lines.exit()
				.transition()
					.duration(transition_fast)
				.attr("x1", move_to_x)
				.attr("x2", move_to_x)
				.remove();
		}}

		// change load rect widths.
		avg_chart.selectAll("rect.databar")
			.data(data)
			.transition()
				.duration(transition_delay)
			.attr("width", avg_chart_x);

		limit = avg_chart_x.domain()[1] * 0.07;

		// redraw load values, and recompute text coordinates.
		avg_chart.selectAll("text.label")
			.data(data)
			.transition()
				.duration(transition_delay)
			.attr("x", function(d) {{ if (d > limit) {{
										return avg_chart_x(d);
									}} else {{
										return avg_chart_x(d) + avg_chart_x(limit);
									}} }})
			.text(String);
	}}

	setInterval(function() {{
		$.getJSON('/base/JSON_avg_loads', function(data) {{
			var data_list = data.content;
			//console.log('new avg ' + data_list.toString());
			redraw_avg_chart(data_list.reverse());
			}});
	}}, 5000);
</script>
'''.format(initial_data=json.dumps(initial_data))
	#initial_data_range=json.dumps([sum(x) for x in initial_data]))


		# the HTML / DIV version
		return u'''
<script language="javascript">
	data = {initial_data};

	var x = d3.scale.linear()
		.domain([0, d3.max(data)])
		.range(["0px", "300px"]);

	var avg_chart = d3.select('div#load_avg_chart');

	avg_chart.selectAll('div')
		.data(data)
		.enter().append('div')
		.style("width", x)
		.attr("class", "load_avg_chart_bar")
		.text(function(d) {{ return d; }});

</script>
'''.format(initial_data=json.dumps(initial_data))

	status_messages = {
		priorities.LOW: '',
		priorities.NORMAL: '',
		priorities.HIGH: ''
		}

	info_messages = {
		priorities.LOW: '',
		priorities.LOW: '',
				#'<p class="light_indicator low_priority">%s</p>' % (
				#	_(u'automatic update of this page in %s.') %
				#	wmi.WMIObject.countdown('update', 28, uri='/')),
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
		system_status=_(u'Up and running since <strong>{uptime}</strong>.<br /><br />'
			u'Users: <strong>{accounts}</strong> {account_word}, '
			u'<strong>{connected} {open_session_word}</strong>.<br /><br />'
			u'<div class="load_avg_wrapper"><div class="load_avg_label">{load_avg_label}</div><div id="load_avg_chart"></div>{load_avg_chart}</div>'
			).format(
			uptime=uptime_string, accounts=nbusers, connected=cxusers,
			account_word=_('user accounts')
				if nbusers > 1 else _('user account'),
			open_session_word=_('open sessions')
				if cxusers > 1 else _('open session'),
			load_avg_label=_(u'Average load on 15, 5 and 1 minute(s)'),
			load_avg_chart = load_avg_chart()
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
