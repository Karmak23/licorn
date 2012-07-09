# -*- coding: utf-8 -*-

from django                     import forms
from django.utils.translation   import ugettext as _


class AskSharePasswordForm(forms.Form):

	password = forms.CharField( widget=forms.PasswordInput, label="Password")

	def __init__(self, *args, **kwargs):
		self.share = kwargs.get('share', None)
		del kwargs['share']
		super(AskSharePasswordForm, self).__init__(*args, **kwargs)

	def validate_password(self):
		print "check_password ", self.data['password']
		print self.share.check_password(self.data['password'])

		if not self.share.check_password(self.data['password']):
			raise forms.ValidationError(_('The password is not correct'))
		return self.data['password']

	def clean(self,*args, **kwargs):
		print ">> validate"
		super(AskSharePasswordForm, self).clean(*args, **kwargs)
		
		self.validate_password()