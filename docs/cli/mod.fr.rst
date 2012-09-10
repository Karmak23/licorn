.. _mod.fr:

.. highlight:: bash


===
MOD
===

`mod user`
==========



`mod group`
===========


`mod profile`
=============


`mod configuration`
===================

Configuration système
---------------------


Backends
--------

Activer ou désactiver un backend est aussi simple que cela ::

	# activer le backend OpenLDAP
	mod config -b ldap

	# désactiver le backend OpenLDAP
	mod config -B ldap

``mod`` essaiera de rechercher le nom d'un backend le plus proche possible de celui que vous lui donnez, c'est pourquoi il n'est pas nécessaire de spécifier « ``openldap`` » en toutes lettres.
