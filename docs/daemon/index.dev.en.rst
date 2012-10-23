
.. _daemon.dev.en:

==================
The Licorn® daemon
==================

Has a lot of threads. Some of them are started only in `SERVER` mode, others only in `CLIENT` mode, a certain part are common to both.

Threads description
===================

File & perms related threads
----------------------------

.. glossary::

	INotifier
		Receives events on files and directories from `pyinotify` and forwards them to ACLChecker service threads.

	ACLChecker
		Dynamically-started members of a pool, responsible of applying ACLs on filesystems. They have :ref:`configuration directives <settings.threads.aclchecker_min.en>`.

System management related threads
---------------------------------

.. glossary::

	WMIThread
		Implements a limited webserver, serving pure virtual semantic URIs and static files (images, CSS, JS...). Implemented as a forked process in the past (doing CLI calls), the WMI has reintegrated the daemon to avoid data duplication and resource waste (forks, sockets, argument and data reparsing...) between the daemon and an external process.

	CommandListener
		Dedicated to RPC for inter-process (currently :ref:`CLI <cli.en>` only) and inter-machine communications (via the `Pyro <http://www.xs4all.nl/~irmen/pyro3/>`_ exported objects like the :class:`licorn.foundations.messaging.MessageProcessor`). for more technical details, see :ref:`cmdlistener <cmdlistener.en>` development documentation.

General use threads
-------------------

.. glossary::

	MainThread
		Depending on :ref:`licornd's role <settings.role.en>`, the `Mainthread` will set up and launch a different pack of threads. Some are common, though.

	PeriodicThreadsCleaner
		Watches for dead or terminated threads and wipe them from memory. The job is accomplished every :ref:`threads.wipe_time <settings.threads.wipe_time.en>` seconds, and 30 seconds after the daemon started. The start value is fixed and non-negociable, while the cycle period is customizable via the sus-named configuration directive.

	ServiceWorkerThread
		Dynamically-started members of a pool, dedicated to *generic* tasks, which can be CPU-consuming. `ServiceWorkerThread` instances usually start external processes and handle events processing in the daemon.  They have :ref:`configuration directives <settings.threads.service_min.en>`.

	NetworkWorkerThread
		Dynamically-started members of a pool, dedicated to *network* tasks, and by extension CPU-light and other short-time but potentially blocking tasks. Typically, scanning the local network needs a lot of parallel workers, and many of them will timeout after a period of time, during which they cannot be assigned to anything else.  They have :ref:`configuration directives <settings.threads.network_min.en>`.

Internals
=========

.. toctree::
	:maxdepth: 2

	base.en
	main.en
	cmdlistener.en
