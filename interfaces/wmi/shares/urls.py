from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('wmi.shares.views',
	(r'^/?(?:index)?/?$', 'index'),
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/?$', 'serve'),
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/(?P<filename>[^/]+)/?$', 'download'),
	(r'^(?P<login>[^/]+)/(?P<shname>[^/]+)/\+upload/(?P<filename>[^/]+)/?$', 'upload'),
	(r'^enable/?$', 'enable'),
	(r'^disable/?$', 'disable'),

	#(r'^enable/(?P<share>[\w]+)/?$', 'enable'),
	#(r'^disable/(?P<share>[\w]+)/?$', 'disable'),

	#(r'^add/?$', 'enable'),
	#(r'^delete/?$', 'eject'),
	#(r'^run/?$', 'run'),
)
