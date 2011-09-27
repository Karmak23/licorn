# -*- coding: utf-8 -*-
"""
Licorn extensions: volumes - http://docs.licorn.org/extensions/volumes.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, dbus, pyudev, select, re, errno

from threading import RLock

from licorn.foundations           import logging, process, exceptions, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import Singleton, MixedDictObject

from licorn.core                import LMC
from licorn.extensions          import LicornExtension
from licorn.daemon              import InternalEvent, priorities
from licorn.daemon.threads      import LicornBasicThread

BLKID_re = re.compile(r'([^ =]+)="([^"]+)"')

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
	def __init__(self):
		assert ltrace(TRACE_VOLUMES, '| UdevMonitorThread.__init__()')

		LicornBasicThread.__init__(self,
			tname='extensions.volumes.UdevMonitor')

		# set daemon in case we take too much time unihibiting udisks
		# while daemon is stopping.
		self.daemon = True
		self.udev_monitor = pyudev.Monitor.from_netlink(pyudev.Context())
		self.udev_monitor.filter_by(subsystem='block')
		self.udev_monitor.enable_receiving()
		self.udev_fileno = self.udev_monitor.fileno()
		self.lock = RLock()
		self.prevented_actions = []
	def prevent_action_on_device(self, action, device):
		with self.lock:
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

			with self.lock:
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
class Volume:
	""" A single volume object.

		.. note:: This class is individually locked because :class:`Volume`
			can be accessed through multiple extensions (most notably
			:class:`rdiff-backup <licorn.extensions.rdiffbackup.RdiffbackupExtension>`
			which can take ages to complete).

		.. versionadded:: 1.2.4
	"""

	# these options mimic the udisks ones.
	mount_options = {
		'vfat'     : ("shortname=mixed", "dmask=0077", "utf8=1", "showexec"),
		'ntfs'     : ("dmask=0077", "fmask=0177"),
		'iso9660'  : ("iocharset=utf8", "mode=0400", "dmode=0500"),
		'udf'      : ("iocharset=utf8", "umask=0077"),
		# acl and user_xattr are 'built-in' for btrfs
		'btrfs'    : ('noatime', 'errors=remount-ro', 'nodev', 'suid', 'exec',),
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
		self.name        = kernel_device
		self.device      = self.name
		self.label       = label
		self.fstype      = fstype
		self.guid        = guid
		self.mount_point = mount_point
		self.lock        = RLock()
		self.supported   = supported
		self.controller  = volumes_extension

		if mount_point:
			self.enabled = os.path.exists(self.mount_point + Volume.enabler_file)

		else:
			self.enabled = None

		assert ltrace(TRACE_VOLUMES, '| Volume.__init__(%s, %s, enabled=%s)' % (
			self.name, self.mount_point, self.enabled))
	def __str__(self):
		return _(u'volume {0}[{1}]{2}').format(
					stylize(ST_DEVICE, self.device),
					stylize(ST_ATTR, self.fstype),
					_(u' (on %s)') % stylize(ST_PATH, self.mount_point)
						if self.mount_point else _(' (not mounted)'))
	def __enter__(self):
		#print '>> Volume.__enter__', current_thread().name
		self.lock.acquire()
		if self.mount_point is None:
			self.mount()
	def locked(self):
		""" Return ``True`` if instance is currently locked, else ``False``. """
		if self.lock.acquire(blocking=False):
			self.lock.release()
			return False
		#print '>> locked by', self.locker
		return True
	def __exit__(self, type, value, traceback):
		""" TODO: use arguments... """
		#print '>> Volume.__exit__', current_thread().name
		self.lock.release()
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
	def stats(self):
		""" See http://docs.python.org/library/os.html#os.statvfs for
			details.
		"""
		if self.mount_point:
			stat = os.statvfs(self.mount_point)

			# TODO: make the last 1024 variable, when stat.f_bsize takes different values.
			# It seems we need it to be 768.0 on VFAT usb keys, don't know why.

			return (stat.f_bfree * stat.f_bsize / (1024.0*1024.0*1024.0),
					stat.f_blocks * stat.f_bsize / (1024.0*1024.0*1024.0))

		raise VolumeException(_('{0}({1}) not mounted').format(self.device, self.fstype))
	def enable(self, **kwargs):
		""" Reserve a volume for Licorn® usage by placing a special hidden
			file at the root of it.

			:param kwargs: **not used**, but present because this method is
				meant to be called via :meth:`VolumesExtension.volumes_call`,
				which can use any number of arguments.
		"""

		unmount = False

		with self.lock:
			if self.supported:
				if self.mount_point is None:
					unmount = self.mount(emit_event=False)

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

					L_event_dispatch(priorities.NORMAL,
							InternalEvent('volume_enabled', volume=self))

				if unmount:
					self.unmount(emit_event=False)
			else:
				logging.warning(_(u'{0}: cannot enable Licorn® usage on {1} '
					u'(unsupported FS {2}).').format(stylize(ST_NAME, 'volumes'),
						stylize(ST_PATH, self.mount_point),
						stylize(ST_PATH, self.fstype)))

	def disable(self, **kwargs):
		""" Remove the special file at the root of the volume and thus unmark
			it reserved for Licorn® usage.

			:param kwargs: **not used**, but present because this method is
				meant to be called via :meth:`VolumesExtension.volumes_call`,
				which can use any number of arguments.
		"""

		unmount = False

		with self.lock:

			if self.mount_point is None:
				unmount = self.mount(emit_event=False)

			if os.path.exists(self.mount_point + Volume.enabler_file):
				# NOTE: the event must be sent *after* disabling the volume,
				# else other depending extensions will find it still active
				# if they test the `enabled` attribute.

				os.unlink(self.mount_point + Volume.enabler_file)

				self.enabled = False

				L_event_dispatch(priorities.NORMAL,
							InternalEvent('volume_disabled', volume=self))

				logging.notice(_(u'{0}: disabled Licorn® usage on {1}.').format(
					stylize(ST_NAME, 'volumes'), stylize(ST_PATH, self.mount_point)))

				if unmount:
					self.unmount(emit_event=False)

			else:
				logging.info(_(u'{0}: Licorn® usage already disabled on {1}.').format(
				stylize(ST_NAME, 'volumes'), stylize(ST_PATH, self.mount_point)))
	def mount(self, emit_event=True, **kwargs):
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

			.. note:: The mount point creation heuristics take care of already
				existing mount points, and will find a unique and not currently
				taken mount point directory name in any case.

			"""

		assert ltrace(TRACE_VOLUMES, '| Volume.mount(%s, %s)' % (
											self.device, self.mount_point))
		assert ltrace(TRACE_LOCKS, '  locking self.device %s' % self.lock)

		with self.lock:
			if not self.mount_point:
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
				else:
					if emit_event:
						L_event_dispatch(priorities.NORMAL,
							InternalEvent('volume_mounted', volume=self))

					logging.notice(_(u'{0}: mounted device {1}({2}) at {3}.').format(
									stylize(ST_NAME, 'volumes'),
									stylize(ST_DEVICE, self.device),
									stylize(ST_DEVICE, self.fstype),
									stylize(ST_PATH, self.mount_point)))

			if self.supported:
				self.enabled = os.path.exists(self.mount_point + Volume.enabler_file)

		return True
	def unmount(self, force=False, emit_event=True):
		""" Unmount a volume and remove its mount point directory. """

		assert ltrace(TRACE_VOLUMES, '| Volume.unmount(%s, %s)' % (
											self.device, self.mount_point))

		with self.lock:
			if self.mount_point:
				umount_cmd = [ 'umount', self.device ]

				if force:
					umount_cmd.insert(1, '-f')

				# the traditional specific fixes and workarounds...
				if self.fstype == 'ntfs':
					self.controller.threads.udevmonitor.prevent_action_on_device('change', self.device)

				# TODO: Import cdll from ctypes. Then load your os libc, then use libc.mount()
				output = process.execute(umount_cmd)[1].strip()

				if output:
					logging.warning(_(u'{0}: {1}').format(
									stylize(ST_NAME, 'volumes'), output))
				else:
					if emit_event:
						L_event_dispatch(priorities.NORMAL,
							InternalEvent('volume_unmounted', volume=self))

					logging.notice(_(u'{0}: unmounted device {1} from {2}.').format(
									stylize(ST_NAME, 'volumes'),
									stylize(ST_DEVICE, self.device),
									stylize(ST_PATH, self.mount_point)))

				old_mount_point = self.mount_point

				try:
					os.rmdir(old_mount_point)

				except (OSError, IOError), e:
					if e.errno == errno.EBUSY:
						logging.warning(_(u'{0}({1}): mount point {2} still '
							u'busy after unmounting.').format(
								stylize(ST_NAME, 'volumes'),
								stylize(ST_DEVICE, self.device),
								stylize(ST_PATH, self.mount_point)))
						return

					else:
						raise

				self.mount_point = None
				logging.info(_(u'{0}: removed directory {1}.').format(
					stylize(ST_NAME, 'volumes'),
					stylize(ST_PATH, old_mount_point)))
