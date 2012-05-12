# -*- coding: utf-8 -*-
"""
Licorn® WMI - users views tests

:copyright:
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>
	* 2012 Olivier Cortès <olive@licorn.org>
:license: GNU GPL version 2
"""

from django.utils	    import unittest
from django.test.client import Client

from licorn.core 		import LMC
from licorn.interfaces.wmi.libs.utils import select_one

test_user_login = 'wmitest-django'
test_user_passw = 'wmitest-django'

class testUsers(unittest.TestCase):
	""" """
	@classmethod
	def setUpClass(cls):
		cls.user = select_one('users', (test_user_login, ))

		if cls.user is None:
			cls.user, pwd = LMC.users.add_User(
								login=test_user_login,
								gecos=u'Django TS Account',
								password=test_user_passw,
								in_groups=[
									select_one('groups',
										('licorn-wmi', )).gidNumber
									],
								system=True
							)
			del pwd

	@classmethod
	def tearDownClass(cls):
		LMC.users.del_User(cls.user,
						no_archive=True)

		# we must delete it here too, else it won't be garbage collected
		# and next creation will fail.
		del cls.user

class testUsersAnonymous(testUsers):

	def setUp(self):
		# Every test needs a client.
		self.client = Client()

		#not yet
		#enforce_csrf_checks=True
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

	def test_logging_in1(self):
		r = self.client.post('/login/', { 'username': test_user_login,
											'password': test_user_passw }, follow=True)

		self.assertEqual(r.status_code, 404)

class testUsersLoggedIn(testUsers):

	def setUp(self):
		# Every test needs a client.
		self.client = Client()

		#not yet
		#enforce_csrf_checks=True
	def tearDown(self):
		pass

	def test_logging_in2(self):

		logged_in = self.client.login(username=test_user_login,
										password=test_user_passw)
		self.failUnless(logged_in, 'Could not log in!')

	def test_uri_root(self):
		r = self.client.get('/users')
		self.assertEqual(r.status_code, 200)

	def test_uri_new(self):
		r = self.client.get('/users/new')
		self.assertEqual(r.status_code, 200)

		#r = self.client.get('/users/new')
		#self.assertEqual(r.status_code, 200)
