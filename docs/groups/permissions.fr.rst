
.. _groups-permissions.fr:

.. _permissiveness.fr:

=========================
Appartenances aux groupes
=========================

En quelques mots, les groupes Licorn® (qui ne sont rien d'autres que des groupes unix purs) peuvent avoir trois types de membres :

* les *invités*, qui n'ont **toujours** qu'un accès en **lecture seule** aux données partagées du groupe ;
* les *responsables*, qui ont **toujours** un **accès complet** (lecture, modification et suppression) à toutes les données du groupe ;
* et les *membres*, dont les droits d'accès aux données partagées sont dictés par l'état de « *permissivité* » du groupe :

	* l'état *non permissif* signifie que ses membres auront un **accès complet aux données qu'ils ont créées eux-même**, et un accès en lecture seulement aux données créées par les autres membres ou responsables. Les groupes sont créés initialement dans cet état, sauf si vous spécifiez explicitement l'inverse. C'est la configuration idéale pour des groupes de travail avec de nombreux membres, tels que les groupes « fourre-tout » ``Commun`` ou ``Partage``.
	* l'état *permissif* signifie que les membres auront un accès complet à toutes les données partagées du groupe et ce, quelque soit le membre créateur/propriétaire. C'est un peu comme si les membres étaient tous *responsables* du groupe. C'est la configuration préférée pour de petits groupes de travail où les gens ont *besoin* de travailler en commun sur les mêmes fichiers.

Travail à plusieurs sur les mêmes documents
-------------------------------------------

Dans la vie réelle, les membres d'un groupe permisif pourront donc ouvrir les fichiers des autres en modification, mais ceci implique que l'application qui ouvre les fichiers gère ce cas de figure :

* par exemple Microsoft Office® et OpenOffice.org® savent détecter quand deux personnes tentent de modifier le même fichier en même temps, 
* mais un éditeur de texte standard ne le sait pas. Dans ce cas précis, c'est toujours le dernier qui enregistre qui écrase les modifications de l'autre. 

Si vous souhaitez éditer un document *en même temps* à plusieurs, il vous faudra vous tourner vers des éditeurs collaboratifs comme ``Gobby`` (sous Linux) ou ``Etherpad Lite`` (en mode web). La solution ``Etherpad Lite`` devrait être intégrée à Licorn prochainement (cf. `#731 <http://dev.licorn.org/ticket/731>`_).


Partage de fichiers avec des intervenants extérieurs
----------------------------------------------------

Pour donner un accès ponctuel à certains documents à des intervenants extérieurs, nul besoin de leur créer un compte sur le serveur, ni de joindre des fichiers imposants à des courriers électronique. Tournez vous vers les :ref:`partages web simplifiés <simplesharing.fr>` proposés par Licorn®.

.. seealso:: La :ref:`documentation des partages web simplifiés <simplesharing.fr>` pour plus de détails.


Notes pour les gestionnaires / administrateurs
----------------------------------------------


Un utilisateur donné ne peut avoir qu'une seule appartenance à un groupe donné : il sera *invité* **ou** *membre* **ou** *responsable*. Ces statuts s'excluent mutuellement et le système le vérifiera. 
	
Dans la WMI, changer un utilisateur d'état est instantané. Cependant les effets du changements nécessitent que :

* sous Linux, l'utilisateur ferme et ré-ouvre sa session,
* sous Windows ou Mac, il déconnecte et reconnecte les lecteurs réseaux du serveur (se délogguer / relogguer est probablement plus simple).
	
Dans la CLI, la promotion d'un utilisateur est immédiate ( invité → membre, invité → responsable ou membre → responsable), mais la déchéance demandera confirmation avec l'option ``--force``.
