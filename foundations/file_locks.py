# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

file_locks - Historic and backward compatible locks based on files '*.lock'

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2

"""

import sys, os, time
from licorn.foundations import styles, logging, exceptions

class FileLock:
	"""
		This FileLock class is a reimplementation of basic locks with files.
		This is needed to be compatible with adduser/login binaries, which
		use /etc/{passwd,group}.lock to signify that the system files are locked.

	"""

	def __init__(self, configuration, filename = None, waitmax = 10, verbose = True):

		# TODO: don't blow up if user_dir isn't set (which is the case for daemon user)

		self.pretty_name = str(self.__class__).rsplit('.', 1)[1]

		if filename is None :
			raise exceptions.LicornRuntimeError("please specify a file to lock")

		if filename[0] == '/':
			self.filename = filename + '.lock'
			self.lockname = filename.rsplit('/', 1)[1]
		else:
			self.filename = "%s/%s.lock" % (configuration.user_dir, filename)
			self.lockname = filename

		logging.progress('%s: new instance with %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.filename)))

		self.waitmax = waitmax
		self.wait    = waitmax
		self.verbose = verbose

	def Lock(self):
		"""Acquire a lock, i.e. create $file.lock."""
		logging.progress('%s: pseudo-locking %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.lockname)))

		try:
			self.wait = self.waitmax
			while os.path.exists(self.filename) and self.wait >= 0:
				if self.verbose:
					sys.stderr.write("\r %s waiting %d second(s) for %s lock to be released... " \
						% (styles.stylize(styles.ST_NOTICE, '*'), self.wait, self.lockname))
					sys.stderr.flush()
				self.wait = self.wait - 1
				time.sleep(1)

			if self.wait <= 0:
				sys.stderr.write("\n")
				raise IOError, "%s lockfile still present, can't acquire lock after timeout !" % self.lockname

			else:
				try:
					open(self.filename, "w")
				except (IOError, OSError):
					raise IOError, "Can't create lockfile %s." % self.filename

		except KeyboardInterrupt:
			sys.stderr.write("\n")
			raise

		logging.progress('%s: successfully locked %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.filename)))

	def Unlock(self):
		"""Free the lock by removing the associated lockfile."""
		
		logging.progress('%s: removing lock on %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.lockname)))

		if os.path.exists(self.filename):
			try:
				os.unlink(self.filename)
			except (OSError):
				raise OSError, "can't remove lockfile %s." % self.filename

		logging.progress('%s: successfully unlocked %s.' % (self.pretty_name,
			styles.stylize(styles.ST_PATH, self.filename)))

	def IsLocked(self):
		"""Tell if a file is currently locked by looking if the associated lock
		is present."""
		return os.path.exists(self.filename)

