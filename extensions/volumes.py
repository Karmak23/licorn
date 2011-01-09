# -*- coding: utf-8 -*-
"""
Licorn extensions: volumes - http://docs.licorn.org/extensions/volumes.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os, gamin, dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from licorn.foundations           import logging, pyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, MixedDictObject, LicornConfigObject
from licorn.foundations.constants import gamin_events

from licorn.core               import LMC
from licorn.extensions         import LicornExtension

# static dbus helper methods.
def udisks_device_attributes(udisks_device_path):
	""" Get and return the :class:`~dbus.Interface` and
		:class:`~dbus.Properties` for a given Device Udisks Path.
	"""

	device_object = dbus.SystemBus().get_object("org.freedesktop.UDisks",
												udisks_device_path)
	device_iface = dbus.Interface(device_object,
									'org.freedesktop.UDisks.Device')
	device_props = dbus.Interface(device_object, dbus.PROPERTIES_IFACE)
	properties = lambda x: device_props.Get('org.freedesktop.UDisks.Device', x)

	return device_iface, properties
# Licorn Volumes related things.
class Volume:
	""" TODO. """
	def __init__(self, udisks_device, mount_point, kernel_device, volume_extension):
		self.name = udisks_device
		self.device = kernel_device
		self.mount_point = mount_point
		self.enabled = os.path.exists(
					mount_point + '/' + volume_extension.paths.enabler)
		self.volume_extension = volume_extension
		assert ltrace('volumes', '| Volume.__init__(%s, %s, %s, enabled=%s)' % (
			self.name, self.device, self.mount_point, self.enabled))
	def enable(self):
		if os.path.exists(self.mount_point + '/' +
					self.volume_extension.paths.enabler):

			logging.info('Licorn® usage of volume %s already enabled.' %
					stylize(ST_PATH, self.mount_point))
		else:
			open(self.mount_point + '/' +
				self.volume_extension.paths.enabler, 'w').write('\n')
			self.enabled = True
			logging.info('Enabled Licorn® usage of volume %s.' %
				stylize(ST_PATH, self.mount_point))
	def disable(self):
		if os.path.exists(self.mount_point + '/' +
					self.volume_extension.paths.enabler):

			os.unlink(self.mount_point + '/' +
				self.volume_extension.paths.enabler)
			self.enabled = False
			logging.info('Disabled Licorn® usage of volume %s.' %
					stylize(ST_PATH, self.mount_point))
		else:
			logging.info('Licorn® usage of volume %s already disabled.' %
					stylize(ST_PATH, self.mount_point))
class VolumesExtension(Singleton, LicornExtension):
	""" Handles backup volumes.

		Nice reads along the way:

		* http://freedesktop.org/wiki/Software/udisks
		* http://mdzlog.alcor.net/2010/06/27/navigating-the-policykit-maze/
		* http://askubuntu.com/questions/16730/default-mount-options-on-auto-mounted-ntfs-partitions-how-to-add-noexec-and-f

	"""
	def __init__(self):
		assert ltrace('volumes', '| VolumesExtension.__init__()')
		LicornExtension.__init__(self,
			name='volumes',
			controllers_compat=[ 'system' ])

		self.server_only = True

		self.paths.enabler = '.org.licorn.reserved_volume'

		# don't handle these mount points, this is left to the distro.
		# FIXME: why don't just 'include' /mnt/* and /media/*, this could be
		# more secure, instead of the risk of forgetting some special mount
		# points.
		self.excluded_mounts = ('/', '/boot', '/home', '/var', '/tmp',
			'/var/tmp')

		# accepted FS must implement posix1e ACLs and user_xattr.
		# 'vfat' doesn't, 'fuseblk' can be too much things.
		self.accepted_fs = ('ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'jfs',
			'reiserfs')

		# 0xaf = hfs
		# 0x0b = vfat
		self.accepted_partitions = [ '0x83' ]

		self.volumes = MixedDictObject('volumes')

		# TODO: add our volumes to notifications, to change the status when
		# administrator touches or unlinks special files in volume's root.
		self.inotifications = []
	def initialize(self):
		""" Make the extension available if python module ``python-parted`` is
			installed locally.
		"""

		# http://stackoverflow.com/questions/4142690/cant-connect-to-org-freedesktop-udisks-via-dbus-python

		assert ltrace(self.name, '> initialize()')

		try:
			self.system_bus = dbus.SystemBus()

			self.udisks_object = self.system_bus.get_object(
									"org.freedesktop.UDisks",
									"/org/freedesktop/UDisks")
			self.udisks_interface = dbus.Interface(self.udisks_object,
										'org.freedesktop.UDisks')
			self.udisks_properties = dbus.Interface(self.udisks_object,
										dbus.PROPERTIES_IFACE)
			self.udisks_props = lambda x: self.udisks_properties.Get(
											'org.freedesktop.UDisks', x)


			# get the list of currently connected devices.
			self.rescan()

			# WARNING: don't connect dbus signals HERE, this is too early
			# and it will block.

			#print '>> ', self.udisks_props('KnownFilesystems')

			# udisks is here, we are available.
			self.available = True

		except Exception, e:
			logging.warning2("%s: not available because %s." % (self.name, e))
			self.available = False

		assert ltrace(self.name, '< initialize(%s)' % self.available)

		return self.available
	def is_enabled(self):
		""" volumes extension is enabled if udisks daemon is not inhibited. """
		assert ltrace(self.name, '| is_enabled() → %s' %
						(not self.udisks_props('DaemonIsInhibited')))
		return not self.udisks_props('DaemonIsInhibited')
	def enable(self):
		""" Inhibit the udisks daemon to get full access to licornd. This will
			not affect clients because this extension is server-side only.
		"""

		self.udisks_interface.UnInhibit(self.udisks_cookie)
		return True
	def disable(self):
		""" Un-inhibit the udisks daemon to restore full access to other users.
		"""

		self.udisks_cookie = self.udisks_interface.Inhibit()
		#self.rescan()
		return True
	def system_load(self):
		""" Connect udisks signals now. """

		assert ltrace(self.name, '| system_load()')

		# stay up-to-date.
		self.udisks_object.connect_to_signal('DeviceAdded',
				self.udisks_device_added_callback)
		self.udisks_object.connect_to_signal('DeviceRemoved',
				self.udisks_device_removed_callback)
	def rescan(self):
		""" Ask the udisks-daemon for currently connected devices. Wipe out old
			references remaining in self. """

		assert ltrace(self.name, '| rescan()')

		with self.lock:
			for device_path in self.udisks_interface.EnumerateDevices():
				self.udisks_device_added_callback(device_path)
	def udisks_device_added_callback(self, device):
		""" Add a new device to the local system. """

		assert ltrace('volumes', '| udisks_device_added_callback(%s)' % device)

		diface, dprop = udisks_device_attributes(device)

		if device in self.volumes.keys():
			logging.info('Skipped volume %s (%s), already known.' % (
				stylize(ST_DEVICE, device),
				stylize(ST_PATH, self[device].mount_point)
				)
			)
			return

		if dprop('DeviceIsPartition') \
				and not dprop('DeviceIsSystemInternal') \
				and dprop('PartitionType') in self.accepted_partitions:

			self.add_volume(device)
	def udisks_device_removed_callback(self, device):
		""" Remove a disk from the local system. """
		assert ltrace('volumes', '| udisks_device_removed_callback(%s)' % device)

		diface, dprop = udisks_device_attributes(device)

		if device in self.volumes.keys():
			self.remove_volume(device)
	def add_volume(self, device):
		""" add a volume from OS data if it doesn't already exist. """

		assert ltrace(self.name, '| add_volume(%s)' % device)

		# NOTE: if parsing /proc/mounts (which is not the case, but this is
		# a note), we've got to replace these nasty \\040 by the real ascii
		# code. This is because space is the field separator in
		# /proc/mounts, and thus in paths it is protected in the \040 octal
		# form.
		# This is not needed when using udisks.
		#
		# mount_point.replace('\\040', '\040')

		diface, dprop = udisks_device_attributes(device)

		if dprop('DeviceIsMounted'):
			mount_point = dprop('DeviceMountPaths')[0]
		else:
			mount_point = self.mount(device)

		kernel_device = dprop('DeviceFilePresentation')

		self.volumes[device] = Volume(device,
				mount_point, kernel_device, self)

		logging.progress('Added device %s (%s) to volumes.' % (
					stylize(ST_DEVICE, kernel_device),
					stylize(ST_PATH, mount_point)
				)
			)
	def remove_volume(self, device):
		""" Remove a volume. """

		assert ltrace(self.name, '| remove_volume(%s)' % device)

		mount_point = self.volumes[device].mount_point
		kernel_device = self.volumes[device].device

		del self.volumes[device]

		logging.progress('Removed device %s (%s) from volumes.' % (
					stylize(ST_DEVICE, kernel_device),
					stylize(ST_PATH, mount_point)
				)
			)
	def scan_one_volume(self, volume):
		""" Gather information about a particular volume and create internal
			object for it, if it doesn't already exist.
		"""

		assert ltrace(self.name, '| scan_one_volume()')

		with self.lock:
			for mount in open('/proc/mounts'):
				device, mount_point, fs_type, mount_opts, \
					fsck_1, fsck_2 = mount.split(' ')

				if device == volume:
					self.add_volume(device, mount_point)
	def mount(self, device):
		""" TODO. """

		with self.lock:
			diface, dprop = udisks_device_attributes(device)

			# TODO: check the FS if needed, before mounting.
			# TODO: report the check in the Volume object, for the user to know
			#		what's going on.


			#, 'acl', 'user_xattr'

			return diface.FilesystemMount(dprop('IdType'),
					['noatime', 'exec'])
	def unmount(self, device):
		""" Un-mount a device, provided it is not a system internal one. """

		diface, dprop = udisks_device_attributes(device)

		with self.lock:

			if device in self.keys():

				# TODO: catch any failure and use the "force" option.

				diface.FilesystemUnmount()

				if os.path.exists(mount_point):
					os.unlink(mount_point)
			else:
				raise exceptions.BadArgumentError('%s: unmount: not a '
					'valid device %s.' % (self.name, device))
	def volumes_call(self, volumes, method_name):
		""" generic method for enable/disable calling on volumes. """

		# TODO: implement partial matching, e.g. "sdb1" will match "/dev/sdb1"
		# and produce the same result as if "/dev/sdb1" has been given.
		#
		# TODO: implement all of this with reverse mappings dicts, this will be
		# much-much simpler and won't duplicate the code...

		assert ltrace(self.name, '| volume_call(%s, %s)' % (volumes, method_name))

		with self.lock:
			devices     = self.keys()
			by_mntpnt   = dict([ (vol.mount_point, vol) for vol in self.values() ])
			by_kernel   = dict([ (vol.device, vol) for vol in self.values() ])
			mount_points = by_mntpnt.keys()
			kernel_devices = by_kernel.keys()

			for volume in volumes:
				if volume in kernel_devices:
					getattr(by_kernel[volume], method_name)()

				elif volume in devices:
					getattr(self[volume], method_name)()

				elif volume in mount_points:
					getattr(by_mntpnt[volume], method_name)()

				else:
					logging.warning2('Skipped non existing device or '
						'mount_point %s.' % volume)
	def add_volumes(self, volumes):
		""" try to enable the given volumes.

			:param volumes: a list of devices or mount points, given as strings,
				to enable.
		"""
		return self.volumes_call(volumes, 'enable')
	def del_volumes(self, volumes):
		""" try to disable the given volumes.

			:param volumes: a list of devices or mount points, given as strings,
				to disable.
		"""
		return self.volumes_call(volumes, 'disable')
	def get_CLI(self, opts, args):
		""" TODO """

		#print '>> ', self.volumes.keys()

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
					if hasattr(volume, 'mount_point') else ' not mounted',
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
