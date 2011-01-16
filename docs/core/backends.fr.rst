.. _core.backends.fr:

========
Backends
========

Gestionnaire de backends
========================

Le gestionnaire de backends (voir :class:`~licorn.core.backends.BackendsManager`, en anglais) héberge toutes les instances des backends. Il les charge et les décharge, les active et les désactive.

Il hérite du gestionnaire de modules (voir :class:`~licorn.core.classes.ModulesManager`, en anglais), et a pas mal de choses en commun avec le gestionnaire d'extensions (voir :class:`~licorn.extensions.ExtensionsManager`, en anglais) (voyez :ref:`core.modules.fr` pour plus de détails).


Backends
========

Voici les backends en eux-mêmes. Ils héritent tous des :ref:`classes abstraites de backends <core.backends.abstract>` (en anglais).

.. toctree::
	:maxdepth: 2

	backends/shadow
	backends/openldap
	backends/dnsmasq
