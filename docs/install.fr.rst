
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

#. Installez :program:`darcs` and les paquetages Python requis::

	sudo apt-get -qy --force-yes install nullmailer darcs \
			pyro python-gamin python-pylibacl python-ldap \
			python-xattr python-netifaces python-dumbnet \
			python-pyip python-ipcalc python-dbus python-udev

#. à propos de ``python-pylibacl`` : vérifiez que c'est au moins la version *0.3* (à partir de ``Hardy`` c'est bon).
#. Récupérez les sources avec :program:`darcs`::

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

#. Créez tous les liens nécessaires sur votre système (les chemins sont spécifiques à Debian/Ubuntu)::

	# initialisez cette variable avec le répertoire
	# qui contient vos sources Licorn®.
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

#. Quelques liens qui dépendent de la version de votre système:

  * Pour Debian / Ubuntu *>= Lucid* (Python 2.6)::

	sudo ln -sf "${LCN_DEV_DIR}" /usr/lib/python2.6/dist-packages/licorn

  * Pour Debian / Ubuntu <= Karmic (Python 2.5)::

	sudo ln -sf "${LCN_DEV_DIR}" /usr/lib/python2.5/site-packages/licorn

#. *Optionnel* : pour que le :ref:`démon <daemon.fr>` `licornd` démarre avec la machine, téléchargez l'init-script, et configurez le service:

	* pour Debian / Ubuntu équipé d':program:`upstart`:: le script n'est pas encore écrit, le fonctionnement avec upstart n'est pas encore clairifié. Pour l'instant prennez le script suivant.
	* pour Debian / Ubuntu équipé de SYSV::

	sudo wget http://dev.licorn.org/files/init.d-script \
		-O /etc/init.d/licornd
	sudo update-rc.d licornd defaults 98

#. **Avant toute autre chose** : remontez votre partition :file:`/home` avec les options ``acl`` et ``user_xattr``, et modifiez votre fichier :file:`/etc/fstab` pour que le changement soit permanent::

	sudo mount -o remount,acl,user_xattr /home

	# si /home n'est pas une partition séparée chez vous,
	# remontez / avec les mêmes options et modifiez la fstab en conséquence.
	sudo mount -o remount,acl,user_xattr /

#. Définissez les directives minimum dans votre :ref:`fichier de configuration principal <configuration.fr>` et amendez :file:`/etc/sudoers`  (IRL les fichiers sont pré-configurés par les scripts de post-installation des paquetages Licorn®)::

	sudo -s
	echo 'licornd.role = SERVER' >> /etc/licorn/licorn.conf
	cat >> /etc/sudoers <<EOF
	Defaults	env_keep = "DISPLAY LTRACE LICORN_SERVER"
	EOF
	exit

#. Démarrez le démon Licorn®, laissez-lui modifier votre configuration système pour rendre le tout homogène, et attendez le message "ready for TTY interaction". Lorsque vous le voyez, tout est prêt à être utilisé (vous pouvez le stopper si vous voulez, ou le laisser tourner pour voir l'évolution du système)::

	sudo licornd -rvD
	[...]
	 * [2010/08/12 18:32:28.4740] licornd/master@server(29568): all threads started, ready for TTY interaction.

	[Control-C]

#. À partir de maintenant, `sudo` n'est plus nécessaire. Les membres du groupe ``admins`` peuvent controller :program:`licornd` directement (ce groupe a été créé par le démon à son premier lancement).
#. Si vous désirez activer le support LDAP::

	sudo apt-get install -yq --force-yes slapd libnss-ldap libpam-ldap
	sudo mod config -b openldap

#. optional: launch the daemon with `licornd -vD` (`-v`is optionnal, this is the verbose flag). Without `-D` it will fork into the background. With it, you will see what the daemon does. This step is optional because every Licorn® tool will get the daemon automatically started if they need it.
#. enjoy Licorn® on your Linux system.