class VolumesExtension(Singleton, LicornExtension):
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
								'/var/tmp')

		# accepted FS must implement posix1e ACLs and user_xattr.
		# 'vfat' doesn't, 'fuseblk' can be too much things.
		self.accepted_fs = ('ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'jfs',
			'reiserfs')

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

		assert ltrace(self.trace_name, '> initialize()')

		# we need the thread to be created to eventually add udisks-related
		# methods a little later.
		self.threads.udevmonitor = UdevMonitorThread()

		try:
			self.system_bus = dbus.SystemBus()
			self.udisks_object = self.system_bus.get_object(
									"org.freedesktop.UDisks",
									"/org/freedesktop/UDisks")
		except:
			self.udisks_object = None

		else:
			self.udisks_interface = dbus.Interface(self.udisks_object,
										'org.freedesktop.UDisks')
			self.udisks_properties = dbus.Interface(self.udisks_object,
										dbus.PROPERTIES_IFACE)
			self.udisks_props = lambda x: self.udisks_properties.Get(
										'org.freedesktop.UDisks', x)

			self.threads.udevmonitor.pre_run_method = self.__inhibit_udisks
			self.threads.udevmonitor.post_run_method = self.__uninhibit_udisks

		try:
			# get the list of currently connected devices.
			self.rescan_volumes()

			# after that, start a monitor to watch adds/dels.
			self.threads.udevmonitor.start()

			# we are always available, because only relying on udev.
			self.available = True

		except Exception, e:
			pyutils.print_exception_if_verbose()
			logging.warning2(_(u'{0}: not available because {1}.').format(
				stylize(ST_NAME, self.name), e))
			self.available = False

		assert ltrace(self.trace_name, '< initialize(%s)' % self.available)

		return self.available
	def is_enabled(self):
		""" Volumes extension is always enabled if available, return always
			True. """
		assert ltrace(self.trace_name, '| is_enabled() → True')

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
		"""

		#self.rescan()
		return True
	def system_load(self):
		""" Nothing particular to do here. This method exists because this
			extension is attached to the :class:`SystemController` (for pure
			logical purpose, because it doesn't load any data into it). """

		assert ltrace(self.trace_name, '| system_load()')
		pass

	def __inhibit_udisks(self):
		""" TODO """

		assert ltrace(self.trace_name, '| __inhibit_udisks(%s)' % (
				self.udisks_object is not None))

		if self.udisks_object is not None \
				and not self.udisks_props('DaemonIsInhibited'):

			self.udisks_cookie = self.udisks_interface.Inhibit()
	def __uninhibit_udisks(self):
		""" TODO """

		assert ltrace(self.trace_name, '| __uninhibit_udisks(%s)' % (
						self.udisks_object is not None))

		if self.udisks_object is not None \
				and self.udisks_props('DaemonIsInhibited') \
				and hasattr(self, 'udisks_cookie'):

			# make sure *WE* inhibited udisks, else this won't work.
			self.udisks_interface.Uninhibit(self.udisks_cookie)
	def rescan_volumes(self):
		""" Get a list of connected block devices from :command:`udev`, record
			them inside us (creating the corresponding :class:`Volume` objects,
			and mount them if not already mounted. """

		assert ltrace(self.trace_name, '| rescan_volumes()')

		udev_context = pyudev.Context()

		kernel_devices = []

		with self.lock:
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
	def __update_cache_informations(self):
		""" Read :file:`/proc/mounts` and run :command:`blkid` (the cache file
			:file:`/etc/blkid.tab` has been found to be unreliably updated when
			volumes are pluged in/out) and keep useful informations inside us
			for future use. """

		assert ltrace(self.trace_name, '| __update_cache_informations()')

		self.proc_mounts = {}
		for line in open('/proc/mounts').readlines():
			splitted = line.split(' ')
			# NOTE: when parsing /proc/mounts, we've got to replace these
			# nasty \\040 by the real ascii code. This is because space is
			# the separator in /proc/mounts, and thus in paths it is protected
			# in its \040 octal form.
			self.proc_mounts[splitted[0]] = splitted[1].replace('\\040', '\040')

		self.blkid = {}

		# We can't assume the cache file is up-to-date, i've seen a number of
		# cases on my VM where it was not updated.
		#if os.path.exists('/etc/blkid.tab'):
		#	for line in open('/etc/blkid.tab').readlines():
		#		data = BLKID_re.match(line)
		#		if data:
		#			datadict = data.groupdict()
		#			self.blkid[datadict['device']] = {
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
			self.blkid[device] = {}
			for key, value in fields:
					self.blkid[device][key.lower()] = value
	def __system_partition(self, device):
		""" Return ``True`` if the given device or UUID is mounted on one of
			our protected partitions. """

		# NOTE: the current test is much more conservative than just
		# 'if device in excluded_mounts': it takes care of sub-directories
		# system mounted partitions (some external RAID arrays are still
		# seen as external devices, but are handled manually by system
		# administrators.

		mounted = self.proc_mounts.keys()

		if device in mounted:
			return self.proc_mounts[device] == '/' or reduce(pyutils.keep_true,
							(self.proc_mounts[device].startswith(x)
								for x in self.excluded_mounts))

		by_uuid = '/dev/disk/by-uuid/' + self.blkid[device]['uuid']

		if by_uuid in mounted:
			return self.proc_mounts[by_uuid] == '/' or reduce(pyutils.keep_true,
							(self.proc_mounts[by_uuid].startswith(x)
								for x in self.excluded_mounts))


		assert ltrace(self.trace_name,
									'|  __system_partition(device) → False')
		return False
	def add_volume_from_device(self, device=None, by_string=None):
		""" Add a volume from udev data if it doesn't already exist.

			:param device: a :class:`~pyudev.Device` instance.
			:param by_string: a kernel device, passed a string string (eg.
				``/dev/sda1``). **Currently ignored**.
		"""

		assert ltrace(self.trace_name, '| add_volume_from_device(%s)' % device)

		if by_string and device is None:
			print '>> implement getting a udev device from a string'
			return

		assert ltrace(TRACE_LOCKS, '  locking volumes.lock: %s' % self.lock)

		with self.lock:
			kernel_device = device.device_node

			if kernel_device in self.volumes.keys():
				logging.progress(_(u'{0}: skipped already known '
					u'volume {1}.').format(stylize(ST_NAME, self.name),
						self.volumes[kernel_device]))
				# see if we got to remount this one now.
				self.volumes[kernel_device].mount()
				return

			self.__update_cache_informations()

			if kernel_device not in self.blkid.keys() \
				or self.blkid[kernel_device]['type'] in self.container_fs:
				logging.progress(_(u'{0}: skipped LMV/extended '
					u'partition {1}.').format(stylize(ST_NAME, self.name),
						stylize(ST_DEVICE, kernel_device)))
				return

			if 'uuid' not in self.blkid[kernel_device]:
				logging.progress(_(u'{0}: skipped unformatted '
					u'partition {1}.').format(stylize(ST_NAME, self.name),
						stylize(ST_DEVICE, kernel_device)))
				return

			if self.__system_partition(kernel_device):
				logging.progress(_(u'{0}: skipped system partition '
					u'{1}.').format(stylize(ST_NAME, self.name),
						stylize(ST_DEVICE, kernel_device)))
				return

			if self.blkid[kernel_device]['type'] in self.accepted_fs:
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
							stylize(ST_ATTR, self.blkid[kernel_device]['type'])))
					return

			label = (self.blkid[kernel_device]['label']
							if 'label' in self.blkid[kernel_device] else '')

			mount_point = (self.proc_mounts[kernel_device]
					if kernel_device in self.proc_mounts else None)

			vol = Volume(kernel_device,
						self.blkid[kernel_device]['type'],
						self.blkid[kernel_device]['uuid'],
						label,
						mount_point,
						supported,
						self)

			self.volumes[kernel_device] = vol

		vol.mount()

		L_event_dispatch(priorities.NORMAL,
							InternalEvent('volume_added', volume=vol))

		logging.info(_(u'{0}: added {1}.').format(stylize(ST_NAME, self.name), vol))
	def del_volume_from_device(self, device=None, by_string=None):
		""" Remove a volume if it exists.

			:param device: the :class:`~pyudev.Device` instance which has
				vanished, that we must now remove.
			:param by_string: a kernel device, passed a string string (eg.
				``/dev/sda1``). **Currently ignored**.
		"""

		assert ltrace(self.trace_name, '| del_volume_from_device(%s)' % device)

		if by_string and device is None:
			print '>> implement getting a udev device from a string'
			return

		with self.lock:

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
				L_event_dispatch(priorities.NORMAL, InternalEvent('volume_removed', volume=volstr))

				# the unmount should have been done before, hence the force=True.
				if volume.mount_point:
					volume.unmount(force=True)

				del self.volumes[kernel_device]
				del volume

				logging.info(_(u'{0}: removed {1}.').format(stylize(ST_NAME, self.name), volstr))
	def volumes_call(self, volumes, method_name, **kwargs):
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

		assert ltrace(self.trace_name, '| volumes_call(%s, %s)' % (volumes, method_name))

		with self.lock:
			devices        = self.keys()
			by_mntpnt      = dict((vol.mount_point, vol) for vol in self.values())
			by_kernel      = dict((vol.device, vol) for vol in self.values())
			mount_points   = by_mntpnt.keys()
			kernel_devices = by_kernel.keys()

			for volume in volumes:

				if volume in kernel_devices:
					getattr(by_kernel[volume], method_name)(**kwargs)

				elif volume in devices:
					getattr(self[volume], method_name)(**kwargs)

				elif volume in mount_points:
					getattr(by_mntpnt[volume], method_name)(**kwargs)

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
			#print '>> path', path, 'stat', stat, 'free', free, 'total', total
			return _(u', {0:.2f}Gb/{1:.2f}Gb free ({2:.1%})').format(
				free, total, (free / total))

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
		with self.lock:
			return self.volumes.keys()
	def iterkeys(self):
		with self.lock:
			return self.volumes.iterkeys()
	def iteritems(self):
		with self.lock:
			return self.volumes.iteritems()
	def items(self):
		with self.lock:
			return self.volumes.items()
	def values(self):
		with self.lock:
			return self.volumes.values()
	def itervalues(self):
		with self.lock:
			return self.volumes.itervalues()
	def iter(self):
		with self.lock:
			return self.volumes.iter()
	def __iter__(self):
		with self.lock:
			return self.volumes.__iter__()
	def __getitem__(self, key):
		with self.lock:
			return self.volumes[key]
