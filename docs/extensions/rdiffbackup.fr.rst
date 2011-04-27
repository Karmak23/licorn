.. _extensions.rdiffbackup.fr:

======================
Extension Rdiff-backup
======================

L'extension `Rdiff-backup` gère les sauvegardes du système sur disque externe. Les sauvegardes système contiennent toute la configuration spécifique de la machine, ainsi que toutes les données utilisateurs (contenu du :file:`/home/` principalement).

En l'état actuel, les sauvegardes ne sont pas compressées ni encryptées. La première sauvegarde nécessitera au moins 1Gio d'espace libre pour la partie système, en plus du volume de vos propres données (utilisateurs et groupes).

Les sauvegardes sont incrémentales et chaque incrément ne prend que peu d'espace (à moduler en fonction de la quantité de données qui changent chaque jour, bien sûr).

Utilisation
===========

Disques externes supportés
--------------------------

N'importe quel disque externe supporté par Ubuntu fonctionnera, pour peu qu'il soit formatté et réservé à Licorn® (suivez la documentation sur :ref:`l'utilisation des volumes <extensions.volumes.usage.fr>`, ou directement :ref:`comment réserver un volume <extensions.volumes.reserve.fr>`).

Opérations de sauvegarde
------------------------

À l'heure actuelle, **toutes les opérations de sauvegarde sont automatiques**, dès qu'un volume de sauvegarde est branché. Il est cependant possible de déclencher une sauvegarde manuellement depuis la WMI.

L'intervale de sauvegarde est configuré via la directive :ref:`backup.interval <backup.interval.fr>`, et c'est tout.

.. note::
	* Si vous devez débrancher le volume dédié aux sauvegardes, celles-ci s'arrêtent. Elles reprennent dès que vous le rebranchez, sans action particulière de votre part.
	* Même si vous pouvez brancher plusieurs volumes sur le système, les **sauvegardes sont effectuées sur le premier branché** uniquement. Si vous souhaitez mettre en place une rotation de sauvegardes sur plusieurs disques, arrangez-vous pour ne pas les connecter en même temps.

Opérations de restauration
--------------------------

Actuellement, **les restaurations sont complètement manuelles** et doivent être réalisées en dehors de Licorn®. Ce problème est en train d'être adressé par les developpeurs et une solution sera mise en place dans les prochains jours.


Documentation pour les développeurs
===================================

Voyez la :ref:`documentation dédiée de l'extension rdiffbackup <extensions.rdiffbackup.dev.en>` (en anglais).
