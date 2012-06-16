add priv cdrom
add group grp1,grp2
add user testw1,testw2 -G licorn-wmi,cdrom,audio
add user testa1,testa2 -G admins,grp1

# check_users()

## Licorn® part-time admins (licorn-wmi)

	- login testw1

### me

	- mod gecos > OK
	- mod passwd > OK
	- mod shell > OK

	- add me grp1 > OK
	- mod me grp1 > OK
	- del me grp1 > OK

	- del me licorn-wmi > error priv
	- del me cdrom > error priv
	- (del me audio > not visible)

	- del me > error captain
	- lock me > error lock me
	- skel > OK
	- massive del > error captain

### standard users

	- add user test3 (in grp1, gst-grp2) > OK

	- mod test3 gecos > OK
	- mod test3 passwd > OK
	- mod test3 shell > OK

	- add test3 grp1 > OK
	- mod test3 grp1 > OK
	- del test3 grp1 > OK

	- add test3 cdrom > OK
	- del test3 cdrom > OK

	- lock test3 > OK
	- unlock test3 > OK

	- skel test3 > OK
	- del test3 > OK

	- add test5 > OK
	- massive del test5 > OK


### siblings

	- mod gecos testw2 > error even more powerful
	- mod passwd testw2 > error even more powerful
	- mod shell testw2 > error even more powerful

	- add testw2 grp1 > OK
	- mod testw2 grp1 > OK
	- del testw2 grp1 > OK

	- remove testw2 cdrom > OK
	- add testw2 cdrom > OK
	- remove testw2 licorn-wmi > error remove licorn-wmi

	- del testw2 > error even more
	- lock testw2 > error even more
	(CLI: mod user testw2 -l)
	- unlock testw2 > error even more
	- skel testw2 > error even more
	- massive del > error even more

	- add user test4 (in licorn-wmi) > OK
	- del user test4 > error even more

### more power (admins)

	- mod gecos testa1 > error even more
	- mod passwd testa1 > error even more
	- mod shell testa1 > error even more

	- add testa1 grp2 > error even more
	- mod testa1 grp1 > error even more
	- del testa1 grp1 > error even more

	- add testa1 cdrom > error even more
	- remove testa1 licorn-wmi > error even more

	- lock testw2 > error even more
	- skel testw2 > error even more
	- del testw2 > error even more
	- massive del > error even more

## Licorn® Full-time administrators (`admins`)

	- login testa1

### standard users

	- all like `licorn-wmi`

	- add test6 video > OK
	- del test6 video > OK

### `licorn-wmi` users

	- all like "standard users" for an admin account.

	- del test7 licorn-wmi > OK
	- massive del > OK

### Siblings

	- mod gecos testa2 > error even more powerful
	- mod passwd testa2 > error even more powerful
	- mod shell testa2 > error even more powerful

	- add testa2 grp1 > OK
	- mod testa2 grp1 > OK
	- del testa2 grp1 > OK

#### priv restricted
	- remove testa2 cdrom > OK
	- add testa2 cdrom > OK

#### restricted
	- add testa2 audio > OK
	- remove testa2 audio > OK

#### system priv
	- add testa2 licorn-wmi > OK
	- remove testa2 licorn-wmi > OK

	- del testa2 admins > error even more

	- del testa2 > error even more
	- lock testa2 > error even more
	(CLI: mod user testa2 -l)
	- unlock testa2 > error even more
	- skel testa2 > error even more
	- massive del > error even more

	- add user testa3 (in admins) > OK
	- del user testa3 > error even more

# check_groups()

## standard user

	- go to /groups/edit/licorn-wmi > 403
	- go to /groups/edit/admins > 403
	- go to /groups/edit/root > 403
	- go to /groups/edit/grp1 > 403
	- go to /groups/view/grp1 > 403

## `licorn-wmi` user


### Standard groups

	- add std group > OK
	- mod perm > OK
	- mod perm again > OK
	- mod perm massive > OK
	- mod perm massive again > OK
	- mod description > OK

	- add std {guest,member,resp} > OK
	- del std {guest,member,resp} > OK
	- add licorn-wmi {guest,member,resp} > OK
	- del licorn-wmi {guest,member,resp} > OK
	- add admins {guest,member,resp} > error insufficient
	- del admins {guest,member,resp} > error insufficient

	- del std group > OK

### Power groups

#### privileges

	- go to /groups/edit/licorn-wmi
		- mod description > error insufficient
		- add / del admins > error insufficient
		- add std member > OK
		- go to /groups/del/302 > error strongly not

#### system restricted

	- go to /groups/del/24 > error strongly not		(if add priv cdrom)
	- go to /groups/del/22 > error restricted

#### system non-restricted non-helpers

	- go to /groups/edit/acl
		- mod description > error non-helpers
		- add / del members > error non-helpers

#### helpers

	- go to /groups/edit/gst-grp1
		- mod description > error insufficient
		- add / del admins members > error admins
		- add / del standard / licorn-wmi members > OK
	- go to /groups/delete/305 > error not possible

## `admins` user
