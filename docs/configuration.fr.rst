
.. _configuration.fr:

.. highlight:: bash

=============
Configuration
=============

Vous pouvez à tout moment consulter la configuration actuelle avec la commande suivante ::

	get config

La liste des :ref:`backends <core.backends.fr>` et des :ref:`extensions <extensions.fr>` n'est pas loin ::

	get config backends
	get config extensions


Fichier de configuration principal
==================================

Situé à l'emplacement :file:`/etc/licorn/licorn.conf`, le fichier de configuration principal inclut un grand nombre de directives, qui ont toutes une valeur d'usine de repli (ce qui explique que le fichier est pratiquement vide à sa création), excepté une (:ref:`role <settings.role.fr>`):

.. note:: les directives sont listées dans l'ordre alphabétique, pas dans l'ordre d'importance.

.. _settings.extensions.rdiffbackup.fr:

Système de sauvegardes
----------------------

.. _extensions.rdiffbackup.backup_time.fr:

	**extensions.rdiffbackup.backup_time**
		L'heure du jour à laquelle la sauvegarde incrémentale est lancée. Valeur d'usine : ``02:00`` (du matin). Spéficiez-la comme une heure sur 24H sous forme de chaîne de texte, comme ``13:45``. Les autres formats d'heure ne sont pas encore supportés.

.. _extensions.rdiffbackup.backup_week_day.fr:

	**extensions.rdiffbackup.backup_week_day**
		Les jours de la semaine où la sauvegarde sera lancée. Valeur d'usine : ``*``, ce qui signifie « tous les jours ». Cette directive doit être une chaîne de texte contenant des chiffres de l'ensemble ``0-6`` séparés par des virgules. ``0`` est dimanche.


Configuration générale
----------------------

.. _settings.role.fr:

	**role**
		Le rôle de votre installation Licorn® locale. Valeur d'usine: dépendante de votre mode d'installation: ``UNSET`` pour une installation depuis les sources, ``CLIENT`` ou ``SERVER`` pour une installation depuis les paquetages.

	.. warning:: Cette directive **doit** être fixée à l'une des valeurs *CLIENT* ou *SERVER*, avant de lancer le :ref:`daemon <daemon.fr>`. Si ce n'est pas fait, le daemon vous le rappellera.


.. _settings.threads.service_min.fr:

	**threads.service_min**
		Le nombre minimal de processus légers de services, lancés dès le démarrage du daemon. Lorsqu'ils sont inactifs, ils deviennent «threads de réserve» et attendent l'arrivée de nouvelles tâches («spare threads» dans le texte). Valeur d'usine: **10 threads** sont démarrés. Plus de renseignements sur le :ref:`mécanisme de service <daemon.services.fr>` ?


.. _settings.threads.service_max.fr:

	**threads.service_max**
		Le nombre maximum de threads de service concurrents. Valeur d'usine: **150 threads** tourneront pendant les périodes de plus forte charge du daemon. Dès que le nombre de tâches décroit, les threads de service supplémentaires (au delà de :ref:`threads.service_min <settings.threads.service_min.fr>`) se terminent au fûr et à mesure, automatiquement.

.. 	_settings.threads.wipe_time.fr:

	**threads.wipe_time**
		Le délai d'attente entre deux nettoyages de threads terminés. Cette directive est utilisée par :class:`PeriodicThreadsCleaner`. Valeur d'usine: **600 seconds** (= 10 minutes).

	.. note::
		* Cette directive n'affecte pas le premier cycle de nettoyage de chacun des nettoyeurs, qui a toujours lieu 30 secondes après le démarrage du démon.
		* Les nettoyeurs sont susceptibles d'être déclenchés en dehors de cet intervale, dans des conditions très précises (notamment à la suite d'une période de forte charge).


