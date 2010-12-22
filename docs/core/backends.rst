.. _core.backends:

========
Backends
========

Backends manager
================

The backends manager holds all the backends instance. It loads and unloads them, enables and disables them.

All in all, the backends manager inherits from the :class:`~licorn.core.classes.ModulesManager`, and shares a lot with :class:`~licorn.extensions.ExtensionsManager` (see :ref:`core.modules` for more details).

.. autoclass:: licorn.core.backends.BackendsManager
	:exclude-members: GUID, getAttrProxy, getDaemon, getLocalStorage, delegateTo, getProxy, Pyro_dyncall, remote_retrieve_code, remote_supply_code, setCodeValidator, setPyroDaemon, setGUID
	:members:
	:undoc-members:


Backends
========

These are the real backends implementation. They all inherit from one or more of the abstract classes below.

.. toctree::
	:maxdepth: 2

	backends/shadow
	backends/openldap
	backends/dnsmasq


Backends abstract classes
=========================

.. autoclass:: licorn.core.backends.CoreBackend
	:members:
	:undoc-members:

.. autoclass:: licorn.core.backends.NSSBackend
	:members:
	:undoc-members:

.. autoclass:: licorn.core.backends.UsersBackend
	:members:
	:undoc-members:

.. autoclass:: licorn.core.backends.GroupsBackend
	:members:
	:undoc-members:

.. autoclass:: licorn.core.backends.MachinesBackend
	:members:
	:undoc-members:
