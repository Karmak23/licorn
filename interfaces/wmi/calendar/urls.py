from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('wmi.calendar.views',
	(r'^/?$', 'home'),
	(r'^users/(?P<uid>\d+)/(?P<action>\w+)/(?P<value>.*)/(?P<option>.*)$', "action"),
			
)
