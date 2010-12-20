.. _core:

============
Licorn® Core
============

The «**core**» handles all important objects of Licorn® (users, groups, machines, etc) through the use of *controllers* which contain and operate on *unit objects*. The number of controllers can vary from a system to another, depending on the locally installed services.

All controllers are held in the :class:`~LicornMasterController`, abbreviated as `LMC`. The `LMC` enables or disables backends, controllers and extensions, via the :class:`~BackendsManager` and :class:`~ExtensionsManager`(these 2 are are always present in the `LMC`).


Licorn® Master Controller
=========================

.. module:: licorn.core

.. autoclass:: LicornMasterController

	.. versionadded:: 1.3
		the :class:`LicornMasterController` was created during the 1.2 ⇢ 1.3 development cycle.

	.. attribute:: users

		`LMC`'s internal instance of class :class:`UsersController`. More details in :ref:`core.users`.

	.. attribute:: groups

		`LMC`'s internal instance of class :class:`GroupsController`. More details in :ref:`core.groups`.

	.. attribute:: locks

		The internal lock manager. Holds all the :class:`~threading.RLock` for all controllers (:class:`LockedController` and derivatives) and individual core objects (:class:`CoreUnitObject` and derivatives). This object should be a :class:`LockManager` instance, but it is not yet: it's just a simple :class:`MixedDictObject`. It should soon evolve.

	.. attribute:: msgproc

		The :class:`MessageProcessor` is used to communicate with clients and between servers, via Pyro (inter-process, local or networked, communication). This object is a special case: it comes from :mod:`licorn.foundations` instead of :mod:`licorn.core`, because other low-level objects in :mod:`licorn.foundations` rely on it and because it doesn't hold any system object (all core objects do). This instance is held in the LMC for the daemon to always have a reference to its own message processor object. FIXME: may go in the :class:`LicornDaemon` soon.

	.. attribute:: _ServerLMC

		An albeit-internal read-only attribute, containing a Pyro AttrProxy to a server-daemon LMC, used in client-daemon initialization only. It's assigned by :meth:`init_client_second_pass` and used internally in private initialization methods to synchronize the backends and extensions from server to clients.

Usage
-----

Once the LMC is instanciated, there are 2 ways for using it:

* **locally** (from inside the daemon), the LMC holds the real system controllers and unit-objects, making them accessible anywhere (`LMC` is a global object).

	* **SERVER**-role daemon::

		LMC.init_conf(...)
		...
		LMC.init_server()
		...

	* **CLIENT**-role daemon::

		LMC.init_conf(...)
		...
		LMC.init_client_first_pass()
		...
		#load and start CommandListener thread here
		...
		LMC.init_client_second_pass()
		...

* **remotely** (from outside the daemon), for use in CLI tools mainly::

	RWI = LMC.connect()
	...
	# put operational code here
	...
	# program terminates, and thus:
	LMC.release()


Common role-related methods
---------------------------

.. class:: LicornMasterController

	.. automethod:: init_conf


Server-role methods
-------------------

.. class:: LicornMasterController

	.. automethod:: init_server
	.. automethod:: reload_controllers_backends


Client-role methods
-------------------

.. class:: LicornMasterController

	.. automethod:: init_client_first_pass
	.. automethod:: init_client_second_pass


Remote-side (no-role) methods
-----------------------------

.. class:: LicornMasterController

	.. automethod:: connect
	.. automethod:: release


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


Core Controllers abstract classes
=================================

.. module:: licorn.core.classes

.. autoclass:: LockedController
	:exclude-members: GUID, getAttrProxy, getDaemon, getLocalStorage, delegateTo, getProxy, Pyro_dyncall, remote_retrieve_code, remote_supply_code, setCodeValidator, setPyroDaemon, setGUID
	:members:
	:undoc-members:

.. autoclass:: CoreController
	:members:
	:undoc-members:

.. autoclass:: CoreFSController
	:exclude-members: ACLRule
	:members:
	:undoc-members:


Core Objects abstract classes
=============================

.. autoclass:: CoreUnitObject
	:members:
	:undoc-members:

.. autoclass:: CoreStoredObject
	:members:
	:undoc-members:

Modules abstract classes
========================

.. autoclass:: ModulesManager
	:members:
	:undoc-members:
