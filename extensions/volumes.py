# -*- coding: utf-8 -*-
"""
Licorn extensions: volumes - http://docs.licorn.org/extensions/volumes.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, gamin, dbus, pyudev, select, re
from traceback import print_exc
from threading import RLock

from licorn.foundations           import logging, pyutils, process, exceptions
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, MixedDictObject, LicornConfigObject
from licorn.foundations.constants import gamin_events

from licorn.core               import LMC
from licorn.extensions         import LicornExtension
from licorn.daemon.threads     import LicornBasicThread

BLKID_re = re.compile(r'([^ =]+)="([^"]+)"')

class UdevMonitorThread(LicornBasicThread):
	"""
		.. versionadded:: 1.2.4
	"""
	def __init__(self):
		""" TODO. """

		assert ltrace('volumes', '| UdevMonitorThread.__init__()')

		LicornBasicThread.__init__(self, pname='extensions', tname='UdevMonitor')

		self.udev_monitor = pyudev.Monitor.from_netlink(pyudev.Context())
		self.udev_monitor.filter_by(subsystem='block')
		self.udev_monitor.enable_receiving()
		self.udev_fileno = self.udev_monitor.fileno()
	def run_func(self):
		""" This method is meant to be called in the while loop of the default
			:meth:`~licorn.daemon.threads.LicornBasicThread.run` method of
			the :class:`~licorn.daemon.threads.LicornBasicThread`.

			Udev information:

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


		"""

		# this should be a level2 ltrace...
		#assert ltrace('volumes', '| UdevMonitorThread.run_func()')

		readf, writef, errf = select.select([self.udev_fileno], [], [], 1.0)

		if readf:
			action, device = self.udev_monitor.receive_device()

			if action == 'add':
				if 'partition' in device.attributes:
					LMC.extensions.volumes.add_volume_from_device(device)
			elif action == 'change':
				if 'partition' in device.attributes:
					# TODO: implement a real change method...
					LMC.extensions.volumes.unmount_volumes([device.device_node])
					LMC.extensions.volumes.del_volume_from_device(device)
					LMC.extensions.volumes.add_volume_from_device(device)
			elif action == 'remove':
				LMC.extensions.volumes.del_volume_from_device(device)
			else:
				logging.progress('%s: %s %s' % (self.name, action, device))
class VolumeException(exceptions.LicornRuntimeException):
	"""
		.. versionadded:: 1.2.4
	"""
	pass
class Volume:
	""" Handle a single volume.

		.. note:: This class is individually locked because :class:`Volume`
			can be accessed through multiple extensions (most notably
			:class:`rdiff-backup <RdiffBackupExtension>` which can take ages to
			complete).

		.. versionadded:: 1.2.4
	"""
	mount_base_path = '/media/'
	enabler_file    = '/.org.licorn.reserved_volume'
	def __init__(self, kernel_device, fstype, guid, label, mount_point=None):
		self.name        = kernel_device
		self.device      = self.name
		self.label       = label
		self.fstype      = fstype
		self.guid        = guid
		self.mount_point = mount_point
		self.lock        = RLock()
		#: __unmount is used to remember the mount status between __enter__ and
		#: __exit__ calls.
		self.__unmount   = False
		if mount_point:
			self.enabled = os.path.exists(self.mount_point + Volume.enabler_file)
		else:
			self.enabled = None
		assert ltrace('volumes', '| Volume.__init__(%s, %s, enabled=%s)' % (
			self.name, self.mount_point, self.enabled))
	def __str__(self):
		return 'volume %s%s' % (
					stylize(ST_DEVICE, self.device),
					' (%s)' % stylize(ST_PATH, self.mount_point)
						if self.mount_point else '')
	def __enter__(self):
		if self.lock.acquire(False):
			if self.mount_point is None:
				self.__unmount = True
				self.mount()
		else:
			raise VolumeException('volume %s already locked.' % str(self))
	def __exit__(self, type, value, traceback):
		""" TODO: use arguments... """
		if self.__unmount:
			self.unmount()
		self.lock.release()
	def __compute_mount_point(self):
		if self.label:
			self.mount_point = Volume.mount_base_path + self.label

			# avoid overmounting another volume with the same label.
			mount_point_base = self.mount_point
			counter = 1
			while os.path.exists(self.mount_point):
				self.mount_point = '%s %s' % (mount_point_base, counter)

		else:
			# overmounting is very unlikely to happen with guid...
			self.mount_point = Volume.mount_base_path + self.guid
	def enable(self, **kwargs):
		""" Reserve a volume for Licorn® usage by placing a special hidden
			file at the root of it. """

		with self.lock:
			if os.path.exists(self.mount_point + Volume.enabler_file):

				logging.info('volumes: Licorn® usage on %s already enabled.' %
						stylize(ST_PATH, self.mount_point))
			else:
				open(self.mount_point + Volume.enabler_file, 'w').write('\n')
				self.enabled = True
				logging.notice('volumes: enabled Licorn® usage on %s.' %
					stylize(ST_PATH, self.mount_point))
	def disable(self, **kwargs):
		""" Remove the special file at the root of the volume and thus unmark
			it reserved for Licorn® used. """
		with self.lock:
			if os.path.exists(self.mount_point + Volume.enabler_file):
				os.unlink(self.mount_point + Volume.enabler_file)
				self.enabled = False
				logging.notice('volumes: disabled Licorn® usage on %s.' %
						stylize(ST_PATH, self.mount_point))
			else:
				logging.info('volumes: Licorn® usage on %s already disabled.' %
						stylize(ST_PATH, self.mount_point))
	def mount(self, **kwargs):
		""" Mount a given volume, after having created its mount point
			directory if needed. This method simply calls the :prog:`mount`
			program via the :func:`~licorn.foundations.process.execute`
			function. """

		assert ltrace('volumes', '| Volume.mount(%s, %s)' % (
											self.device, self.mount_point))
		with self.lock:
			if not self.mount_point:

				self.__compute_mount_point()

				if not os.path.exists(self.mount_point):
					os.makedirs(self.mount_point)
					logging.progress('volumes: created mount point directory %s.' %
												stylize(ST_PATH, self.mount_point))

				mount_cmd = [ 'mount', '-t', self.fstype, '-o',
					'acl,user_xattr,noatime,errors=remount-ro,nodev,suid,exec',
					self.device, self.mount_point ]

				output = process.execute(mount_cmd)[1].strip()

				if output:
					logging.warning('volumes: ' + output)
				else:
					logging.notice('volumes: mounted device %s at %s.' % (
									stylize(ST_DEVICE, self.device),
									stylize(ST_PATH, self.mount_point)))

			self.enabled = os.path.exists(self.mount_point + Volume.enabler_file)
	def unmount(self, force=False):
		""" Unmount a volume and remove its mount point directory. """

		assert ltrace('volumes', '| Volume.unmount(%s, %s)' % (
											self.device, self.mount_point))

		with self.lock:
			if self.mount_point:
				umount_cmd = [ 'umount', self.device ]

				if force:
					umount_cmd.insert(1, '-f')

				output = process.execute(umount_cmd)[1].strip()

				if output:
					logging.warning('volumes: ' + output)
				else:
					logging.notice('volumes: unmounted device %s from %s.' % (
									stylize(ST_DEVICE, self.device),
									stylize(ST_PATH, self.mount_point)))

				old_mount_point = self.mount_point
				os.rmdir(old_mount_point)
				self.mount_point = None
				logging.progress('volumes: removed directory %s.' %
											stylize(ST_PATH, old_mount_point))
class VolumesExtension(Singleton, LicornExtension):
	""" Handles volumes via uDEV.

		Eventually, if udisks is available, we inhibit it to avoid double work
		and user interaction.

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
	def __init__(self):
		assert ltrace('volumes', '| VolumesExtension.__init__()')
		LicornExtension.__init__(self,
			name='volumes',
			controllers_compat=[ 'system' ])

		self.server_only = True

		# don't handle these mount points, this is left to the distro.
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
		self.excluded_mounts = ('/', '/boot', '/home', '/var', '/tmp',
								'/var/tmp')

		# accepted FS must implement posix1e ACLs and user_xattr.
		# 'vfat' doesn't, 'fuseblk' can be too much things.
		self.accepted_fs = ('ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'jfs',
			'reiserfs')

		self.volumes = MixedDictObject('volumes')

		# TODO: add our volumes to notifications, to change the status when
		# administrator touches or unlinks special files in volume's root.
		self.inotifications = []
	def __del__(self):
		""" Put the eventual udisks daemon in a normal state before giving
			back hand.

			.. note:: the :class:`UdevMonitorThread` instance will be stopped
				as part of the daemon global stop process. Don't stop it here.
		"""

		self.__uninhibit_udisks()
	def initialize(self):
		""" The extension is available if udev is OK and we can get a list of
			already connected devices.

			Eventually, if udisks is present and enabled, we inhibit it.
		"""

		assert ltrace(self.name, '> initialize()')

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

			self.__inhibit_udisks()

		try:
			logging.info('%s: started %s extension with udev v%s, pyudev v%s.'
				% (self.name, stylize(ST_SPECIAL, LMC.configuration.app_name),
					pyudev.udev_version(), pyudev.__version__))

			# get the list of currently connected devices.
			self.rescan_volumes()

			# after that, start a monitor to watch adds/dels.
			self.__start_udev_monitor()

			# we are always available, because only relying on udev.
			self.available = True

		except Exception, e:
			print_exc(e)
			logging.warning2("%s: not available because %s." % (self.name, e))
			self.available = False

		assert ltrace(self.name, '< initialize(%s)' % self.available)

		return self.available
	def is_enabled(self):
		""" Volumes extension is always enabled if available, return always
			True. """
		assert ltrace(self.name, '| is_enabled() → True')
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
		""" Nothing particular to do here. TODO: check if calling
			rescan_volumes() twice is really usefull. """

		assert ltrace(self.name, '| system_load()')
		pass
	def __start_udev_monitor(self):
		""" Create and start the :class:`UdevMonitorThread`. We start it now,
			just after the device listing, to be sure not to miss any device
			change. This won't hurt the daemon anyway which will test if the
			thread is alive or not.

		"""
		self.udev_monitor_thread = UdevMonitorThread()
		self.udev_monitor_thread.start()

		self.threads.append(self.udev_monitor_thread)
	def __inhibit_udisks(self):
		""" TODO """

		assert ltrace(self.name, '| __inhibit_udisks(%s)' % (
				self.udisks_object is not None))

		if self.udisks_object is not None \
				and not self.udisks_props('DaemonIsInhibited'):

			self.udisks_cookie = self.udisks_interface.Inhibit()
	def __uninhibit_udisks(self):
		""" TODO """

		assert ltrace(self.name, '| __uninhibit_udisks(%s)' % (
						self.udisks_object is not None))

		if self.udisks_object is not None \
				and self.udisks_props('DaemonIsInhibited'):

			self.udisks_interface.UnInhibit(self.udisks_cookie)
	def rescan_volumes(self):
		""" get a list of connected block devices from udev, and mount them if
			needed. """

		assert ltrace(self.name, '| rescan_volumes()')

		udev_context = pyudev.Context()

		kernel_devices = []

		with self.lock:
			self_devices = self.volumes.keys()

			for device in udev_context.list_devices(subsystem='block',
														DEVTYPE='partition'):

				kernel_devices.append(device.device_node)
				self.add_volume_from_device(device)

			# remove old devices, wipped away during the time.
			for device in self_devices:
				if device not in kernel_devices:
					self.del_volume_from_device(device)

		del udev_context
	def __update_cache_informations(self):
		""" Read :file:`/proc/mounts` and :file:`/etc/blkid.tab` and keep
			useful informations inside us for future use. """

		assert ltrace(self.name, '| __update_cache_informations()')

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
			our protected partitions."""

		mounted = self.proc_mounts.keys()

		if device in mounted:
			assert ltrace(self.name, '|  __system_partition(device) → %s' % (
							self.proc_mounts[device] in self.excluded_mounts))
			return self.proc_mounts[device] in self.excluded_mounts

		by_uuid = '/dev/disk/by-uuid/' + self.blkid[device]['uuid']

		if by_uuid in mounted:
			assert ltrace(self.name, '|  __system_partition(device) → %s' % (
							self.proc_mounts[by_uuid] in self.excluded_mounts))
			return self.proc_mounts[by_uuid] in self.excluded_mounts

		assert ltrace(self.name, '|  __system_partition(device) → False')
		return False
	def add_volume_from_device(self, device=None, by_string=None):
		""" add a volume from OS data if it doesn't already exist. """

		assert ltrace(self.name, '| add_volume_from_device(%s)' % device)

		if by_string and device is None:
			print '>> implement getting a udev device from a string'

		with self.lock:
			kernel_device = device.device_node

			if kernel_device in self.volumes.keys():
				logging.progress('%s: skipped already known volume %s.' % (
					self.name, self.volumes[kernel_device]))
				# see if we got to remount this one now.
				self.volumes[kernel_device].mount()
				return

			self.__update_cache_informations()

			if kernel_device not in self.blkid.keys():
				# this happens for extended partitions, they don't get listed
				# there. Skip them.
				return

			if 'uuid' not in self.blkid[kernel_device]:
				logging.progress('%s: skipped unformatted partition %s.' %(
						self.name, stylize(ST_DEVICE, kernel_device)))
				return

			if self.__system_partition(kernel_device):
				logging.progress('%s: skipped system partition %s.' %(
						self.name, stylize(ST_DEVICE, kernel_device)))
				return

			if self.blkid[kernel_device]['type'] \
											not in self.accepted_fs:
				logging.progress('%s: skipped partition %s (excluded %s '
					'filesystem).' % (self.name,
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
						mount_point)

			self.volumes[kernel_device] = vol

		vol.mount()

		logging.info('%s: added %s.' % ( self.name, vol))
	def del_volume_from_device(self, device=None, by_string=None):
		""" Remove a volume. """

		assert ltrace(self.name, '| del_volume_from_device(%s)' % device)

		if by_string and device is None:
			print '>> implement getting a udev device from a string'

		with self.lock:

			kernel_device = device.device_node

			if kernel_device in self.volumes.keys():
				mount_point = self.volumes[kernel_device].mount_point

				# we don't unmount, this should have already been done, because
				# the device disappeared from the kernel/udev list: it's
				# already gone from the system...

				volstr = str(self.volumes[kernel_device])

				del self.volumes[kernel_device]

				logging.info('%s: removed %s.' % (self.name, volstr))
	def volumes_call(self, volumes, method_name, **kwargs):
		""" generic method for enable/disable calling on volumes. """

		# TODO: implement partial matching, e.g. "sdb1" will match "/dev/sdb1"
		# and produce the same result as if "/dev/sdb1" has been given.
		#
		# TODO: implement all of this with reverse mappings dicts, this will be
		# much-much simpler and won't duplicate the code...

		assert ltrace(self.name, '| volume_call(%s, %s)' % (volumes, method_name))

		with self.lock:
			devices        = self.keys()
			by_mntpnt      = dict([ (vol.mount_point, vol) for vol in self.values() ])
			by_kernel      = dict([ (vol.device, vol) for vol in self.values() ])
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
					logging.warning2('%s: skipped non existing device or '
						'mount_point %s.' % (self.name, volume))
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
		""" Unmount and then eject devices. """

		# TODO: splitting volume_list has nothing to do here, it should be
		# done in cli*. This is because of del not having the same syntax as
		# mod.

		final_volume_list = []

		for volume_list in volumes:
			final_volume_list.extend(volume_list.split(','))

		self.volumes_call(final_volume_list, 'unmount', force=force)
	def mount_volumes(self, volumes):
		""" (re-)Mount devices (they must be connected). """

		# TODO: splitting volume_list has nothing to do here, it should be
		# done in cli*. This is because of add not having the same syntax as
		# mod.

		final_volume_list = []

		for volume_list in volumes:
			final_volume_list.extend(volume_list.split(','))

		self.volumes_call(final_volume_list, 'mount')
	def get_CLI(self, opts, args):
		""" TODO """

		def stat_fs_to_str(path):
			""" See http://docs.python.org/library/os.html#os.statvfs for
				details.
			"""

			stat = os.statvfs(path)
			free = stat.f_bfree * stat.f_bsize / (1024.0*1024.0*768.0)
			total = stat.f_blocks * stat.f_bsize / (1024.0*1024.0*768.0)
			#print '>> path', path, 'stat', stat, 'free', free, 'total', total
			return ', %.2fGb/%.2fGb free (%.2f%%)' % (
				free, total, (free / total) * 100.0
			)
		return '\n'.join([ '%s%s' % (
			stylize(ST_ENABLED if self.volumes[volkey].enabled
				else ST_DISABLED, volume.device),
			' on %s%s' % (stylize(ST_PATH, volume.mount_point),
				stat_fs_to_str(volume.mount_point))
					if volume.mount_point else ' not mounted',
			) for volkey, volume in sorted(self.volumes.items()) ]) + \
				'\n' if len(self.volumes) > 0 else ''
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
