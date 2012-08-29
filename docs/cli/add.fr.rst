.. _add:

.. highlight:: bash


===
ADD
===

`add user`
==========

Ajouter un ou plusieurs utilisateurs en même temps
--------------------------------------------------

Import massif de comptes depuis un fichier
------------------------------------------

Avec la commande :command:`add users`, et avec un fichier CSV, vous pouvez facilement importer massivement des utilisateurs.

Commande principale::

	add users --filename=import.csv

Options:

	Différents paramètres peuvents être utilisés pour interagir avec le mécanisme:

	* --filename : défini le fichier à importer.
	* --separator : défini le séparateur des colonnes du fichier. Si il n'est pas renseigné, il sera automatiquement trouvé dans le fichier (ceci pour conduire à des erreurs si plusieurs séparateurs sont utilisés dans le fichier).
	* --profile : défini un profil global pour tous les utilisateurs qui seront importés (voir l'option --profile-column si votre fichier contient cette information).
	* --confirm-import : effectue réellement l'import, sinon un récapitulatif du test de l'import sera présenté à l'utilisateur.

	* --firstname-column : défini la colonne du prénom dans le fichier.
	* --last-name-column : défini la colonne du nom de famille dans le fichier.
	* --gecos-column : défini la colonne du gecos dans le fichier, si spécifé  les colonnes "Prénom" et "Nom de famille" ne seront pas utilisées.
	* --group-column : défini la colonne des groupes dans le fichier.
	* --password-column : défini la colonne du mot de passe dans le fichier.
	* --profile-column : défini la colonne du profil dans le fichier.
	* --login-column : défini la colonne de l'identifiant dans le fichier.

Note :

	* La plupart des paramètres sont optionnels, mais vous devez tout de même au minimum fournir soit le "gecos" soit le couple "prénom"/"nom de famille" ainsi que soit un profile global soit une colonne de profile.

`add machine`
=============

Ajouter une machine dans la configuration locale (DHCP et DNS)
--------------------------------------------------------------


Scanner le réseau local à la recherche de nouvelles machines
------------------------------------------------------------

Avec la commande :command:`add machines --auto-scan`::

	add machines -av

