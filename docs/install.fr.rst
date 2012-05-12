.. _install.fr:

=======================
Installation de la bête
=======================

.. highlight:: bash


Avec des paquetages
===================

La version stable de Licorn® est empaquetée pour `Ubuntu Lucid 10.04 LTS` et supérieur, mais disponible uniquement pour nos clients sous contrat (vous devez avoir un identifiant/mot-de-pass). Si vous en êtes, téléchargez les paquetages depuis le dépôt suivant, sinon suivez l'`installation depuis les sources<install.from_sources.fr>`::

	deb http://identifiant:motdepasse@packages.licorn.org/ubuntu/ <codename> main restricted

Où `<codename>` devrait être `lucid`, `maverick`, etc.

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

.. _install.from_sources.fr:

Depuis les sources
==================

.. warning:: Cette installation depuis les sources s'adresse **à des développeurs** seulement. Ça peut endommager votre système au pire, ou ne pas marcher du tout au mieux, si vous manquez un truc de cette procédure.

Première installation
---------------------

Ceci installera Licorn® en mode serveur sur votre machine locale, de manière à ce que le développement soit très simplement testable : il suffit de taper `[Control-R]` sur le terminal du daemon après tout changement de code. Une fois l'installation terminée, vous pourrez :ref:`modifier la configuration <configuration.fr>` librement.

.. note:: vous devez être un utilisateur de `sudo` confirmé avant de commencer cette installation. Sur Ubuntu, ça devrait être déjà le cas. Sur Debian vous devrez vous rendre membre du groupe ``sudo``.

#. Installez :program:`darcs`::

	sudo apt-get install darcs

#. Récupérez les sources de Licorn® avec :program:`darcs`::

	mkdir sources && cd sources
	[ -d licorn ] && ( cd licorn; darcs pull -a )
	[ -d licorn ] || darcs get dev.licorn.org:/home/groups/darcs-Licorn licorn

#. Installez Licorn® en mode développeur::

	cd licorn && make devinstall
	# à partir de là, vous n'avez plus besoin de `sudo` pour Licorn®.

	# à n'importe quel moment, vous pouvez tout désinstaller :
	#make uninstall

#. *Optionnel* : pour que le :ref:`démon <daemon.fr>` `licornd` démarre avec la machine, copiez l'`init-script` et configurez le service::

	sudo cp contrib/init-script /etc/init.d/licornd
	sudo update-rc.d licornd defaults 98

.. note:: pour Debian / Ubuntu équipé d':program:`upstart`: le script n'est pas encore écrit, le fonctionnement avec :program:`upstart` n'est pas encore clairifié.

#. optionnel: lancez le daemon avec la commande `licornd -rvD`. `-v` (*verbeux*) pour un peu plus de messages, `-D` pour laisser le démon accroché à votre terminal. Cette étape est optionnelle car tous les outils CLI démarrent le démon automatiquement en cas de besoin.
#. Goûtez aux joies de Licorn® sur votre système : vous pouvez utiliser les :ref:`outils CLI <quickstart.cli.fr>` ou la :ref:`WMI <quickstart.wmi.fr>`. Dans tous les cas, le :ref:`guide de démarrage rapide <quickstart.fr>` est un bon point de départ.


Support LDAP
------------

#. Si vous désirez activer le support LDAP::

	sudo apt-get install --yes --force-yes slapd libnss-ldap libpam-ldap 

	# le paquet suivant n'est disponible que dans notre repo privé,
	# mais il ne fait rien de plus qu'auto-configurer pam-ldap.
	sudo apt-get install --yes --force-yes ldap-auth-config-licorn

	# puis éditez /etc/ldap.conf avec le contenu suivant :
	base dc=meta-it,dc=local
	uri ldapi:///
	ldap_version 3
	rootbinddn cn=admin,dc=meta-it,dc=local
	pam_password md5

	# Demandez à Licorn® d'activer LDAP au niveau système, et
	# pour les nouveaux comptes utilisateurs et groupes.
	mod config -b openldap

	# le fichier /etc/ldap.secret sera rempli automatiquement au prochain démarrage de licornd.

Pour une vue détaillée de ce que fait Licorn®, voyez `la page du wiki de développement sur LDAP <http://dev.licorn.org/wiki/LDAPBackend>`_, et le code source du :ref:`backend OpenLDAP <backends.openldap.fr>`.
