.. _extensions.volumes:


.. highlight:: bash


=================
Volumes extension
=================

Description
===========

The `Volumes` extension takes care of external mass storage devices.

It watches when you plug them in and out, offers ability to mount/unmount/autodiscover them, and makes the attached volumes available to other parts of Licorn® (e.g. :ref:`extensions.rdiffbackup` and possibly others).

Which devices are supported?
----------------------------

Any device you want to use with Licorn **must be already partitioned and formatted** with one of these file-systems (``posix.1e`` ACLs and ``eXtended ATTRibutes`` capable):

* ext2 / ext3 / ext4
* btrfs
* xfs
* jfs
* reiserfs

Connecting a new volume just requires your human energy to plug the device in one of the server's USB, eSATA or FireWire ports (it will be detected automatically, this can take up to 20 seconds).

**Once the device is connected, it will be automatically mounted** in :file:`/media`.

.. note::
	*Any non-formatted or other-than-supported-FS formatted device will not be used by Licorn®; **it will thus not be automatically mounted**.
	* If the partition has a label, the mount-point will be :file:`/media/partition_label`, else it will be something more complicated (the partition UUID, something like ``dafd9069-e7de-4f5f-bc09-a7849b2d5389``, which identifies this partition in a unique way), and the mount-point will be accordingly complicated, like :file:`/media/dafd9069-e7de-4f5f-bc09-a7849b2d5389`.

.. _extensions.volumes.usage:

Usage
=====


General usage
-------------

Keep in mind that you can use either the device name (:file:`/dev/...`) or the mount_point (:file:`/media/...`) to act on a given volume::

	# get a list of connected / supported volumes, with free space displayed:
	get volumes
	# red-colored devices are not enabled for Licorn®, green-colored are.

	# manually mount any previously manually-dismounted volume:
	add volume /dev/xxx

	# manually unmount a volume (it can be safely ejected after this):
	del volume /dev/xxx

	# unmount all volumes:
	del volumes -a
	# long syntax:
	del volumes --all

	# Reserve (=enable) a volume for Licorn® usage:
	mod volume -e /dev/xxx
	# the long way:
	mod volume --enable /dev/xxx

	# Stop using a given volume for Licorn®:
	mod volume -d /dev/xxx
	# the long way:
	mod volume --disable /dev/xxx


Reserving a volume for Licorn® sole usage
-----------------------------------------

This operation is necessary if you want Licorn® to use a particular volume, else it will just help you (with auto-mounting), but not use it in any ways.

To reserve a volume, just plug the device in, wait a little, and type::

	# show the list of connected volumes:
	get volumes
	[...]

	# enable licorn reservation for the volume:
	mod volumes -e /dev/xxx

	# alternatively, you can use the mount-point:
	mod volumes -e /media/xxxxxx

Once done, this volume will automatically be used by any part of Licorn® requiring a volume to do its job. You don't have to reload or rescan anything.

Troubleshooting
===============

* the device doesn't show up in :command:`get volumes` once connected:

	* first, be sure to have waited 10 to 20 seconds,
	* be sure your volume is already partitionned
	* be sure the partition you want to use is formatted with a supported FS (see above).
	* check if your device shows up in the kernel log (command :command:`sudo dmesg | tail -n 10`). If it doesn't:

		* be sure the device is turned on.
		* check your connection cable, try with another one.
		* your server or the external drive could have a hardware problem. Please contact your dedicated support.

How-to partition and format a volume?
-------------------------------------

You can do this using tools like :command:`gparted`. Search for additionnal information on your community's support website.

See also
========

The :ref:`volumes dedicated developer documentation <extensions.volumes.dev>` can give you additionnal information, if you fit in its audience.
