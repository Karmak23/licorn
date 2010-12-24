.. _opensshextension:

=================
OpenSSH extension
=================

The `OpenSSH` extension affects primarily the server.

Server side
===========

* Adds ``AllowGroups`` directive to restrict system access to groups ``admins`` (Licorn® administrator group) and ``remotessh`` (for standard or system users; not administrators).
* Denies ``PermitRootLogin`` by default.
* Checks ``sshd`` running status.
* start/stop/restart/reload ``ssh`` service when needed.

Client side
===========

* nothing yet, but we could imagine the same configuration, only for admins (not even remotessh members, I don't know). Feel free to `submit ideas on the development site <http://dev.licorn.org/newticket>`_.

Class documentation
===================

.. automodule:: licorn.extensions.openssh
	:members:
	:undoc-members:
