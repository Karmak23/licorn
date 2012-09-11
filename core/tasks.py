# -*- coding: utf-8 -*-
"""
:copyright: 2012 Robin Lucbernet <robin@meta-it.fr>

:license: GNU GPL version 2

Introduction
============

	The TaskController is a scheduler to manage tasks. A task is an action that
	can be delayed in the time and rescheduled.

	The main goal of this controller is to automate execution of several Licorn
	tasks (automate machine extinction ...)

Task arguments
==============

	``name``:
		name of the task (string) - **REQUIRED**
	``action``:
		action of the task / method to run (string) - **REQUIRED**

	``year``, ``month``, ``day``, ``week_day``, ``hour``, ``minute``,
	``second``:
		temporal arguments defining when the task will be scheduled. The syntax
		used for temporal arguments is inspired by the cron timing format:

		+-------------------+-------------------------------------------+-----------------------------+
		| Syntax            | Explanation                               | Example(s)                  |
		+===================+===========================================+=============================+
		| `\*`              | every                                     |                             |
		+-------------------+-------------------------------------------+-----------------------------+
		| `\*/n`            | every modulo n                            | - \*/2 = [0,2,4,6,8,...]    |
		|                   |                                           | - \*/15 = [0,15,30,45]      |
		|                   |                                           | - \*/45 = [0,45]            |
		+-------------------+-------------------------------------------+-----------------------------+
		| `n:m`             | period, from n to m (included)            | 5:10 = [5,6,7,8,9,10]       |
		+-------------------+-------------------------------------------+-----------------------------+
		| `[x[,y[...]]]`    | several occurence                         |                             |
		+-------------------+-------------------------------------------+-----------------------------+
		| `A^[x[,y[...]]]`  | A except x,y,...                          | - \*/2^4,6 = [0,2,8,10,...] |
		|                   |                                           | - 5:10^7 = [5,6,8,9,10]     |
		+-------------------+-------------------------------------------+-----------------------------+

		Every arguments are positive integers, except for ``day`` where
		we can user negative integer to specify day from the end of the month
		(-1 is the last day, -2 the days before and so on ...)

		By default, every temporal arguments are equal to **\***, except
		``second`` which is **0**.

	``delay_until_year``, ``delay_until_month``, ``delay_until_day``,
	``delay_until_hour``, ``delay_until_minute``, ``delay_until_second``:
		These args can be used in order to delay the first occurence of the
		task. Defaults are None.

	``args`` and ``kwargs``
		define args and kwargs of the action. Expected arg syntax:
		arg1[;arg2[...]] ; kwarg syntax: k1=v1[;k2=v2[...]]

	``defer_resolution``
		define when args and kwargs will be resolved. If True, by default,
		during each task execution. Else, during task load.

CLI examples
============

	1. **ADD** task:



	+ Basic action, every minute::

		add task --name "example1" --action logging.notice
			--args "example1: every minute"

	+ Basic action, every 5 second::

		add task --name "example2" --action logging.notice
			--args "example2: every 5 sec" --second \*/5

	+ The 2012, july 14 at 13h37 every 15 second except 30::

		add task --name "example3" --action logging.notice
			--args msg --year 2012 --month 7 --day 14 --hour 13
			--minute 37 --second \*/15^30

	+ The 15 and the last day of the month, every 15 minutes except 30, between
	hours 12 and 14::

		add task --name "example3" --action logging.notice --args msg
			--day 15,-1	--hour 12:14 --minute \*/15^30

	2. **DEL** task:

	You can use either ``id`` or ``name`` of the task to delete it::

		del task 0
		del task example1

	3. **MOD** task:

	This is not avalaible for the moment. Just delete the task you want to
	modify and create it correctly.

	4. **GET** task:

	By default select all task, or the specified one::

		get tasks
		get tasks -a

		get task example1


Developer documentation
=======================


"""
import types, json, calendar, errno, re, gc, sys
import time
from operator   import attrgetter

from datetime                     import datetime, timedelta
from dateutil.rrule               import *
from dateutil.relativedelta       import *

from licorn.foundations           import settings, logging, exceptions, \
										pyutils, events
from licorn.foundations.base      import DictSingleton
from licorn.foundations.workers   import workers
from licorn.foundations.constants import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.styles    import *

from licorn.core                  import LMC
from licorn.core.classes          import CoreController, CoreStoredObject, \
										SelectableController

from licorn.daemon.threads        import LicornJobThread
from licorn.interfaces.wmi.app    import wmi_event_app

from licorn.foundations.events    import LicornEvent

