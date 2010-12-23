.. _extensions:

==========
Extensions
==========

User & Administrator documentation
==================================

Extensions share a lot with :ref:`backends <core.backends>`, because they inherit from the generalistic :ref:`modules`.

.. toctree::
	:maxdepth: 2

	openssh
	squid
	samba
	postfix
	nullmailer


Developper documentation
========================

The first thing to read is :ref:`core module documentation <core.modules>`, because extensions inherit from the :class:`~licorn.core.classes.CoreModule` class. The :class:`~licorn.extensions.ExtensionsManager` inherits from the :class:`~licorn.core.classes.ModulesManager`, too.

To know more about a specific extension, follow the user-documentation links above, the classes are there.

Extensions classes
==================

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
