# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, sys, time, gamin, signal

from threading   import Thread, Event, Semaphore
from collections import deque

from licorn.foundations         import fsapi, logging, exceptions, styles, process
from licorn.foundations.objects import LicornThread, Singleton
from licorn.core                import groups, configuration
from licorn.daemon.core         import dname

class ACLChecker(LicornThread, Singleton):
	""" A Thread which gets paths to check from a Queue, and checks them in time. """
	def __init__(self, cache, pname = dname):
		LicornThread.__init__(self, pname)

		self.cache      = cache

		# will be filled later
		self.inotifier  = None
		self.groups     = None
	def set_inotifier(self, ino):
		""" Get the INotifier instance from elsewhere. """
		self.inotifier = ino
	def set_groups(self, grp):
		""" Get system groups from elsewhere. """
		self.groups = grp
	def process_message(self, event):
		""" Process Queue and apply ACL on the fly, then update the cache. """

		#logging.debug('%s: got message %s.' % (self.name, event))
		path, gid = event

		if path is None: return

		acl = self.groups.BuildGroupACL(gid, path)

		try:
			if os.path.isdir(path):
				fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl') , -1)
				#self.inotifier.gam_changed_expected.append(path)
				fsapi.auto_check_posix1e_acl(path, False, acl['default_acl'], acl['default_acl'])
				#self.inotifier.gam_changed_expected.append(path)
				#self.inotifier.prevent_double_check(path)
			else:
				fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl'))
				#self.inotifier.prevent_double_check(path)
				fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')
				#self.inotifier.prevent_double_check(path)

		except (OSError, IOError), e:
			if e.errno != 2:
				logging.warning("%s: problem in GAMCreated on %s (was: %s, event=%s)." % (self.name, path, e, event))

		# FIXME: to be re-added when cache is ok.
		#self.cache.cache(path)
	def enqueue(self, path, gid):
		""" Put an event into our queue, to be processed later. """
		if self._stop_event.isSet():
			#logging.warning("%s: thread is stopped, not enqueuing %s|%s." % (self.name, path, gid))
			return

		#logging.progress('%s: enqueuing message %s.' % (self.name, (path, gid)))
		LicornThread.dispatch_message(self, (path, gid))