# ranges of temporal args
ranges = {
	'second'  : range(60),
	'minute'  : range(60),
	'hour'    : range(24),
	'day'     : range(1,32),
	'month'   : range(12),
	'year'    : range(1, 2038),
	'week_day': range(7) # 0 is monday
}
days = {
	'0': _('Monday'),
	'1': _('Tuesday'),
	'2': _('Wednesday'),
	'3': _('Thrusday'),
	'4': _('Friday'),
	'5': _('Satursday'),
	'6': _('Sunday'),
	'*': _('ALL')
}

class Task(CoreStoredObject):
	"""
		Create a new Task object.

		This class provide method to validate and schedule the task.

		:backend:  backend of the task (for the moment the unique backend for task is the file definied in the Licorn setting)
		:name:     name of the task
		:action:   action assigned to the task

		:year, month, day, hour, minute, second, week_day: temporal arguments defining occurences of the task
		:delay_until_year, delay_until_month, delay_until_day, delay_until_hour, delay_until_minute, delay_until_second:
			delay the first occurence of the task.

		:args: args of the action
		:kwargs: kwargs of the action

		:defer_resolution: if True, the args resolution will be done just before task execution, else during task load, only the first time.

	"""

	# from upper class, manage what to drop during Pyro pickle
	_lpickle_ = {
		'to_drop': [
				'thread', 'action_func'
			]
		}

	by_name = {}

	def __init__(self, backend, name, action, year, month, day, hour, minute,
		second,	week_day, delay_until_year, delay_until_month, delay_until_day,
		delay_until_hour, delay_until_minute, delay_until_second,
		defer_resolution, args, kwargs, *our_args, **our_kwargs):
		""" init the new task object """

		super(Task, self).__init__(backend=backend, controller=LMC.tasks)

		self.id       = LMC.tasks.get_next_unset_id()

		# name of the task
		self.name   = name
		# action assigned to the task
		self.action = action

		# temporal argument, defined occurence of the task
		self.year   = year
		self.month  = month
		self.day    = day
		self.hour   = hour
		self.minute = minute
		self.second = second

		self.week_day = week_day

		self.delay_until_year   = delay_until_year
		self.delay_until_month  = delay_until_month
		self.delay_until_day    = delay_until_day
		self.delay_until_hour   = delay_until_hour
		self.delay_until_minute = delay_until_minute
		self.delay_until_second = delay_until_second

		self.backend = backend

		self.defer_resolution = defer_resolution

		# always keep args and kwargs to be able to resolve them again
		self.args            = args
		self.kwargs          = kwargs
		self.resolved_args   = None
		self.resolved_kwargs = None

		# if not defer_resolution, resolve it now
		if not self.defer_resolution:
			self.resolve_parameters()

		# our job thread
		self.thread   = None

		self.nb_of_run = 0
		self.checked   = False
		self.scheduled = False
		self.next_running_time = None

		self.neg_to_exclude = []

		self.__class__.by_name[self.name] = self.weakref

	def __del__(self):
		if self.__class__.by_name[self.name] == self.weakref:
			del self.__class__.by_name[self.name]

	def resolve_parameters(self):
		"""
		Resolve the args and kwargs parameters.

		Never modify 'args' and 'kwargs', use 'resolved_args' and
		'resolved_kwargs' in order to be able to resolve them again at another
		time.
		"""
		_args = []
		for a in self.args:
			try:
				_args.append(eval(a))

			except KeyError, e:
				logging.notice(_(u'{0}: arg {1} cannot be resolved, (error: '
					u'{2}), you may want to defer the action parameters '
					u'resolution using the {3} option.').format(
						self.pretty_name, stylize(ST_ATTR, a),
						stylize(ST_ERROR, e),
						stylize(ST_COMMENT, 'defer_resolution')))

			except Exception, e:
				logging.exception(_(u'Exception while evaluating "{0}"'), a)
				_args.append(a)

		_kwargs = {}
		for k, v in self.kwargs.iteritems():
			try:
				_kwargs.update({k: eval(v)})

			except Exception, e:
				logging.exception(_(u'Exception while evaluating "{0}"'), v)
				_kwargs.update({k: v})

		# save them
		self.resolved_args, self.resolved_kwargs = _args, _kwargs
	def _cli_get(self, long_output=False, no_colors=False):
		""" Command Line Interface get task output """

		def format_time_args():
			return stylize(ST_EMPTY, u', '.join(
					u'{0}={1}'.format(_(arg), getattr(self, arg))
						for arg in (u'year', u'month', u'day', u'hour',
									u'minute', u'second', u'week_day',
									u'delay_until_year', u'delay_until_month',
									u'delay_until_day', u'delay_until_hour',
									u'delay_until_minute', u'delay_until_second')
							if getattr(self, arg) != None
					))

		def format_next_run():
			if self.thread.is_alive():
				return _(u"next @{0} {1}").format(
							self.next_running_time,
							stylize(ST_EMPTY, _(u'(in %s)')
									% pyutils.format_time_delta(
										self.thread.remaining_time(),
										long_output=False)
								)
						)
			else:
				return stylize(ST_BAD, _(u'Operation thread is down.'))

		# WARNING: we use ''' for \n and \t readability.
		return _(u'''{id}: {name}, {counter}, {next}
			{action}({args}{comma}{kwargs}) {defer}
			{time}''').format(
						id=self.id,
						name=stylize(ST_NAME, self.name),
						action=stylize(ST_COMMENT, self.action),
						args=u', '.join([str(a) for a in self.args ]),
						comma=u', ' if (self.args != [] and self.kwargs != {}) else u'',
						kwargs=u', '.join([ u'{0}={1}'.format(k, v)
							for k, v in self.kwargs.iteritems()]),
						defer=stylize(ST_EMPTY, _(u' ({0})').format(
								_(u'with deferred resolution')
							)) if self.defer_resolution else u'',
						time=format_time_args(),
						next=format_next_run(),
						counter=_(u'ran {0} time(s)').format(
							stylize(ST_SPECIAL, self.nb_of_run))
					)

	def serialize(self, backend_action=None):
		""" Save task data to backend. """
		if backend_action == None:
			backend_action = backend_actions.UPDATE

		with self.lock:
			self.backend.save_Task(self)
	def move_to_backend(self, new_backend, force=False,
		internal_operation=False):
		""" move_to_backend is not yet implemented for Task """
		raise NotImplementedError
	def execute(self):
		""" This is the function that the thread will call when executing the
		 task """

		# resolve parameters now if needed:
		if self.defer_resolution:
			self.resolve_parameters()

		# we need to execute it
		self.nb_of_run += 1
		workers.service_enqueue(priorities.NORMAL, self.action_func,
			*self.resolved_args, **self.resolved_kwargs)

		# try to reschedule it
		self.schedule(rescheduling=True)

	def json_dump(self):
		""" return task as JSON in order to save it. """
		# Do not record unserializable object like function instance or thread
		return {
			"name"     : self.name,
			"action"   : self.action,

			"year"     : self.year,
			"month"    : self.month,
			"day"      : self.day,
			"week_day" : self.week_day,
			"hour"     : self.hour,
			"minute"   : self.minute,
			"second"   : self.second,

			"delay_until_year"   : self.delay_until_year,
			"delay_until_month"  : self.delay_until_month,
			"delay_until_day"    : self.delay_until_day,
			"delay_until_hour"   : self.delay_until_hour,
			"delay_until_minute" : self.delay_until_minute,
			"delay_until_second" : self.delay_until_second,

			"args"     : self.args,
			"kwargs"   : self.kwargs,

			"defer_resolution" : self.defer_resolution
		}

	def get_next_running_date(self, now=None):
		""" return the date of the next task's occurence """
		if now is None:
			now = datetime.now()

		for d in self.get_running_dates():
			if d > now:
				return d
	def get_running_dates(self, now=None):
		""" generator yield next task occurence.
		This function massively used the ``rrule`` function from the ``dateutil``
		package.
		"""

		# We use the rrule function from the python-dateutil package.
		# Prepare its kwargs dict.
		kwargs_rrule = {}

		if now is None:
			now = datetime.now()

		# rrule internal kwargs
		rrule_kwargs = {
			'second'   : 'bysecond',
			'minute'   : 'byminute',
			'hour'     : 'byhour',
			'day'      : 'bymonthday',
			'week_day' : 'byweekday',
			'month'    : 'bymonth',
			'year'     : 'byyear'
		}

		def check_for_exclusion(arg, kwargs):
			""" check exclusion X^[x[,y[...]]], return X and the kwargs dict
				containing only not excluded value.

				:arg: name of the argument to check
				:kwargs: kwargs dict to use """

			_arg = getattr(self, arg)

			try:
				if '^' in _arg:
					s = _arg.split('^')
					return_arg = s[0]
					to_exclude = [ int(a) for a in s[1].split(',') ]

					# check for negativ argument, they will be excluded before
					# yielding
					for i, a in enumerate(to_exclude):
						if a < 0:
							if arg == 'day':
								self.neg_to_exclude.append(a)
								del to_exclude[i]

					# update the rrule's kwargs
					kwargs.update({ rrule_kwargs[arg]: [ t
									for t in ranges[arg]
										if t not in to_exclude ] })

					return return_arg, kwargs

				# if no excape chars in arg, return it untouched
				else:
					return _arg, kwargs

			except:
				logging.warning(_(u'Error while checking argument "{0}" '
									u'against {1}:').format(_arg, kwargs))
				raise


		args = ['year', 'month', 'day', 'hour', 'minute', 'second', 'week_day']
		for arg in args:
			# resolve the argument
			_arg = getattr(self, arg)

			if _arg != None:
				_arg=str(_arg)
				if _arg == '*':
					# do nothing default mode in rrule
					pass
				elif _arg.startswith('*') and _arg[1]=="^":
					# exclusion
					_arg, kwargs_rrule = check_for_exclusion(arg, kwargs_rrule)

				elif str(_arg).startswith('*') and _arg[1]=="/":
					#INTERVAL
					_arg, kwargs_rrule = check_for_exclusion(arg, kwargs_rrule)

					interval = int(_arg[2:])

					possibilities = kwargs_rrule[rrule_kwargs[arg]] if \
						kwargs_rrule.has_key(rrule_kwargs[arg]) else ranges[arg]

					kwargs_rrule[rrule_kwargs[arg]] = \
						[ a for a in possibilities if (a%interval)==0 ]

				elif ':' in _arg:
					#PERIOD
					_arg, kwargs_rrule = check_for_exclusion(arg, kwargs_rrule)

					s = _arg.split(':')

					possibilities = kwargs_rrule[rrule_kwargs[arg]] if \
						kwargs_rrule.has_key(rrule_kwargs[arg]) else ranges[arg]

					# increment the 2nd arg in order to include it too
					period = [ t for t in possibilities if t in range(int(s[0]),
						int(s[1])+1)]
					kwargs_rrule.update({ rrule_kwargs[arg]: period})

				else:
					#SEVERAL
					_arg, kwargs_rrule = check_for_exclusion(arg, kwargs_rrule)

					possibilities = kwargs_rrule[rrule_kwargs[arg]] if \
						kwargs_rrule.has_key(rrule_kwargs[arg]) else ranges[arg]

					several = [int(a) for a in _arg.split(',')]

					match=[]
					for t in several:
						# if negativ value, add it
						if str(t)[0]=='-':
							match.append(int(t))

						# else if it is possible
						elif t in possibilities:
								match.append(int(t))

					kwargs_rrule.update({ rrule_kwargs[arg]: match})

		# 'byyear' does not exist for rrule, we have to manage it with 'dtstart'
		# argument.
		dtstart = None
		years   = None
		if kwargs_rrule.has_key('byyear'):
			years = [ y for y in kwargs_rrule["byyear"] if y >= datetime.now().year ]

			ref = datetime(year=min(years), month=1, day=1)
			if ref > now:
				dtstart=ref
			del kwargs_rrule["byyear"]

		# finally check delay_until_* and modify the dtstart if necessary
		delta = relativedelta()

		if self.delay_until_year != None:
			year_ref = int(kwargs_rrule['dtstart'].year) \
				if kwargs_rrule.has_key('dtstart') else now.year

			delta += relativedelta(years=+(int(self.delay_until_year)-year_ref))

		if self.delay_until_month != None:
			month_ref = int(kwargs_rrule['dtstart'].month) \
				if kwargs_rrule.has_key('dtstart') else now.month

			delta += relativedelta(months=(int(self.delay_until_month)-month_ref))

		if self.delay_until_day != None:
			day_ref = int(kwargs_rrule['dtstart'].day) \
				if kwargs_rrule.has_key('dtstart') else now.day

			delta += relativedelta(days=(int(self.delay_until_day)-day_ref))

		if self.delay_until_hour != None:
			hour_ref = int(kwargs_rrule['dtstart'].hour) \
				if kwargs_rrule.has_key('dtstart') else now.hour

			delta += relativedelta(hours=(int(self.delay_until_hour)-hour_ref))

		if self.delay_until_minute != None:
			minute_ref = int(kwargs_rrule['dtstart'].minute) \
				if kwargs_rrule.has_key('dtstart') else now.minute

			delta += relativedelta(minutes=(int(self.delay_until_minute)-minute_ref))

		if self.delay_until_second != None:
			second_ref = int(kwargs_rrule['dtstart'].second) \
				if kwargs_rrule.has_key('dtstart') else now.second

			delta += relativedelta(seconds=(int(self.delay_until_second)-second_ref))

		if delta != relativedelta():
			dtstart = now + delta

		else:
			if dtstart == None:
				dtstart = now

		kwargs_rrule['dtstart'] = dtstart

		# deal with rrule_freq
		freq_rrule = YEARLY

		if self.month=='*':
			freq_rrule = MONTHLY

		if self.day=='*':
			freq_rrule = DAILY

		if self.hour=="*":
			freq_rrule = HOURLY

		if self.minute == '*':
			freq_rrule = MINUTELY

		if self.second == '*':
			freq_rrule = SECONDLY

		for d in rrule(freq_rrule, **kwargs_rrule):
			# special treatment for 'year' because rrule does not manage it
			if years != None:
				if d.year not in years:
					continue

			# special treatment for negativ exclude:
			skipped     = []
			month_range = max(calendar.monthrange(d.year, d.month))

			for i in self.neg_to_exclude:
				skipped.append(month_range + i + 1)

			if not d.day in skipped:
				yield d
	def schedule(self, rescheduling=False, test=False, now=None):
		""" schedule or reschedule a task """
		if now == None:
			now = datetime.now()

		# get the next running date
		running_time = self.get_next_running_date(now=now)

		if test:
			return running_time

		if running_time is None:
			logging.notice(_(u'{0}: {1} for task {2}, un-scheduled.').format(
				self.pretty_name,
				stylize(ST_BAD, _(u"No remaining occurence")),
				stylize(ST_NAME, self.name)))

			if LMC.tasks.by_name(self.name) != None:
				LMC.tasks.del_task(self.id)

			return False

		if running_time > now:
			self.next_running_time = running_time
			job=LicornJobThread(self.execute, tname=self.name,
						time=time.mktime(running_time.timetuple()), count=1)

			if rescheduling:
				self.thread.stop()

			self.thread = job
			self.thread.start()

			self.scheduled = True

		return self.scheduled

	def stop(self):
		self.thread.stop()
		del self.thread

	def validate(self):
		""" task validation mechanism """

		args_to_check = [
			('name', self.name), ('action', self.action), ('year', self.year),
			('month', self.month), ('day', self.day), ('hour', self.hour),
			('minute', self.minute), ('second', self.second),
			('week_day', self.week_day),
			('delay_until_year', self.delay_until_year),
			('delay_until_month', self.delay_until_month),
			('delay_until_day', self.delay_until_day),
			('delay_until_hour', self.delay_until_hour),
			('delay_until_minute', self.delay_until_minute),
			('delay_until_second', self.delay_until_second),
		]

		temporal_args = ['year', 'month', 'day', 'hour',
											'minute', 'second', 'week_day']

		def validate_range(t, arg, can_be_neg=False):
			if arg != 'day':
				# negativ arg only for day argument
				can_be_neg = False

			if can_be_neg:
  				if str(t)[0]=='-':
  					t=str(t)[1:]

  			if int(t) not in ranges[arg]:
  				raise exceptions.BadArgumentError(_(u"{1} on task {0} for "
  					u"argument {2}={5}: should be between {3} and {4}").format(
						stylize(ST_NAME, name),
						stylize(ST_BAD, _(u'Not in range')),
						arg, min(ranges[arg])
							if not can_be_neg
							else '-{0}'.format(max(ranges[arg])),
						max(ranges[arg]), t))

		def validate_exclusion(arg, _arg, can_be_neg=False):
			""" validate exclusion X^x[,y[..]] where x,y are positiv integer"""

			if '^' in str(_arg):
				s          = _arg.split('^')
				return_arg = s[0]
				to_exclude = [ int(a) for a in str(s[1]).split(',') if a != '' ]

				for a in to_exclude:
					validate_range(a, arg, can_be_neg=can_be_neg)

				return return_arg

			else:
				return _arg

		for arg, _arg in args_to_check:
			if _arg == None:
				continue
			# first of all check every type
			if type(_arg) not in (types.StringType, types.NoneType,
				types.IntType, types.UnicodeType):

				raise exceptions.BadArgumentError(_(u"{0} on task {1} for "
					u"argument {2}={3}: excepted type are String, Integer or "
					u"None").format(
						stylize(ST_BAD, _(u"Type error")),
						stylize(ST_NAME, self.name), arg, _arg))

			# if temporal arg, check it carefully
			if arg in temporal_args:
				_arg=str(_arg)
				if _arg == '*':
					continue
				elif str(_arg).startswith('*') and str(_arg)[1] == '/':
					# check exclusion
					_arg = validate_exclusion(arg, _arg, can_be_neg=True)

					# check range
					for t in str(_arg[2:]).split(','):
						if t != '':
							validate_range(t, arg)
				elif str(_arg).startswith('*') and str(_arg)[1] == '^':
					# check exclusion
					_arg = validate_exclusion(arg, _arg, can_be_neg=True)

					# check range
					for t in str(_arg[2:]).split(','):
						if t != '':
							validate_range(t, arg)

				elif ':' in str(_arg):
					# check exclusion
					_arg = validate_exclusion(arg, _arg, can_be_neg=True)

					# check range
					for t in _arg.split(':'):
						validate_range(int(t), arg)

				else:

					_arg = str(_arg)
					# check exclusion
					_arg = validate_exclusion(arg, _arg, can_be_neg=True)
					# check range
					for t in str(_arg).split(','):
						try:
							t = int(t)
						except:
							raise exceptions.BadArgumentError(_(u"{0} on task "
								u"{1} for argument {2}={3} has to "
								u"be an Integer").format( stylize(ST_BAD,
															_(u"Type error")),
									stylize(ST_NAME, self.name), arg, t))

						validate_range(t, arg, can_be_neg=True)

						if arg=='year':
							if int(t) < datetime.now().year:
								raise exceptions.BadArgumentError(_(u"{0} on "
									u"task {1} for argument {2}={3} has to "
									u"be > {4}").format(
										stylize(ST_BAD,	_(u"Argument error")),
										stylize(ST_NAME, self.name), arg, t,
										datetime.now().year))

			# delay_until_* arguments are only int, nothing more
			elif str(arg).startswith('delay_until_'):
				try:
					t = int(_arg)
				except:
					raise exceptions.BadArgumentError(_(u"{1} on task {0} for "
						u"argument {2}={3}: should be transtypable to int").format(
						name, stylize(ST_BAD, _(u'Type Error')),
						arg, _arg))

		# check action
		if type(self.action) not in (types.UnicodeType, types.StringType):
			raise exceptions.BadArgumentError(_(u"{0} on task {1} for argument "
				u"'action'={2} has to be a String").format(
					stylize(ST_BAD, _(u"Type error")),
					stylize(ST_NAME, self.name), self.action))

		# check defer_resolution
		if type(self.defer_resolution) != types.BooleanType:
			raise exceptions.BadArgumentError(_(u"{0} on task {1} for argument "
				u"'defer_resolution'={2} has to be a Boolean").format(
					stylize(ST_BAD, _(u"Type error")),
					stylize(ST_NAME, self.name), self.defer_resolution))
