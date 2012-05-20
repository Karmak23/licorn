.. _specs.backup.en:

.. highlight:: bash

====================
Backup specification
====================

Example
=======

Backup relies on backup volumes to exist and be connected::

	# list, add, del backup volumes
	get volumes

	# add a .org.licorn.backup_volume file
	add volume --path /dev/sda1

	# --path is optional, /dev/ will be guessed
	add volume sda1

	# a path works too
	add volume --path /media/External_USB

	# create a .org.licorn.ignore_volume file
	mod volume --ignore --path ...

	# delete the .org.licorn.backup_volume
	del volume sda1

	# will remove .org.licorn.backup_volume file
	# AND create a .org.licorn.ignore_volume file
	del volume sda1 --permanent


Here is how I intend to use the backup module from CLI::

	get backups
	get snapshots
	#
	# list of backups, with backup IDs...
	#

	get config backup
	#
	# display the list of backup configuration, excluded/included files/dirs
	#

	# create a backup for the whole system with every changed file/dir
	# --now is optional, without any argument this is now.
	add backup --now
	add snapshot

	# FIXME: explore validity:
	add backup --full
	# not an incremental snapshot (is it feasible? pertinent?)

	# schedule a backup tonight
	add backup at 23:30

	# schedule a backup in 3 hours
	add backup in 3 hours
	add backup in 3h

	# other syntaxes and options (self-explanatory I hope)
	add backup in 30 min
	add backup in 30min
	add backup in 30 minutes
	add backup in 30minutes
	add backup in 10 sec
	...

	# including / excluding files/dirs
	mod backup --exclude|-X '<rdiff-backup-pattern>'
	# and the pattern goes into /etc/licorn/rdiff-backup.excludes.conf
	# idem for (FIXME: find if pertinent or not to have both include/exclude)
	mod backup --include|-I '...'

	# remove the backup ID -> *and all older backups*
	del backup <backup ID>
	this will delete all backups older than ... . Are you sure ?
	del backup <ID> --force | --batch

	# keep only the 3 last backups runs
	del backups --keep 3
	# don't forget "are you sure" and --force...

	# remove all backups older than...
	del backups --older 3 months
