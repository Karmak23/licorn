
.. _extensions.volumes.dev.en:

=========================================
Volumes extension developer documentation
=========================================

Technical details
=================

Server side
-----------

* Checks pluged-in volumes via ``udev``.
* inhibits the ``udisks`` daemon while operating, to avoid conflicts.
* Waits for **partitions** to come up, and automount them in :file:`/media`. This implies that `volumes` doesn't care about raw disks, and doesn't offer anything for them (but this could change in the near future).
* offers CLI commands to manipulate volumes (see above).

Client side
-----------

* **nothing yet**, but we could imagine forwarding connected volumes names and paths to thick-clients to allow them to backup their data on the server. This doesn't concern /home, which is remotely mounted and already backed up by the server.


Classes documentation
=====================

.. automodule:: licorn.extensions.volumes
	:members:
	:undoc-members:
