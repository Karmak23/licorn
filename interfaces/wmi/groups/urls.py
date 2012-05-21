from django.conf.urls.defaults import *
from django.conf import settings

from licorn.foundations import hlstr

urlpatterns = patterns('groups.views',
    (r'^/?$', 'main'),

    (r'^edit/(?P<gid>\d+)/?$', 'group',  { 'action': 'edit' }),
    (r'^edit/(?P<name>%s)/?$' % hlstr.regex['group_name'][1:-1]  , 'group', {'action': 'edit'}),
    (r'^new/?$', 'group', { 'action': 'new' }),

    (r'^view/(?P<gid>\d+)/?$', 'view'),
    (r'^view/(?P<name>%s)/?$' % hlstr.regex['group_name'][1:-1]  , 'view'),

	(r'^mod/(?P<gid>\d+)/(?P<action>\w+)/(?P<value>.+)?$', 'mod'),

	(r'^create/?$', 'create'),

	(r'^delete/(?P<gid>\d+)/(?P<no_archive>.*)/?$', 'delete'),

	(r'^.*message/(?P<part>.+)/(?P<gid>\d+)?/?$', 'message'),

    (r'^massive/(?P<action>\w+)/(?P<gids>.+)/(?P<value>.*)/?$', 'massive'),


)
