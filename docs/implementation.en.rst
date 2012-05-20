.. _implementation:

========================
Licorn®'s implementation
========================

Users, groups & profiles
========================

- Users

- Groups

	- system groups:
		- are *visually* hidden
		- don't hold a shared directory
		- are not accessible via WMI
	- we never alter GID < 300 (except giving them friendly names in case they are used as privileges), but we use GID 100 [`users`] as a base for default profile.

- Profiles

	- used as primary groups for user accounts => only one per user


.. toctree::
	:maxdepth: 2

	daemon/index.en
