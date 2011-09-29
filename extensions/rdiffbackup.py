# -*- coding: utf-8 -*-
"""
Licorn extensions: rdiff-backup - http://docs.licorn.org/extensions/rdiffbackup.en.html

:copyright: 2010-2011 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, sys, time, errno
from threading import RLock, Event

from licorn.foundations        import logging, exceptions, process, pyutils
from licorn.foundations.styles import *
from licorn.foundations.ltrace import ltrace
from licorn.foundations.ltraces import *
from licorn.foundations.base   import Singleton, MixedDictObject, LicornConfigObject

from licorn.core               import LMC
from licorn.daemon.threads     import LicornJobThread
from licorn.extensions         import LicornExtension
from licorn.extensions.volumes import VolumeException
from licorn.interfaces.wmi     import WMIObject, wmi_register, wmi_unregister

from licorn.daemon             import priorities, roles

class RdiffbackupException(exceptions.LicornRuntimeException):
	""" A simple type of exception, to deal with rdiff-backup specific problems.

		.. versionadded:: 1.2.4
	"""
	pass
class RdiffbackupExtension(Singleton, LicornExtension, WMIObject):
	""" Handle Incremental backups via rdiff-backup, and offers a
		:class:`licorn.interfaces.wmi.WMIObject` interface for nice GUI
		operations.

		Rdiff-backup web site: http://www.nongnu.org/rdiff-backup/

		:command:`rdiff-backup` verbosity settings go from 0 to 9, with 3 as
		the default), and the :option:`--print-statistics` switch so some
		statistics will be displayed at the end (even without this switch, the
		statistics will still be saved in the :file:`rdiff-backup-data`
		directory.

		Restoring::

			--restore-as-of now
			                10D
			                5m4s
			                2010-01-23

		Restore from increment::

			rdiff-backup backup/rdiff-backup-data/increments/file.2003-03-05T12:21:41-07:00.diff.gz local-dir/file


		Cleaning::

			rdiff-backup --remove-older-than 2W host.net::/remote-dir
			                                 20B    (20 backups)


		Globing filelist::

			rdiff-backup --include-globbing-filelist include-list / /backup


		List different versions of a given file::

			rdiff-backup --list-increments out-dir/file


		Files changed the last 5 days::

			rdiff-backup --list-changed-since 5D out-dir/subdir


		5 days back system state::

			rdiff-backup --list-at-time 5D out-dir/subdir


		Average statistics::

			rdiff-backup --calculate-average
			       out-dir/rdiff-backup-data/session_statistics*


		Other interesting options::

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


		.. TODO:: snapshot backups http://wiki.rdiff-backup.org/wiki/index.php/UnattendedRdiff


		.. versionadded:: 1.2.4
	"""
	#: the environment variable used to override rdiff-backup configuration
	#: during tests or real-life l33Tz runs.
	globbing_env_var_name = "LICORN_RDIFF_BACKUP_CONF"
	module_depends = [ 'volumes' ]

	def __init__(self):
		assert ltrace(TRACE_RDIFFBACKUP, '| RdiffbackupExtension.__init__()')
		LicornExtension.__init__(self, name='rdiffbackup')

		self.controllers_compat = [ 'system' ]

		#: rdiff-backup could be enabled on clients too, but this is another
		#: story. This will eventually come later.
		self.server_only = True

		self.paths.backup_directory         = 'licorn.backups'
		self.paths.backup_duration_file     = '.org.licorn.backups.duration'
		self.paths.statistics_file          = '.org.licorn.backups.statistics'
		self.paths.statistics_duration_file = '.org.licorn.backups.statistics.duration'
		self.paths.increments_file          = '.org.licorn.backups.increments'
		self.paths.increment_sizes_file     = '.org.licorn.backups.increments.sizes'
		self.paths.last_backup_file         = '.org.licorn.backups.last_time'
		self.paths.globbing_file_system     = os.path.join(
												LMC.configuration.config_dir,
												'rdiff-backup-globs.conf')
		self.paths.globbing_file_local      = self._find_local_globbing_filelist()

	def _find_local_globbing_filelist(self):
		""" See if environment variable exists and use it, or return the
			default path for the rdiff-backup configuration.
		"""

		filename = os.getenv(RdiffbackupExtension.globbing_env_var_name, None)

		if filename:
			logging.notice(_(u'{0}: using environment variable {1} pointing to '
				'{2} for rdiff-backup configuration.').format(self.name,
					stylize(ST_COMMENT,
							RdiffbackupExtension.globbing_env_var_name),
					stylize(ST_PATH, filename)))
		else:
			filename = (os.path.join(LMC.configuration.config_dir,
								'rdiff-backup-globs.local.conf'))

		return filename
	def _find_binary(self, binary):
		""" Return the path of a binary on the local system, or ``None`` if
			not found in the :envvar:`PATH`. """

		default_path = '/bin:/usr/bin:/usr/local/bin:/opt/bin:/opt/local/bin'

		binary = '/' + binary

		for syspath in os.getenv('PATH', default_path).split(':'):
			if os.path.exists(syspath + binary):

				assert ltrace(self._trace_name, '| _find_binary(%s) → %s' % (
						binary[1:], syspath + binary))

				return syspath + binary

		assert ltrace(self._trace_name, '| _find_binary(%s) → None' % binary[1:])
		return None
	def initialize(self):
		""" Return True if :command:`rdiff-backup` is installed on the local
			system.
		"""

		assert ltrace(self._trace_name, '> initialize()')

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

		assert ltrace(self._trace_name, '< initialize(%s)' % self.available)
		return self.available
	def is_enabled(self):
		""" the :class:`RdiffbackupExtension` is enabled if available and when
			the :mod:`~licorn.extensions.volumes` extension is available too
			(we need volumes, to backup onto).

			If we are enabled, create a :class:`RdiffbackupThread` instance
			to be later collected and started by the daemon, the necessary
			internal :class:`~threading.Event` to run and synchronize
			properly, and the wmi_object part too.
		"""
		if 'volumes' in LMC.extensions:

			# will be True if a backup (or stats) is running.
			self.events.running = Event()
			# will be True while the real backup is running, False for stats.
			self.events.backup = Event()

			# will be set if a timer thread is up and running, else false,
			# meaning no backup volume is connected.
			self.events.active = Event()

			# this will be set to the volume we're backing up on
			self.current_backup_volume = None

			# hold a reference inside us too. It doesn't hurt, all volumes
			# are individually locked anyway.
			self.volumes = LMC.extensions.volumes.volumes

			if self._enabled_volumes() != []:
				self.__create_timer_thread()

			self.create_wmi_object('/backups')

			# NOTE: the event collection must be done here, instead of
			# self.enable() method, else the callbacks aren't collected at
			# daemon boot, because only is_enabled() is called by
			# ExtensionsManager.

			# register our callbacks in the event manager.
			L_event_collect(self)

			# register the newly-created WMIObject
			wmi_register(self)

			logging.info(_(u'{0}: started extension and auto-backup '
				'timer.').format(stylize(ST_NAME, self.name)))

			return True

		return False
	def __create_timer_thread(self):
		if not self.events.active.is_set():
			self.threads.auto_backup_timer = LicornJobThread(
							target=self.backup,
							delay=LMC.configuration.backup.interval,
							tname='extensions.rdiffbackup.AutoBackupTimer',
							# first backup starts 5 seconds later.
							time=(time.time()+5.0)
							)
			self.threads.auto_backup_timer.start()
			self.events.active.set()
	def __stop_timer_thread(self):
		if self.events.active.is_set():
			self.events.active.clear()

			# we need to test the existence of the thread, because this method
			# can be called multiple times. When non-enabled volumes are removed,
			# it will; and this will fail because there was NO timer anyway.
			if hasattr(self.threads, 'auto_backup_timer'):
				self.threads.auto_backup_timer.stop()
				del self.threads.auto_backup_timer
	def enable(self):
		""" This method will (re-)enable the extension, if :meth:`is_enabled`
			agrees that we can do it. The WMI object (already created by
			:meth:`is_enabled`) will be registered (a simple "reload" in the
			browser will see the Backup related things magically appear [again]).
		"""

		self.enabled = self.is_enabled()

		return self.enabled
	def disable(self):
		""" Disable the extension. This disables everything, from the timer
			thread to the WMI objects, dynamically (a simple "reload" in the
			WMI will see all "Backups" related things vanish. """

		if self.events.running.is_set():
			logging.warning(_('{0}: cannot disable now, a backup is in '
				'progress. Please wait until the end and retry.').format(
					stylize(ST_NAME, self.name)))
			return False

		# avoid a race with a backup beiing relaunched while we stop.
		self.events.running.set()

		# unregister our callbacks, to avoid beiing called while stopping
		L_event_uncollect(self)

		self.__stop_timer_thread()

		wmi_unregister(self)
		del self.wmi

		# clean the thread reference in the daemon.
		self.licornd.clean_objects()

		del self.volumes

		del self.events.backup

		self.enabled = False

		self.events.running.clear()
		del self.events.running

		return True
	def running(self):
		""" Returns ``True`` if a backup is currently running, else ``False``.
		"""
		return self.events.running.is_set()
	def system_load(self):
		""" This methods does nothing, but returns ``True``. It exists because
			this extension is affiliated to the
			:class:`~licorn.core.system.SystemController`, and
			every system-affiliated class must define it.

			.. TODO:: in the future, this method will probably refresh
				statistics and update the timer value according to the last
				backup date-time.
		"""

		return True
	def _enabled_volumes(self, complete=True):
		""" Returns a list of Licorn® enabled volumes. """

		return [ volume for volume in self.volumes if volume.enabled
													and (not complete
													or volume.mount_point) ]
	def _rdiff_statistics(self, volume):
		""" Compute statistics on a given volume. This method internally
			launches :program:`rdiff-backup-statistics` multiple times to
			pre-compute statistics and save them in hidden files on the
			volume, making WMI data outputs always ready and CPU friendly
			(the statistics operation is very lenghty and CPU intensive, its
			output must be cached).
		"""

		assert ltrace(self._trace_name, '| _rdiff_statistics(%s)' % volume)

		with volume.mount():
			logging.notice(_(u'{0}: computing statistics on {1}, '
				u'please wait…').format(stylize(ST_NAME, self.name), volume))

			start_time = time.time()
			for command_line, output_file in (
					([ 'rdiff-backup-statistics', '--quiet',
												self._backup_dir(volume) ],
								self.paths.statistics_file),
					([ 'rdiff-backup', '--list-increments', '--parsable-output',
												self._backup_dir(volume) ],
								self.paths.increments_file),
					([ 'rdiff-backup', '--list-increment-sizes',
												self._backup_dir(volume) ],
								self.paths.increment_sizes_file)
				):

				command = self.commands.nice[:]
				command.extend(command_line)

				assert ltrace(self._trace_name, 'executing %s, please wait.' % command)

				output, errors = process.execute(command)

				with open(os.path.join(volume.mount_point, output_file), 'w') as f:
					f.write(output)

			end_time = time.time()

			self._record_statistics_duration(volume, end_time - start_time)

			assert ltrace(TRACE_TIMINGS, '%s duration on '
				'%s: %s.' % (' '.join(command_line[:2]), volume,
					pyutils.format_time_delta(end_time - start_time)))

			return True
	def _record_statistics_duration(self, volume, duration):
		""" This methods does nothing yet.

			.. TODO:: to be implemented.
		"""

		pass
	def _backup_dir(self, volume):
		""" Returns the fixed path for the backup directory of a volume, passed
			as parameter. """
		return os.path.join(volume.mount_point, self.paths.backup_directory)
	def _backup_enabled(self, volume):
		""" Test if a volume is backup-enabled or not (is the backup directory
			present on it?).

			.. note:: This method won't automatically mount connected but
				unmounted volumes, to avoid confusing the user, displaying
				an information as if the volumes was mounted, whereas it
				is not (remember: locking a volume will automatically mount
				it, and unmount it right after the operation; in queries
				it will appear mounted, even if the situation has changed
				just after).

		"""
		if volume.mount_point:
			backup_dir = self._backup_dir(volume)
			return os.path.exists(backup_dir) and os.path.isdir(backup_dir)

		return False
	def _backup_enabled_volumes(self):
		""" Returns a list of backup-enabled volumes. """
		return [ volume for volume in self.volumes
						if volume.enabled and self._backup_enabled(volume) ]
	def recompute_statistics(self, volumes=None):
		""" Launch the :meth:`_rdiff_statistics` methods on each volume of a
			list passed as parameter, or on all enabled volumes if parameter
			is ``None``.

			It will verify if the volume is Licorn® enabled before running
			anything, and will skip unusable ones.

		"""

		if volumes is None:
			volumes = self._enabled_volumes()

		else:
			for volume in volumes:
				with volume.mount():
					if not volume.enabled:
						volumes.remove(volume)
						logging.info(_(u'Skipped disabled %s.') % volume)

		for volume in volumes:
			with volume.mount():
				self._rdiff_statistics(volume)
	# a comfort alias
	statistics = recompute_statistics
	def _compute_needed_space(self, volume):
		""" Verify how much space is needed on the backup volume to hold the
			next backup.

			If there has been one or more backup before, we
			compute twice the increment average size (just to be sure it fits).

			It no backup ever occured, we compute the size of the current global
			file system. This is far from perfect, but on standard systems (no
			customized configuration file), this is nearing reality.
		"""

		with volume.mount():
			try:
				for line in open(os.path.join(volume.mount_point,
								self.paths.statistics_file)
							).readlines():
					if line.startswith('TotalDestinationSizeChange'):
						return 2.0 * float(line.split()[1])

			except (IOError, OSError), e:
				if e.errno == errno.ENOENT:
					# this is the first backup: the volume must hold a nearly
					# complete copy of the file-system.

					exclusions = []

					for config_file in (self.paths.globbing_file_system,
										self.paths.globbing_file_local):
						if os.path.exists(config_file):
							exclusions.extend(x[2:-1]
								for x in open(config_file).readlines()
									if x[0] == '-' and '**' not in x)

					# TODO: remove local configuration directory sizes.
					return LMC.extensions.volumes.global_system_size(exclude=exclusions)

		raise RdiffbackupException(_(u'No statistics file or corrupted, '
								u'cannot compute backup needed space.'))
	def _has_enough_free_space(self, volume):
		""" Return True if the given volume has enough free space to hold
			the next backup. """

		with volume.mount():
			assert ltrace(self._trace_name, ' | _has_enough_free_space(%s): %s > %s ? %s' % (
				volume, volume.stats()[0] , self._compute_needed_space(volume),
				volume.stats()[0] > self._compute_needed_space(volume)))

			return volume.stats()[0] > self._compute_needed_space(volume)
	def _held_backups(self, volume):
		""" Return the number of backups held on a given volume, as an integer. """

		try:
			return len(open(os.path.join(volume.mount_point,
								self.paths.increments_file)).readlines())

		except (IOError, OSError), e:
			if e.errno == errno.ENOENT:
				return 0
			else:
				raise e
	def _remove_old_backups(self, volume, older_than):
		""" remove backups in the way rdiff-backup wants it to be done. """

		command = self.commands.ionice[:]
		command.extend(self.commands.nice[:])

		rdiff_command = [ self.paths.binary,
							'--remove-older-than', older_than,
							'--verbosity', '0',
							# --force is needed in case there is more than one
							# increment to remove (we don't know how many will
							# be selected, thus we always add --force.
							'--force',
							self._backup_dir(volume) ]

		command.extend(rdiff_command)

		cmd_start = time.time()

		with volume.mount():
			output, error = process.execute(command)

		assert ltrace(TRACE_TIMINGS, 'rdiff-backup clean older than %s on %s: %s.'
							% (older_than, volume, pyutils.format_time_delta(
										time.time() - cmd_start)))

		# FIXME: do this a better way ? keep this in a log ?
		sys.stderr.write(error)

		self._rdiff_statistics(volume)
	def _clean_obsolete_backups(self, volume):
		logging.info(_(u'{0}: cleaning obsolete backup on {1:s}.').format(
										stylize(ST_NAME, self.name), volume))
		return self._remove_old_backups(volume, older_than='1Y')
	def time_before_next_automatic_backup(self, as_string=True):
		""" Returns the time until next automatic backup, as a nicely formatted
			and localized string. If ``as_string`` is ``False``, the time will
			be returned as a `float` usable directly in any calculus-expression,
			without any formatting.

			You can call this method from the daemon's interactive shell, if
			you find it of any use::

				[…] [press "i" on your keyboard]
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
	def backup(self, volume=None, force=False):
		""" Start a backup in the background (`NORMAL` priority) and reset the
			backup timer, if no other backup is currently running. Internally,
			this method enqueues the private :meth:`__backup_procedure` method
			in the Service Queue.

			.. note::
				* If a backup takes more than the configured
				  :term:`backup interval <backup.interval>` to complete,
				  next planned backup will *not* occur because it will be
				  cancelled by the :meth:`running` method having returned
				  ``True``. This avoids backups running over them-selves,
				  but implies backups are not really ran at the configured
				  interval.

				* if all service threads are busy
				  (which is very unlikely to occur, given how many they are),
				  the backup could eventually be delayed until one service
				  thread is free again.

				* in this very same case, the backup timer would have been
				  reset anyway,
				  leading to a potential desynchronization
				  between the times of the "real" backup event and the timer
				  completion. I find this completely harmless, until proven
				  otherwise (feel free to shed a light on any problem I forgot).

			Provided your Licorn® daemon is attached to your terminal, you can
			launch a manual backup in the daemon's interactive shell, like
			this::

				[…] [press "i" on your keyboard]
				 * [2011/11/01 20:19:22.0170] Entering interactive mode. Welcome into licornd's arcanes…
				Licorn® @DEVEL@, Python 2.6.6 (r266:84292, Sep 15 2010, 15:52:39) [GCC 4.4.5] on linux2
				licornd> LMC.extensions.rdiffbackup.backup(force=True)
				[…]
				licornd> [Control-D]
				 * [2011/11/01 20:28:16.2913] Leaving interactive mode. Welcome back to Real World™.
				[…]
		"""

		if self.events.running.is_set():
			logging.notice(_(u'{0}: a backup is already running.').format(
												stylize(ST_NAME, self.name)))
			return

		self.threads.auto_backup_timer.reset()

		L_service_enqueue(priorities.NORMAL,
										self.__backup_procedure,
										volume=volume, force=force)
	def __backup_procedure(self, volume=None, force=False):
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

			.. warning::
				* **DO NOT CALL THIS METHOD DIRECTLY**. Instead, run
				  :meth:`backup` to reset the timer properly, and check if
				  a backup is not already in progress.
				* If a volume is left is a locked state for any reason,
				  this is currently a problem because not future backup
				  will happen until the lock is released. **TODO:** we should
				  probably make this case more error-proof.
		"""

		assert ltrace(self._trace_name, '> __backup_procedure()')

		if self.events.running.is_set():
			logging.progress(_(u'{0}: a backup is already running, '
				u'nothing done.').format(stylize(ST_NAME, self.name)))
			return

		first_found = False

		if volume is None:
			try:
				volume = self._enabled_volumes(complete=False)[0]
				first_found = True

			except IndexError:
				logging.warning2(_(u'{0}: no volumes to backup onto, '
					u'aborting.').format(stylize(ST_NAME, self.name)))
				return

		logging.progress(_(u'{0:s}: backup procedure computes pre-requisites, '
			u'please wait.').format(self.name))

		with volume.mount():
			if not force and (
					time.time() - self._last_backup_time(volume) <
										LMC.configuration.backup.interval):

				logging.notice(_(u'{0}: not backing up on {1}, last backup is '
					u'less than {2}.').format(stylize(ST_NAME, self.name),
						volume,
						pyutils.format_time_delta(
							LMC.configuration.backup.interval)))
				return

			self.events.running.set()

			already_cleaned = False
			nb_backups      = self._held_backups(volume)

			while not self._has_enough_free_space(volume):

				if nb_backups < 2:
					# TODO: implement an alert mechanism !!
					logging.warning(_(u'{0:s}: volume {1:s} does not have '
						u'enough free space or is not big enough to hold '
						u'more than two backups, aborting. '
						u'Space needed: {2}; free space: {3}.').format(
							self, volume,
							pyutils.bytes_to_human(self._compute_needed_space(volume), as_string=True),
							pyutils.bytes_to_human(volume.stats()[0], as_string=True)))
					self.events.running.clear()
					return

				nb_backups -= 1
				# remove the last backup on the volume (see beginning of this
				# file for explanation of rdiff-backup syntax).
				self._remove_old_backups(volume, older_than=str(nb_backups) + 'B')
				already_cleaned = True

			self.events.backup.set()

			self.current_backup_volume = volume

			logging.notice(_(u'{0:s}: running backup on{1} {2:s}, '
					u'please wait…').format(self,
					_(u' first available') if first_found else '', volume))

			backup_directory = self._backup_dir(volume)

			if not os.path.exists(backup_directory):
				os.mkdir(backup_directory)
				logging.progress(_(u'{0:s}: created directory {1}.').format(
					self, stylize(ST_PATH, backup_directory)))

			command = self.commands.ionice[:]
			command.extend(self.commands.nice[:])

			rdiff_command = [ self.paths.binary, '--verbosity', '1',
											'/', self._backup_dir(volume) ]

			for config_file in (self.paths.globbing_file_system,
								self.paths.globbing_file_local):
				if os.path.exists(config_file):
					rdiff_command.insert(1, config_file)
					rdiff_command.insert(1, '--include-globbing-filelist')

				else:
					logging.warning2(_(u'{0}: Rdiff-backup configuration file {1} '
						u'does not exist.').format(stylize(ST_NAME, self.name),
							stylize(ST_PATH, config_file)))

			command.extend(rdiff_command)

			self._write_last_backup_file(volume)

			assert ltrace(self._trace_name, '  executing %s, please wait.' %
														' '.join(command))
			backup_start = time.time()

			output, error = process.execute(command)

			assert ltrace(TRACE_TIMINGS, 'rdiff-backup duration on %s: %s.'
								% (volume, pyutils.format_time_delta(
											time.time() - backup_start)))

			# FIXME: do this a better way
			sys.stderr.write(error)

			self.current_backup_volume = None
			self.events.backup.clear()

			if not already_cleaned:
				self._clean_obsolete_backups(volume)

			else:
				self._rdiff_statistics(volume)

			self.events.running.clear()

			logging.notice(_(u'{0}: terminated backup procedure on {1}.').format(
										stylize(ST_NAME, self.name), volume))

			assert ltrace(self._trace_name, '< __backup_procedure()')
	def _write_last_backup_file(self, volume):
		""" Put :func:`time.time` in the last backup file. This file is here
			to avoid doing more than one backup per hour.

			:param volume: the :class:`~licorn.extensions.volumes.Volume` you
				want to update last backup file onto.
		"""

		with volume.mount():
			last_backup_file = (volume.mount_point
										+ '/' + self.paths.last_backup_file)
			open(last_backup_file, 'w').write(str(time.time()))
			logging.progress(_(u'{0}: updated last backup file {1}.').format(
				stylize(ST_NAME, self.name), stylize(ST_PATH, last_backup_file)))
	def _last_backup_time(self, volume):
		""" Return the contents of the "last backup file" of a given volume as
			a float, for delta-between-backup computations.

			:param volume: the :class:`~licorn.extensions.volumes.Volume` you
				want last backup time from.
		"""

		with volume.mount():
			try:
				return float(open(volume.mount_point +
							'/' + self.paths.last_backup_file).read().strip())
			except ValueError:
				# empty or corrupted file
				return 0.0
			except (IOError, OSError), e:
				if e.errno == 2:
					return 0.0
	def _backup_informations(self, volume, as_string=False):
		""" Return an HTML string for backup information. """
		if as_string:
			guid = volume.guid.replace('-', '_')
			return '{last_backup}<br />{next_backup}'.format(
					last_backup=_(u'Last backup on this volume '
						'occured {0} ago.').format(
							self._countdown('last_backup_vol_' + guid,
								time.time() - self._last_backup_time(volume),
								limit=9999999999.0))
								if self._last_backup_time(volume) > 0
								else _(u'No backup has occured yet.'),
					next_backup=_(u"Next backup attempt will occur "
						"in {0}.").format(
						self._countdown('next_backup_vol_' + guid,
							self.time_before_next_automatic_backup(
								as_string=False))))
		else:
			return (time.time() - self._last_backup_time(volume),
				self.time_before_next_automatic_backup(as_string=False))
	def volume_mounted_callback(self, volume, *args, **kwargs):
		""" Trigerred when a volume is mounted on the system. It will check
			if any of the connected (mounted or not) volumes is enabled for
			Licorn®, and will create the timer thread, if not already present.
		"""

		assert ltrace(self._trace_name, '| volume_mounted_callback(%s)', volume)

		if self._enabled_volumes(complete=False) != []:
			self.__create_timer_thread()
	def volume_unmounted_callback(self, volume, *args, **kwargs):
		""" Trigerred when a volume is unmounted from the system. If no
			Licorn® enabled volume remains connected (mounted or not), this
			method will stop the timer thread, if not already stopped.
		"""

		assert ltrace(self._trace_name, '| volume_unmounted_callback(%s)', volume)

		if self._enabled_volumes(complete=False) == []:
			self.__stop_timer_thread()
	# NOTE: we don't need a volume_added_callback(): any added volume gets
	# mounted right away if compatible; thus volume_mounted_callback() will
	# catch it. Any added but not compatible (thus not mounted) volume will
	# be of no help, we can safely ignore it.
	def volume_removed_callback(self, volume, *args, **kwargs):
		""" Trigerred when a volume is disconnected from the system. If no
			other Licorn® enabled volume remains connected (mounted or not),
			this method will stop the timer thread, if not already stopped.
		"""

		assert ltrace(self._trace_name, '| volume_removed_callback(%s)', volume)

		if self._enabled_volumes(complete=False) == []:
			self.__stop_timer_thread()
	def volume_enabled_callback(self, volume, *args, **kwargs):
		""" Trigerred when a new volume is enabled on the system; will blindly
			create the timer thread, if not already present.
		"""

		assert ltrace(self._trace_name, '| volume_enabled_callback(%s)', volume)

		if self._enabled_volumes() != []:
			self.__create_timer_thread()
	def volume_disabled_callback(self, volume, *args, **kwargs):
		""" Trigerred when a volume is disconnected from the system. If no
			Licorn® enabled volume remains, this method will stop the timer
			thread, if not already stopped.
		"""

		assert ltrace(self._trace_name, '| volume_disabled_callback(%s)', volume)

		if self._enabled_volumes() == []:
				self.__stop_timer_thread()
	def main_configuration_file_changed_callback(self, *args, **kwargs):
		""" Trigerred when the Licorn® main configuration file changed. If the
			:ref:`backup.interval <backup.interval.en>` changed and the
			timer thread is running, it will be reset with the new interval
			value.

			.. note:: when a dynamic change occur, the timer will be simply
				reset. No sophisticated computation will be done to substract
				the already-passed time from the new interval.
		"""

		if self.events.active.is_set():
			if LMC.configuration.backup.interval != self.threads.auto_backup_timer.delay:
				logging.info(_(u'{0}: backup interval changed from {1} to {2}, '
					'restarting timer.').format(stylize(ST_NAME, self.name),
						stylize(ST_ATTR, self.threads.auto_backup_timer.delay),
						stylize(ST_ATTR, LMC.configuration.backup.interval)))
				self.__stop_timer_thread()
				self.__create_timer_thread()
	def _html_eject_status(self, volume, small=False):
		""" Builds a part of HTML code used in the WMI object, related to
			ejection status of a given volume. This method should probably
			migrate into a template some day.
		"""
		if volume.locked():
			if small:
				return ('<span class="micro_indicator micro_{eject_css}">'
								'{eject_img}</span>'.format(
									eject_css='impossible',
									eject_img=(
										'<img src="/images/22x22/'
										'media-record.png" alt="'
										+ _(u'Backup in progress icon') + '" '
										'style="margin-top: -3px;"/>'
										)
									)
								)
			else:
				return ('<span class="small_indicator {eject_css}">'
								'{eject_img}&nbsp;{eject_message}</span>'.format(
									eject_css='impossible',
									eject_message=
										_(u"Can't eject, backup in progress"),
									eject_img=(
										'<img src="/images/22x22/'
										'media-record.png" alt="'
										+ _(u'Backup in progress icon') + '" '
										'style="margin-top: -3px;"/>'
										)
									)
								)
		else:
			if small:
				return ('<span class="micro_indicator micro_{eject_css}">'
								'<a href="{eject_uri}">{eject_img}'
								'</a></span>'.format(
									eject_css='possible',
									eject_uri=('/backups/eject/'
										+ volume.device.rsplit('/', 1)[1]),
									eject_img=(
										'<img src="/images/22x22/'
										'eject.png" alt="'
										+ _(u'Eject device icon') + '" />'
									)
								)
							)
			else:
				return ('<span class="small_indicator {eject_css}">'
								'<a href="{eject_uri}">{eject_img}&nbsp;'
								'{eject_message}</a></span>'.format(
									eject_css='possible',
									eject_message=_(u'Eject the volume'),
									eject_uri=('/backups/eject/'
										+ volume.device.rsplit('/', 1)[1]),
									eject_img=(
										'<img src="/images/22x22/'
										'eject.png" alt="'
										+ _(u'Eject device icon') + '" />'
									)
								)
							)
	# these 3 will be mapped into R/O properties by the WMIObject creation
	# process method. They will be deleted from here after the mapping is done.
	def _wmi_name(self):
		""" Normalized-name method which returns a localized string for the
			name of the WMI part of this extension.
		"""
		return _(u'Backups')
	def _wmi_alt_string(self):
		""" Normalized-name method which returns a localized string for the
			Alternate description string of the WMI part of this extension.
		"""
		return _(u'Manage backups and restore files')
	def _wmi_context_menu(self):
		""" Normalized-name method which returns the dynamic context menu for
			the WMI part of this extension.

		"""
		"""
					# to come:
						(_(u'Explore backups'), '/backups/search',
							_(u'Search in backup history for files or '
								'directories to restore'),
							'ctxt-icon', 'icon-export'),
						(_(u'Settings'), '/backups/settings',
							_(u'Manage system backup settings'),
							'ctxt-icon', 'icon-energyprefs'),
			"""
		return (
					(
						_(u'Run'),
						'/backups/run',
						_(u'Run a system incremental backup now'),
						'ctxt-icon',
						'/images/24x24/importer.png',
						lambda: self._enabled_volumes() != []
							and not self.events.running.is_set()
					),
					(
						_(u'Scan volumes'),
						'/backups/rescan',
						_(u'Force the system to rescan and remount connected '
							'volumes'),
						'ctxt-icon',
						'/images/24x24/importer.png',
						lambda: self._enabled_volumes() == []
					)
				)
	def _wmi__status(self):
		""" Method called from the WMI root, to nicely integrate backup
			status and critical messages on the dashboard. """

		messages = []

		if self.events.running.is_set():
			if self.events.backup.is_set():
				messages.append((priorities.HIGH,
					'<p class="light_indicator backup_in_progress '
					'high_priority">%s</p>' % (
						_(u'Backup in progress on volume {volume}…').format(
							volume=self.current_backup_volume.mount_point))))
			else:
				messages.append((priorities.NORMAL,
					'<p class="light_indicator backup_stats_in_progress '
					'normal_priority">%s</p>' % (
						_('Backup statistics computation '
							'in progress on volume {volume}…').format(
							volume=self.current_backup_volume.mount_point))))

		else :
			if self.events.active.is_set():
				messages.append((priorities.NORMAL,
					'<p class="light_indicator normal_priority">%s</p>' % (
					_(u'Next backup in {0}').format(
						self._countdown('next_backup',
						self.threads.auto_backup_timer.remaining_time(),
						uri='/')
					))))
			else:
				messages.append((priorities.NORMAL,
					'<p class="light_indicator normal_priority">'
					'<img src="/images/16x16/emblem-important.png" '
					'alt="Important emblem" width="16" height="16" '
					'style="margin-top: -5px" />'
					'&nbsp;%s</p>' % (_(u'No backup volume connected'))))

		return messages
	def _wmi__info(self):
		""" Method called from WMI root, to nicely integrate backup
			informations on the dashboard. """

		messages = []
		vprogress = ''

		volumes = self._backup_enabled_volumes()

		if volumes != []:
			for volume in volumes:
				if volume.mount_point:
					free, total = volume.stats()
					vprogress += ('<p>{eject_icon}&nbsp;&nbsp;'
						'{mount_point}&nbsp;&nbsp;&nbsp;{progress_bar}'
						'{used}</p>\n').format(
						eject_icon=self._html_eject_status(volume, small=True),
						mount_point=volume.mount_point,
						progress_bar=self._progress_bar(
							volume.device.rsplit('/', 1)[1],
							(total - free) / total * 100.0),
						used=_(u'used')
						)

			messages.append((priorities.NORMAL, vprogress))

		return messages
	def _wmi_run(self, uri, http_user, volume=None, force=False, **kwargs):
		""" Run a backup from the WMI (from http://xxx/backup/run). Offer the
			user to force the operation if the last backup is less than the
			configured interval.

			.. note:: this method should probably migrate to a template someday.
		"""

		w = self.utils
		title = _(u'Run a manual backup')

		auto_select = ''
		if volume is None:
			try:
				volume = self._enabled_volumes()[0]
				volume.mount()
				auto_select = ('<div style="text-align: center:">%s</div>'
					% _(u'Note: auto-selected volume {volume} for next '
						'backup.').format(volume=volume.mount_point))

			except IndexError:
				return (w.HTTP_TYPE_TEXT, w.page(title,
					w.main_content(w.error(_(u'No volume to backup onto. '
						'Please plug a {app_name} enabled volume into '
						'your server before starting this procedure.'
						'<br /><br />See <a href="http://docs.licorn.org'
						'/extensions/rdiffbackup.en.html">'
						'Backup-related documentation</a> for '
						'details on enabling backup volumes.').format(
						app_name=LMC.configuration.app_name)))
					+ w.sub_content('')))
		else:
			volume = self.volumes['/dev/' + volume]

		last_backup_time = time.time() - self._last_backup_time(volume)

		if last_backup_time < LMC.configuration.backup.interval and not force:

			title = _(u'Run a manual backup on volume {0}').format(
															volume.mount_point)
			data      = w.page_body_start(uri, http_user, self._ctxtnav, title)
			main_data = ''

			main_data += w.question(
				_(u'Recent backup detected'),
				_(u'{auto_select}<br /><br />The last backup has been run '
					'{last_backup_time} ago, which is less than the '
					'system configured interval ({interval}). Are you '
					'sure you want to force a manual backup now?<br /><br />'
					'(if you do not answer withing {next_backup_time}, '
					'an automatic backup will occur anyway)').format(
						auto_select=auto_select,
						last_backup_time=self._countdown('last_backup',
								last_backup_time,
								limit=9999999999.0),
						next_backup_time=self._countdown('next_backup',
								self.time_before_next_automatic_backup(
									as_string=False)),
						interval=pyutils.format_time_delta(
							LMC.configuration.backup.interval)),
				yes_values   = \
					[ _(u"Run >>"), "/backups/run/%s/force" %
							volume.device.rsplit('/', 1)[1], _(u"R") ],
				no_values    = \
					[ _(u"<< Cancel"),   "/backups",      _(u"C") ])

			return (w.HTTP_TYPE_TEXT,
				w.page(title, data
				+ w.main_content(main_data)
				+ w.sub_content('')
				+ w.page_body_end()))

		else:
			# we've got to translate the 'force' boolean because WMI doesn't
			# forward them as real boolean (it sends force='force' or None).
			self.backup(volume=volume, force=True if force else False)
			return (self.utils.HTTP_TYPE_REDIRECT,
							self.wmi.successfull_redirect)
	def _wmi_enable(self, uri, http_user, device, referer=None, **kwargs):
		""" Eject a device, from the WMI. """

		w      = self.utils
		device = '/dev/' + device
		volume = self.volumes[device]
		title  = _(u"Enable volume {device}").format(device=device)

		try:
			volume.enable()

		except Exception, e:
			pyutils.print_exception_if_verbose()

			return (w.HTTP_TYPE_TEXT, w.page(title,
				w.error(_(u'Could not enable volume {device} (was: '
					u'{exc}).{rewind}').format(
						device=device, exc=e,
						rewind=self.wmi.rewind_message))))

		return (self.utils.HTTP_TYPE_REDIRECT, referer
					if referer else self.wmi.successfull_redirect)
	def _wmi_eject(self, uri, http_user, device, referer=None, **kwargs):
		""" Eject a device, from the WMI. """

		w      = self.utils
		device = '/dev/' + device
		volume = self.volumes[device]
		title  = _(u"Eject volume {device}").format(device=device)

		if volume.locked():
			backup_info = (_(u' (a backup is underway)')
				if self.events.running.is_set() else '')

			return (w.HTTP_TYPE_TEXT, w.page(title,
				w.error(_(u"Volume {device} is in use{backup_info}, "
					"can't eject it!{rewind}").format(
						device=device,
						backup_info=backup_info,
						rewind=self.wmi.rewind_message))))

		volume.unmount()

		return (self.utils.HTTP_TYPE_REDIRECT, referer
					if referer else self.wmi.successfull_redirect)
	def _wmi_rescan(self, uri, http_user, **kwargs):
		""" Rescan volumes, mount everything that needs to, and reload page. """

		LMC.extensions.volumes.rescan_volumes()
		LMC.extensions.volumes.mount_volumes()

		#TODO: send a jquery notice to display on next page.
		return (self.utils.HTTP_TYPE_REDIRECT, self.wmi.successfull_redirect)
	def _wmi_main(self, uri, http_user, sort="date", order="asc", **kwargs):
		""" Main backup list (integrates volumes). """
		start = time.time()

		w = self.utils

		title = _(u"System backups")
		data  = w.page_body_start(uri, http_user, self._ctxtnav, '')

		main_content_data = ''
		rdiff_stats_output = ''
		base_div = (u'<div style="font-size:120%; '
			u'text-align: justify; margin-left:10%; '
			u'margin-right: 10%;">{message}</div>')

		if self.events.active.is_set():

			if self.events.running.is_set():
				backup_status = ('<div class="backups important '
					'backups_important">{0}</div>'.format(
						_('A backup is currently in progress, '
						'please do not disconnect <strong>{volume}</strong>.'
						'<br /><br /> (update in {countdown}…)').format(
							volume=''.join([ vol.mount_point
												for vol in self.volumes
													if vol.locked()]),
							countdown=self._countdown('next_reload', 118))))
			else:
				backup_status = ''

			# XXX: 20110923; this test seems to fail just after having
			# enabled a given volume. It is mounted, but the backup page
			# says it is not.
			#
			# We must deactivate the first backup timer to test it a
			# little deeper.
			if self._backup_enabled_volumes() != []:

				main_content_data += backup_status

				for volume in self._backup_enabled_volumes():
					base_div = ('<h2>{h2title}</h2>\n'
								'<p>{eject_status}</p>\n'
								'<p>{backup_info}</p>\n')

					eject_status = self._html_eject_status(volume)

					try:
						stats = open(volume.mount_point
								+ '/' + self.paths.increment_sizes_file).read().strip()

						if stats == '':
							stats = _(u'No historical data yet on <strong>{0}</strong>. '
								'Please wait for the first backup to finish.').format(volume.label)

					except (IOError, OSError), e:
						if e.errno == 2:
							# not ready yet (first backup rinnung)
							stats = _(u'No historical data yet on <strong>{0}</strong>. '
								'Please wait for the first backup to finish.').format(volume.label)
						else:
							raise e

					rdiff_stats_output += (u'\n<h3>{0}</h3>\n<pre '
						u'class="backups_statistics">{1}</pre>'
						u'<br /><br /><br />'.format(
							_('Backup status for {0}').format(volume.label),
							stats))

					main_content_data += base_div.format(
							h2title=_(u'Volume {label}').format(
								label=volume.label),
							backup_info=(
								self._backup_informations(volume, as_string=True)
									if backup_status is '' else ''),
							eject_status=eject_status
						)
			else:
				countdown_until_next_backup = self._countdown('next_backup',
						self.time_before_next_automatic_backup(
							as_string=False))

				main_content_data += base_div.format(message=_(u'All '
					'backup volumes are currently unmounted (you can safely '
					'disconnect them from your server).<br /><br />Next '
					'automatic backup will occur in {countdown}, and will '
					'automatically remount any backup volume still connected '
					'at this moment.').format(
						countdown=countdown_until_next_backup))

			return (w.HTTP_TYPE_TEXT, w.page(title, data
				+ w.main_content(main_content_data)
				+ w.sub_content(rdiff_stats_output)
				+ w.page_body_end(w.total_time(start, time.time()))))

		else:
			if self.volumes.values() == []:

				main_content_data += base_div.format(message=_(u'No backup '
					u'volume found: '
					u'no external volume is currently connected to '
					u'the server, or all the '
					u'connected volumes are not <a '
					u'href="http://docs.licorn.org/extensions/'
					u'volumes.en.html#extensions-volumes-compatible-en" '
					u'class="online_help" target="_blank" '
					u'title="Click to know which volumes are compatible, '
					u'and how to make one.">compatible with '
					u'Licorn®</a>.<br /><br />'
					u'Please connect a compatible backup volume to your '
					u'server, wait a few seconds and reload the current page.'))

			else:
				local_string = _(u'One or '
					u'more external volume(s) is '
					u'connected, but none is currently dedicated to '
					u'Licorn®. Would you like to '
					u'<a href="http://docs.licorn.org/extensions/'
					u'volumes.en.html#extensions-volumes-reserve-en" '
					u'class="online_help" target="_blank">enable and '
					u'reserve</a> '
					u'any of them for Licorn® use?')

				local_string += u'<ul class="volumes_list">'

				for volume in self.volumes.itervalues():
					local_string += (u'<li><a href="/backups/enable/{0}">{1}</a>'
								u'<ul class="volume_atributes">'
								u'<li>{2}</li><li>{3}</li><li>{4}</li></ul>'.format(
									volume.device.rsplit('/', 1)[1],
									_(u'use volume "<strong>{0}</strong>"').format(volume.label),
									_(u'currently not mounted,') if volume.mount_point is None
										else _(u'currently mounted on: <strong>{0}</strong>,').format(volume.mount_point),
									_(u'device: <strong>{0}</strong>,').format(volume.name),
									_(u'FS type: <strong>{0}</strong>').format(volume.fstype)))

				local_string += u'</ul>'

				main_content_data += base_div.format(message=local_string)

			return (w.HTTP_TYPE_TEXT, w.page(title, data
				+ w.main_content(main_content_data)
				+ w.sub_content('')
				+ w.page_body_end(w.total_time(start, time.time()))))
