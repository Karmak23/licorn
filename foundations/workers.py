# -*- coding: utf-8 -*-
"""
Licorn® foundations - workers 

:copyright:
	* 2010-2012 Olivier Cortès <olive@deep-ocean.net>
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
:license: GNU GPL version 2
"""

from threading import current_thread
from Queue     import Empty, Queue, PriorityQueue

# licorn.foundations imports
from base      import ObjectSingleton
from ltrace    import *
from ltraces   import *
from constants import priorities

# FIXME: this should move elsewhere someday.
from licorn.daemon.threads import ServiceWorkerThread, \
									ACLCkeckerThread, \
									NetworkWorkerThread

class WorkerService(ObjectSingleton):
	def __init__(self):
		self.serviceQ  = PriorityQueue()
		self.networkQ  = PriorityQueue()
		self.aclcheckQ = PriorityQueue()

		self.queues = {
				'service' : self.serviceQ,
				'network' : self.networkQ,
				'aclcheck': self.aclcheckQ
			}

	def stop(self):

		for (qname, queue) in self.queues.iteritems():
			size = queue.qsize()
			if size > 0:
				assert ltrace(TRACE_DAEMON, 'queue %s has %d items left: %s' % (
						qname, size, [
							str(item) for item in queue.get_nowait() ]))

		for q in self.queues.itervalues():
			q.put((-1, None))
	def background_service(self, prio=None):

		if prio is None:
			prio = priorities.NORMAL

		def wrap1(func):
			def wrap2(*a, **kw):
				self.serviceQ.put((prio, func, a, kw))
			return wrap2
		return wrap1
	def service_enqueue(self, prio, func, *args, **kwargs):
		self.serviceQ.put((prio, func, args, kwargs))
	def service_wait(self):
		if isinstance(current_thread(), ServiceWorkerThread):
			raise RuntimeError(_(u'Cannot join the serviceQ from '
				u'a ServiceWorkerThread instance, this would deadblock!'))
		self.serviceQ.join()
	def background_network(self, prio=None):

		if prio is None:
			prio = priorities.LOW

		def wrap1(func):
			def wrap2(*args, **kwargs):
				self.networkQ.put((prio, func, args, kwargs))
			return wrap2
		return wrap1
	def network_enqueue(self, prio, func, *args, **kwargs):
		self.networkQ.put((prio, func, args, kwargs))
	def network_wait(self):
		if isinstance(current_thread(), NetworkWorkerThread):
			raise RuntimeError(_(u'Cannot join the networkQ from '
				u'a NetworkWorkerThread instance, this would deadblock!'))
		self.__queues.networkQ.join()
	def background_aclcheck(self, prio=None):

		if prio is None:
			prio = priorities.HIGH

		def wrap1(func):
			def wrap2(*args, **kwargs):
				self.aclcheckQ.put((prio, func, args, kwargs))
			return wrap2
		return wrap1
	def aclcheck_enqueue(self, prio, func, *args, **kwargs):
		self.aclcheckQ.put((prio, func, args, kwargs))
	def aclcheck_wait(self):
		if isinstance(current_thread(), ACLCkeckerThread):
			raise RuntimeError(_(u'Cannot join the ackcheckerQ from '
				u'a ACLCkeckerThread instance, this would deadblock!'))
		self.aclcheckQ.join()

workers = WorkerService()

__all__ = ('workers', )
