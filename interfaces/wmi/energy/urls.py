from django.conf.urls.defaults import *
from django.conf import settings

from licorn.foundations import hlstr

urlpatterns = patterns('energy.views',
    (r'^/?$', 'policies'),
    (r'^policies/?$', 'policies'),

    (r'^add_rule/(?P<who>.*)/(?P<hour>.*)/(?P<minute>.*)/(?P<day>.*)/?$', 'add_rule',  {'new': False}),
    (r'^del_rule/(?P<tid>.*)/?$', 'del_rule'),

    (r'^get_recap/?$', 'get_recap'),
    (r'^get_calendar_data/?$', 'get_calendar_data'),
    (r'^generate_machine_html/(?P<mid>.*)/?$', 'generate_machine_html'),
    (r'^get_machine_list/?$', 'get_machine_list'),

)
