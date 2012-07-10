.. _install.fr:

=========================
Procédures d'installation
=========================

.. highlight:: bash


Via des paquetages
==================

Installation typique
--------------------

La procédure d'installation est assez rapide :

* ajoutez une source d'installation pour Licorn® dans le fichier  :file:`/etc/apt/sources.list.d/licorn.list` (cf. :ref:`sources d'installation <install.sources_list.fr>`).
* installez un des meta-paquetages Licorn® (cf. :ref:`noms des paquetages <install.packages_names.fr>`) ::

	sudo apt-get update

	# par exemple :
	sudo apt-get install licorn-server

	# au besoin, si l'installation est une mise à jour importante
	# et que ça plante pendant le processus :

	sudo apt-get -f install

* **fermez votre session et ré-ouvrez-la** pour bénéficier des nouveaux droits sur les programmes Licorn® (cf. note ci-après).
* C'est fini ! Enchainez-donc sur le :ref:`Quickstarter <quickstart.fr>`.

.. note:: Si vous faisiez préalablement partie du groupe ``sudo`` (sur `Debian` et `Ubuntu 12.04` et supérieures) ou ``admin`` (sur `Ubuntu 11.10` et inférieures), **vous faites maintenant partie du groupe** ``admins``, le groupe des adminstrateurs Licorn®.

	Si vous n'étiez ni ``sudo`` ni ``admin`` avant l'installation, il est fortement recommandé d'ajouter votre compte utilisateur ou un autre dans le groupe ``admins`` (via la commande ``adduser `whoami` admins``) sinon personne ne pourra utiliser les outils Licorn® !

.. _install.sources_list.fr:

Sources d'installation pour `Debian` et `Ubuntu`
------------------------------------------------

La version stable de Licorn® est empaquetée pour les distributions Ubuntu et Debian actuellement supportées par leurs communautés respectives. La distribution préférée pour installer Licorn® est actuellement `Ubuntu 12.04 LTS (Precise)`. Téléchargez les paquetages depuis le dépôt suivant::

	deb http://archive.licorn.org/ubuntu <codename> main restricted

Où `<codename>` devrait être `precise` (12.04 LTS) ou `lucid` (10.04 LTS).

Pour Debian, l'adresse est différente::

	deb http://archive.licorn.org/debian <codename> main

Où ``<codename>`` est `squeeze`, `wheezy` ou `sid`.

.. note:: Les paquetages Licorn® peuvent être en retard sur `Debian` (par rapport à `Ubuntu`), ou certaines versions peuvent ne pas être disponibles sur les distributions `testing` et `sid`. `Suivez les nouvelles <http://dev.licorn.org/blog>`_ pour avoir les informations les plus à jour sur le sujet.

.. seealso:: Pour tester les derniers paquets des dernières versions de Licorn®, participer à l'amélioration du logiciel ou bénéficier des dernières fonctionnalités plus rapidement, il existe un canal de paquets quotidiens ::

		deb http://daily.licorn.org/{ubuntu/debian} <codename> main

	Contactez-nous si vous voulez participer aux programme de test, il y a des choses à gagner ;-)

.. _install.packages_names.fr:

Noms de paquetages
------------------

.. _licorn-ldap-server.fr:

	licorn-ldap-server
		L'installation la plus commune de nos jours : ce paquet installe tous les composants « serveur » de Licorn® et le :ref:`backend LDAP <core.backends.ldap.fr>`. La configuration LDAP est celle d' `Ubuntu`/`Debian` (via :program:`debconf`), comme sur n'importe quelle installation sans Licorn®. Après avoir installé ce paquetage, Licorn® est **prêt à être utilisé**.

.. _licorn-server.fr:

	licorn-server
		Une option moins intrusive : ce paquet installera toute la partie serveur de Licorn®, mais avec seulement le :ref:` backend shadow <core.backends.shadow.fr>` activé. Pas de LDAP, donc, mais un Licorn® totalement fonctionnel en mode « autonome ».

.. _licorn-client.fr:

	licorn-client
		Installez ce paquetage sur les postes clients ; celà les rendra pilotables à distance depuis votre serveur Licorn® pour les tâches d'administration système (proxy, mise à jour de sécurité automatiques, extinction et redémarrage à distance). Techniquement, ça installe exactement le même code que sur le serveur, mais la configuration est différente et les services chargés sont limités.

