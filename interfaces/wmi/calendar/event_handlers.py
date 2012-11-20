# -*- coding: utf-8 -*-

from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from licorn.interfaces.wmi.libs import utils

from calendarserver.tools.principals import principalForPrincipalID


def calendar_add_proxie_handler(request, event):

    try:
        user = event.kwargs['user']
    except KeyError:
        user = None
        group = event.kwargs['group']
        if group.is_guest or group.is_responsible:
            group = group.standard_group

    proxy = event.kwargs['user_proxy']
    mode = event.kwargs['proxy_type']

    if user is not None:
        yield utils.notify(
            _("User <strong><em>{0}</strong></em> is now a {2} of "
                "<strong><em>{1}</strong></em>'s calendar".format(
                    proxy.login,
                    user.login,
                    "writer" if mode == 'write' else "reader")))
    else:
        yield utils.notify(
            _("User <strong><em>{0}</strong></em> is now a {2} of "
                "<strong><em>{1}</strong></em>'s calendar".format(
                    proxy.login,
                    group.name,
                    "writer" if mode == 'write' else "reader")))

    # add the new proxy to the correct list
    yield utils.format_RPC_JS(
        'update_instance',
        'readers_proxy' if mode == 'read' else 'writers_proxy',
        proxy.login,
        render_to_string(
            '/calendar/parts/table_row.html', {
                'proxy': proxy,
                'mode': mode,
                'avalaible_list': False,
            }
        ),
        'setup_calendar_row'
    )
    # remove the proxy from avalaible proxies
    yield utils.format_RPC_JS(
        'remove_instance',
        'avalaible_proxies',
        proxy.login,
        ("<tr class='no-data'><td><em>No <strong>avalaible</strong> calendar "
            "for the moment</em></td></tr>")
    )


def calendar_del_proxie_handler(request, event):
    try:
        user = event.kwargs['user']
    except KeyError:
        user = None
        group = event.kwargs['group']
        if group.is_guest or group.is_responsible:
            group = group.standard_group

    proxy = event.kwargs['user_proxy']
    mode = event.kwargs['proxy_type']

    if user is not None:
        yield utils.notify(
            _("User <strong><em>{0}</strong></em> is no more {2} of "
                "<strong><em>{1}</em></strong>'s calendar").format(
                    proxy.login, user.login,
                    "writer" if mode == 'write' else "reader"))
    else:
        yield utils.notify(
            _("User <strong><em>{0}</strong></em> is no more {2} of "
                "<strong><em>{1}</strong></em>'s calendar").format(
                    proxy.login, group.name,
                    "writer" if mode == 'write' else "reader"))

    yield utils.format_RPC_JS(
        'remove_instance',
        'readers_proxy' if mode == 'read' else 'writers_proxy',
        proxy.login,
        "<tr class='no-data'><td><em>{0}</em></td></tr>".format(
            _('No <strong>{0}</strong> for the moment').format(
                "writer" if mode == 'write' else "reader"))
    )

    # add the proxy to the avalaible proxies list
    yield utils.format_RPC_JS(
        'update_instance',
        'avalaible_proxies',
        proxy.login,
        render_to_string('/calendar/parts/user_button.html', {
            'avalaible_items': {
                        'title' : _('Manage permissions'),
                        'no_data_text':  _('No <strong>user avalaible</strong> for the moment.'),
                        'list': [ principalForPrincipalID("users:"+proxy.login) ],
                        'states': [
                            {
                                'title': "Reader",
                                'class': "btn-success",
                                'base_url_action': "/calendar/users/"+str(proxy.uidNumber)+"/add/{0}/read"
                            },
                            {
                                'title': "Writer",
                                'class': "btn-primary",
                                'base_url_action': "/calendar/users/"+str(proxy.uidNumber)+"/add/{0}/write"
                            }
                        ]
                    },
            'mode': mode,
            'avalaible_list': True,
        }),
        "setup_avalaible_proxies"
    )
