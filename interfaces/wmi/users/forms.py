# -*- coding: utf-8 -*-
import os

from django                      import forms
from django.utils.translation    import ugettext_lazy as _
from licorn.core                 import LMC

class UserForm(forms.Form):
	def __init__(self, mode, user, *args, **kwargs):
		# mode = None => basic mode, new user(blank field)
		#		 "edit" => edit mode (fill field with defaults values)
		# 		 "massiv" => massiv mode (only show shell and groups)

		super(self.__class__, self).__init__(*args, **kwargs)

		def widget_attrs(action_name, user):
			widget_attrs = {}
			if mode != 'new':
				widget_attrs.update({
					'class':'instant',
					'data-instant-url': '/users/mod/{0}/{1}/'.format(user.uid, action_name)
				})
			return widget_attrs




		if mode=="massiv":
			user_shell = LMC.configuration.users.default_shell
		else:
			if mode=='edit':
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
				widget= forms.TextInput(attrs=widget_attrs('gecos', user)),
				max_length=100,
				initial=user_gecos,
				label=_('Full name'))

			self.fields['password'] = forms.CharField(widget=forms.PasswordInput)
			self.fields['password_confim'] = forms.CharField(
				widget=forms.PasswordInput(attrs=widget_attrs('password', user)))

		self.fields['shell'] = forms.ChoiceField(
			widget= forms.Select(attrs=widget_attrs('shell', user)),
				choices = [(p, p) for p in LMC.configuration.users.shells ],
				initial = user_shell)

class SkelInput(forms.Form):
	def __init__(self, initial_skel='', class_name='', *args, **kwargs):
		super(self.__class__, self).__init__(*args, **kwargs)

		self.fields['skel_to_apply'] = forms.ChoiceField(
				choices=((s, os.path.basename(s))
								for s in LMC.configuration.users.skels),
				initial=initial_skel,
				label=_('Which skel do you want to apply?'))


class ImportForm(forms.Form):
	def __init__(self, *args, **kwargs):
		super(self.__class__, self).__init__(*args, **kwargs)
		self.fields['file']  = forms.FileField(
				label=_('CSV file'))

		self.fields['separator'] = forms.CharField(
				initial=';',
				label=_('Columns separator'))

		self.fields['profile'] = forms.ChoiceField(
					choices = [(p.gidNumber, p.name) for p in LMC.profiles ])

		self.fields['profile_col'] = forms.CharField(
				label=_('Profile column'))

		self.fields['lastname'] = forms.CharField(
				label=_('Last name column'))
		self.fields['firstname'] = forms.CharField(
				label=_('First name column'))

		self.fields['gecos'] = forms.CharField(
				initial='',
				label=_('Gecos column'))
		
		self.fields['group'] = forms.CharField(
				label=_('Group column'))
		self.fields['login'] = forms.CharField(
				initial='',
				label=_('Login column'))
		self.fields['password'] = forms.CharField(
				initial='',
				label=_('Password column'))


# key : (id, text, active)
def get_user_form_blocks(request):
	group_form_blocks = {
		'agid' : ('ageneral', u'General information', True),
		'bstandard' : ('bstandard', u'Groups', False),
	}

	if request.user.is_superuser:
		group_form_blocks.update({
			'cprivileged' : ('cprivileged', u'Privileged groups', False),
			'dsystem' : ('dsystem', u'Systems groups', False)
		})

	return group_form_blocks