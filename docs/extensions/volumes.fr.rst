.. _extensions.volumes.fr:


.. highlight:: bash


=================
Extension Volumes
=================

Description
===========

L'extension `Volumes` gère les disques externes.

Elle surveille les connexions et offre des fonctionnalités de montage / démontage / découverte de périphériques. Elle met les volumes connectés à disposition du reste de Licorn® (par exemple l':ref:`extension Rdiff-Backup <extensions.rdiffbackup.fr>` et d'autres).

.. _extensions.volumes.compatible.fr:

Quels périphériques sont supportés (compatibles) ?
--------------------------------------------------

Tout disque externe que vous voulez utiliser avec Licorn® **doit être préalablement partitionné et formatté** avec l'un de ces systèmes de fichiers (qui supporte les ACLs ``posix.1e`` et les ``attributs étendus``):

* ext2 / ext3 / ext4
* btrfs
* xfs
* jfs
* reiserfs

**Dès que vous connectez le disque externe** sur un des ports USB, eSATA ou FireWire de votre serveur, **il est automatiquement monté** dans :file:`/media` (suivant les cas, cette opération peut prendre quelques secondes à quelques minutes, si la partition doit être vérifiée).

.. note::
	* Tout disque externe non-formatté ou formatté avec un autre système de fichiers ne sera pas utilisé par Licorn®; Par conséquent **il ne sera pas monté automatiquement** (sauf configuration explicite).
	* Si la partition montée possède un ``label``, le point de montage l'utilisera (et deviendra :file:`/media/label_de_partition`). Si la partition ne possède pas de label, le point de montage sera quelque chose de plus compliqué (par exemple  :file:`/media/dafd9069-e7de-4f5f-bc09-a7849b2d5389`) : Il sera construit à partir de l'UUID de la partition (un numéro comme ``dafd9069-e7de-4f5f-bc09-a7849b2d5389``, qui identifie la partition de manière unique).

.. _extensions.volumes.usage.fr:

Utilisation
===========

Utilisation générale
--------------------

Gardez en mémoire que vous pouvez adresser un volume soit par son nom de périphérique (par exemple (:file:`/dev/sdb1`), soit par son point de montage (par exemple :file:`/media/Save_Licorn`). Licorn® vous laisse le choix::

	# obtenir la liste des volumes connectés / activés,
	# avec l'espace disponible sur chacun:
	get volumes
	# les volumes dont le nom est rouge ne sont pas
	# activés/réservés pour Licorn®, les verts le sont.

	# démonter un volume en vue de son éjection
	# (vous pouvez le débrancher après ça)
	del volume /dev/sdb1

	# monter manuellement un volume préalablement démonté:
	add volume /dev/sdb1

	# démonter tous les volumes connectés:
	# (ça marche aussi s'il n'y en qu'un, c'est plus court à taper)
	del volumes -a
	# syntaxe complète
	del volumes --all

	# Réserver (=activer) un volume pour Licorn®
	mod volume -e /dev/sdb1
	# version longue:
	mod volume --enable /dev/sdb1

	# Désactiver la réservation pour Licorn®
	mod volume -d /dev/sdb1
	# version longue
	mod volume --disable /dev/sdb1

.. _extensions.volumes.reserve.fr:

Réserver un volume pour Licorn®
-------------------------------

Cette opération est nécessaire pour permettre à Licorn® d'utiliser un volume (pour les sauvegardes par exemple). Sans ça, le disque sera laissé de côté, et Licorn® vous aidera juste en opérant l'auto-montage (sur un serveur, c'est pratique).

Pour réserver un volume, branchez-le, attendez un petit moment qu'il soit auto-monté, et tapez::

	# récupérer les noms des volumes montés
	get volumes
	[...]

	# activer la réservation pour Licorn®
	mod volumes -e /dev/xxx

	# alternativement, vous pouvez utiliser le point de montage:
	mod volumes -e /media/xxxxxx

Une fois activé, ce volume sera automatiquement utilisé par n'importe quelle partie de Licorn® qui a besoin d'un volume pour fonctionner. Pas besoin de recharger quoi que ce soit, le changement est pris en compte dynamiquement.

Résolution des problèmes
========================

* mon périphérique n'apparait pas dans le listing de la commande :command:`get volumes` une fois connecté:

	* premièrement, attendez 10 à 20 secondes qu'il soit détecté (certains disques mettent un certain temps à démarrer, et ne sont détectés qu'une fois que leur moteur est lancé),
	* vérifiez que le disque est bien partionné,
	* vérifiez que la partition est formattée avec un système de fichier supporté (voir plus haut).
	* vérifiez que votre disque est détecté par le noyau (commande :command:`sudo dmesg | tail -n 10`). S'il ne l'est pas:

		* vérifiez qu'il est allumé.
		* vérifiez les branchement du cable, au besoin essayez-en un autre.
		* essayez une autre prise pour brancher le disque.
		* Le serveur ou le disque pourrait avoir un problème matériel. Contactez votre support dédié.

Comment partionner et formatter un volume ?
-------------------------------------------

Vous pouvez faire ça sous Linux avec un outil comme :command:`gparted`. Sinon, recherchez plus d'informations sur le site de votre communauté Linux locale.

Directives de configuration
---------------------------

	**volumes.mount_all_fs**
		Cette directive permet de faire monter tous les volumes à `licornd`, y compris les volumes non compatibles. Il suffit pour celà de la définir à la valeur ``True``. Ceci permet un certain confort sur les machines qui servent aussi de station de travail (comme `udisks` est inhibé par `licornd`, sans cette directive l'on est obligé de monter les volumes manuellement).
		.. note:: les volumes non compatibles ne sont pas listés pour autant via la commande `get volumes`.


.. seealso::

	La :ref:`documentation des volumes dédiée aux développeurs <extensions.volumes.dev.en>` (en anglais), qui pourra vous donner de plus amples détails, si vous êtes développeur.
