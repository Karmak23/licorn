.. _core.classes:


Licorn® Core
============

Handles all important objects of Licorn® (users, groups, machines, etc) through the use of *controllers* which contain and operate on *unit objects*. The number of controllers can vary from a system to another, depending on the locally installed services. Thus, all controllers are held in the :class:`~LicornMasterController`, which enables or disables other controllers and backends (via the :class:`~BackendController`, which is always here).


Licorn® Master Controller 
-------------------------

.. module:: licorn.core

.. autoclass:: LicornMasterController
	:members:


Core Controllers classes
------------------------

.. module:: licorn.core.classes

.. autoclass:: GiantLockProtectedObject
	:members:

.. autoclass:: CoreController
	:members:

.. autoclass:: CoreFSController
	:members:


Core Objects
------------

.. autoclass:: CoreUnitObject
	:members:

.. autoclass:: CoreStoredObject
	:members:

