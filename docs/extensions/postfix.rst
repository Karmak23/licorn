.. _postfixextension:

===============
Postfix extension
===============

*NOTE: this is a work in progress.*

The `Postfix` extension affects primarily the server and can affect the clients if postfix is installed.

Server side
===========

* checks /etc/postfix/main.cf for postfix presence
* analyzes main.cf for mailbox type
* checks /etc/default/postfix for activation status
* start/stop/restart/reload postfix service when configuration changes

Client side
===========

* [not yet] configure client as a satellite system (mail relay).
