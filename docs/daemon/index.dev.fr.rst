
=================
Le daemon Licorn®
=================

** à traduire**

Has a lot of threads. Some of them are started only in `SERVER` mode, others only in `CLIENT` mode, a certain part are common to both.

Threads description
===================

File & perms related threads
----------------------------

.. glossary::

	INotifier
		Receives events on files / dirs from `gamin` and forwards them to the :term:`ACLChecker`.

	ACLChecker
		Receives check requests from `INotifier`. Automatically applies ACLs and standard posix perms when needed. For more technical details, head to the :ref:`ACLChecker dedicated documentation <aclchecker>`.


Network related threads
-----------------------

.. glossary::

	NetworkLinksBuilder
		Started at daemon boot, to scan the network and ping all known machines. Terminates after the first scan

All threads after this point are grouped in pools. You can :term:`adjust the number of *poolers* in the configuration <licornd.threads.pool_members>`.

	Reverser-*
		A pool of threads to handle reverse DNS requests.

	Pyrofinder-*
		A pool of threads to lookup pyro daemon on networked hosts.

	Arpinger-*
		A pool of threads to lookup ethernet addresses of networked hosts.

	Pinger-*
		A pool of simple pingers, to find the current status of hosts (online or not).

	IPScanner-*
		A pool of advanced network scanner threads: they ping hosts, and if hosts are up, they chain data to other network threads to gather the maximum information about the host beiing scanned. Can be seen as a part of :program:`nmap` integrated into `licornd`. These threads are used in all network detection and scanning.

System management related threads
---------------------------------

.. glossary::

	WMIThread
		Implements a limited webserver, serving pure virtual semantic URIs and static files (images, CSS, JS...). Implemented as a forked process in the past (doing CLI calls), the WMI has reintegrated the daemon to avoid data duplication and resource waste (forks, sockets, argument and data reparsing...) between the daemon and an external process.

	CommandListener
		Dedicated to RPC for inter-process (currently :ref:`CLI` only) and inter-machine communications (via the `Pyro <http://www.xs4all.nl/~irmen/pyro3/>`_ exported objects :term:`SystemController` and :term:`MessageProcessor`). for more technical details, see :ref:`cmdlistener` development documentation.

General use threads
-------------------

.. glossary::

	MainThread
		Depending on :ref:`licornd's role <licornd.role>`, the `Mainthread` will set up and launch a different pack of threads. Some are common, though.

	PeriodicThreadsCleaner
		Watches for dead or terminated threads and wipe them from memory. The job is accomplished every :term:`licornd.threads.wipe_time` seconds, and 30 seconds after the daemon started. The start value is fixed and non-negociable, while the cycle period is customizable via the sus-named configuration directive.

	QueuesEmptyer
		Periodically (delay configured via :term:`licornd.threads.wipe_time` too) empties all network queues, when daemon :term:`network features are disabled <licornd.network.enabled>`. This thread exists not to waste system resources, because the queues still needs to be created for the Machines part to continue working.

Internals
=========

.. toctree::
	:maxdepth: 2

	init
	core
	main
	cmdlistener
	aclchecker
