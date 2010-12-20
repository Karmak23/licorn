.. _configuration:

.. highlight:: bash


=============
Configuration
=============

You can always access your current configuration by issuing the command::

	get config

Backend specific configuration can be reached here::

	get config backends
	#more to come...


Main Configuration file
=======================

Generally located at :file:`/etc/licorn/licorn.conf` the main configuration files holds a big number of directives, which all have factory defaults (explaining why the file is nearly empty just after installation), except one (:term:`licornd.role`):

General directives
------------------

.. glossary::

	licornd.role
		Role of your current Licorn® installation. This directive **must** be set to either *CLIENT* or *SERVER*, before daemon launch. If it is unset, the daemon will remind you.

	licornd.threads.pool_members
		How many resolver threads to start in pools. This value is common to all threads pools (Pingers, Arpingers, Reversers, PyroFinders, etc). Default: **5 threads** will be started. There is no configuration for min and max yet.

	licornd.threads.wipe_time
		The cycle delay of :term:`PeriodicThreadsCleaner` and :term:`QueuesEmptyer` threads. How long will they wait between each iteration of their cleaning loop. (Default: **600 seconds**, = 10 minutes). This doesn't affect their first run, which is always 30 seconds after daemon start.

	licornd.network.enabled
		Enable or disable the *automagic* network features. This includes network discovery (LAN and further), Reverse DNS resolution, ARP resolution and *server-based* status updates (polling from server to clients).

		.. note:: even with ``licornd.network.enabled=False``, LAN connections to the :ref:`daemon` are still authorized: **client-initiated connections (daemon synchronization, status push…) continue to work**, regardless of this directive (this is because ALT® clients strictly need the daemon to work).

WMI related
-----------

.. glossary::

	licornd.wmi.enabled
		Self explanatory: should the WMI be started or not? If you don't use it, don't activate it. You will save some system resources.

	licornd.wmi.listen_address
		Customize the interface the WMI listens on. Set it as an IP address (not a hostname yet).

	licornd.wmi.port
		**Port `3356`** by default. Set it as an integer, for example `licornd.wmi.port = 8282`. There is no particular restriction, except that this port must be different from the Pyro one (see :term:`licornd.pyro.port`).

	licornd.wmi.group
		Users members of this group will be able to access the WMI and administer some [quite limited] parts of the system. Default value is **`licorn-wmi`** . Any value referencing a non existing group will trigger a group creation at next daemon start. It is a good idea (or not, depending on your users) to *register this group as a privilege*.

	licornd.wmi.log_file
		Path to the WMI `access_log` (default: :file:`/var/log/licornd-wmi.log`). The log format is Apache compatible, it is a `CustomLog`.


CommandListener (Pyro) related
------------------------------

