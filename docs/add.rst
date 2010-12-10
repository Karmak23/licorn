.. _add:

.. highlight:: bash


===
ADD
===

`add user`
==========

Adding one or more users at a time
----------------------------------

Massive accounts imports from files
-----------------------------------

With the command :command:`add users` (notice the 's').

	add users --filename=import.csv
	

`add machine`
=============

Adding one machine to the local configuration (DHCP and DNS)
------------------------------------------------------------


Scanning local network looking for new hosts
--------------------------------------------

With the command :command:`add machines --auto-scan`::

	add machines -av

