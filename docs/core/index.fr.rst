.. _core.fr:

==================
Le Cœur de Licorn®
==================

Le «cœur» (**core** en anglais) gère tous les objets les plus importants de Licorn® (utilisateurs, groupes, machines, etc) via l'utilisation de  :ref:`contrôleurs <core.abstract.controller>`, qui contiennent et opèrent sur les :ref:`objets unitaires <core.abstract.unitobject>`. Le nombre de contrôleurs peut varier d'un système à l'autre, celà dépend des services installés localement (qui influent sur les backends, qui influent sur les types d'objets unitaires disponibles).

Tous les contrôleurs sont hébergés dans le :class:`~licorn.core.LicornMasterController`, abbrégé en **LMC**. Dans le :ref:`daemon`, le ``LMC`` est une instance globale.

Le contrôleur maître de Licorn® (Licorn® master controller)
===========================================================

Le ``LMC`` est une des parties les plus importantes et centrales du cœur (``core``) de Licorn®. Il a :ref:`sa page dédiée <core.lmc>`.

Contrôleurs et objets du cœur
=============================

.. toctree::
	:maxdepth: 2

	lmc.fr
	users.fr
	groups.fr
	profiles.fr
	privileges.fr
	machines.fr
	system.fr

Les Modules: backends et extensions
===================================

.. toctree::
	:maxdepth: 2

	backends/index.fr
	../extensions/index.fr


Classes abstraites et concepts
==============================

.. toctree::

	abstract.fr

En attendant la traduction française de la documentation, :ref:`celle en anglais est disponible<core.abstract.en>`.
