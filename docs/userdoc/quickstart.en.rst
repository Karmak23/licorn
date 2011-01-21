.. _quickstart:

.. highlight:: bash

Quickstarter: Licorn® in 3 minutes
==================================

Licorn® is easy to use, you will usually not spend much time on it. This is what I expect from good software: **efficiency** (and sex appeal, but it's software, huh?). Licorn® is all about efficiency for the system manager.

You can quickstart with the :abbr:`CLI Command Line Interface`, which is my prefered interface for its conciseness and good level of auto-guess-what-human-want-without-bothering.

The :abbr:`WMI Web Management Interface` is perfect for normal persons: it has less functionnalities and is totally fool-proof (no root acces). Some say it's a nice piece of modern web interface.

CLI Quickstarter
----------------

Creating 3 users and putting them together in a work group just created::

	add user john --gecos "John Doe"
	add user betty --gecos "Betty Boop"
	add user patty --gecos "Patty Smith"
	add group WorkGroup --members john,betty,patty

After that, putting already existing user ''Ben Gates'' in the group::

	# the short way
	add user ben WorkGroup
	# the long way:
	mod user ben --add-to-group WorkGroup

Betty lost her password::

	# create a random new one (will be printed on screen)
	mod user betty -P

	# interactively change it; root doesn't need to know the old one.
	sudo mod user betty -C
	# the same, human-readable:
	sudo mod user betty --change-password

The group Workgroup is be not permissive by default, meaning that when a member shares a file with others, they can read it but not modify it (:ref:`more details on permissiveness <permissiveness>`?). It you want to be able to, just make the group permissive::

	mod group WorkGroup -p
	# same thing, human-readable:
	mod group WorkGroup --set-permissive

Creating another permissive group, and making already-existing and future users automatically members of this group::

	add group Public_Shared -p --descr 'common shared files for every one'

	# this is applyed live for existing users:
	mod profile users --add-groups Public_Shared

You just modified the `Users` profile, which is shipped by default on Licorn®::

	get profiles
		...
	# -l stands for "--long", you get more informations
	get groups -l
		...
	get users
		...

Clean everything just done in this quickstarter::

	# if you don't specify --no-archive, everything is moved and timestamped in /home/archives
	del user --not-system --no-archive
	del group --not-system --no-archive

Now you can :ref:`discover more about the CLI <cli>`.

WMI Quickstarter
----------------

The WMI offers high-level but limited-set of functionnality compared to CLI. It is aimed at non-professionnal users and occasionnal system administrators. It's fully internationnalized and localized (currently English and French, but more translations are welcome).

To connect to the WMI, you must identify yourself as a user member of group ``licorn-wmi``. To do this, provided you're already an admin of the local machine, just run::

	add user <my_login> licorn-wmi

Then, using the WMI is pretty straightforward: `just head to it with your web browser <http://localhost:3356/>`_ and log in with your standard account.
