from django.conf.urls.defaults import *

urlpatterns = patterns(
    'wmi.calendar.views',

    (r'^/?$', 'home'),
    (r'^users/(?P<obj_id>\d+)/(?P<action>\w+)/(?P<value>.*)/(?P<option>.*)$',
        "action"),
    (r'^groups/(?P<obj_id>\d+)/(?P<action>\w+)/(?P<value>.*)/(?P<option>.*)$',
        "action"),
)
