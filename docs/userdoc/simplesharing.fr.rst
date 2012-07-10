
.. _simplesharing.fr:

.. highlight:: bash

=======================
Partages web simplifiés
=======================

Avec votre serveur Licorn®, vous pouvez partager des fichiers avec des personnes extérieures très simplement :

* dans votre :ref:`répertoire personnel <homedir.fr>`, vous trouverez un dossier nommé :file:`Public`. S'il n'y est pas, créez-le. Attention : c'est « *Public* » avec un « P » majuscule.
* dans ce dossier :file:`Public`, tout répertoire que vous créerez devient automatiquement un partage ! Créez-en donc autant que vous le souhaitez et déposez dedans ce qui vous plait (documents, images…).

Voici un exemple de partage tel qu'il est vu par un visiteur extérieur :

.. image:: ../screenshots/fr/simplesharing/simplesharing0001.png
   :alt: Vue publique d'un partage web simplifié


Adresse de partage
~~~~~~~~~~~~~~~~~~

Vous trouverez la liste de vos partages actifs dans votre `WMI <https://localhost:3356/share/>`_. Dans cette liste, chaque partage se voit affecté une **URI courte** à transmettre à vos partenaires externes pour qu'ils accèdent au partage.

.. image:: ../screenshots/fr/simplesharing/simplesharing0002.png
   :alt: Liste des partages web dans la WMI Licorn®

Les partages sont accessibles depuis l'extérieur comme un extranet public. L'accessibilité dépend de certains paramètres techniques (*est-ce que votre serveur est « atteignable » depuis l'extérieur ?*), mais de manière générale s'il y a un problème, celui-ci sera affiché dans la WMI avec un lien vers de l'aide pour le résoudre.


Notes pour les gestionnaires / administrateurs
----------------------------------------------

Pré-requis
~~~~~~~~~~

Les partages web simplifiés nécessitent que votre serveur Licorn® soit accessible depuis l'extérieur. Pour celà :

* votre routeur doit translater le port ``3356`` de l'extérieur du réseau vers le serveur Licorn®.
* vous devez connaître le nom ou l'adresse IP de votre serveur.
* posséder un nom de domaine est un vrai plus, car vos utilisateurs pourront le donner comme adresse de partage.

Disponibilité
~~~~~~~~~~~~~

 * les partages web simplifiés sont disponibles et activés automatiquement dans les versions 1.4 et supérieures.
 * dans les version 1.3.x, c'est une :ref:`fonctionnalité expérimentale <settings.experimental.enabled.fr>` qu'il vous faut activer manuellement.
 * non-disponible avant la version 1.3.


