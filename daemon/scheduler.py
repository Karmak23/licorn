# -*- coding: utf-8 -*-
"""
Licorn Daemon BasicScheduler (very very basic scheduler).

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

from threading   import Thread, Event, Semaphore, Timer
from collections import deque

from licorn.foundations           import logging, styles
from licorn.foundations.classes   import LicornThread
from licorn.foundations.constants import filters

from licorn.daemon.core           import dname

class BasicScheduler(LicornThread):
	""" A Thread to do basic timed tasks. """

	def __init__(self, pname=dname, **kwargs):

		LicornThread.__init__(self)

		self.name = "%s/%s" % (
			pname, str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		self.jobs = {}
	def add_job(self, ):
		""" add a job in the queue.
			"""

	def del_job(self, jobid):
		''' delete a job. '''
		return True
	def has_job(self, job=None, jobid=None):
		if jobid is not None:
			return jobid in self.jobs
		raise exceptions.BadArgumentError('must supply a job or a job ID.')
	def process_message(self):
		pass
