.. _install.en:

====================
Installing the beast
====================

.. highlight:: bash


From packages
=============

Typical installation
--------------------


Installation Licorn® from packages is quite simple:

* add an installation source in the file :file:`/etc/apt/sources.list.d/licorn.list` (cf. :ref:`installation sources <install.sources_list.en>`).
* install one of the Licorn® meta-packages (cf. :ref:`packages names <install.packages_names.en>`)::

	sudo apt-get update

	# for example:
	sudo apt-get install licorn-server

	# in case of a big upgrade, which can eventually crash:

	sudo apt-get -f install

* **close your session and open it again** to benefit from Licorn® new ``admins`` group (cf. note below).
* That's it! Head over to the :ref:`Quickstarter <quickstart.en>`.

.. note:: If you were previously a member of the ``sudo`` (on `Debian` and `Ubuntu 12.04` and after) or ``admin`` group (on `Ubuntu 11.10` and previous), **you are now a member of group** ``admins``, the Licorn® administrators.

	If you weren't ``sudo`` nor ``admin`` before installing, you're strongly advised to add yourself or anyone else to group ``admins`` (via ``adduser `whoami` admins``) else nobody will be able to run Licorn® tools!

.. _install.sources_list.en:

Installation sources for `Debian` and `Ubuntu`
----------------------------------------------

The stable version of Licorn® is currently packaged for `Ubuntu` and `Debian`, for versions supported by their respective communities. The prefered distribution to install Licorn® on is `Ubuntu 12.04 LTS (Precise)`. Install the packages from this APT repository::

	deb http://archive.licorn.org/ubuntu/ <codename> main restricted

Where `<codename>` should be `precise` (12.04 LTS) or `lucid` (10.04 LTS).

On Debian, the address is different::

	deb http://archive.licorn.org/debian <codename> main

Where ``<codename>`` is `squeeze`, `wheezy` or `sid`.

.. note:: Licorn® packages can be a little late on `Debian` (regarding `Ubuntu`), or some versions can be unavailable on `testing` and `sid` distributions. `Read the news <http://dev.licorn.org/blog>`_ to get up-to-date informations on the subject.

.. seealso:: To test latest Licorn® packages, participate to software enhancements or benefit new functionnalities quicker, we maintain a dedicated installation channel::

		deb http://daily.licorn.org/{ubuntu/debian} <codename> main

	Contact-us if you plan to participate to the the test program, there are things to win ;-)


.. _install.packages_names.en:

Packages names
--------------

Here are a few package names:

.. glossary::

	licorn-ldap-server
		The most common installation nowadays on servers: it pulls in all the Licorn® server parts and the LDAP backend (and its default configuration, via :program:`debconf`). After installing this package, Licorn® is **ready-to-use**.

	licorn-server
		A less intrusive option: it will install all the necessary parts for quickstarting a Licorn® server, with only the :file`shadow` backend configured. You can install the LDAP server package afterwards if you change your mind.

	licorn-client
		Install this package on the client machines on your network, this will make them remote-drivable from the server for many system management tasks. Technically, this pulls in exactly the same code as in the server packages, but configuration is different and only a subset of services are really run.

All these packages will install some other depandencies (most notably `python-licorn`, `licorn-bin` and other `python-*` packages). For more details, see `the Debian package documentation <http://dev.licorn.org/wiki/UserDoc/DebianPackagesDependancies>`_ on the developper site.

.. note:: Licorn® is a server-management sofware, which means its packages have a lot of ``Recommends``. Licorn® can handle all of them, but you won't necessarily *need* them. It's up to you to install them or not. Licorn® can live without them.

.. seealso:: There are other Licorn® meta-packages that will interest you or not. Use `Debian` or `Ubuntu` tools and search for « ``licorn`` » to obtain an exhaustive list.


.. _install.from_sources.en:

From sources
============

.. warning:: This installation is intended **FOR DEVELOPERS** or system administrators whishing to follow stable channel quicker than packages (Licorn® handles this gracefully). It can cause damage on your system or don't work at all if you miss something during this procedure.

Base installation
-----------------

This will install Licorn® in :ref:`local server mode <settings.role.en>`, making developement easy: just hit `[Control-R]` on the daemon's terminal to reload it with your modified code. Feel free to :ref:`reconfigure it <configuration.en>` after installation took place.

.. note:: you should be a valid ``sudo`` user before starting this installation. On Ubuntu, there should be no problem by default. On Debian you should add yourself to the ``sudo`` group.

#. Install `git`, `git-flow` and a few needed packages::

	sudo apt-get install git-core git-flow make gettext

#. Get the source localy with git::

	mkdir sources && cd sources
	[ -d licorn ] && ( cd licorn; git pull )
	[ -d licorn ] || git clone git://dev.licorn.org/home/groups/licorn.git licorn

#. Install for developement::

	cd licorn && make devinstall
	# From here, you don't need `sudo` anymore to use Licorn®.

	# whenever you want, to uninstall everything:
	#make uninstall

#. optional : to get `licornd` started at boot, get the init-script, and configure it::

	sudo cp contrib/init-script /etc/init.d/licornd
	sudo update-rc.d licornd defaults 98

	# Alternatively, you can simply edit /etc/rc.local and insert
	licornd -r

.. note:: for `Debian` / `Ubuntu` with :program:`upstart`: how we should integrate with :program:`upstart` is not clear, there is no :program:`upstart` script yet.

#. close and re-open your session to be a member of the new ``admins`` groups.

#. enjoy Licorn® on your Linux system: you can use :ref:`CLI tools <quickstart.cli.en>`, or the :ref:`WMI <quickstart.wmi.en>`. Head over to the :ref:`Quickstart <quickstart.en>` for more information.

LDAP Support
------------

#. Prepare your system for :program:`slapd` installation:

	- Make sure your machine has a FQDN in :file:`/etc/hostname`: “``Machine.licorn.local``” is OK, “``Machine``” is not;
	- Make sure :program:`hostname` outputs this name correctly; else run ``sudo hostname -F /etc/hostname``;
	- Make sure :program:`dnsdomainname` outputs the domain part of the FQDN, or edit :file:`/etc/hosts` to make it read like this::

		127.0.1.1	machine-name.my.complete.fqdn machine-name

#. Install LDAP support (client/server)::

	sudo apt-get install --yes --force-yes slapd libnss-ldap libpam-ldap

#. Configure the debian packages with ``dc=my,dc=complete,dc=fqdn``;

#. Restart `licornd` to make it detect the lib*-ldap installation::

	licornd -r

#. Then activate the OpenLDAP extension. This makes `licornd` activate LDAP system-wide via ``NSS``::

	mod config -b ldap

	# or the long way:
	# mod configuration --enable-backend openldap

Once activated, the LDAP backend has precedence over ``shadow`` for new user accounts and groups. You can still create users/groups in the ``shadow`` backend by using the ``--backend shadow`` CLI switch.

Should we continue to the :ref:`Quickstarter <quickstart.en>` ? Or directly to the :ref:` Licorn® daemon <daemon.en>` ? Up to you. All roads go to Rome…
