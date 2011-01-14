# -*- coding: utf-8 -*-
"""
Licorn extensions: rdiff-backup - http://docs.licorn.org/extensions/rdiff_backup.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, sys, time

from threading import RLock, Event

import gettext
_ = gettext.gettext
gettext.textdomain('licorn')

from licorn.foundations        import logging, exceptions, process, pyutils
from licorn.foundations.styles import *
from licorn.foundations.ltrace import ltrace
from licorn.foundations.base   import Singleton, MixedDictObject, LicornConfigObject

from licorn.core               import LMC
from licorn.daemon.threads     import TriggerTimerThread, TriggerWorkerThread
from licorn.extensions         import LicornExtension
from licorn.extensions.volumes import VolumeException
from licorn.interfaces.wmi     import WMIObject

class RdiffbackupException(exceptions.LicornRuntimeException):
	""" A type of exception to deal with rdiff-backup specific problems.

		.. versionadded:: 1.2.4
	"""
	pass
class RdiffbackupExtension(Singleton, LicornExtension, WMIObject):
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

		self.paths.backup_directory         = 'licorn.backups'
		self.paths.backup_duration_file     = '.org.licorn.backups.duration'
		self.paths.statistics_file          = '.org.licorn.backups.statistics'
		self.paths.statistics_duration_file = '.org.licorn.backups.statistics.duration'
		self.paths.increments_file          = '.org.licorn.backups.increments'
		self.paths.increment_sizes_file     = '.org.licorn.backups.increments.sizes'
		self.paths.last_backup_file         = '.org.licorn.backups.last_time'
		self.paths.globbing_file            = self._find_globbing_filelist()

		self.create_wmi_object(uri='/backups', name=_('Backups'),
				alt_string=_('Manage backups and restore files'),
				context_menu_data=(
					(_('Run backup'), '/backups/run',
						_('Run a system incremental backup now'),
						'ctxt-icon', 'icon-add'),
					(_('Explore backups'), '/backups/search',
						_('Search in backup history for files or '
							'directories to restore'),
						'ctxt-icon', 'icon-export'),
					(_('Settings'), '/backups/settings',
						_('Manage system backup settings'),
						'ctxt-icon', 'icon-energyprefs'),
				)
			)
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
							# first backup starts 1 minutes later.
							time=(time.time()+60.0)
							)
			self.threads.auto_backup_worker = TriggerWorkerThread(
							trigger_event=self.events.start_backup,
							target=self.__backup_procedure,
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
			logging.notice('%s: computing statistics on %s, '
				'please wait.' % (self.name, volume))

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

				assert ltrace(self.name, 'executing %s, please wait.' % command)

				output, errors = process.execute(command)

				open(volume.mount_point + '/' + output_file, 'w').write(output)

			end_time = time.time()

			self._record_statistics_duration(volume, end_time - start_time)

			assert ltrace('timings', '%s duration on '
				'%s: %s.' % (' '.join(command_line[:2]), volume,
					pyutils.format_time_delta(end_time - start_time)))


			return True
	def _record_statistics_duration(self, volume, duration):
		""" TODO. """

		pass

	def _backup_dir(self, volume):
		return volume.mount_point + '/' + self.paths.backup_directory
	def _backup_enabled(self, volume):
		""" Test if a volume is backup-enabled or not (the backup directory is
			present on it.

			.. note:: This method won't automatically mount connected but
				unmounted volumes, to avoid confusing the user, displaying
				an information as if the volumes was mounted, whereas it
				is not (remember locking a volume will automatically mount
				it, and unmount it right after the operation; in queries
				it will appear mounted, even if the situation has changed
				just after).

		"""
		if volume.mount_point:
			backup_dir = self._backup_dir(volume)
			return os.path.exists(backup_dir) and os.path.isdir(backup_dir)

		return False
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

		logging.progress('>> please implement volumes._compute_needed_space(self, ...)')
	def _remove_old_backups(self, volume, size=None, number=None,
															older_than=None):
		logging.progress('>> please implement volumes._remove_old_backups(self, ...)')
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
	def backup(self, volume=None, force=False):
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
		self.threads.auto_backup_worker.trigger(volume=volume, force=force)
		logging.notice('%s: started backup in the background; next in %s.' % (
						self.name, self.time_before_next_automatic_backup()))
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

			.. note:: If a backup takes more than the configured
				:term:`backup interval <backup.interval>` to complete, next
				planned backup will not occur.

			.. warning::
				* **DO NOT CALL THIS METHOD DIRECTLY**. Instead, run
				* If a volume is left is a locked state for any reason,
				  this is currently a problem because not future backup
				  will happen until the lock is released. **TODO:** we should
				  probably make this case more error-proof.
		"""

		first_found = False

		if volume is None:
			try:
				volume = self._enabled_volumes()[0]
				first_found = True

			except IndexError:
				logging.warning2('%s: no volumes to backup onto, '
					'aborting.' % self.name)
				return

		#if volume.locked():
		#	logging.warning('%s: %s already locked, aborting backup' % (
		#		self.name, volume))
		#	return

		with volume:
			if not force and (
					time.time() - self._last_backup_time(volume) <
										LMC.configuration.backup.interval):
				logging.info('%s: not backing up on %s, last backup is '
					'less that one hour.' % (self.name, volume))
				return

			logging.notice('%s: starting backup on%s %s.' % (
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

			rdiff_command = [ self.paths.binary, '--verbosity', '2',
											'--never-drop-acls',
											'/', self._backup_dir(volume) ]

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
			logging.notice('%s: terminated backup procedure on %s.' % volume)
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
	def _wmi__status(self):
		""" Method called from wmi:/, to integrate backup informations on the
			status page. """

		return '<strong>NOTHING YET</strong>'
	def _backup_informations(self, volume, as_string=False):
		""" Return an HTML string for backup information. """
		if as_string:
			return '{last_backup}<br />{next_backup}'.format(
					last_backup=_('Last backup on this volume '
						'occured {0}.').format(
							time.strftime(_("on %A %d %B %Y %H:%M"),
							time.localtime(self._last_backup_time(volume)))),
					next_backup=_("Next backup attempt will occur in {0} "
						"(this page will automatically reload).").format(
						self._countdown('next_backup', 3.0 +
							self.time_before_next_automatic_backup(
								as_string=False))))
		else:
			return (self._last_backup_time(volume) - time.time(),
				self.time_before_next_automatic_backup())
	def _wmi_run(self, uri, http_user, volume=None, force=False, **kwargs):
		""" Run a backup from the WMI. Propose the user to force the
			operation if the last backup is less than one hour. """

		w = self.utils
		title = _('Run a manual backup')

		auto_select = ''
		if volume is None:
			try:
				volume = self._enabled_volumes()[0]
				volume.mount()
				auto_select = ('<div style="text-align: center:">%s</div>'
					% _('Note: auto-selected volume {volume} for next '
						'backup.').format(volume=volume.mount_point))
			except IndexError:
				return (w.HTTP_TYPE_TEXT, w.page(title,
					w.error(_("No volume to backup onto. "
						"Please plug one before starting this procedure."))))
		else:
			volume=self.volumes['/dev/'+volume]

		last_backup_time = time.time() - self._last_backup_time(volume)

		if last_backup_time < LMC.configuration.backup.interval and not force:

			title = _('Run a manual backup on volume {0}').format(
															volume.mount_point)
			data  = w.page_body_start(uri, http_user, self._ctxtnav, title)

			data += w.question(
				_('Recent backup detected'),
				_('{auto_select}<br /><br />The last backup has been run '
					'recently ({last_backup_time}), in less than the '
					'system configured interval ({interval}). Are you '
					'sure you want to force a manual backup now?').format(
						auto_select=auto_select,
						last_backup_time=pyutils.format_time_delta(
								-last_backup_time, use_neg=True),
						interval=pyutils.format_time_delta(
							LMC.configuration.backup.interval)),
				yes_values   = \
					[ _("Run >>"), "/backups/run/%s/force" %
							volume.device.rsplit('/', 1)[1], _("R") ],
				no_values    = \
					[ _("<< Cancel"),   "/backups",      _("C") ])

			return (w.HTTP_TYPE_TEXT,
				w.page(title, data + w.page_body_end()))

		else:
			# we've got to translate the 'force' boolean because WMI doesn't
			# forward them as real boolean (it sends force='force' or None).
			self.backup(volume=volume, force=True if force else False)
			return (self.utils.HTTP_TYPE_REDIRECT,
							self.wmi.successfull_redirect)
	def _wmi_eject(self, uri, http_user, device, **kwargs):
		""" Eject a device, from the WMI. """

		device = '/dev/' + device
		volume = self.volumes[device]
		title  = _("Eject volume {device}").format(device=device)

		if volume.locked():
			backup_info = (_(' (a backup is underway)')
				if self.threads.auto_backup_worker.running()
					and volume.locker is self else
						' (locked by {locker})'.format(
							locker=volume.locker.name))


			return (w.HTTP_TYPE_TEXT, w.page(title,
				w.error(_("Volume is in use{backup_info}, "
					"can't eject it!{rewind}").format(
						backup_info=backup_info,rewind=self.wmi.rewind))))

		self.volumes[device].unmount()
		return (self.utils.HTTP_TYPE_REDIRECT, self.wmi.successfull_redirect)
	def _wmi_main(self, uri, http_user, sort="date", order="asc", **kwargs):
		""" Main backup list (integrates volumes). """
		start = time.time()

		w = self.utils

		title = _("System backups")
		data  = w.page_body_start(uri, http_user, self._ctxtnav, '')

		backup_volumes = self._backup_enabled_volumes()

		if backup_volumes == []:

			base_div = ('<div style="font-size:120%; '
				'text-align: justify; margin-left:33%; '
				'margin-right: 33%;">{message}</div>')

			if self.volumes == []:

				data += base_div.format(message=_('No backup volume found. '
					'Please connect your backup volume to your server, for '
					'backup to automatically start.'))

			else:

				data += base_div.format(message=_('No backup found, or all '
					'backup volumes currently unmounted. Next '
					'automatic backup will occur in {countdown}. '
					'Please wait until then, or <a href="{uri}">run a manual '
					'backup now</a>.').format(
						countdown=self._countdown('next_backup', 3.0 +
							self.time_before_next_automatic_backup(
								as_string=False)),
						uri='/backups/run')
					)

			return (w.HTTP_TYPE_TEXT, w.page(title,
				data + w.page_body_end(w.total_time(start, time.time()))))

		#
		# display backup data for each connected volume.
		#

		if self.threads.auto_backup_worker.active():
			backup_status = '<div class="important">{0}</div>'.format(
				_("A backup is currently in progress, "
				"please don't disconnect <strong>{volume}</strong>.").format(
					volume=''.join([ str(vol) for vol in self.volumes
														if vol.locked()])))
		else:
			backup_status = None

		for volume in backup_volumes:
			base_div = ('<h2>{h2title}</h2>\n'
						'<p>{eject_status}</p>\n'
						'<p>{backup_info}</p>\n'
						'<pre style="margin-left:15%; '
						'margin-right: 15%;">'
						'{rdiff_output}</pre>')

			if volume.locked():
				eject_status = ('<span class="small_indicator {eject_css}">'
								'{eject_message}</span>'.format(
									eject_css='impossible',
									eject_message=
										_("Can't eject, backup in progress")))
			else:
				eject_status = ('<span class="small_indicator {eject_css}">'
								'<a href="{eject_uri}">{eject_img}&nbsp;'
								'{eject_message}</a></span>'.format(
									eject_css='possible',
									eject_message=_('Eject the volume'),
									eject_uri=('/backups/eject/'
										+ volume.device.rsplit('/', 1)[1]),
									eject_img=(
										'<img src="/images/22x22/'
										'eject.png" alt="'
										+ _('Eject device icon') + '" />'
									)
								)
							)

			data += base_div.format(
					backup_info=(
						self._backup_informations(volume, as_string=True)
							if backup_status is None else ''),
					h2title=_('Backups on {mount_point}').format(
						mount_point=volume.mount_point),
					eject_status=eject_status,
					rdiff_output=open(volume.mount_point
						+ '/' + self.paths.increment_sizes_file).read().strip()
				)

		return (w.HTTP_TYPE_TEXT, w.page(title,
			data + w.page_body_end(w.total_time(start, time.time()))))
