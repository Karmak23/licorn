.. _extensions.rdiffbackup:

======================
Rdiff-backup extension
======================

*this is a work in progress.*

The `Rdiff-backup` extension takes care of backups on external volumes.

Server side
===========

* lists backups on connected volumes.
* implement incremental backups (day / week / month / year).
* offers the semantics for restoring files / dirs.
* idem for auto-cleaning of backups.
* idem for manual cleaning, compressing.


Client side
===========

* **nothing yet**, but we could imagine backing up thick-clients over the network (see :ref:`extensions.volumes` for idea centralization).

Class documentation
===================

.. automodule:: licorn.extensions.rdiffbackup
	:members:
	:undoc-members:
