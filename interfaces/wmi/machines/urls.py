from django.conf.urls.defaults import *
from django.conf import settings

from licorn.foundations import hlstr

urlpatterns = patterns('machines.views',
    (r'^/?$', 'main'),
    (r'^scan/?$', 'scan'),

    (r'^edit/(?P<mid>.+)/?$', 'edit'),

    (r'^instant_edit/(?P<mid>.+)/(?P<part>.+)/(?P<value>.+)/?$', 'instant_edit'),


	(r'^upgrade/(?P<mid>.+)/?$', 'upgrade'),
	(r'^massive_select_template/(?P<action_name>.+)/(?P<mids>.+)/?$', 'massive_select_template'),



    # NOT YET READY FOR MACHINES
    #(r'^view/(?P<mid>\d+)/?$', 'view'),
    #(r'^view/(?P<hostname>%s)/?$' % hlstr.regex['login'][1:-1]  , 'view', {'semantic': True}),
    )