.. 	_settings.network.lan_scan.fr:

	**network.lan_scan**
		Active ou désactive les fonctionnalités réseau *automagiques*, qui incluent la découverte des machines sur le :abbr:`LAN Local Area Network (=réseau local)`, la résolution DNS inverse des adresses IP des hôtes réseaux, la résolution ARP des adresses IP, et les notifications d'état récupérées par les serveurs Licorn® (fonctionnalité *server-based status polling*).

		.. note:: même avec cette directive positionnée à ``licornd.network.enabled=False``, les connexions réseau au `daemon <daemon/index.fr>`_ sont toujours possibles, et autorisées. **Les connexions des clients Licorn® vers les serveurs** (synchronisation inter-serveurs, notifications d'état poussées depuis les clients, etc) **continuent donc de fonctionner**, quelquesoit la valeur de cette directive (en fait les clients ALT® ont besoin du serveur pour fonctionner, donc les connexions réseau doivent rester possibles).



CommandListener (Pyro)
----------------------

.. _settings.pyro.port.fr:

	**pyro.port**
		Le port d'écoute pour les commandes à distance du daemon (les commandes à distances incluent la CLI et les autres daemons présents sur le réseau local). Cette valeur doit être un nombre entier compris entre 128 et 1024, par exemple ``licorn.pyro.port = 888``. Valeur d'usine : contenu de :envvar:`PYRO_PORT`, ou ``299`` si la variable d'environnement n'est pas définie.

		.. warning::
			* Si vous avez plusieurs machines Licorn®, il faut modifier cette valeur dans le fichier de configuration de chacune, et le faire pour chaque nouvelle machine arrivant sur le réseau.
			* **Vérifiez bien que vous utilisez une valeur inférieure à 1024**. Le système fonctionnera sans problème si la valeur est supérieure, mais il y a une consquence important en termes de sécurité: les ports <1024 ne peuvent être utilisés que par root, et c'est déjà un début de sécurité pour la communcation inter-daemons.
			* Par ailleurs, vérifiez que le port que vous choisissez n'est pas déjà occupé: les ports < 1024 sont standardisés et leur utilisation est restreinte. Certains (comme le ``299``) n'ont pas été utilisés depuis tellement d'années qu'il n'y a aucun risque à l'utiliser mais ce n'est pas le cas de tous.

		.. seealso:: `La documentation de Pyro <http://www.xs4all.nl/~irmen/pyro3/manual/3-install.html>`_ pour plus de détails.



Directives liées à la WMI
-------------------------


.. _settings.wmi.enabled.fr:

	**wmi.enabled**
		Définit si la WMI doit être démarrée ou pas. Si vous ne vous en servez pas, vous économiserez des ressources système en ne la lançant pas. Si la directive n'est pas définie, la WMI est lancée. Pour ne pas la lancer, définissez ``wmi.enabled = False``.


.. _settings.wmi.group.fr:

	**wmi.group**
		Les utilisateurs membres de ce groupe auront accès à la WMI, et pourront administrer le système de manière limitée : ce n'est pas un équivalent « administrateur » complet. La valeur par défaut pour ce groupe est ``licorn-wmi``. Toute référence à un groupe non-existant entrainera sa création immédiate au lancement de la WMI, car elle en a besoin pour fonctionner. Attention aux fautes de frappes, donc.

		.. note:: Ça peut être une bonne idée — ou pas, celà dépend de vos utilisateurs — d' *enregistrer ce groupe en tant que privilège*, pour permettre aux pseudo-administrateurs WMI de déléguer ce droit à certains autres utilisateurs de confiance.


.. _settings.wmi.listen_address.fr:

	**wmi.listen_address**
		Change l'adresse IP où le nom d'hôte sur laquelle :program:`licornd-wmi` écoute et attend les requêtes. Pour l'instant seules les adresses IP sont prises en charge. Par défaut lorsque cette directive n'est pas définie, la WMI écoute sur toutes les interfaces.

		.. versionadded 1.3:: dans les versions précédentes, la WMI n'écoutait que sur l'interface loopback ``localhost`` (adresse IP ``127.0.0.1``).


.. _settings.wmi.log_file.fr:

	**wmi.log_file**
		Chemin vers le fichier journal d'accès HTTP de la WMI. Valeur par défaut : :file:`/var/log/licornd-wmi.log`. Le format de ce fichier de log est compatible avec ceux d':program:`Apache`, c'est un ``CustomLog`` pour les connaisseurs.


.. _settings.wmi.port.fr:

	**wmi.port**
		Port ``3356`` par défaut. Définissez-le en tant que nombre entier, par exemple `wmi.port = 8282`. Il n'y a pas de restriction particulière, à part que ce port doit être différent de celui de Pyro — cf. :ref:`pyro.port <settings.pyro.port.fr>`, et évidemment ne pas être en conflit avec un autre port système.



Utilisateurs et aux groupes
---------------------------

.. warning:: Il faut vraiment avoir des besoins très spécifiques pour changer ces directives. De surcroît, il n'est recommandé de le faire que sur un système vierge de tout compte utilisateur et tout groupe, sans quoi les comptes ou groupes déjà présents pourraient ne plus fonctionner correctement.

.. _settings.users.config_dir.fr:

	**users.config_dir**
		Where Licorn® will put its configuration, preferences and customization files for a given user. Default is :file:`~/.licorn`.

.. _settings.users.check_config_file.fr:

	**users.check_config_file**
		Defines the path where the user customization file for checks will be looked for. Default is `check.conf` in :ref:`users.config_dir <settings.users.config_dir.fr>`, or with full path: :file:`~/.licorn/check.conf`.



Autres directives
-----------------

.. glossary::

.. _settings.experimental.enabled.fr:

	**experimental.enabled**
		Activer les fonctionnalités expérimentales. Les fonctionnalités en question dépendent de la version de Licorn® installée. Par exemple dans la version 1.2.3, celà active les ``Machines`` dans la WMI pour utilisateurs avec pouvoirs, et dans la version 1.3 celà active aussi les partages web simplifiés.


Configuration du système de permissions
=======================================


Configuration globale
---------------------

Dans le répertoire :file:`/etc/licorn/check.d/`, `licornd` recherchera des fichiers qui vérifient des critères de nommage : ceux qui commencent par le nom d'un contrôleur (c.a.d. `users` ou `groups`) et finissent par `.conf`. À titre d'exemples, **ces noms sont valides** ::

	users.specific.conf
	users.special_dirs.conf

	# vous pouvez même mettre des caractères spéciaux…
	users.dir_a and dir-B.conf

But **ces noms sont invalides** ::

	# Il manque le « s » à la fin de « user »
	user.dirs.conf

	# Le suffixe suggère que ce fichier est désactivé : c'est le cas !
	users.specific.conf.disabled

.. warning::
	* Certains fichiers, comme :file:`users.00_default.conf` et :file:`groups.00_default.conf` sont spéciaux : ils sont la configuration d'usine minimale. **Ne les renommez jamais**. Vous pouvez les modifier selon vos besoins mais seulement si vous savez ce que vous faites !
	* Ces fichiers `*00_default*` **DOIVENT** contenir **au moins UNE ligne au maximum DEUX**, en excluant les commentaires (qui peuvent être aussi nombreux que nécessaire). Les autres fichiers de configuration n'ont pas de restrictions de ce type.

	Si vous n'observez pas ces recommendations, « a huge blue godzilla-like dinosaur will appear from another dimension to destroy the big-loved-teddybear of your damn-cute-face-looking little sister (and she will hate you if she happens to know it's all your fault) » (en anglais dans le texte), ou alors les vérifications et :ref:`chk <chk.fr>` ne fonctionnera plus, ou le daemon Licorn® plantera. Vous êtes prévenu(e).



