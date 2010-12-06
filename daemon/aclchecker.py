# -*- coding: utf-8 -*-
"""
Licorn Daemon core.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, time

from licorn.foundations         import fsapi, logging
from licorn.foundations.pyutils import format_time_delta
from licorn.foundations.styles  import *
from licorn.foundations.ltrace  import ltrace

from licorn.daemon.core         import dname
from licorn.daemon.threads      import LicornThread

from licorn.core                import LMC

class ACLChecker(LicornThread):
	""" A Thread which gets paths to check from a Queue, and checks them in time. """
	def __init__(self, cache, pname = dname):
		LicornThread.__init__(self, pname)
		self.call_counter = 0
		self.last_call_time = None
	def dump_status(self, long_output=False, precision=None):
		""" dump current thread status. """
		return '%s(%s%s) %s (%s call%s%s, %s pending events)' % (
			stylize(ST_NAME, self.name), self.ident,
			stylize(ST_OK, '&') if self.daemon else '',
			stylize(ST_OK, 'alive') \
				if self.is_alive() else 'has terminated',
			stylize(ST_COMMENT, self.call_counter),
			's' if self.call_counter > 1 else '',
			', last: %s' % format_time_delta(self.last_call_time - time.time(),
				use_neg=True, long_output=False)
				if self.last_call_time else '',
			stylize(ST_COMMENT, self._input_queue.qsize())
		)
	def process_message(self, event):
		""" Process Queue and apply ACL on the fly, then update the cache. """

		assert ltrace('aclchecker','| process_message(%s)' % str(event))
		path, gid = event

		if path is None: return

		self.call_counter += 1
		self.last_call_time = time.time()

		acl = LMC.groups.BuildGroupACL(gid, path)

		try:
			if os.path.isdir(path):
				fsapi.auto_check_posix_ugid_and_perms(path, -1,
					LMC.groups.name_to_gid('acl') , -1)
				#dthreads.inotifier.gam_changed_expected.append(path)
				fsapi.auto_check_posix1e_acl(path, False,
					acl['default_acl'], acl['default_acl'])
				#dthreads.inotifier.gam_changed_expected.append(path)
				#dthreads.inotifier.prevent_double_check(path)
			else:
				fsapi.auto_check_posix_ugid_and_perms(path, -1,
					LMC.groups.name_to_gid('acl'))
				#dthreads.inotifier.prevent_double_check(path)
				fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')
				#dthreads.inotifier.prevent_double_check(path)

		except (OSError, IOError), e:
			if e.errno != 2:
				logging.warning(
					"%s: problem in ACLChecker on %s (was: %s, event=%s)." % (
						self.name, path, e, event))

		# FIXME: to be re-added when cache is ok.
		#dthreads.cache.cache(path)
	def enqueue(self, path, gid):
		""" Put an event into our queue, to be processed later. """
		if self._stop_event.isSet():
			#logging.warning("%s: thread is stopped, not enqueuing %s|%s." % (self.name, path, gid))
			return

		assert ltrace ('aclchecker', '| enqueue(%s, %s)' % (
			path, gid))
		LicornThread.dispatch_message(self, (path, gid))
