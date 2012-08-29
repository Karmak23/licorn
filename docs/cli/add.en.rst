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

With the command :command:`add users` (notice the 's'), and using a CSV file, you can massively import users accounts.

Main command::

	add users --filename=import.csv


Options:

	Several parameters are provided to fully customize your import:

	* --filename : define the file to import.
	* --separator : define the columns' separator in the CSV file, if not set, will be automaticaly sniffed (which could lead to errors if several common separators are used in the file).
	* --profile : define a global profile to apply on each imported accounts (you can use --profile-column if your file provide the information).
	* --confirm-import : really do the import, else will prompt the result of the tested import.

	* --firstname-column : define the firstname column in the CSV file.
	* --last-name-column : define the lastname column in the CSV file.
	* --gecos-column : define the gecos column in the CSV file, if set, this column takes precedence of first/last names columns.
	* --group-column : define the firstname column in the CSV file.
	* --password-column : define the password column in the CSV file.
	* --profile-column : define the profile column in the CSV file.
	* --login-column : define the login column in the CSV file.

Note :

	* All parameters are optional, but you have to provide either gecos	or first/last names, and either a global profile or a profile column

`add machine`
=============

Adding one machine to the local configuration (DHCP and DNS)
------------------------------------------------------------


Scanning local network looking for new hosts
--------------------------------------------

With the command :command:`add machines --auto-scan`::

	add machines -av

