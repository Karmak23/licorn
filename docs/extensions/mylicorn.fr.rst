
.. _extensions.mylicorn.fr:

===================
Extension MyLicorn®
===================

L'extension `MyLicorn®` permet de relier automatiquement votre serveur Licorn® à une `interface de gestion centralisée <http://my.licorn.org>`_, et offre de nouveaux services liés à l'ouverture sur internet.

* par exemple, grâce à la connexion à `MyLicorn®` votre serveur sait à tout moment si la connexion à internet fonctionne, mais aussi s'il est accessible depuis internet, ce qui bénéficie directement aux :ref:`partages web simplifiés <simplesharing.fr>`.
* dans le même ordre d'idées, le central `MyLicorn®` offre le service d'adresses courtes « `lshare` » (telle que ``http://lsha.re/a1b2c3d4``), pour rendre vos partages accessibles à tout moment, quel que soit l'emplacement de votre serveur Licorn®. Ceci même s'il change d'adresse IP plusieurs fois par jour. Par ailleurs le lien court est plus facile à transmettre.

Dans le daemon Licorn®, l'extension `MyLicorn®` fonctionne de manière silencieuse et automatique.

Le seul paramètre à lui donner est la clef d'API `MyLicorn®`, et celle-ci est affichée sur votre `tableau de bord MyLicorn® <http://my.licorn.org>`_.

.. _extensions.mylicorn.disconnected.fr:

Problèmes de connexion au service MyLicorn®
===========================================

Causes
------

Il peut y avoir plusieurs causes à un problème de connexion :

* la connexion internet est tombée. Licorn® n'y pourra rien, à vous ou votre gestionnaire de réseau de mener les actions nécessaires à son rétablissement. Lorsque celle-ci sera de nouveau fonctionnelle, le daemon Licorn® se reconnectera automatiquement au service `MyLicorn®` dans un délai maximum d'une heure et demie (le délai exact est calculé aléatoirement).

* il y a un problème quelque part sur votre réseau local. Soit le routeur ne fait plus correctement son travail, soit un cable ou un commutateur est défectueux… Il peut y avoir un grand nombre de causes matérielles à un problème de connexion. Le mieux est de vous adresser à votre gestionnaire.

* le serveur central `MyLicorn®` est temporairement indisponible. Celà peut arriver car le service est encore à ses débuts, mais c'est sans conséquence pour vos données. Tout est sauvegardé à distance.

* votre compte `MyLicorn®` ou le compte de votre serveur a été désactivé, soit parce que vous êtes arrivé(e) en fin de contrat de maintenance, soit pour une autre raison. En général vous serez averti au moins par email à l'avance si ce cas se produit. Pour plus de détails, contactez le support via l'adresse ``support AT licorn DOT org``.

Conséquences
------------

Les conséquences d'une déconnexion du service `MyLicorn®` sont **toujours temporaires**, car le serveur tentera périodiquement de se reconnecter tout seul. Elles incluent :

* l'impossibilité de générer des adresses courtes pour les :ref:`partages web simplifiés <simplesharing.fr>`. Ceci ne vous empêche aucunement de préparer les partages, les adresses leur seront attribuées à la reconnexion.

* l'impossibilité pour le serveur de savoir s'il est accessible ou non depuis internet. De même, cette information sera immédiatement mise à jour à la reconnexion.

* en cas de panne temporaire du serveur central, votre `interface de gestion centralisée <http://my.licorn.org>`_ sera aussi innaccessible pendant la durée de la panne. Au delà de cet inconvénient à l'importance toute relative, rien ne craint.

.. _extensions.mylicorn.unreachable.fr:

Votre serveur est innaccessible depuis internet
===============================================

à venir…

.. seealso:: Voyez la :ref:`documentation pour les développeurs <extensions.mylicorn.dev.en>` (en anglais) pour plus de détails.
