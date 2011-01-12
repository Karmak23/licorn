
.. _extensions.rdiffbackup.dev:

==============================================
Rdiff-backup extension developer documentation
==============================================

Technical details
=================

Server side
-----------

* Offers interval-configurable automatic incremental backups.
* [TODO] automatic cleaning of old backups.
* [TODO] lists backups on connected volumes.
* [TODO] CLI/WMI semantics for restoring files / dirs.
* [TODO] manual cleaning, moving backups from a volume to another.


Client side
-----------

* **nothing yet**, but we could imagine backing up thick-clients or other servers over the network (see :ref:`extensions.volumes` for idea centralization).


Classes documentation
=====================

.. automodule:: licorn.extensions.rdiffbackup
	:members:
	:undoc-members:
