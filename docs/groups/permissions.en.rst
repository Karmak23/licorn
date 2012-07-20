
.. _groups.permissions.en:

.. _permissiveness.en:

==================
Groups permissions
==================

In a few words, Licorn® groups can have 3 types of members:

* *guests*, who **always** have **read-only** access to group data;
* *responsibles*, who **always** have **read-write** (and thus delete) access to group data (files and dirs);
* *members*, whose access to group shared data is dictated by the *permissive state* of the group:

	* *not permissive* means that members have **read-write access to files and dirs they create (and own)** in the group shared directory, and read-only access to any other data (created by other members).
	* *permissive* means that members have read-write access to data created by other members of the group.

Working on the same files in a collaborative manner
---------------------------------------------------

In real-life, users members of a permissive group can **work on the same files**. But this requires the application that handles the file to play nice with this feature. This is completely application-dependant and out of reach for Licorn®:

* e.g. MS Office and OpenOffice.org handle this case gracefully and detect hen multiple users open the same file,
* but standard text editors do not, and the last user who saves the document wins.

If you really want to edit the same file *at the same time*, you need to look at collaborative editors like ``Gobby`` (on Linux) or ``Etherpad Lite`` (a web app). ``Etherpad Lite`` should be integrated to Licorn® in the near future (cf. `#731 <http://dev.licorn.org/ticket/731>`_).


Sharing documents with external partners
----------------------------------------

To give limited access to some documents to external partners, no need to create them a guest account on your server, nor attach too-big-files to emails. Look at the :ref:`simple web sharing <simplesharing.en>` feature provided by Licorn®.  

.. seealso:: :ref:`Simple web sharing documentation <simplesharing.en>` for more details.


Notes to managers / administrators
----------------------------------

Licorn® groups are standard unix groups, with some posix1e ACLs *enforced* to allow users (and you) to forget about them. 

A given user can be only guest **or** standard member **or** responsible, for a given group (member statuses are mutually exclusive). The system will enforce this rule.

In the WMI, promoting or demoting a user is an easy task requiring no confirmation. To take effect, ones need:

* under Linux, to logout / login the current session.
* under Mac / Windows, to disconnect / reconnect the network shares (perhaps logging out / back in is simpler).

In the CLI, promoting a user is immediate (guest → member, guest → responsible or member → responsible), but demoting him/her will require a confirmation with the ``--force`` option.
