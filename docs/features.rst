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
		* Optional users attributes via :ref:`extensions`
			* individual calendar & delegations
			* mail addresses, aliases
			* personnal web folder

	Groups and data sharing
		* Unix or LDAP groups
		* Shares for member (via one special directory linked to all member's homes)
			* shares can be :ref:`permissive or not <groupspermissions>`
			* shares are inotified by daemon, permissions are live-enforced
			* ref:`chk` enforces permissions, checks symlink in member's homes and other sanitizations
		* optional attributes via extensions

	System profiles
		* can be seen as a group template
		* hold default quotas, skell, shell, groups memberships
		* are altered live (existing members get instant modifications), or not

	Machines
		* `machines` refer to computers, networked printers, scanners, routers, etc
		* automatically discovered at runtime from various sources (local lease files, local network scan, manual adds)
		* remote power off if supported (with a Licorn® local install)
		* remote upgrades (can be interactive with GNU/Linux clients)
		* remote generic settings apply (env / gconf / KDE / win32)

	Printers
		* to be documented (CUPS support)

	Configuration and System
		* centralize and alter system-wide parameters and other daemons configuration (:program:`apache`, :program:`postfix`, :program:`dnsmasq`...)
		* enable or disable backends and extensions at runtime
		* remote execution and configuration


To complement this feature list or to have more detailled information, you can read:

.. toctree::
	:maxdepth: 1

	backends/index
	extensions/index
	implementation


Technologies
============

These software or services are used or supported as base of the system, or via extensions (listed in no particular order):

Currently supported:

- :ref:`Shadow (backend) <core.backends.shadow>`
- :ref:`OpenLDAP (backend) <core.backends.openldap>`
- :ref:`DNSmasq (backend) <core.backends.dnsmasq>`
- SaMBa (direct basic integration in the controllers)
- :ref:`caldavd (extension) <extensions.caldavd>`

Under development or planned:

- :ref:`squid (extension) <extensions.squid>`
- :ref:`basic volumes management (extension) <extensions.volumes>`
- :ref:`Rdiff Backup (extension) <extensions.rdiffbackup>`
- samba (extension)
- postfix (extension)
- apache2 (extension)
- BIND9 / DHCPd3 (backend)

Licorn® is built upon these technologies (listed in no particular order):

* the beloved `Python <http://python.org/>`_ programming language,
* the `Pyro <http://www.xs4all.nl/~irmen/pyro3/>`_ remote object distribution system,
* `POSIX.1e` ACLs,
* File-system eXtended ATTributes,
* SQLite3,
* GTK+ for graphical interfaces,
* some (but not much) python external modules, like the multi-platform `netifaces` module, the `dumbnet` module and others.

