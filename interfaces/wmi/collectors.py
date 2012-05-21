# -*- coding: utf-8 -*-

import re, Pyro.errors

from licorn.foundations import process
from licorn.core        import LMC

not_started = True

def ramswap():
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
	mem = {}
	for line in open('/proc/meminfo'):
		for x in ( 'MemTotal', 'Active', 'Inactive', 'MemFree', 'Buffers',
			'Cached', 'SwapTotal', 'SwapFree' ):
			mem.update(compute_mem(line, x))

	return mem
ramswap.interval = 5

def connected_users():
	return len(process.execute(['who'])[0].split('\n'))
connected_users.interval = 10

def avg_loads():
	#print '>> AVG'
	# the round() is necessary to make the JS-side happy; without it, there
	# are too many decimals and the graphs can be messed up.
	return [ round(float(x), 3) for x in open('/proc/loadavg').read().split(' ', 3)[0:3] ]
avg_loads.interval = 5


def daemon_status():
	from licorn.daemon.main import daemon
	return daemon.dump_status(as_string=False)
daemon_status.interval        = 5
daemon_status.js_method       = 'refresh_div'
daemon_status.js_arguments    = ([ '$("#main_content")' ], [ 'false' ])
daemon_status.render_template = 'system/daemon_status_main.html'
