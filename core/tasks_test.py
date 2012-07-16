# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

TaskController test - testsuite for TasksController

:copyright:
	* 2012 Robin Lucbernet <robinlucbernet@gmail.com>
:license: GNU GPL version 2
"""

import os, stat, py.test, time, types, calendar

from datetime       import datetime, timedelta
from dateutil.rrule import *
from dateutil.relativedelta import *
from licorn.foundations        import logging, exceptions, process, fsapi
from licorn.foundations.ltrace import lprint

from licorn.core       import LMC
from licorn.core.tasks import TasksController, Task

def tasks(method_name, *args, **kwargs):
	try:
		return LMC.rwi.generic_controller_method_call('tasks', method_name, *args, **kwargs)

	except AttributeError, e:
		LMC.connect()
		return LMC.rwi.generic_controller_method_call('tasks', method_name, *args, **kwargs)

def test_schedule():
	pass

def test1():
	# TASK 1 - every day in January at 12
	tasks('add_task', 'test1', 'logging.notice', month='1', hour='12', minute='0')
	task = tasks('by_name', 'test1')

	_first_event = datetime(2013, 1, 1, 12, 0)
	assert _first_event == task.schedule(test=True)

	_second_event = datetime(2013, 1, 2, 12, 0)
	assert _second_event == task.schedule(test=True, now=_first_event)

	tasks('del_task', task.id)

def test2():
	# TASK 2
	# period : every minute in January at 12 hour
	tasks('add_task', 'test2', 'logging.notice', month='1', hour='12', minute='*')
	task = tasks('by_name', 'test2')

	_first_event = datetime(2013, 1, 1, 12, 0)
	assert _first_event == task.schedule(test=True)

	_second_event = datetime(2013, 1, 1, 12, 1)
	assert _second_event == task.schedule(test=True, now=_first_event)

	_third_event = datetime(2013, 1, 1, 12, 2)
	assert _third_event == task.schedule(test=True, now=_second_event)

	tasks('del_task', task.id)

def test3():
	now = datetime.now()
	# TASK 3
	# every day at 23h30 : add task --minute 30 --hour 23
	tasks('add_task', 'test3', 'logging.notice', hour='23', minute='30')
	task = tasks('by_name', 'test3')

	_first_event = datetime(now.year, now.month, now.day, 23, 30)
	if _first_event < now:
		_first_event = _first_event + timedelta(days=1)
	assert _first_event == task.schedule(test=True)

	_second_event = _first_event + timedelta(days=1)
	assert _second_event == task.schedule(test=True, now=_first_event)

	_third_event = _second_event + timedelta(days=1)
	assert _third_event == task.schedule(test=True, now=_second_event)

	tasks('del_task', task.id)


def test4():
	now = datetime.now()
	# TASK 4 : Every hour, at minute 5
	# add task --minute 5
	tasks('add_task', 'test4', 'logging.notice', minute='5')
	task = tasks('by_name', 'test4')

	if now.minute > 5:
		#next hour
		_first_event = datetime(now.year, now.month, now.day, now.hour+1, 5)
	else:
		# this hour
		_first_event = datetime(now.year, now.month, now.day, now.hour, 5)

	assert _first_event == task.schedule(test=True)

	_second_event = _first_event + timedelta(hours=1)
	assert _second_event == task.schedule(test=True, now=_first_event)

	_third_event = _second_event + timedelta(hours=1)
	assert _third_event == task.schedule(test=True, now=_second_event)

	tasks('del_task', task.id)

def test5():
	now = datetime.now()
	# TASK 5 - Every first day of month at 23h30:
	# add task --minute 30 --hour 23 --day 1
	tasks('add_task', 'test5', 'logging.notice', day='1', hour='23', minute='30')
	task = tasks('by_name', 'test5')

	times=list(rrule(MONTHLY, bymonthday=1, byhour=23, byminute=30, count=3, bysecond=0, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test6():
	now = datetime.now()
	# TASK 6 - Every Monday at 22h28
	#	add task --minute 28 --hour 22 --week-day 1
	tasks('add_task', 'test6', 'logging.notice', week_day='0', hour='22', minute='28')
	task = tasks('by_name', 'test6')
	interval = 7 - now.weekday()

	if now.weekday() == 0 and now.hour <= 22:
		# this is today !
		_first_event = datetime(now.year, now.month, now.day, 22, 28)
	else:
		# nextweek
		_first_event = datetime(now.year, now.month, now.day, 22, 28) + timedelta(days=interval)
	assert _first_event == task.schedule(test=True)

	_second_event = _first_event + timedelta(days=7)
	assert _second_event == task.schedule(test=True, now=_first_event)

	_third_event = _second_event + timedelta(days=7)
	assert _third_event == task.schedule(test=True, now=_second_event)

	tasks('del_task', task.id)

def test7():
	now = datetime.now()
	# TASK 7 - Every friday 13 at 11h22 :
	#	add task --minute 22 --hour 11 --day 13 --weekday 4
	tasks('add_task', 'test7', 'logging.notice', week_day='4', day='13', hour='11', minute='22')
	task = tasks('by_name', 'test7')

	times=list(rrule(WEEKLY, byweekday=4, bymonthday=13, byhour=11, byminute=22, count=3, bysecond=0, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test8():
	now = datetime.now()
	# TASK 8 : From day 2 to day 5, each month at 10h12 :
	#	add task --minute 12 --hour 10 --day 2:5"""
	tasks('add_task', 'test8', 'logging.notice', day='2:5', hour='10', minute='12')
	task = tasks('by_name', 'test8')

	times=list(rrule(WEEKLY, bymonthday=range(2,6), byhour=10, byminute=12, count=3, bysecond=0, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test9():
	now = datetime.now()
	# TASK 9 : From day 2 to day 5, each month at 10h12, EVERY SECOND :
	#	add task --minute 12 --hour 10 --day 2:5"""
	tasks('add_task', 'test9', 'logging.notice', day='2:5', hour='10', minute='12', second='*')
	task = tasks('by_name', 'test9')

	times=list(rrule(WEEKLY, bymonthday=range(2,6), byhour=10, byminute=12,
								count=3, bysecond=range(0, 60), dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test10():
	now = datetime.now()
	# TASK 10 : Every day multiple of 2 at 23h59 :
	#	add task --minute 59 --hour 23 --day */2
	tasks('add_task', 'test10', 'logging.notice', day='*/2', hour='23', minute='59')
	task = tasks('by_name', 'test10')

	times=list(rrule(DAILY, bymonthday= [ d for d in range(1,32) if d % 2 == 0 ],
		byhour=23, byminute=59, count=3, bysecond=0, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test11():
	now = datetime.now()
	# TASK 11 : Every weekday at 22h :
	# 	add task --hour 22 --weekday 0:4 --minute 0
	tasks('add_task', 'test11', 'logging.notice', week_day='0:4', hour='22', minute='0')
	task = tasks('by_name', 'test11')

	times=list(rrule(DAILY, byweekday= range(5), byhour=22, byminute=0,
										count=3, bysecond=0, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test12():
	now = datetime.now()
	# TASK 12 : Every 5 minutes :
	#	add task --minute */5
	tasks('add_task', 'test12', 'logging.notice', minute='*/5')
	task = tasks('by_name', 'test12')

	times=list(rrule(MINUTELY, byminute=[ d for d in range(60) if d % 5 == 0 ],
											bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test13():
	now = datetime.now()
	# TASK 13 : Every last day of the month, at midnight :
	#	add task --day -1 --hour 0 --minute 0
	tasks('add_task', 'test13', 'logging.notice', day='-1', hour='0', minute='0')
	task = tasks('by_name', 'test13')

	times=list(rrule(DAILY, bymonthday=-1, byhour=0, byminute=0, bysecond=0,
					count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test14():
	now = datetime.now()
	# TASK 14 : every last day of month if its a sunday, midnight :
	#	add task --weekday -1 --day -1
	tasks('add_task', 'test14', 'logging.notice', week_day='6', day='-1',
													hour='0', minute='0')
	task = tasks('by_name', 'test14')

	times=list(rrule(DAILY, byweekday=6, bymonthday=-1, byhour=0, byminute=0,
					bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test15():
	now = datetime.now()
	# TASK 15 : every last satursday of the month, midnight
	#	add task --weekday 5 --day 26,27,28,29,30,31
	tasks('add_task', 'test15', 'logging.notice', week_day='5',
						day='26,27,28,29,30,31', hour='0', minute='0')
	task = tasks('by_name', 'test15')

	times=list(rrule(DAILY, byweekday=5, bymonthday=[26,27,28,29,30,31],
				byhour=0, byminute=0, bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test16():
	now = datetime.now()
	# TASK 16 : tous les jours à minuit à partir du 15 février 2014
	#	add task --minute 0 --hour 00 --delay-until-year 2014 --delay-until-day 15 --delay-until-month 02 --delay-until-hour 0 --delay-until-minute 0
	tasks('add_task', 'test16', 'logging.notice', delay_until_year='2014',
								delay_until_day='15', delay_until_month='2',
								delay_until_hour='0', delay_until_minute='0',
								delay_until_second='0', hour='0', minute='0')
	task = tasks('by_name', 'test16')

	dtstart=datetime(year=2014, month=2, day=15)

	times=list(rrule(DAILY, bymonthday=range(60), byhour=0, byminute=0,
								bysecond=0, count=3, dtstart=dtstart))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test161():
	now = datetime.now()
	# TASK 16 : toutes les minutes à partir du 15 février 2014 (13:37, 30 sec) => donc a partir de 13:38
	#	add task --minute * --delay-until-year 2014 --delay-until-day 15 --delay-until-month 02

	tasks('add_task', 'test161', 'logging.notice', delay_until_year='2014',
			delay_until_day='15', delay_until_month='2', delay_until_hour='13',
			delay_until_minute='37', delay_until_second="31", minute='*')
	task = tasks('by_name', 'test161')

	dtstart=datetime(year=2014, month=2, day=15, hour=13, minute=37, second=30)

	times=list(rrule(MINUTELY, bysecond=0, count=3, dtstart=dtstart))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)


def test17():
	now = datetime.now()
	# TASK 17 : toutes les heures, à 'xx:42'
	# 	add task -m 42
	tasks('add_task', 'test17', 'logging.notice', minute='42')
	task = tasks('by_name', 'test17')

	times=list(rrule(HOURLY, byminute=42, bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test18():
	now = datetime.now()
	# TASK 18 : toutes les 15 minutes à partir de maintenant
	# 	add task -m */15
	tasks('add_task', 'test18', 'logging.notice', minute='*/15')
	task = tasks('by_name', 'test18')

	times=list(rrule(HOURLY, byminute=[ d for d in range(60) if d%15==0 ],
										bysecond=0, count=5, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])
	assert times[3] == task.schedule(test=True, now=times[2])
	assert times[4] == task.schedule(test=True, now=times[3])

	tasks('del_task', task.id)

def test19():
	now = datetime.now()
	# TASK 19 : tous les jours du mois de juillet à 13h37
	# 	add task -M 7 -h 13 -m 37
	tasks('add_task', 'test19', 'logging.notice', month='7', hour='13', minute='37')
	task = tasks('by_name', 'test19')

	times=list(rrule(HOURLY, bymonth=7, byhour=13, byminute=37, bysecond=0,
						count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test20():
	now = datetime.now()
	# TASK 20 : tous les jours du mois de juillet, toutes les 15 minutes
	# 	add task -M 7 -m */15
	tasks('add_task', 'test20', 'logging.notice', month='7', minute='*/15')
	task = tasks('by_name', 'test20')

	times=list(rrule(HOURLY, bymonth=7,
		byminute=[ d for d in range(60) if d % 15 == 0 ], bysecond=0, count=3,
		dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test21():
	# TASK 21 :	le 27 janvier 2013, toutes les 15 minutes
	# add task -y 2013 -M 1 -d 27 -m */15
	tasks('add_task', 'test21', 'logging.notice', year='2013', month='1',
												day='27', minute='*/15')
	task = tasks('by_name', 'test21')

	times=list(rrule(HOURLY, bymonthday=27, bymonth=1,
		byminute=[ d for d in range(60) if d % 15 == 0 ], bysecond=0, count=3,
		dtstart=datetime(2013,1, 1)))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])
	tasks('del_task', task.id)

def test211():
	# TASK 21 :	le 27 janvier 2014, toutes les 15 minutes
	# add task -y 2013 -M 1 -d 27 -m */15
	tasks('add_task', 'test211', 'logging.notice', year='2014', month='1',
													day='27', minute='*/15')
	task = tasks('by_name', 'test211')

	times=list(rrule(HOURLY, bymonthday=27, bymonth=1,
		byminute=[ d for d in range(60) if d%15==0 ], bysecond=0, count=3,
		dtstart=datetime(2014,1, 1)))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test22():
	now = datetime.now()
	# TASK 22 : tous les mois, l'avant-dernier jour du mois
	# 	add task -d -2
	tasks('add_task', 'test22', 'logging.notice', day='-2', hour='0', minute='0')
	task = tasks('by_name', 'test22')

	times=list(rrule(HOURLY, bymonthday=-2, byhour=0, byminute=0, bysecond=0,
														count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test23():
	now = datetime.now()
	# TASK 23 : tous les mois, le 15 et le dernier jour du mois
	#	add task -d 15,-1
	tasks('add_task', 'test23', 'logging.notice', day='-1,15', hour='0', minute='0')
	task = tasks('by_name', 'test23')

	times=list(rrule(DAILY, bymonthday=[-1,15], byhour=0, byminute=0,
					bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test24():
	now = datetime.now()
	# TASK 24 : tous les mois, les jours pairs
	#	add task -d */2
	tasks('add_task', 'test24', 'logging.notice', day='*/2', hour='0', minute='0')
	task = tasks('by_name', 'test24')

	times=list(rrule(HOURLY, bymonthday=[ d for d in range(31) if d %2 == 0 ],
				byhour=0, byminute=0, bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test25():
	now = datetime.now()
	# TASK 25 : toutes les semaines, le mercredi et le vendredi
	# 	add task --week-day 2,4
	tasks('add_task', 'test25', 'logging.notice', week_day='2,4', hour='0', minute='0')
	task = tasks('by_name', 'test25')

	times=list(rrule(HOURLY, byweekday=[ 2,4 ], byhour=0, byminute=0,
						bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])
	tasks('del_task', task.id)

def test26():
	# TASK 26 : le 27 Janvier 2013 à 13h33 uniquement.
	#	add task -y 2013 -M 1 -d 27 -h 13 -m 33
	tasks('add_task', 'test26', 'logging.notice', year='2013', month='1',
										day='27', hour='13', minute='33')
	task = tasks('by_name', 'test26')

	times=list(rrule(YEARLY, bymonth=1, bymonthday=27, byhour=13, byminute=33,
				bysecond=0, count=3, dtstart=datetime(2013, 1, 1)))

	assert times[0] == task.schedule(test=True)
	assert None == task.schedule(test=True, now=times[0])

	tasks('del_task', task.id)

def test27():
	now = datetime.now()
	# TASK 27 : tous les jours mais pas le 13
	#	add task -d *^13
	tasks('add_task', 'test27', 'logging.notice', day='*^13', hour='0', minute='0')
	task = tasks('by_name', 'test27')

	times=list(rrule(DAILY, bymonthday=[d for d in range(31) if d!=13],
				byhour=0, byminute=0, bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test28():
	now = datetime.now()
	# TASK 28 : tous les jours mais pas le 13, le 20 et le 22
	#	add task -d *^13,20,22
	tasks('add_task', 'test28', 'logging.notice', day='*^13,20,22', hour='0', minute='0')
	task = tasks('by_name', 'test28')

	times=list(rrule(DAILY,
		bymonthday=[d for d in range(31) if d not in (13, 20, 22)], byhour=0,
		byminute=0, bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test29():
	now = datetime.now()
	# TASK 29 : tous les jours mais pas le vendredis
	#	add task -weekday *^4
	tasks('add_task', 'test29', 'logging.notice', week_day='*^4', hour='0', minute='0')
	task = tasks('by_name', 'test29')

	times=list(rrule(DAILY, byweekday=[d for d in range(7) if d != 4], byhour=0,
								byminute=0, bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test30():
	pass
	# TASK 30 : demain a 13h37
	# add task -d +1 -h 13 -m 37
	#tasks('add_task', 'test30', 'logging.notice', day='+1', hour='13', minute='37')
	#task = tasks('by_name', 'test30')

	#times=list(rrule(DAILY, bymonthday=now.day+1, byhour=13, byminute=37, bysecond=0, count=3, dtstart=now))

	#assert times[0] == task.schedule(test=True)
	#assert None == task.schedule(test=True, now=times[0])
	#tasks('del_task', task.id)


def test31():
	""" check interval task """
	# interval every 30 minute :
	now = datetime.now()
	tasks('add_task', 'test31', 'logging.notice', minute='*/30')
	task = tasks('by_name', 'test31')

	times=list(rrule(MINUTELY, byminute=[0,30], bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

	# interval 45 minute, must not trigger at "0" min
	tasks('add_task', 'test31bis', 'logging.notice', minute='*/45')
	task = tasks('by_name', 'test31bis')

	times=list(rrule(MINUTELY, byminute=[0,45], bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

def test_exclusion():
	# in interval
	now = datetime.now()
	tasks('add_task', 'test32', 'logging.notice', minute='*/15^30')
	task = tasks('by_name', 'test32')

	times=list(rrule(MINUTELY, byminute=[0,15,45], bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

	# in period
	tasks('add_task', 'test33', 'logging.notice', minute='29:31^30')
	task = tasks('by_name', 'test33')

	times=list(rrule(MINUTELY, byminute=[29,31], bysecond=0, count=3, dtstart=now))

	assert times[0] == task.schedule(test=True)
	assert times[1] == task.schedule(test=True, now=times[0])
	assert times[2] == task.schedule(test=True, now=times[1])

	tasks('del_task', task.id)

	# in every
	tasks('add_task', 'test34', 'logging.notice', minute='*^1,2,4')
	task = tasks('by_name', 'test34')

	times=list(rrule(MINUTELY,
					byminute=[ t for t in range(60) if t not in (1,2,4)],
					bysecond=0, count=10, dtstart=now))

	i = 1
	assert times[0] == task.schedule(test=True)	
	while i < 10:
		assert times[i] == task.schedule(test=True, now=times[i-1])
		i+=1

	tasks('del_task', task.id)

#def test_single():
#	now = datetime.now()
#	tasks('add_task', 'test35', 'logging.notice', year=now.year+1, day=16, month=9, hour=0, minute='0')
#	task = tasks('by_name', 'test35')
#	until = now + relativedelta(years=+2)
#	times=list(rrule(YEARLY, bymonth=9, bymonthday=16, byhour=0, byminute=0, bysecond=0, count=3, dtstart=now, until=until))
#	print times
#	assert times[0] == task.schedule(test=True)
#	assert times[1] == task.schedule(test=True, now=times[0])
#	assert times[2] == task.schedule(test=True, now=times[1])


"""def test_massive():
	now = datetime.now()

	nb_count=50

	test_rule = {
		'year'   : '*',
		'month'  : 1,
		'day'    : 1,
		'hour'   : 0,
		'minute' : 0,
		'second' : 0,	
	}
	def get_none_result(n):
		i=0
		ret = []
		while i < n:
			ret.append(None)
			i+=1
		return ret
	def every_n_year_1_january_midnight(n, ex=[]):
		every_n_year_1_january_midnight = []
		for d in range(2013, 2038):
			if d%n==0 and d not in ex:
				every_n_year_1_january_midnight.append(datetime(year=d, month=1, day=1, hour=0, minute=0, second=0))

		return every_n_year_1_january_midnight
	def get_range(r, n, ex):
		ret = [ d for d in range(r) if (d%n==0 and d not in ex)]
		return ret
	def result_star_slash(n, ex=[]):
		neg = False
				
		for x in ex:
			if str(x)[0]=='-':
				neg = True
		if neg:
			print "RESULT SIMPLE NEG"
			return {
				'year'    : get_none_result(nb_count),
				'month'   : get_none_result(nb_count),
				'day'     : list(rrule(DAILY, bymonth=1, bymonthday=get_range(32,n,ex), byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'hour'    : get_none_result(nb_count),
				'minute'  : get_none_result(nb_count),
				'second'  : get_none_result(nb_count),
				'week_day': get_none_result(nb_count),
		}

		else:

			return {
				'year'    : every_n_year_1_january_midnight(n),
				'month'   : list(rrule(MONTHLY, bymonth=get_range(12,n,ex), bymonthday=1, byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'day'     : list(rrule(DAILY, bymonth=1, bymonthday=get_range(32,n,ex), byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'hour'    : list(rrule(HOURLY, bymonth=1, bymonthday=1, byhour=get_range(24,n,ex), byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'minute'  : list(rrule(MINUTELY, bymonth=1, bymonthday=1, byhour=0, byminute=get_range(60,n,ex), bysecond=0, count=nb_count, dtstart=now)),
				'second'  : list(rrule(MINUTELY, bymonth=1, bymonthday=1, byhour=0, byminute=0, bysecond=get_range(60,n,ex), count=nb_count, dtstart=now)),
				'week_day': list(rrule(DAILY, bymonth=1, byweekday=get_range(7,n,ex), byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
			}
	def get_without_exclude(r, ex):
		ret=[]
		for i in rrule(DAILY, bymonth=1, bymonthday=range(1,32), byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now):
			for x in ex:
				if str(x)[0] == '-':
					x = max(calendar.monthrange(i.year, i.month)) + x + 1
				
				if i.day != x:
					ret.append(i)
		return ret
	def result_star_except(to_exclude):
		print "result_star_except"
		neg = False
		for x in to_exclude:
			if str(x)[0]=='-':
				neg = True

		if neg:
			return {
				'year'    : get_none_result(nb_count),
				'month'   : get_none_result(nb_count),
				'day'     : get_without_exclude(32, to_exclude),
				'hour'    : get_none_result(nb_count),
				'minute'  : get_none_result(nb_count),
				'second'  : get_none_result(nb_count),
				'week_day': get_none_result(nb_count),
		}
		else:
			return {
				'year'    : every_n_year_1_january_midnight(1, ex=[to_exclude]),
				'month'   : list(rrule(MONTHLY, bymonth=get_without_exclude(12,to_exclude), bymonthday=1, byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'day'     : list(rrule(DAILY, bymonth=1, bymonthday=get_without_exclude(32,to_exclude), byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'hour'    : list(rrule(HOURLY, bymonth=1, bymonthday=1, byhour=get_without_exclude(24,to_exclude), byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'minute'  : list(rrule(MINUTELY, bymonth=1, bymonthday=1, byhour=0, byminute=get_without_exclude(60,to_exclude), bysecond=0, count=nb_count, dtstart=now)),
				'second'  : list(rrule(MINUTELY, bymonth=1, bymonthday=1, byhour=0, byminute=0, bysecond=get_without_exclude(60,to_exclude), count=nb_count, dtstart=now)),
				'week_day': list(rrule(DAILY, bymonth=1, byweekday=get_without_exclude(7,to_exclude), byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
			}
	def result_simple(n, ex=[]):

		neg = False
		neg_ex = False
		for x in n:
			if str(x)[0]=='-':
				neg = True
		for x in ex:
			if str(x)[0]=='-':
				neg = True

		if neg and not neg_ex:
			print "RESULT SIMPLE NEG"
			return {
				'year'    : get_none_result(nb_count),
				'month'   : get_none_result(nb_count),
				'day'     : list(rrule(DAILY, bymonth=1, bymonthday=[d for d in n if d not in ex], byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'hour'    : get_none_result(nb_count),
				'minute'  : get_none_result(nb_count),
				'second'  : get_none_result(nb_count),
				'week_day': get_none_result(nb_count),
			}
		
		else:
			year = [ d for d in n if (str(d)[0]!='-' and d>=now.year and d not in ex)]
			if year == []:
				year = [ None, None, None ]

			return {
				'year'    : year,
				'month'   : list(rrule(MONTHLY, bymonth=[d for d in n if d not in ex], bymonthday=1, byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'day'     : list(rrule(DAILY, bymonth=1, bymonthday=[d for d in n if d not in ex], byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'hour'    : list(rrule(HOURLY, bymonth=1, bymonthday=1, byhour=[d for d in n if d not in ex], byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'minute'  : list(rrule(MINUTELY, bymonth=1, bymonthday=1, byhour=0, byminute=[d for d in n if d not in ex], bysecond=0, count=nb_count, dtstart=now)),
				'second'  : list(rrule(SECONDLY, bymonth=1, bymonthday=1, byhour=0, byminute=0, bysecond=[d for d in n if d not in ex], count=nb_count, dtstart=now)),
				'week_day': list(rrule(DAILY, bymonth=1, byweekday=[d for d in n if d not in ex], byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
			}
	def result_period(n, ex=[], msg=''):

		neg = False
		neg_ex = False
		for x in n:
			if str(x)[0]=='-':
				neg = True
		for x in ex:
			if str(x)[0]=='-':
				neg = True

		if neg :
			print "RESULT SIMPLE NEG"
			return {
				'year'    : get_none_result(nb_count),
				'month'   : get_none_result(nb_count),
				'day'     : list(rrule(DAILY, bymonth=1, bymonthday=[d for d in n if d not in ex], byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'hour'    : get_none_result(nb_count),
				'minute'  : get_none_result(nb_count),
				'second'  : get_none_result(nb_count),
				'week_day': get_none_result(nb_count),
			}
		
		else:
			year = [ d for d in n if (str(d)[0]!='-' and d>=now.year and d not in ex)]
			if year == []:
				year = [ None, None, None ]

			return {
				'year'    : year,
				'month'   : list(rrule(MONTHLY, bymonth=[d for d in n if d not in ex], bymonthday=1, byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'day'     : list(rrule(DAILY, bymonth=1, bymonthday=[d for d in n if d not in ex], byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'hour'    : list(rrule(HOURLY, bymonth=1, bymonthday=1, byhour=[d for d in n if d not in ex], byminute=0, bysecond=0, count=nb_count, dtstart=now)),
				'minute'  : list(rrule(MINUTELY, bymonth=1, bymonthday=1, byhour=0, byminute=[d for d in n if d not in ex], bysecond=0, count=nb_count, dtstart=now)),
				'second'  : list(rrule(SECONDLY, bymonth=1, bymonthday=1, byhour=0, byminute=0, bysecond=[d for d in n if d not in ex], count=nb_count, dtstart=now)),
				'week_day': list(rrule(DAILY, bymonth=1, byweekday=[d for d in n if d not in ex], byhour=0, byminute=0, bysecond=0, count=nb_count, dtstart=now)),
			}

	for arg in ('year', 'minute', 'hour', 'month', 'day', 'second', 'week_day'):
		for test, result in [
							 #('*', result_star_slash(1)),

							 #('*/2', result_star_slash(2)),
							 #('*/5', result_star_slash(5)),
							 
							 #('5', result_simple([5])),
							 #('4,5,6', result_simple([4,5,6])),
							 #('1:6', result_period(range(1,7))),
							 #("5,-1", result_simple([5,-1])),

							 #EXCEPT 
							 #('*^1', result_star_except([1])),
							 #('*^1,3,5', result_star_except([1,3,5])),
							 #('4,5,6^4', result_simple([4,5,6], ex=[4])),
							 #("*/2^4,6", result_star_slash(2, ex=[4,6])),
							 #('1:6^1,2', result_period(range(1,7), ex=[1,2])),
							 # negativ except : should NOT work, except for day
							 ("*^-1", result_star_except([-1])),
							 ('*^15,-1', result_star_except([15, -1])),
							 ('14:31^15,-1', result_period(range(14,32), ex=[15, -1])),
							 ('*/15^15,-1', result_star_slash(15, ex=[15, -1])),
							 ('28,29,30,31^28,-1', result_simple([28,29,30,31], ex=[28,-1])),
							]:

			print test, result[arg]
			kw = test_rule.copy()
			kw[arg] = test

			print "KW ", kw
			if arg == 'week_day':
				del kw['day']
			tasks('add_task', 'test-{0}-{1}'.format(arg, test), 'logging.notice', **kw)
			task = tasks('by_name', 'test-{0}-{1}'.format(arg, test))

			print "task created"
			
			print "result ", result[arg]



			try:
				assert result[arg][0] == task.schedule(test=True)
			except AttributeError,e:
				# no task, check if it was expected
				assert result[arg][0] == None

			i=1
			while i < nb_count:
				print i
				try:
					t = task.schedule(test=True, now=result[arg][i-1])
					print "CHECKING ", t , " == ", result[arg][i] , " now = ", result[arg][i-1]
					assert result[arg][i] == t
				except AttributeError,e:
					# no task, check if it was expected
					assert result[arg][i] == None

				i+=1
							
			if task != None:
				tasks('del_task', task.id)
"""
def test_massive():

	ranges = {
		'second'   : range(60),
		'minute'   : range(60),
		'hour'     : range(24),
		'day'      : range(1,32),
		'month'    : range(12),
		'year'     : range(1, 2038), 
		'week_day' : range(7) # 0 is monday
		}
	
	rkw = {
		'second'   : 'bysecond',
		'minute'   : 'byminute',
		'hour'     : 'byhour',
		'day'      : 'bymonthday',
		'week_day' : 'byweekday',
		'month'    : 'bymonth',
		'year'     : 'byyear'
		}
	rfreq = {
		'second'   : SECONDLY,
		'minute'   : MINUTELY,
		'hour'     : HOURLY,
		'day'      : DAILY,
		'week_day' : DAILY,
		'month'    : MONTHLY,
		'year'     : YEARLY
	}

	def get_result(arg, value, exclude={}):
		kw={}
		to_exclude={
			'year' : [],
			'month' : [],
			'day' : [],
			'hour' : [],
			'minute' : [],
			'second' : [],
			'week_day': []
		}
		neg=False
		def get_none_result(n):
			i=0
			ret = []
			while i < n:
				ret.append(None)
				i+=1
			return ret
		def check_for_exclusion(arg, value):
			ex = []
			neg=False
			ret, to_ex = value.split('^')
			for e in to_ex.split(','):
				if int(e)<0 and arg!='day':
					neg =True
				else:
					print "APPEND TO EXCLUDE ", e
					to_exclude[arg].append(int(e))
			 
			return neg, ret
		
		# check for exclusion
		if '^' in str(value):
			neg, value = check_for_exclusion(arg, value)
		

		if str(value).startswith('*/'):
			interval = int(value[2:])
			kw[rkw[arg]] = [ d for d in ranges[arg] if d%interval==0 ]

		elif ':' in str(value):
			start, end = value.split(":")
			kw[rkw[arg]] = [ d for d in ranges[arg] if d in range(int(start), int(end)+1) ]			
		else:
			for t in str(value).split(','):
				try:
					kw[rkw[arg]].append(int(t))
				except KeyError, AttributeError:
					kw[rkw[arg]] = [ int(t) ]
			
		
		# check for negativ:
		for v in kw[rkw[arg]]:
			if int(v)<0 and arg!='day':
				neg=True
		
		if neg:
			del kw[rkw[arg]]


		if not kw.has_key('bysecond'):
			kw.update({'bysecond' : 0})

		# finding freq
		freq = MINUTELY
		for p in ('year', 'month', 'day', 'hour', 'minute', 'second', 'week_day'):
			if kw.has_key(rkw[p]):
				if '*' in str(kw[rkw[p]]):
					freq = rfreq[p]

		dtstart=datetime.now()
		if kw.has_key('byyear'):
			years = [ int(y) for y in kw["byyear"] if y >= datetime.now().year ]
			if years != []:
				ref = datetime(year=min(years), month=1, day=1)
				if ref > now:
					dtstart=ref
			del kw['byyear']
		else:
			years = ranges['year']

		print "rrule(",freq, ", count=50, dtstart=", dtstart ,",", kw,")"
		#assert True == False
		print "will be excluded ", to_exclude
		#print list(rrule(freq, count=50, dtstart=dtstart, **kw))
		for date in rrule(freq, count=50, dtstart=dtstart, **kw):
			if neg:
				yield None
			elif date > datetime.now():
				excluded = False
				
				for p in ('year', 'month', 'day', 'hour', 'minute', 'second'):
					attr = getattr(date, p)
					if type(attr) != types.ListType:
						attr = [ attr ]
					for a in attr:
						for x in to_exclude[p]:
							print x, ' in , ',to_exclude[p]
							if int(x) > 0 and a == x:
								print a, " EXCLUDED"
								excluded = True 
							elif int(x) < 0:
								if a == max(calendar.monthrange(date.year, date.month)) + x + 1:
									excluded = True

				#special treatment for weekdays
				if date.weekday() in to_exclude['week_day']:
					excluded = True

				if date.year not in years:
					continue

				if not excluded:
					print "yield ", date
					yield date


	for arg in ('minute', 'year', 'hour', 'month', 'day', 'second', 'week_day'):
		""""""
		for test, result in [
							 ('*', get_result(arg,'*/1')),

							 ('*/2', get_result(arg, '*/2')),
							 ('*/5', get_result(arg, '*/5')),
							 
							 ('5', get_result(arg, '5')),
							 ('4,5,6', get_result(arg, '4,5,6')),
							 ('1:6', get_result(arg, '1:6')),
							 ("2,-1", get_result(arg, "2,-1")),

							 #EXCEPT 
							 ('*^1', get_result(arg,'*/1^1')),
							 ('*^1,3,5', get_result(arg,'*/1^1,3,5')),
							 ('4,5,6^4',  get_result(arg,'4,5,6^4')),
							 ("*/2^4,6", get_result(arg, '*/2^4,6')),
							 ('1:6^1,2', get_result(arg,'1:6^1,2')),
							 # negativ except : should NOT work, except for day
							 ("*^-1", get_result(arg, "*/1^-1")),
							 ('*^15,-1', get_result(arg, '*/1^15,-1')),
							 ('14:31^15,-1', get_result(arg, '14:31^15,-1')),
							 ('*/15^15,-1', get_result(arg, '*/15^15,-1')),
							 ('28,29,30,31^28,-1', get_result(arg, '28,29,30,31^28,-1')),
							]:

			kw = {}
			kw[arg] = test

			#if arg == 'week_day':
			#	del kw['day']
			
			tasks('add_task', 'test-{0}-{1}'.format(arg, test), 'logging.notice', **kw)
			task = tasks('by_name', 'test-{0}-{1}'.format(arg, test))

			now = datetime.now()
			for r in result:
				if r != None and task !=None:
					if r > now:
						assert r == task.schedule(test=True, now=now)
						now = r
				else:
					# was it expected?
					assert task == r
							
			if task != None:
				tasks('del_task', task.id)




