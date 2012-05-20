.. _extensions.samba3.fr:

================
Extension Samba3
================

L'xtension `Samba3` affecte seulement le serveur Licorn®. Elle est actuellement très basique et prend en charge les seules opérations d'ajout/suppression de compte utilisateur, et le changement de mot de passe, pour tenir l'infrastructure Samba synchronisée avec le côté Unix, via :program:`smbpasswd`.

Côté Serveur
============

Dans la version 1.3, l'extension `samba3`:

* vérifie la présence de :file:`/usr/bin/smbpasswd` et se marque disponible/activée en fonction. Ceci implique que vous pouvez installer votre infrastructure Samba sur une autre machine : tant que :program:`smbpasswd` est installé et configuré localement, peut importe que les services samba soient locaux ou distants, la synchronisation se fera.
* le fichier :file:`smb.conf` n'est actuellement pas touché par Licorn®.


.. todo::
	* gérer les services samba en local s'ils sont installés.

Côté client
===========

* Rien pour l'instant.


.. _extensions.samba3.faq.fr:

Foire Aux Questions
===================

Quand je supprime un compte utilisateur via Licorn®, j'observe des messages d'avertissement de samba3 dans les journaux système
-------------------------------------------------------------------------------------------------------------------------------

Les messages prennent la forme suivante::

	[…] samba3: pdb_get_group_sid: Failed to find Unix account for <user>
	[…] samba3: Failed to delete entry for user <user>.

Ils sont parfaitement normaux et n'affectent pas le bon fonctionnement du système. Samba essaie de supprimer le compte Unix de l'utilisateur, alors que cette opération a déjà été efectuée par Licorn®. Ces messages sont inévitables dans la mesure où Samba est configuré pour maintenir les mots de passe Unix synchronisés avec les siens, au cas où un utilisateur change son mot de passe sur un poste Windows/Mac.

