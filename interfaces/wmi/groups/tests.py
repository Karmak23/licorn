# -*- coding: utf-8 -*-
"""
Licorn® WMI - users views tests

:copyright:
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
	* 2012 Olivier Cortès <olive@licorn.org>
:license: GNU GPL version 2
"""
import sys, urllib, tempfile, gc

from django.utils	    import unittest
from django.test.client import Client

from licorn.foundations           import logging
from licorn.foundations.ltrace    import *
from licorn.foundations.constants import relation
from licorn.core 		          import LMC

# users used to log in the wmi
manager_user_login_test = 'wmitest-staff'
manager_user_passw_test = 'wmitest-staff'

std_user_login_test = 'wmitest-standard'
std_user_passw_test = 'wmitest-standard'


# users to test on
standard_user_login    = 'wmiTs-standard-user'
manager_user_login     = 'wmiTs-manager-user'
admin_user_login       = 'wmiTs-admin-user'
# groups to test on
standard_group_name    = 'wmiTs-standard-group'
privileged_group_name  = 'wmiTs-privileged-group'
system_group_name      = 'wmiTs-system-group'

# shortcuts
uqp = urllib.quote_plus

gecos_to_test = [ 'newGecosFromTS', 'Lucberné', 'Luçbernet', "pléïn d'àcçèñtß" ]

class testUsers(unittest.TestCase):
	"""
	Users URLs:

		/													index html
		/message/part/uid 									messages html
		/new 												new page html
		/edit/login 										edit page html
			 /uid
		/view/login 										view page html
			 /uid

		/create 											create post action
		/delete/uid/no_archive 								delete action
		/mod/uid/action/value								mod action

		/massive/action/uids/value 							massive action

		/import/confirm 									import post action
																+ get page html
		/upload 											upload post action
		/check_pwd_strenght/password						check password action
		/generate_pwd										return random password
	"""

	def __init__(self, *args, **kwargs):
		super(testUsers, self).__init__(*args, **kwargs)

	@classmethod
	def get_name(cls, name, suffix):
		return name + '_' + suffix
	@classmethod
	def setup_tests_environnement(cls, suffix):
		""" setup tests environnement :
				- add tests users (standard/manager/admin) to run tests on.
				- add tests groups (standard/privileged/system) to run tests on.
		"""
		# create the standard test user
		try:
			cls.standard_user = LMC.users.by_login(cls.get_name(standard_user_login, suffix))
		except KeyError:
			cls.standard_user, dummy = LMC.users.add_User(
								login=cls.get_name(standard_user_login, suffix),
								gecos=u'Django TS Account - test user',
								in_groups=[]
							)

		# create the manager test user
		try:
			cls.manager_user = LMC.users.by_login(cls.get_name(manager_user_login, suffix))

		except KeyError:
			cls.manager_user, dummy = LMC.users.add_User(
								login=cls.get_name(manager_user_login, suffix),
								gecos=u'Django TS Account - test licorn-wmi user',
								password="not_so_random",
								in_groups=[
									LMC.groups.by_name('licorn-wmi').gidNumber
									]
							)
		# create the admin test user
		try:
			cls.admin_user = LMC.users.by_login(cls.get_name(admin_user_login, suffix))

		except KeyError:
			cls.admin_user, dummy = LMC.users.add_User(
								login=cls.get_name(admin_user_login, suffix),
								gecos=u'Django TS Account - test admins user',
								password="not_so_random",
								in_groups=[
									LMC.groups.by_name('admins').gidNumber
									]
							)

		# create the standard group
		try:
			cls.standard_group = LMC.groups.by_name(cls.get_name(standard_group_name, suffix))

		except KeyError:
			cls.standard_group = LMC.groups.add_Group(name=cls.get_name(standard_group_name, suffix))

		# create the system group
		try:
			cls.system_group = LMC.groups.by_name(cls.get_name(system_group_name, suffix))

		except KeyError:
			cls.system_group = LMC.groups.add_Group(name=cls.get_name(system_group_name, suffix),
														system=True)

		# create the system group
		try:
			cls.privileged_group = LMC.groups.by_name(cls.get_name(privileged_group_name, suffix))

		except KeyError:
			cls.privileged_group = LMC.groups.add_Group(
				name=cls.get_name(privileged_group_name, suffix),
				system=True)

		LMC.privileges.add([cls.privileged_group])

	@classmethod
	def setUpClass(cls, suffix):
		cls.setup_tests_environnement(suffix=suffix)

	@classmethod
	def tearDownClass(cls):
		""" remove the test environnememt """
		users_to_del = [ cls.standard_user, cls.manager_user, cls.admin_user]

		groups_to_del = [ cls.standard_group, cls.system_group,
											cls.privileged_group ]

		for u in users_to_del:
			LMC.users.del_User(u, no_archive=True)

		for g in groups_to_del:
			LMC.groups.del_Group(g, no_archive=True)

		# we must delete everything, else they won't be garbage collected
		# immediately and next creation will fail (#769).
		del u, g, cls.manager_user, cls.standard_user, cls.admin_user, \
			cls.standard_group, cls.system_group, cls.privileged_group, \
			users_to_del, groups_to_del

		gc.collect()

class testWmiUsers(testUsers):

	""" Things ALLOWED for an licorn-wmi user on users:
			* on ADMINS account :
				- nothing
			* on his OWN account
				- modify everythings, except things listed in FORBIDDEN list
			* on LICORN-WMI account :
				- only modify groups membership except for licorn-wmi group
			* on STANDARD account :
				- modify everythings


		Things FORBIDDEN for an licorn-wmi user on users:
			* on ADMINS account :
				- modify/delete
			* on his OWN account
				- delete his own account
				- remove himself from licorn-wmi group
				- lock/unlock his own account
			* on LICORN-WMI account :
				- remove a licorn-wmi member from licorn-wmi
				- modify anything else than group membership (cannot mod gecos, pssw ...)
			* on STANDARD account :
				- nothing
	 """

	@classmethod
	def setUpClass(cls, *args, **kwargs):
		""" setup the environnement needed to run these tests """
		super(testWmiUsers, cls).setUpClass(suffix='1', *args, **kwargs)

		# create the manager user we will log in with
		try:
			cls.manager = LMC.users.by_login(manager_user_login_test)

		except KeyError:
			cls.manager, dummy = LMC.users.add_User(
								login=manager_user_login_test,
								gecos=u'Django TS Account - test licorn-wmi user',
								password=manager_user_passw_test,
								in_groups=[
									LMC.groups.by_name('licorn-wmi').gidNumber
									]
							)

	@classmethod
	def tearDownClass(cls, *args, **kwargs):
		super(testWmiUsers, cls).tearDownClass(*args, **kwargs)

		# remove our user used to log in as manager
		LMC.users.del_User(cls.manager, no_archive=True)
		del cls.manager

	def setUp(self):

		# log in our client object
		self.client = Client()
		logged_in = self.client.login(username=manager_user_login_test,
									password=manager_user_passw_test)
		self.failUnless(logged_in, 'Could not log in!')

	def tearDown(self):
		pass

	def test_manager_can_delete_standard_user(self):

		uid_to_del   = self.standard_user.uidNumber
		login_to_del = self.standard_user.login

		del self.__class__.standard_user

		r = self.client.get('/users/delete/{0}/False'.format(uid_to_del))
		self.assertEqual(r.status_code, 200)

		self.assertEqual(uid_to_del in LMC.users.keys(), False)

		logging.notice('>>> %s: %s %s' % (login_to_del,
				sys.getrefcount(LMC.users.by_login(login_to_del)),
				gc.get_referrers(LMC.users.by_login(login_to_del))
				)
			)

		for objekt in gc.get_referrers(LMC.users.by_login(login_to_del)):
			lprint(objekt)
			for obj2 in gc.get_referrers(objekt):
				lprint(obj2)
				for obj3 in gc.get_referrers(obj2):
					lprint(obj3)

		# TODO: re-activate this one when #769 is fixed.
		self.assertEqual(login_to_del in LMC.users.logins, False)

		# Recreate the standard_user, it should have been deleted
		try:
			# try/except to because of #769
			# TODO: remove this try/Except when #769 is fixed.
			self.__class__.standard_user = LMC.users.by_login(standard_user_login)

		except KeyError:
			self.__class__.standard_user, dummy = LMC.users.add_User(
								login=standard_user_login,
								gecos=u'Django TS Account - test user',
								password="not_so_random",
								in_groups=[]
							)

		#logging.notice('>>> %s %s' % (self.__class__.__name__, self.__class__.standard_user))