.. glossary::

	licornd.pyro.port
		**Port `299`** by default. Set it as an integer, for example `licorn.pyro.port = 888`. **Be sure to put it under 1024** (the system will work if it >1024, but there's a bad security implication; ports <1024 can only be bound by root and this is little but certain protection). Be careful not to take an already taken port on your system.

Note: If you dont set this configuration directive, the Pyro environment variable :envvar:`PYRO_PORT` takes precedence over the Licorn® factory default. See `the Pyro documentation <http://www.xs4all.nl/~irmen/pyro3/manual/3-install.html>`_ for details.

Users and groups related
------------------------

.. glossary::

	users.config_dir
		Where Licorn® will put its configuration, preferences and customization files for a given user. Default is :file:`~/.licorn`.

	users.check_config_file
		Defines the path where the user customization file for checks will be looked for. Default is `check.conf` in :term:`users.config_dir`, or with full path: :file:`~/.licorn/check.conf`.


Other directives
----------------

.. glossary::

	experimental.enabled
		turn on experimental features, depending on wich version of Licorn® you have installed. For example, in version 1.2.3, the experimental directive enables the `Machines` tab in the WMI (the wires are already enabled but non-sysadmins don't get the feature).


Check configuration files
=========================


System-wide configuration
-------------------------

In the system directory :file:`/etc/licorn/check.d/`, `licornd` will look for files that match a certain naming criteria: the filenames must start with the name of a controller (e.g. `users` or `groups`) and end with the suffix `.conf`. Thus **these names are valid**::

	users.specific.conf
	users.special_dirs.conf

	# you can even put special punctuation in filenames...
	users.dir_a and dir-B.conf

But **these names are not**::

	# lacks the 's' at the end of 'user'
	user.dirs.conf

	# suffix suggests it's disabled: it is!
	users.specific.conf.disabled

Important notes:

* the files :file:`users.00_default.conf` and :file:`groups.00_default.conf` are very special. **never rename them**.
* the `*00_default*` files named above MUST contain **at least ONE line and at most TWO lines**, comments excluded (you can put as many as you want). If you don't follow this rule, a huge blue godzilla-like dinosaur will appear from another dimension to destroy the big-loved-teddybear of your damn-cute-face-looking little sister (and she will hate you if she happens to know it's all your fault). You're warned.



User-level customizations
-------------------------

Put your own customizations in the path designed by :term:`users.check_config_file`. User customizations cannot override any system rules, except the one for :file:`~` (`$HOME`) (see :ref:`random_notes` below).


Check files syntax
------------------

* other files can contain any number of lines, with mixed comments.
* a line starting with `#` is a comment (`#` should be the *first* character of the line).
* basic syntax (without spaces, put here only for better readability)::

	<relative_path>		<TAB>		<permission_definition>

* where:

	* `<relative_path>` is relative from your home directory, or from the group shared dir. For exemple, protecting your :file:`.gnome` directory, just start the line with `.gnome`.
	* `<relative_path>` can be nearly anything you want (UTF-8, spaces, etc accepted). **But NO TAB please**, because `TAB` is the separator.
	* the `<TAB>` is mandatory (see above).

* And <permission_definition> is one of: :term:`NOACL`, `POSIXONLY`, :term:`RESTRICT[ED]`, `PRIVATE` or a :term:`Complex ACL definition`:

.. glossary::

	NOACL
		(`POSIXONLY` is a synonym) defines that the dir or file named `<relative_path>` and all its contents will have **NO POSIX.1e ACLs** on it, only standard unix perms. When checking this directory or file, Licorn® will apply standard permssions (`0777` for directories, `0666` for files) and'ed with the current *umask* (from the calling CLI process, not the user's one).

	RESTRICT[ED]
		(we mean `RESTRICT` or `RESTRICTED`, and `PRIVATE` which are all synonyms) Only posix permissions on this dir, and very restrictive (`0700` for directories, `0600` for regular files), regardless of the umask.

	Complex ACL definition
		You can define any POSIX.1e ACL here (e.g. `user:Tom:r-x,group:Friends:r-x,group:Trusted:rwx`). This ACL which will be checked for correctness and validity before beiing applyed. **You define ACLs for files only**: ACLs for dirs will be guessed from them. You've got some Licorn® specific :ref:`acls_configuration_shortcuts` for these (see below).


.. _acls_configuration_shortcuts:

ACLs configuration shortcuts
----------------------------

To build you system-wide or user-customized ACLs rules, some special values are available to you. This allows more dynamic configuration.

.. glossary::

	@acls.*
		Refer to factory default values for ACLs, pre-computed in Licorn® (e.g. `@acls.acl_base` refers to the value of `LMC.configuration.acls.acl_base`). More doc to come on this subject later, but command :command:`get config | grep acls` can be a little help for getting all the possible values.

	@defaults.*
		Refer to factory defaults for system group names or other special cases (see :command:`get config` too, for a complete listing).

	@users.*
		Same thing for users-related configuration defaults and factory settings (same comment as before, :command:`get config` is your friend).

	@groups.*
		You get the idea (you really know what I want tu put in these parents, don't you?).

	@UX and @GX
		These are special magic to indicate that the executable bit of files (User eXecutable and Group eXecutable, respectively) should be maintained as it is. This means that prior to the applying of ACLs, Licorn® will note the status of the executable bit and replace these magic flags by the real value of the bit. If you want to force a particular executable bit value, just specify `-` or `x` and the exec bit will be forced off or on, respectively). Note that `@UX` and `@GX` are always translated to `x` for directories, to avoid traversal problems.


You can always find detailled examples in the system configuration files shipped in your Licorn® package.


.. _random_notes:

Random Notes
------------

A user, even an administrator, cannot override any system rule, except the `~` one (which affects the home dir) This is because factory rules define sane rules for the system to run properly. These rules are usually fixed (`ssh` expects `~/.ssh` to be 0700 for example, this is non-sense to permit to modify these).

