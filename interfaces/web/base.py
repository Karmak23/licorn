# -*- coding: utf-8 -*-

import os, time, re

from licorn.core           import users
from licorn.interfaces.web import utils as w

def __status_actions() :
	return '''
<div id="actions">
	<div class="action">
		<a href="/server/reboot" title="Redémarrer le serveur."><img src="/images/32x32/reboot.png" alt="Redémarrer le serveur." /><br />Redémarrer le serveur</a>
	</div>
	<div class="action">
		<a href="/server/halt" title="Éteindre le serveur."><img src="/images/32x32/shutdown.png" alt="Éteindre le serveur." /><br />Éteindre le serveur</a>
	</div>
</div>
	'''

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
				uptime_string += '%d jour%s, ' % (uptime_day, s_day)
			uptime_string += '%d heure%s, ' % (uptime_hour, s_hour)
		uptime_string += '%d min%s, ' % (uptime_min, s_min)
	uptime_string += '%d sec%s' % (uptime_sec, s_sec)				
			
	return '''En marche depuis <strong>%s</strong>.<br /><br />
Utilisateurs&nbsp;: <strong>%d</strong> au total, <strong>%d actuellement connecté%s</strong>.<br /><br />
Charge sur les 1, 5, et 15 dernières minutes&nbsp;: <strong>%s</strong>, %s, %s''' % (uptime_string, nbusers, cxusers, s_users, loads[0], loads[1], loads[2]) 

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

	return '''
Processeur%s&nbsp;: %d x <strong>%s</strong><br /><br />
Mémoire Physique&nbsp;: <strong>%.2fGio</strong> au total,<br />
%.2f Gio programmes, %.2f Gio cache, %.2f Gio tampons.<br /><br />
Mémoire virtuelle&nbsp;: %.2f Gio au total, <strong>%.0f%% libre<strong>.
''' % (s, cpus, model, mem['MemTotal'], (mem['Inactive'] + mem['Active']), mem['Cached'], mem['Buffers'], mem['SwapTotal'], (mem['SwapFree'] * 100.0 / mem['SwapTotal']) )
	
def index(uri) :
		
	start = time.time()

	title = "État du serveur"
	data  = '%s\n%s\n%s\n<div id="content">' % (w.backto(), __status_actions(), w.menu(uri)) 

	data += '''<table>
	<tr>
		<td><h1>Informations Système</h1><br />%s</td>
		<td><h1>État du système</h1>%s</td>
	</tr>
''' % (system_info(), system_load())

	data += '''
	<tr>
		<td colspan="2">&#160;</td></tr>
	</tr>
</table>
</div>
%s
	''' % (w.total_time(start, time.time()))

	return w.page(title, data)

