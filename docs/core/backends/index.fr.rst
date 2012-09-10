.. _core.backends.fr:

========
Backends
========

Gestionnaire de backends
========================

Le gestionnaire de backends (voir :class:`~licorn.core.backends.BackendsManager`, en anglais) héberge toutes les instances des backends. Il les charge et les décharge, les active et les désactive.

Il hérite du gestionnaire de modules (voir :class:`~licorn.core.classes.ModulesManager`, en anglais), et a pas mal de choses en commun avec le gestionnaire d'extensions (voir :class:`~licorn.extensions.ExtensionsManager`, en anglais).

.. seealso:: La documentation des :ref:`modules abstraits <core.modules.en>` (en anglais) pour plus de détails.


Backends
========

Voici les backends en eux-mêmes. Ils héritent tous des :ref:`classes abstraites de backends <core.backends.abstract.fr>`.

.. toctree::
	:maxdepth: 2

	shadow.fr
	openldap.fr
	dnsmasq.fr

.. _core.backends.abstract.fr:

Classes abstraites des backends
===============================

La :ref:`documentation sur les classes abstraites des backends <core.backends.abstract.en>` n'est disponible qu'en anglais pour l'instant. N'oubliez pas le :ref:`Gestionnaire de backends <core.backends.manager.class.en>`, qui fait partie des classes abstraites mais dont la documentation anglaise est située juste au dessus.
