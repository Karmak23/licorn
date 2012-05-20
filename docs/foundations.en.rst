.. _foundations:

Licorn® Foundations
===================

Base
----

Collection of very basic objects used as base classes or attributes.

.. module:: licorn.foundations.base

.. autoclass:: NamedObject
	:members:
	:inherited-members:

.. autoclass:: MixedDictObject
	:members:
	:inherited-members:

.. autoclass:: LicornConfigObject
	:members:
	:inherited-members:

.. autoclass:: Enumeration
	:members:
	:inherited-members:

.. autoclass:: DictSingleton
	:members:

.. autoclass:: ObjectSingleton
	:members:


Classes
-------

Collection of simple but directly operational objects used in other parts of the code.

.. module:: licorn.foundations.classes

.. autoclass:: FileLock
	:members:
	
Logging
-------

.. automodule:: licorn.foundations.logging
	:members: error, warning, warning2, notice, info, progress, debug, debug2, ask_for_repair


Messaging
---------

The messaging is implemented via Pyro callback model.

.. module:: licorn.foundations.messaging

.. autoclass:: MessageProcessor
	:members:

.. autoclass:: LicornMessage
	:members:

TTYutils
--------

.. automodule:: licorn.foundations.ttyutils
	:members:	
