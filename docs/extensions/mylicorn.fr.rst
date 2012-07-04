
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

Causes possibles
----------------

Il peut y avoir plusieurs causes à un problème de connexion :

* la connexion internet est tombée. Licorn® n'y pourra rien ; à vous ou votre gestionnaire de réseau de mener les actions nécessaires à son rétablissement. Lorsque celle-ci sera de nouveau fonctionnelle, Licorn® se reconnectera automatiquement au service dans un délai d'une heure et demie maximum (le délai exact est variable car calculé aléatoirement).

* il y a un problème physique quelque part sur votre réseau local. Soit le routeur ne fait plus correctement son travail, soit un cable ou un commutateur est débranché ou défectueux… Il peut y avoir un grand nombre de causes matérielles à un problème de connexion. Le mieux est de vous adresser à votre gestionnaire informatique ou votre prestataire de support.

* le serveur central `MyLicorn®` est temporairement indisponible. Cela peut arriver car le service en est encore à ses débuts, mais c'est sans conséquence pour vos données, qui sont sauvegardées à distance périodiquement.

* votre compte `MyLicorn®` ou le compte de votre serveur a été désactivé, soit parce que vous êtes arrivé(e) en fin de contrat de maintenance, soit pour une autre raison. En général vous serez averti au moins par email à l'avance si ce cas se produit. Pour plus de détails, contactez le support via l'adresse ``support À licorn POINT org``.

D'autres causes plus rares sont également possibles. Contactez votre gestionnaire informatique ou prestataire de support pour plus d'informations.

Conséquences
------------

Les conséquences d'une déconnexion du service `MyLicorn®` sont **toujours temporaires**, car le serveur tentera périodiquement de se reconnecter tout seul. Elles incluent :

* l'impossibilité de générer des adresses courtes pour les :ref:`partages web simplifiés <simplesharing.fr>`. Ceci ne vous empêche aucunement de préparer les partages, les adresses leur seront attribuées à la reconnexion.

* l'impossibilité pour le serveur de savoir s'il est accessible ou non depuis internet. De même, cette information sera immédiatement mise à jour à la reconnexion.

* en cas de panne temporaire du serveur central, votre `interface de gestion centralisée <http://my.licorn.org>`_ sera aussi innaccessible pendant la durée de la panne. Au delà de cet inconvénient à l'importance relative, rien d'autre n'est affecté.

Résolution
----------

La résolution de ce problème dépend trop de la cause pour être exposée ici. Par ailleurs c'est hors sujet sur ce site dédié à la documentation de Licorn®. Les actions nécessaires doivent être menées à bien par du personnel qualifié.

.. _extensions.mylicorn.unreachable.fr:

Votre serveur est inaccessible depuis internet
==============================================

En deux mots : `le fait que vous accédiez à internet ne signifie pas qu'internet peut accéder à vous.` Dans la plupart des cas c'est une bonne chose car cela signifie que votre réseau est correctement sécurisé.

Causes possibles
----------------

* votre serveur est à l'intérieur d'un réseau protégé, derrière un pare-feu, un routeur ou encore une « box » internet. C'est une configuration toute à fait classique et c'est donc la cause la plus probable.

* si votre serveur Licorn® est mobile – comprenez un « ordinateur portable », les connexions via smartphones bloquent aussi les ports nécessaires à l'acces au serveur chez la plupart des opérateurs. Nous ne pouvons que vous conseiller de choisir un opérateur qui vous laisse `libre` de faire ce que vous entendez faire.

D'autres causes plus rares sont également possibles. Contactez votre gestionnaire informatique ou prestataire de support pour plus d'informations.

Conséquences
------------

* aucun :ref:`partage web simplifié <simplesharing.fr>` n'est accessible si votre serveur ne l'est pas.

* les connexions à distance (``SSH``) seront vraissemblablement affectées et impossibles elles aussi.

* d'autres services moins communs, comme un serveur de réception de courrier seront affectés de la même manière.


Résolution
----------

* la solution consiste à remonter la chaîne d'accès à internet pour vérifier que chaque maillon permet la connexion depuis l'extérieur. Il ne faut cependant pas tout autoriser vers toutes les machines car cela pourrait avoir de graves conséquences pour la sécurité de votre réseau.

* le minimum vital pour permettre les partages web simplifiés est indiqué par le message de la WMI à destination des gestionnaires de réseau (**numéro de port** à ouvrir et **adresse de la machine** cible).

* pour les connexions à distance et les autres services, le port ouvrir ou translater dépend du service en question. Votre gestionnaire informatique ou votre prestataire de support devrait savoir quoi faire.

La résolution des autres causes est hors sujet sur ce site dédié à la documentation de Licorn®. Les actions nécessaires doivent être menées à bien par du personnel qualifié.

.. seealso:: Voyez la :ref:`documentation pour les développeurs <extensions.mylicorn.dev.en>` (en anglais) pour plus de détails.
