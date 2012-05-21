.. _extensions.samba3.en:

================
Samba3 extension
================


The `Samba` extension affects only the server. It is currently very basic, and handles ``smbpasswd`` calls for user account creation/deletion and password synchronization.

Server side
===========

As of version 1.3, the `samba3` extension:

* checks :file:`/usr/bin/smbpasswd` for ``samba``'s presence and mark itself available/enabled accordingly. This means that the samba daemons can be installed on another machine, and you can configure smbpasswd to interact with them remotely without any problem.
* The file :file:`smb.conf` remains untouched by Licorn®.


.. todo::
	* start/stop/restart/reload SMB services when configuration changes

Client side
===========

* nothing yet. perhaps winbind sychronization will be pulled in someday. Feel free to ask for new functionnalities.


.. _extensions.samba3.faq.en:

Frequently Asked Questions
==========================

When I delete a user account via Licorn®, i see samba3 warning messages in the Licorn® daemon's log
---------------------------------------------------------------------------------------------------

The messages appear as follow::

	[…] samba3: pdb_get_group_sid: Failed to find Unix account for <user>
	[…] samba3: Failed to delete entry for user <user>.

These messages are perfectly normal and don't affect the system operations. Samba tries to delete the Unix account of the user, which has already been handled by Licorn®. These messages can't be supressed because Samba is configured by default to synchronize Unix passwords, in case a user changes his password on a Windows/Mac machine.

