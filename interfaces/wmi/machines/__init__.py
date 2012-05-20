# this file makes the current directory a python package, and this is mandatory
# for the WMI app to be able to automatically import the event_handlers.py.

push_permissions = {
	'/machines': (lambda req: req.user.is_staff, (), None),
	}
