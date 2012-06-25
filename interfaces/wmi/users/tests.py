# -*- coding: utf-8 -*-
"""
Licorn® WMI - users views tests

:copyright:
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
	* 2012 Olivier Cortès <olive@licorn.org>
:license: GNU GPL version 2
"""
import urllib, tempfile

from django.utils	    import unittest
from django.test.client import Client

from licorn.foundations.constants	  import relation
from licorn.core 		              import LMC

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
standard_group_name   = 'wmiTs-standard-group'
privileged_group_name = 'wmiTs-privileged-group'
system_group_name     = 'wmiTs-system-group'


gecos_to_test = [ 'newGecosFromTS', 'Lucberné', 'Luçbernet', 'pléïn d\'àcçèñt']

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
			cls.standard_user, pwd = LMC.users.add_User(
								login=cls.get_name(standard_user_login, suffix),
								gecos=u'Django TS Account - test user',
								in_groups=[]
							)
			del pwd

		# create the manager test user
		try:
			cls.manager_user = LMC.users.by_login(cls.get_name(manager_user_login, suffix)) 
		except KeyError:
			cls.manager_user, pwd = LMC.users.add_User(
								login=cls.get_name(manager_user_login, suffix),
								gecos=u'Django TS Account - test licorn-wmi user',
								password="random",
								in_groups=[
									LMC.groups.by_name('licorn-wmi').gidNumber
									]
							)
			del pwd

		# create the admin test user
		try:
			cls.admin_user = LMC.users.by_login(cls.get_name(admin_user_login, suffix)) 
		except KeyError:
			cls.admin_user, pwd = LMC.users.add_User(
								login=cls.get_name(admin_user_login, suffix),
								gecos=u'Django TS Account - test admins user',
								password="random",
								in_groups=[
									LMC.groups.by_name('admins').gidNumber
									]
							)
			del pwd

		
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
			cls.privileged_group]

		for u in users_to_del:
			LMC.users.del_User(u, no_archive=True)

		for g in groups_to_del:
			LMC.groups.del_Group(g, no_archive=True)
		
		# we must delete it here too, else it won't be garbage collected
		# and next creation will fail.
		
		del cls.manager_user, cls.standard_user, cls.admin_user, \
			cls.standard_group, cls.system_group, cls.privileged_group
		
class testUsersAnonymous(testUsers):
	@classmethod
	def setUpClass(cls, *args, **kwargs):
		""" setup the environnement needed to run these tests """
		super(testUsersAnonymous, cls).setUpClass(suffix='0', *args, **kwargs)

	@classmethod
	def tearDownClass(cls, *args, **kwargs):
		super(testUsersAnonymous, cls).tearDownClass(*args, **kwargs)

	def setUp(self):
		# Every test needs a client.
		self.client = Client()

	def tearDown(self):
		pass

	def test_uri_root_anonymous(self):
		r = self.client.get('/users', follow=True)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.request['PATH_INFO'], '/login/')
		self.assertEqual(r.request['QUERY_STRING'], 'next=%2Fusers%2F')

	def test_uri_gen_pass_anonymous(self):
		""" TODO: test return messages for different kind of errors. """

		r = self.client.get('/users/check_pwd_strenght')
		self.assertEqual(r.status_code, 404)

		r = self.client.get('/users/check_pwd_strenght/toto')
		self.assertEqual(r.status_code, 200)

		r = self.client.get('/users/check_pwd_strenght/blablablablabla')
		self.assertEqual(r.status_code, 200)

		r = self.client.get('/users/check_pwd_strenght/2aZ45_DCH34-Gh76')
		self.assertEqual(r.status_code, 200)

		r = self.client.get('/users/check_pwd_strenght/2aZ45_DCH34-Gh76')
		self.assertEqual(r.status_code, 200)

