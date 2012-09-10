.. _del.en:

.. highlight:: bash


===
DEL
===

`del user`
==========

This deletes one or more user account at a time, specifying either its UID or login. Examples::

	del user toto
	del user toto,tutu

	del user john --no-archive
	del user 10012,10013

To delete a bunch of user accounts by group or profile, head to the specific sections.

`del group`
===========

Deleting one or more group at the same time
-------------------------------------------

	del group hackers
	del group hackers,noobers onemoregroup,oneagain


Mass deleting groups and member's accounts
------------------------------------------

	# delete the group, its member's accounts, without archiving any data (not very kind).
	del group lusers --del-users --no-archive


`del profile`
=============


Deleting profiles and user accounts
-----------------------------------

**WARNING**: you can easily shoot yourself in the foot if you're one of them! Use with caution…

	del profile users --del-users
