.. _install.en:

====================
Installing the beast
====================

.. highlight:: bash


From packages
=============

The stable version of Licorn is packaged for `Ubuntu Lucid 10.04 LTS` and higher, but is only accessible to our customers (you need a login/password provided by us). If you are one of them, get the packages from the APT repository below. Else, skip to :ref:`installation from sources<install.from_sources.en>`::

	deb http://login:password@packages.licorn.org/ubuntu/ <codename> main restricted

Where `<codename>` should be `lucid`, `maverick` and so on.

Here are a few package names:

.. glossary::

	licorn-ldap-server
		The most common installation nowadays on servers: it pulls in all the Licorn® server parts and the LDAP backend (and its default configuration). After installing this package, Licorn® is **ready-to-be-used**.

	licorn-server
		A not-so-intrusive option: it will install all the necessary parts for quickstarting a Licorn® server, with only the `shadow` backend configured. You can install the LDAP server package afterwards if you change your mind.

	licorn-client
		Install this package on the client machines on your network, this will make them remote-drivable from the server for many system management tasks. Technically, this pulls in exactly the same code as in the server packages: only the configuration is different.

All these packages will install some other depandencies (most notably `python-licorn`, `licorn-bin` and a few other `python-*` packages). For more details, see `the Debian package documentation <http://dev.licorn.org/wiki/UserDoc/DebianPackagesDependancies>`_ on the developper site.


.. _install.from_sources.en:

From sources
============

.. warning:: This installation is intended **FOR DEVELOPERS ONLY**. It can cause damage on your system or don't work at all if you miss something during this procedure.

Base installation
-----------------

This will install Licorn® in :ref:`local server mode <settings.role.en>`, making developement easy: just hit `[Control-R]` on the daemon's terminal to reload it with your modified code. Feel free to :ref:`reconfigure it <configuration.en>` after installation took place.

.. note:: you should be a valid `sudo` user before starting this installation. On Ubuntu, there should be no problem by default. On Debian you should add yourself to the ``sudo`` group.

#. Install `git`, `git-flow` and a few needed packages::

	sudo apt-get install git-core git-flow make gettext python-sphinx

#. Get the source localy with darcs::

	mkdir sources && cd sources
	[ -d licorn ] && ( cd licorn; git pull )
	[ -d licorn ] || git clone dev.licorn.org:/home/groups/licorn.git licorn

#. Install for developement::

	cd licorn && make devinstall
	# From here, you don't need `sudo` anymore to use Licorn®.

	# whenever you want, to uninstall everything:
	#make uninstall

#. optional : to get `licornd` started at boot, get the init-script, and configure it::

	sudo cp contrib/init-script /etc/init.d/licornd
	sudo update-rc.d licornd defaults 98

.. note:: for Debian / Ubuntu with :program:`upstart`: how we should integrate with :program:`upstart` is not clear, there is no :program:`upstart` script yet.

#. optional: launch the daemon with `licornd -rvD`. `-v` (*verbose*) is optional, `-D` makes the daemon stay attached to your terminal instead of forking into the background. This step is optional because every CLI tool will fork the daemon if needed.
#. enjoy Licorn® on your Linux system: you can use :ref:`CLI tools <quickstart.cli.en>`, or the :ref:`WMI <quickstart.wmi.en>`. Head over to the :ref:`Quickstart <quickstart.en>` for more information.

LDAP Support
------------

#. Prepare your system for `slapd` installation:

	- Make sure your machine has a FQDN in `/etc/hostname`;
	- Make sure `hostname` outputs this name correctly;
	- Make sure `dnsdomainname` outputs the domain part of the FQDN, or edit `/etc/hosts` to make it read like this::

		127.0.1.1	machine-name.my.complete.fqdn machine-name

#. Install LDAP support (client/server)::

	sudo apt-get install --yes --force-yes slapd libnss-ldap libpam-ldap

#. Configure the debian packages with ``dc=my,dc=complete,dc=fqdn``;

#. Restart `licornd` to make it detect the lib*-ldap installation::

	licornd -r

#. Then activate the OpenLDAP extension. This makes `licornd` activate LDAP system-wide via NSS::

	mod config -b openldap

Once activated, the LDAP backend has precedence over `shadow` for new user accounts and groups. You can still create users/groups in the `shadow` backend by using the ``--backend shadow`` CLI switch.

