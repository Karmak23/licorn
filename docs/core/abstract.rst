.. _core.abstract:

=================
Core abstractions
=================

Core Controllers abstract classes
=================================

.. module:: licorn.core.classes

The LockedController
--------------------

.. autoclass:: LockedController
	:exclude-members: GUID, getAttrProxy, getDaemon, getLocalStorage, delegateTo, getProxy, Pyro_dyncall, remote_retrieve_code, remote_supply_code, setCodeValidator, setPyroDaemon, setGUID
	:members:
	:undoc-members:

.. _core.abstract.controller:

The CoreController
------------------

.. autoclass:: CoreController
	:members:
	:undoc-members:

The CoreFSController
--------------------

.. autoclass:: CoreFSController
	:exclude-members: ACLRule
	:members:
	:undoc-members:


Core Objects abstract classes
=============================

.. _core.abstract.unitobject:

The CoreUnitObject
------------------

.. autoclass:: CoreUnitObject
	:members:
	:undoc-members:

The CoreStoredObject
--------------------

.. autoclass:: CoreStoredObject
	:members:
	:undoc-members:

.. _core.modules:

Modules abstract classes
========================

The ModulesManager
------------------

It's the base for backends and extensions, because their principles are the same.

.. autoclass:: ModulesManager
	:members:
	:undoc-members:

.. autoclass:: CoreModule
	:members:
	:undoc-members:
