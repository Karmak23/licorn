
.. _quickstart.fr:

.. highlight:: bash

====================================
Prise en main : Licorn® en 3 minutes
====================================

Licorn® est très facile à utiliser, la plupart du temps on ne passe pas beaucoup de temps dessus. C'est la rançon d'un logiciel efficace, pas vrai ? On ne perd du temps qu'avec les logiciels mals conçus ou lorsqu'on les utilise en dehors de leur champ d'application.

Vous pouvez démarrer avec la prise en main des outils :abbr:`CLI (Command Line Interface)` (Interface en ligne de commande), qui sont mes outils préférés car ils sont très conçis et essaient de deviner un maximum ce que vous voulez leur dire.

La :abbr:`WMI (Web Management Interface)` (Interface de Gestion par le Web) est parfaite pour les gens normaux: elle offre moins de fonctionnalité mais elle est totalement blindée (aucun accès root ou équivalent, impossible de casser le système avec). C'est une webapp moderne dont le contenu change en réponse immédiate aux modifications du système : il est inutile de « recharger la page » !

.. _quickstart.cli.fr:

Prise en main de la CLI
=======================

Pour pouvoir utiliser les outils en ligne de commande Licorn®, vous devez être membre du groupe ``admins``. Alors si ce n'est pas déja fait ::

	sudo add user `whoami` admins

Création de 3 utilisateurs et création d'un groupe de travail dont on les rend membres::

	add user jean --gecos "Jean Dupont"
	add user beatrice --gecos "Béatrice Durand"
	add user patrick --gecos "Patrick Dupond"
	add group Partage --members jean,beatrice,patrick

Après ça, ajout de l'utilisateur ``Benjamin Gates`` (qui existait déjà) dans le même groupe::

	# la version courte
	add user ben Partage
	# la version longue
	mod user ben --add-to-group Partage

Chacun des quatre utilisateurs a maintenant accès au répertoire ``Partage`` (directement depuis son répertoire personnel ou dans :file:`/home/groups/Partage`) dont le contenu leur est réservé.

Béatrice a perdu son mot de passe::

	# On lui en crée un nouveau aléatoire (qui sera affiché à l'écran)
	mod user beatrice -P

	# on lui change interactivement (root n'a pas besoin de connaître l'ancien):
	sudo mod user beatrice -C
	# la même en version lisible par un humain:
	sudo mod user beatrice --change-password

Le groupe ``Partage`` n'est pas :ref:`permissif <groups/permissions.fr>` à sa création, ce qui signifie que ses membres ne peuvent pas modifier les documents des autres, mais seulement les lire (:ref:`plus de détails sur les permissions <groups.permissions.fr>` ?). Pour que tous les membres puissent modifier tous les fichiers contenus dans le répertoire sans distinction, rendons le groupe permissif::

	mod group Partage -p
	# version humainement lisible:
	mod group Partage --set-permissive

Créons un nouveau partage permissif, dédié à tous les utilisateurs du réseau. Ceux qui existent préalablement y auront accès aussi, rétro-activement ::

	add group Commun -p --descr 'fichiers partagés pour tout le monde'

	# l'application est immédiate pour les utilisateurs existants :
	mod profile users --add-groups Commun

En fait nous venons de modifier le :ref:`profil <profiles.fr>` ``Users``, qui est un composant « d'usine », livré avec Licorn® ::

	# lister les profils utilisateurs
	get profiles
		...
	# -l signifie "--long", pour obtenir plus d'informations
	get groups -l
		...
	get users
		...
	get users -l

Nettoyons maintenant tous les exemples utilisés dans cette prise en main::

	# si vous ne spécifiez pas --no-archive,
	# toutes les données sont déplacées dans /home/archives

	# on détruit tous les comptes sauf ben (qui existait avant)
	del users --not-system -X ben

	# on détruit tous les groupes non systèmes
	# (j'espère que vous n'en aviez pas créé avant la prise en main…)
	del group --not-system

Maintenant, vous pouvez passer à :ref:`la documentation complète de la CLI <cli/index.fr>` pour en découvrir toutes les fonctionnalités.

.. _quickstart.wmi.fr:

Prise en main rapide de la WMI
==============================

La WMI offre des fonctionnalités de haut-niveau, mais  globalement moins que la CLI. Elle vise les utilisateurs non-professionnels (non-IT) et les administrateurs systèmes occasionnels. Mais rassurez tout le monde : ses fonctionnalités sont tellement utiles que même les administrateurs chevronnés s'en servent.

La WMI est complètement traduite en français et en anglais, contraitement à la CLI qui reste en anglais pour l'instant. Réaliser une traduction est assez simple, contactez-nous si vous avez besoin d'une traduction particulière.

Autoriser les connexions à la WMI
---------------------------------

Pour vous connecter à la WMI, vous aurez besoin de faire partie d'un groupe spécial nommé ``licorn-wmi``, si vous n'êtes pas déjà membre d'``admins`` (les ``admins`` sont l'équivalent de ``root`` pour Licorn®). Pour vous rendre membre de ce groupe (j'espère que vous êtes déjà administrateur de la machine, sinon ça ne marchera pas), tapez ::

	# Cette étape est déjà effectuée dans l'installation développeur
	add user `whoami` licorn-wmi

Après ça, utiliser la WMI est assez simple: `dirigez votre navigateur internet vers la WMI <https://localhost:3356/>`_ et utilisez votre identifiant et votre mot de passe pour y entrer. La WMI est accessible en HTTPS seulement, avec un certificat auto-signé depuis la version 1.3.2. Il vous faudra l'accepter avant de continuer.
