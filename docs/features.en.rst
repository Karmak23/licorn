.. _features:

=============
Features list
=============


Functionnalities
================

Trying to sum up Licorn® features in a few words is a hard task: simply put, here at `META IT <http://meta-it.fr/>`_ we use Licorn® to manage our GNU/Linux systems. Having said that, we can try to list some emerging points:


.. glossary::

	Users management
		* LDAP or Unix shadow account
			* :term:`chk` enforces permissions and ACLs inside the home dir
		* Optional users attributes via :ref:`extensions.en`
			* individual calendar & delegations
			* mail addresses, aliases
			* personnal web folder

	Groups and data sharing
		* Unix or LDAP groups
		* Shares for member (via one special directory linked to all member's homes)
			* shares can be :ref:`permissive or not <permissiveness.en>`
			* shares are inotified by daemon, permissions are live-enforced
			* ref:`chk.en` enforces permissions, checks symlink in member's homes and other sanitizations
		* optional attributes via extensions

	System profiles
		* can be seen as a group template
		* hold default quotas, skell, shell, groups memberships
		* are altered live (existing members get instant modifications), or not

	Machines
		* `machines` refer to computers, networked printers, scanners, routers, etc
		* automatically discovered at runtime from various sources (local lease files, local network scan, manual adds)
		* if Licorn® is installed on remote clients / servers, you get:
			* web-proxy automatic configuration
			* remote power off and extended status if supported
			* coming feature: remote upgrades (can be interactive with GNU/Linux clients)
			* coming feature: remote generic settings apply (env / gconf / KDE / win32)

	Backups
		* handles automatically :ref:`external mass storage <extensions.volumes.en>` devices and :ref:`runs automatic backup <extensions.rdiffbackup.en>` at regular date/time.

	Printers
		* coming feature: complete and transparent CUPS integration

	Configuration and System
		* centralize and alter system-wide parameters and other daemons configuration (:program:`apache`, :program:`postfix`, :program:`dnsmasq`, etc)
		* enable or disable backends and extensions at runtime
		* remote execution and configuration


To complement this feature list or to have more detailled information, you can read:

.. toctree::
	:maxdepth: 1

	core/backends/index.en
	extensions/index.en
	implementation.en


Technologies
============

These software or services are used or supported as base of the system, or via extensions (listed in no particular order):

Currently supported:

- :ref:`Shadow (backend) <core.backends.shadow.en>`
- :ref:`OpenLDAP (backend) <core.backends.openldap.en>`
- :ref:`DNSmasq (backend) <core.backends.dnsmasq.en>`
- SaMBa (currently: basic integration in the controllers)
- :ref:`caldavd (extension) <extensions.caldavd.en>`
- :ref:`squid (extension) <extensions.squid.en>`
- :ref:`basic volumes management (extension) <extensions.volumes.en>`
- :ref:`Rdiff Backup (extension) <extensions.rdiffbackup.en>`

Under development or planned:

- samba (as featured extension)
- postfix (as extension)
- apache2 (as extension)
- BIND9 / DHCPd3 (as backend)

Licorn® is built upon these technologies (listed in no particular order):

* the beloved `Python <http://python.org/>`_ programming language,
* the `Pyro <http://www.xs4all.nl/~irmen/pyro3/>`_ remote object distribution system,
* `POSIX.1e ACLs <http://en.wikipedia.org/wiki/Access_control_list>`_,
* File-system `user eXtended ATTributes <http://en.wikipedia.org/wiki/Extended_file_attributes>`_,
* SQLite3,
* `udev <http://en.wikipedia.org/wiki/Udev>`_ (`fr <http://fr.wikipedia.org/wiki/Udev>`_), `udisks <http://freedesktop.org/wiki/Software/udisks>`_,
* `rdiff-backup <http://www.nongnu.org/rdiff-backup/index.html>`_
* GTK+ for graphical interfaces,
* some (but not much) python external modules, like the multi-platform `netifaces` module, the `dumbnet` module and others.

