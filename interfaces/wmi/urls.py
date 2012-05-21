from django.conf.urls.defaults import *
from django.conf               import settings
from django.http               import HttpResponseRedirect, HttpResponsePermanentRedirect

urlpatterns = patterns('',

	# / and /test are special
	(r'^$', 'wmi.system.views.index'),
	(r'^test/?$', 'wmi.system.views.test'),

	# /favicon.ico doesn't exist in our well-organized world.
	(r'^media/favicon.ico$', lambda x: HttpResponsePermanentRedirect('/media/images/favicon.ico')),

    (r'^jsi18n/(?P<packages>\S+?)/$', 'django.views.i18n.javascript_catalog'),

	# in the WMI, we serve the media files too. This is not recommended by
	# Django documentation and developpers, but this is a small Management
	# Interface with an integrated web-server, not a big-balls high-trafic
	# website.
	(r'^media/(?P<path>.*)$', 'django.views.static.serve', {
				'document_root': settings.MEDIA_ROOT, 'show_indexes':True}),

	# login / logout is handled by django, with out own template only
	(r'^login/?$', 'django.contrib.auth.views.login',
                                            {'template_name': 'login.html'}),
	(r'^logout/?$', 'wmi.app.logout'),

	# long-polling stream-like server-side-push
	(r'^setup/.*$', 'wmi.app.setup'),
	(r'^push/?$', 'wmi.app.push'),

	# app routes
	(r'^system/', include('wmi.system.urls')),
	(r'^users/', include('wmi.users.urls')),
	(r'^groups/', include('wmi.groups.urls')),
	(r'^machines/', include('wmi.machines.urls')),
	(r'^backups?/', include('wmi.backup.urls')),
	(r'^energy?/', include('wmi.energy.urls')),
)
