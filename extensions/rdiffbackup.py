# -*- coding: utf-8 -*-
"""
Licorn extensions: rdiff-backup - http://docs.licorn.org/extensions/rdiff_backup.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, sys, time

from threading import RLock, Event

from licorn.foundations        import logging, exceptions, process, pyutils
from licorn.foundations.styles import *
from licorn.foundations.ltrace import ltrace
from licorn.foundations.base   import Singleton, MixedDictObject, LicornConfigObject

from licorn.core               import LMC
from licorn.daemon.threads     import TriggerTimerThread, TriggerWorkerThread
from licorn.extensions         import LicornExtension
from licorn.extensions.volumes import VolumeException

class RdiffbackupException(exceptions.LicornRuntimeException):
	""" A type of exception to deal with rdiff-backup specific problems.

		.. versionadded:: 1.2.4
	"""
	pass
class RdiffbackupExtension(Singleton, LicornExtension):
	""" Handle Incremental backups via rdiff-backup.

		Web site: http://www.nongnu.org/rdiff-backup/

		:command:`rdiff-backup` verbosity settings go from 0 to 9, with 3 as
		the default), and the :option:`--print-statistics` switch so some
		statistics will be displayed at the end (even without this switch, the
		statistics will still be saved in the :file:`rdiff-backup-data`
		directory.

		Restoring:

			--restore-as-of now
							10D
							5m4s
							2010-01-23

		Restore from increment::

			rdiff-backup backup/rdiff-backup-data/increments/file.2003-03-05T12:21:41-07:00.diff.gz local-dir/file


		Cleaning::

			rdiff-backup --remove-older-than 	2W host.net::/remote-dir
												20B		(20 backups)


		Globing filelist::

			rdiff-backup --include-globbing-filelist include-list / /backup


		List different versions of a given file::

			rdiff-backup --list-increments out-dir/file


		Files changed the last 5 days::

			rdiff-backup --list-changed-since 5D out-dir/subdir


		5 days back system state::

			rdiff-backup --list-at-time 5D out-dir/subdir


		Average statistics::

			rdiff-backup --calculate-average \
			out-dir/rdiff-backup-data/session_statistics*


		--create-full-path
			Normally only the final directory of the destination  path  will
			be  created  if it does not exist. With this option, all missing
			directories on the destination path will be  created.  Use  this
			option  with  care:  if  there is a typo in the remote path, the
			remote filesystem could fill up  very  quickly  (by  creating  a
			duplicate backup tree). For this reason this option is primarily
			aimed at scripts which automate backups.


		--exclude-special-files
			Exclude all device files, fifo files, socket files, and symbolic
			links.


		-l, --list-increments
			List  the  number  and  date of partial incremental backups con-
			tained in the specified destination  directory.   No  backup  or
			restore will take place if this option is given.


		--list-increment-sizes
			List  the  total  size  of all the increment and mirror files by
			time.  This may be helpful in deciding how  many  increments  to
			keep,  and  when to --remove-older-than.  Specifying a subdirec-
			tory is allowable; then only the sizes of the mirror and  incre-
			ments pertaining to that subdirectory will be listed.


		--parsable-output
			If set, rdiff-backup's output will be tailored for easy  parsing
			by computers, instead of convenience for humans.  Currently this
			only applies when listing increments using  the  -l  or  --list-
			increments  switches,  where  the  time will be given in seconds
			since the epoch.


		--preserve-numerical-ids
			If  set,  rdiff-backup will preserve uids/gids instead of trying
			to preserve unames and gnames.  See the USERS AND GROUPS section
			for more information.


		--print-statistics
			If  set,  summary  statistics will be printed after a successful
			backup.  If not set, this information will  still  be  available
			from  the  session  statistics file.  See the STATISTICS section
			for more information.


		-r, --restore-as-of restore_time
			Restore the specified directory as it was  as  of  restore_time.
			See  the TIME FORMATS section for more information on the format
			of restore_time, and see the RESTORING section for more informa-
			tion on restoring.


		.. note:: TODO: snapshot backups http://wiki.rdiff-backup.org/wiki/index.php/UnattendedRdiff


		.. versionadded:: 1.2.4
	"""
	#: the environment variable used to override rdiff-backup configuration
	#: during tests or real-life l33Tz runs.
	globbing_env_var_name = "LICORN_RDIFF_BACKUP_CONF"
	module_depends = [ 'volumes' ]

	def __init__(self):
		assert ltrace('rdiffbackup', '| RdiffbackupExtension.__init__()')
		LicornExtension.__init__(self, name='rdiffbackup')

		self.controllers_compat = [ 'system' ]

		#: rdiff-backup could be enabled on clients too, but this is another
		#: story. This will eventually come later.
		self.server_only = True

		self.paths.backup_directory     = 'licorn.backups'
		self.paths.statistics_file      = '.licorn.backup.statistics'
		self.paths.increments_file      = '.licorn.backup.increments'
		self.paths.increment_sizes_file = '.licorn.backup.increments.sizes'
		self.paths.last_backup_file     = '.licorn.backup.last_time'
		self.paths.globbing_file        = self._find_globbing_filelist()
	def _find_globbing_filelist(self):
		""" See if environment variable exists and use it, or return the
			default path for the rdiff-backup configuration.
		"""

		filename = os.getenv(RdiffbackupExtension.globbing_env_var_name, None)

		if filename:
			logging.notice('%s: using environment variable %s pointing to '
				'%s for rdiff-backup configuration.' % (self.name,
					stylize(ST_COMMENT,
							RdiffbackupExtension.globbing_env_var_name),
					stylize(ST_PATH, filename)))
		else:
			filename = (LMC.configuration.config_dir
								+ '/' + 'rdiff-backup-globs.conf')

		return filename
	def _find_binary(self, binary):
		""" Return the path of a binary on the local system, or ``None`` if
			not found in the :envvar:`PATH`. """

		default_path = '/bin:/usr/bin:/usr/local/bin:/opt/bin:/opt/local/bin'

		binary = '/' + binary

		for syspath in os.getenv('PATH', default_path).split(':'):
			if os.path.exists(syspath + binary):

				assert ltrace(self.name, '| _find_binary(%s) → %s' % (
						binary[1:], syspath + binary))

				return syspath + binary

		assert ltrace(self.name, '| _find_binary(%s) → None' % binary[1:])
		return None
	def initialize(self):
		""" Return True if :command:`rdiff-backup` is installed on the local
			system.
		"""

		assert ltrace(self.name, '> initialize()')

		# these ones will be filled later.
		self.paths.binary           = self._find_binary('rdiff-backup')
		self.paths.nice_bin         = self._find_binary('nice')
		self.paths.ionice_bin       = self._find_binary('ionice')

		if self.paths.binary:
			self.available = True

			self.commands = LicornConfigObject()

			if self.paths.nice_bin:
				self.commands.nice = [ self.paths.nice_bin, '-n', '19' ]
			else:
				self.commands.nice = []

			if self.paths.ionice_bin:
				self.commands.ionice = [ self.paths.ionice_bin, '-c', '3' ]
			else:
				self.commands.ionice = []

		else:
			logging.warning2('%s: not available because rdiff-binary not '
				'found in $PATH.' % self.name)

		assert ltrace(self.name, '< initialize(%s)' % self.available)
		return self.available
	def is_enabled(self):
		""" the :class:`RdiffbackupExtension` is enabled when the
			:mod:`~licorn.extensions.volumes` extension is available (we need
			volumes to backup onto).

			If we are enabled, create a :class:`RdiffbackupThread` instance
			to be later collected and started by the daemon.
		"""
		if 'volumes' in LMC.extensions:

			# hold a reference inside us too. It doesn't hurt, all volumes
			# are individually locked anyway.
			self.volumes = LMC.extensions.volumes.volumes

			self.events.start_backup = Event()

			self.threads.auto_backup_timer = TriggerTimerThread(
							trigger_event=self.events.start_backup,
							delay=LMC.configuration.backup.interval,
							pname='extensions',
							tname='Rdiffbackup.AutoBackupTimer',
							# first backup starts 10 minutes later.
							time=(time.time()+600.0)
							)
			self.threads.auto_backup_worker = TriggerWorkerThread(
							trigger_event=self.events.start_backup,
							target=self.backup,
							pname='extensions',
							tname='Rdiffbackup.AutoBackupWorker'
							)

			self.threads.auto_backup_worker.start()
			self.threads.auto_backup_timer.start()
			return True

		return False
	def system_load(self):
		""" TODO. """

		#TODO: refresh statistics.

		return True
	def _enabled_volumes(self):
		""" Return a list of licorn enabled volumes. """

		return [ volume for volume in self.volumes if volume.enabled ]
	def _rdiff_statistics(self, volume):
		""" TODO """

		assert ltrace(self.name, '| _rdiff_statistics(%s)' % volume)

		with volume:
			logging.info('%s: computing statistics on %s, '
				'please wait.' % (self.name, volume))

			for command_line, output_file in (
					([ 'rdiff-backup-statistics', '--quiet',
												self._backup_dir(volume) ],
								self.paths.statistics_file),
					([ 'rdiff-backup', '--list-increments',
												self._backup_dir(volume) ],
								self.paths.increments_file),
					([ 'rdiff-backup', '--list-increment-sizes',
												self._backup_dir(volume) ],
								self.paths.increment_sizes_file)
				):

				command = self.commands.nice[:]
				command.extend(command_line)

				assert ltrace(self.name, 'executing %s, please wait.' % command)

				start_time = time.time()
				output, errors = process.execute(command)

				assert ltrace('timings', '%s duration on '
					'%s: %s.' % (' '.join(command_line[:2]), volume,
						pyutils.format_time_delta(time.time() - start_time)))

				open(volume.mount_point + '/' + output_file, 'w').write(output)

			return True
	def _backup_dir(self, volume):
		return volume.mount_point + '/' + self.paths.backup_directory
	def _backup_enabled(self, volume):
		with volume:
			return os.path.exists(
						)
	def _backup_enabled_volumes(self):
		return [ volume for volume in self.volumes
						if self._backup_enabled(volume) ]
	def recompute_statistics(self, volumes=None):
		""" TODO """

		if volumes is None:
			volumes = self._enabled_volumes()
		else:
			for volume in volumes:
				with volume:
					if not volume.enabled:
						volumes.remove(volume)
						logging.info('Skipped disabled %s.' % volume)

		for volume in volumes:
			with volume:
				self._rdiff_statistics(volume)
	def _compute_needed_space(self, volume, clean=False):

		print '>> please implement volumes._compute_needed_space(self, ...)'
		pass
	def _remove_old_backups(self, volume, size=None, number=None,
															older_than=None):
		print '>> please implement volumes._remove_old_backups(self, ...)'
		pass
	def manual_backup(self, volume=None, force=False, batch=False):
		""" Do a backup and reset the backup thread timer.

			Provided your Licorn® daemon is attached to your terminal, you can
			launch a manual backup in the daemon's interactive shell, like
			this::

				[…] [i on keyboard]
				 * [2011/11/01 20:19:22.0170] Entering interactive mode. Welcome into licornd's arcanes…
				Licorn® @DEVEL@, Python 2.6.6 (r266:84292, Sep 15 2010, 15:52:39) [GCC 4.4.5] on linux2
				licornd> LMC.extensions.rdiffbackup.manual_backup(force=True)
				[…]
				licornd> [Control-D]
				 * [2011/11/01 20:28:16.2913] Leaving interactive mode. Welcome back to Real World™.
				[…]

		"""

		self.threads.auto_backup_timer.reset()
		# wait for the timer to acknoledge the reset action()
		time.sleep(0.2)
		self.threads.auto_backup_worker.trigger(volume=volume, force=force,
			batch=batch)
		logging.notice('%s: triggered a manual backup in the background (next automatic in %s).' % (
				self.name, self.time_before_next_automatic_backup()))
	def time_before_next_automatic_backup(self, as_string=True):
		""" Display a notice about time remaining before next automatic backup.

			You can call this method from the daemon's interactive shell, if
			you find it of any use::

				[…]
				 * [2011/11/01 20:19:22.0170] Entering interactive mode. Welcome into licornd's arcanes…
				Licorn® @DEVEL@, Python 2.6.6 (r266:84292, Sep 15 2010, 15:52:39) [GCC 4.4.5] on linux2
				licornd> LMC.extensions.rdiffbackup.time_before_next_automatic_backup()
				'44 mins 3 secs'
				licornd> [Control-D]
				 * [2011/11/01 20:28:16.2913] Leaving interactive mode. Welcome back to Real World™.
				[…]

		"""
		if as_string:
			return pyutils.format_time_delta(
					self.threads.auto_backup_timer.remaining_time())
		else:
			return self.threads.auto_backup_timer.remaining_time()
	def backup(self, volume=None, force=False, batch=False):
		""" Do a complete backup procedure, which includes:

			* finding a backup volume. If none is given, the first available
			  will be choosen.
			* verifying if no backup has occured in the last hour. If it has,
			  the backup is cancelled.
			* computing the space needed for the backup, and eventually
			  cleaning the backup volume before proceeding, if needed.
			* updating the last backup time: it's the time of the backup
			  **start**, not the end, to be sure one backup per
			  :term:`backup.interval` is
			  executed, not one backup per :term:`backup.interval` +
			  backup_duration, which could
			  greatly delay future backups if they take a long time.
			* doing the rdiff-backup.
			* updating the average statistics for the backup volume (this
			  permits finer accuracy when computing needed space).

			:param volume: a :class:`~licorn.extensions.volumes.Volume`
				instance on which you want to make a backup of the system onto,
				or ``None`` if you want the method to search for the first
				available volume.

			:param force: a boolean, used to force a backup, even if the last
				backup has been done in less than the configured
				:term:`backup interval <backup.interval>`.

			:param batch: a boolean to indicate that the current operation is
				happening is headless and noninteractive mode, and thus no
				exceptions should be raised because no-one could handle them.

				When no exceptions are raised inside this method, a warning is
				displayed in the daemon's log and the method simply returns
				(this mechanism is used for automatic backup, when no backup
				volume is available; is this situation, in standard CLI
				conditions, an exception would be raised to be catched by the
				calling CLI process).

			.. note:: If a backup takes more than the configured
				:term:`backup interval <backup.interval>` to complete, next
				planned backup will not occur.

			.. warning: If a volume is left is a locked state for any reason,
				this is currently a problem because not future backup
				will happen until the lock is released. **TODO:** we should
				probably make this case more error-proof.
		"""

		first_found = False

		if volume is None:
			first_found = True
			try:
				volume = self._enabled_volumes()[0]
			except IndexError:
				if batch:
					logging.warning2('%s: no volumes to backup onto.' %
																	self.name)
					return
				else:
					raise RdiffBackupException('no volumes to backup onto!')

		try:
			with volume:
				if not force and (
						time.time() - self._last_backup_time(volume) <
											LMC.configuration.backup.interval):
					logging.info('%s: not backing up on %s, last backup is '
						'less that one hour.' % (self.name, volume))
					return

				logging.info('%s: backing up on%s %s.' % (
					self.name, ' first available'
						if first_found else '', volume))

				backup_directory = self._backup_dir(volume)

				if not os.path.exists(backup_directory):
					os.mkdir(backup_directory)
					logging.progress('%s: created directory %s.'
										% stylize(ST_PATH, backup_directory))

				self._compute_needed_space(volume, clean=True)

				command = self.commands.ionice[:]
				command.extend(self.commands.nice[:])

				rdiff_command = [ self.paths.binary, '/', self._backup_dir(volume) ]

				if os.path.exists(self.paths.globbing_file):
					rdiff_command.insert(1, self.paths.globbing_file)
					rdiff_command.insert(1, '--include-globbing-filelist')
				else:
					logging.warning2("%s: Rdiff-backup configuration file %s "
						"doesn't exist." % (self.name,
							stylize(ST_PATH, self.paths.globbing_file)))

				command.extend(rdiff_command)

				self._write_last_backup_file(volume)

				assert ltrace(self.name, '  executing %s, please wait.' %
															' '.join(command))
				backup_start = time.time()

				output, error = process.execute(command)

				assert ltrace('timings', 'rdiff-backup duration on %s: %s.'
									% (volume, pyutils.format_time_delta(
												time.time() - backup_start)))

				# FIXME: do this a better way
				sys.stderr.write(error)

				self._remove_old_backups(volume)
				self._rdiff_statistics(volume)
		except VolumeException, e:
			logging.warning("%s: can't backup on %s, it's not available "
				"(was: %s)." % (self.name, volume, e))
	def _write_last_backup_file(self, volume):
		""" Put :func:`time.time` in the last backup file. This file is here
			to avoid doing more than one backup per hour.

			:param volume: the :class:`~licorn.extensions.volumes.Volume` you
				want to update last backup file onto.
		"""

		with volume:
			last_backup_file = (volume.mount_point
										+ '/' + self.paths.last_backup_file)
			open(last_backup_file, 'w').write(str(time.time()))
			logging.progress('%s: updated last backup file %s.'
							% (self.name, stylize(ST_PATH, last_backup_file)))
	def _last_backup_time(self, volume):
		""" Return the contents of the "last backup file" of a given volume as
			a float, for delta-between-backup computations.

			:param volume: the :class:`~licorn.extensions.volumes.Volume` you
				want last backup time from.
		"""

		with volume:
			try:
				return float(open(volume.mount_point +
							'/' + self.paths.last_backup_file).read().strip())
			except ValueError:
				# empty or corrupted file
				return 0.0
			except (IOError, OSError), e:
				if e.errno == 2:
					return 0.0
