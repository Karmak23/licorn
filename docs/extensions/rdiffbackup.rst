.. _extensions.rdiffbackup:

======================
Rdiff-backup extension
======================

*this is a work in progress.*

The `Rdiff-backup` extension takes care of backups on external volumes.

Server side
===========

* Offers interval-configurable incremental backups. Backups are completely automatic, provided you plugin any external mass storage device, formated in
* [TODO] idem for auto-cleaning of backups.
* [TODO] lists backups on connected volumes.
* [TODO] offers the semantics for restoring files / dirs.
* idem for manual cleaning, compressing.

Supported backup devices
------------------------

* any external mass storage device.
* must be formated for GNU/Linux with an ACL-compatible file-system (see :ref:`volumes usage <extensions.volumes.usage>`)
* must be reserved for Licorn® use (see :ref:`volumes usage <extensions.volumes.usage>`)

Client side
===========

* **nothing yet**, but we could imagine backing up thick-clients over the network (see :ref:`extensions.volumes` for idea centralization).

Class documentation
===================

.. automodule:: licorn.extensions.rdiffbackup
	:members:
	:undoc-members:
