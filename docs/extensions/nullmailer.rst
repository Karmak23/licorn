.. _nullmailerextension:

====================
Nullmailer extension
====================

*NOTE: this is a work in progress.*

The `Nullmailer` extension affects primarily the server and can affect the clients if ``nullmailer`` is installed there.

Server side
===========

* checks /etc/??? for ``nullmailer`` presence
* start/stop/restart/reload ``nullmailer`` service when configuration changes

Client side
===========

* [not yet] configure client as a satellite system (mail relay) to the server.
