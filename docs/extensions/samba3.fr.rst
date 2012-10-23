.. _extensions.samba3.fr:

================
Extension Samba3
================

L'xtension `Samba3` affecte seulement le serveur Licorn®. Elle est actuellement très basique et prend en charge les seules opérations d'ajout/suppression de compte utilisateur, et le changement de mot de passe, pour tenir l'infrastructure Samba synchronisée avec le côté Unix, via :program:`smbpasswd`.

Côté Serveur
============

Dans les versions 1.5.x et supérieures, l'extension `samba3` assure les mêmes fonctions que dans les versions précédentes, et de nouvelles :

* génération des scripts ``netlogon`` lors des ouvertures de sessions sur les postes Windows® ;
* gestion de templates de profils Windows (dans :file:`/home/windows/profiles`) ;
* vérification forcée des permissions dans :file:`/home/windows` et tous ses sous-répertoires à chaque démarrage du daemon Licorn® ;
* mappage de certains groupes Licorn® à des groupes Windows® dignes d'intérêt ; par exemple le groupe ``samba-admins`` est l'équivalent Licorn® des *Administrateurs du Domaine*, et le groupe ``users`` correspond aux `Utilisateurs du domaine` (ou `Utilisateurs authentifiés`) ;
* ajout de permissions Microsoft spéficiques aux groupes précédement mappés (par exemple la permission ``SeMachineAccountPrivilege`` qui permet aux membres de ``samba-admins`` d'ajouter des machines sur le domaine Windows®).
* livraison de tous les scripts `netlogon` et fichiers REG d'usine ajoutant des fonctionnalités particulières du côté des postes clients Microsoft.

Dans les versions 1.4.x et précédentes, l'extension :

* vérifie la présence de :file:`/usr/bin/smbpasswd` et se marque disponible/activée en fonction. Ceci implique que vous pouvez installer votre infrastructure Samba sur une autre machine : tant que :program:`smbpasswd` est installé et configuré localement, peut importe que les services samba soient locaux ou distants, la synchronisation se fera.
* le fichier :file:`smb.conf` n'est actuellement pas touché par Licorn®.


.. todo::
	* gérer les services samba en local s'ils sont installés.

Côté client
===========

* Rien pour l'instant.

.. _extensions.samba3.profiles.fr:

Personnalisation des profils Windows®
=====================================

Lorsque les utilisateurs s'identifient sur les postes Windows®, les actions suivantes sont opérées par le serveur Licorn® :

- sous Windows® 2000/XP Professionel, le répertoire `Mes Documents` de l'utilisateur est `mappé` vers son `répertoire maison` sur le serveur, via le lecteur ``H:`` ;
- sous Windows® Vista/Seven Professionnel, les `bibliothèques` **Documents**, **Images** et **Musique** sont mappées vers leurs équivalents sur le serveur, via des sous-répertoires du lecteur ``H:`` ;
- certains `lecteurs réseaux` sont ou peuvent être automatiquement attachés au Poste de travail (nommé récemment « `Ordinateur` » sous Windows Vista et Seven) ;
- le `Menu Démarrer` et d'autres attributs de session sont adaptés ou peuvent l'être en fonction de plusieurs paramètres.

Ceci passe par un système de scripts profondément personnalisable. Pour chaque utilisateur, un `script de netlogon` est automatiquement généré au moment où celui-ci s'est correctement authentifié sur le serveur Licorn®, puis le script est exécuté sur la machine où s'ouvre la session de l'utilisateur. Ce script est crée dans :file:`\\\\SERVEUR\\netlogon` (:file:`/home/windows/netlogon/` sur le serveur Licorn®), et porte le nom de la machine sur lequel l'utilisateur ouvre la session.

Ce script de `netlogon` est la somme de plusieurs autres, dont le contenu depend des groupes de l'utilisateur, de la version de Windows® sur son poste de travail, et d'autres paramètres explicités ci-après.

.. _extensions.samba3.netlogon.fr:

Scripts ``netlogon`` fournis par Licorn®
----------------------------------------

Ces scripts sont tous personnalisables et sont initialement livrés dans le répertoire :file:`/home/windows/netlogon/templates`. Pour les personnaliser, copiez-les dans :file:`/home/windows/netlogon/local`. Voici une description sommaire de leur contenu :

.. glossary::

	**__header.cmd**
		Fonctions communes à toutes les versions de Windows®, à toutes les
		machines et à tous les utilisateurs (qu'ils soient administrateurs ou
		non). **Ce script est toujours exécuté en premier**.

	**samba-admins.cmd**
		Fonctions communes aux administrateurs du domaine Windows® (membres du
		groupe Licorn® ``samba-admins``). Ce script est lancé juste après
		:file:`__header.cmd` et déverrouille le poste de toutes ses
		restrictions. Il accroche le lecteur ``L:`` (Le partage ``netlogon``)
		au poste de travail pour faciliter l'édition des scripts depuis les
		postes Windows® des administrateurs.

		.. note:: les administrateurs du domaine (membres de ``samba-admins`` ne
			sont pas nécessairement administrateurs Licorn® (membres de
			``admins``) ; ce sont deux rôles distincts que vous pouvez attribuer
			à des personnes différentes. Pour être exact, ``admins`` implique
			``samba-admins``, mais pas l'inverse.

	**responsibles.cmd**
		Fonctions communes aux « responsables », c'est à
		dire les membres du groupe Licorn® ``licorn-wmi`` (= les *gestionnaires*)
		et plus généralement les utilisateurs nommés *responsables* d'au moins
		un groupe sur le système (:ref:`qu'est-ce à dire ? <groups.permissions.fr>`).

	**users.cmd**
		Fonctions communes à tous les autres utilisateurs, non-administrateurs,
		non-gestionnaires et non-responsables. La version d'usine de ce script
		restreint les postes (cache le lecteur C:, empêche les modifications
		dans le panneau de configuration, etc).

		.. warning:: Si vous dupliquez ce script pour le modifier, veillez
			à conserver les appels aux fichiers REG qui assurent les restrictions
			des postes, sinon vos utilisateurs auront plus de droits que prévu.

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

