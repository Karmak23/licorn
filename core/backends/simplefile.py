# -*- coding: utf-8 -*-
"""
Licorn Simple File backend - 

:copyright: 2012 Robin Lucbernet <robin@meta-it.fr>
:license: GNU GPL version 2.

.. versionadded:: 1.3
"""

import os, crypt, tempfile, grp, pyinotify, json, datetime

from threading  import Timer
from traceback  import print_exc
from contextlib import nested

from licorn.foundations           import settings, logging, exceptions
from licorn.foundations           import readers, hlstr, fsapi, workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import Singleton, BasicCounter
from licorn.foundations.classes   import FileLock
from licorn.foundations.constants import priorities
from licorn.core                  import LMC
from licorn.core.tasks            import Task
from licorn.core.backends         import TasksBackend

class SimplefileBackend(Singleton, TasksBackend):
	""" A simple file backend. """

	init_ok = False

	def __init__(self):

		assert ltrace(TRACE_SIMPLEFILE, '> __init__(%s)' % SimplefileBackend.init_ok)

		if SimplefileBackend.init_ok:
			return

		TasksBackend.__init__(self, name='simplefile')

		# the simplefile backend is always enabled on a Linux system.
		self.available = True
		self.enabled   = True

		SimplefileBackend.init_ok = True
		assert ltrace(TRACE_SIMPLEFILE, '< __init__(%s)' % SimplefileBackend.init_ok)
	def initialize(self):
		return self.available
	
	def load_Task(self, task):
		assert ltrace_func(TRACE_SHADOW)
		self.load_Tasks()
	def load_Tasks(self):

		assert ltrace_func(TRACE_SHADOW)

		# take tasks from config file
		try:
			_file = open(settings.licornd.cron_file, "rb")
			data = json.load(_file)
			_file.close()
		except IOError, e:
			data = []
		

		now = datetime.datetime.now()

		for json_data in data:
			if json_data is not None:
				try:
					name = json_data['name']
					action = json_data['action']
				except KeyError:
					logging.exception('Exception while loading tasks')
					return
				
				_year   = json_data['year'] if json_data.has_key('year') else None
				month  = json_data['month'] if json_data.has_key('month') else None
				day    = json_data['day'] if json_data.has_key('day') else None
				hour   = json_data['hour'] if json_data.has_key('hour') else None
				minute = json_data['minute'] if json_data.has_key('minute') else None
				second = json_data['second'] if json_data.has_key('second') else None

				week_day = json_data['week_day'] if json_data.has_key('week_day') else None

				delay_until_year   = json_data['delay_until_year'] if json_data.has_key('delay_until_year') else None
				delay_until_month  = json_data['delay_until_month'] if json_data.has_key('delay_until_month') else None
				delay_until_day    = json_data['delay_until_day'] if json_data.has_key('delay_until_day') else None
				delay_until_hour   = json_data['delay_until_hour'] if json_data.has_key('delay_until_hour') else None
				delay_until_minute = json_data['delay_until_minute'] if json_data.has_key('delay_until_minute') else None
				delay_until_second = json_data['delay_until_second'] if json_data.has_key('delay_until_second') else None

				args = json_data['args'] if json_data.has_key('args') else None
				kwargs = json_data['kwargs'] if json_data.has_key('kwargs') else None

				defer_resolution = bool(json_data['defer_resolution']) if json_data.has_key('defer_resolution') else None
				
				LMC.tasks.add_task(name, action, year=_year, month=month, day=day, 
					hour=hour, minute=minute, second=second, delay_until_year=delay_until_year,
					delay_until_month=delay_until_month, delay_until_day=delay_until_day,
					delay_until_minute=delay_until_minute, delay_until_second=delay_until_second,
					args=args, kwargs=kwargs, defer_resolution=defer_resolution, week_day=week_day, load=True)
				
					
		assert ltrace_func(TRACE_SHADOW, 1)
	def save_Task(self, task):
		self.save_Tasks(LMC.tasks)
	def save_Tasks(self, tasks):
		tab = []
		for task in tasks:
			tab.append(task.json_dump())
		_file = open(settings.licornd.cron_file, "w")
		json.dump(tab, _file, cls=JSONTaskEncoder, indent=4)
		_file.close()
	def delete_Task(self, task):
		self.save_Tasks(LMC.tasks)



from licorn.core.classes          import CoreStoredObject
try:
	from licorn.foundations._json     import LicornEncoder as encoder
except:
	from json import JSONEncoder as encoder

class JSONTaskEncoder(encoder):
    def default(self, obj):
		if isinstance(obj, CoreStoredObject):
			r = "LMC."+ obj.controller.name + '.by_name('+ obj.name+')'
			return r
		else:
			super(JSONTaskEncoder, self).default(obj)
