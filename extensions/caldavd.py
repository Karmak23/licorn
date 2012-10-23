# -*- coding: utf-8 -*-
"""
Licorn extensions: caldavd - http://docs.licorn.org/extensions/caldavd.html

:copyright:
	* 2010 Olivier Cortès <oc@meta-it.fr>
	* 2010 Guillaume Masson <guillaume.masson@meta-it.fr>

:license: GNU GPL version 2

"""

import os, uuid
from traceback import print_exc
import xml.etree.ElementTree as ET

from licorn.foundations           import logging, pyutils, fsapi, network
from licorn.foundations           import readers, writers, events
from licorn.foundations.workers   import workers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, MixedDictObject, LicornConfigObject
from licorn.foundations.classes   import FileLock
from licorn.foundations.constants import distros, services, svccmds, priorities, filters

from licorn.core                  import LMC
from licorn.core.classes          import only_if_enabled

from licorn.extensions import ServiceExtension


from calendarserver.tools.principals   import action_addProxy, addProxy, principalForPrincipalID
from calendarserver.tools.util         import getDirectory, loadConfig, setupMemcached
from twistedcaldav.config              import config as caldav_config
from twistedcaldav.config              import ConfigDict
from twistedcaldav.directory.directory import DirectoryRecord


from twistedcaldav.directory.directory import DirectoryService





## {{{ http://code.activestate.com/recipes/577739/ (r4)
from xml.dom.minidom import Document
import copy, types

class dict2xml(object):
    doc     = Document()

    def __init__(self, structure):
        if len(structure) == 1:
            rootName    = str(structure.keys()[0])
            self.root   = self.doc.createElement(rootName)

            self.doc.appendChild(self.root)
            self.build(self.root, structure[rootName])

    def build(self, father, structure):
        if type(structure) == dict:
            for k in structure:
                tag = self.doc.createElement(k)
                father.appendChild(tag)
                self.build(tag, structure[k])
        
        elif type(structure) == list:
            grandFather = father.parentNode
            tagName     = father.tagName
            grandFather.removeChild(father)
            for l in structure:
                tag = self.doc.createElement(tagName)
                self.build(tag, l)
                grandFather.appendChild(tag)
            
        else:
            data    = str(structure)
            tag     = self.doc.createTextNode(data)
            father.appendChild(tag)
    
    def display(self):
        print self.doc.toprettyxml(indent="  ")

    """example = {'sibbling':{'couple':{'mother':'mom','father':'dad','children':[{'child':'foo'},
                                                          {'child':'bar'}]}}}
    xml = dict2xml(example)
    xml.display()"""

class XML2Dict(object):

    def __init__(self, coding='UTF-8'):
        self._coding = coding

    def _parse_node(self, node):
        tree = {}

        #Save childrens
        for child in node.getchildren():
            print child
            print child.text
            ctag = child.tag
            cattr = child.attrib
            ctext = child.text.strip().encode(self._coding) if child.text is not None else ''
            print ctext
            ctree = self._parse_node(child)

            if not ctree:
                cdict = self._make_dict(ctag, ctext, cattr)
            else:
                cdict = self._make_dict(ctag, ctree, cattr)

            if ctag not in tree: # First time found
                tree.update(cdict)
                continue

            atag = '@' + ctag
            atree = tree[ctag]
            if not isinstance(atree, list):
                if not isinstance(atree, dict):
                    atree = {}

                if atag in tree:
                    atree['#'+ctag] = tree[atag]
                    del tree[atag]

                tree[ctag] = [atree] # Multi entries, change to list

            if cattr:
                ctree['#'+ctag] = cattr

            tree[ctag].append(ctree)

        return  tree

    def _make_dict(self, tag, value, attr=None):
        '''Generate a new dict with tag and value
        
        If attr is not None then convert tag name to @tag
        and convert tuple list to dict
        '''
        ret = {tag: value}

        # Save attributes as @tag value
        if attr:
            atag = '@' + tag

            aattr = {}
            for k, v in attr.items():
                aattr[k] = v

            ret[atag] = aattr

            del atag
            del aattr

        return ret

    def parse(self, xml):
        '''Parse xml string to python dict
        
        '''
        EL = ET.fromstring(xml)

        return self._make_dict(EL.tag, self._parse_node(EL), EL.attrib)

