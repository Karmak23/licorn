.. _core.fr:

==================
Le Cœur de Licorn®
==================

Le «cœur» (**core** en anglais) gère tous les objets les plus importants de Licorn® (utilisateurs, groupes, machines, etc) via l'utilisation de  :ref:`contrôleurs <core.abstract.controller>`, qui contiennent et opèrent sur les :ref:`objets unitaires <core.abstract.unitobject>`. Le nombre de contrôleurs peut varier d'un système à l'autre, celà dépend des services installés localement (qui influent sur les backends, qui influent sur les types d'objets unitaires disponibles).

Tous les contrôleurs sont hébergés dans le :class:`~licorn.core.LicornMasterController`, abbrégé en **LMC**. Dans le :ref:`daemon <daemon.fr>`, le ``LMC`` est une instance globale.

Le contrôleur maître de Licorn® (Licorn® master controller)
===========================================================

Le ``LMC`` est une des parties les plus importantes et centrales du cœur (``core``) de Licorn®. Il a :ref:`sa page dédiée <core.lmc.fr>`.

Contrôleurs et objets du cœur
=============================

Cette section n'est pas traduite et fait référence à la documentation en anglais.

.. toctree::
	:maxdepth: 2

	lmc.fr
	users.en
	groups.en
	profiles.fr
	privileges.en
	machines.en
	system.en

Les Modules: backends et extensions
===================================

.. toctree::
	:maxdepth: 2

	backends/index.fr
	../extensions/index.fr


Classes abstraites et concepts
==============================

En attendant la traduction française de la documentation, :ref:`celle en anglais est disponible<core.abstract.en>`.
