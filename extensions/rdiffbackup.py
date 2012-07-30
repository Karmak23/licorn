# -*- coding: utf-8 -*-
"""
Licorn extensions: rdiff-backup - http://docs.licorn.org/extensions/rdiffbackup.en.html

:copyright: 2010-2011 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, sys, time, errno, types, glob
from functools import wraps
from threading import Event

from licorn.foundations           import settings, logging, exceptions
from licorn.foundations           import process, pyutils, fsapi
from licorn.foundations           import events, cache
from licorn.foundations.events    import LicornEvent
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, LicornConfigObject
from licorn.foundations.constants import priorities
from licorn.foundations.workers   import workers

from licorn.core                import LMC
from licorn.core.classes        import only_if_enabled
from licorn.daemon.threads      import LicornJobThread
from licorn.extensions          import LicornExtension

RDIFF_TASK_NAME     = 'extensions.rdiffbackup.autobackup'
RDIFF_DEFAULT_TIME  = '02:00'
RDIFF_DEFAULT_WKDAY = '*'
RDIFF_SETTING_TIME  = 'extensions.rdiffbackup.backup_time'
RDIFF_SETTING_WKDAY = 'extensions.rdiffbackup.backup_week_day'

def lazy_mounted(func):
	@wraps(func)
	def decorated(self, volume=None, *args, **kwargs):

		if volume is None:
			volume = self.find_first_volume_available()

			if volume is None:
				logging.exception(_(u'{0}: No default volume found, aborting call '
										u'of {1}({2}, {3})').format(
											stylize(ST_NAME, ext.name),
											func.__name__, str(args),
											str(kwargs)))
				return None

		elif type(volume) in (types.StringType, types.UnicodeType):
			volume = self.volumes[volume]

		with volume:
			auto_unmount = False

			if volume.mount_point is None:
				auto_unmount = True
				volume.mount(emit_event=False)

			try:
				res = func(self, volume, *args, **kwargs)

			finally:
				if auto_unmount:
					volume.unmount(emit_event=False)

			return res
	return decorated
def if_not_already_running_on_this_volume(func):
	@wraps(func)
	def decorated(self, volume, *args, **kwargs):

		if self.events.running.is_set():
			logging.notice(_(u'{0}: an operation is already in progress '
							u'on {1}, aborting.').format(self.pretty_name, volume))
			return

		with volume.mount():
			self.current_operated_volume = volume
			self.events.running.set()

			result = func(self, volume, *args, **kwargs)
			# we let the volume mounted after the operation

			self.events.running.clear()
			self.current_operated_volume = None

		return result

	return decorated
class RdiffbackupException(exceptions.LicornRuntimeException):
	""" A simple type of exception, to deal with rdiff-backup specific problems.

		.. versionadded:: 1.2.4
	"""
	pass
class RdiffbackupExtension(ObjectSingleton, LicornExtension):
	""" Handle Incremental backups via rdiff-backup.

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
	module_depends        = [ 'volumes' ]

	def __init__(self):
		assert ltrace_func(TRACE_RDIFFBACKUP)

		LicornExtension.__init__(self, name='rdiffbackup')

		self.controllers_compat = [ 'system' ]

		#: rdiff-backup could be enabled on clients too, but this is another
		#: story. This will eventually come later.
		self.server_only = True

		self.paths.backup_directory         = 'licorn.backups'
		self.paths.backup_duration_file     = '.org.licorn.backups.duration'
		self.paths.last_backup_log_file     = '.org.licorn.backups.last_log'
		self.paths.statistics_file          = '.org.licorn.backups.statistics'
		self.paths.statistics_duration_file = '.org.licorn.backups.statistics.duration'
		self.paths.increments_file          = '.org.licorn.backups.increments'
		self.paths.increment_sizes_file     = '.org.licorn.backups.increments.sizes'
		self.paths.last_backup_file         = '.org.licorn.backups.last_time'
		self.paths.globbing_file_system     = os.path.join(
												settings.config_dir,
												'rdiff-backup-globs.conf')
		self.paths.globbing_file_local      = self._find_local_globbing_filelist()

		# backup is run every day, at 02:00 AM.
		self.settings = LicornConfigObject()
		self.reload_settings()
	def compare_settings(self):
		time     = settings.get(RDIFF_SETTING_TIME, RDIFF_DEFAULT_TIME).strip()
		week_day = settings.get(RDIFF_SETTING_WKDAY, RDIFF_DEFAULT_WKDAY).strip()

		return time != self.settings.time or week_day != self.settings.week_day
	def reload_settings(self, compare=False):
		self.settings.time = settings.get(RDIFF_SETTING_TIME, RDIFF_DEFAULT_TIME).strip()
		self.settings.week_day = settings.get(RDIFF_SETTING_WKDAY, RDIFF_DEFAULT_WKDAY).strip()
		self.settings.hour, self.settings.minute = self.settings.time.split(':')
	def _find_local_globbing_filelist(self):
		""" See if environment variable exists and use it, or return the
			default path for the rdiff-backup configuration.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		filename = os.getenv(RdiffbackupExtension.globbing_env_var_name, None)

		if filename:
			logging.notice(_(u'{0}: using environment variable {1} pointing to '
				'{2} for rdiff-backup configuration.').format(self.name,
					stylize(ST_COMMENT,
							RdiffbackupExtension.globbing_env_var_name),
					stylize(ST_PATH, filename)))
		else:
			filename = (os.path.join(settings.config_dir,
								'rdiff-backup-globs.local.conf'))

		return filename
	def _find_binary(self, binary):
		""" Return the path of a binary on the local system, or ``None`` if
			not found in the :envvar:`PATH`. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

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

		assert ltrace_func(self._trace_name)

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
				self.commands.ionice = [ self.paths.ionice_bin, '-c3' ]
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
			properly.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if 'volumes' in LMC.extensions:

			# will be True if a backup (or stats) is running.
			self.events.running = Event()
			# will be True while the real backup is running, False for stats.
			self.events.backup = Event()

			# will be set if a timer thread is up and running, else false,
			# meaning no backup volume is connected.
			self.events.active = Event()

			# this will be set to the volume we're backing up on
			self.current_operated_volume = None

			# hold a reference inside us too. It doesn't hurt, all volumes
			# are individually locked anyway.
			self.volumes = LMC.extensions.volumes

			from rdiff_backup.Globals import version as rdiff_backup_version

			logging.info(_(u'{0}: extension enabled on top of {1} version '
				u'{2}.').format(self.pretty_name,
								stylize(ST_NAME, 'rdiff-backup'),
								stylize(ST_UGID, rdiff_backup_version)))

			return True

		return False
	def __create_backup_task(self):
		assert ltrace_func(TRACE_RDIFFBACKUP)

		if not self.events.active.is_set():
			self.events.active.set()

			try:
				self.task_id = LMC.tasks.add_task(RDIFF_TASK_NAME,
												'LMC.extensions.rdiffbackup.backup',
												hour=self.settings.hour,
												minute=self.settings.minute,
												week_day=self.settings.week_day).id

				logging.info(_(u'{0}: backup task scheduled.').format(self.pretty_name))

			except exceptions.AlreadyExistsException:
				pass
	def __remove_backup_task(self):

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if self.events.active.is_set():
			# mark us inactive first, else the task deletion protector
			# will forbid the task unscheduling.
			self.events.active.clear()

			try:
				LMC.tasks.del_task(self.task_id)
				del self.task_id

				logging.info(_(u'{0}: backup task un-scheduled.').format(self.pretty_name))

			except:
				pass
	def enable(self):
		""" This method will (re-)enable the extension, if :meth:`is_enabled`
			agrees that we can do it.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		self.enabled = self.is_enabled()

		if self.enabled:
			self.licornd_cruising()

		return self.enabled
	def disable(self):
		""" Disable the extension. This disables everything, even the timer
			thread, dynamically. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if self.events.running.is_set():
			logging.warning(_('{0}: cannot disable now, a backup is in '
				'progress. Please wait until the end and retry.').format(
					self.pretty_name))
			return False

		# Try to avoid any race-collision with any operation beiing
		# relaunched while we stop.
		self.events.running.set()

		self.__remove_backup_task()

		# clean the thread reference in the daemon.
		self.licornd.clean_objects()

		del self.volumes

		del self.events.backup

		self.enabled = False

		self.events.running.clear()
		del self.events.running

		return True
	def running(self):
		""" Returns ``True`` if a backup is currently running, else ``False``. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

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
		assert ltrace_func(TRACE_RDIFFBACKUP)

		return True
	def enabled_volumes(self, count_unmounted=False):
		""" Returns a list of Licorn® enabled volumes. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		return [ volume for volume in self.volumes
						if volume.enabled and (volume.mount_point
												or count_unmounted) ]

	# The operation status is cached, primarily to avoid a race bug in the WMI:
	# on ejection, the WMI reloads /backup which mounts the volume in turn,
	# which aborts the eject operation...
	#
	# Then, it is cached because its value will never change until next backup.
	# The backup procedure body will force a refresh of it; the loop is looped.
	@cache.cached(cache.one_week)
	@lazy_mounted
	def operations_status(self, volume=None, *args, **kwargs):
		""" Get the status of lastly ran operations. Return it as a dict of
			tuples, containing data organized like this:

			{
				op_code_name: ('Op Friendly Name', (True, False or None), 'operation log'),
				...
			}
					),
				([ 'rdiff-backup', '--list-increments', '--parsable-output',
											self.backup_dir(volume) ],
					),

		"""

		all_status = {}

		for log, op, op_name in (
					(self.paths.last_backup_log_file, '00_last_backup', _('Last Backup')),
					(self.paths.increments_file, '01_incrs', _(u'Increments listing')),
					(self.paths.statistics_file, '02_stats', _(u'Statistics computation')),
				):

			if os.path.exists(os.path.join(volume.mount_point, log + '.failed')):
				all_status[op] = (op_name, False, open(os.path.join(volume.mount_point, log + '.failed')).read().strip())

			elif os.path.exists(os.path.join(volume.mount_point, log)):
				all_status[op] = (op_name, True, open(os.path.join(volume.mount_point, log)).read().strip())

			else:
				all_status[op] = (op_name, None, '')

		return all_status
	@lazy_mounted
	def backup_dir(self, volume=None):
		""" Returns the fixed path for the backup directory of a volume, passed
			as parameter. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		return os.path.join(volume.mount_point, self.paths.backup_directory)
	def find_first_volume_available(self):
		try:
			return self.enabled_volumes(count_unmounted=True)[0]

		except IndexError:
			logging.warning(_(u'{0}: no volume found!').format(
							self.pretty_name))
			return None

	# NOTE: no lazy_mount here, else wmi_main() would crash. There must be
	# some places where we don't automount anything (even in lazy mode).
	#@lazy_mounted
	def backup_enabled(self, volume=None):
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

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if volume.mount_point:
			backup_dir = self.backup_dir(volume)
			return os.path.exists(backup_dir) and os.path.isdir(backup_dir)

		return False
	def backup_enabled_volumes(self):
		""" Returns a list of backup-enabled volumes. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		return [ volume for volume in self.volumes
						if volume.enabled and self.backup_enabled(volume) ]
	def compute_statistics(self, volumes=None):
		""" Launch in the background the :meth:`__rdiff_statistics` method
			on each volume of a
			list passed as parameter, or on all enabled volumes if parameter
			is ``None``.

			It will verify if the volume is Licorn® enabled before running
			anything, and will skip unusable ones.

		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if volumes is None:
			volumes = self.enabled_volumes()

		else:
			for volume in volumes:
				with volume.mount():
					if not volume.enabled:
						volumes.remove(volume)
						logging.info(_(u'Skipped disabled %s.') % volume)

		for volume in volumes:
			workers.service_enqueue(priorities.LOW,
								self.__rdiff_statistics,
								volume=volume)

	# a comfort alias
	statistics = compute_statistics
	@cache.cached(cache.one_day)
	def compute_total_space(self, *args, **kwargs):
		""" This method tries to find the space needed to make a full backup,
			given the full size of the system, and :program:`rdiff-backup`
			exclusions.

			It computes only an estimation, because it ignores ``**`` entries
			in the exclusions files. We consider they don't make such a big
			difference on system with Gb to Tb of data.
		"""

		exclusions = []

		for config_file in (self.paths.globbing_file_system,
							self.paths.globbing_file_local):
			if os.path.exists(config_file):
				for line in open(config_file).readlines():
					if line[0] == '-' and '**' not in line:
						line = line[2:].strip()

						append = True

						for exc in exclusions[:]:
							if line.startswith(exc):
								# line is a subdir, skip and stop here.
								append = False
								break

							if exc.startswith(line):
								exclusions.remove(exc)

						if append:
							exclusions.append(line)

		# TODO: remove local configuration directory sizes.
		return LMC.extensions.volumes.global_system_size(exclude=exclusions)
	@lazy_mounted
	def compute_needed_space(self, volume=None, *args, **kwargs):
		""" Verify how much space is needed on the backup volume to hold the
			next backup.

			If there has been one or more backup before, we
			compute twice the increment average size (just to be sure it fits).

			It no backup ever occured, we compute the size of the current global
			file system. This is far from perfect, but on standard systems (no
			customized configuration file), this is nearing reality.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		logging.info(_(u'{0}: Computing needed space for next backup, '
						u'please wait…').format(self.pretty_name))

		try:
			# Get rdiff-backup sessions to compute averages.
			sessions = sorted(glob.glob(os.path.join(self.backup_dir(volume),
							'rdiff-backup-data', 'session_statistics.*')))

		except (IOError, OSError), e:
			if e.errno == e.ENOENT:
				# There is no backup yet, next will be the first. The volume
				# must hold a nearly complete copy of the file-system.
				return self.compute_total_space(*args, **kwargs)

			else:
				# The problem is worse.
				raise

		# we will calculate the average excluding the FIRST session, which is
		# the original full backup. Using it would make the average of
		# increments wrong.
		#
		# This is particularly true on a system with e.g. 3.5Tb of data backed
		# up and a 10G first increment: with only these 2 backups the average
		# size is 1.33Tb, which is totally inaccurate when trying to guess the
		# next needed space.
		sessions = sessions[1:]

		if sessions == []:
			# There is only one backup done, the first full. We can assume
			# nothing about needed space, just return 10% of total space and
			# pray it will suffice. If the sysadmin sized the backup volume
			# correctly, this is not a problem. Further estimations will be
			# more accurate than this one, which is just an estimation ;-)
			return self.compute_total_space(*args, **kwargs) / 10.0

		# If we reach here, there is more than one backup on the system, we
		# can compute a real estimation of next backups. Just an estimation,
		# though.
		rdiff_command = self.commands.ionice[:]
		rdiff_command.extend(self.commands.nice[:])

		rdiff_command = [ self.paths.binary,
							'--calculate-average' ] + sessions

		out, err = process.execute(rdiff_command)

		for line in out.split('\n'):
			if line.startswith('TotalDestinationSizeChange'):
				return float(line.split()[1])

		# If we didn't already return, there is a strange problem.
		return -1
	@lazy_mounted
	def _has_enough_free_space(self, volume=None):
		""" Return True if the given volume has enough free space to hold
			the next backup. """

		assert ltrace(self._trace_name, '| _has_enough_free_space(%s): %s > %s ? %s' % (
			volume, volume.stats()[0] , self.compute_needed_space(volume),
			volume.stats()[0] > self.compute_needed_space(volume)))

		return volume.stats()[0] > 2 * self.compute_needed_space(volume)
	@lazy_mounted
	def _held_backups(self, volume=None):
		""" Return the number of backups held on a given volume, as an integer. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		try:
			return len(open(os.path.join(volume.mount_point,
								self.paths.increments_file)).readlines())

		except (IOError, OSError), e:
			if e.errno == errno.ENOENT:
				return 0
			else:
				raise e
	@lazy_mounted
	def _backup_history(self, volume=None):

		try:
			return open(volume.mount_point
					+ '/' + self.paths.increment_sizes_file).read().strip()

		except (IOError, OSError), e:
			if e.errno == 2:
				# not ready yet (first backup running, or not yet run)
				return None
			else:
				raise e
	@if_not_already_running_on_this_volume
	def __remove_old_backups(self, volume, older_than):
		""" remove backups in the way rdiff-backup wants it to be done. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		command = self.commands.ionice[:]
		command.extend(self.commands.nice[:])

		rdiff_command = [ self.paths.binary,
							'--remove-older-than', older_than,
							'--verbosity', '0',
							# --force is needed in case there is more than one
							# increment to remove (we don't know how many will
							# be selected, thus we always add --force.
							'--force',
							self.backup_dir(volume) ]

		command.extend(rdiff_command)

		cmd_start = time.time()

		output, error = process.execute(command, dry_run=30
						if self.name in settings.debug else False)

		assert ltrace(TRACE_TIMINGS, 'rdiff-backup clean older than %s on %s: %s.'
							% (older_than, volume, pyutils.format_time_delta(
										time.time() - cmd_start)))

		# FIXME: do this a better way ? keep this in a log ?
		sys.stderr.write(error)
	# NOTE: do not protect this one too.
	def __clean_obsolete_backups(self, volume, *args, **kwargs):

		assert ltrace_func(TRACE_RDIFFBACKUP)

		logging.info(_(u'{0}: cleaning obsolete backup on {1}.').format(
										self.pretty_name, volume))

		self.__remove_old_backups(volume, older_than='1Y')

		logging.info(_(u'{0}: obsolete backup cleaned on {1}.').format(
									self.pretty_name, volume))
	def time_before_next_automatic_backup(self):
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
		assert ltrace_func(TRACE_RDIFFBACKUP)

		#return LMC.tasks.by_name(RDIFF_TASK_NAME).next_running_time
		return LMC.tasks.by_name(RDIFF_TASK_NAME).thread.remaining_time()
	def backup(self, volume=None, force=False):
		""" Start a backup in the background (`NORMAL` priority) and reset the
			backup timer, if no other backup is currently running. Internally,
			this method enqueues the private :meth:`__backup_procedure` method
			in the Service Queue.

			.. note:: 
				* if a backup is already running, another will not be launched
				  over it.

				* if all service threads are busy
				  (which is very unlikely to occur, given how many they are),
				  the backup could eventually be delayed until one service
				  thread is free again.

				* in this very same case, the backup timer would have been
				  reset anyway, leading to a potential desynchronization
				  between the times of the "real" backup event and the timer
				  completion. I find this completely harmless, until proven
				  otherwise (feel free to shed a light on any problem I forgot).

			As a `get inside` demonstration (you can use CLI in normal circumstances),
			you can always launch a manual backup like this::

				licornd> LMC.extensions.rdiffbackup.backup(force=True)
				licornd> [Control-D]
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if volume is None:
			volume = self.find_first_volume_available()

		elif not volume.enabled:
			raise exceptions.BadArgumentError(_(u'Cannot run a backup on '
											u'non-reserved volume {0}. Please '
											u'reserve it first, or choose '
											u'another one.').format(volume.name))

		minimum_interval = settings.get('extensions.rdiffbackup.backup.minimum_interval', 3600*6)

		if minimum_interval < 3600:
			logging.warning(_(u'{0}: minimum backup interval cannot be less than {1}, '
				u'clipping.').format(self.pretty_name, pyutils.format_time_delta(3600)))
			# TODO: rewrite settings when the primitive exists.
			minimum_interval = 360
		if volume:
			if not force and (
					time.time() - self._last_backup_time(volume) < minimum_interval):

				logging.notice(_(u'{0}: not backing up on {1}, last backup is '
								u'less than {2}.').format(self.pretty_name,	volume, 
									pyutils.format_time_delta(minimum_interval)))
				return

			workers.service_enqueue(priorities.NORMAL,
										self.__backup_procedure,
										volume=volume, force=force)

		else:
			logging.warning(_(u'Sorry, no backup volumes available.'))
	# WARNING: do not protect/lock/lazy_mount this one.
	def __backup_procedure(self, volume, force=False, *args, **kwargs):
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

		assert ltrace_func(TRACE_RDIFFBACKUP)

		already_cleaned = self.__backup_check_space(volume, force=force)

		self.__backup_procedure_body(volume)

		if not already_cleaned:
			self.__clean_obsolete_backups(volume)

		self.__rdiff_statistics(volume)

		# force the cache to expire and update the operations status for the
		# WMI and other interfaces. Wait one second to be sure the current
		# backup procedure releases the volume, because the operations status
		# will re-acquire it.
		workers.service_enqueue(priorities.LOW, self.operations_status, volume,
										cache_force_expire=True, job_delay=1.0)

		assert ltrace(self._trace_name, '< __backup_procedure()')
	@if_not_already_running_on_this_volume
	def __backup_procedure_body(self, volume):

		assert ltrace_func(TRACE_RDIFFBACKUP)

		self.events.backup.set()

		LicornEvent('backup_started', volume=volume).emit()

		logging.notice(_(u'{0}: running backup on {1}, '
						u'please wait…').format(
							self.pretty_name, volume))

		backup_directory = self.backup_dir(volume)

		if not os.path.exists(backup_directory):
			os.mkdir(backup_directory)
			logging.progress(_(u'{0}: created directory {1}.').format(
				self.pretty_name, stylize(ST_PATH, backup_directory)))

		command = self.commands.ionice[:]
		command.extend(self.commands.nice[:])

		rdiff_command = [ self.paths.binary, '--exclude-sockets',
						'--exclude-fifos', '--exclude-device-files',
						'--verbosity', '2', '/', self.backup_dir(volume) ]

		# We list the local customized file first, in order to include it
		# after the system one if both are present; the first takes precedence
		# on the second.
		for config_file in (self.paths.globbing_file_local,
							self.paths.globbing_file_system):
			if os.path.exists(config_file):
				rdiff_command.insert(1, config_file)
				rdiff_command.insert(1, '--include-globbing-filelist')

			else:
				logging.warning(_(u'{0}: configuration file {1} '
									u'does not exist.').format(
										self.pretty_name,
										stylize(ST_PATH, config_file)))

		command.extend(rdiff_command)

		self.__write_last_backup_file(volume)

		assert ltrace(self._trace_name, '  executing %s, please wait.' %
													' '.join(command))
		backup_start = time.time()

		outlog = os.path.join(volume.mount_point, self.paths.last_backup_log_file)
		errlog = os.path.join(volume.mount_point, self.paths.last_backup_log_file + '.failed')

		output, errors = process.execute(command, dry_run=10
													if self.name in settings.debug
													else False)

		assert ltrace(TRACE_TIMINGS, 'rdiff-backup duration on %s: %s.'
							% (volume, pyutils.format_time_delta(
										time.time() - backup_start)))

		if not self.name in settings.debug:
			fsapi.remove_files(outlog, errlog)

			with open(outlog, 'w') as f:
				f.write(output)

			if errors:
				with open(errlog, 'w') as f:
					f.write(errors)

				LicornEvent('backup_failed', errorlog=errlog).emit()

		self.events.backup.clear()

		LicornEvent('backup_ended', volume=volume, log=output).emit()

		logging.notice(_(u'{0}: backup procedure terminated on {1}.').format(
									self.pretty_name, volume))
	# NOTE: do not protect this one: all called methods are already protected.
	def __backup_check_space(self, volume, force=False):

		assert ltrace_func(TRACE_RDIFFBACKUP)

		already_cleaned = False

		if force:
			logging.warning(_(u'Forcing backup on volume {0}, '
							u'free space ckeck ignored. This could lead to '
							u'incomplete backups, please use with care!'
								).format(stylize(ST_PATH, volume.device)))
		else:
			nb_backups = self._held_backups(volume)

			logging.progress(_(u'{0}: computing needed space for next '
									u'backup, please wait.').format(self.pretty_name))

			while not self._has_enough_free_space(volume):
				if nb_backups < 2:
					# TODO: implement an alert mechanism !!
					raise RdiffbackupException(_(u'Volume {0} does not have '
							u'enough free space or is not big enough to hold '
							u'more than two backups. '
							u'Space needed: {1}; free space: {2}.').format(
								volume,
								pyutils.bytes_to_human(
											self.compute_needed_space(volume),
											as_string=True),
								pyutils.bytes_to_human(
											volume.stats()[0], as_string=True)))

				nb_backups -= 1
				# remove the last backup on the volume (see beginning of this
				# file for explanation of rdiff-backup syntax).
				self.__remove_old_backups(volume, older_than=str(nb_backups) + 'B')
				self.__rdiff_statistics(volume)
				already_cleaned = True

		return already_cleaned
	@lazy_mounted
	def __write_last_backup_file(self, volume=None):
		""" Put :func:`time.time` in the last backup file. This file is here
			to avoid doing more than one backup per hour.

			:param volume: the :class:`~licorn.extensions.volumes.Volume` you
				want to update last backup file onto.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		last_backup_file = (volume.mount_point
									+ '/' + self.paths.last_backup_file)
		open(last_backup_file, 'w').write(str(time.time()))
		logging.progress(_(u'{0}: updated last backup file {1}.').format(
			self.pretty_name, stylize(ST_PATH, last_backup_file)))
	@if_not_already_running_on_this_volume
	def __rdiff_statistics(self, volume, *args, **kwargs):
		""" Compute statistics on a given volume. This method internally
			launches :program:`rdiff-backup-statistics` multiple times to
			pre-compute statistics and save them in hidden files on the
			volume, making outputs always ready and CPU friendly
			(the statistics operation is very lenghty and CPU intensive, its
			output must be cached in a file between backups).
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		logging.notice(_(u'{0}: computing statistics on {1}, '
			u'please wait…').format(self.pretty_name, volume))

		LicornEvent('backup_statistics_started', volume=volume).emit()

		start_time = time.time()
		for command_line, output_file in (
				([ 'rdiff-backup-statistics', '--quiet',
											self.backup_dir(volume) ],
					self.paths.statistics_file),
				([ 'rdiff-backup', '--list-increments', '--parsable-output',
											self.backup_dir(volume) ],
					self.paths.increments_file),
				([ 'rdiff-backup', '--list-increment-sizes',
											self.backup_dir(volume) ],
					self.paths.increment_sizes_file)
			):

			outlog = os.path.join(volume.mount_point, output_file)
			errlog = os.path.join(volume.mount_point, output_file + '.failed')

			command = self.commands.ionice[:]
			command.extend(self.commands.nice)
			command.extend(command_line)

			assert ltrace(self._trace_name, 'executing %s, please wait.' % command)

			output, errors = process.execute(command, dry_run=10
												if self.name in settings.debug
												else False)

			if not self.name in settings.debug:
				# FIXME: we should not remove it, but rename it to "*.last"
				fsapi.remove_files(outlog, errlog)

				with open(outlog, 'w') as f:
					f.write(output)

				if errors:
					with open(errlog, 'w') as f:
						f.write(errors)

					LicornEvent('backup_statistics_failed', logfile=errlog).emit()

		end_time = time.time()

		self.__record_statistics_duration(volume, end_time - start_time)

		assert ltrace(TRACE_TIMINGS, '%s duration on '
						'%s: %s.' % (' '.join(command_line[:2]), volume,
						pyutils.format_time_delta(end_time - start_time)))

		LicornEvent('backup_statistics_ended', volume=volume).emit()

		logging.notice(_(u'{0}: statistics computation '
						u'finished on {1}.').format(
							self.pretty_name, volume))

		return True
	def __record_statistics_duration(self, volume, duration):
		""" This methods does nothing yet.

			.. TODO:: to be implemented.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)
		pass
	@lazy_mounted
	def _last_backup_time(self, volume=None):
		""" Return the contents of the "last backup file" of a given volume as
			a float, for delta-between-backup computations.

			:param volume: the :class:`~licorn.extensions.volumes.Volume` you
				want last backup time from.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		try:
			return float(open(volume.mount_point +
						'/' + self.paths.last_backup_file).read().strip())
		except ValueError:
			# empty or corrupted file
			return 0.0
		except (IOError, OSError), e:
			if e.errno == 2:
				return 0.0
	@lazy_mounted
	def _backup_informations(self, volume=None):
		""" Return an HTML string for backup information. """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if type(volume) == types.StringType:
			volume = self.volumes[volume]

		return (self._last_backup_time(volume),
				time.time() - self._last_backup_time(volume),
				self.time_before_next_automatic_backup())
	@events.callback_method
	@only_if_enabled
	def licornd_cruising(self, *args, **kwargs):
		""" When licornd is ready, create the timer thread and eventually
			start a backup (the thread will decide).

			Putting this code here in an event callback allow not starting
			a backup during the daemon initial checks without doing convoluted
			things.
		"""

		if self.enabled_volumes() != []:
			self.__create_backup_task()

		else:
			# the backup task is a saved task, and as such it has been
			# restored at daemon relaunch. We need to unload it if there
			# not backup volumes.
			self.__remove_backup_task()

		workers.service_enqueue(priorities.LOW, self.compute_total_space)

	@events.handler_method
	def task_pre_add(self, *args, **kwargs):
		""" This is a very bare method to protect our own task from deletion
			in a runtime daemon. But, hey: it works ;-) """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if kwargs.pop('task').name == RDIFF_TASK_NAME and not (
							self.enabled and self.events.active.is_set()):
			raise exceptions.LicornStopException(_(u'No need to schedule the '
													u'autobackup task yet.'))

	@events.handler_method
	def task_pre_del(self, *args, **kwargs):
		""" This is a very bare method to protect our own task from deletion
			in a runtime daemon. But, hey: it works ;-) """

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if kwargs.pop('task').name == RDIFF_TASK_NAME and (
								self.enabled and self.events.active.is_set()):
			raise exceptions.LicornStopException(_(u'Removing the '
										u'auto-backup task is not allowed.'))
	@events.handler_method
	@only_if_enabled
	def volume_mounted(self, *args, **kwargs):
		""" Trigerred when a volume is mounted on the system. It will check
			if any of the connected (mounted or not) volumes is enabled for
			Licorn®, and will create the timer thread, if not already present.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if self.enabled_volumes(count_unmounted=True):
			self.__create_backup_task()
	@events.handler_method
	@only_if_enabled
	def volume_unmounted(self, *args, **kwargs):
		""" Trigerred when a volume is unmounted from the system. If no
			Licorn® enabled volume remains connected (mounted or not), this
			method will stop the timer thread, if not already stopped.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if not self.enabled_volumes(count_unmounted=True):
			self.__remove_backup_task()
	# NOTE: we don't need a volume_added_callback(): any added volume gets
	# mounted right away if compatible; thus volume_mounted_callback() will
	# catch it. Any added but not compatible (thus not mounted) volume will
	# be of no help, we can safely ignore it.
	@events.handler_method
	@only_if_enabled
	def volume_removed(self, *args, **kwargs):
		""" Trigerred when a volume is disconnected from the system. If no
			other Licorn® enabled volume remains connected (mounted or not),
			this method will stop the timer thread, if not already stopped.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if not self.enabled_volumes(count_unmounted=True):
			self.__remove_backup_task()
	@events.handler_method
	@only_if_enabled
	def volume_enabled(self, *args, **kwargs):
		""" Trigerred when a new volume is enabled on the system; will blindly
			create the timer thread, if not already present.
		"""
		assert ltrace_func(TRACE_RDIFFBACKUP)

		self.__create_backup_task()
	@events.handler_method
	@only_if_enabled
	def volume_disabled(self, *args, **kwargs):
		""" Trigerred when a volume is disconnected from the system. If no
			Licorn® enabled volume remains, this method will stop the timer
			thread, if not already stopped.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if self.enabled_volumes() == []:
			self.__remove_backup_task()
	@events.handler_method
	@only_if_enabled
	def settings_changed(self, *args, **kwargs):
		""" Trigerred when the Licorn® main configuration file changed. If the
			:ref:`backup.interval <backup.interval.en>` changed and the
			timer thread is running, it will be reset with the new interval
			value.

			.. note:: when a dynamic change occur, the timer will be simply
				reset. No sophisticated computation will be done to substract
				the already-passed time from the new interval.
		"""

		assert ltrace_func(TRACE_RDIFFBACKUP)

		if self.events.active.is_set():
			if self.compare_settings():
				self.reload_settings()
				self.__create_backup_task()
				self.__remove_backup_task()

__all__ = ('RdiffbackupException', 'RdiffbackupExtension', )
