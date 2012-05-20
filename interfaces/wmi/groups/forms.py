# -*- coding: utf-8 -*-

import os

from django                     import forms
from django.utils.translation   import ugettext_lazy as _

from licorn.interfaces.wmi.libs import utils
from licorn.core                import LMC

class GroupForm(forms.Form):
	def __init__(self, edit_mod, group, *args, **kwargs):

		super(self.__class__, self).__init__(*args, **kwargs)

		if edit_mod:
			group_name          = group.name
			group_description   = group.description
			group_skel          = group.groupSkel
			group_permissive    = group.permissive

			self.immutables = [ 'gid', 'name' ]

			self.fields['gid'] = forms.CharField(
				widget=forms.forms.TextInput(attrs={'readonly':'readonly'}),
				max_length=100,
				initial=group.gidNumber,
				label=_('Group identifier'))

		else:
			self.immutables = [ ]

			group_name          = ""
			group_description   = ""
			group_skel          = ""
			group_permissive    = False

		self.fields['name'] = forms.CharField(
			widget=forms.TextInput(),
			max_length=100,
			initial=group_name,
			label=_('Group name'))

		self.fields['description'] = forms.CharField(
			max_length=150,
			initial=group_description,
			label=_('Group description'))

		if group is None or group.is_standard:
			self.fields['permissive'] = forms.BooleanField(
				initial = group_permissive,
				label=_('Is the dir permissive ?'))

			self.fields['skel'] = forms.ChoiceField(
				choices = [(s, os.path.basename(s)) for s in LMC.configuration.users.skels ],
				initial = group_skel,
				label=_('Group skel'))
