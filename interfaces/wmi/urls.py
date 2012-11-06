import os

from django.conf.urls.defaults import *
from django.conf               import settings
from django.http               import HttpResponseRedirect, HttpResponsePermanentRedirect

from libs.utils                import dynamic_urlpatterns

from licorn.core               import LMC

handler500 = 'wmi.system.views.error_handler'

js_info_dict = { 'domain': 'djangojs', 'packages': ('wmi',), }

urlpatterns = patterns('',

	# / and /test are special
	(r'^$', 'wmi.system.views.main'),
	(r'^reach/(?P<key>[\w]{8,8})/?$', 'wmi.system.views.reach'),

	# /favicon.ico doesn't exist in our well-organized world.
	(r'^media/favicon.ico$', lambda x: HttpResponsePermanentRedirect('/media/images/favicon.ico')),

    (r'^jsi18n/(?P<packages>\S+?)/$', 'django.views.i18n.javascript_catalog', js_info_dict),

	# in the WMI, we serve the media files too. This is not recommended by
	# Django documentation and developpers, but this is a small Management
	# Interface with an integrated web-server, not a big-balls high-trafic
	# website.
	(r'^media/(?P<path>.*)$', 'django.views.static.serve', {
				'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),

	# login / logout is handled by django, with out own template only
	(r'^login/?$', 'django.contrib.auth.views.login',
                                            {'template_name': 'login.html'}),
	(r'^logout/?$', 'wmi.app.logout'),

	# long-polling stream-like server-side-push
	(r'^setup/.*$', 'wmi.app.setup'),
	(r'^push/?$', 'wmi.app.push'),

	# static and minimal app routes (core apps)
	(r'^system/', include('wmi.system.urls')),
	(r'^(users|sys_users)/', include('wmi.users.urls')),
	(r'^groups/', include('wmi.groups.urls')),
)

# dynamic app routes, loaded only if all dependancies are satisfied.
for base_url, module_name in dynamic_urlpatterns(os.path.dirname(__file__)):
	urlpatterns += patterns('', (base_url, include('wmi.%s.urls' % module_name)))

for ext in LMC.extensions:
	if ext.enabled and hasattr(ext, '_wmi_urls'):
		for url_regex, view in ext._wmi_urls():
			urlpatterns += patterns('', (url_regex, view))

