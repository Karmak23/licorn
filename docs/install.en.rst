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

#. Install darcs and required python-packages::

	sudo apt-get -qy --force-yes install nullmailer darcs \
			pyro python-gamin python-pylibacl python-ldap \
			python-xattr python-netifaces python-dumbnet \
			python-pyip python-ipcalc python-dbus \
			python-gobject gettext python-pygments \
			python-gevent python-sqlite python-django \
			python-jinja2 python-pip

	sudo pip install djinja

#. Given the Ubuntu distro you have::

	# On Ubuntu <= Natty, you need our private package repository for this one (contact us):
	sudo apt-get install --yes --force-yes python-udev

	# On Oneiric, python-pyudev is available:
	sudo apt-get install --yes --force-yes python-pyudev

#. About `python-pylibacl`: be sure to install at least version *0.3*.
#. Get the source localy with darcs::

	mkdir sources
	cd sources
	if [ -d licorn ]; then
		(
			cd licorn
			darcs pull -a
		)
	else
		darcs get dev.licorn.org:/home/groups/darcs-Licorn licorn
	fi

#. Make symlinks onto you Debian/Ubuntu-like Linux distribution::

	# export this variable to wherever your Licorn® source is.
	export LCN_DEV_DIR=~/sources/licorn

	for i in add mod del chk get
	do
		sudo rm -f /usr/bin/${i}
		sudo ln -sf "${LCN_DEV_DIR}/interfaces/cli/${i}.py" /usr/bin/${i}
		sudo chmod a+x /usr/bin/${i}
	done

	sudo rm -f /usr/sbin/licornd*
	sudo ln -sf "${LCN_DEV_DIR}/daemon/main.py" /usr/sbin/licornd
	sudo ln -sf "${LCN_DEV_DIR}/daemon/wmi.py" /usr/sbin/licornd-wmi
	sudo chmod a+x /usr/sbin/licornd*

	sudo mkdir -p /etc/licorn
	sudo ln -sf "${LCN_DEV_DIR}/config/check.d" /etc/licorn

	sudo mkdir -p /usr/share/licorn
	sudo ln -sf "${LCN_DEV_DIR}/interfaces/wmi" /usr/share/licorn/wmi
	sudo ln -sf "${LCN_DEV_DIR}/core/backends/schemas" \
		/usr/share/licorn/schemas
	sudo ln -sf "${LCN_DEV_DIR}/locale/fr.mo" \
		/usr/share/locale/fr/LC_MESSAGES/licorn.mo
	sudo ln -sf "${LCN_DEV_DIR}/locale/fr.js.mo" \
		/usr/share/locale/fr/LC_MESSAGES/licornjs.mo

#. Some version dependant links:

  * Under debian / Ubuntu <= Natty Narwhal (Python 2.7)::

        sudo ln -sf "${LCN_DEV_DIR}" /usr/lib/python2.7/site-packages/licorn

  * Under debian / Ubuntu *>= Lucid* (Python 2.6)::

	sudo ln -sf "${LCN_DEV_DIR}" /usr/lib/python2.6/dist-packages/licorn

  * Under debian / Ubuntu <= Karmic (Python 2.5)::

        sudo ln -sf "${LCN_DEV_DIR}" /usr/lib/python2.5/site-packages/licorn

#. optional : to get `licornd` started at boot, get the init-script, and configure it::

	sudo wget http://dev.licorn.org/files/init.d-script \
		-O /etc/init.d/licornd
	sudo update-rc.d licornd defaults 98

#. *before anything* : remount your `/home` partition with `acl` and `user_xattr` options. Insert these options in your `/etc/fstab` for permanent use::

	sudo mount -o remount,acl,user_xattr /home

#. Define the bare minimum directives in your main configuration file (IRL they are positionned by the packages post-installation scripts) and amend `sudoers`::

	# for licorn <= 1.2.5
	echo 'licornd.role = SERVER' >> /etc/licorn/licorn.conf

	# for licorn >= 1.3 (including DEV and WMI2 branches)
	echo 'role = SERVER' >> /etc/licorn/licorn.conf

	# common to all versions
	cat >> /etc/sudoers <<EOF
	Defaults	env_keep = "DISPLAY LTRACE LICORN_SERVER LICORN_DEBUG"
	EOF

#. Start the Licorn® daemon, let it handle automatically the last configuration bits. Then stop it when you see the message "`ready for interaction`"::

	sudo licornd -vD
	[...]
	 * [2010/08/12 18:32:28.4740] licornd/master@server(29568): all threads started, ready for interaction.

	[Control-C]

#. From here, you don't need to use `sudo` anymore. Members of group `admins` can control `licornd` and CLI tools directly.
#. if you want LDAP support, install our packages or see `the LDAP development wiki page<http://dev.licorn.org/wiki/LDAPBackend>`::

	sudo apt-get install -yq --force-yes slapd libnss-ldap libpam-ldap

	# this one is available only in our repository.
	sudo apt-get install -yq --force-yes ldap-auth-config-licorn

	# Edit /etc/ldap.conf if you don't have access to the Debian package,
	# and put this content into it:
	base dc=meta-it,dc=local
	uri ldapi:///
	ldap_version 3
	rootbinddn cn=admin,dc=meta-it,dc=local
	pam_password md5

	# Then make licornd use OpenLDAP over shadow for new accounts/groups.
	sudo mod config -b openldap

	# The file /etc/ldap.secret will be automatically filled by licornd at next launch.

#. optional: launch the daemon with `licornd -vD` (`-v`is optionnal, this is the verbose flag). Without `-D` it will fork into the background. With it, you will see what the daemon does. This step is optional because every Licorn® tool will get the daemon automatically started if they need it.
#. enjoy Licorn® on your Linux system, by continuing through the :ref:`quickstart<quickstart.en>`.
