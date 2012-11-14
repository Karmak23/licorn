# -*- coding: utf-8 -*-
"""
Licorn extensions: caldavd - http://docs.licorn.org/extensions/caldavd.html

:copyright:
    * 2010 Olivier Cortès <oc@meta-it.fr>
    * 2010-2012 Guillaume Masson <guillaume.masson@meta-it.fr>
    * 2012 Robin Lucbernet <robin@meta-it.fr>

:license: GNU GPL version 2

"""

###############################################################################
# extensions.caldavd imports
###############################################################################

# import python modules
import os
import uuid
import types
import functools

# import caldavd internals
from traceback import print_exc
import xml.etree.ElementTree as ET
from calendarserver.tools.principals import action_addProxy, getProxies, \
    action_removeProxy, principalForPrincipalID
from calendarserver.tools.util import getDirectory, loadConfig, setupMemcached
from twistedcaldav.config import config as caldav_config
from twistedcaldav.config import ConfigDict

# import from licorn
from licorn.foundations.styles import *
from licorn.foundations.ltraces import *
from licorn.foundations.events import LicornEvent
from licorn.foundations import logging, fsapi, readers, writers, events, exceptions
from licorn.foundations.workers import workers
from licorn.foundations.base import ObjectSingleton, LicornConfigObject
from licorn.foundations.constants import distros, services, svccmds, \
    priorities, filters
from licorn.core.classes import only_if_enabled
from licorn.core import LMC
from licorn.extensions import ServiceExtension

# Directory service constants
XML_BACKEND = "twistedcaldav.directory.xmlfile.XMLDirectoryService"
LDAP_BACKEND = "twistedcaldav.directory.ldapdirectory.LdapDirectoryService"

# default users calendar password
# Used when create a calendar for an already existing user
GENERIC_PWD = "calendar_user"

###############################################################################
# Helpers
###############################################################################


def my_Configdict2xmlEtree(_dict):
    """ Map a dict object into xml """

    # create the XML dict element
    xml_dict = ET.Element('dict')

    for k, v in _dict.iteritems():
        # create the key element, and append it to the dict
        elem = ET.Element('key')
        elem.text = k
        xml_dict.append(elem)

        # NOTE : PEP8 say : use isinstance() instead of type()
        # But be carrefull, instance(True, types.Integer) = True

        # create the value element depending on type(value)
        if isinstance(v, types.StringTypes):
            elem_value = ET.Element('string')
            elem_value.text = v

        elif isinstance(v, types.BooleanType):
            if v:
                elem_value = ET.Element('true')
            else:
                elem_value = ET.Element('false')

        elif isinstance(v, types.IntType):
            elem_value = ET.Element('integer')
            elem_value.text = str(v)

        elif isinstance(v, types.NoneType):
            elem_value = ET.Element('string')

        elif isinstance(v, ConfigDict) or isinstance(v, types.DictType):
            elem_value = my_Configdict2xmlEtree(v)

        xml_dict.append(elem_value)

    return xml_dict


def only_if_backend_openldap_is_not_enabled(func):
    """ Event decorator. Run the method only if the 'openldap' backend
        is not enabled.
    """

    @functools.wraps(func)
    def decorated(self, *args, **kwargs):

        if not LMC.backends.guess_one('openldap').enabled:
            return func(self, *args, **kwargs)

    return decorated


###############################################################################
# CaldavdExtension class
###############################################################################

class CaldavdExtension(ObjectSingleton, ServiceExtension):
    """ Handles Apple Calendar Server configuration and service.

        How it works ?
            -> if licornd's backend is OpenLDAP :
                - users are stored in LDAP
                - a ressource for each group stored in resources.xml file


            -> if licornd's backend is SHADOW:
                - users and resources are stored in xml files

        How to use ?
            -> nothing to do, calendars are automaticaly created for each
            groups and users if they are stored in the right backend.

            -> groups members can automaticaly read or write into group's
            calendar (guests=read-only; members/responsibles=read-write)

        .. versionadded:: 1.2.4
        .. versionmodified:: 1.7. Rework the extension to handle calendarserver
            3.2

    """
    def __init__(self):
        assert ltrace_func(TRACE_EXTENSIONS)

        ServiceExtension.__init__(
            self,
            name='caldavd',
            service_name='calendarserver',

            # On Debian, always SYSV. On Ubuntu, this a community package
            # which uses the "old" SYSV service mechanism.
            service_type=services.SYSV,
            service_long=True
        )

        # nothing to do on the client side.
        self.server_only = True

        # users and groups can get calendars.
        self.controllers_compat = ['users', 'groups']

        self.paths.main_dir = '/etc/caldavd'
        self.paths.accounts = self.paths.main_dir + '/accounts.xml'
        self.paths.resources = self.paths.main_dir + '/resources.xml'
        self.paths.configuration = self.paths.main_dir + '/caldavd.plist'
        self.paths.sudoers = self.paths.main_dir + '/sudoers.plist'
        self.paths.pid_file = '/var/run/caldavd/caldavd.pid'

        self.data = LicornConfigObject()

        if LMC.configuration.distro in (distros.UBUNTU, distros.LICORN,
                                        distros.DEBIAN):
            self.paths.defaults = '/etc/default/calendarserver'

        # create default directoryservice config for ldap and xml backends
        self.default_config = LicornConfigObject()

        try:
            # openLDAP may not be installed
            ldap_backend = LMC.backends.guess_one('openldap')
        except exceptions.DoesntExistException:
            ldap_backend = None

        if ldap_backend is not None:
            self.default_config.ldap_directory = {
                'type': LDAP_BACKEND,
                'params': {
                    'tls': False,
                    'restrictToGroup': '',
                    'resourceSchema': {
                        'autoScheduleEnabledValue': 'yes',
                        'resourceInfoAttr': '',
                        'readOnlyProxyAttr': '',
                        'proxyAttr': '',
                        'autoScheduleAttr': ''
                    },
                    'restrictEnabledRecords': False,
                    'groupSchema': {
                        'memberIdAttr': '',
                        'nestedGroupsAttr': '',
                        'membersAttr': 'memberUid'
                    },
                    'uri': '{0}'.format(LMC.backends.openldap.uri),
                    'tlsRequireCert': 'never',
                    'rdnSchema': {
                        'users': {
                            'emailSuffix': '',
                            'attr': 'uid',
                            'calendarEnabledAttr': '',
                            'mapping': {
                                'recordName': 'cn',
                                'lastName': 'sn',
                                'fullName': 'gecos',
                                'emailAddresses': 'mail',
                                'firstName': 'givenName'
                            },
                            'filter': '',
                            'calendarEnabledValue': 'yes',
                            'loginEnabledAttr': '',
                            'rdn': 'ou=People',
                            'loginEnabledValue': 'yes'
                        },
                        'guidAttr': 'entryUUID',

                        'base': '{0}'.format(LMC.backends.openldap.base),
                        'groups': {
                            'emailSuffix': '',
                            'filter': '',
                            'rdn': 'ou=Groups',
                            'attr': 'cn',
                            'mapping': {
                                'recordName': 'cn',
                                'lastName': 'sn',
                                'fullName': 'cn',
                                'emailAddresses': 'mail',
                                'firstName': 'givenName'
                            }
                        },

                    },
                    'tlsCACertDir': '',
                    'cacheTimeout': 30,
                    'credentials': {
                        'dn': '{0}'.format(LMC.backends.openldap.rootbinddn),
                        'password': '{0}'.format(LMC.backends.openldap.secret)
                    },
                    'tlsCACertFile': '',
                    'authMethod': 'PAM'
                }
            }
        else:
            self.default_config.ldap_directory = None
        self.default_config.xml_directory = {
            'type': 'twistedcaldav.directory.xmlfile.XMLDirectoryService',
            'params': {
                'xmlFile': '{0}'.format(self.paths.accounts)
            }
        }

    def initialize(self):
        """ Set :attr:`self.available` to ``True`` if calendarserver service
            is installed and all of its data files load properly.
        """

        assert ltrace_func(TRACE_CALDAVD)

        self.available = False

        if os.path.exists(self.paths.main_dir):

            try:
                self.__parse_files()
                self.setup_calendarserver_environement()
                self.available = True

            except ImportError, e:
                logging.warning2(
                    _(u'{0}: extension not available because {1}.').format(
                        stylize(ST_NAME, self.name), e)
                )

            except (IOError, OSError), e:
                if e.errno == 2:
                    logging.warning2(
                        _(u'{0}: extension not yet available because {1} '
                            '(calendarserver is probably installing, try again'
                            ' later).').format(stylize(ST_NAME, self.name), e)
                    )
                else:
                    raise e
        else:
            logging.warning2(
                _(u'{0}: extension not available because {1} '
                    'not installed.').format(
                        stylize(ST_NAME, self.name),
                        stylize(ST_NAME, self.service_name)
                    )
            )

        return self.available

    def switch_directoryService(self, key):
        """ Modify the calendarserver configuration the use the correct
        backend """

        # load calendarserver config file
        if key.lower() == 'ldap':
            directoryservice_dict = self.default_config.ldap_directory
        elif key.lower() == 'xml':
            directoryservice_dict = self.default_config.xml_directory

        directoryservice_xml = my_Configdict2xmlEtree(directoryservice_dict)

        # Reload the whole xml file in order to set correctly the
        #"DirectoryService" part.
        xml_parsed = ET.parse(self.paths.configuration)

        # TODO: comment it
        count_ref = None
        for count, i in enumerate(xml_parsed.iter()):
            if i.text == 'DirectoryService':
                count_ref = int(count)

        xml_parsed.getroot()[0][count_ref - 1] = directoryservice_xml

        xml_parsed.write(self.paths.configuration)

        # set the new calendarser backend
        self.calendarserver_backend = LDAP_BACKEND if key == 'ldap' else \
            XML_BACKEND

        self.clear_accounts_and_ressources()
        self.setup_calendarserver_environement()

    def check(self, batch=False, auto_answer=None):
        """ Check eveything needed for the caldavd extension and service.

            1. Check that calendarserver use the right backend:
                - if licornd backend is ONLY shadow, calendarserver's backend
                    is XMLDirectoryService
                - elif OPENLAP is enabled in licornd backend, calendarserver
                    has to user LdapDirectoryService


            2. if calendarserver's backend is XMLDirectoryService:
                - check that already existing users and groups have a calendar

            3. for all users, check their relationship with groups and apply
                proxies.

        """

        assert ltrace_func(TRACE_CALDAVD)

        # get actual calendarserver backend
        self.calendarserver_backend = caldav_config.DirectoryService.type

        # check licorn backends
        shadow_backend = LMC.backends.guess_one('shadow')
        try:
            # openLDAP may not be installed
            ldap_backend = LMC.backends.guess_one('openldap')
        except KeyError:
            ldap_backend = None

        # if current licorn backend is LDAP and caldav backend is not LDAP,
        # change caldav backend to LDAP
        if ldap_backend is not None and ldap_backend.enabled:
            if self.calendarserver_backend != LDAP_BACKEND:
                self.switch_directoryService('ldap')

        # elif current licorn backend is SHADOW, change caldav to SHADOW
        elif shadow_backend.enabled:
            if self.calendarserver_backend == LDAP_BACKEND:
                self.switch_directoryService('xml')

        if self.calendarserver_backend == XML_BACKEND:
            # check if already existing STD users have a calendar.
            for user in LMC.users.select(filters.STANDARD):
                if not self.check_if_element_has_calendar('users', user.login):
                    self.user_post_add(user=user, password=GENERIC_PWD)

        for group in LMC.groups.select(filters.STANDARD):
            # if the group is in the same backend than calendarserver
            if (group.backend == shadow_backend and
                self.calendarserver_backend == XML_BACKEND) or \
                (ldap_backend is not None and
                    group.backend.name == ldap_backend.name and
                    self.calendarserver_backend == LDAP_BACKEND):

                print ">> group_post_add"
                self.group_post_add(group=group)

        #self.service(svccmds.RELOAD)
        self.setup_calendarserver_environement()

        for u in LMC.users.select(filters.STANDARD):
            print "<> each user"
            # if the user is in the same backend than calendarserver
            if (u.backend.name == shadow_backend.name and
                self.calendarserver_backend == XML_BACKEND) or \
                (ldap_backend is not None and
                    u.backend.name == ldap_backend.name and
                    self.calendarserver_backend == LDAP_BACKEND):

                for g in u.groups:
                    # same story, check group backend
                    print "in user groups"
                    if (group.backend == shadow_backend and
                        self.calendarserver_backend == XML_BACKEND) or \
                        (ldap_backend is not None and
                            group.backend.name == ldap_backend.name and
                            self.calendarserver_backend == LDAP_BACKEND):

                        if not g.is_system or g.is_guest or g.is_responsible:

                            self.group_post_add_user(user=u, group=g)

    def check_if_element_has_calendar(self, _type, element):
        """ Return True is element ``element`` of type ``type`` has already
            a calendar else False
        """
        logging.info(
            '{0}: Checking if element {1} of type {2} has already a '
            'calendar'.format(
                stylize(ST_NAME, self.name), stylize(ST_PATH, element),
                stylize(ST_PATH, _type)))

        if principalForPrincipalID('{0}:{1}'.format(_type, element)) is None:
            return False
        else:
            return True

    def setup_calendarserver_environement(self):
        """ setup calendarserver environment with its own internal mecanism """

        # load the calendarserver configuration
        loadConfig(None)
        caldav_config.directory = getDirectory()

        # setup memcache
        setupMemcached(caldav_config)

    def __parse_files(self):
        """ Create locks and load all caldavd data files. """

        # TODO: implement sudoers if needed.

        #self.locks = LicornConfigObject()
        #self.locks.accounts = FileLock(self.paths.accounts)
        #self.locks.configuration = FileLock(self.paths.configuration)
        #self.locks.sudoers = FileLock(self.paths.sudoers)
        self.data.defaults = readers.shell_conf_load_dict(
            self.paths.defaults)

        self.data.accounts = readers.xml_load_tree(self.paths.accounts)
        self.data.resources = readers.xml_load_tree(self.paths.resources)

        # self.data.configuration = readers.plist_load_dict(
        #                                   self.paths.configuration)
    def is_enabled(self):
        """ Return ``True`` if the directive ``start_calendarserver`` is set to
            ``yes`` in the service configuration file
            (:file:`/etc/default/calendarserver` on Debian/Ubuntu).

            If the directive doesn't exist yet, we consider the service as
            freshly installed: we try to strip examples from the accounts file
            if they exists, and return ``False`` because the service is not
            yet enabled.
        """
        assert ltrace_func(TRACE_CALDAVD)

        try:
            if self.data.defaults['start_calendarserver'] in ('yes', 'YES'):

                # ensure the service is running, if it should be.
                if not self.running(self.paths.pid_file):
                    self.service(svccmds.START)

                assert ltrace(
                    globals()['TRACE_' + self.name.upper()],
                    '| is_enabled() → True')

                logging.info(
                    _(u'{0}: started extension, managing {1} service '
                        '({2}).').format(
                            stylize(ST_NAME, self.name),
                            stylize(ST_NAME, self.service_name),
                            (_(u'pid=%s') % stylize(
                                ST_UGID,
                                open(self.paths.pid_file).read().strip()))
                            if os.path.exists(self.paths.pid_file)
                            else stylize(ST_COMMENT, _('Starting up'))))

                return True
            else:
                assert ltrace(
                    globals()['TRACE_' + self.name.upper()],
                    '| is_enabled() → True')

                logging.info(
                    _(u'{0}: extension disabled because service {1} '
                        'disabled on the local system.').format(
                            stylize(ST_NAME, self.name),
                            stylize(ST_NAME, self.service_name)))
                return False

        except KeyError:
            self.data.defaults['start_calendarserver'] = 'no'
            self.__write_defaults()
            self.__strip_examples()
            assert ltrace(
                globals()['TRACE_' + self.name.upper()],
                '| is_enabled() → False')
            return False

    def enable(self):
        """ Set the directive ``start_calendarserver`` to ``yes`` in the
            service configuration file, then start the caldavd service and
            return ``True`` if everything succeeds, else ``False``.
        """
        assert ltrace_func(TRACE_CALDAVD)

        try:
            self.data.defaults['start_calendarserver'] = 'yes'
            self.__write_defaults()
            self.start()
            assert ltrace(
                globals()['TRACE_' + self.name.upper()],
                '| enable() → True')
            self.enabled = True

            return True

        except Exception, e:
            logging.warning(
                _(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
            print_exc()
            assert ltrace(
                globals()['TRACE_' + self.name.upper()],
                '| enable() → False')
            return False

    def disable(self):
        """ Stop the caldavd service, then set the directive
            ``start_calendarserver`` to ``no`` in the service configuration
            file and return ``True`` if everything succeeds, else ``False``.
        """
        assert ltrace_func(TRACE_CALDAVD)

        try:
            self.stop()
            self.data.defaults['start_calendarserver'] = 'no'
            self.__write_defaults()
            assert ltrace(
                globals()['TRACE_' + self.name.upper()],
                '| disable() → True')
            self.enabled = False

            return True

        except Exception, e:
            logging.warning(
                _(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
            print_exc()
            assert ltrace(
                globals()['TRACE_' + self.name.upper()],
                '| disable() → False')
            return False

    def __strip_examples(self):
        """ TODO. """
        assert ltrace_func(TRACE_CALDAVD)

        self.data.accounts.getroot().set('realm', 'Licorn / META IT')
        self.del_account('user', 'admin')
        self.del_account('user', 'test')
        self.del_account('group', 'users')
        self.del_account('location', 'mercury')
        self.__write_accounts()

    def __write_defaults(self):
        """ Backup the service configuration file, then save it with our
            current data.
        """
        assert ltrace_func(TRACE_CALDAVD)

        fsapi.backup_file(self.paths.defaults)
        writers.shell_conf_write_from_dict(
            self.data.defaults, self.paths.defaults, mode=0640)
        return True

    def __write_accounts(self):
        """ Write the XML accounts file to disk, after having backed it up. """
        assert ltrace_func(TRACE_CALDAVD)

        # TODO: assert self.locks.accounts.is_locked()
        writers.xml_write_from_tree(
            self.data.accounts, self.paths.accounts, mode=0640)
        # TODO: self.locks.accounts.release()
        return True

    def __write_resources(self):
        """ Write the XML resources file to disk, after having backed it up."""
        assert ltrace_func(TRACE_CALDAVD)

        # TODO: assert self.locks.accounts.is_locked()
        writers.xml_write_from_tree(
            self.data.resources, self.paths.resources, mode=0640)
        # TODO: self.locks.accounts.release()
        return True

    def __write_elements_and_reload(self):
        """ Write the accounts file and reload the caldavd service. A reload is
            needed, else caldavd doesn't see new user accounts and resources.
        """
        assert ltrace_func(TRACE_CALDAVD)

        print ">> __write_elements_and_reload"

        self.__write_accounts()
        self.__write_resources()

        for filename in self.paths:
            if (os.path.exists(filename) and filename != self.paths.main_dir):
                os.chmod(filename, 0640)
                os.chown(
                    filename, LMC.users.guess_one('caldavd').uidNumber,
                    LMC.groups.guess_one('caldavd').gidNumber)

        # fu...ing caldavd service which doesn't understand reload.
        # we put this in a service thread to avoid the long wait.
        workers.service_enqueue(
            priorities.NORMAL, self.service, svccmds.RESTART)

    def users_load(self):
        """ eventually load users-related data. Currently this method does
            nothing. """

        assert ltrace_func(TRACE_CALDAVD)
        return True

    def groups_load(self):
        """ eventually load groups-related data. Currently this method does
            nothing. """

        assert ltrace_func(TRACE_CALDAVD)
        return True

    def __create_xml_element(self, acttype, uid, guid, name):
        """ Create the XML ElementTree object base for a caldav account (can be
            anything), then return it for the caller to add specific
            SubElements to it.
        """
        assert ltrace_func(TRACE_CALDAVD)

        if acttype in ("resource", "location"):
            # special treatment, search in correct file
            xml_elem = ET.SubElement(self.data.resources.getroot(), acttype)
        else:
            # users, groups
            xml_elem = ET.SubElement(self.data.accounts.getroot(), acttype)

        xml_elem.text = '\n '
        xml_elem.tail = '\n'

        xmluid = ET.SubElement(xml_elem, 'uid')
        xmluid.text = uid
        xmluid.tail = '\n   '

        xmlguid = ET.SubElement(xml_elem, 'guid')
        xmlguid.text = guid
        xmlguid.tail = '\n  '

        xmlname = ET.SubElement(xml_elem, 'name')
        xmlname.text = name
        xmlname.tail = '\n  '

        return xml_elem

    def add_user(self, uid, guid, name, password, **kwargs):
        """ Create a caldav user account. """

        assert ltrace_func(TRACE_CALDAVD)

        user = self.__create_xml_element('user', uid, guid, name)

        xmlpwd = ET.SubElement(user, 'password')
        xmlpwd.text = password
        xmlpwd.tail = '\n'
        return True

    def add_group(self, uid, guid, name, **kwargs):
        """ Create a caldav group account. """

        assert ltrace_func(TRACE_CALDAVD)

        group = self.__create_xml_element('group', uid, guid, name)

        xmlmembers = ET.SubElement(group, 'members')
        xmlmembers.text = '\n   '
        xmlmembers.tail = '\n'
        return True

    def add_resource(self, uid, guid, name, type, gst_uid=None, **kwargs):
        """ Create a caldav resource account. """

        assert ltrace_func(TRACE_CALDAVD)

        resource = self.__create_xml_element('resource', uid, guid, name)

        if resource is not None:
            return True
        else:
            return False

    def del_resource(self, uid):
        for xmldata in self.data.resources.findall('resource'):
            if xmldata.find('uid').text == uid:
                self.data.resources.getroot().remove(xmldata)
                return True

        logging.warning2(
            _(u'{0}: unable to delete {1} {2}, not found in {3}.').format(
                stylize(ST_NAME, self.name), "resource", stylize(ST_UGID, uid),
                stylize(ST_PATH, self.paths.resources)))
        return False

    def add_member(self, name, login, **kwargs):
        """ Create a new entry in the members element of a group. """

        assert ltrace_func(TRACE_CALDAVD)

        for xmldata in self.data.accounts.findall('group'):
            if xmldata.find('uid').text == name:
                xmlmember_list = xmldata.find('members')

                xmlmember = ET.SubElement(xmlmember_list, 'member')
                xmlmember.set('type', 'users')
                xmlmember.text = login
                xmlmember.tail = '\n        '
                return True
        return False

    def mod_account(self, acttype, uid, attrname, value):
        """ Alter a caldav account: find a given attribute, then modify its
            value, then write the configuration to disk and reload the service.
        """
        assert ltrace_func(TRACE_CALDAVD)

        for xmldata in self.data.accounts.findall(acttype):
            if xmldata.find('uid').text == uid:
                xmlattr = xmldata.find(attrname)
                xmlattr.text = value
                return True

        logging.warning2(
            _(u'{0}: unable to modify {1} for {2} {3}, not found '
                'in {4}.').format(
                    stylize(ST_NAME, self.name),
                    stylize(ST_ATTR, attrname), acttype,
                    stylize(ST_NAME, uid),
                    stylize(ST_PATH, self.paths.accounts)))
        return False

    def del_account(self, acttype, uid):
        """ delete the resource in the accounts file. """

        assert ltrace_func(TRACE_CALDAVD)

        for xmldata in self.data.accounts.findall(acttype):
            if xmldata.find('uid').text == uid:
                self.data.accounts.getroot().remove(xmldata)
                return True

        logging.warning2(
            _(u'{0}: unable to delete {1} {2}, not found in {3}.').format(
                stylize(ST_NAME, self.name), acttype, stylize(ST_UGID, uid),
                stylize(ST_PATH, self.paths.accounts)))
        return False

    def del_member(self, name, login):
        """ delete the user from the members of the group
            in the accounts file. """

        assert ltrace_func(TRACE_CALDAVD)

        for xmldata in self.data.accounts.findall('group'):
            if xmldata.find('uid').text == name:
                for xmlmember in xmldata.findall('members/member'):
                    if xmlmember.text == login:
                        xmldata.find('members').remove(xmlmember)
                        return True

        logging.warning2(
            _(u'{0}: unable to delete user {1} from group {2}, '
                'not found in {3}.').format(
                    stylize(ST_NAME, self.name),
                    stylize(ST_LOGIN, login), stylize(ST_NAME, name),
                    stylize(ST_PATH, self.paths.accounts)))
        return False

    @events.handler_method
    @only_if_enabled
    def user_pre_add(self, *args, **kwargs):
        """ Lock the accounts file in prevision of a change. """
        #return self.locks.accounts.acquire()
        return True

    @events.handler_method
    @only_if_enabled
    @only_if_backend_openldap_is_not_enabled
    def user_post_add(self, *args, **kwargs):
        """ Create a caldavd user account """

        assert ltrace_func(TRACE_CALDAVD)

        user = kwargs.pop('user')
        password = kwargs.pop('password')

        """logging.info(_(u'{0}: creating calendar for {1}: '
            '{2}').format(stylize(ST_NAME, self.name),
                        stylize(ST_PATH, "user"),
                        stylize(ST_OK, user.login)))"""

        # we don't deal with system accounts, they don't get calendar for free.
        if user.is_system:
            return True

        try:

            if self.add_user(
                uid=user.login, guid=str(uuid.uuid1()), password=password,
                    name=user.gecos):

                logging.info(
                    '{0}: calendar for user {1} created'.format(
                        self.name, user.login))

                self.__write_elements_and_reload()

            return True

        except Exception, e:
            logging.warning(
                _(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
            print_exc()
            return False

    @events.handler_method
    @only_if_enabled
    def user_pre_change_password(self, *args, **kwargs):
        """ """
        assert ltrace_func(TRACE_CALDAVD)

        # TODO: return self.locks.accounts.acquire()
        return True

    @events.handler_method
    @only_if_enabled
    @only_if_backend_openldap_is_not_enabled
    def user_post_change_password(self, *args, **kwargs):
        """ Update the user's password in caldavd accounts file. """

        assert ltrace_func(TRACE_CALDAVD)

        user = kwargs.pop('user')
        password = kwargs.pop('password')

        # we don't deal with system accounts, they don't get calendar for free.
        if user.is_system:
            return True

        try:
            if self.mod_account(
                acttype='user', uid=user.login, attrname='password',
                    value=password):

                self.__write_elements_and_reload()
                #logging.info('%s: changed user %s password.' % (
                #   self.name, self.paths.accounts))
            return True
        except Exception, e:
            logging.warning(
                _(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
            print_exc()
            return False

    @events.handler_method
    @only_if_enabled
    def user_pre_del(self, *args, **kwargs):
        """ delete a user and its resource in the caldavd accounts file, then
            reload the service. """

        assert ltrace_func(TRACE_CALDAVD)

        user = kwargs.pop('user')
        print "PRE DELLLLLL"
        # we don't deal with system accounts, they don't get calendar for free.
        if user.is_system:
            return True

        try:

            # remove proxies
            for g in user.groups:
                print "g", g.name

                if g.is_guest or g.is_responsible:
                    std_group = g.standard_group
                else:
                    std_group = g

                if g.is_guest:
                    option = "read"
                else:
                    option = "write"

                # find the resource, and remove proxy
                resource_principal = principalForPrincipalID(
                    'resources:resource_' + std_group.name)
                action_removeProxy(resource_principal, ('users:' + user.login))

                LicornEvent(
                    'calendar_del_proxie', user_proxy=new_user, group=group,
                    proxy_type=option).emit()

                logging.info(
                    '{0}: deleted proxy for user {1} on resource {2}'.format(
                        self.name, user.login, 'resource_' + g.name))

            if self.calendarserver_backend == LDAP_BACKEND:
                # no specif action
                pass

            elif self.calendarserver_backend == XML_BACKEND:

                # delete the user from the account.xml file
                if self.del_account(acttype='user', uid=user.login):
                    self.__write_elements_and_reload()
            else:
                logging.warning2(
                    '{0}: unknown calendarserver backend {1}.'.format(
                    self.name, self.calendarserver_backend))

            logging.info('{0}: user {1} deleted.'.format(
                self.name, user.login))

            return True

        except Exception, e:
            logging.warning(
                _(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
            print_exc()
            return False

    @events.handler_method
    @only_if_enabled
    def group_pre_add(self, *args, **kwargs):
        """ Lock the accounts file in prevision of a change. """
        #return self.locks.accounts.acquire()
        return True

    @events.handler_method
    @only_if_enabled
    def group_post_add(self, *args, **kwargs):
        """
            Group added handler.

            Groups in calendarserver have not calendars.
            Create a ressource for each standard groups.
        """

        assert ltrace_func(TRACE_CALDAVD)

        group = kwargs.pop('group')

        # only do something is group is standard
        if not group.is_standard:
            return

        # is this still usefull ?
        resource_uuid = str(uuid.uuid1())

        try:
            #if group.is_standard:
            resource_name = "resource_" + group.name

            group_resource_principal = principalForPrincipalID(
                'resources:' + resource_name)

            if group_resource_principal is None:

                self.add_resource(
                    uid=resource_name, guid=resource_uuid,
                    name=group.description, type='groups',
                    # we've got to construct the guest group
                    # name, because the guest group doesn't
                    # exist yet (it is created *after* the
                    # standard group.
                    gst_uid=group.guest_group.name)

                self.__write_elements_and_reload()

                logging.info('{0}: resource {1} created for group {2}.'.format(
                    stylize(ST_NAME, self.name),
                    stylize(ST_PATH, resource_name),
                    stylize(ST_PATH, group.name)))

            else:
                logging.info(
                    '{0}: resource {1} already exists for group {2}.'.format(
                        stylize(ST_NAME, self.name),
                        stylize(ST_PATH, resource_name),
                        stylize(ST_PATH, group.name)))

                #logging.info('%s: added group and resource in %s.' % (
                #   self.name, self.paths.accounts))

            return True

        except Exception, e:
            logging.warning(
                _(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
            print_exc()
            return False

    @events.handler_method
    @only_if_enabled
    def group_pre_del(self, *args, **kwargs):
        """ Pre delete group handler
            Remove the associated resource.
            No need to remove all proxies, they are removed automaticaly.
        """

        assert ltrace_func(TRACE_CALDAVD)

        group = kwargs.pop('group')

        if not group.is_standard:
            return

        try:
            # delete the group resource
            self.del_resource(uid="resource_" + group.name)

            # write and reload
            self.__write_elements_and_reload()

            logging.info('{0}: resource {1} deleted for group {2}.'.format(
                stylize(ST_NAME, self.name),
                stylize(ST_PATH, "resource_" + group.name),
                stylize(ST_PATH, group.name)))

            return True

        except Exception, e:
            logging.warning(_(u'{0}: {1}').format(
                            stylize(ST_NAME, self.name), e))
            print_exc()
            return False

    @events.handler_method
    @only_if_enabled
    @only_if_backend_openldap_is_not_enabled
    def group_pre_add_user(self, *args, **kwargs):
        """ Lock the accounts file in prevision of a change. """
        #return self.locks.accounts.acquire()
        return True

    @events.handler_method
    @only_if_enabled
    def group_post_add_user(self, *args, **kwargs):
        """ User added in group handler.

            Find the group associated resource and declare user as proxy.
        """

        assert ltrace_func(TRACE_CALDAVD)

        group = kwargs.pop('group')
        user = kwargs.pop('user')

        # we don't deal with system accounts, don't bother us with that.
        if user.is_system:
            return True

        if group.is_guest or group.is_responsible:
            std_group = group.standard_group
        else:
            std_group = group

        group_resource_principal = principalForPrincipalID(
            'resources:resource_' + std_group.name)
        if group_resource_principal is None:
            # If group has just been added into the system,
            # we need to reload calendarserver environement in order to find the
            # ressource
            self.setup_calendarserver_environement()

        # if group resource still not found, it doesn't exist
        if group_resource_principal is None:
            logging.warning2('{0}: cannot find principal for {1}'.format(
                stylize(ST_NAME, self.name),
                stylize(ST_PATH, 'resources:resource_' + std_group.name)))

        else:
            def __add_user_group(d, group, user):
                #print "__add_user_group", d

                read_proxies, write_proxies = d

                read_proxies = [
                    principalForPrincipalID(pid).record.shortNames[0]
                    for pid in read_proxies]
                write_proxies = [
                    principalForPrincipalID(pid).record.shortNames[0]
                    for pid in write_proxies]

                #print "R", read_proxies
                #print "W", write_proxies

                if group.is_guest:
                    if user.login not in read_proxies:
                        action_addProxy(
                            group_resource_principal, 'read',
                            ('users:' + user.login))
                        LicornEvent(
                            'calendar_add_proxie', group=group,
                            user_proxy=user, proxy_type="read").emit()
                    else:
                        logging.info(
                            '{0}: user {1} already a read proxy of ressource '
                            '{2}'.format(
                                stylize(ST_NAME, self.name),
                                stylize(ST_PATH, user.login),
                                stylize(ST_PATH, group_resource_principal)))
                else:
                    if user.login not in write_proxies:
                        action_addProxy(
                            group_resource_principal, 'write',
                            ('users:' + user.login))

                        LicornEvent(
                            'calendar_add_proxie', group=group,
                            user_proxy=user, proxy_type="write").emit()
                    else:
                        logging.info(
                            '{0}: user {1} already a write proxy of ressource '
                            '{2}'.format(
                                stylize(ST_NAME, self.name),
                                stylize(ST_PATH, user.login),
                                stylize(ST_PATH, group_resource_principal)))

                #self.service(svccmds.RESTART)
                #self.setup_calendarserver_environement()

            proxies = getProxies(group_resource_principal)
            proxies.addCallback(__add_user_group, group, user)

    @events.handler_method
    @only_if_enabled
    def group_pre_del_user(self, *args, **kwargs):
        """ User deleted from group handler.

            Find the group associated resource and remove user's proxy.
        """

        assert ltrace_func(TRACE_CALDAVD)

        group = kwargs.pop('group')
        user = kwargs.pop('user')

        # we don't deal with system accounts, don't bother us with that.
        if user.is_system:
            return True

        try:

            if group.is_guest or group.is_responsible:
                std_group = group.standard_group
            else:
                std_group = group

            if group.is_guest:
                option = "read"
            else:
                option = "write"

            resource_principal = principalForPrincipalID(
                'resources:resource_' + std_group.name)

            action_removeProxy(resource_principal, ('users:' + user.login))

            LicornEvent(
                'calendar_del_proxie', group=group, user_proxy=user,
                proxy_type=option).emit()

            return True
        except Exception, e:
            logging.warning(_(u'{0}: {1}').format(
                            stylize(ST_NAME, self.name), e))
            print_exc()
            return False

    @events.handler_method
    @only_if_enabled
    @only_if_backend_openldap_is_not_enabled
    def group_post_del_user(self, *args, **kwargs):
        """ Lock the accounts file in prevision of a change. """
        #return self.locks.accounts.acquire()
        return True

    def clear_accounts_and_ressources(self):

        # build a tree structure
        root = ET.Element("accounts")
        root.set('realm', "TOTOTOTOTOOTOTO")
        res_tree = ET.ElementTree(root)
        ac_tree = ET.ElementTree(root)

        self.data = LicornConfigObject()
        self.data.accounts = ac_tree
        self.data.resources = res_tree

        self.data.defaults = readers.shell_conf_load_dict(
            self.paths.defaults)

        self.__write_elements_and_reload()