.. note:: la suite n'est pas traduite. Le moindre volontarisme sera fortement apprécié, peut-être même récompensé…


User-level customizations
-------------------------

Put your own customizations in the path designed by :ref:`users.check_config_file <settings.users.check_config_file.fr>`. User customizations cannot override any system rules, except the one for :file:`~` (`$HOME`) (see :ref:`random_notes` below).


Check files syntax
------------------

* other files can contain any number of lines, with mixed comments.
* a line starting with `#` is a comment (`#` should be the *first* character of the line).
* basic syntax (without spaces, put here only for better readability)::

	<relative_path>		<TAB>		<permission_definition>

* where:

	* `<relative_path>` is relative from your home directory, or from the group shared dir. For exemple, protecting your :file:`.gnome` directory, just start the line with `.gnome`.
	* `<relative_path>` can be nearly anything you want (UTF-8, spaces, etc accepted). **But NO TAB please**, because `TAB` is the separator.
	* the `<TAB>` is mandatory (see above).

* And <permission_definition> is one of: :term:`NOACL`, `POSIXONLY`, :term:`RESTRICT[ED]`, `PRIVATE` or a :term:`Complex ACL definition`:

.. glossary::

	NOACL
		(`POSIXONLY` is a synonym) defines that the dir or file named `<relative_path>` and all its contents will have **NO POSIX.1e ACLs** on it, only standard unix perms. When checking this directory or file, Licorn® will apply standard permssions (`0777` for directories, `0666` for files) and'ed with the current *umask* (from the calling CLI process, not the user's one).

	RESTRICT[ED]
		(we mean `RESTRICT` or `RESTRICTED`, and `PRIVATE` which are all synonyms) Only posix permissions on this dir, and very restrictive (`0700` for directories, `0600` for regular files), regardless of the umask.

	Complex ACL definition
		You can define any POSIX.1e ACL here (e.g. `user:Tom:r-x,group:Friends:r-x,group:Trusted:rwx`). This ACL which will be checked for correctness and validity before beiing applyed. **You define ACLs for files only**: ACLs for dirs will be guessed from them. You've got some Licorn® specific :ref:`acls_configuration_shortcuts` for these (see below).


.. _acls_configuration_shortcuts.fr:

ACLs configuration shortcuts
----------------------------

To build you system-wide or user-customized ACLs rules, some special values are available to you. This allows more dynamic configuration.

.. glossary::

	@acls.*
		Refer to factory default values for ACLs, pre-computed in Licorn® (e.g. `@acls.acl_base` refers to the value of `LMC.configuration.acls.acl_base`). More doc to come on this subject later, but command :command:`get config | grep acls` can be a little help for getting all the possible values.

	@defaults.*
		Refer to factory defaults for system group names or other special cases (see :command:`get config` too, for a complete listing).

	@users.*
		Same thing for users-related configuration defaults and factory settings (same comment as before, :command:`get config` is your friend).

	@groups.*
		You get the idea (you really know what I want tu put in these parents, don't you?).

	@UX and @GX
		These are special magic to indicate that the executable bit of files (User eXecutable and Group eXecutable, respectively) should be maintained as it is. This means that prior to the applying of ACLs, Licorn® will note the status of the executable bit and replace these magic flags by the real value of the bit. If you want to force a particular executable bit value, just specify `-` or `x` and the exec bit will be forced off or on, respectively). Note that `@UX` and `@GX` are always translated to `x` for directories, to avoid traversal problems.


You can always find detailled examples in the system configuration files shipped in your Licorn® package.


.. _random_notes.fr:

Random Notes
------------

A user, even an administrator, cannot override any system rule, except the `~` one (which affects the home dir) This is because factory rules define sane rules for the system to run properly. These rules are usually fixed (`ssh` expects `~/.ssh` to be 0700 for example, this is non-sense to permit to modify these).

