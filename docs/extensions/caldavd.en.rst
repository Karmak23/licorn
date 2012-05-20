.. _extensions.caldavd:

=================
Caldavd extension
=================

*this is a work in progress.*

The `Caldavd` extension handles Apple Calendar server and its configuration.

Server side
===========

* Checks caldavd configuration.
* Create a calendar for each newly created user.
* maintain user password up-to-date in caldavd data when a user changes his password.
* in progress: create calendars for groups.


TODO
====

* implement delegation
* create a calendar for already existing users and groups if we install the caldavd service on an already running system. This is kind of a migration support.

Class documentation
===================

.. automodule:: licorn.extensions.caldavd
	:members:
	:undoc-members:
