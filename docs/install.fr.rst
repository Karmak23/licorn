.. _install.fr:

=======================
Installation de la bête
=======================

.. highlight:: bash


Avec des paquetages
===================

La version stable de Licorn® est empaquetée pour `Ubuntu Lucid 10.04 LTS` et supérieur. Téléchargez les paquetages depuis l'archive suivante::

	deb http://packages.licorn.org/ubuntu/ <codename> main restricted

Où `<codename>` devrait être "maverick" ou "lucid", etc.

Quelques noms de paquetages:

.. glossary::

.. _licorn-ldap-server.fr:

	licorn-ldap-server
		L'installation la plus commune de nos jours : ce paquet installe tous les composants «serveur» de Licorn® et le :ref:`backend LDAP <core.backends.ldap.fr>` (et sa configuration d'usine). Après avoir installé ce paquetage, Licorn® est **prêt à être utilisé**.

.. _licorn-server.fr:

	licorn-server
		Une option moins intrusive : ce paquet installera toute la partie serveur de Licorn®, mais avec seulement le :ref:` backend shadow <core.backends.shadow.fr>` activé. Vous pouvez installer le paquet précédent par la suite si vous changez d'idée.

.. _licorn-client.fr:

	licorn-client
		Installez ce paquetage sur les postes clients Ubuntu Lucid LTS ; celà les rendra pilotables à distance depuis votre serveur pour les tâches d'administration système. Techniquement, ça installe exactement le même code que sur le serveur, mais la configuration est différente.

Tous ces paquetages installeront des dépendances externes (comme `python-licorn`, `licorn-bin` et quelques autres paquetages `python-*`). Pour plus de détails, lisez `la documentation des paquets Debian <http://dev.licorn.org/wiki/UserDoc/DebianPackagesDependancies>`_ (en anglais) sur le site de développement.


Depuis les sources
==================

.. warning:: Cette installation depuis les sources s'adresse **à des développeurs** seulement. Ça peut endommager votre système au pire, ou ne pas marcher du tout au mieux, si vous manquez un truc de cette procédure.

#. Install darcs and required python-packages::

	sudo apt-get -qy --force-yes install nullmailer darcs \
			pyro python-gamin python-pylibacl python-ldap \
			python-xattr python-netifaces python-dumbnet \
			python-pyip python-ipcalc

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

	sudo rm -f /usr/sbin/licornd
	sudo ln -sf "${LCN_DEV_DIR}/daemon/main.py" /usr/sbin/licornd
	sudo chmod a+x /usr/sbin/licornd

	sudo mkdir /etc/licorn
	sudo ln -sf "${LCN_DEV_DIR}/config/check.d" /etc/licorn

	sudo mkdir -p /usr/share/licorn
	sudo ln -sf "${LCN_DEV_DIR}/interfaces/wmi" /usr/share/licorn/wmi
	sudo ln -sf "${LCN_DEV_DIR}/core/backends/schemas" \
		/usr/share/licorn/schemas
	sudo ln -sf "${LCN_DEV_DIR}/locale/fr.mo" \
		/usr/share/locale/fr/LC_MESSAGES/licorn.mo

#. Some version dependant links:

  * Under debian / Ubuntu <= Karmic (Python 2.5)::

	sudo ln -sf "${LCN_DEV_DIR}" /usr/lib/python2.5/site-packages/licorn

  * Under debian / Ubuntu *>= Lucid* (Python 2.6)::

	sudo ln -sf "${LCN_DEV_DIR}" /usr/lib/python2.6/dist-packages/licorn

#. optional : to get `licornd` started at boot, get the init-script, and configure it::

	sudo wget http://dev.licorn.org/files/init.d-script \
		-O /etc/init.d/licornd
	sudo update-rc.d licornd defaults 98

#. *before anything* : remount your `/home` partition with `acl` and `user_xattr` options. Insert these options in your `/etc/fstab` for permanent use::

	sudo mount -o remount,acl,user_xattr /home

#. Define the bare minimum directives in your main configuration file (IRL they are positionned by the packages post-installation scripts) and amend `sudoers`::

	echo 'licornd.role = SERVER' >> /etc/licorn/licorn.conf
	cat >> /etc/sudoers <<EOF
	Defaults	env_keep = "DISPLAY LICORN_TRACE LICORN_SERVER"
	EOF

#. Start the Licorn® daemon, let it handle the last configuration bits, then stop it when you see the message "`ready for interaction`"::

	sudo licornd -vD
	[...]
	 * [2010/08/12 18:32:28.4740] licornd/master@server(29568): all threads started, ready for interaction.

	[Control-C]

#. From here, you don't need to use `sudo` anymore. Members of group `admins` can control `licornd`
#. if you want LDAP support:  (see wiki/LDAPBackend] for configuration defaults, which Licorn® expects)::

	sudo apt-get install -yq --force-yes slapd libnss-ldap libpam-ldap
	sudo mod config -b openldap

#. optional: launch the daemon with `licornd -vD` (`-v`is optionnal, this is the verbose flag). Without `-D` it will fork into the background. With it, you will see what the daemon does. This step is optional because every Licorn® tool will get the daemon automatically started if they need it.
#. enjoy Licorn® on your Linux system.
