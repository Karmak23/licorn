from django.conf.urls.defaults import *
from django.conf import settings

from licorn.foundations import hlstr

urlpatterns = patterns('groups.views',
    (r'^/?$', 'main'),

    (r'^edit/(?P<gid>\d+)/?$', 'group',  { 'action': 'edit' }),
    (r'^edit/(?P<name>%s)/?$' % hlstr.regex['group_name'][1:-1]  , 'group', {'action': 'edit'}),
    (r'^new/?$', 'group', { 'action': 'new' }),

	(r'^mod/(?P<gid>\d+)/(?P<action>\w+)/(?P<value>.+)?$', 'mod'),

	(r'^create/?$', 'create'),
    (r'^hotkeys_help/?$', 'hotkeys_help'),

	(r'^delete/(?P<gid>\d+)/(?P<no_archive>.*)/?$', 'delete'),

    (r'^massive/(?P<action>\w+)/(?P<gids>[^/]+)/(?P<value>.*)/?$', 'massive'),
    (r'^massive_select_template/(?P<action_name>.+)/(?P<gids>.+)/?$', 'massive_select_template'),



)