class testStandardUsers(testUsers):
	"""
		Things ALLOWED for a standard user:
			* on ADMINS account :
				- nothing
			* on LICORN-WMI account :
				- nothing
			* on STANDARD account :
				- nothing
			* on his OWN account 
				- modify ONLY its own gecos, shell, password.
				- can access to /users/check_pwd_strenght and 
								/users/generate_pwd


		Things FORBIDDEN for a standard user:
			* on ADMINS account :
				- everything
			* on LICORN-WMI account :
				- everything
			* on STANDARD account :
				- everything
			* on his OWN account 
				- everything except things listed in ALLOWED part
	"""
	@classmethod
	def setUpClass(cls, *args, **kwargs):
		""" setup the environnement needed to run these tests """
		super(testStandardUsers, cls).setUpClass(suffix='2', *args, **kwargs)

		# create the manager user we will log in with
		try:
			cls.standard = LMC.users.by_login(std_user_login_test) 
		except KeyError:
			cls.standard, pwd = LMC.users.add_User(
								login=std_user_login_test,
								gecos=u'Django TS Account - test licorn-wmi user',
								password=std_user_passw_test,
								in_groups=[]
							)
			del pwd


	@classmethod
	def tearDownClass(cls, *args, **kwargs):
		super(testStandardUsers, cls).tearDownClass(*args, **kwargs)

		# remove our user used to log in as manager
		LMC.users.del_User(cls.standard, no_archive=True)
		del cls.standard

	def setUp(self):
		self.client = Client()
		logged_in = self.client.login(username=std_user_login_test, 
									password=std_user_passw_test)
		self.failUnless(logged_in, 'Could not log in!')

	def tearDown(self):
		pass


	def test_standard_user_cannot_modify_admin(self):

		urls_forbidden = [
			'/users/delete/{0}/False', 
			
			'/users/mod/{0}/gecos/testtest',
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.default_shell),
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.shells[-1]),
			'/users/mod/{0}/password/testtest',
			'/users/mod/{0}/skel/'+urllib.quote_plus(LMC.configuration.users.default_skel),
			
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.GUEST),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.MEMBER),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.RESPONSIBLE),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.NO_MEMBERSHIP),			

			'/users/mod/{0}/lock',
			'/users/mod/{0}/unlock',
		]

		for url in urls_forbidden:
			r = self.client.get(url.format(self.admin_user.uid), follow=True)
			self.assertEqual(r.status_code, 403) 
	
	def test_standard_user_cannot_modify_manager(self):

		urls_forbidden = [
			'/users/delete/{0}/False', 
			
			'/users/mod/{0}/gecos/testtest',
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.default_shell),
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.shells[-1]),
			'/users/mod/{0}/password/testtest',
			'/users/mod/{0}/skel/'+urllib.quote_plus(LMC.configuration.users.default_skel),
			
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.GUEST),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.MEMBER),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.RESPONSIBLE),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.NO_MEMBERSHIP),

			'/users/mod/{0}/lock',
			'/users/mod/{0}/unlock',
		]

		for url in urls_forbidden:
			r = self.client.get(url.format(self.manager_user.uid), follow=True)
			self.assertEqual(r.status_code, 403) 

	def test_standard_user_cannot_modify_standard_user(self):

		urls_forbidden = [
			'/users/delete/{0}/False', 
			
			'/users/mod/{0}/gecos/testtest',
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.default_shell),
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.shells[-1]),
			'/users/mod/{0}/password/testtest'
			'/users/mod/{0}/skel/'+urllib.quote_plus(LMC.configuration.users.default_skel),
			
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.GUEST),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.MEMBER),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.RESPONSIBLE),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.NO_MEMBERSHIP),
			

			'/users/mod/{0}/lock',
			'/users/mod/{0}/unlock',
		]

		for url in urls_forbidden:
			r = self.client.get(url.format(self.standard_user.uid), follow=True)
			self.assertEqual(r.status_code, 403) 

	def test_standard_user_cannot_create_user(self):
		r = self.client.post('/users/create')
		self.assertEqual(r.status_code, 403) 

	def test_standard_user_cannot_import_user(self):
		r = self.client.post('/users/import/True')
		self.assertEqual(r.status_code, 403) 
	
	def test_standard_user_cannot_upload(self):
		r = self.client.post('/users/upload')
		self.assertEqual(r.status_code, 403) 

	def test_standard_user_cannot_view_users_pages(self):
		pages = [
			'/users/',
			'/users/view/toto',
			'/users/edit/toto',
			'/users/import',
			'/users/view/new',
		]

		for url in pages:
			r = self.client.get(url, follow=True)
			self.assertEqual(r.status_code, 403) 



	def test_standard_user_can_modify_its_own_gecos(self):
		for gecos in gecos_to_test:
			r = self.client.get('/users/mod/{0}/gecos/{1}'.format(
													self.standard.uid, gecos))
			self.assertEqual(r.status_code, 200)
			self.assertEqual(self.standard.gecos, gecos)

	def test_standard_user_can_modify_its_own_password(self):
		r = self.client.get('/users/mod/{0}/password/{1}'.format(
								self.standard.uid, std_user_passw_test))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard.check_password(std_user_passw_test), True)

	def test_standard_user_can_modify_its_own_shell(self):
		r = self.client.get('/users/mod/{0}/shell/{1}'.format(self.standard.uid, 
				urllib.quote_plus(LMC.configuration.users.default_shell)))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard.shell, 
			LMC.configuration.users.default_shell)

		r = self.client.get('/users/mod/{0}/shell/{1}'.format(self.standard.uid, 
				urllib.quote_plus(LMC.configuration.users.shells[-1])))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard.shell, LMC.configuration.users.shells[-1])
	
	def test_standard_user_can_run_check_pwd_strenght(self):
		r = self.client.get('/users/check_pwd_strenght/tototototo')
		self.assertEqual(r.status_code, 200)

	def test_standard_user_can_run_generate_pwd(self):
		r = self.client.get('/users/generate_pwd/')
		self.assertEqual(r.status_code, 200)

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
			cls.manager, pwd = LMC.users.add_User(
								login=manager_user_login_test,
								gecos=u'Django TS Account - test licorn-wmi user',
								password=manager_user_passw_test,
								in_groups=[
									LMC.groups.by_name('licorn-wmi').gidNumber
									]
							)
			del pwd

		

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

		
	def test_modify_standard_user(self):
		pass

	def test_modify_admin_user(self):
		urls_to_test = [ 
			'/users/delete/{0}/False'.format(self.admin_user.uid), 
			
			'/users/mod/{0}/gecos/testtest',
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.default_shell),
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.shells[-1]),
			'/users/mod/{0}/password/testtest',
			'/users/mod/{0}/skel/'+urllib.quote_plus(LMC.configuration.users.default_skel),
			
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.GUEST),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.MEMBER),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.RESPONSIBLE),
			'/users/mod/{0}/groups/'+str(self.standard_group.gid)+'/'+str(relation.NO_MEMBERSHIP),
			

			'/users/mod/{0}/lock',
			'/users/mod/{0}/unlock',
		]


		for url in urls_to_test:
			r = self.client.get(url.format(self.admin_user.uid), follow=True)
			self.assertEqual(r.status_code, 403)	
		
	def test_modify_my_own_account(self):
		# I cannot delete / lock / unlock my account
		urls_to_test = [ 
			'/users/delete/{0}/False', 
			'/users/mod/{0}/lock',
			'/users/mod/{0}/unlock'
		]

		for url in urls_to_test:
			r = self.client.get(url.format(self.manager.uid), follow=True)
			self.assertEqual(r.status_code, 403)
		
		
	def test_modify_licorn_wmi(self):
		urls_to_test = [ 
			'/users/mod/{0}/groups/'+str(LMC.groups.by_name('licorn-wmi').gid)+'/'+str(relation.NO_MEMBERSHIP),
			
			'/users/mod/{0}/password/'+manager_user_passw_test,
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.default_shell),
			'/users/mod/{0}/shell/'+urllib.quote_plus(LMC.configuration.users.shells[-1]),
			'/users/mod/{0}/skel/users',
			'/users/mod/{0}/lock',
			'/users/mod/{0}/unlock'
		]
		for gecos in gecos_to_test:
			urls_to_test.append('/users/mod/{0}/gecos/'+gecos)

		for url in urls_to_test:
			r = self.client.get(url.format(self.manager_user.uid), follow=True)
			self.assertEqual(r.status_code, 403)

	def test_manager_can_modify_its_own_gecos(self):
		for gecos in gecos_to_test:
			r = self.client.get('/users/mod/{0}/gecos/{1}'.format(
									self.manager.uid, gecos))
			self.assertEqual(r.status_code, 200)
			self.assertEqual(self.manager.gecos, gecos)

		
	def test_manager_can_modify_its_own_password(self):
		r = self.client.get('/users/mod/{0}/password/{1}'.format(
								self.manager.uid, manager_user_passw_test))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager.check_password(manager_user_passw_test), True)
								

	def test_manager_can_modify_its_own_shell(self):
		r = self.client.get('/users/mod/{0}/shell/{1}'.format(self.manager.uid, 
				urllib.quote_plus(LMC.configuration.users.default_shell)))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager.shell, 
			LMC.configuration.users.default_shell)

		r = self.client.get('/users/mod/{0}/shell/{1}'.format(self.manager.uid, 
				urllib.quote_plus(LMC.configuration.users.shells[-1])))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager.shell, LMC.configuration.users.shells[-1])

	
	def test_manager_can_modify_its_own_groups(self):
		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.manager.uid, self.standard_group.gid,
								relation.GUEST))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager in self.standard_group.guest_group.members, True)
		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.manager.uid, self.standard_group.gid,
								relation.MEMBER))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager in self.standard_group.members, True)
		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.manager.uid, self.standard_group.gid,
								relation.RESPONSIBLE))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager in self.standard_group.responsible_group.members, True)

		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.manager.uid, self.standard_group.gid,
								relation.NO_MEMBERSHIP))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager in self.standard_group.members, False)

	def test_manager_can_modify_its_own_skel(self):
		# WARNING : WILL FAIL UNTIL #782 WILL BE FIXED
		r = self.client.get('/users/mod/{0}/skel/{1}'.format(
								self.manager.uid, 
								urllib.quote_plus('/etc/skel')))
		self.assertEqual(r.status_code, 200)
		# cannot test if the skel have really been applyed because it is a 
		# FileSystem operation

	def test_manager_can_modify_licorn_wmi_groups(self):
		# guest
		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.manager_user.uid, self.standard_group.gid,
								relation.GUEST))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager_user in self.standard_group.guest_group.members, True)

		# member
		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.manager_user.uid, self.standard_group.gid,
								relation.MEMBER))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager_user in self.standard_group.members, True)

		# resp
		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.manager_user.uid, self.standard_group.gid,
								relation.RESPONSIBLE))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager_user in self.standard_group.responsible_group.members, True)


		# no membership
		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.manager_user.uid, self.standard_group.gid,
								relation.NO_MEMBERSHIP))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.manager_user not in self.standard_group.guest_group.members, True)
		self.assertEqual(self.manager_user not in self.standard_group.members, True)
		self.assertEqual(self.manager_user not in self.standard_group.responsible_group.members, True)

	def test_manager_can_modify_standard_user_gecos(self):
		for gecos in gecos_to_test:
			r = self.client.get('/users/mod/{0}/gecos/{1}'.format(
									self.standard_user.uid, gecos))
			self.assertEqual(r.status_code, 200)
			self.assertEqual(self.standard_user.gecos, gecos)

	def test_manager_can_modify_standard_user_password(self):
		r = self.client.get('/users/mod/{0}/password/{1}'.format(
								self.standard_user.uid, manager_user_passw_test))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user.check_password(manager_user_passw_test), True)		

	def test_manager_can_modify_standard_user_shell(self):
		r = self.client.get('/users/mod/{0}/shell/{1}'.format(
			self.standard_user.uid, 
			urllib.quote_plus(LMC.configuration.users.default_shell)))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user.shell, 
										LMC.configuration.users.default_shell)	
		
		r = self.client.get('/users/mod/{0}/shell/{1}'.format(
			self.standard_user.uid, 
			urllib.quote_plus(LMC.configuration.users.shells[-1])))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user.shell, 
											LMC.configuration.users.shells[-1])	
		
	def test_manager_can_modify_standard_user_groups(self):
		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.standard_user.uid, self.standard_group.gid,
								relation.GUEST))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user in self.standard_group.guest_group.members, True)

		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.standard_user.uid, self.standard_group.gid,
								relation.MEMBER))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user in self.standard_group.members, True)

		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.standard_user.uid, self.standard_group.gid,
								relation.RESPONSIBLE))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user in self.standard_group.responsible_group.members, True)

		r = self.client.get('/users/mod/{0}/groups/{1}/{2}'.format(
								self.standard_user.uid, self.standard_group.gid,
								relation.NO_MEMBERSHIP))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user not in self.standard_group.guest_group.members, True)
		self.assertEqual(self.standard_user not in self.standard_group.members, True)
		self.assertEqual(self.standard_user not in self.standard_group.responsible_group.members, True)


		
	def test_manager_can_modify_standard_user_skel(self):
		r = self.client.get('/users/mod/{0}/skel/{1}'.format(self.standard_user.uid, 
								urllib.quote_plus('/etc/skel')))
		self.assertEqual(r.status_code, 200)

		r = self.client.get('/users/mod/{0}/lock'.format(
								self.standard_user.uid), follow=True)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user.is_locked, True)

		r = self.client.get('/users/mod/{0}/unlock'.format(
								self.standard_user.uid), follow=True)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(self.standard_user.is_locked, False)

	
	def test_manager_can_delete_standard_user(self):
		uid_to_del = self.standard_user.uid
		del self.__class__.standard_user
		r = self.client.get('/users/delete/{0}/False'.format(uid_to_del))
		self.assertEqual(r.status_code, 200)
		try:
			LMC.users.by_uid(uid_to_del)	
			self.assertEqual(False, True)
		except KeyError:
			self.assertEqual(True, True)
		
		# recreate the standard_user it should have been deleted
		try:
			self.__class__.standard_user = LMC.users.by_login(standard_user_login) 
		except KeyError:
			self.__class__.standard_user, pwd = LMC.users.add_User(
								login=standard_user_login,
								gecos=u'Django TS Account - test user',
								password="random",
								in_groups=[]
							)
			del pwd

	def test_manager_can_view_home_page(self):
		r = self.client.get('/users/')
		self.assertEqual(r.status_code, 200)

	def test_manager_can_view_message_page(self):
		r = self.client.get('/users/message/skel/{0}'.format(self.standard_user.uid))
		self.assertEqual(r.status_code, 200)
		r = self.client.get('/users/message/delete/{0}'.format(self.standard_user.uid))
		self.assertEqual(r.status_code, 200)
		r = self.client.get('/users/message/lock/{0}'.format(self.standard_user.uid))
		self.assertEqual(r.status_code, 200)
	
	def test_manager_can_view_new_page(self):
		r = self.client.get('/users/new/')
		self.assertEqual(r.status_code, 200)

	def test_manager_can_view_edit_page_by_uid(self):
		r = self.client.get('/users/edit/{0}'.format(self.standard_user.uid))
		self.assertEqual(r.status_code, 200)

	def test_manager_can_view_view_page_by_uid(self):
		r = self.client.get('/users/view/{0}'.format(self.standard_user.uid))
		self.assertEqual(r.status_code, 200)

	def test_manager_can_view_import_page(self):
		r = self.client.get('/users/import/'.format(self.standard_user.login))
		self.assertEqual(r.status_code, 200)

	# will fail until #784 is not fixed
	def test_manager_can_view_edit_page_by_login(self):
		r = self.client.get('/users/edit/{0}'.format(self.standard_user.login))
		self.assertEqual(r.status_code, 200)
	
	def test_manager_can_view_view_page_by_login(self):
		r = self.client.get('/users/view/{0}'.format(self.standard_user.login))
		self.assertEqual(r.status_code, 200)

	def test_manager_can_run_import(self):
		csv_handler, csv_filename = tempfile.mkstemp()
		r = self.client.post('/users/import/False', {
			'csv_filepath': csv_filename, 
			'profile': 'users',
			'lastname' : 0,
			'firstname' : 1,
			'group' : 2,
			'login' : 3,
			'password' : 4
		})
		self.assertEqual(r.status_code, 200)	
		
	def test_manager_can_run_check_pwd_strengt(self):
		r = self.client.get('/users/check_pwd_strenght/tototototo')
		self.assertEqual(r.status_code, 200)

	
	def test_manager_can_run_generate_pwd(self):
		r = self.client.get('/users/generate_pwd/')
		self.assertEqual(r.status_code, 200)

	
	def test_manager_can_run_create(self):
		r = self.client.post('/users/create/')
		self.assertEqual(r.status_code, 200)

	
	def test_upload(self):
		csv_handler, csv_filename = tempfile.mkstemp()
		myfile = open(csv_filename,'r') 	
		r = self.client.post('/users/upload/', {
			'file': myfile,
		})
		self.assertEqual(r.status_code, 200)
















