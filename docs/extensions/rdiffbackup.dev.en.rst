
.. _extensions.rdiffbackup.dev.en:

==============================================
Rdiff-backup extension developer documentation
==============================================

Technical details
=================

Server side
-----------

* Offers interval-configurable automatic incremental backups.
* Automaticaly cleans old backups; always keep TWO of them.
* Lists backups on connected volumes.
* [TODO] CLI/WMI semantics for restoring files / dirs.
* [TODO] manual cleaning, moving backups from a volume to another.


Client side
-----------

* **nothing yet**, but we could imagine backing up thick-clients or other servers over the network (see :ref:`volumes <extensions.volumes.en>` for idea centralization).

Internal events and extension status
====================================

* ``event('active')``:
	* ``True`` if the backup timer runs. Means that there is at least a backup enabled volume connected.
	* ``False`` if the timer is Off; means that there is no **enabled** volume connected, but there could be volumes waiting to be enabled.

* ``event('running')``:
	* implies ``events('active')`` == ``True``
	* means that a volume is connected, mounted and locked, e.g. ``self.current_operated_volume`` is not ``None``.
	* means that a backup operation (or statistics computations) is currently running.

Classes documentation
=====================

.. automodule:: licorn.extensions.rdiffbackup
	:members:
	:undoc-members:


