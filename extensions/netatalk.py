# -*- coding: utf-8 -*-
"""
Licorn extensions: netatalk - http://docs.licorn.org/extensions/netatalk.html

:copyright: 2013 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os
import re

from licorn.foundations           import logging, events, settings
from licorn.foundations           import process, platform
from licorn.foundations.styles    import (stylize,
                                          ST_PATH, ST_NAME, ST_UGID,
                                          ST_OK)
from licorn.foundations.base      import ObjectSingleton
from licorn.foundations.classes   import ConfigFile
from licorn.foundations.constants import services, svccmds

from licorn.extensions            import ServiceExtension
from licorn.core.classes          import only_if_enabled
from licorn.core                  import LMC


class NetatalkExtension(ObjectSingleton, ServiceExtension):
    """

    ## TODO for v3.0

    admin group = @admins

    """

    def __init__(self):
        ServiceExtension.__init__(self,
                                  name='netatalk',
                                  service_name='netatalk',
                                  service_type=services.SYSV)

        # Paths are the same on Ubuntu and Debian.
        self.paths.sshd_config = '/etc/ssh/sshd_config'
        self.paths.pid_file    = '/var/run/afpd.pid'

    @property
    def path_daemon(self):
        if platform.is_debian_derivative:
            return u'/usr/sbin/afpd'

    @property
    def path_afpd_conf(self):

        return u'/etc/netatalk/afpd.conf'

    @property
    def afp_version(self):

        afp_output = process.execute((self.path_daemon, '-v'))[0]

        try:
            return afp_output.splitlines()[0].split()[1]

        except:
            logging.exception('BOUH!')
            return '<unknown>'

    @property
    def path_apple_volumes_default(self):

        return u'/etc/netatalk/AppleVolumes.default'

    def nothing(self):
        return

    def initialize(self):

        if os.path.exists(self.path_daemon):
            self.available = True

            self.configuration = ConfigFile(self.paths.sshd_config,
                                            separator=' ')
        else:
            logging.warning2(_(u'{0}: not available because {1} or {2} do '
                             u'not exist on the system.').format(
                             self.pretty_name,
                             stylize(ST_PATH, self.paths.sshd_binary)))

        return self.available

    def is_enabled(self):

        # TODO: implement disabler

        if not self.running(self.paths.pid_file):
            self.service(svccmds.START)

        logging.info(_(u'{0}: extension available on top of {1} version '
                     u'{2}, service currently {3}.').format(self.pretty_name,
                     stylize(ST_NAME, 'afpd'),
                     stylize(ST_UGID, self.afp_version),
                     stylize(ST_OK, _('enabled'))))

        # return must_be_running
        return True

    def check(self, batch=False, auto_answer=None):
        """ TODO: implement me. """

        #
        # TODO: default afpd.conf:
        # - -tcp -noddp -uamlist uam_guest.so,uams_dhx2_passwd.so \
        #   -nosavepassword
        #

        need_reload = False

        for group in LMC.groups:
            if group.is_standard and self.__add_group_conf(group,
                                                           with_reload=False):
                need_reload = True

        new_data = ''
        need_rewrite = False

        for line in open(self.path_apple_volumes_default).readlines():

            # We will wipe /home/groups/ANYTHING, provided ANYTHING
            # is not a group name, and not a multi-path. Eg
            # /home/groups/Time_Machine/Machine1 is valid, even if
            # “ Time_Machine ” is not a group. The purpose is to
            # keep Time Machine entries; did you guess it?
            offender = re.match(r'{0}/(?P<name>[^/]+)\s+'.format(
                                LMC.configuration.groups.base_path), line)

            logging.info('offender: %s' % (offender and offender.group('name') or ''))

            if offender and offender.group('name') not in LMC.groups.keys():
                # TODO: if not logging.ask_for_repair(_('Wipe bad entry?')):
                need_rewrite = True
                continue

            new_data += line

        if need_rewrite:
            #with open(self.path_apple_volumes_default, 'w') as f:
            #    f.write(new_data)
            logging.info('rewrite %s' % new_data)

        if need_reload or need_rewrite:
            self.service(svccmds.RELOAD)

        return True

    def enable(self, batch=False, auto_answer=None):

        self.check(batch=batch, auto_answer=auto_answer)

        self.service(svccmds.START)

        self.enabled = True

        return True

    def disable(self):

        self.service(svccmds.STOP)

        self.enabled = False

        return True

    def __del_group_conf(self, group, with_reload=True):

        new_data = ''
        need_rewrite = False

        for line in open(self.path_apple_volumes_default).readlines():
            if re.match(r'{0}\s+'.format(group.homeDirectory), line):
                need_rewrite = True
                continue

            new_data += line

        if need_rewrite:
            with open(self.path_apple_volumes_default, 'w') as f:
                f.write(new_data)

            if with_reload:
                self.service(svccmds.RELOAD)

        return need_rewrite

    def __add_group_conf(self, group, with_reload=True):

        need_rewrite = True

        for line in open(self.path_apple_volumes_default).readlines():
            if re.match(r'{0}\s+'.format(group.homeDirectory), line):
                need_rewrite = False

        if need_rewrite:
            with open(self.path_apple_volumes_default, 'a') as f:
                f.write('{0} "{1}" cnidscheme:dbd '
                        'allow:@{2},@{1},@rsp-{1}\n'.format(
                        group.homeDirectory, group.name,
                        settings.defaults.admin_group))

            if with_reload:
                self.service(svccmds.RELOAD)

        return need_rewrite

    @events.handler_method
    @only_if_enabled
    def group_post_add(self, *args, **kwargs):
        """ Add the new group configuration and reload the service. Only for
            standard groups. """

        group = kwargs.pop('group')

        if group.is_system:
            return

        return self.__add_group_conf(group)

    @events.handler_method
    @only_if_enabled
    def group_pre_del(self, *args, **kwargs):
        """ Remove the group configuration and reload the service. Only for
            standard groups. """

        group = kwargs.pop('group')

        if group.is_system:
            return

        return self.__del_group_conf(group)
