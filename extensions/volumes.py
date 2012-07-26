# -*- coding: utf-8 -*-
"""
Licorn extensions: volumes - http://docs.licorn.org/extensions/volumes.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, dbus, pyudev, select, re, errno, functools, itertools

from collections import deque

from licorn.foundations           import logging, exceptions
from licorn.foundations           import process, pyutils, hlstr
from licorn.foundations.events    import LicornEvent
from licorn.foundations.base      import DictSingleton, MixedDictObject, Enumeration
from licorn.foundations.classes   import PicklableObject, SharedResource
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core                import LMC
from licorn.core.classes        import SelectableController
from licorn.extensions          import LicornExtension
from licorn.daemon.threads      import LicornBasicThread

BLKID_re = re.compile(r'([^ =]+)="([^"]+)"')

# decorators:
def self_locked(func):
	""" Volume lock decorator. This will just lock the volume
		`:class:~threading.RLock` for the duration of the decorated method.
	"""
	@functools.wraps(func)
	def decorated(self, *args, **kwargs):

		with self:
			return func(self, *args, **kwargs)

	return decorated
def automount(func):
	""" Volume automount decorator. This will automount the volume, and
		unmount after the end of the operation, if it was previously
		unmounted. Things worth to note:
		 * This decorator **locks the volume** too, by the way (it just
		   includes the functionnality of the `@lock` decorator).
		 * It won't emit the `volume_mounted` and `volume_unmounted`
		   events, because the volume will be automatically unmounted
		   at the end of original method execution if it wasn't previously
		   mounted, so other threads must not react to the auto-mount.
	"""
	@functools.wraps(func)
	def decorated(self, *args, **kwargs):

		with self:
			auto_unmount = False

			if self.mount_point is None:
				assert ltrace(self._trace_name, '  volume %s auto-mounting.' % self)
				self.mount(emit_event=False)
				auto_unmount = True

			try:
				return func(self, *args, **kwargs)

			finally:
				if auto_unmount:
					assert ltrace(self._trace_name, '  volume %s auto-unmounting.' % self)
					self.unmount(emit_event=False)

	return decorated
class UdevMonitorThread(LicornBasicThread):
	""" Handles the :command:`udev` connection and events.

		Useful information (`udev` dumps):

		* for a device (not handled yet)::

			looking at device '/devices/pci0000:00/0000:00:11.0/0000:02:03.0/usb1/1-1/1-1:1.0/host15/target15:0:0/15:0:0:0/block/sdb':
			KERNEL=="sdb"
			SUBSYSTEM=="block"
			DRIVER==""
			ATTR{range}=="16"
			ATTR{ext_range}=="256"
			ATTR{removable}=="1"
			ATTR{ro}=="0"
			ATTR{size}=="246016"
			ATTR{alignment_offset}=="0"
			ATTR{discard_alignment}=="0"
			ATTR{capability}=="51"
			ATTR{stat}=="      53      168      417      156        0        0        0        0        0      156      156"
			ATTR{inflight}=="       0        0"

		* for a partition::

			looking at device '/devices/pci0000:00/0000:00:11.0/0000:02:03.0/usb1/1-1/1-1:1.0/host15/target15:0:0/15:0:0:0/block/sdb/sdb1':
			KERNEL=="sdb1"
			SUBSYSTEM=="block"
			DRIVER==""
			ATTR{partition}=="1"
			ATTR{start}=="95"
			ATTR{size}=="245921"
			ATTR{alignment_offset}=="0"
			ATTR{discard_alignment}=="4294918656"
			ATTR{stat}=="      43      168      337      124        0        0        0        0        0      124      124"
			ATTR{inflight}=="       0        0"


		.. versionadded:: 1.2.4
	"""
	def __init__(self, *args, **kwargs):
		assert ltrace(TRACE_VOLUMES, '| UdevMonitorThread.__init__()')

		kwargs['tname'] = 'extensions.volumes.UdevMonitor'

		LicornBasicThread.__init__(self, *args, **kwargs)

		# set daemon in case we take too much time unihibiting udisks
		# while daemon is stopping.
		self.daemon = True
		self.udev_monitor = pyudev.Monitor.from_netlink(pyudev.Context())
		self.udev_monitor.filter_by(subsystem='block')
		self.udev_monitor.enable_receiving()
		self.udev_fileno = self.udev_monitor.fileno()
		self.prevented_actions = deque()
	def prevent_action_on_device(self, action, device):
		self.prevented_actions.append((action, device))
	def run_action_method(self):
		""" This method is meant to be called in the while loop of the default
			:meth:`~licorn.daemon.threads.LicornBasicThread.run` method of
			the :class:`~licorn.daemon.threads.LicornBasicThread`.
		"""

		# this should be a level2 ltrace...
		#assert ltrace(TRACE_VOLUMES, '| UdevMonitorThread.run_func()')

		readf, writef, errf = select.select([self.udev_fileno], [], [])

		if readf:
			action, device = self.udev_monitor.receive_device()

			if (action, device.device_node) in self.prevented_actions:
				self.prevented_actions.remove((action, device.device_node))
				assert ltrace(TRACE_VOLUMES, '  skipped prevented action '
								'%s on device %s.' % (action, device))
				return

			try:
				assert ltrace(TRACE_VOLUMES, '| udev action %s received for device '
							'%s (%s).' % ((stylize(ST_ATTR, action),
								stylize(ST_PATH, device),
								', '.join(attr for attr in device.attributes))))

				if action == 'add':
					if 'partition' in device.attributes:
						LMC.extensions.volumes.add_volume_from_device(device)

				elif action == 'change':
					if 'partition' in device.attributes:

						# TODO: implement a real change method...
						LMC.extensions.volumes.unmount_volumes([device.device_node])
						LMC.extensions.volumes.del_volume_from_device(device)
						LMC.extensions.volumes.add_volume_from_device(device)

					else:
						logging.progress(_(u'{0}: unhandled action {1} for '
							u'device {2} ({3}).').format(self.name, action,
								device, ', '.join(attr
									for attr in device.attributes)))

				elif action == 'remove':
					LMC.extensions.volumes.del_volume_from_device(device)

				else:
					logging.progress(_(u'{0}: unknown action {1} for '
						u'device {2} ({3}).').format(
						self.name, action, device,
						', '.join(attr for attr in device.attributes)))

			except (IOError, OSError), e:
				if e.errno != errno.ENOENT:
					# "no such file or dir" happens sometimes on some devices.
					# experienced on NTFS partitions (other types don't trigger
					# the problem).
					raise
class VolumeException(exceptions.LicornRuntimeException):
	""" Just an exception about Volumes specific problems.

		.. versionadded:: 1.2.4
	"""
	pass
class Volume(PicklableObject, SharedResource):
	""" A single volume object.

		.. note:: This class is individually locked because :class:`Volume`
			can be accessed through multiple extensions (most notably
			:class:`rdiff-backup <licorn.extensions.rdiffbackup.RdiffbackupExtension>`
			which can take ages to complete).

		.. versionadded:: 1.2.4
	"""

	# core controller search attribute
	_id_field = 'device'

	_lpickle_ = {
			'by_name' : [ 'controller' ],
			'to_drop' : [ 'lock' ],
		}

	# these options mimic the udisks ones.
	mount_options = {
		'vfat'     : ("shortname=mixed", "dmask=0077", "utf8=1", "showexec"),
		'ntfs'     : ("dmask=0077", "fmask=0177"),
		'iso9660'  : ("iocharset=utf8", "mode=0400", "dmode=0500"),
		'udf'      : ("iocharset=utf8", "umask=0077"),
		# acl and user_xattr are 'built-in' for btrfs; 'errors=remount-ro' is unrecognized
		'btrfs'    : ('noatime', 'nodev', 'suid', 'exec',),
		'xfs'      : ('acl', 'user_xattr', 'noatime', 'errors=remount-ro', 'nodev', 'suid', 'exec',),
		'jfs'      : ('acl', 'user_xattr', 'noatime', 'errors=remount-ro', 'nodev', 'suid', 'exec',),
		'ext2'     : ('acl', 'user_xattr', 'noatime', 'errors=remount-ro', 'nodev', 'suid', 'exec',),
		'ext3'     : ('acl', 'user_xattr', 'noatime', 'errors=remount-ro', 'nodev', 'suid', 'exec',),
		'ext4'     : ('acl', 'user_xattr', 'noatime', 'errors=remount-ro', 'nodev', 'suid', 'exec',),
		'reiserfs' : ('acl', 'user_xattr', 'noatime', 'errors=remount-ro', 'nodev', 'suid', 'exec',),
	}
	#: Fixed path where removable volumes should be mounted. Currently set to
	#: ``/media/`` (with the final '/' to speed up strings concatenations).
	mount_base_path = u'/media/'

	#: The name of the special file which indicates the volume is reserved.
	#: Currently ``/.org.licorn.reserved_volume`` (with the leading '/' to
	#: speed up strings concatenations).
	enabler_file    = u'/.org.licorn.reserved_volume'
	def __init__(self, kernel_device, fstype, guid, label,
									mount_point=None, supported=True,
									volumes_extension=None):

		super(Volume, self).__init__()

		self.device      = kernel_device
		self.label       = label
		self.fstype      = fstype
		self.guid        = guid
		self.mount_point = mount_point
		self.supported   = supported
		self.controller  = volumes_extension

		if mount_point:
			self.enabled = os.path.exists(self.mount_point + Volume.enabler_file)

		else:
			self.enabled = None

		assert ltrace(TRACE_VOLUMES, '| Volume.__init__(%s, %s, enabled=%s)' % (
			self.name, self.mount_point, self.enabled))
	@property
	def name(self):
		""" Sometimes, a volume doesn't have a label.
			In this case we return the guid. """

		if self.label != '':
			return self.label

		return self.guid
	def __str__(self):
		return _(u'volume {0}[{1}]{2}').format(
					stylize(ST_DEVICE, self.device),
					stylize(ST_ATTR, self.fstype),
					_(u' (on %s)') % stylize(ST_PATH, self.mount_point)
						if self.mount_point else _(' (not mounted)'))
	def locked(self):
		return self.busy()
	def __compute_mount_point(self):
		if self.label:
			self.mount_point = Volume.mount_base_path + self.label

			# avoid overmounting another volume with the same label.
			mount_point_base = self.mount_point
			counter = 1
			while os.path.exists(self.mount_point):
				self.mount_point = _(u'{base} {counter}').format(
								base=mount_point_base, counter=counter)
				counter += 1

		else:
			# overmounting is very unlikely to happen with guid...
			self.mount_point = Volume.mount_base_path + self.guid
	@automount
	def stats(self):
		""" See http://docs.python.org/library/os.html#os.statvfs for
			details.
			f_bsize, f_frsize, f_blocks, f_bfree, f_bavail, f_files, f_ffree, f_favail, f_flag, f_namemax
		"""
		mpt_stat = os.statvfs(self.mount_point)

		return (mpt_stat.f_bavail * mpt_stat.f_bsize * 1.0,
				mpt_stat.f_blocks * mpt_stat.f_bsize * 1.0)
	@automount
	def enable(self, **kwargs):
		""" Reserve a volume for Licorn® usage by placing a special hidden
			file at the root of it.

			:param kwargs: **not used**, but present because this method is
				meant to be called via :meth:`VolumesExtension.volumes_call`,
				which can use any number of arguments.
		"""

		if self.supported:
			if os.path.exists(self.mount_point + Volume.enabler_file):

				logging.info(_(u'{0}: Licorn® usage already enabled on {1}.'
					).format(stylize(ST_NAME, 'volumes'),
						stylize(ST_PATH, self.mount_point)))
			else:
				open(self.mount_point + Volume.enabler_file, 'w').write('\n')

				self.enabled = True

				logging.notice(_(u'{0}: enabled Licorn® usage on {1}.'
					).format(stylize(ST_NAME, 'volumes'),
						stylize(ST_PATH, self.mount_point)))

				LicornEvent('volume_enabled', volume=self).emit()
		else:
			logging.warning(_(u'{0}: cannot enable Licorn® usage on {1} '
				u'(unsupported FS {2}).').format(stylize(ST_NAME, 'volumes'),
					stylize(ST_PATH, self.mount_point),
					stylize(ST_PATH, self.fstype)))
	@automount
	def disable(self, **kwargs):
		""" Remove the special file at the root of the volume and thus unmark
			it reserved for Licorn® usage.

			:param kwargs: **not used**, but present because this method is
				meant to be called via :meth:`VolumesExtension.volumes_call`,
				which can use any number of arguments.
		"""

		if os.path.exists(self.mount_point + Volume.enabler_file):
			# NOTE: the event must be sent *after* disabling the volume,
			# else other depending extensions will find it still active
			# if they test the `enabled` attribute.

			os.unlink(self.mount_point + Volume.enabler_file)

			self.enabled = False

			LicornEvent('volume_disabled', volume=self).emit()

			logging.notice(_(u'{0}: disabled Licorn® usage on {1}.').format(
				stylize(ST_NAME, 'volumes'), stylize(ST_PATH, self.mount_point)))

		else:
			logging.info(_(u'{0}: Licorn® usage already disabled on {1}.').format(
			stylize(ST_NAME, 'volumes'), stylize(ST_PATH, self.mount_point)))
	def mount(self, emit_event=True, *args, **kwargs):
		""" Mount a given volume, after having created its mount point
			directory if needed. This method simply calls the :command:`mount`
			program via the :func:`~licorn.foundations.process.execute`
			function. After the mount, update the :attr:`~Volume.enabled`
			attribute according to the presence of the
			:attr:`~Volume.enabler_file`.

			Volume is mounted with file-system options
			:option:`acl`, :option:`user_xattr`, :option:`noatime`,
			:option:`errors=remount-ro`, :option:`nodev`, :option:`suid`,
			:option:`exec` (this is a fixed parameter and can't currently be
			modified; this could change in the near future).

			.. note::
				* if the volume is already mounted, nothing happens and
				  the method simply returns `self` to be compatible with
				  context-managers-related `with volume.mount()` calls.
				* The mount point creation heuristics take care of already
				  existing mount points, and will find a unique and not currently
				  taken mount point directory name in any case.
			"""

		assert ltrace(TRACE_VOLUMES, '| Volume.mount(%s, current_mount_point=%s)' % (
											self.device, self.mount_point))

		# to be compatible with the @self_locked decorator without blocking,
		# the real part of this method lies in `self.__mount()`.
		if self.mount_point:
			return self

		return self.__mount(emit_event, *args, **kwargs)
	@self_locked
	def __mount(self, emit_event=True, *args, **kwargs):
		""" The real mount procedure. """
		assert ltrace(TRACE_VOLUMES, '| Volume.__mount(%s, current_mount_point=%s)' % (
											self.device, self.mount_point))
		self.__compute_mount_point()

		if not os.path.exists(self.mount_point):
			os.makedirs(self.mount_point)
			logging.info(_(u'{0}: created mount point {1}.').format(
				stylize(ST_NAME, 'volumes'),
				stylize(ST_PATH, self.mount_point)))

		if self.supported:
			mount_cmd = [ 'mount', '-t', self.fstype, '-o',
				','.join(Volume.mount_options[self.fstype]),
				self.device, self.mount_point ]

		else:
			# probably VFAT, NTFS or ISO9660. We need to find the
			# user at console and give the device to him.

			other_mount_options = ''

			# TODO: use ConsoleKit or whatever is better than this. As
			# of 20110420, I couldn't find easily what is deprecated
			# and what should officially be used to find the user at
			# console. Any hint is welcome. At least, this
			# implementation is very simple and works on Ubuntu
			# (tested on Maverick).
			if os.path.isdir('/var/run/console'):
				for entry in os.listdir('/var/run/console'):
					try:
						user = LMC.users.by_login(entry)
						other_mount_options = ',uid=%s,gid=%s' % (
									user.uidNumber, user.gidNumber)
						break
					except KeyError:
						pass

			mount_cmd = [ 'mount', '-t', self.fstype, '-o',
				'noatime,errors=remount-ro,'
					+ ','.join(Volume.mount_options[self.fstype])
					+ other_mount_options,
				self.device, self.mount_point ]

		assert ltrace(TRACE_VOLUMES, '| %s' % ' '.join(mount_cmd))

		output = process.execute(mount_cmd)[1].strip()

		if output:
			logging.warning(_(u'{0}: {1}').format(
							stylize(ST_NAME, 'volumes'), output))

		# This must be tested before the event is emitted.
		if self.supported:
			self.enabled = os.path.exists(self.mount_point + Volume.enabler_file)

		if emit_event:
			LicornEvent('volume_mounted', volume=self).emit()

		logging.notice(_(u'{0}: mounted device {1}({2}) at {3}.').format(
						stylize(ST_NAME, 'volumes'),
						stylize(ST_DEVICE, self.device),
						stylize(ST_DEVICE, self.fstype),
						stylize(ST_PATH, self.mount_point)))

		return self
	@self_locked
	def unmount(self, force=False, emit_event=True):
		""" Unmount a volume and remove its mount point directory. """

		assert ltrace(TRACE_VOLUMES, '| Volume.unmount(%s, %s)' % (
											self.device, self.mount_point))

		if self.mount_point:
			umount_cmd = [ 'umount', self.device ]

			# self.workers is always at least equal to 1 here, because the
			# unmounting thread is considered a worker, too. We can't test
			# self.busy(), it would always be True.
			if len(self.workers) > 1 and not force:
				logging.warning(_('{0}: still got workers: {1}.').format(self,
								', '.join(w.name for w in self.workers)))

				raise VolumeException(_('Cannot unmount {0}, still busy in Licorn®.').format(self))

			if force:
				umount_cmd.insert(1, '-f')

			# the traditional specific fixes and workarounds...
			if self.fstype == 'ntfs':
				self.controller.threads.udevmonitor.prevent_action_on_device('change', self.device)

			# TODO: Import cdll from ctypes. Then load your os libc, then use libc.mount()
			output = process.execute(umount_cmd)[1].strip()

			old_mount_point  = self.mount_point

			# self.mount_point must be None before the event is emitted.
			self.mount_point = None

			if output:
				logging.warning(_(u'{0}: {1}').format(
								stylize(ST_NAME, 'volumes'), output))
			else:
				if emit_event:
					LicornEvent('volume_unmounted', volume=self).emit()

				logging.notice(_(u'{0}: unmounted device {1} from {2}.').format(
								stylize(ST_NAME, 'volumes'),
								stylize(ST_DEVICE, self.device),
								stylize(ST_PATH, old_mount_point)))


			try:
				os.rmdir(old_mount_point)

			except (OSError, IOError), e:
				if e.errno == errno.EBUSY:
					logging.warning(_(u'{0}({1}): mount point {2} still '
						u'busy after unmounting.').format(
							stylize(ST_NAME, 'volumes'),
							stylize(ST_DEVICE, self.device),
							stylize(ST_PATH, old_mount_point)))

				elif e.errno != errno.ENOENT:
					logging.warning(_(u'{0}({1}): cannot remove mount '
						u'point {2}: {3}.').format(
							stylize(ST_NAME, 'volumes'),
							stylize(ST_DEVICE, self.device),
							stylize(ST_PATH, old_mount_point), e))

				return False

			logging.info(_(u'{0}: removed directory {1}.').format(
				stylize(ST_NAME, 'volumes'),
				stylize(ST_PATH, old_mount_point)))
		return True
class VolumesExtension(DictSingleton, LicornExtension, SelectableController):
	""" Handles volumes via :command:`udev`. Do the auto-mount work.

		Eventually, if :command:`udisks` is available, it will be inhibited
		to avoid double work and interaction conflicts.

		Nice reads along the way:

		* http://packages.python.org/pyudev/index.html
		* http://freedesktop.org/wiki/Software/udisks
		* http://hal.freedesktop.org/docs/udisks/
		* http://mdzlog.alcor.net/2010/06/27/navigating-the-policykit-maze/
		* http://askubuntu.com/questions/16730/default-mount-options-on-auto-mounted-ntfs-partitions-how-to-add-noexec-and-f
		* http://stackoverflow.com/questions/4142690/cant-connect-to-org-freedesktop-udisks-via-dbus-python
		* http://dbus.freedesktop.org/doc/dbus-python/doc/tutorial.html

		Not used but evaluated:

		* http://stackoverflow.com/questions/1138383/python-get-mount-point-on-windows-or-linux
		* http://www.kernel.org/pub/linux/utils/kernel/hotplug/gudev/index.html
		* http://stackoverflow.com/questions/2861098/how-do-i-use-udev-to-find-info-about-inserted-video-media-e-g-dvds

		.. versionadded:: 1.2.4
	"""
	module_depends = [ 'gloop' ]

	_lpickle_ = { 'to_drop' : [ 'cache', 'dbus', 'udisks' ] }

	#: used in `RWI.select()`
	@property
	def object_type_str(self):
		return _(u'volume')
	@property
	def object_id_str(self):
		return _(u'device')
	@property
	def sort_key(self):
		""" The key (attribute or property) used to sort
			User objects from RWI.select(). """
		return 'device'
	def by_device(self, device, strong=False):
		# we need to be sure we get an int(), because the 'uid' comes from RWI
		# and is often a string.
		return self.volumes[device]
	# the generic way (called from RWI)
	by_key  = by_device
	by_id   = by_device
	by_name = by_device

	# end `RWI.select()`
	def guess_one(self, thing):
		try:
			return SelectableController.guess_one(self, thing)

		except KeyError:
			for vol in self:
				if vol.label == thing or vol.mount_point == thing or vol.guid == thing:
					return vol

			raise KeyError(_(u'No Volume by that device name, label, mount_point nor GUID "{0}"!').format(thing))

	def word_match(self, word):
		return hlstr.word_match(word, tuple(itertools.chain(*[
						(vol.device, vol.label, vol.guid) for vol in self])))

	def __init__(self):
		assert ltrace(TRACE_VOLUMES, '| VolumesExtension.__init__()')
		LicornExtension.__init__(self,
			name='volumes',
			controllers_compat=[ 'system' ])

		self.server_only = True

		# NOTE on excluded_mounts: don't handle these mount points,
		# this is left to the distro and they are considered "reserved".
		#
		# NOTE 2: we can't put '/' there, because with the lter test we use, it
		# would match every time. Thus, '/' is handled separately below (see
		# __system_partition() method).
		#
		# FIXME: why don't just 'include' /mnt/* and /media/*, this could be
		# more secure, instead of the risk of forgetting some special mount
		# points.
		#
		# all "none" device do not need to be protected, they can't be matched
		# anyway by a real device name.
		#
		#~ none on /proc type proc (rw,noexec,nosuid,nodev)
		#~ none on /sys type sysfs (rw,noexec,nosuid,nodev)
		#~ fusectl on /sys/fs/fuse/connections type fusectl (rw)
		#~ none on /sys/kernel/debug type debugfs (rw)
		#~ none on /sys/kernel/security type securityfs (rw)
		#~ none on /dev type devtmpfs (rw,mode=0755)
		#~ none on /dev/pts type devpts (rw,noexec,nosuid,gid=5,mode=0620)
		#~ none on /dev/shm type tmpfs (rw,nosuid,nodev)
		#~ none on /var/run type tmpfs (rw,nosuid,mode=0755)
		#~ none on /var/lock type tmpfs (rw,noexec,nosuid,nodev)
		#~ none on /var/lib/ureadahead/debugfs type debugfs (rw,relatime)
		#~ binfmt_misc on /proc/sys/fs/binfmt_misc type binfmt_misc (rw,noexec,nosuid,nodev)
		#~ .host:/ on /mnt/hgfs type vmhgfs (rw,ttl=1)
		#~ none on /proc/fs/vmblock/mountPoint
		#
		self.excluded_mounts = ('/boot', '/home', '/var', '/tmp',
								'/var/tmp',)
		self.excluded_size_mnts = ( '/proc', '/sysfs', '/selinux',
								'/dev', '/sys', '/media', '/mnt', '/srv',)
		self.excluded_devices = ('rootfs', 'none', 'binfmt_misc', 'fusectl',
								'udev', 'gvfs-fuse-daemon', 'devpts', 'sysfs',
								'cgroup', 'proc', 'tmpfs',)

		# accepted FS must implement posix1e ACLs and user_xattr.
		# 'vfat' doesn't, 'fuseblk' can be too much things.
		self.accepted_fs = ('ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'jfs',
																'reiserfs',)

		# TODO: implement LVM2 handlers...
		self.container_fs = ('LVM2_member')

		self.volumes = MixedDictObject('volumes')

		# TODO: add our volumes to notifications, to change the status when
		# administrator touches or unlinks special files in volume's root.
		self.inotifications = []
	def initialize(self):
		""" The extension is available if udev is OK and we can get a list of
			already connected devices.

			Eventually, if udisks is present and enabled, we inhibit it.
		"""

		assert ltrace(self._trace_name, '> initialize()')

		self.cache  = Enumeration('cache')
		self.udisks = Enumeration('udisks')

		# we need the thread to be created to eventually add udisks-related
		# methods a little later.
		self.threads.udevmonitor = UdevMonitorThread()

		system_bus = LMC.extensions.gloop.dbus.system_bus

		try:
			self.udisks.obj = system_bus.get_object(
									"org.freedesktop.UDisks",
									"/org/freedesktop/UDisks")
		except:
			self.udisks.obj = None

		else:
			self.udisks.interface = dbus.Interface(self.udisks.obj,
										'org.freedesktop.UDisks')
			self.udisks.properties = dbus.Interface(self.udisks.obj,
										dbus.PROPERTIES_IFACE)
			self.udisks.props = lambda x: self.udisks.properties.Get(
										'org.freedesktop.UDisks', x)

			self.threads.udevmonitor.pre_run_method = self.__inhibit_udisks
			self.threads.udevmonitor.post_run_method = self.__uninhibit_udisks

		# after that, start a monitor to watch adds/dels.
		self.threads.udevmonitor.start()

		try:
			# get the list of currently connected devices.
			self.rescan_volumes()

			# we are always available, because only relying on udev.
			self.available = True

		except Exception:
			logging.exception(_(u'{0}: not available because'), (ST_NAME, self.name))
			self.available = False

		assert ltrace(self._trace_name, '< initialize(%s)' % self.available)

		return self.available
	def is_enabled(self):
		""" Volumes extension is always enabled if available, return always
			True. """
		assert ltrace(self._trace_name, '| is_enabled() → True')

		logging.info(_(u'{0}: started extension with pyudev v{2} '
			u'on top of udev v{1}.').format(stylize(ST_NAME, self.name),
				stylize(ST_UGID, pyudev.udev_version()),
				stylize(ST_UGID, pyudev.__version__)))

		return True
	def enable(self):
		""" We have nothing to do here. Udisks daemon is already inhibited if we
			are available, and there's nothing more to enable on the system
			(udev is always here, we hope).
		"""

		return True
	def disable(self):
		""" Un-inhibit the udisks daemon to restore full access to other users.

			.. note:: currently, the volume extension CANNOT be disabled (it's
				useless to disable it).
		"""

		#self.rescan()
		return False
	def system_load(self):
		""" Nothing particular to do here. This method exists because this
			extension is attached to the :class:`SystemController` (for pure
			logical purpose, because it doesn't load any data into it). """

		assert ltrace(self._trace_name, '| system_load()')
		pass

	def __inhibit_udisks(self):
		""" TODO """

		assert ltrace(self._trace_name, '| __inhibit_udisks(%s)' % (
				self.udisks.obj is not None))

		if self.udisks.obj is not None \
				and not self.udisks.props('DaemonIsInhibited'):

			self.udisks.cookie = self.udisks.interface.Inhibit()
	def __uninhibit_udisks(self):
		""" TODO """

		assert ltrace(self._trace_name, '| __uninhibit_udisks(%s)' % (
						self.udisks.obj is not None))

		if self.udisks.obj is not None \
				and self.udisks.props('DaemonIsInhibited') \
				and hasattr(self, 'udisks_cookie'):

			# make sure *WE* inhibited udisks, else this won't work.
			self.udisks.interface.Uninhibit(self.udisks.cookie)
	def __update_cache_informations(self):
		""" Read :file:`/proc/mounts` and run :command:`blkid` (the cache file
			:file:`/etc/blkid.tab` has been found to be unreliably updated when
			volumes are pluged in/out) and keep useful informations inside us
			for future use. """

		assert ltrace(self._trace_name, '| __update_cache_informations()')

		self.cache.proc_mounts = {}

		for line in open('/proc/mounts').readlines():
			splitted = line.split(' ')
			# NOTE: when parsing /proc/mounts, we've got to replace these
			# nasty \\040 by the real ascii code. This is because space is
			# the separator in /proc/mounts, and thus in paths it is protected
			# in its \040 octal form.
			self.cache.proc_mounts[splitted[0]] = splitted[1].replace('\\040', '\040')

		self.cache.blkid = {}

		# We can't assume the cache file is up-to-date, i've seen a number of
		# cases on my VM where it was not updated.
		#if os.path.exists('/etc/blkid.tab'):
		#	for line in open('/etc/blkid.tab').readlines():
		#		data = BLKID_re.match(line)
		#		if data:
		#			datadict = data.groupdict()
		#			self.cache.blkid[datadict['device']] = {
		#					'fstype' : datadict['type'],
		#					'uuid'   : datadict['uuid']
		#				}
		#else:
		#~ sudo blkid
		#~ /dev/sda1: UUID="c142d7c1-d7a3-4f61-838a-97b95fb3af46" TYPE="ext4"
		#~ /dev/sda5: UUID="1c7a588d-9c47-4c42-8013-0613bd4681d7" TYPE="swap"
		#~ /dev/sdb1: UUID="8b984ebd-5505-47e2-adb6-3cb21bcb6089" TYPE="ext4" LABEL="SAVE_LICORN"
		#~ /dev/sdb2: LABEL="Untitled" TYPE="hfs"
		#~ /dev/sdb3: LABEL="SAVE 2" UUID="6A7B-1DE6" TYPE="vfat"
		#~ /dev/sdc1: LABEL="LICORN_SAVE" UUID="ba55069a-f48a-424f-b6ce-752209559938" TYPE="ext4"

		for line in process.execute(['blkid'])[0].split('\n'):
			if line == '':
				continue
			device, data = line.split(':', 1)
			fields = BLKID_re.findall(data)
			self.cache.blkid[device] = {}
			for key, value in fields:
					self.cache.blkid[device][key.lower()] = value
	def __system_partition(self, device):
		""" Return ``True`` if the given device or UUID is mounted on one of
			our protected partitions. """

		# NOTE: the current test is much more conservative than just
		# 'if device in excluded_mounts': it takes care of sub-directories
		# system mounted partitions (some external RAID arrays are still
		# seen as external devices, but are handled manually by system
		# administrators.

		mounted = self.cache.proc_mounts.keys()

		if device in mounted:
			return self.cache.proc_mounts[device] == '/' or reduce(pyutils.keep_true,
							(self.cache.proc_mounts[device].startswith(x)
								for x in self.excluded_mounts))

		by_uuid = '/dev/disk/by-uuid/' + self.cache.blkid[device]['uuid']

		if by_uuid in mounted:
			return self.cache.proc_mounts[by_uuid] == '/' or reduce(pyutils.keep_true,
							(self.cache.proc_mounts[by_uuid].startswith(x)
								for x in self.excluded_mounts))


		assert ltrace(self._trace_name,
									'|  __system_partition(device) → False')
		return False

	def rescan_volumes(self):
		""" Get a list of connected block devices from :command:`udev`, record
			them inside us (creating the corresponding :class:`Volume` objects,
			and mount them if not already mounted. """

		assert ltrace(self._trace_name, '| rescan_volumes()')

		udev_context = pyudev.Context()

		kernel_devices = []

		with self.locks._global:
			self_devices = self.volumes.keys()

			for device in udev_context.list_devices(subsystem='block',
														DEVTYPE='partition'):

				kernel_devices.append(device.device_node)
				self.add_volume_from_device(device)

			# remove old devices, wipped away during the time.
			for device_key in self_devices:
				if device_key not in kernel_devices:
					self.del_volume_from_device(self.volumes[device_key])

		del udev_context
	def global_system_size(self, exclude=None):
		""" Sum the occupied space of all mounted FS, except those from the
			current Licorn® `volumes` (which are removable, and thus likely
			to be backup volumes) and return it as a float."""

		if exclude is None:
			exclude = []

		import platform

		if platform.system() == 'Linux':
			self.__update_cache_informations()

			the_total = 0.0

			# First, sum up the used size of all mounted partitions, except
			# the ones that are directly or indirectly excluded.
			for device, mount_point in self.cache.proc_mounts.iteritems():

				# Exclude external volumes, they should never be
				# included in the backups, they *are* the backup :-)
				# Also exclude cryptfs volumes, they are the same size
				# as their holding device, but don't occupy this space.
				if device in self.excluded_devices \
					or device in self \
					or device.endswith('/.Private'):
					continue

				skip_it = False

				# If a mount_point is sub-dir of any of the exclusions, don't
				# even worry adding its size at all. It's the case for all
				# /media or /mnt sub-dirs.
				for excluded in exclude[:]:
					if mount_point.startswith(excluded):

						# if an exactly-matched mount_point is excluded, be
						# sure to remove it from the excluded list, else
						# its `du` would be substracted from the total, in
						# the next for loop.
						if mount_point == excluded:
							exclude.remove(excluded)

						skip_it = True
						break

				if skip_it:
					continue

				mpt_stat = os.statvfs(mount_point)

				the_total += (mpt_stat.f_blocks - mpt_stat.f_bavail) * mpt_stat.f_bsize

			# Then, substract the size of all other exclusions (subdirs,
			# subfiles, whatever). Some will certainly fail to compute (most
			# notably any '**' from librdiff globbing file-lists), but even
			# without them, we will get a fairly good result.
			for excluded in exclude:

				if excluded in self.excluded_size_mnts:
					# don't take any time to `du` these: they contain only
					# mount_points (no local directory nor file), and `du`
					# mounted file-system will be very-time consuming and
					# too-much resource intensive.
					continue

				try:
					du_excl = float(process.execute(['du', '-bs', excluded])[0].split()[0])

				except IndexError:
					# occurs when `du` can't find the target, which is
					# perfectly normal for librdiff exclusions which contain
					# '**' or any other glob pattern.
					continue

				the_total -= du_excl

			assert ltrace(TRACE_VOLUMES, ' | global_system_size(): %s'
											% pyutils.bytes_to_human(the_total))
			return the_total

		else:
			logging.warning(_(u'{0}: computing global system size is not '
							u'implemented for systems other than Linux. '
							u'Returning 0 and hoping this will be sufficient.'))
			return 0
	def add_volume_from_device(self, device=None, by_string=None):
		""" Add a volume from udev data if it doesn't already exist.

			:param device: a :class:`~pyudev.Device` instance.
			:param by_string: a kernel device, passed a string string (eg.
				``/dev/sda1``). **Currently ignored**.
		"""

		assert ltrace(self._trace_name, '| add_volume_from_device(%s)' % device)

		if by_string and device is None:
			lprint('>> implement getting a udev device from a string')
			return

		assert ltrace(TRACE_LOCKS, '  locking volumes.lock: %s' % self.locks._global)

		with self.locks._global:
			kernel_device = device.device_node

			if kernel_device in self.volumes.keys():
				logging.progress(_(u'{0}: skipped already known '
					u'volume {1}.').format(stylize(ST_NAME, self.name),
						self.volumes[kernel_device]))
				# see if we got to remount this one now.
				#self.volumes[kernel_device].mount()
				return

			self.__update_cache_informations()

			if kernel_device not in self.cache.blkid.keys() \
				or self.cache.blkid[kernel_device]['type'] in self.container_fs:
				logging.progress(_(u'{0}: skipped LMV/extended '
					u'partition {1}.').format(stylize(ST_NAME, self.name),
						stylize(ST_DEVICE, kernel_device)))
				return

			if 'uuid' not in self.cache.blkid[kernel_device]:
				logging.progress(_(u'{0}: skipped unformatted '
					u'partition {1}.').format(stylize(ST_NAME, self.name),
						stylize(ST_DEVICE, kernel_device)))
				return

			if self.__system_partition(kernel_device):
				logging.progress(_(u'{0}: skipped system partition '
					u'{1}.').format(stylize(ST_NAME, self.name),
						stylize(ST_DEVICE, kernel_device)))
				return

			if self.cache.blkid[kernel_device]['type'] in self.accepted_fs:
				supported = True
			else:
				supported = False
				return_now = False
				try:
					if not LMC.configuration.extensions.volumes.mount_all_fs:
						return_now = True

				except AttributeError:
					# if LMC.configuration.extensions.volumes.mount_all_fs
					# doesn't exist, we don't mount unsupported FS by default.
					return_now = True

				if return_now:
					logging.progress(_(u'{0}: skipped partition {1} (excluded '
						u'{2} filesystem).').format(stylize(ST_NAME, self.name),
							stylize(ST_DEVICE, kernel_device),
							stylize(ST_ATTR, self.cache.blkid[kernel_device]['type'])))
					return

			label = (self.cache.blkid[kernel_device]['label']
							if 'label' in self.cache.blkid[kernel_device] else '')

			mount_point = (self.cache.proc_mounts[kernel_device]
					if kernel_device in self.cache.proc_mounts else None)

			vol = Volume(kernel_device,
						self.cache.blkid[kernel_device]['type'],
						self.cache.blkid[kernel_device]['uuid'],
						label,
						mount_point,
						supported,
						self)

			self.volumes[kernel_device] = vol

		LicornEvent('volume_added', volume=vol).emit()

		logging.info(_(u'{0}: added {1}.').format(stylize(ST_NAME, self.name), vol))

		vol.mount()
	def del_volume_from_device(self, device=None, by_string=None):
		""" Remove a volume if it exists.

			:param device: the :class:`~pyudev.Device` instance which has
				vanished, that we must now remove.
			:param by_string: a kernel device, passed a string string (eg.
				``/dev/sda1``). **Currently ignored**.
		"""

		assert ltrace(self._trace_name, '| del_volume_from_device(%s)' % device)

		if by_string and device is None:
			lprint('>> implement getting a udev device from a string')
			return

		with self.locks._global:

			try:
				kernel_device = device.device_node

			except AttributeError:
				# we are not deleting from a UDEV device, but from a licorn one.
				# attribute has not the same name.
				kernel_device = device.device

			if kernel_device in self.volumes.keys():

				volume = self.volumes[kernel_device]

				# keep a trace of the object, to ba able to display a message.
				volstr = str(volume)

				# TODO: shouldn't this be synchronous ?
				LicornEvent('volume_removed', volume=volstr).emit()

				# the unmount should have been done before, hence the force=True.
				if volume.mount_point:
					volume.unmount(force=True)

				del self.volumes[kernel_device]
				del volume

				logging.info(_(u'{0}: removed {1}.').format(stylize(ST_NAME, self.name), volstr))
	def volumes_call(self, volumes, method_name, *args, **kwargs):
		""" Generic method for action on volumes.

			:param volumes: a list of strings designating volumes, either by
				their kernel device names (eg. ``/dev/sdb2``) or their mount
				point (eg. ``/media/Save_Licorn``).
			:param method_name: the method to call on the volumes objects,
				passed as a string.
			:param kwargs: the arguments for the called method.
		"""

		# TODO: implement partial matching, e.g. "sdb1" will match "/dev/sdb1"
		# and produce the same result as if "/dev/sdb1" has been given.
		#
		# TODO: implement all of this with reverse mappings dicts, this will be
		# much-much simpler and won't duplicate the code...

		assert ltrace(self._trace_name, '| volumes_call(%s, %s)' % (volumes, method_name))

		with self.locks._global:
			devices        = self.keys()
			by_mntpnt      = dict((vol.mount_point, vol) for vol in self.itervalues())
			by_kernel      = dict((vol.device, vol) for vol in self.itervalues())
			mount_points   = by_mntpnt.keys()
			kernel_devices = by_kernel.keys()

			for volume in volumes:
				try:
					# if `volume` is a real one of us, this will succeed.
					getattr(volume, method_name)(*args, **kwargs)

				except:
					# else, it can be anything, encoded as a string. just search.
					if volume in kernel_devices:
						getattr(by_kernel[volume], method_name)(*args, **kwargs)

					elif volume in devices:
						getattr(self[volume], method_name)(*args, **kwargs)

					elif volume in mount_points:
						getattr(by_mntpnt[volume], method_name)(*args, **kwargs)

					else:
						logging.warning2(_(u'{0}: skipped non existing device or '
							u'mount_point {1}.').format(stylize(ST_NAME, self.name),
								volume))
	def enable_volumes(self, volumes):
		""" try to enable the given volumes.

			:param volumes: a list of devices or mount points, given as strings,
				to enable.
		"""
		return self.volumes_call(volumes, 'enable')
	def disable_volumes(self, volumes):
		""" try to disable the given volumes.

			:param volumes: a list of devices or mount points, given as strings,
				to disable.
		"""
		return self.volumes_call(volumes, 'disable')
	def unmount_volumes(self, volumes, force=False):
		""" Unmount and then eject devices.

			This method internally calls the
			:meth:`~VolumesExtension.volumes_call` method with  argument
			`method_name` set to ``unmount`` and simply forwards the `force`
			argument.

			:param volumes: see method :meth:`~VolumesExtension.volumes_call`.
			:param force: a boolean, specifying if volumes should be unmounted
				even if still in use (can be dangerous, use with caution).
		"""

		# TODO: splitting volume_list has nothing to do here, it should be
		# done in cli*. This is because of del not having the same syntax as
		# mod.

		final_volume_list = []

		for volume_list in volumes:
			final_volume_list.extend(volume_list.split(','))

		self.volumes_call(final_volume_list, 'unmount', force=force)
	def mount_volumes(self, volumes=None):
		""" (re-)Mount devices (they must prior be connected).

			This method internally calls the
			:meth:`~VolumesExtension.volumes_call` method with argument
			`method_name` set to ``mount``, without any other argument.

			:param volumes: see method :meth:`~VolumesExtension.volumes_call`.

		"""

		# TODO: splitting volume_list has nothing to do here, it should be
		# done in cli*. This is because of add not having the same syntax as
		# mod.

		if volumes is None :
			final_volume_list = self.volumes.itervalues()

		else:
			for volume_list in volumes:
				final_volume_list = volume_list.split(',')

		self.volumes_call(final_volume_list, 'mount')
	def get_CLI(self, opts, args):
		""" This method builds the output of the :command:`get volumes` command.

			:param opts: the CLI options generated by the ``argparser``.
			:param args: the CLI arguments generated by the ``argparser``.
		"""

		def stat_fs_to_str(volume):
			free, total = volume.stats()
			return _(u', {0} of {1} free ({2:.1%})').format(
				pyutils.bytes_to_human(free), pyutils.bytes_to_human(total),
				(free / total))

		return u'\n'.join(u'%s[%s]%s' % (
			stylize(ST_ENABLED if self.volumes[volkey].enabled
				else ST_DISABLED, volume.device),
			stylize(ST_ATTR, volume.fstype),
			_(u' on {0}{1}').format(
				stylize(ST_PATH, volume.mount_point),
				stat_fs_to_str(volume))
					if volume.mount_point else _(u' not mounted'),
			) for volkey, volume in sorted(self.volumes.items())) + \
				u'\n' if len(self.volumes) > 0 else u''
	def keys(self):
		with self.locks._global:
			return self.volumes.keys()
	def iterkeys(self):
		with self.locks._global:
			return self.volumes.iterkeys()
	def iteritems(self):
		with self.locks._global:
			return self.volumes.iteritems()
	def items(self):
		with self.locks._global:
			return self.volumes.items()
	def values(self):
		with self.locks._global:
			return self.volumes.values()
	def itervalues(self):
		with self.locks._global:
			return self.volumes.itervalues()
	def iter(self):
		with self.locks._global:
			return self.volumes.iter()
	def __iter__(self):
		with self.locks._global:
			return self.volumes.__iter__()
	def next(self):
		with self.locks._global:
			return self.volumes.next()
	def __getitem__(self, key):
		with self.locks._global:
			return self.volumes[key]

__all__ = ('Volume', 'VolumesExtension', 'VolumeException', )
