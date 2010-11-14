# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os

from licorn.foundations         import fsapi, logging
from licorn.foundations.styles  import *
from licorn.foundations.ltrace  import ltrace
from licorn.foundations.base    import Singleton
from licorn.foundations.thread  import _thcount, _threads

from licorn.daemon.core         import dname
from licorn.daemon.threads      import LicornThread

from licorn.core                import LMC

class ACLChecker(LicornThread, Singleton):
	""" A Thread which gets paths to check from a Queue, and checks them in time. """
	def __init__(self, cache, pname = dname):
		LicornThread.__init__(self, pname)

		self.cache      = cache

		# will be filled later
		self.inotifier  = None
	def dump_status(self, long_output=False, precision=None):
		""" dump current thread status. """
		return '''%s(%s%s) %s
	self._stop_event  = %s (%s)
	self._input_queue = %s (%s items)
	self.cache        = %s
	self.inotifier    = %s''' % (
		stylize(ST_NAME, self.name), self.ident,
		stylize(ST_OK, '&') if self.daemon else '',
		stylize(ST_OK, 'alive') \
			if self.is_alive() else 'has terminated',
		self._stop_event, self._stop_event.isSet(),
		self._input_queue, stylize(ST_COMMENT, self._input_queue.qsize()),
		self.cache,
		self.inotifier
	)
	def set_inotifier(self, ino):
		""" Get the INotifier instance from elsewhere. """
		self.inotifier = ino
	def process_message(self, event):
		""" Process Queue and apply ACL on the fly, then update the cache. """

		#assert logging.debug('%s: got message %s.' % (self.name, event))
		path, gid = event

		if path is None: return

		acl = LMC.groups.BuildGroupACL(gid, path)

		try:
			if os.path.isdir(path):
				fsapi.auto_check_posix_ugid_and_perms(path, -1,
					LMC.groups.name_to_gid('acl') , -1)
				#self.inotifier.gam_changed_expected.append(path)
				fsapi.auto_check_posix1e_acl(path, False,
					acl['default_acl'], acl['default_acl'])
				#self.inotifier.gam_changed_expected.append(path)
				#self.inotifier.prevent_double_check(path)
			else:
				fsapi.auto_check_posix_ugid_and_perms(path, -1,
					LMC.groups.name_to_gid('acl'))
				#self.inotifier.prevent_double_check(path)
				fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')
				#self.inotifier.prevent_double_check(path)

		except (OSError, IOError), e:
			if e.errno != 2:
				logging.warning(
					"%s: problem in ACLChecker on %s (was: %s, event=%s)." % (
						self.name, path, e, event))

		# FIXME: to be re-added when cache is ok.
		#self.cache.cache(path)
	def enqueue(self, path, gid):
		""" Put an event into our queue, to be processed later. """
		if self._stop_event.isSet():
			#logging.warning("%s: thread is stopped, not enqueuing %s|%s." % (self.name, path, gid))
			return

		assert ltrace ('cache', '%s: enqueuing message %s.' % (
			self.name, (path, gid)))
		LicornThread.dispatch_message(self, (path, gid))
