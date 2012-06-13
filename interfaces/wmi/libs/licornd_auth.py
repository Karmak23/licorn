# -*- coding: utf-8 -*-

from django.contrib.auth.models import User, check_password
from django.conf                import settings

from licorn.foundations         import logging, settings as licorn_settings
from licorn.foundations         import pyutils
from licorn.core                import LMC

class LicorndAuthBackend:
	""" Authenticate against OpenERP users. """

	supports_object_permissions = False
	supports_anonymous_user     = False
	supports_inactive_user      = True

	def _find_login_for_gecos(self, gecos):
		for user in LMC.users:
			if user.gecos.lower() == gecos.lower():
				return user.login

		raise exceptions.DoesntExistException()
	def _check_credentials(self, login, password):
		try:
			return LMC.users.by_login(login).check_password(password)

		except KeyError:
			return False
	def _user_infos_by_login(self, login):
		u = LMC.users.by_login(login)
		return (u.uidNumber, u.login, u.gecos, u.locked,
											tuple(g.name for g in u.groups))

	def authenticate(self, username=None, password=None):

		django_user = None
		licorn_user = None

		try:
			# try the login, with case matching
			if self._check_credentials(username, password):
				uid, login, gecos, locked, groups = self._user_infos_by_login(username)

			# try the login lowercased.
			elif self._check_credentials(username.lower(), password):
				username = username.lower()
				uid, login, gecos, locked, groups = self._user_infos_by_login(username)

			# Try the username (gecos), eg. "Olivier Cortès"
			else:
				username = self._find_login_for_gecos(username.encode('utf-8'))

				if self._check_credentials(username, password):
					uid, login, gecos, locked, groups = self._user_infos_by_login(username)

			if uid:
				django_user, created = User.objects.get_or_create(username=username)

				try:
					django_user.first_name, \
						django_user.last_name = gecos.split(' ', 1)

				except ValueError:
					django_user.first_name = django_user.last_name = gecos

				django_user.uid          = uid
				django_user.email	     = login + '@localhost'
				django_user.is_active    = not locked
				django_user.is_superuser = (licorn_settings.defaults.admin_group
												in groups)
				django_user.is_staff     = (django_user.is_superuser or (
											licorn_settings.licornd.wmi.group
												in groups))

		except Exception:
			logging.exception(_(u'Exception while trying to authenticate '
														u'user {0}'), username)
		return django_user
	def get_user(self, user_id):
		user = None

		try:
			user = User.objects.get(pk=user_id)

		except Exception, e:
			if settings.DEBUG:
				pyutils.print_exception_if_verbose()

		return user
