# -*- coding: utf-8 -*-
"""
Licorn extensions: caldavd - http://docs.licorn.org/extensions/caldavd.html

:copyright:
	* 2010 Olivier Cortès <oc@meta-it.fr>
	* 2010 Guillaume Masson <guillaume.masson@meta-it.fr>

:license: GNU GPL version 2

"""

import os, uuid
from gettext import gettext as _
from traceback import print_exc
import xml.etree.ElementTree as ET

from licorn.foundations           import logging, pyutils, fsapi, network
from licorn.foundations           import readers, writers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, MixedDictObject, LicornConfigObject
from licorn.foundations.classes   import FileLock
from licorn.foundations.constants import gamin_events, distros, services, svccmds

from licorn.core               import LMC
from licorn.extensions         import ServiceExtension

class CaldavdExtension(Singleton, ServiceExtension):
	""" Handles Apple Calendar Server configuration and service.

		.. versionadded:: 1.2.4

	"""
	def __init__(self):
		assert ltrace('extensions', '| CaldavdExtension.__init__()')
		ServiceExtension.__init__(self, name='caldavd',
			service_name='calendarserver',
			service_type=services.SYSV,
			service_long=True
		)

		# nothing to do on the client side.
		self.server_only        = True

		# users and groups can get calendars.
		self.controllers_compat = ['users', 'groups']

		self.paths.main_dir      = '/etc/caldavd'
		self.paths.accounts      = self.paths.main_dir + '/accounts.xml'
		self.paths.configuration = self.paths.main_dir + '/caldavd.plist'
		self.paths.sudoers       = self.paths.main_dir + '/sudoers.plist'
		self.paths.pid_file      = '/var/run/caldavd/caldavd.pid'

		self.data = LicornConfigObject()

		if LMC.configuration.distro in (distros.UBUNTU, distros.LICORN,
					distros.DEBIAN):
			self.paths.service_defaults = '/etc/default/calendarserver'
	def initialize(self):
		""" Set :attr:`self.available` to ``True`` if calendarserver service
			is installed and all of its data files load properly.
		"""

		self.available = False

		if os.path.exists(self.paths.main_dir):

			try:
				self.__parse_files()
				self.available = True
			except ImportError, e:
				logging.warning2(
					'Caldavd extension not available because %s.' % e)
			except (IOError, OSError), e:
				if e.errno == 2:
					logging.warning2(
						'Caldavd extension not yet available because %s '
						'(calendarserver is probably installing, try again'
						'later).' % e)
				else:
					raise e
		else:
			logging.warning2('Caldavd extension not available because caldavd '
				'not installed.')

		return self.available
	def check(self, batch=False, auto_answer=None):
		""" Check eveything needed for the caldavd extension and service.
			Currently we just check ``chmod`` on caldavd files (because they
			contain user passwords in clear-text). """

		for filename in self.paths:
			if (os.path.exists(filename) and filename != self.paths.main_dir):
				os.chmod(filename, 0640)
	def __parse_files(self):
		""" Create locks and load all caldavd data files. """

		# TODO: implement sudoers if needed.

		#self.locks = LicornConfigObject()
		#self.locks.accounts = FileLock(self.paths.accounts)
		#self.locks.configuration = FileLock(self.paths.configuration)
		#self.locks.sudoers = FileLock(self.paths.sudoers)
		self.data.service_defaults = readers.shell_conf_load_dict(
					self.paths.service_defaults)

		self.data.accounts = readers.xml_load_tree(self.paths.accounts)

		self.data.configuration = readers.plist_load_dict(
											self.paths.configuration)
	def is_enabled(self):
		""" Return ``True`` if the directive ``start_calendarserver`` is set to
			``yes`` in the service configuration file
			(:file:`/etc/default/calendarserver` on Debian/Ubuntu).

			If the directive doesn't exist yet, we consider the service as
			freshly installed: we try to strip examples from the accounts file
			if they exists, and return ``False`` because the service is not
			yet enabled.
		"""
		try:
			if self.data.service_defaults['start_calendarserver'] \
															in ('yes', 'YES'):

				# ensure the service is running, if it should be.
				if not self.running(self.paths.pid_file):
					self.service(svccmds.START)
				assert ltrace(self.name, '| is_enabled() → True')
				return True
		except KeyError:
			self.data.service_defaults['start_calendarserver'] = 'no'
			self.__write_defaults()
			self.__strip_examples()
			assert ltrace(self.name, '| is_enabled() → False')
			return False
	def enable(self):
		""" Set the directive ``start_calendarserver`` to ``yes`` in the
			service configuration file, then start the caldavd service and
			return ``True`` if everything succeeds, else ``False``.
		"""

		try:
			self.data.service_defaults['start_calendarserver'] = 'yes'
			self.__write_defaults()
			self.start()
			assert ltrace(self.name, '| enable() → True')
			return True

		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			assert ltrace(self.name, '| enable() → False')
			return False
	def disable(self):
		""" Stop the caldavd service, then set the directive
			``start_calendarserver`` to ``no`` in the service configuration
			file and return ``True`` if everything succeeds, else ``False``.
		"""

		try:
			self.stop()
			self.data.service_defaults['start_calendarserver'] = 'no'
			self.__write_defaults()
			assert ltrace(self.name, '| disable() → True')
			return True

		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			assert ltrace(self.name, '| disable() → False')
			return False
	def __strip_examples(self):
		""" TODO. """
		assert ltrace(self.name, '| __strip_example()')

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
		assert ltrace(self.name, '| __write_defaults()')

		fsapi.backup_file(self.paths.service_defaults)
		writers.shell_conf_write_from_dict(self.data.service_defaults,
			self.paths.service_defaults)
		os.chmod(self.paths.service_defaults, 0640)
	def __write_accounts(self):
		""" Write the XML accounts file to disk, after having backed it up. """
		assert ltrace(self.name, '| __write_accounts()')

		# TODO: assert self.locks.accounts.is_locked()
		fsapi.backup_file(self.paths.accounts)
		writers.xml_write_from_tree(self.data.accounts, self.paths.accounts)
		os.chmod(self.paths.accounts, 0640)
		# TODO: self.locks.accounts.release()
		return True
	def __write_accounts_and_reload(self):
		""" Write the accounts file and reload the caldavd service.	A reload
			is needed, else caldavd doesn't see new user accounts and resources.
		"""
		assert ltrace(self.name, '| __write_accounts_and_reload()')

		self.__write_accounts()

		# fu...ing caldavd service which doesn't understand reload.
		self.service(svccmds.RESTART)
	def users_load(self):
		""" eventually load users-related data. Currently this method does
			nothing. """

		assert ltrace(self.name, '| users_load()')
		return True
	def groups_load(self):
		""" eventually load groups-related data. Currently this method does
			nothing. """

		assert ltrace(self.name, '| groups_load()')
		return True
	def __create_account(self, acttype, uid, guid, name):
		""" Create the XML ElementTree object base for a caldav account (can be
			anything), then return it for the caller to add specific
			SubElements to it.
		"""
		assert ltrace(self.name, '| __create_account(%s, %s, %s, %s)' % (
			acttype, uid, guid, name))

		account = ET.SubElement(self.data.accounts.getroot(), acttype)
		account.text = '\n	'
		account.tail = '\n'

		xmluid = ET.SubElement(account, 'uid')
		xmluid.text = uid
		xmluid.tail = '\n	'

		xmlguid = ET.SubElement(account, 'guid')
		xmlguid.text = guid
		xmlguid.tail = '\n	'

		xmlname = ET.SubElement(account, 'name')
		xmlname.text = name
		xmlname.tail = '\n	'

		return account
	def add_user(self, uid, guid, name, password, **kwargs):
		""" Create a caldav user account. """

		assert ltrace(self.name, '| add_user(%s, %s, %s)' % (uid, guid, name))

		user = self.__create_account('user', uid, guid, name)

		xmlpwd = ET.SubElement(user, 'password')
		xmlpwd.text = password
		xmlpwd.tail = '\n'
		return True
	def add_group(self, uid, guid, name, **kwargs):
		""" Create a caldav group account. """

		assert ltrace(self.name, '| add_group(%s, %s, %s)' % (uid, guid, name))

		group = self.__create_account('group', uid, guid, name)

		xmlmembers = ET.SubElement(group, 'members')
		xmlmembers.text = '\n	'
		xmlmembers.tail = '\n'
		return True
	def add_resource(self, uid, guid, name, type, gst_uid, **kwargs):
		""" Create a caldav resource account. """

		assert ltrace(self.name, '| add_resource(%s, %s, %s, %s, %s)' % (
			uid, guid, name, type, gst_uid))

		resource = self.__create_account('resource', uid, guid, name)

		xmlproxies = ET.SubElement(resource, 'proxies')
		xmlproxies.text = '\n		'
		xmlproxies.tail = '\n'

		xmlmember = ET.SubElement(xmlproxies, 'member')
		xmlmember.set('type', type)
		xmlmember.text = uid
		xmlmember.tail = '\n	'

		xmlroproxies = ET.SubElement(resource, 'read-only-proxies')
		xmlroproxies.text = '\n		'
		xmlroproxies.tail = '\n'

		xmlromember = ET.SubElement(xmlroproxies, 'member')
		xmlromember.set('type', type)
		xmlromember.text = gst_uid
		xmlromember.tail = '\n	'

		return True
	def add_member(self, name, login, **kwargs):
		""" Create a new entry in the members element of a group. """

		assert ltrace(self.name, '| add_member(%s, %s)' % (login, name))

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
		assert ltrace(self.name, '| mod_account(%s, %s, %s, %s)' % (acttype,
				uid, attrname, value))

		for xmldata in self.data.accounts.findall(acttype):
			if xmldata.find('uid').text == uid:
				xmlattr = xmldata.find(attrname)
				xmlattr.text = value
				return True

		logging.warning2('%s: unable to modify %s for %s %s, not found '
			'in %s.' % (self.name, attrname, acttype, uid, self.paths.accounts))
		return False
	def del_account(self, acttype, uid):
		""" delete the resource in the accounts file. """

		assert ltrace(self.name, '| del_account(%s, %s)' % (acttype, uid))

		for xmldata in self.data.accounts.findall(acttype):
			if xmldata.find('uid').text == uid:
				self.data.accounts.getroot().remove(xmldata)
				return True

		logging.warning2('%s: unable to delete %s %s, not found in %s.' %
			(self.name, acttype, uid, self.paths.accounts))
		return False
	def del_member(self, name, login):
		""" delete the user from the members of the group
			in the accounts file. """

		assert ltrace(self.name, '| del_member(%s from %s)' % (login, name))

		for xmldata in self.data.accounts.findall('group'):
			if xmldata.find('uid').text == name:
				for xmlmember in xmldata.findall('members/member'):
					#logging.warning2('boucle for : membre %s' % xmlmember.text )
					if xmlmember.text == login:
						xmldata.find('members').remove(xmlmember)
						return True

		logging.warning2('%s: unable to delete user %s from %s, '
			'not found in %s.' %
				(self.name, login, name, self.paths.accounts))
		return False
	def user_pre_add_callback(self, **kwargs):
		""" Lock the accounts file in prevision of a change. """
		#return self.locks.accounts.acquire()
		return True
	def user_post_add_callback(self, login, password, gecos, system, **kwargs):
		""" Create a caldavd user account and the associated calendar resource,
			then write the configuration and release the associated lock.
		"""

		assert ltrace(self.name, '| user_post_add_callback(%s)' % login)

		# we don't deal with system accounts, they don't get calendar for free.
		if system:
			return True

		try:
			# create an internal guest group to hold R/O proxies
			gst_uid = LMC.configuration.groups.guest_prefix + login

			if (
					self.add_user(uid=login, guid=str(uuid.uuid1()),
									password=password, name=gecos)
				and
					self.add_group(uid=gst_uid, guid=str(uuid.uuid1()),
										name="R/O holder for user %s" % login)
				and
					self.add_resource(uid=login, guid=str(uuid.uuid1()),
									name=gecos, type='users', gst_uid=gst_uid)
					):
				self.__write_accounts_and_reload()
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def user_pre_change_password_callback(self, **kwargs):
		""" """
		assert ltrace(self.name, '| user_pre_change_password_callback(%s)' %
																		login)
		# TODO: return self.locks.accounts.acquire()
		return True
	def user_post_change_password_callback(self, login, password, system, **kwargs):
		""" Update the user's password in caldavd accounts file. """

		assert ltrace(self.name, '| user_post_change_password_callback(%s)' %
																		login)

		# we don't deal with system accounts, they don't get calendar for free.
		if system:
			return True

		try:
			if self.mod_account(acttype='user', uid=login,
							attrname='password', value=password):
				self.__write_accounts_and_reload()
				#logging.progress('%s: changed user %s password.' % (
				#	self.name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def user_pre_del_callback(self, login, system, **kwargs):
		""" delete a user and its resource in the caldavd accounts file, then
			reload the service. """

		assert ltrace(self.name, '| user_pre_del_callback(%s)' % login)

		# we don't deal with system accounts, they don't get calendar for free.
		if system:
			return True

		try:
			#TODO: self.locks.accounts.acquire()
			if (
					self.del_account(acttype='resource', uid=login)
				and
					self.del_account(acttype='user', uid=login)
					):
				self.__write_accounts_and_reload()
				#logging.progress('%s: deleted user and resource in %s.' % (
				#	self.name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def group_pre_add_callback(self, **kwargs):
		""" Lock the accounts file in prevision of a change. """
		#return self.locks.accounts.acquire()
		return True
	def group_post_add_callback(self, name, description, system, **kwargs):
		""" Create a caldavd group account and the associated calendar resource,
			then write the configuration and release the associated lock.
		"""

		assert ltrace(self.name, '| group_post_add_callback(%s)' % name)

		# we don't deal with system groups, they don't get calendar for free.
		group, rw_access = self.usable_group(name, system)

		if group is None:
			return True

		# we do not create direct entries for gst-* and rsp-*
		if not rw_access or (rw_access and name != group):
			return

		try:
			# create an internal guest group to hold R/O proxies
			gst_uid = LMC.configuration.groups.guest_prefix + name

			if (
					self.add_group(uid=name, guid=str(uuid.uuid1()),
								name=description)
				and
					self.add_group(uid=gst_uid, guid=str(uuid.uuid1()),
							name="R/O holder for group %s" % name)
				and
					self.add_resource(uid=name, guid=str(uuid.uuid1()),
							name=description, type='groups', gst_uid=gst_uid)
					):
				self.__write_accounts_and_reload()
				#logging.progress('%s: added group and resource in %s.' % (
				#	self.name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def group_pre_del_callback(self, name, system, **kwargs):
		""" delete a group and its resource in the caldavd accounts file, then
			reload the service. """

		assert ltrace(self.name, '| group_pre_del_callback(%s)' % name)

		# we don't deal with system groups, they don't get calendar for free.
		if system:
			return

		try:
			#TODO: self.locks.accounts.acquire()
			if (
					self.del_account(acttype='resource', uid=name)
				and
					self.del_account(acttype='group', uid=name)
				and
				# remove the hidden group that holds R/O proxies
					self.del_account(acttype='group',
						uid=LMC.configuration.groups.guest_prefix + name)
					):
				self.__write_accounts_and_reload()
				#logging.progress('%s: deleted group and resource in %s.' % (
				#	self.name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def group_pre_add_user_callback(self, **kwargs):
		""" Lock the accounts file in prevision of a change. """
		#return self.locks.accounts.acquire()
		return True
	def group_post_add_user_callback(self, name, system, uid, login, **kwargs):
		""" add a user to the member element of a group in the caldavd
			accounts file, then reload the service. """

		assert ltrace(self.name, '| group_post_add_user_callback(%s in %s)'
			% (login, name))

		# we don't deal with system accounts, don't bother us with that.
		if LMC.users.is_system_uid(uid):
			return True

		# we don't deal with system groups, they don't get calendar for free.
		group, rw_access = self.usable_group(name, system)

		if group is None:
			return True

		try:

			#TODO: self.locks.accounts.acquire()
			if self.add_member(name=group if rw_access else name, login=login):
				self.__write_accounts_and_reload()
				#logging.progress('%s: added user %s in group %s in %s.' % (
				#	self.name, login, name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def group_pre_del_user_callback(self, name, system, uid, login, **kwargs):
		""" delete a user from the members element of a group in the caldavd
			accounts file, then reload the service. """

		assert ltrace(self.name, '| group_pre_del_user_callback(%s from %s)'
			% (login, name))

		# we don't deal with system accounts, don't bother us with that.
		if LMC.users.is_system_uid(uid):
			return True

		# we don't deal with system groups, they don't get calendar for free.
		group, rw_access = self.usable_group(name, system)

		if group is None:
			return True

		try:
			#TODO: self.locks.accounts.acquire()
			if self.del_member(name=group if rw_access else name, login=login):
				self.__write_accounts_and_reload()
				#logging.progress('%s: removed user %s from group %s in %s.' % (
				#	self.name, login, name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def group_post_del_user_callback(self, **kwargs):
		""" Lock the accounts file in prevision of a change. """
		#return self.locks.accounts.acquire()
		return True
	def add_delegate(self):
		""" TODO. """
		pass
	def del_delegate(self):
		""" TODO. """
		pass
	def _cli_get(self, opts, args):
		""" TODO """
		return ''
	def _cli_get_parse_arguments(self):
		""" return get compatible args. """

		pass
	def usable_group(self, name, system):

		if system:
			for prefix, rw_access in (
					(LMC.configuration.groups.resp_prefix, True),
					(LMC.configuration.groups.guest_prefix, False)
				):
				if name.startswith(prefix):
					return name[len(prefix):], rw_access
		else:
			return name, True

		return None, None
	def _wmi_user_data(self, login, system, **kwargs):
		""" return the calendar for a given user. """

		if system:
			return (None, None)

		hostname = network.get_local_hostname()
		port     = self.data.configuration['HTTPPort']

		return (_('Personnal calendar URI'),
			'<a href="CalDAV://%s:%s/calendars/resources/%s/calendar">'
			'CalDAV://%s:%s/calendars/resources/%s/calendar</a>' % (
					hostname, port, login,
					hostname, port, login
				)
		)
	def _wmi_group_data(self, name, system, templates, **kwargs):
		""" return the calendar for a given user. """

		group, rw_access = self.usable_group(name, system)

		if group is None:
			return templates[1]

		hostname = network.get_local_hostname()
		port     = self.data.configuration['HTTPPort']

		return templates[0] % (_('Group calendar URI'),
			'<a href="CalDAV://%s:%s/calendars/resources/%s/calendar">'
			'CalDAV://%s:%s/calendars/resources/%s/calendar</a>' % (
					hostname, port, group,
					hostname, port, group
				)
			)
