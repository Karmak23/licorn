# this file makes the current directory a python package, and this is mandatory
# for the WMI app to be able to automatically import the event_handlers.py.

push_permissions = {
		# we have 'shares?' in urls.py. Hope this will work.
		'/share' : (lambda req: req.user.is_staff, (), ()),
	}

dependancies = ('LMC.extensions.simplesharing.enabled', )
base_url     = r'^shares?/'
