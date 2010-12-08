.. _daemon:

.. highlight:: bash


The Licorn® daemon
==================

`licornd` handles all the dirty job for you. It manages the system, updates `/etc`, modifies users, groups, checks files permissions and `POSIX.1e` ACLs, so you never have to handle them manually. It has a **top-like information interface**, and even a built-in python interpreter if you need to gather specific informations.

Behinds this seems-quite-huge presentation, you will find a big-balled but very administrator-friendly program.

Start and auto-start
--------------------

Provided that you are an administrator of the current machine (member of group `admin`), **any attempt to use CLI tools will automatically launch the daemon** in the background, if it is not already running. The daemon currently takes less than a second to be fully operationnal and operate the CLI command you initialy launched.

If for any reason you need to start it by hand, just do it the simple way::

	licornd
	
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
	
	
