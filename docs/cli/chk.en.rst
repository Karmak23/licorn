.. _chk:

.. highlight:: bash

===
CHK
===

Check and repair system objects and attributes.

`chk user`
==========



`chk group`
===========

Multiple commands::

	# check all groups and batch repair everything
	chk groups --all --verbose --batch
	chk groups -avb

	#check links in member's homes too
	chk group hackers --extended
	chk group hackers -e


`chk config`
============

Check the base system, create required groups, check base directories ACLs (but not contents)::

	chk configuration --verbose --batch
	chk config -vb

Check the same, with base directories contents, and backends configuration (e.g. load missing schemata in :ref:`openldap backend <core.backends.openldap>` LINK_TO_BACKEND_USERDOC_PLEASE)::

	# check and repair backends too.
	chk configuration --extended --verbose --batch
	chk config -evb
