add priv cdrom
add group grp1,grp2
add user tests --system
add user testw1,testw2 -G licorn-wmi,cdrom,audio
add user testa1,testa2 -G admins,grp1

# check_users()

## Standard users

### On myself

	- mod gecos > OK
	- mod shell > OK
	- mod password > OK
	- go to /users/mod/1003/lock/ > error captain + log
	- go to /users/mod/1003/unlock/ > error insufficient own + log
	- go to /users/mod/1003/groups/300/1 > error insufficient own + log
	- go to /users/mod/1003/groups/300/1 > error insufficient own + log

	- view groups > 403

### On others

	- go to /users > 403
	- go to /users/view/root > 403
	- go to /users/edit/root > 403
	- go to /users/delete/0 > 403
	- go to /users/mod/0/lock > error not allowed + log
	- go to /users/mod/0/gecos/test > error not allowed + log
	- go to /users/mod/0/password/test > error not allowed + log
	- go to /users/mod/0/groups/10000/1 > error not allowed + log

	- go to /users/view/tests > 403
	- go to /users/edit/tests > 403
	- go to /users/delete/300 > 403
	- go to /users/mod/300/lock > error not allowed + log
	- go to /users/mod/300/unlock > error not allowed + log
	- go to /users/mod/300/gecos/test > error not allowed + log
	- go to /users/mod/300/password/test > error not allowed + log
	- go to /users/mod/300/groups/10000/1 > error not allowed + log

	- go to /users/view/testw1 > 403
	- go to /users/edit/testw1 > 403
	- go to /users/delete/1001 > 403
	- go to /users/mod/1001/lock > error insufficient + log
	- go to /users/mod/1001/unlock > error insufficient + log
	- go to /users/mod/1001/gecos/test > error insufficient + log
	- go to /users/mod/1001/password/test > error insufficient + log
	- go to /users/mod/1001/groups/10000/1 > error insufficient + log

	- go to /users/view/testa1 > 403
	- go to /users/edit/testa1 > 403
	- go to /users/delete/1003 > 403
	- go to /users/mod/1001/lock > error insufficient + log
	- go to /users/mod/1001/gecos/test > error insufficient + log
	- go to /users/mod/1001/groups/10000/1 > error insufficient + log

## Licorn® manager (licorn-wmi)

### On myself

	- mod gecos > OK
	- mod passwd > OK
	- mod shell > OK

	- add me {gst,grp1,rsp} > OK
	- mod me grp1 > OK
	- del me grp1 > OK

	- del me licorn-wmi > error remove from privilege
	- del me cdrom / remotessh > OK
	- del me audio > not visible
		- go to /users/mod/1001/groups/29/0 > error system restricted

	- del me > error captain
	- lock me > error lock me
	- apply skel > OK
	- massive del > error captain

### On standard users

	- add user test3 (in grp1, gst-grp2) > OK

	- mod test3 gecos > OK
	- mod test3 passwd > OK
	- mod test3 shell > OK

	- add test3 grp1 > OK
	- mod test3 grp1 > OK
	- del test3 grp1 > OK

	(CLI: add priv cdrom)
	- add test3 cdrom > OK
	- del test3 cdrom > OK

	- lock test3 > OK
	- unlock test3 > OK

	- skel test3 > OK
	- del test3 > OK

	- add test5 > OK
	- massive del test5 > OK


### On pre-siblings

	- add test6 > OK
	- add test6 cdrom > OK
	- add test6 licorn-wmi > OK
	- del test6 cdrom > OK
	- del test6 licorn-wmi > error manager
	- del test6 > error manager

### On siblings

	- mod gecos testw2 > error manager
	- mod passwd testw2 > error manager
	- mod shell testw2 > error manager

	- add testw2 {gst,grp1,rsp} > OK
	- mod testw2 grp1 > OK
	- del testw2 grp1 > OK

	- remove testw2 cdrom > OK
	- add testw2 cdrom > OK
	- remove testw2 licorn-wmi > error manager

	- lock testw2 > error manager
	(CLI: mod user testw2 -l)
	- unlock testw2 > error manager
	- del testw2 > error manager
	- skel testw2 > error manager
	- massive del > error manager

	- add user test4 (in licorn-wmi) > OK
	- del user test4 > error manager

