.. _extensions.volumes:

=================
Volumes extension
=================

*this is a work in progress.*

The `Volumes` extension takes care of external disks pluged in and out, and connects them to other parts of Licorn®. Its only functionnality is to reference volumes and make them available for other extensions (e.g. :ref:`rdiffbackup` and possibly others).

Server side
===========

* Checks pluged-in volumes when they are mounted (via inotify).
*

Client side
===========

* **nothing yet**, but we could imagine forwarding connected volumes names and paths to thick-clients to allow them to backup their data on the server. This doesn't concern /home, which is remotely mounted and already backed up by the server.

Class documentation
===================

.. automodule:: licorn.extensions.volumes
	:members:
	:undoc-members:
