
.. _features.fr:

===============
Fonctionnalités
===============

Essayer de résumer les fonctionnalités de Licorn® en quelques mots tient de la gageure: en quelques mots, nous l'utilisons tous les jours, ici à `META IT <http://meta-it.fr/>`_, pour administrer complètement nos serveurs GNU/Linux. Pour aller un peu plus loin, voici une liste (non exhaustive) de points importants:

.. glossary::

	Gestion des utilisateurs
		* Comptes Unix (shadow) ou LDAP
			* l'outil :term:`chk` garantit et répare les permissions et les ACLs dans le répertoire personnel
		* Attributs utilisateurs optionnels via les :ref:`extensions <extensions.fr>`
			* Calendrier individuel et délégations
			* Adresses courriel et alias
			* Dossier web personnel

	Groupes et partage de données
		* Groupes Unix ou LDAP
		* Partages pour les membres des groupes (accès simplifié via un lien dans le répertoire personnel)
			* les partages peuvent être :ref:`permissifs ou pas <permissiveness.fr>`
			* chaque groupe a des invités et des responsables, avec des :ref:`permissions spéciales <permissiveness.fr>`.
			* les partages sont surveillés par le daemon Licorn® et les permissions et ACLs sont appliqués en live
			* L'outil ref:`chk` garantit et répare les permissions sur demande, vérifie et répare les liens symboliques dans les répertoires utilisateurs, et autres joyeusetés
		* Attributs de groupes optionnels via les :ref:`extensions <extensions.fr>`
			* calendriers de groupe, accessible en lecture/écriture à tous les membres

	Profils système
		* Les profils peuvent être vus comme des squelettes de comptes utilisateurs et groups
		* Ils fixent des quotas, un répertoire personnel de base, un shell et des appartenances à des groupes
		* Ils sont modifiables et rétro-appliqués en live (les membres existants récupèrent les modifications faites, même après que leur compte a été créé), ou pas (c'est paramétrable).

	Machines
		* Les `machines` font référence à tout type de matériel réseau (ordinateurs, routeurs, imprimantes & scanners, etc)
		* Elles sont automatiquement découvertes pendant la vie du serveur, via de multiples sources
		* L'on peut les éteindre à distance si elles sont équipées de Licorn® (sous Linux uniquement, pour l'instant)
		* L'on peut aussi les mettre à jour (avec des mises à jour intéractives sur les clients GNU/Linux) (fonctionnalité en développement)
		* L'on peut leur appliquer des paramètres système génériques (par exemple le proxy), leur configuration est centralisée (en développement)

	Sauvegardes
		* Les sauvegardes sont automatiquement gérées sur :ref:`disques externes <extensions.volumes.fr>` et sont :ref:`exécutées automatiquement <extensions.rdiffbackup.fr>` à des heures / jours réguliers.

	Imprimantes
		* Support et intégration complète de CUPS (en développement)

	Système et configuration
		* Licorn® centralise et modifie les paramètres systèmes et la configuration des autres daemons (samba, calendrier, :program:`apache`, :program:`postfix`, :program:`dnsmasq`, etc)
		* les :ref:`backends <core.backends.fr>` et les :ref:`extensions <extensions.fr>` sont activables et désactivables pendant l'exécution
		* Le système peut être contrôlé et configuré à distance

Pour complémenter cette liste de fonctionnalités et obtenir de plus amples informations, vous pouvez parcourir les documentations suivantes:

.. toctree::
	:maxdepth: 1

	core/backends/index.fr
	extensions/index.fr

.. comment
 implementation.fr


Technologies
============

Ces logiciels ou services sont utilisés ou supportés dans le système de base, ou via des extensions (la liste n'est pas dans un ordre particulier):

Actuellement supportés:

- :ref:`Shadow (backend) <core.backends.shadow.fr>`
- :ref:`OpenLDAP (backend) <core.backends.openldap.fr>`
- :ref:`DNSmasq (backend) <core.backends.dnsmasq.fr>`
- SaMBa (intégration basique directement dans le code)
- :ref:`caldavd (extension) <extensions.caldavd.fr>`
- :ref:`squid (extension) <extensions.squid.fr>`
- :ref:`Gestion basique des volumes (extension) <extensions.volumes.fr>`
- :ref:`Rdiff Backup (extension) <extensions.rdiffbackup.fr>`

En développement:

- samba (en tant qu'extension)
- postfix (en tant qu'extension)
- apache2 (en tant qu'extension)
- BIND9 / DHCPd3 (en tant que backend)


Licorn® est construit sur ces technologies (listées sans ordre particulier) :

* le très apprécié langage de programmation `Python <http://python.org/>`_,
* le système de distribution d'objets à distance `Pyro <http://www.xs4all.nl/~irmen/pyro3/>`_,
* les `ACLs POSIX.1e <http://en.wikipedia.org/wiki/Access_control_list>`_,
* les `Attributs étendus utilisateurs <http://en.wikipedia.org/wiki/Extended_file_attributes>`_,
* SQLite3,
* `udev <http://fr.wikipedia.org/wiki/Udev>`_) et `udisks <http://freedesktop.org/wiki/Software/udisks>`_,
* `rdiff-backup <http://www.nongnu.org/rdiff-backup/index.html>`_
* GTK+ pour les interfaces graphiques,
* quelques modules python externes, comme `netifaces` (multiplateformes), `dumbnet` et d'autres.
