
.. _extensions.mylicorn.dev.en:

===========================================
MyLicorn® extension developer documentation
===========================================

Technical details
=================

Server side
-----------

A Licorn® daemon in *server* mode:

* Connects to the central `my.licorn.org` server via a JSON-RPC API.
* Handles disconnections and errors gracefully, will retry connection automatically at random intervals.
* provides two properties for the rest of the daemon:

	* ``mylicorn.connected``, which indicates that a session is open to the central server.
	* ``mylicorn.reachable``, whichs indicates that the *current server* is reachable or not from the internet.

* The RPC calls are rate-limited. Anonymous servers cannot make more than 30 calls per hour.
* There can be only one anonymous session per distinct IP.
* If you need more RPC calls, or more server behind the same IP, official price plans will be soon available, but you can still contact me (via ``contact AT licorn DOT org`` for current and specific offers.

The JSON-RPC API is currently not functionnaly limited for servers, which means that besides call quotas, servers can use any method without any other particular restriction.

.. note:: To set your API key in the Licorn® daemon, just type ``get in`` (as member of ``admins`` in the CLI). Once at the daemon prompt, enter ``LMC.extensions.mylicorn.api_key = '…your_api_key…'``. The daemon will save it to :file:`/etc/licorn/mylicorn.conf`, and reauthenticate immediately to benefit from the higher RPC quota.

	You can edit the file manually (it is a simple JSON-encoded text-file), but doing it via the daemon can help avoiding errors, because it will validate the key before using it.

Client side
-----------

Nothing particular. Client licornd connect like servers.


Classes documentation
=====================

.. automodule:: licorn.extensions.mylicorn.mylicorn
	:members:
	:undoc-members:
