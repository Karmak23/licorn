.. _groupspermissions:

.. _permissiveness:

==================
Groups permissions
==================

In a few words, Licorn® groups (which are pure unix groups, in fact) can have 3 types of members:

* *guests*, who **always** have **read-only** access to group data;
* *responsibles*, who **always** have **read-write** (and thus delete) access to group data (files and dirs);
* *members*, whose access to group shared data is dictated by the *permissive state* of the group:

	* *not permissive* means that members have **read-write access to files and dirs they create (and own)** in the group shared directory, and read-only access to any other data (created by other members).
	* *permissive* means that members have read-write access to data created by other members of the group.

In real-life terms, this means that users members of a permissive group **can work on the same files in a collaborative manner**, provided the application that handles the file can play nice with this feature, which is completely application-dependant (e.g. MS Office and OpenOffice.org handle this cases, standard text editors do not)	.

.. warning::
	A given user can be only guest **or** responsible **or** standard member for a given group (=member statuses are mutually exclusive).

	Currently, the system will not enforce this. Thus, if you give him/her more than one membership, the one with the most restrictive permissions will be applyed by the system (i.e. a *guest & responsible* will be only *guest*, a *responsible & member* will only be *member*).
