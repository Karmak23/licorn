
.. _daemon.services.en:

====================
The Service facility
====================

Service facility is an internal mechanism which allow a high level of parallelism in the daemon, and total asynchronous behaviour between every part of Licorn®. It's based on prioritized jobs, submitted from anywhere (there is no limitation).

.. note:: there is currently no callback mechanism in the service facility because in its current form, callbacks would be useless: it would resume the situation to a synchronous call, which you can make much easily by just calling the initial method.

Usage
=====

When you want synchronous behaviour for anything in Licorn®, just call the method and wait for the result. It will be executed by the current thread. Example::

	LMC.users.AddUser(uid=..., login=..., ...)

When you want asynchronous and background processing, just put the method name in the service queue with a priority, and it will be picked by the first awaiting service thread. Example::

	...
	from licorn.daemon import priorities, service
	...

	service(priorities.LOW, lambda: LMC.groups.CheckGroups(['10000']))

The group check will now occur in the background.

[more to come; :ref:`the french version <daemon.services.fr>` has currently more informations ]
