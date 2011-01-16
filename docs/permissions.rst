
.. permissions:

===================
Licorn® permissions
===================

Objects
=======

PermissionsController
	- instanciate before system/users/groups

PermissionProvider

PermissionChecker


Levels
======
																PROVIDER
anonymous			← True										system?? users??
authenticated		← system(pid) CLI, valid_user() WMI			users
granted				← users.user_grant(user, permission)		users
guest				← groups.member('gst-' + group)				groups
member				← groups.member(group)						groups
owner				← fsapi.owner() || users.is_self(user)		users?? system?? fsapi??
responsible			← groups.member('rsp-' + group)				groups
admin				← groups.member('admins')					groups



Permissions
===========

WMI_ACCESS??						← anonymous
WMI_VIEW							← authenticated
WMI_SYS_INFO_VIEW					← admin
SYSTEM_REMOTE_LOGIN					← member('remotessh')

GROUPS_ADMIN								← admin
	↳ GROUPS_ADD
	↳ GROUPS_DELETE
	↳ GROUPS_MODIFY
		↳ GROUPS_MODIFY_MEMBERS				← responsible
			↳ GROUPS_ADD_MEMBERS
			↳ GROUPS_DELETE_MEMBERS
				↳ GROUPS_VIEW_MEMBERS		← member
	↳ GROUPS_CHECK							← member
	↳ GROUPS_VIEW							← authenticated

USERS_ADMIN									← admin
	↳ USERS_ADD								← admin
	↳ USERS_DELETE							← admin
	↳ USERS_MODIFY							← admin
		↳ USERS_MODIFY_RESTRICTED_DETAILS	← admin
			↳ USERS_MODIFY_PASSWORD			← owner
			↳ USERS_MODIFY_PUBLIC_DETAILS	← owner
			↳ USERS_GRANT_STATUS_VIEW??		← owner
		↳ USERS_MODIFY_PUBLIC_DETAILS		← owner
	↳ USERS_STATUS_VIEW??					← granted
	↳ USERS_CHECK							← owner
	↳ USERS_VIEW							← authenticated

BACKUP_ADMIN						← admin
BACKUP_VIEW							← authenticated
BACKUP_VIEW_CONTENT					← owner
BACKUP_SEARCH						← ??
BACKUP_RESTORE						← admin
BACKUP_RESTORE_CONTENT				← owner

MACHINES_VIEW						← authenticated
MACHINES_DETAILS_VIEW				← owner
