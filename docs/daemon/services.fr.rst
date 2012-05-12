
.. _daemon.services.fr:

=======================
Le mécanisme de Service
=======================

Ce mécanisme interne au daemon permet un grand niveau de parallelisme et une activité complètement asynchrone pour chaque partie de Licorn®. Il est basé sur la soumission de travaux priorisés, depuis n'importe quel endroit du code (il n'y a aucune limitation actuellement).

C'est très utile pour tous les travaux en arrière plan et les tâches planifiées ou déclenchées sur évènements, dont Licorn® est truffée.

**Ce mécanisme n'est actuellement pas temps réel**: une tâche de haute priorité sera forcément la prochaine à être éxécutée, mais rien ne garantit qu'elle sera exécutée **immédiatement** si tous les threads de services présents sont occupés sur des tâches longues.

.. note:: il n'y a pas de mécanisme de `callbacks` dans la forme actuelle du ``service``, car il serait inutile par design: il résumerait la situation à un appel synchrone (on attend le retour de la callback pour rendre la main). Dans ce cas là, appelez simplement la fonction dont vous avez besoin, et vous aurez les éventuels retours et messages au fûr et à mesure qu'ils apparaissent.

.. versionadded:: 1.2.5

.. warning:: ce mécanisme est récent, il est probable qu'il soit sujet à changement prochainement, comme pour ajouter des niveaux de priorité, ajouter une possibilité de retour (callbacks) ou changer l'algorithme de tenue en charge. Restez connecté(e).

Utilisation
===========

Lorsque vous avez besoin d'un appel synchrone dans Licorn®, appelez juste la méthode et attendez le résultat. Cette methode sera exécutée dans the thread Pyro courant. Exemple::

	LMC.users.AddUser(uid=..., login=..., ...)

Lorsque vous avez besoin de simplement lancer un traitement dont vous n'attendez aucunre réponse ou retour, ou pour paralléliser des tâches, déposez votre méthode dans la file d'attente des services avec une priorité d'exécution, et la tâche sera exécutée par le premier thread disponible. Exemple::

	...
	from licorn.daemon import priorities, service
	...

	service(priorities.LOW, lambda: LMC.groups.CheckGroups(['10000']))

La vérification des données partagées du groupe sera opérée en arrière plan et vous récupérez la main immédiatement.

Priorités
=========

Actuellement, trois:

	``priorities.LOW``
		toute tâche dont l'exécution n'est pas importante. Les tâches dans cette priorité **seront réalisées**, mais vous n'aurez aucune indication sur quand (toute tâche de priorité supérieure passant avant). Par exemple la plupart des tâches de la découverte active du réseau sont réalisée à cette priorité car elle passent après toutes les autres opérations.

	``priorities.NORMAL``
		la priorité normale. C'est un peu mieux que ``LOW``, mais moins bien que ``HIGH``. À utiliser pour les tâches courantes de Licorn (checks et fast_checks notamment). Dans les mécanismes de découverte du réseau, une seule tâche est en priorité normale: la recherche de Pyro distants (elle intervient sur des machines dont on connait déjà l'état de marche).

	``priorities.HIGH``
		la priorité haute, pour les tâches nécessitant une réactivité maximale, par exemple la modification des objets systèmes (add/mod/del) et la scrutation des fichiers de configuration (mécanisme ``inotify``).

Fonctionnement en charge
========================

Le nombre de threads de service varie automatiquement en fonction de la charge de services en attente. L'algorithme de décision est basique mais sera amélioré en fonction des besoins.
