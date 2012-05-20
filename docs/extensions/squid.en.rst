.. _extensions.squid.en:

===============
Squid extension
===============

*NOTE: this is a work in progress.*

The `Squid` extension handles the web and FTP proxy configuration, and affects Licorn® clients and servers. It is extensively tested on Squid 2.7, and has been modified to work with Squid 3 (but not tested as much as 2.7).

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


Developper documentation
========================

see the :ref:`squid extension dedicated developer documentation <extensions.squid.dev.en>`.
