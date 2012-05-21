from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('wmi.backup.views',
	(r'^/?(?:index)?/?$', 'index'),
	(r'^enable/(?P<device>[\w]+)/?$', 'enable'),
	(r'^eject/(?P<device>[\w]+)/?$', 'eject'),
	(r'^run/dialog?$', 'run_dialog'),
	(r'^run/?$', 'run'),
	(r'^rescan/?$', 'rescan'),
)