Tous ces paquetages installeront des dépendances externes (comme `python-licorn`, `licorn-bin` et d'autres paquetages `python-*`). Pour plus de détails, lisez `la documentation des paquets Debian <http://dev.licorn.org/wiki/UserDoc/DebianPackagesDependancies>`_ (en anglais) sur le site de développement.

.. note:: Licorn® étant un logiciel de gestion de serveur, les paquetages sont truffés de recommandations (``Recommends`` en anglais dans le texte) que Licorn® peut gérer mais dont vous n'avez pas forcément besoin. À vous de voir si vous installez les ``Recommends`` ou pas.

.. seealso:: Il y a d'autres meta-paquets Licorn® qui vous interesseront ou pas. Utilisez les outils `Debian` ou `Ubuntu` pour rechercher « ``licorn`` » et obtenir une liste complète.

.. _install.from_sources.fr:

Depuis les sources
==================

.. warning:: Cette installation depuis les sources s'adresse **à des développeurs** ou des administrateurs testeurs ou soucieux de suivre les versions plus rapidement que la sortie des paquetages. Ça peut endommager votre système au pire, ou ne pas marcher du tout au mieux, si vous manquez un truc de cette procédure.

Première installation
---------------------

Ceci installera Licorn® en mode serveur sur votre machine locale, de manière à ce que le développement soit très simplement testable : il suffit de taper `[Control-R]` sur le terminal du daemon après tout changement de code. Une fois l'installation terminée, vous pourrez :ref:`modifier la configuration <configuration.fr>` librement.

.. note:: vous devez être un utilisateur de `sudo` confirmé avant de commencer cette installation. Sur Ubuntu, ça devrait être déjà le cas. Sur Debian vous devrez vous rendre membre du groupe ``sudo``.

#. Installez :program:`git`, `git-flow` et le minimum vital::

	sudo apt-get install git-core git-flow make gettext

#. Récupérez les sources de Licorn® avec :program:`git`::

	mkdir sources && cd sources
	[ -d licorn ] && ( cd licorn; git pull )
	[ -d licorn ] || git clone git://dev.licorn.org/home/groups/licorn.git licorn

#. Installez Licorn® en mode développeur::

	cd licorn && make devinstall
	# à partir de là, vous n'avez plus besoin de `sudo` pour utiliser Licorn®.

	# à n'importe quel moment, vous pouvez tout désinstaller via :
	#make uninstall

#. *Optionnel* : pour que le :ref:`démon <daemon.fr>` `licornd` démarre avec la machine, copiez l'`init-script` et configurez le service::

	sudo cp contrib/init-script /etc/init.d/licornd
	sudo update-rc.d licornd defaults 98

	# Alternativement, vous pouvez insérer dans /etc/rc.local:
	licornd -r

.. note:: pour `Debian` / `Ubuntu` équipé d':program:`upstart`: le script n'est pas encore écrit, le fonctionnement avec :program:`upstart` n'est pas encore clairifié.

#. fermez votre session et ré-ouvrez-la pour faire partie du nouveau groupe ``admins``.

#. Goûtez aux joies de Licorn® sur votre système : vous pouvez utiliser les :ref:`outils CLI <quickstart.cli.fr>` ou la :ref:`WMI <quickstart.wmi.fr>`. Dans tous les cas, le :ref:`guide de démarrage rapide <quickstart.fr>` est un bon point de départ.

.. _install.ldap_support.fr:

Support LDAP
------------


#. Preparez votre système pour l'installation de :program:`slapd` :

	- Vérfiez que votre machine a bien un FQDN dans :file:`/etc/hostname` : « ``Machine.licorn.local`` » est bon, « ``Machine`` » ne l'est pas ;
	- Vérifiez que :program:`hostname` renvoie bien ce nom complet ; sinon lancez ``sudo hostname -F cat /etc/hostname`` ;
	- Vérifiez que :program:`dnsdomainname` renvoie juste la partie domaine du FQDN. Sinon éditez :file:`/etc/hosts` (ou configurez votre DNS si vous en avez un ; cette documentation n'a pas la vocation d'un cours de configuration réseau…) pour qu'il ressemble à ça ::

		127.0.1.1	nom-machine.mon.fqdn.complet nom-machine

#. Installez le support LDAP (client/serveur) ::

	sudo apt-get install --yes --force-yes slapd libnss-ldap libpam-ldap

#. Configurez les paquets debian avec « ``dc=mon,dc=domaine,dc=complet`` » ;

#. Relancez `licornd` pour qu'il détecte la nouvelle installation::

	licornd -r

#. Activez l'extension LDAP dans :program:`licornd` ce qui l'activera au niveau système via ``NSS`` ::

	mod config -b ldap

	# ou la version longue :
	# mod configuration --enable-backend openldap

À partir de maintenant les nouveaux comptes utilisateurs et groupes seront créés dans ``LDAP``. Vous pouvez cependant continuer à les créer dans le backend ``shadow`` avec l'argument CLI ``--backend shadow``.

On continue sur le :ref:`Quickstarter <quickstart.fr>` ? Ou encore directement sur le :ref:`daemon Licorn® <daemon.fr>` ? À vous de voir ; tous les chemins mènent à Rome…
