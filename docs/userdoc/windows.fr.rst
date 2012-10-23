
.. _windows.fr:

.. highlight:: bash

===================
Licorn® et Windows®
===================

Votre serveur Licorn® peut jouer le rôle de contrôleur de domaine NT. Ceci inclue la personnalisation de l'ouverture des sessions utilisateurs sur les postes Windows XP professionnel et Windows Vista / 7 Professionnel.


Pré-requis
~~~~~~~~~~

``Samba 3`` doit être installé sur votre serveur Licorn®, et :ref:`l'extension samba3 <extensions.samba3.fr>` activée (vérifiez avec la commande ``get conf ext``).

Configuration des postes Clients
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Windows Vista et Seven Professionnel
====================================

Pour inscrire un poste Windows 7 sur le domaine Samba/Licorn® :

* s'identifier *administrateur local* (pas sur le domaine) sur le poste ;
* sortir du domaine actuel en inscrivant le poste sur n'importe quel *groupe de travail* ;
* redémarrer le poste comme demandé ;
* ré-ouvrir une session en *administrateur local* ;
* parcourir le réseau et fusionner à minima le fichier ``win7.reg`` (dans ``\\SERVEUR\netlogon\templates\registry\``) ;
* fusionner éventuellement d'autres fichiers de registre en fonction des fonctionnalités voulues :
	* pour supprimer la pré-sélection du dernier utilisateur précédement identifié sur le poste, utilisez :file:`Dont_display_last_username.reg`,

	  .. note:: Afin de pouvoir fusionner les fichiers en double-cliquant dessus, il est nécessaire :
		* soit de connecter ``\\SERVEUR\netlogon`` comme un lecteur réseau, et de les exécuter explicitement à partir du lecteur ainsi connecté,
		* soit de copier les fichiers localement (sur le bureau par exemple) si vous parcourez le partage via le réseau.

		Sans celà, vous obtiendrez une erreur de type « *Impossible d'importer fichier.reg : une erreur imputable au disque ou au système de fichiers s'est produite lors de l'ouverture de ce fichier* ».
* redémarrer le poste une seconde fois ;
* ré-ouvrir une session *administrateur local* ;
* joindre le nouveau domaine configuré sur le serveur (par ex. ``CYBER-BASE``). Windows® vous demandera un identifiant et mot de passe habilité à joindre le domaine :
	* utilisez n'importe quel compte membre du groupe ``samba-admins`` sur le serveur Licorn® ;
* redémarrer le poste encore une fois.

À partir de là, les utilisateurs du domaine peuvent s'authentifier sur le poste.

.. seealso:: le `Wiki de Samba à propos de Windows 7 (en anglais) <http://wiki.samba.org/index.php/Windows7>`_ pour une personnalisation plus poussée.

Windows XP Professionnel
========================

La procédure est exactement la même que pour Windows 7, excepté qu'il n'y a pas besoin de fusionner le fichier ``win7.reg``.

Personnalisation des sessions utilisateurs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Scripts de session ``netlogon``
===============================

Ces scripts sont exécutés pour tous les utilisateurs, mais leur contenu est différent en fonction des groupes et des responsabilités de chacun.

* les scripts d'usine et les fichiers REG sont dans ``\\SERVEUR\netlogon\templates`` (voir aussi la :ref:`description des scripts livrés <extensions.samba3.netlogon.fr>`) ;
* ne les modifiez-pas dans ce répertoire, vos modifications seraient écrasées par les mises à jour de Licorn® ;
* dupliquez les scripts que vous souhaitez personnaliser dans le dossier ``\\SERVEUR\netlogon\local`` ;
* Vous pouvez créer de nouveaux scripts en fonction de vos besoins particuliers. Par exemple, si vous avez un groupe ``Adherents``,
	* personnalisations pour les membres du groupe : créer un script ``local/Adherents.cmd`` (notez la majuscule, exactement comme le nom du groupe Licorn®),
	* personnalisations pour les invités : créer un script ``local/gst-Adherents.cmd``
	* personnalisations pour les responsables : créer un script ``local/rsp-Adherents.cmd``

Disponibilité
~~~~~~~~~~~~~

 * le contrôleur de domaine via Samba3 est disponible dans toutes les versions de Licorn® (il suffit de configurer Samba).
 * les versions 1.5 et supérieures ajoutent des fonctionnalités particulières (cf. documentation de l':ref:`extension samba3 <extensions.samba3.fr>`):


