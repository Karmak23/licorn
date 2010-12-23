.. _opensshextension:

=================
OpenSSH extension
=================

The `OpenSSH` extension affects primarily the server.

Server side
===========

* checks ``sshd`` running status
* Adds ``AllowGroups`` directive to restrict system access.
* Denies ``PermitRootLogin`` by default.
* start/stop/restart/reload ``ssh`` service when needed.

Client side
===========

* nothing yet, but we could imagine the same configuration, only for admins (not even remotessh members, I don't know). Feel free to `submit ideas on the development site <http://dev.licorn.org/newticket>`_.

Class documentation
===================

.. automodule:: licorn.extensions.openssh
	:members:
	:undoc-members:
