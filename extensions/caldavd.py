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

from licorn.foundations           import logging, pyutils, readers, writers, fsapi
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
		else:
			logging.warning2('Caldavd extension not available because caldavd '
				'not installed.')

		return self.available
	def check(self, batch=False, auto_answer=None):
		""" Check eveything needed for the caldavd extension and service.
			Currently we just check ``chmod`` on caldavd files (because they
			contain user passwords in clear-text). """

		for filename in self.paths:
			if os.path.exists(filename):
				os.chmod(filename, 0640)
	def __parse_files(self):
		""" Create locks and load all caldavd data files. """

		#self.locks = LicornConfigObject()
		#self.locks.accounts = FileLock(self.paths.accounts)
		#self.locks.configuration = FileLock(self.paths.configuration)
		#self.locks.sudoers = FileLock(self.paths.sudoers)

		self.data.service_defaults = readers.shell_conf_load_dict(
					self.paths.service_defaults)

		self.data.accounts = readers.xml_load_tree(self.paths.accounts)

		self.data.configuration = readers.plist_load_dict(
											self.paths.configuration)

		# TODO: implement sudoers if needed.
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
			return True

		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
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
			return True

		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def __strip_examples(self):
		""" TODO. """

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

		fsapi.backup_file(self.paths.service_defaults)
		writers.shell_conf_write_from_dict(self.data.service_defaults,
			self.paths.service_defaults)
		os.chmod(self.paths.service_defaults, 0640)
	def __write_accounts(self):
		""" Write the XML accounts file to disk, after having backed it up. """

		# TODO: assert self.locks.accounts.is_locked()
		fsapi.backup_file(self.paths.accounts)
		writers.xml_write_from_tree(self.data.accounts, self.paths.accounts)
		os.chmod(self.paths.accounts, 0640)
		# TODO: self.locks.accounts.release()
	def __write_accounts_and_reload(self):
		""" Write the accounts file and reload the caldavd service.	A reload
			is needed, else caldavd doesn't see new user accounts and resources.
		"""

		self.__write_accounts()

		# fu...ing caldavd service which doesn't understand reload.
		self.service(svccmds.RESTART)
	def users_load(self):
		""" eventually load users-related data. Currently this method does
			nothing. """

		assert ltrace('caldavd', '| users_load()')
		return True
	def groups_load(self):
		""" eventually load groups-related data. Currently this method does
			nothing. """

		assert ltrace('caldavd', '| groups_load()')
		return True
	def __create_account(self, acttype, uid, guid, name):
		""" Create the XML ElementTree object base for a caldav account (can be
			anything), then return it for the caller to add specific
			SubElements to it.
		"""

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

		assert ltrace('caldavd', '> add_user(%s)' % uid)

		user = self.__create_account('user', uid, guid, name)

		xmlpwd = ET.SubElement(user, 'password')
		xmlpwd.text = password
		xmlpwd.tail = '\n'

		assert ltrace('caldavd', '< add_user(%s)' % uid)
	def add_resource(self, uid, guid, name, **kwargs):
		""" Create a caldav resource account. """

		assert ltrace('caldavd', '> add_resource(%s)' % uid)

		resource = self.__create_account('resource', uid, guid, name)

		xmlproxies = ET.SubElement(resource, 'proxies')
		xmlproxies.text = '\n		'
		xmlproxies.tail = '\n'

		xmlmember = ET.SubElement(xmlproxies, 'member')
		xmlmember.set('type', 'users')
		xmlmember.text = uid
		xmlmember.tail = '\n	'

		assert ltrace('caldavd', '< add_resource(%s)' % uid)
	def mod_account(self, acttype, uid, attrname, value):
		""" Alter a caldav account: find a given attribute, then modify its
			value, then write the configuration to disk and reload the service.
		"""

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

		for xmldata in self.data.accounts.findall(acttype):
			if xmldata.find('uid').text == uid:
				self.data.accounts.getroot().remove(xmldata)
				return True

		logging.warning2('%s: unable to delete %s %s, not found in %s.' %
			(self.name, acttype, uid, self.paths.accounts))
		return False
	def user_pre_add_callback(self, **kwargs):
		""" Lock the accounts file in prevision of a change. """
		#return self.locks.accounts.acquire()
		pass
	def user_post_add_callback(self, login, password, gecos, **kwargs):
		""" Create a caldavd user account and the associated calendar resource,
			then write the configuration and release the associated lock.
		"""

		assert ltrace('caldavd', '| user_post_add_callback(%s)' % login)

		try:
			self.add_user(uid=login, guid=str(uuid.uuid1()),
							password=password, name=gecos)
			self.add_resource(uid=login, guid=str(uuid.uuid1()), name=gecos)
			self.__write_accounts_and_reload()
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def user_pre_change_password_callback(self, **kwargs):
		""" """
		assert ltrace('caldavd', '| user_pre_change_password_callback(%s)' %
																		login)
		# TODO: return self.locks.accounts.acquire()
		pass
	def user_post_change_password_callback(self, login, password, **kwargs):
		""" Update the user's password in caldavd accounts file. """

		assert ltrace('caldavd', '| user_post_change_password_callback(%s)' %
																		login)

		try:
			self.mod_account('user', login, 'password', password)
			self.__write_accounts_and_reload()
			logging.progress('%s: changed user %s password.' % (
				self.name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def user_pre_del_callback(self, login, **kwargs):
		""" delete a user and its resource in the caldavd accounts file, then
			reload the service. """

		assert ltrace('caldavd', '| user_pre_del_callback(%s)' % login)

		try:
			#TODO: self.locks.accounts.acquire()
			self.del_account('resource', login)
			self.del_account('user', login)
			self.__write_accounts_and_reload()
			logging.progress('%s: deleted user and resource in %s.' % (
				self.name, self.paths.accounts))
			return True
		except Exception, e:
			logging.warning('%s: %s' % (self.name, e))
			print_exc()
			return False
	def add_delegate(self):
		""" TODO. """
		pass
	def del_delegate(self):
		""" TODO. """
		pass
	def get_CLI(self, opts, args):
		""" TODO """
		return ''
	def get_parse_arguments(self):
		""" return get compatible args. """

		pass
