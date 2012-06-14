from django.conf.urls.defaults import *
from django.conf import settings

from licorn.foundations import hlstr

urlpatterns = patterns('users.views',
    (r'^/?$', 'main'),

    (r'^.*message/(?P<part>.+)/(?P<uid>\d+)?/?$', 'message'),

    (r'^new/?$', 'user', { 'action': 'new' }),

    (r'^edit/(?P<uid>\d+)/?$', 'user',  { 'action': 'edit' }),
    (r'^edit/(?P<login>%s)/?$' % hlstr.regex['login'][1:-1]  , 'user', {'action': 'edit'}),

    (r'^create/?$', 'create'),

    (r'^delete/(?P<uid>\d+)/(?P<no_archive>.*)/?$', 'delete'),

    (r'^view/(?P<uid>\d+)/?$', 'view'),
    (r'^view/(?P<login>%s)/?$' % hlstr.regex['login'][1:-1]  , 'view', {'semantic': True}),

	# consider this one as a replacement for mod* and use only the 'value' argument
	#     (r'^mod/(?P<uid>\d+)/(?P<action>\w+)/(?P<value>.+)$', 'mod'),
	(r'^mod/(?P<uid>\d+)/(?P<action>\w+)/(?P<value>.*)$', 'mod'),
    #(r'^mod/(?P<uid>\d+)/gecos/(?P<gecos>%s)$' % hlstr.regex['description'][1:-1] , 'mod', {'action': 'gecos'}),
    #(r'^mod/(?P<uid>\d+)/password/(?P<pwd>.+)$', 'mod', {'action': 'password'}),
    #(r'^mod/(?P<uid>\d+)/shell/(?P<shell>.+)$', 'mod', {'action': 'shell'}),
    #(r'^mod/(?P<uid>\d+)/groups/(?P<groups>.*)$', 'mod', {'action': 'groups'}),
    #(r'^mod/(?P<uid>\d+)/skel/(?P<skel>.+)/?$', 'mod', {'action': 'skel'}),
    #(r'^mod/(?P<uid>\d+)/lock/?$', 'mod', {'action': 'lock'}),
    #(r'^mod/(?P<uid>\d+)/unlock/?$', 'mod', {'action': 'unlock'}),

	# consider (?:\d,?)+ as RE for P<uids>

    (r'^massive/delete/(?P<uids>[,\d]+)/(?P<no_archive>.*)/?$', 'massive', {'action': 'delete'}),
    (r'^massive/skel/(?P<uids>[,\d]+)/(?P<skel>.*)/?$', 'massive', {'action': 'skel'}),
    (r'^massive/export/(?P<uids>[,\d]+)(?:/(?P<type>.*))?/?$', 'massive', {'action': 'export'}),

    (r'^import/(?P<confirm>.*)/?$', 'import_view'),
    (r'^upload/?$', 'upload_file'),

    (r'^check_pwd_strenght/(?P<pwd>.+)/?$', 'check_pwd_strenght'),
    (r'^generate_pwd/?$', 'generate_pwd'),
    )