def my_Configdict2xmlEtree(_dict):
	"""returns xml"""
	root = ET.Element('dict')


	for k,v in _dict.iteritems():
		#print k, v
		elem = ET.Element('key')
		elem.text = k

		root.append(elem)
		#print type(v)
		if type(v) == types.StringType:
			elem_value = ET.Element('string')
			elem_value.text = v
		if type(v) == types.BooleanType:
			if v:
				elem_value = ET.Element('true')
			else:
				elem_value = ET.Element('false')
		if type(v) == types.IntType:
			elem_value = ET.Element('integer')
			elem_value.text = str(v)
		if type(v) == types.NoneType:
			elem_value = ET.Element('string')

		if isinstance(v, ConfigDict) or type(v) == types.DictType:
			elem_value = my_Configdict2xmlEtree(v)

		root.append(elem_value)

	return root







class CaldavdExtension(ObjectSingleton, ServiceExtension):
	""" Handles Apple Calendar Server configuration and service.

		.. versionadded:: 1.2.4

	"""
	def __init__(self):
		assert ltrace_func(TRACE_EXTENSIONS)

		ServiceExtension.__init__(self, name='caldavd',
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

		self.paths.main_dir      = '/etc/caldavd'
		self.paths.accounts      = self.paths.main_dir + '/accounts.xml'
		self.paths.resources      = self.paths.main_dir + '/resources.xml'
		self.paths.configuration = self.paths.main_dir + '/caldavd.plist'
		self.paths.sudoers       = self.paths.main_dir + '/sudoers.plist'
		self.paths.pid_file      = '/var/run/caldavd/caldavd.pid'

		self.data = LicornConfigObject()

		if LMC.configuration.distro in (distros.UBUNTU, distros.LICORN,
										distros.DEBIAN):
			self.paths.service_defaults = '/etc/default/calendarserver'

		# create default directoryservice config for ldap and xml backends
		self.default_config = LicornConfigObject()
		self.default_config.ldap_directory = { 
			
			'type': 'twistedcaldav.directory.ldapdirectory.LdapDirectoryService', 

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
				'uri': 'ldap:///', 
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
					
					'base': 'dc=meta-it,dc=local', 
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
					'dn': 'cn=admin,dc=meta-it,dc=local', 
					'password': 'metasecret' 
				}, 
				'tlsCACertFile': '',
				'authMethod': 'PAM'
			}
		}
		self.default_config.xml_directory = { 
			'type': 'twistedcaldav.directory.xmlfile.XMLDirectoryService', 
			'params': {
				'xmlFile': '/etc/caldavd/accounts.xml'
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
				logging.warning2(_(u'{0}: extension not available '
					'because {1}.').format(stylize(ST_NAME, self.name), e))

			except (IOError, OSError), e:
				if e.errno == 2:
					logging.warning2(_(u'{0}: extension not yet available '
					'because {1} (calendarserver is probably installing, '
					'try again later).').format(stylize(ST_NAME, self.name), e))
				else:
					raise e
		else:
			logging.warning2(_(u'{0}: extension not available because {1} '
				'not installed.').format(stylize(ST_NAME, self.name),
					stylize(ST_NAME, self.service_name)))

		return self.available
	def switch_directoryService(self, key):
		""" TODO """




		# load calendarserver config file
		config_xml = my_Configdict2xmlEtree(self.default_config.ldap_directory if key=='ldap' else self.default_config.xml_directory)

		# Relaod the whole xml file in order to modify the correct "DirectoryService" part.
		
		xml_parsed = ET.parse(self.paths.configuration)

		count_ref = None

		for count, i in enumerate(xml_parsed.iter()):
			if i.text == 'DirectoryService':
				count_ref = int(count)

		xml_parsed.getroot()[0][count_ref - 1] = config_xml

		xml_parsed.write(self.paths.configuration)

	def check(self, batch=False, auto_answer=None):
		""" Check eveything needed for the caldavd extension and service.
			First check ``chmod`` on caldavd files (because they
			contain user passwords in clear-text). 

			Secondly, match the caldav backend to the licorn backend.

			If backend 'openldap' is activated on Licorn side, only users and 
				groups from licorn ldap backend will be used into calendarserver
			
			If backend 'openldap' not activated, use default 'shadow' backend.

		"""

		assert ltrace_func(TRACE_CALDAVD)

		for filename in self.paths:
			if (os.path.exists(filename) and filename != self.paths.main_dir):
				os.chmod(filename, 0640)


		

		

		# check licorn backends
		shadow_backend = LMC.backends.guess_one('shadow')
		ldap_backend   = LMC.backends.guess_one('openldap')

		CALDAV_LDAP_BACKEND = "twistedcaldav.directory.ldapdirectory.LdapDirectoryService"

		caldav_backend = caldav_config.DirectoryService.type
		need_reload = False

		# if current licorn backend is LDAP and caldav backend is not LDAP,
		# change caldav backend to LDAP
		if ldap_backend.enabled:
			if caldav_backend != CALDAV_LDAP_BACKEND:
				need_reload = True
				self.switch_directoryService('ldap')

		# elif current licorn backend is SHADOW, change caldav backend to SHADOW
		elif shadow_backend.enabled:
			if caldav_backend == CALDAV_LDAP_BACKEND:
				need_reload = True
				self.switch_directoryService('xml')


		if need_reload:
			# we changed something, reload the service in order to changes take
			# effect.
			self.service(svccmds.RELOAD)

		# after reload check existing users/groups
		if not ldap_backend.enabled:
			# check if already existing STD users have a calendar.
			for user in LMC.users.select(filters.STANDARD):
				if not self.check_if_element_has_calendar('users', user.login):
					print "ADD USER"
					#self.post_add_user(....)
			for group in LMC.groups.select(filters.STANDARD):
				if not self.check_if_element_has_calendar('groups', group.name) and \
					not self.check_if_element_has_calendar('groups', 'rsp-'+group.name) and \
					not self.check_if_element_has_calendar('groups', 'gst-'+group.name) and \
					not self.check_if_element_has_calendar('resources', group.name):
						print "ADD GROUP"
						#self.post_add_group(....)

		# if ldap backend check if group resource exists

		# and don't forget to remove (or at least warn about) superfluous entries.
		logging.info(_(u'**Please implement caldavd extension check for '
			'pre-existing users and groups.**'))

	def check_if_element_has_calendar(self, type, element):
		""" ask calendarserver """
		print ">> check if calendar ",element, principalForPrincipalID('{0}:{1}'.format(type, element))
		if principalForPrincipalID('{0}:{1}'.format(type, element)) is None:
			return False
		else:
			return True



	def setup_calendarserver_environement(self):
		loadConfig(None)
		caldav_config.directory = getDirectory()
		setupMemcached(caldav_config)

	def __parse_files(self):
		""" Create locks and load all caldavd data files. """

		# TODO: implement sudoers if needed.

		#self.locks = LicornConfigObject()
		#self.locks.accounts = FileLock(self.paths.accounts)
		#self.locks.configuration = FileLock(self.paths.configuration)
		#self.locks.sudoers = FileLock(self.paths.sudoers)
		self.data.service_defaults = readers.shell_conf_load_dict(
					self.paths.service_defaults)

		self.data.accounts  = readers.xml_load_tree(self.paths.accounts)
		self.data.resources = readers.xml_load_tree(self.paths.resources)

		# self.data.configuration = readers.plist_load_dict(
		#									self.paths.configuration)
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
			if self.data.service_defaults['start_calendarserver'] \
															in ('yes', 'YES'):

				# ensure the service is running, if it should be.
				if not self.running(self.paths.pid_file):
					self.service(svccmds.START)

				assert ltrace(globals()['TRACE_' + self.name.upper()], '| is_enabled() → True')

				logging.info(_(u'{0}: started extension, managing {1} service '
					'({2}).').format(stylize(ST_NAME, self.name),
					stylize(ST_NAME, self.service_name),
					(_(u'pid=%s') % stylize(ST_UGID,
						open(self.paths.pid_file).read().strip()))
							if os.path.exists(self.paths.pid_file)
							else stylize(ST_COMMENT, _('Starting up'))))

				return True
			else:
				assert ltrace(globals()['TRACE_' + self.name.upper()], '| is_enabled() → True')

				logging.info(_(u'{0}: extension disabled because service {1} '
					'disabled on the local system.').format(
					stylize(ST_NAME, self.name),
					stylize(ST_NAME, self.service_name)))
				return False

		except KeyError:
			self.data.service_defaults['start_calendarserver'] = 'no'
			self.__write_defaults()
			self.__strip_examples()
			assert ltrace(globals()['TRACE_' + self.name.upper()], '| is_enabled() → False')
			return False
	def enable(self):
		""" Set the directive ``start_calendarserver`` to ``yes`` in the
			service configuration file, then start the caldavd service and
			return ``True`` if everything succeeds, else ``False``.
		"""
		assert ltrace_func(TRACE_CALDAVD)

		try:
			self.data.service_defaults['start_calendarserver'] = 'yes'
			self.__write_defaults()
			self.start()
			assert ltrace(globals()['TRACE_' + self.name.upper()], '| enable() → True')
			self.enabled = True

			return True

		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
			print_exc()
			assert ltrace(globals()['TRACE_' + self.name.upper()], '| enable() → False')
			return False
	def disable(self):
		""" Stop the caldavd service, then set the directive
			``start_calendarserver`` to ``no`` in the service configuration
			file and return ``True`` if everything succeeds, else ``False``.
		"""
		assert ltrace_func(TRACE_CALDAVD)

		try:
			self.stop()
			self.data.service_defaults['start_calendarserver'] = 'no'
			self.__write_defaults()
			assert ltrace(globals()['TRACE_' + self.name.upper()], '| disable() → True')
			self.enabled = False

			return True

		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
			print_exc()
			assert ltrace(globals()['TRACE_' + self.name.upper()], '| disable() → False')
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

		fsapi.backup_file(self.paths.service_defaults)
		writers.shell_conf_write_from_dict(self.data.service_defaults,
			self.paths.service_defaults, mode=0640)
		return True
	def __write_accounts(self):
		""" Write the XML accounts file to disk, after having backed it up. """
		assert ltrace_func(TRACE_CALDAVD)

		# TODO: assert self.locks.accounts.is_locked()
		writers.xml_write_from_tree(self.data.accounts, self.paths.accounts, mode=0640)
		# TODO: self.locks.accounts.release()
		return True
	def __write_resources(self):
		""" Write the XML resources file to disk, after having backed it up. """
		assert ltrace_func(TRACE_CALDAVD)

		# TODO: assert self.locks.accounts.is_locked()
		writers.xml_write_from_tree(self.data.resources, self.paths.resources, mode=0640)
		# TODO: self.locks.accounts.release()
		return True
	
	def __write_elements_and_reload(self):
		""" Write the accounts file and reload the caldavd service.	A reload
			is needed, else caldavd doesn't see new user accounts and resources.
		"""
		assert ltrace_func(TRACE_CALDAVD)

		self.__write_accounts()
		self.__write_resources()

		# fu...ing caldavd service which doesn't understand reload.
		# we put this in a service thread to avoid the long wait.
		workers.service_enqueue(priorities.NORMAL, self.service, svccmds.RESTART)
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
		
		xml_elem.text = '\n	'
		xml_elem.tail = '\n'

		xmluid = ET.SubElement(xml_elem, 'uid')
		xmluid.text = uid
		xmluid.tail = '\n	'

		xmlguid = ET.SubElement(xml_elem, 'guid')
		xmlguid.text = guid
		xmlguid.tail = '\n	'

		xmlname = ET.SubElement(xml_elem, 'name')
		xmlname.text = name
		xmlname.tail = '\n	'

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
		xmlmembers.text = '\n	'
		xmlmembers.tail = '\n'
		return True
	def add_resource(self, uid, guid, name, type, gst_uid=None, **kwargs):
		""" Create a caldav resource account. """

		assert ltrace_func(TRACE_CALDAVD)

		resource = self.__create_xml_element('resource', uid, guid, name)

		"""xmlproxies = ET.SubElement(resource, 'proxies')
		xmlproxies.text = '\n		'
		xmlproxies.tail = '\n'

		xmlmember = ET.SubElement(xmlproxies, 'member')
		xmlmember.set('type', type)
		xmlmember.text = uid
		xmlmember.tail = '\n	'

		xmlroproxies = ET.SubElement(resource, 'read-only-proxies')
		xmlroproxies.text = '\n		'
		xmlroproxies.tail = '\n'

		if gst_uid:
			xmlromember = ET.SubElement(xmlroproxies, 'member')
			xmlromember.set('type', type)
			xmlromember.text = gst_uid
			xmlromember.tail = '\n	'"""

		return True
	def add_member(self, name, login, **kwargs):
		""" Create a new entry in the members element of a group. """

		assert ltrace_func(TRACE_CALDAVD)

		for xmldata in self.data.accounts.findall('group'):
			if xmldata.find('uid').text == name:
				xmlmember_list = xmldata.find('members')

				xmlmember = ET.SubElement(xmlmember_list, 'member')
				xmlmember.set('type', 'users')
				xmlmember.text = login
				xmlmember.tail = '\n		'
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

		logging.warning2(_(u'{0}: unable to modify {1} for {2} {3}, not found '
			'in {4}.').format(stylize(ST_NAME, self.name),
				stylize(ST_ATTR, attrname), acttype,
				stylize(ST_NAME, uid), stylize(ST_PATH, self.paths.accounts)))
		return False
	def del_account(self, acttype, uid):
		""" delete the resource in the accounts file. """

		assert ltrace_func(TRACE_CALDAVD)

		for xmldata in self.data.accounts.findall(acttype):
			if xmldata.find('uid').text == uid:
				self.data.accounts.getroot().remove(xmldata)
				return True

		logging.warning2(_(u'{0}: unable to delete {1} {2}, not found in {3}.').format(
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
					#logging.warning2('boucle for : membre %s' % xmlmember.text )
					if xmlmember.text == login:
						xmldata.find('members').remove(xmlmember)
						return True

		logging.warning2(_(u'{0}: unable to delete user {1} from group {2}, '
			'not found in {3}.').format(stylize(ST_NAME, self.name),
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
	def user_post_add(self, *args, **kwargs):
		""" Create a caldavd user account and the associated calendar resource,
			then write the configuration and release the associated lock.
		"""

		assert ltrace_func(TRACE_CALDAVD)

		user     = kwargs.pop('user')
		password = kwargs.pop('password')

		# we don't deal with system accounts, they don't get calendar for free.
		if user.is_system:
			return True

		try:
			# create an internal guest group to hold R/O proxies.
			# do not call it 'gst-$USER' in case the user has the name of
			# a group, this would conflict with the genuine gst-$GROUP.
			"""gst_uid = '.org.%s.%s%s' % (self.name,
									LMC.configuration.groups.guest_prefix,
									user.login)"""

			if (
					self.add_user(uid=user.login,
									guid=str(uuid.uuid1()),
									password=password,
									name=user.gecos)):
				"""and
					self.add_group(uid=gst_uid,
									guid=str(uuid.uuid1()),
									name=_(u'R/O holder for user %s.')
										% user.login)
				and
					self.add_resource(uid=user.login,
									guid=str(uuid.uuid1()),
									name=user.gecos, type='users',
									gst_uid=gst_uid)"""

				self.__write_elements_and_reload()

			return True

		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
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
	def user_post_change_password(self, *args, **kwargs):
		""" Update the user's password in caldavd accounts file. """

		assert ltrace_func(TRACE_CALDAVD)

		user     = kwargs.pop('user')
		password = kwargs.pop('password')

		# we don't deal with system accounts, they don't get calendar for free.
		if user.is_system:
			return True

		try:
			if self.mod_account(acttype='user', uid=user.login,
							attrname='password', value=password):

				self.__write_elements_and_reload()
				#logging.progress('%s: changed user %s password.' % (
				#	self.name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
			print_exc()
			return False
	@events.handler_method
	@only_if_enabled
	def user_pre_del(self, *args, **kwargs):
		""" delete a user and its resource in the caldavd accounts file, then
			reload the service. """

		assert ltrace_func(TRACE_CALDAVD)

		user = kwargs.pop('user')

		# we don't deal with system accounts, they don't get calendar for free.
		if user.is_system:
			return True

		try:
			#TODO: self.locks.accounts.acquire()
			if (
					self.del_account(acttype='resource', uid=user.login)
				and
					self.del_account(acttype='group',
						uid='.org.%s.%s%s' % (self.name,
										LMC.configuration.groups.guest_prefix,
										user.login))
				and
					self.del_account(acttype='user', uid=user.login)
					):

				self.__write_elements_and_reload()
				#logging.progress('%s: deleted user and resource in %s.' % (
				#	self.name, self.paths.accounts))

			return True

		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
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
		""" Create a caldavd group account and the associated calendar resource,
			then write the configuration and release the associated lock.
		"""

		assert ltrace_func(TRACE_CALDAVD)

		group = kwargs.pop('group')

		if not (group.is_responsible or group.is_standard or group.is_guest):
			return

		resource_uuid = str(uuid.uuid1())
		try:
			if ( ldap_backend.active or 
				self.add_group(uid=group.name, guid=str(uuid.uuid1()),
								name=group.description)
				and
				(
					(
					group.is_standard
					and
					self.add_resource(uid="resource_"+group.name, guid=resource_uuid,
										name=group.description,
										type='groups',
										# we've got to construct the guest group
										# name, because the guest group doesn't
										# exist yet (it is created *after* the
										# standard group.
										gst_uid=group.guest_group.name)
					)
				)):
				"""
					 or (
					group.is_guest
					and
					self.add_resource(uid=group.name,
										guid=str(uuid.uuid1()),
										name=group.description, type='groups')
					)
				"""
				self.__write_elements_and_reload()

				# deal with proxies
				
				
				# the standard group ressource is the principal
				#principal = config.directory.recordWithShortName("resources", "resource_"+group.sortName)
				principal = principalForPrincipalID('resources:resource_'+group.name.replace('gst-', '').replace('rsp-',''))

				action_addProxy(principal, 'read', ('groups:gst-'+group.name))
				action_addProxy(principal, 'write', ('groups:rsp-'+group.name))
				action_addProxy(principal, 'write', ('groups:'+group.name))





				#logging.progress('%s: added group and resource in %s.' % (
				#	self.name, self.paths.accounts))

			return True

		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(stylize(ST_NAME, self.name), e))
			print_exc()
			return False
	@events.handler_method
	@only_if_enabled
	def group_pre_del(self, *args, **kwargs):
		""" delete a group and its resource in the caldavd accounts file, then
			reload the service. """

		assert ltrace_func(TRACE_CALDAVD)

		group = kwargs.pop('group')

		if not (group.is_standard or group.is_guest):
			return

		try:
			#TODO: self.locks.accounts.acquire()
			if (
				self.del_account(acttype='resource', uid=group.name)
				and
				self.del_account(acttype='group', uid=group.name)
				):

				self.__write_elements_and_reload()
				#logging.progress('%s: deleted group and resource in %s.' % (
				#	self.name, self.paths.accounts))

			return True

		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(
							stylize(ST_NAME, self.name), e))
			print_exc()
			return False
	@events.handler_method
	@only_if_enabled
	def group_pre_add_user(self, *args, **kwargs):
		""" Lock the accounts file in prevision of a change. """
		#return self.locks.accounts.acquire()
		return True
	@events.handler_method
	@only_if_enabled
	def group_post_add_user(self, *args, **kwargs):
		""" add a user to the member element of a group in the caldavd
			accounts file, then reload the service. """

		assert ltrace_func(TRACE_CALDAVD)

		group = kwargs.pop('group')
		user  = kwargs.pop('user')

		# we don't deal with system accounts, don't bother us with that.
		if user.is_system or not (group.is_standard or group.is_guest):
			return True

		try:
			#TODO: self.locks.accounts.acquire()
			if self.add_member(name=group.name, login=user.login):
				self.__write_elements_and_reload()
				#logging.progress('%s: added user %s in group %s in %s.' % (
				#	self.name, login, name, self.paths.accounts))

			return True
		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(
							stylize(ST_NAME, self.name), e))
			print_exc()
			return False
	@events.handler_method
	@only_if_enabled
	def group_pre_del_user(self, *args, **kwargs):
		""" delete a user from the members element of a group in the caldavd
			accounts file, then reload the service. """

		assert ltrace_func(TRACE_CALDAVD)

		group = kwargs.pop('group')
		user  = kwargs.pop('user')

		# we don't deal with system accounts, don't bother us with that.
		if user.is_system or not (group.is_standard or group.is_guest):
			return True


		#call manage_principals
		"""try:
			#TODO: self.locks.accounts.acquire()
			if self.del_member(name=group.name, login=user.login):
				self.__write_elements_and_reload()
				#logging.progress('%s: removed user %s from group %s in %s.' % (
				#	self.name, login, name, self.paths.accounts))

			return True
		except Exception, e:
			logging.warning(_(u'{0}: {1}').format(
							stylize(ST_NAME, self.name), e))
			print_exc()
			return False"""
	@events.handler_method
	@only_if_enabled
	def group_post_del_user(self, *args, **kwargs):
		""" Lock the accounts file in prevision of a change. """
		#return self.locks.accounts.acquire()
		return True
	def _cli_get(self, opts, args):
		""" TODO """
		return ''
	def _cli_get_parse_arguments(self):
		""" return get compatible args. """
		pass
	def _wmi_user_data(self, user, hostname, *args, **kwargs):
		""" return the calendar for a given user. """

		if user.is_system:
			return (None, None)

		return (_('Personnal calendar URI'),
			'<a href="CalDAV://{hostname}:{port}/'
			'calendars/resources/{login}/calendar">'
			'CalDAV://{hostname}:{port}/calendars/'
			'resources/{login}/calendar</a>'.format(
				hostname=hostname,
				port=self.data.configuration['HTTPPort'],
				login=user.login))
	def _wmi_group_data(self, group, templates, hostname, *args, **kwargs):
		""" return the calendar for a given user. """

		if not (group.is_standard or group.is_guest):
			return templates[1]

		return templates[0] % (_('Group calendar URI'),
			'<a href="CalDAV://{hostname}:{port}/'
			'calendars/resources/{name}/calendar">'
			'CalDAV://{hostname}:{port}/calendars/'
			'resources/{name}/calendar</a>'.format(
					hostname=hostname,
					port=self.data.configuration['HTTPPort'],
					name=group.name))