### On administrators

	- mod gecos testa1 > error administrator
	- mod passwd testa1 > error administrator
	- mod shell testa1 > error administrator

	- add testa1 grp2 > error administrator
	- mod testa1 grp1 > error administrator
	- del testa1 grp1 > error administrator

	- add testa1 cdrom > error administrator
	- remove testa1 licorn-wmi > error administrator

	- lock testw2 > error administrator
	- skel testw2 > error administrator
	- del testw2 > error administrator
	- massive del > error administrator
	- massive skel > error administrator

### On specials

	- go to /users/edit/root
		- change gecos > error restricted
		- change passwd > error restricted
		- change shell > error restricted
		- add / del {guest,member,resp} > error restricted
		- add / del privilege > error restricted

	(CLI: add user "tests" --system)
	- go to /users/edit/tests
		- change gecos > error system
		- change passwd > error system
		- change shell > error system
		- add / del {guest,member,resp} > error system
		- add / del privilege > error system

## Licorn® Full-time administrators (`admins`)

	- login testa1

### On myself

	- mod gecos > OK
	- mod passwd > OK
	- mod shell > OK

	- add me {gst,grp1,rsp} > OK
	- mod me grp1 > OK
	- del me grp1 > OK

	- del me licorn-wmi > OK
	- add me licorn-wmi > OK
	- add / del me cdrom / remotessh > OK
	- add / del me audio > OK
	- del me admins > error insufficient + CLI

	- del me > error captain
	- lock me > error lock me
	- apply skel > OK
	- massive del > error captain

### On standard users

	- all like `licorn-wmi`

	- add user / manager video > OK
	- del user / manager video > OK

### On managers

	- all like "standard users" for an admin account.

	- del test7 licorn-wmi > OK
	- massive del > OK

### On pre-sibling

	- add user testa3 (in admins) > OK
	- del user testa3 > error insufficient + CLI
	- del user testa3 admins > error insufficient + CLI

### On siblings

	- mod gecos testa2 > error insufficient + CLI
	- mod passwd testa2 > error insufficient + CLI
	- mod shell testa2 > error insufficient + CLI

	- add testa2 {gst,grp1,rsp} > OK
	- mod testa2 grp1 > OK
	- del testa2 grp1 > OK

	- add / del testa2 cdrom > OK
	- add / del testa2 licorn-wmi > OK
	- add / del testa2 audio > OK

	- del testa2 admins > error insufficient + CLI

	- del testa2 > error insufficient + CLI
	- massive del > error insufficient + CLI

# check_groups()

## From a standard user

	- go to /groups/ > 403
	- go to /groups/edit/licorn-wmi > 403
	- go to /groups/edit/admins > 403
	- go to /groups/edit/root > 403
	- go to /groups/edit/grp1 > 403
	- go to /groups/view/grp1 > 403

	- go to /groups/mod/0/* > 403
	- go to /groups/mod/300/* > 403
	- go to /groups/mod/10000/* > 403

## From a manager

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

	- restricted / system members
		- /groups/mod/10000/users/300/2 > error system
		- /groups/mod/10000/users/300/0 > error system
		- /groups/mod/10000/users/0/2 > error restricted
		- /groups/mod/10000/users/0/0 > error restricted

### Power groups

#### privileges

	- go to /groups/edit/licorn-wmi
		- mod description > error insufficient
		- add / del admins > error insufficient
		- add std member > OK
		- go to /groups/delete/302 > error strongly not

#### system restricted

	- go to /groups/delete/24 > error strongly not		(if add priv cdrom)
	- go to /groups/delete/22 > error restricted

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

### Standard groups

	- idem `licorn-wmi`

### Power groups

#### privileges

	- go to /groups/edit/licorn-wmi
		- mod description > OK
		- add / del std member > OK
		- add / del licorn-wmi users > OK
		- add / del admins > OK
		- go to /groups/delete/302 > error strongly not

#### system non-restricted non-helpers

	- go to /groups/edit/acl
		- mod description > OK
		- add / del members > OK
		- add / del licorn-wmi users > OK
		- add / del admins > OK
		- go to /groups/delete/300 > strongly not

#### helpers

	- go to /groups/edit/gst-grp1
		- mod description > OK
		- add / del admins members > OK
		- add / del standard / licorn-wmi members > OK
	- go to /groups/delete/305 > error strongly not

#### system restricted

	- go to /groups/delete/24 > error strongly not + CLI
	- go to /groups/delete/22 > error strongly not + CLI
