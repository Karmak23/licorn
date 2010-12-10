.. _configuration:

.. highlight:: bash


=============
Configuration
=============

You can always access your current configuration by issuing the command::

	get config

Backend specific configuration can be reached here::

	get config backends
	#more to come...
	
	
Main Configuration file
=======================

Generally located at :file:`/etc/licorn/licorn.conf` the main configuration files holds a big number of directives, which all have factory defaults (explaining why the file is nearly empty just after installation), except one (:term:`licornd.role`):

General directives
------------------

.. glossary::

	licornd.role
		role of your current Licorn® installation.

WMI related
-----------

.. glossary::

	licornd.wmi.enabled
		self explanatory: should the WMI be started or not? If you don't use it, don't activate it. You will gain some system resources.

	licornd.wmi.listen_address
		customize the interface the WMI listens on. Set it as an IP address (not a hostname yet).

	licornd.wmi.port
		`3356` by default. Set it as an integer, for example `licornd.wmi.port = 8282`.

Users and groups related
------------------------

.. glossary::

	users.config_dir
		where Licorn® will put its configuration, preferences and customization files for a given user. Default is :file:`~/.licorn`.

	users.check_config_file
		defines the path where the user customization for checks will be looked for. default is `:term:`users.config_dir`/check.conf`.


Other directives
----------------

.. glossary::

	experimental.enabled
		turn on experimental features, depending on wich version of Licorn® you have installed. For example, in version 1.2.3, the experimental directive enables the `Machines` tab in the WMI (the wires are already enabled but non-sysadmins don't get the feature).
	

Check configuration files
=========================

System-wide configuration
-------------------------

In the directory :file:`/etc/licorn/check.d/`, `licornd` will look for files that match a certain naming criteria: the files must start with the name of a controller (e.g. `users` or `groups`) and end with `.conf`. Thus **these names are valid**::

	users.specific.conf
	users.special_dirs.conf
	
	# you can even put special punctuation in filenames...
	users.dir_a and dir-B.conf

But **these names are not**::

	# lacks the 's' at the end of 'user'
	user.dirs.conf
	
	# suffix suggests it's disabled: it is!
	users.specific.conf.disabled


User-level customizations
-------------------------

Put your own customizations in the path designed by :term:`users.check_config_file`.


Check files syntax
------------------

* WARNING: the `users._default.conf` and `groups._default.conf` are special ones. '''NEVER''' rename them.
* the general syntax of file names is (without the spaces): `<controller_name>.<file_name>.conf`
	* where `<controller_name>` in (`users`, `groups`), whether the contents of the file will be related to users or groups.
	* `<file_name>` can be nearly anything you want as Unix name (UTF-8, spaces, etc accepted, '''BUT NOT TAB CHARACTER please''').

 * WARNING: the `*_default*` files named above MUST contain at least ONE line and at most TWO lines, comments excluded (you can put as many as you want). If you don't follow this rule, a huge blue godzilla-like dinosaur will appear from another dimension to destroy the big-loved-teddybear of your damn-cute-face-looking little sister (and she will hate you if she happens to know it's all your fault). You're warned.
 * other files can contain any number of lines, with mixed comments.
 * a line starting with `#` is a comment (`#` should be the '''first''' charracter of the line).
 * basic syntax (without spaces, put here only for better readability):

	<relative_path>		<TAB>		NOACL|POSIXONLY|RESTRICT|RESTRICTED|PRIVATE|<complex_acl_definition>

   * where `<relative_path>` is relative from your home directory, or from the group shared dir. For exemple, protecting your `.gnome` directory, just start the line with `.gnome`. 
   * the `<TAB>` is mandatory (separator). 
   * `NOACL` == `POSIXONLY`: it defines that the dir named <relative_path> and all its contents will have no posix1e ACLs on it, only standard unix perms. When checking this directory, Licorn® will apply perms built from the current '''umask''' (from the calling CLI process).
   * `RESTRICT` == `RESTRICTED` == `PRIVATE`: Only posix permissions on this dir, very restrictive (0700 for directories and 0600 for regular files), regardless of the umask.
   * '''complex ACL definition''': you can define any posix1e ACL (e.g. `user:Tom:r-x,group:Friends:r-x,group:Trusted:rwx`), which will be checked for correctness and validity.
     * you define ACLs for files only. ACLs for dirs will be guessed from them. Please use `@acls.file*` for factory defaults and don't forget to pux `@UX` and `@GX` in your ACLs. These values will be translated to `x` automatically for directories. For files, the translation depends on wether the file is executable or not prior to the ACLs check. The executable bit will be preserved as it is for files. If you don't use the `@*` magic and put `x` directly, all your files will become executable under the dir specified in the rule.
     * you can access defaults from the Licorn® configuration (basically the `configuration.acls` and `configuration.defaults` objects, see output from `get config` for details). To access a configuration value, just prefix it with `@` and do not mention the word `configuration` (e.g. `@acls.acl_base` refers to  the value of `LMC.configuration.acls.acl_base`). See shipped system files for further examples.

== Random Notes ==

 * a user, even an administrator, cannot override any system rule, except the `_default` one (which affects the home dir) This is because factory rules define sane rules for the system to run properly. These rules are usually fixed (`ssh` expects `~/.ssh` to be 0700 for example, this is non-sense to permit to modify these ).

