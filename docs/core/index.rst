.. _core:

============
Licorn® Core
============

The «**core**» handles all important objects of Licorn® (users, groups, machines, etc) through the use of :ref:`controllers <core.abstract.controller>` which contain and operate on :ref:`unit objects <core.abstract.unitobject>`. The number of controllers can vary from a system to another, depending on the locally installed services.

All controllers are held in the :class:`~licorn.core.LicornMasterController`, abbreviated **LMC** (in the :ref:`daemon`, ``LMC`` is a global instance).

The Licorn® master controller
=============================

The ``LMC`` is one of the most important and central part of the ``core``. It has :ref:`its own dedicated page <core.lmc>`.

Core controllers and objects
============================

.. toctree::
	:maxdepth: 2

	backends
	users
	groups
	profiles
	privileges
	machines
	system

Abstract classes & concepts
===========================

.. toctree::

	abstract
