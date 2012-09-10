.. _daemon.fr:

.. highlight:: bash

=================
Le daemon Licorn®
=================

:program:`licornd` est le programme qui fait le sale boulot à notre place — autant dire que je l'apprécie beaucoup. Il administre les objets système (utilisateurs, groupes, etc) de l'intérieur. Il met à jour :file:`/etc/*`, surveille les données partagées, vérifie et applique automatiquement les bonnes permissions et les :abbr:`ACL (Access Control Lists -- listes de contrôle d'accès)`\s ``POSIX.1e``, de manière à ce que vous n'ayez jamais besoin de les manipuler directement (en cas de problème constaté, :ref:`chk <chk.fr>` est votre ami).

Il lance la `WMI <wmi/index.fr>`_ et fait tourner les sauvegardes incrémentales du système en tant que processus légers (threads), offre une :ref:`interface d'informations à la top <daemon_toplike_interface.fr>`, et même un :ref:`interpréteur interactif <daemon_interactive_shell.fr>` à distance si vous avez besoin de récupérer des informations spécifiques ou si vous êtes juste curieu[x|se] à propos de son fonctionnement.

Derrière cette présentation qui semble décrire quelque chose d'énorme et pataud, vous trouverez un processus très économe en ressources système qui fera tout son possible pour assister l'administrateur système dans des tâches qui sans :program:`licornd`, seraient d'une longueur interminable et d'un ennui mortel (vous avez déjà été obligé(e) de corriger des :abbr:`ACL (Access Control Lists -- listes de contrôle d'accès)`\s sur plusieurs Gigaoctets de données ?).

État du daemon
==============

À tout moment, vous pouvez obtenir des informations sur le daemon actuellement en fonctionnement, avec une commande spécifique::

	get status

Ce qui donne par exemple sur ma machine:

.. image:: ../screenshots/fr/daemon/daemon0001.png
   :alt: Get status (ou interface top-like)


Démarrage et auto-démarrage
===========================

**Dans des conditions normales, le démarrage et l'arrêt du daemon sont complètement automatiques**: ils sont gérés par les scripts de votre distribution GNU/Linux. Par exemple sur Debian et Ubuntu, :program:`licornd` est lancé au démarrage de la machine et stoppé à l'arrêt. Vous pouvez le contrôler ensuite à l'aide de la commande :program:`service` de votre distribution (référez-vous à la documentation spécifique à votre distribution pour plus de détails).

Malgré celà, vous pourriez avoir envie ou besoin de gérer tout ça vous même. Vous pouvez de toute manière interférer avec les services système sans problème (:program:`licornd` est assez souple de ce côté là).

Considérant le fait que vous êtes administrateur Licorn® (c'est à dire membre du groupe ``admins`` sur la machine locale ou dans l'annuaire LDAP, si LDAP il y a), **toute tentative d'utiliser un outil CLI lancera automatiquement le daemon**, s'il ne tourne pas déjà. Il lui faudra un certain temps pour être opérationnel et réactif à la commande que vous avez initialement tapée, suivant votre système.

Si vous devez le lancer à la main pour n'importe quelle raison, la méthode est simple ::

	licornd

Si vous voulez qu'il reste accroché à votre terminal et affiche de fabuleux messages d'information ::

	licornd -vD

	# version longue:
	licornd --verbose --no-daemon

Si un daemon tourne déjà, et que vous voulez *récupérer la main* sur le nouveau daemon que vous lancez depuis votre terminal ::

	licornd --replace

	# la commande que j'utilise systématiquement pour reprendre
	# le contrôle sur un daemon déjà lancé, depuis mon terminal :
	licornd -rvD

.. note:: l'argument :option:`--replace` n'a aucune conséquence si aucun daemon n'est préalablement lancé.


Fichiers et configuration
=========================

    * le journal: :file:`/var/log/licornd.log`
    * le fichier de `configuration <configuration.fr>`_: :file:`/etc/licorn/main.conf`, dans lequel toutes les directives commençant par ``licornd.`` concernent le daemon.


Sessions intéractives
=====================

Si vous souhaitez intéragir avec le daemon (Quelque fois c'est simplement rigolo, d'autres fois c'est nécessaire), démarrez-le avec l'option :option:`-D` (version longue :option:`--no-daemon`) ::

	licornd -D

	# ou:
	licornd -vD

	# et de même avec -vvD et -vvvD pour afficher de plus en plus de messages

Le daemon restera alors attaché à votre terminal. Vous avez alors accès à l' **interface top-like**.


.. _daemon_toplike_interface.fr:

Interface Top-like
------------------

.. image:: ../screenshots/fr/daemon/daemon0001.png
   :alt: Interface top-like (ou sortie de ``get status``)

Les raccourcis claviers suivants sont disponibles:

.. glossary::

	:kbd:`Space`
		Will display the current status of the daemon, its threads and controller instances. The status can be very verbose or not, depending on the full status flag (see below). Typing repeatedly on kbd:`Space` will emulate a top-like behaviour, allowing to monitor the daemon status in real-time, even if it is very busy.

	:kbd:`Control-t`
		Will do exactly the same as :kbd:`Space`. It's a standard behaviour in shells of BSD systems, and I missed it a lot under `GNU/Linux`.

	:kbd:`Control-y`
		Will do exactly the same as :kbd:`Space`, but will clear the screen first.

	:kbd:`f` or :kbd:`l`
		Will toggle between normal and full status. The status flag is remembered until the daemon terminates or restarts.

	:kbd:`Control-r`
		Will restart the daemon (by sending it an ``USR1`` signal). Very useful when you modified any configuration directive or source code.

	:kbd:`Control-c`
		Will break and terminate, as expected.

	:kbd:`Control-u`
		Will terminate the daemon with a traditionnal ``TERM`` signal (15), simulating a normal :command:`kill` or :command:`killall`.

	:kbd:`Control-k`
		**Extreme caution**: will send a real ``KILL`` signal (9). Use this when you think the daemon is stuck and doesn't respond anymore (this can happen when it blocks on DNS timeout, it seems totally unresponsive, but is not).

	:kbd:`Enter`
		Will just display a newline (usefull for manually marking spaces between different operations).

	:kbd:`Control-L`
		Will clear the screen, like in a normal terminal.

	:kbd:`i`
		Will enter the interactive shell (see below). Press :kbd:`Control-d` or type `exit` to leave the shell.

.. _daemon_interactive_shell.fr:

Interactive shell
-----------------

.. warning:: Using this feature can be dangerous in some conditions. Remember that your daemon runs as ``root`` on your system. Don't try anything fancy here!

The daemon's interactive shell is an enhanced python shell. Its major features are:

* a powerfull completion system (with the traditionnal :kbd:`Tab` key)
* an full command history, remembered across interactive sessions (even if the daemon stops or restarts); history file is located at :file:`~/.licorn/licornd_history`.
* the Licorn runtime environment: you are **inside** the daemon, which keeps running while you type. You can act on threads, send messages, fill `queues` with manually-crafted data to see how the system reacts, import modules to test them, and more.
* 2 helper functions: :func:`~foundations.ltrace.dump` and :func:`~foundations.ltrace.fulldump`, to introspect nearly any Licorn® object.

Other daemon's arguments
========================

Please refer to integrated help for an exhaustive listing of the daemon's CLI arguments, they are documented online::

	licornd --help

.. seealso::
	En anglais pour l'instant, en attendant la traduction:

	* :ref:`La documentation développeur du daemon <daemon.dev.fr>`.
	* :ref:`L'infrastructure de services <daemon.services.en>`.
