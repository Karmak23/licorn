.. _extensions.rdiffbackup.en:

======================
Rdiff-backup extension
======================

The `Rdiff-backup` extension takes care of backups on external volumes. Backups include system specific data (configuration), and all user data (basically, :file:`/home/` contents).

Currently, backups are not compressed nor encrypted. The first backup will need at least 1Gib of free space (for system data), added to your own data volume (the :file:`/home/` contents).

Backups are incremental, and each increment take only a few space more (this actually depends on the volume of changing data, so this can vary a lot from a system to another).

Usage
=====

Supported backup devices
------------------------

Any external mass storage device, already formated and enabled for Licorn® (see :ref:`volumes usage <extensions.volumes.usage>` to know how to do it).

Backup operations
-----------------

Currently, **backup operations are fully automatic**, provided a backup volume is plugged in. If you must unplug the device, the automatic backup will continue once you have plugged it back in, without any further action.

Backup interval can be customized via the :term:`backup.interval` configuration directive, and thats all for now.

.. note:: even if you can plug in and enable more than one device on the system, **backups are done on the first connected device only**. If you want to rotate backups on more than one disk, you must plug them one at a time.

Restore operations
------------------

Currently, **restore operations are fully manual** and must be done outside Licorn®. This issue is currently beiing adressed by the developers and will soon be available.


Developper documentation
========================

see the :ref:`rdiffbackup extension dedicated developer documentation <extensions.rdiffbackup.dev.en>`.
