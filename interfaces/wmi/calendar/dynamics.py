# -*- coding: utf-8 -*-
"""
Licorn WMI3 calendar dynamics

:copyright:
    * 2012 Robin Lucbernet <robin@meta-it.fr>

:license: GNU GPL version 2
"""
# django imports
from django.template.loader import render_to_string

# licorn imports
from licorn.foundations import cache, exceptions
from licorn.core import LMC
from licorn.interfaces.wmi.libs import utils
from licorn.interfaces.wmi.users.views import generate_tab_content
from licorn.foundations.constants import filters
from licorn.extensions.caldavd import LDAP_BACKEND, XML_BACKEND

# calendarserver internals
from calendarserver.tools.principals import principalForPrincipalID, getProxies


@cache.cached(cache.five_minutes)
def enabled():

    try:
        return LMC.extensions.caldavd.enabled

    except AttributeError:
        return False


def dynamic_sidebar(request):
    if enabled():

        # check licorn backends
        shadow_backend = LMC.backends.guess_one('shadow')
        try:
            # openLDAP may not be installed
            ldap_backend = LMC.backends.guess_one('openldap')
        except exceptions.DoesntExistException:
            ldap_backend = None

        # first, we need to check that the user could have a calendar
        # (is he/she stored in the same backend than caldav ?)
        user = LMC.users.guess_one(request.user.username)
        if (user.backend.name == shadow_backend.name and
            LMC.extensions.caldavd.calendarserver_backend == XML_BACKEND) or \
            (ldap_backend is not None and
                user.backend.name == ldap_backend.name and
                LMC.extensions.caldavd.calendarserver_backend == LDAP_BACKEND):

            return render_to_string('calendar/parts/sidebar.html', {})

    return ''


def get_users_principals(do_not_include):

    up = []

    for u in LMC.users.select(filters.STANDARD):
        if u.login not in do_not_include:
            p = principalForPrincipalID('users:' + u.login)
            if p:
                up.append(p)

    return up


def dynamic_users_tab(users, mode):

    if mode not in ('new', "massiv"):

        user = users[0]

        # check licorn backends
        shadow_backend = LMC.backends.guess_one('shadow')
        try:
            # openLDAP may not be installed
            ldap_backend = LMC.backends.guess_one('openldap')
        except exceptions.DoesntExistException:
            ldap_backend = None

        # first, we need to check that the user could have a calendar
        # (is he/she stored in the same backend than caldav ?)
        if (user.backend.name == shadow_backend.name and
            LMC.extensions.caldavd.calendarserver_backend == XML_BACKEND) or \
            (ldap_backend is not None and
                user.backend.name == ldap_backend.name and
                LMC.extensions.caldavd.calendarserver_backend == LDAP_BACKEND):

            # get user principal
            principal_user = principalForPrincipalID('users:' + user.login)
            # get its proxies
            proxies = utils.my_deferred_blocker(getProxies(principal_user))

            read_proxies = [principalForPrincipalID(p) for p in proxies[0]]
            write_proxies = [principalForPrincipalID(p) for p in proxies[1]]

            do_not_include = [user.login]
            for t in [str(p).split(')')[1] for p in read_proxies]:
                do_not_include.append(t)

            for t in [str(p).split(')')[1] for p in write_proxies]:
                do_not_include.append(t)

            content = render_to_string(
                '/calendar/parts/user_calendar_content.html', {
                    'user': user,
                    'read_proxies': read_proxies,
                    'write_proxies': write_proxies,
                    'users_principals': get_users_principals(
                        do_not_include=do_not_include),
                    'base_url_action': "/calendar/users/" +
                    str(user.uidNumber),
                }
            )

            return [
                {
                    'id': 'calendar',
                    'title': 'Calendar',
                    'content': generate_tab_content('calendar', content)
                }
            ]
        else:
            return []
    else:
        return []


def dynamic_groups_tab(groups, mode):

    if mode not in ('new', "massiv"):

        group = groups[0]

        # get group principal
        principal_group = principalForPrincipalID(
            'resources:resource_' + group.name)
        # get its proxies
        proxies = utils.my_deferred_blocker(getProxies(principal_group))

        read_proxies = [principalForPrincipalID(p) for p in proxies[0]]
        write_proxies = [principalForPrincipalID(p) for p in proxies[1]]

        do_not_include = []
        for t in [str(p).split(')')[1] for p in read_proxies]:
            do_not_include.append(t)

        for t in [str(p).split(')')[1] for p in write_proxies]:
            do_not_include.append(t)

        content = render_to_string(
            '/calendar/parts/group_calendar_content.html', {
                'group': group,
                'read_proxies': read_proxies,
                'write_proxies': write_proxies,
                'users_principals': get_users_principals(
                    do_not_include=do_not_include),
                'base_url_action': "/calendar/groups/" + str(group.gidNumber),
            }
        )

        return [
            {
                'id': 'calendar',
                'title': 'Calendar',
                'content': generate_tab_content('calendar', content)
            }
        ]

    else:
        return []
