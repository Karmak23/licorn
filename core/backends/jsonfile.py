# -*- coding: utf-8 -*-
"""
Licorn Simple File backend -

:copyright: 2012 Robin Lucbernet <robin@meta-it.fr>
:license: GNU GPL version 2.

.. versionadded:: 1.3
"""

import os, errno

from licorn.foundations           import settings, logging, exceptions
from licorn.foundations           import readers, hlstr, fsapi, workers, json
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import Singleton

from licorn.core                  import LMC
from licorn.core.backends         import TasksBackend
from licorn.core.classes          import CoreStoredObject

class JSONTaskEncoder(json.LicornEncoder):
    def default(self, obj):
		if isinstance(obj, CoreStoredObject):
			# return the object stringified, it will be re-resolved
			# next time tasks are loaded from the data file.
			return 'LMC.{0}.by_name({1})'.format(obj.controller.name, obj.name)

		else:
			super(JSONTaskEncoder, self).default(obj)

class JsonfileBackend(Singleton, TasksBackend):
	""" A JSON file backend. """

	init_ok = False

	def __init__(self):

		assert ltrace(TRACE_JSONFILE, '> __init__(%s)' % JsonfileBackend.init_ok)

		if JsonfileBackend.init_ok:
			return

		TasksBackend.__init__(self, name='jsonfile')

		# the jsonfile backend is always enabled on a Linux system.
		self.available = True
		self.enabled   = True

		JsonfileBackend.init_ok = True
		assert ltrace(TRACE_JSONFILE, '< __init__(%s)' % JsonfileBackend.init_ok)
	def initialize(self):
		return self.available
	def load_Task(self, task):
		assert ltrace_func(TRACE_JSONFILE)
		self.load_Tasks()
	def load_Tasks(self):

		assert ltrace_func(TRACE_JSONFILE)

		try:
			with open(settings.tasks_data_file, 'r') as f:
				data = json.load(f)

		except (IOError, OSError), e:
			if e.errno == errno.ENOENT:
				data = []

			else:
				raise

		for json_data in data:
			if json_data is not None:
				try:
					name   = json_data['name']
					action = json_data['action']

				except KeyError:
					logging.exception(_(u'{0}: Exception while loading tasks'),
															self.pretty_names)
					logging.warning(_(u'{0}: consequently, THERE IS CURRENTLY '
						u'NO TASKS IN THE DAEMON!').format(self.pretty_name))
					return

				_year  = json_data['year'] if json_data.has_key('year') else None
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

				# FIXME: yield the task like all other backends.
				LMC.tasks.add_task(name, action, year=_year, month=month, day=day,
					hour=hour, minute=minute, second=second, delay_until_year=delay_until_year,
					delay_until_month=delay_until_month, delay_until_day=delay_until_day, delay_until_hour=delay_until_hour,
					delay_until_minute=delay_until_minute, delay_until_second=delay_until_second,
					args=args, kwargs=kwargs, defer_resolution=defer_resolution, week_day=week_day, load=True)

		assert ltrace_func(TRACE_JSONFILE, 1)
	def save_Task(self, task):
		self.save_Tasks(LMC.tasks)
	def save_Tasks(self, tasks):
		tab = []
		for task in tasks:
			tab.append(task.json_dump())
		try:
			with open(settings.tasks_data_file, 'w') as f:
				json.dump(tab, f, cls=JSONTaskEncoder, indent=4)

		except (OSError, IOError), e:
			logging.exception(_(u'{0}: could not save tasks on disk'), self.pretty_name)

	def delete_Task(self, task):
		self.save_Tasks(LMC.tasks)
