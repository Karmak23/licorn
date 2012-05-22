.. _core.backends.openldap.design.en:

=============================
OpenLDAP backend Design Notes
=============================

The Debian package on Ubuntu 12.04 doesn't do the same setup that on Lucid.
	- /etc/hosts matters for `hostname -d`, which determines the default `dn` in Precise 12.04.
		- in the line:

			127.0.1.1 machine.domain.name machine

			the entry with the FQDN must be first, else it fails silently in slapd postinst script.

	- /etc/hostname: unsure. FQDN or not ?
		- works with FQDN
		- is it necessary ? (in the default conf, /etc/hostname != FQDN)
