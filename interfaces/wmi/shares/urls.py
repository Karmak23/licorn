from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('wmi.shares.views',

	# WMI share listing
	(r'^/?(?:index)?/?$', 'index'),

	# Management don't need the user login in request path,
	# it's auto-extracted from `request.user.username`.
	(r'^(?P<shname>[^/]+)/password/(?P<newpass>[^/]*)/?$', 'password'),
	(r'^(?P<shname>[^/]+)/\+check/?$', 'check_share'),
	(r'^(?P<shname>[^/]+)/accepts_uploads/?$', 'accepts_uploads'),
	(r'^enable/?$', 'enable'),
	(r'^disable/?$', 'disable'),

	# Public views need login + share name in the request path
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/?$', 'serve'),
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/\+upload/?$', 'upload'),
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/(?P<filename>[^/]+)/?$', 'download'),

	# not implemented
	#(r'^enable/(?P<share>[\w]+)/?$', 'enable'),
	#(r'^disable/(?P<share>[\w]+)/?$', 'disable'),
	#(r'^add/?$', 'add'),
	#(r'^delete/?$', 'delete'),
)