class ExtinctionTask(Task):
	def validate(self):
		super(ExtinctionTask, self).validate()

		if self.hour == '*':
			raise exceptions.BadArgumentError(_(u"{0} on extinction task {1} "
				u"for argument 'hour'={2} has to be a Integer where 0<=hour<60").format(
					stylize(ST_BAD, _(u"BadArgumentError")),
					stylize(ST_NAME, self.name), self.hour))
		if self.minute == '*':
			raise exceptions.BadArgumentError(_(u"{0} on extinction task {1} "
				u"for argument 'minute'={2} has to be a Integer where 0<=minute<60").format(
					stylize(ST_BAD, _(u"BadArgumentError")),
					stylize(ST_NAME, self.name), self.minute))

		if self.week_day is None:
			raise exceptions.BadArgumentError(_(u"{0} on extinction task {1} "
				u"for argument 'week_day'={2} has to be a Integer where 0<=week_day<7").format(
					stylize(ST_BAD, _(u"BadArgumentError")),
					stylize(ST_NAME, self.name), self.week_day))

		# Extinction Task specific tests:
		# We only need to check that a rule of a speficied machine, is only set once by day and hour.
		# eg. we cannot set a rule for the machine '192.168.0.16' twice on monday at 14.
		# but we can set a rule for the machine '192.168.0.16' on monday at 14h and another on monday at 15h.

		our_days = self.week_day.split(',')
		if our_days == ['*']:
			our_days = range(0,7)

		for task in LMC.tasks:
			if isinstance(task, ExtinctionTask):
				same_day     = False
				same_hour    = False
				same_machine = False


				# check day
				for d in our_days:
					if task.week_day == '*':
						same_day = True
						_day = '*'
					else:
						if d in task.week_day.split(','):
							# same day
							same_day = True
							_day = d

				if task.minute == self.minute and task.hour == self.hour:
					same_hour = True
					_hour = '{0}:{1}'.format(task.hour, task.minute)

				# check machines
				for m in task.args:
					if m in self.args:
						same_machine = True
						_machine = m

					if same_machine and same_hour and same_day:
						raise exceptions.BadArgumentError(
							_(u'Another rule already exists for the machine {0} '
								u'on day {1} at {2}, please delete it first.').format(
									_machine,
									days[str(_day) if _day != '*' else '*'],
									_hour))
