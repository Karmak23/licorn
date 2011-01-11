
.. _daemon:

.. highlight:: bash


The Licorn® daemon
==================

`licornd` handles all the dirty job for you. It manages the system, users, groups and all other valuable objects. It updates `/etc`, monitors shared group dirs and automatically checks and enforces files permissions and `POSIX.1e` ACLs in there, so you never have to handle them manually. It also **runs the WMI** as a thread, provides a **top-like information interface** when you start it attached to the terminal, and even a built-in python interpreter if you need to gather specific informations or just want to be curious about its internals.

Behinds this seems-quite-huge presentation, you will find a big-balled but very administrator-friendly program.

Start and auto-start
--------------------

**In standard conditions, the daemon start and stop process is completely automatic**: it is managed by your GNU/Linux distribution startup scripts. For example on Debian & Ubuntu, :program:`licornd` is started at boot and stopped on reboot or halt, without any further human intervention. You can start / stop / restart it by using the :command:`service` system command (refer to your distro documentation for more details).

Though, you could want to know how to handle it yourself, because you can completely interfere with the system service handlers without any trouble.

Provided that you are an administrator of the current machine (member of group `admin`), **any attempt to use CLI tools will automatically launch the daemon** in the background, if it is not already running. **The daemon takes less than a second to be fully operationnal** and answers to the CLI command you initialy launched.

If for any reason you need to start it by hand, just do it the simple way::

	licornd

If you want it to stay on your terminal and display nice information messages::

	licornd --verbose --no-daemon

	# the short way:
	licornd -vD

Given there is already another daemon running and you want to replace it with another one::

	licornd --replace

	# the command i use often during debug phases to retake
	# control over a daemon already forked in the background:
	licornd -rvD

Note that using the :option:`--replace` flag won't hurt if there's no daemon running: the program will just continue as if you didn't provided it.


Configuration
-------------

    * its log : `/var/log/licornd.log`
    * the config file : `/etc/licorn/main.conf`


Interactive sessions
--------------------

For some reason, you will need to interact directly with the daemon (Actually, this can be fun!). Just start it with a special flag::

	licornd -D
	# or:
	licornd -vD
	# and so on with -vvD and -vvvD


Daemon's arguments
------------------

Please refer to integrated help for an exhaustive listing of the daemon's CLI arguments, they are documented online::

	licornd --help


