.. _extensions.squid:

===============
Squid extension
===============

*NOTE: this is a work in progress.*

The `Squid` extension affects clients and server. It handles completely the HTTP/FTP proxy configuration for the local network.

Server side
===========

* checks squid.conf and adds mandatory directives for the local networked clients to be able to connect to squid.
* handles local :file:`/etc/environment` to put in :envvar:`http_proxy` and other needed variables.
* handles squid daemon start/stop/restart when configuration changes.
* idem for gconf/gnome (mandatory setting).
* idem for KDE.

Client side
===========

* handles :file:`/etc/environment` to configure :envvar:`http_proxy` to point to the server.
* idem for gconf/gnome (mandatory setting).
* idem for KDE.

Class documentation
===================

.. automodule:: licorn.extensions.squid
	:members:
	:undoc-members:
