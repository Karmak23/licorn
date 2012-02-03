.. _ltrace:

.. highlight:: bash

=======================================
The Licorn® TRACE mechanism: ``ltrace``
=======================================

If you ever wanted to flood your terminal in a hype manner, this documentation is for you.

If you want to follow Licorn® internal decisions and mechanisms at runtime, this is also for you. Combined with the :command:`licornd` :ref:`interactive shell <daemon_interactive_shell>`, the ``ltrace`` mechanism allows any kind of runtime debug in all Licorn® programs (even the WMI!).

The ``ltrace`` mechanism is simple to use:

* setup the :envvar:`LTRACE` environment variable to any supported value (see below),
* launch the Licorn® programs with the :command:`python` interpreter, without any kind of optimization (eg. without using :option:`-O` or :option:`-OO`). This will enable :keyword:`assert` calls, ontop of which :mod:`~licorn.foundations.ltrace` is built.


.. note:: Relying on :keyword:`assert` calls has one big advantage: when run in optimized mode (eg with :option:`-O` or :option:`-OO`), :keyword:`assert` code is simply suppressed from python bytecode. This is like compiling a C program with or without debugging symbols and hooks: it runs **much faster** without. This is the same with ``ltrace``: running without it in normal conditions makes Licorn® programs lightning fast, and using ``ltrace`` calls in debugging conditions just helps.


Launching Licorn® programs in trace mode
========================================

This is quite special, because of how these programs work in standard conditions: they re-exec themselves at start, if you are not root. Until the re-exec mechanism is rewritten to simplify this operation, you must use these commands:

To trace the daemon's internals, instead of typing::

	licornd -rvvD

You have to type::

	# see below for LTRACE values
	export LTRACE='…'
	sudo python /usr/sbin/licornd -rvvD


To trace a CLI command, instead of typing::

	get users -l

You have to type::

	# see below for LTRACE values
	export LTRACE='…'
	sudo python /usr/bin/get -l

And so on.


LTRACE values
=============

To sum up ``ltrace`` internal features:

* you can use different values in the :envvar:`LTRACE` environment variable, for the daemon and CLI. It's up to you.
* you can define complex values for the :envvar:`LTRACE` environment variable, with ``|`` (``OR`` expression) and ``^`` (``NOT`` expression) and combinations of them. Eg::

	# traces everything (but you know:
	# too much verbosity kills the verbosity)
	export LTRACE='all'

	# A sane (but still very verbose) default to start with:
	export LTRACE='all^base^objects^checks^fsapi^thread^network'

	# ltracing a specific extension:
	export LTRACE='volumes'

	# ltracing interactions between 2 extensions:
	export LTRACE='volumes|rdiffbackup'

	# ltracing network wide-related things:
	export LTRACE='network|machines|system|thread'

	# ltracing daemon's internals:
	export LTRACE='daemon'

	# ltracing daemon's internals, a little more readable:
	export LTRACE='daemon^thread^inotifier'

	# WARNING: the following will not work as expected,
	# because containers and modules are in the wrong order:
	export LTRACE='thread^inotifier|daemon^users^groups|core'

	# use this one instead:
	export LTRACE='daemon^thread^inotifier|core^users^groups'

	#… i'm sure you got the point.

As stated in the examples above, be carefull that the order of ``ltrace`` modules is important in the variable.

This is because ``ltrace`` modules are organized in sets, and the containing set must appear **before** its contained modules (but no matter where the **how before** it is). Eg:

* ``core`` includes ``users``, ``groups``, ``system`` and others;
* ``daemon`` includes ``thread``, ``inotifier`` and others;
* ``extensions`` includes ``volumes``, ``rdiffbackup`` and others;
* and so on.

Until this documentation is finished, see the :mod:`licorn.foundations.ltraces` module for all possible values.

.. note:: ``ltrace`` module names must be unique across all the Licorn® code. As of version 1.3, they are.
