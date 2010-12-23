.. _quickstart:

.. highlight:: bash

Licorn® quickstarter: what can you do in less than one minute ?
===============================================================

One minute is quite a big time spent on Licorn®, you will usually not do it as much. You can quickstart with the CLI (wich has full cow-power) or the WMI, which has less functionnalities but is a nice piece of web interface.

CLI Quickstarter
----------------

Creating 3 users, putting them together in a work group::

	add group WorkGroup
	add user john --gecos "John Doe" --ingroups WorkGroup
	add user betty --gecos "Betty Boop" -G WorkGroup
	add user patty --gecos "Patty Smith" -G WorkGroup

After that, putting already existing user ''Ben Gates'' in the group::

	add user ben WorkGroup

Betty lost her password::

	# create a random new one (will be printed on screen)
	mod user betty -P

	# interactively change it; root doesn't need to know the old one.
	sudo mod user betty -C
	# same command, human-readable:
	sudo mod user betty --change-password

The group will be not permissive by default, meaning that when a member shares a file with others, they can read it but not modify it. It you want to be able to, just make the group permissive::

	mod group WorkGroup -p
	# same thing, human-readable:
	mod group WorkGroup --set-permissive

Creating another permissive group, and making already-existing and future users automatically members of this group::

	add group Public_Shared -p --descr 'common shared files for every one'
	# this is applyed live for existing users:
	mod profile users --add-groups Public_Shared

You just modified the `Users` profile, which is shipped by default on Licorn®::

	get profiles
	# -l stands for "--long", you get more informations
	get groups -l
	get users

WMI Quickstarter
----------------

The WMI offers high-level but limited-set of functionnality compared to CLI. It is aimed at non-professionnal users and occasionnal system administrators. It's fully internationnalized and localized (currently English and French, but more translations are welcome).

To connect to the WMI, you must identify yourself as a user member of group ``licorn-wmi``. To do this, provided you're already an admin of the local machine, just run::

	add user <my_login> licorn-wmi

Then, using the WMI is pretty straightforward: `just head to it with your web browser <http://localhost:3356/>`_ and log in with your standard account.
