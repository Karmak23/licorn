.. _extensions.squid.fr:

===============
Extension Squid
===============

*NOTE: cette page est en cours de rédaction.*

L'extension `Squid` gère la configuration du serveur mandataire HTTP/FTP. Elle affecte les clients et les serveurs Licorn®. Elle a été testée majoritairement sur Squid 2.7, et a été modifié pour être compatible avec Squid 3 (mais n'a pas été officiellement validée).

Côté serveur
============

* vérifie :file:`/etc/squid/squid.conf` et ajoute le nécessaire pour que les clients locaux puisse se connecter au proxy.
* gère le fichier :file:`/etc/environment` pour y insérer :envvar:`http_proxy` et les autres variables nécessaires.
* gère le démarrage/redémarrage du daemon :program:`squid` quand c'est nécessaire.
* gère la configuration gconf/gnome sous forme de clés non-modifiables par les utilisateurs (configuration ``mandatory``).
* KDE n'est pas encore géré.

Côté clients
============

* gère :file:`/etc/environment` pour y configurer :envvar:`http_proxy` et les autres variables en les faisant pointer vers le serveur.
* idem pour gconf/gnome.
* KDE n'est pas encore géré.


Documentation pour les développeurs
===================================

Voyez la :ref:`documentation dédiée de l'extension squid <extensions.squid.dev.en>` (en anglais).
