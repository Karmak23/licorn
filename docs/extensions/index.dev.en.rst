
.. _extensions.dev:

===================================
Extensions Developper documentation
===================================

The first thing to read is :ref:`core module documentation <core.modules.en>`, because extensions inherit from the :class:`~licorn.core.classes.CoreModule` class (they share a lot with :ref:`backends <core.backends.en>` in this regard). The :class:`~licorn.extensions.ExtensionsManager` inherits from the :class:`~licorn.core.classes.ModulesManager`, too.

To know more about a specific extension, follow the user-documentation links above, the classes are there.

Extensions core classes
=======================

The Extensions manager
----------------------

.. autoclass:: licorn.extensions.ExtensionsManager
	:members:
	:undoc-members:

Extensions abstract classes
---------------------------

.. autoclass:: licorn.extensions.LicornExtension
	:members:
	:undoc-members:

.. autoclass:: licorn.extensions.ServiceExtension
	:members:
	:undoc-members:

Extensions specific classes
===========================

.. toctree::
	:maxdepth: 2

	mylicorn.dev.en
	openssh.dev.en
	volumes.dev.en
	rdiffbackup.dev.en
	squid.dev.en
