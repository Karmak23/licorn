.. _extensions.samba:

===============
Samba extension
===============

*NOTE: this is a work in progress.*

The `Samba` extension affects only the server. It handles ``smbpasswd`` calls for user account creation and password synchronization.

Server side
===========

* checks /etc/samba/smb.conf for samba presence
* start/stop/restart/reload SMB services when configuration changes

Client side
===========

* nothing yet. perhaps winbind sychronization will be pulled in someday. Feel free to ask for new functionnalities.
