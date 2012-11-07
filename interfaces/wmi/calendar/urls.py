from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('wmi.calendar.views',
	(r'^/?$', 'home'),
	(r'^users/(?P<obj_id>\d+)/(?P<action>\w+)/(?P<value>.*)/(?P<option>.*)$', "action"),
	(r'^groups/(?P<obj_id>\d+)/(?P<action>\w+)/(?P<value>.*)/(?P<option>.*)$', "action"),
			
)
