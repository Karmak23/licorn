# this file makes the current directory a python package, and this is mandatory
# for the WMI app to be able to automatically import the event_handlers.py.

push_permissions = {
	# base URL			returns True/False					when True					when False
	#																					None means 'Forbidden',
	#																					'()' means 'no collector'
	'/'              : (lambda req: req.user.is_staff, 		('ramswap','avg_loads'), 	()),
	'/system/daemon' : (lambda req: req.user.is_superuser, 	('daemon_status', ), 		None),
}
