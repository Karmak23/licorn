from django.conf.urls.defaults import *

urlpatterns = patterns('wmi.system.views',
	(r'^daemon/?$', 'daemon_status'),
	#(r'^config(?:uration)/?$', 'configuration'),
	(r'^download/(?P<filename>.+)/?$', 'download'),
	(r'^shutdown/all/cancel/?$', 'shutdown_all_cancel'),
	(r'^shutdown/all/?$', 'shutdown_all'),
	(r'^shutdown/cancel/?$', 'shutdown_cancel'),
	(r'^shutdown/?$', 'shutdown'),
	(r'^restart/all/?$', 'shutdown_all', {'reboot': True}),
	(r'^restart/?$', 'shutdown', {'reboot': True}),
)
