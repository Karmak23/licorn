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

.. _extensions.samba3.netlogon.fr:

Personnalisation des profils Windows®
=====================================

Lorsque les utilisateurs s'identifient sur les postes Windows®, les actions suivantes sont opérées par le serveur Licorn® :

- Le répertoire `Mes Documents` de l'utilisateur est `mappé` vers son `répertoire maison` sur le serveur.
- certains `lecteurs réseaux` sont ou peuvent être automatiquement attachés au Poste de travail (nommé récemment « `Ordinateur` » sous Windows Vista et Seven),
- le `Menu Démarrer` et d'autres attributs de session sont adaptés ou peuvent l'être en fonction de plusieurs paramètres.

Ceci passe par un système de scripts profondément personnalisable. Pour chaque utilisateur, un `script de netlogon` est automatiquement généré au moment où celui-ci s'est correctement authentifié sur le serveur Licorn®, puis le script est exécuté sur la machine où s'ouvre la session de l'utilisateur.

Ce script ``netlogon`` est la somme de plusieurs autres, dont le contenu depend des groupes de l'utilisateur, de la version de Windows® sur son poste de travail, et d'autres paramètres explicités ci-après.

Scripts ``netlogon`` fournis par Licorn®
----------------------------------------

Ces scripts sont tous personnalisables et sont initialement livrés dans le répertoire :file:`/home/windows/netlogon/templates`. Pour les personnaliser, copiez-les dans :file:`/home/windows/netlogon/local`. Voici une description sommaire de leur contenu :

.. glossary::

	**_base.cmd**
		Fonctions communes à toutes les versions de Windows®, à toutes les
		machines et à tous les utilisateurs (qu'ils soient administrateurs ou
		non). **Script toujours lancé en premier**.

	**_admins.cmd**
		Fonctions communes aux administrateurs (membres du groupe Licorn®
		``admins``). Ce script est lancé juste après :file:`_base.cmd`
		et déverrouille le poste de toutes ses restrictions.

	**_resps.cmd**
		Fonctions communes aux « responsables », c'est à
		dire les membres du groupe Licorn® ``licorn-wmi`` (= les *gestionnaires*)
		et plus généralement les utilisateurs nommés *responsables* d'au moins
		un groupe sur le système (:ref:`qu'est-ce à dire ? <groups.permissions.fr>`).

	**_users.cmd**
		Fonctions communes à tous les autres utilisateurs, non-administrateurs,
		non-gestionnaires et non-responsables.

.. note:: Si vous copiez puis modifiez un script fourni par Licorn® pour le
	personnaliser, le script d'origine ne sera plus exécuté du tout : le vôtre
	est prioritaire. Veillez donc à ne rien supprimer d'essentiel dans votre
	version.

.. warning:: Si vous décidiez de modifier les scripts « d'usine » fournis par
	les paquetages Licorn®, sachez que ceux-ci sont écrasés à chaque mise à jour
	du logiciel. C'est pour celà que la personnalisation implique la copie à un
	autre endroit.

.. _extensions.samba3.faq.fr:

Foire Aux Questions
===================

Quand je supprime un compte utilisateur via Licorn®, j'observe des messages d'avertissement de samba3 dans les journaux système
-------------------------------------------------------------------------------------------------------------------------------

Les messages prennent la forme suivante::

	[…] samba3: pdb_get_group_sid: Failed to find Unix account for <user>
	[…] samba3: Failed to delete entry for user <user>.

Ils sont parfaitement normaux et n'affectent pas le bon fonctionnement du système. Samba essaie de supprimer le compte Unix de l'utilisateur, alors que cette opération a déjà été efectuée par Licorn®. Ces messages sont inévitables dans la mesure où Samba est configuré pour maintenir les mots de passe Unix synchronisés avec les siens, au cas où un utilisateur change son mot de passe sur un poste Windows/Mac.

