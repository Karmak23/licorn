from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('wmi.shares.views',
	(r'^/?(?:index)?/?$', 'index'),

	# public views need login + share name
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/?$', 'serve'),
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/(?P<filename>[^/]+)/?$', 'download'),
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/\+upload/(?P<filename>[^/]+)/?$', 'upload'),

	# management don't need the login, it's taken from the request
	(r'^(?P<shname>[^/]+)/password/(?P<newpass>[^/]+)/?$', 'password'),
	(r'^(?P<shname>[^/]+)/accepts_uploads/?$', 'accepts_uploads'),
	(r'^enable/?$', 'enable'),
	(r'^disable/?$', 'disable'),

	#(r'^enable/(?P<share>[\w]+)/?$', 'enable'),
	#(r'^disable/(?P<share>[\w]+)/?$', 'disable'),

	#(r'^add/?$', 'enable'),
	#(r'^delete/?$', 'eject'),
	#(r'^run/?$', 'run'),
)
