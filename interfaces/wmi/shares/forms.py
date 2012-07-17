# -*- coding: utf-8 -*-

from django                     import forms
from django.utils.translation   import ugettext as _


class AskSharePasswordForm(forms.Form):

	password = forms.CharField(widget=forms.PasswordInput, label="Password")

	def __init__(self, *args, **kwargs):
		self.share = kwargs.pop('share', None)
		super(AskSharePasswordForm, self).__init__(*args, **kwargs)

	def validate_password(self):
		if not self.share.check_password(self.data['password']):
			raise forms.ValidationError(_('Incorrect password'))

		return self.data['password']

	def clean(self,*args, **kwargs):
		super(AskSharePasswordForm, self).clean(*args, **kwargs)

		self.validate_password()
