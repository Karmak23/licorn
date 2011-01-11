.. _extensions.volumes:

=================
Volumes extension
=================

**this is a work in progress.**

The `Volumes` extension takes care of external mass storage devices.

It watches when you plug them in and out, offers ability to mount/unmount/autodiscover them, and makes the attached volumes available to other parts of Licorn® (e.g. :ref:`rdiffbackup` and possibly others).

.. _extensions.volumes.usage:

Usage
=====

Any device you want to use with Licorn must be formatted with one of these file-systems:

* ext2 / ext3 / ext4
* btrfs
* xfs
* jfs
* reiserfs

.. note:: any non-formatted or other-formatted device will not be used by Licorn®; it will thus not be automatically mounted.

Connecting a volume just requires your human energy to plug the device in one of the server's USB, eSATA or FireWire ports (it will be detected automatically ; if it doesn't after having waited 10 to 20 seconds, your server has probably serious problem; please contact support@licorn.org).

Once the device is connected, it will be automatically mounted in file:`/media`. If the partition has a label, the mount-point will be :file:`/media/partition_label`, else it will be something more complicated (the partition UUID, something like ``dafd9069-e7de-4f5f-bc09-a7849b2d5389``, which identifies this partition in a unique way), and the mount-point will be accordingly complicated, like :file:`/media/dafd9069-e7de-4f5f-bc09-a7849b2d5389`.

General usage
-------------

Some CLI commands related to volumes (remember that you can use either the device name (:file:`/dev/...`) or the mount_point (:file:`/media/...`)to act on a given volume)::

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

Detailled functionnalities
==========================

Server side
-----------

* Checks pluged-in volumes via ``udev``.
* Waits for partitions to come up, and automount them in :file:`/media`.
* offers CLI commands to manipulate volumes (see above).

Client side
-----------

* **nothing yet**, but we could imagine forwarding connected volumes names and paths to thick-clients to allow them to backup their data on the server. This doesn't concern /home, which is remotely mounted and already backed up by the server.

Class documentation
===================

.. automodule:: licorn.extensions.volumes
	:members:
	:undoc-members:
