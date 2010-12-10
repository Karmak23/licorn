.. _implementation:

========================
Licorn®'s implementation
========================

Users, groups & profiles
========================

- Users

-Groups

	- system groups:
		- are *visually* hidden
		- don't hold a sharedir
		- are not accessible via WMI
	- we never alter GID < 300, but we use GID(100) as a base for default profile

- Profiles

	- used as primary groups for user accounts => only one per user



The Licorn® daemon
==================

Has a lot of threads. Some of them are started only in `SERVER` mode, others only in `CLIENT` mode, a certain part are common to both.


File & perms related threads
----------------------------

.. glossary::

	INotifier
		Receives events on files / dirs from `gamin` and forwards them to the `ACLChecker`.

	ACLChecker
		Receives check requests from `INotifier`. Automatically applies ACLs and standard posix perms when needed.
	
	
Network related threads
-----------------------

.. glossary::

	NetworkLinksBuilder
		Started at daemon boot, to scan the network and ping all known machines. Terminates after the first scan
		
	Reverser-*
		A pool of threads to handle reverse DNS requests.
	
	Pyrofinder-*
		A pool of threads to lookup pyro daemon on networked hosts.
		
	Arpinger-*
		A pool of threads to lookup ethernet addresses of networked hosts.
		
	
System management related threads
---------------------------------

.. glossary::

	WMIThread
		Implements a limited webserver, serving pure virtual semantic URIs and static files (images, CSS, JS...). Implemented as a forked process in the past (doing CLI calls), the WMI has reintegrated the daemon to avoid data duplication and resource waste (forks, sockets, argument and data reparsing...) between the daemon and an external process.

General use threads
-------------------

.. glossary::

	MainThread
		Depending on :ref:`licornd's role <licornd.core>`, the `Mainthread` will set up and launch a different pack of threads. Some are common, though.

	PeriodicThreadsCleaner
		Watches for dead or terminated threads and wipe them from memory. The job is accomplished every :term:`licornd.threads.wipe_time` seconds, and 30 seconds after the daemon started. The start value is fixed and non-negociable, while the cycle period is customizable via the sus-named configuration directive.
more to come...
