# -*- coding: utf-8 -*-
import os

from django                      import forms
from django.utils.translation    import ugettext_lazy as _
from licorn.core                 import LMC

class UserForm(forms.Form):
	def __init__(self, edit_mod, user, *args, **kwargs):

		super(self.__class__, self).__init__(*args, **kwargs)

		if edit_mod:
			user_login = user.login
			user_gecos = user.gecos
			if user.profile:
				user_profile = user.profile.name

			else:
				user_profile = _('No profile')

			user_shell = user.shell

			self.immutables = [ 'uid', 'login', 'profile' ]

			self.fields['uid'] = forms.CharField(
				widget=forms.forms.TextInput(attrs={'readonly':'readonly'}),
				max_length=100,
				initial=user.uidNumber,
				label=_('UID'))

		else:
			self.immutables = [ ]

			user_login = ''
			user_id = ''
			user_gecos = ''
			user_profile = ''
			user_shell = ''

		self.fields['login'] = forms.CharField(
			widget=forms.TextInput(),
			max_length=100,
			initial=user_login,
			label=_('Login'))

		self.fields['profile'] = forms.ChoiceField(
			widget=forms.Select(attrs={'readonly':'readonly'}),
					choices = [(p.gidNumber, p.name) for p in LMC.profiles ],
					initial = user_profile)

		self.fields['gecos'] = forms.CharField(
			max_length=100,
			initial=user_gecos,
			label=_('Full name'))

		self.fields['password'] = forms.CharField(widget=forms.PasswordInput)
		self.fields['password_confim'] = forms.CharField(widget=forms.PasswordInput)

		self.fields['shell'] = forms. ChoiceField(
			choices = [(p, p) for p in LMC.configuration.users.shells ],
			initial = user_shell)



class SkelInput(forms.Form):
	def __init__(self, initial_skel='', class_name='', *args, **kwargs):
		super(self.__class__, self).__init__(*args, **kwargs)
		self.fields['skel_to_apply'] = forms.ChoiceField(
				choices = [(s, os.path.basename(s)) for s in LMC.configuration.users.skels ],
				initial = initial_skel,
				label=_('Which skel do you want to apply?'))


class ImportForm(forms.Form):
	def __init__(self, *args, **kwargs):
		super(self.__class__, self).__init__(*args, **kwargs)
		self.fields['file']  = forms.FileField(
				label=_('CSV file'))

		self.fields['profile'] = forms.ChoiceField(
					choices = [(p.gidNumber, p.name) for p in LMC.profiles ])

		self.fields['lastname'] = forms.CharField(
				initial='0',
				label=_('Last name column'))
		self.fields['firstname'] = forms.CharField(
				initial='1',
				label=_('First name column'))
		self.fields['group'] = forms.CharField(
				initial='2',
				label=_('Group column'))
		self.fields['login'] = forms.CharField(
				initial='',
				label=_('Login column'))
		self.fields['password'] = forms.CharField(
				initial='',
				label=_('Password column'))