class TasksController(DictSingleton, CoreController, SelectableController):
	"""
	Task Controler. Manage tasks, add them, delete them.
	"""
	init_ok = False
	load_ok = False

	taskClasses = {
			'LMC.machines.shutdown': pyutils.MixIn(ExtinctionTask, Task),
		}

	# local and specific implementations of SelectableController methods.
	def by_id(self, t_id, strong=True):
		return self[int(t_id)]

	def by_name(self, t_name, strong=True):
		# call weakref to retrun real object
		return Task.by_name[t_name]()

	by_key  = by_id

	# end SelectableController

	def __init__(self, load=True):
		if TasksController.init_ok:
			return

		self.backend = None
		super(TasksController, self).__init__(name='tasks')


		TasksController.init_ok = True

		#self.threads.scheduler = TaskSchedulerThread(self)
		#self.threads.scheduler.start()
		self.threads_by_task_id = {}
		self.threads = []

		#self.load()

		events.collect(self)

	@events.handler_method
	def licornd_cruising(self, *args, **kwargs):
		""" Event handler that will load the controller when
			Licornd is `cruising`, which means “ `everything is ready, boys` ”. """
		self.load()

	def load(self):
		""" Load tasks form different backends """
		if TasksController.load_ok:
			return

		assert ltrace_func(TRACE_TASKS)
		self.reload()

		TasksController.load_ok = True
	def reload(self):
		""" Load (or reload) the data structures from the system data. """

		assert ltrace_func(TRACE_TASKS)

		with self.lock:
			# clear the sched queue
			for t in self.threads:
				t.stop(force=True)
			self.threads = []

			try:
				# reload tasks
				for backend in self.backends:
					backend.load_Tasks()

			except Exception:
				# do not catch the 'unknown file', if there is no config file,
				# it's ok
				#if e.errno != errno.ENOENT:
				logging.exception(_(u'{0}: Exception while reloading '
										u'tasks').format(self.pretty_name))
	def add_task(self, name, action, year=None, month=None, day=None, hour=None,
		minute=None, second=None, week_day=None, delay_until_year=None,
		delay_until_month=None,	delay_until_day=None, delay_until_hour=None,
		delay_until_minute=None, delay_until_second=None, defer_resolution=None,
		args=None, kwargs=None, test=False, load=False):
		""" add a new task into the controller """

		# apply defaults here
		if year is None:
			year   = '*'
		if month is None:
			month  = '*'
		if day is None:
			day    = '*'
		if hour is None:
			hour   = '*'
		if minute is None:
			minute = '*'
		if second is None:
			second = '0'

		if args is None:
			args = []
		if kwargs is None:
			kwargs = {}

		if defer_resolution is None:
			defer_resolution = True
		# end defaults

		# create the task object
		try:
			# Check if task name is unique
			self.by_name(name)
			raise exceptions.AlreadyExistsException(_(u'Another task with the '
												u'same name already exists'))

		# catch only the by_name() KeyError!!
		except KeyError:
			taskClass = TasksController.taskClasses.get(action, Task)

			# instanciate the task object
			task = taskClass(self._prefered_backend, name, action, year=year,
				month=month, day=day, hour=hour, minute=minute, second=second,
				week_day=week_day, delay_until_year=delay_until_year,
				delay_until_month=delay_until_month,
				delay_until_day=delay_until_day,
				delay_until_hour=delay_until_hour,
				delay_until_minute=delay_until_minute,
				delay_until_second=delay_until_second,
				defer_resolution=defer_resolution, args=args, kwargs=kwargs)

			task.validate()

			try:
				LicornEvent('task_pre_add', task=task).emit(synchronous=True)

			except exceptions.LicornStopException, e:
				logging.warning(_(u'{0}: addition prevented: {1}').format(
														self.pretty_name, e))

				# delete the task from the configuration file.
				task.backend.delete_Task(task)
				del task
				return

			self[task.id] = task

			#resolve action
			try:
				task.action_func = pyutils.resolve_attr(task.action, {
											"LMC": LMC, "logging": logging })
			except Exception:
				raise exceptions.BadArgumentError(_(u'{0}: {1} for task {2}: '
								u'{3} argument cannot be resolved.').format(
									self.pretty_name,
									stylize(ST_BAD, _(u"Cannot resolve action")),
									stylize(ST_NAME, self.name),
									stylize(ST_COMMENT, 'action')))

			if task.schedule():
				task.serialize(backend_actions.CREATE)

				task_args = ''
				for arg in ('year', 'month', 'day', 'hour', 'minute', 'second',
					'week_day', 'delay_until_year', 'delay_until_month',
					'delay_until_day', 'delay_until_hour', 'delay_until_minute',
					'delay_until_second'):

					if getattr(task, arg) != None:
						task_args += ' {0}={1}'.format(arg, getattr(task, arg))

				logging.notice(_(u'{0}: scheduling task {1} on {2}: {3}; {4}').format(
								self.pretty_name, stylize(ST_NAME, task.name),
								stylize(ST_COMMENT, task.next_running_time),
								'{0}({1}, {2})'.format(task.action,
														task.args,
														task.kwargs),
								task_args))

				if isinstance(task, ExtinctionTask):
					LicornEvent('task_extinction_added', task=task).emit(priorities.LOW)

				# forward the good news
				LicornEvent('task_added', task=task).emit(priorities.LOW)

			return task
	def get_next_unset_id(self):
		# TODO: use settings.core.tasks.max_tasks
		return pyutils.next_free(self.keys(), 0, 65535)
	def del_task(self, task_id):
		# if the task exists
		task = self.by_id(task_id)

		if task != None:

			try:
				LicornEvent('task_pre_del', task=task).emit(synchronous=True)

			except exceptions.LicornStopException, e:
				logging.warning(_(u'{0}: deletion prevented: {1}').format(
														self.pretty_name, e))
				return

			name = task.name

			# cancel it from the scheduler
			task.stop()

			# del its reference
			del self[task.id].__class__.by_name[task.name]
			del self[task.id]

			# del it from the config
			task.backend.delete_Task(task)

			logging.notice(_('{0}: task {1} unscheduled and {2}.').format(
											self.pretty_name,
											stylize(ST_NAME, task.name),
											stylize(ST_BAD, _(u'removed'))))

			was_instance = isinstance(task, ExtinctionTask)

			del task

			if was_instance:
				LicornEvent('task_extinction_deleted', name=name).emit(priorities.LOW)

			LicornEvent('task_deleted', name=name).emit(priorities.LOW)

		# checkpoint!
		gc.collect()
	def dump_status(self, long_output=False, precision=None,
		as_string=True, cli_output=True, *args, **kwargs):

		if as_string:
			desc = _(u"Scheduler threads:")
			for task in self.values():
				desc += _(u'\n\t{0} (id: {1}): {2} > {3}(args={4}, kwargs={5})').format(
					stylize(ST_NAME,task.name), task.id,
					_(u'next in %s ') % pyutils.format_time_delta(
						task.thread.remaining_time())
							if time != 0
							 else _(u'Currently running'),
					task.action, task.args, task.kwargs)

			return desc


	# used in `RWI.select()`
	@property
	def object_type_str(self):
		return _(u'task')
	@property
	def object_id_str(self):
		return _(u'id')
	@property
	def sort_key(self):
		""" The key (attribute or property) used to sort
			User objects from RWI.select(). """
		return 'name'
	# end
	def select(self, filter_string=filters.ALL):
		""" Filter tasks on different criteria."""
		with self.lock:
			if filters.ALL == filter_string:
				filtered_tasks = self.values()
			elif filter_string == filters.EXTINCTION_TASK:
				filtered_tasks = []
				for task in self.values():
					if isinstance(task, ExtinctionTask):
						 filtered_tasks.append(task)
			else:
				filtered_tasks = []
				for t in self.values():
					if t.id == filter_string:
						filtered_tasks.append(t)

			return filtered_tasks
	def to_script(self, selected=None, script_format=None, script_separator=None):
		""" Export the user accounts list to XML. """

		with self.lock:
			if selected is None:
				tasks = self
			else:
				tasks = selected

		return script_separator.join(script_format.format(task=task, t=task,
												self=task) for task in tasks)
	def _cli_get(self, selected=None, long_output=False, no_colors=False):
		""" Export the tasks list to human readable form. """

		with self.lock:

			if selected is None:
				tasks = self.values()
			else:
				tasks = selected

			tasks.sort()

			assert ltrace_func(TRACE_TASKS)

			# FIXME: forward long_output, or remove it.
			return u'\n'.join((task._cli_get() for task
							in sorted(tasks, key=attrgetter('id')))) + u'\n'

