.. _cli.en:

====================================
Licorn® CLI (Command Line Interface)
====================================

The Licorn® CLI consists of five tools, used to manage the entire system:

.. glossary::

	get
		list, select and display data

	add
		add objects to the system

	mod
		modify system objects

	del
		delete objects from the system

	chk
		check objects, paths, configuration, whatever can be, and repair interactively (or not).

All of them include integrated help if you call the program with argument `--help` (or `-h`) or if you make any mistake on the command line.

The logic behind the CLI is convention-driven, oriented towards extreme simplicity and maximum automatism. All CLI tools will try to provide maximum flexibility to you. Understand that:

#. commands you type can be as small as possible, provided there is no ambiguity,
#. command-line flags are legions, and many of them have synonyms: *just pick the one that fits you best*,
#. if you use the command-line a lot (like me), you'll find that Licorn® CLI tools try to match "common" arguments: `-i` (like in `rm -i`), `-f` (like in `cp -f`), `-a` (for `all`), and some other that you could be used to.

Licorn GET
==========

.. toctree::

	get.en

Licorn ADD
==========

.. toctree::

	add.en

Licorn MOD
==========

.. toctree::

	mod.en

Licorn DEL
==========

.. toctree::

	del.en

Licorn CHK
==========

.. toctree::

	chk.en

CLI messages
============

.. todo:: this section needs reviewing and refreshing to correspond to the current version of Licorn®.

CLI messages correspond to verbose level.

.. note:: On production system `python -OO` is used ; `debug()` and `debug2()` messages are totally disabled. Using `-vvvv` (or more) will not produce any output, unless scripts are explicitely run with "`python /usr/lib/horizon/<script>.py -vvvv`" to avoid the `-OO`.

* '''verbose level -1''', only `warning()` and `error()` messages are displayed.
* '''verbose level 0 (default)''', `notice()` messages are displayed too. `NOTICE` messages are important for the user. For instance, an automatically created password has to be displayed in order to be noted by the admin, to be transmitted to the user. Without this, something will block, the user cannot log into the system.
* '''verbose level 1 (`-v`)''', `info()` messages are displayed too. `INFO` message are not as important as `NOTICE`, but help following ''changes'' made on the system. For instance, when HST change an ACL on a file, this is an info.
* '''verbose level 2 (`-vv`)''', `progress()` messages are displayed too. `PROGRESS` level help keep track of progress of operations. For instance, when checking ACLs, this will display the filename of the current file beiing checked, whatever its ACLs is, the pathname of the current dir beiing checked, and the former phases of procedures (e.g. when creating a user, this could be "finding UID", "creating user data in internal structures", "saving internal data to disk", "creating user's home", "applying user skel").
* '''verbose level 3 (`-vvv`)''', `debug()` messages are displayed too. `DEBUG` level help keep track of progress of operations when no other official progress tracker exists. For instance, when checking ACLs, this will display the filename of the current file beiing checked, whatever its ACLs is.
* '''verbose level 4 (`-vvvv`)''', `debug2()` messages are displayed too. `DEBUG2` level helps following decisions the program take. It will display the ACL comparison and the result for every file beiing checked.
