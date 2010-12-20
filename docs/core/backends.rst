.. _core.backends:

========
Backends
========

Backends manager
================

The backends manager holds all the backends instance. It loads and unloads them, enables and disables them. All in all, it inherits from the :ref:`~licorn.core.classes.ModulesManager`, because :ref:`Backends` and :ref:`Extensions` share a lot in their structure.

.. autoclass:: licorn.core.backends.BackendsManager
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
