.. _cli.fr:

============================================
Licorn® CLI : interface en ligne de commande
============================================

La CLI est composée de 5 outils, à travers lesquels on gère l'intégralité du système:

	**get**
		lister, sélectionner et afficher les objets système

	**add**
		ajouter des objets

	**mod**
		modifier des objets système

	**del**
		effacer des objets du système

	**chk**
		vérifier ou réparer des objets, des chemins ou la configuration.

Toutes ces commandes incluent une aide intégrée, visible quand vous lancez le programme avec l'argument :option:`--help` (ou :option:`-h`), ou automatiquement affichée lorsque le programme détecte une erreur dans les options que vous lui passez.



The logic behind the CLI is convention-driven, oriented towards extreme simplicity and maximum automatism. All CLI tools will try to provide maximum flexibility to you. Understand that:

#. commands you type can be as small as possible, provided there is no ambiguity,
#. command-line flags are legions, but most of them are synonyms: *just pick the one that fits you best*,

Licorn GET
==========

.. toctree::

	get.fr

Licorn ADD
==========

.. toctree::

	add.fr

Licorn MOD
==========

.. toctree::

	mod.fr

Licorn DEL
==========

.. toctree::

	del.fr

Licorn CHK
==========

.. toctree::

	chk.fr

CLI messages
============

.. todo:: ce texte doit être relu et rafraîchi pour correspondre à la version actuelle de Licorn®.

CLI messages correspond to verbose level.

.. note:: On production system `python -OO` is used ; `debug()` and `debug2()` messages are totally disabled. Using `-vvvv` (or more) will not produce any output, unless scripts are explicitely run with "`python /usr/lib/horizon/<script>.py -vvvv`" to avoid the `-OO`.

* '''verbose level -1''', only `warning()` and `error()` messages are displayed.
* '''verbose level 0 (default)''', `notice()` messages are displayed too. `NOTICE` messages are important for the user. For instance, an automatically created password has to be displayed in order to be noted by the admin, to be transmitted to the user. Without this, something will block, the user cannot log into the system.
* '''verbose level 1 (`-v`)''', `info()` messages are displayed too. `INFO` message are not as important as `NOTICE`, but help following ''changes'' made on the system. For instance, when HST change an ACL on a file, this is an info.
* '''verbose level 2 (`-vv`)''', `progress()` messages are displayed too. `PROGRESS` level help keep track of progress of operations. For instance, when checking ACLs, this will display the filename of the current file beiing checked, whatever its ACLs is, the pathname of the current dir beiing checked, and the former phases of procedures (e.g. when creating a user, this could be "finding UID", "creating user data in internal structures", "saving internal data to disk", "creating user's home", "applying user skel").
* '''verbose level 3 (`-vvv`)''', `debug()` messages are displayed too. `DEBUG` level help keep track of progress of operations when no other official progress tracker exists. For instance, when checking ACLs, this will display the filename of the current file beiing checked, whatever its ACLs is.
* '''verbose level 4 (`-vvvv`)''', `debug2()` messages are displayed too. `DEBUG2` level helps following decisions the program take. It will display the ACL comparison and the result for every file beiing checked.
