from django.conf.urls.defaults import *
from django.conf import settings

from licorn.foundations import hlstr

urlpatterns = patterns('machines.views',
    (r'^/?$', 'main'),
    (r'^scan/?$', 'scan'),
    # NOT YET READY FOR MACHINES
    #(r'^view/(?P<mid>\d+)/?$', 'view'),
    #(r'^view/(?P<hostname>%s)/?$' % hlstr.regex['login'][1:-1]  , 'view', {'semantic': True}),
    )
