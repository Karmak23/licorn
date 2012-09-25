# -*- coding: utf-8 -*-

import os

from django                     import forms
from django.utils.translation   import ugettext as _

from licorn.interfaces.wmi.libs import utils
from licorn.core                import LMC


class GroupForm(forms.Form):
	def __init__(self, _mode, group, *args, **kwargs):

		super(self.__class__, self).__init__(*args, **kwargs)

		def widget_attrs(action_name, group):
			widget_attrs = {}
			if _mode != 'new':
				widget_attrs.update({
					'class':'instant',
					'data-instant-url': '/groups/mod/{0}/{1}/'.format(group.gid, action_name)
				})
			return widget_attrs

		if _mode == 'massiv':
			self.fields['skel'] = forms.ChoiceField(
					choices = [(s, os.path.basename(s)) for s in LMC.configuration.users.skels ],
					initial = LMC.configuration.users.default_skel,
					label=_('Group skel'))

		else:

			if _mode == 'edit':
				group_name          = group.name
				group_description   = group.description
				group_skel          = group.groupSkel
				group_permissive    = group.permissive

				self.fields['gid'] = forms.CharField(
					widget=forms.forms.TextInput(attrs={'readonly':'readonly'}),
					max_length=100,
					initial=group.gidNumber,
					label=_('Group identifier'))

				ro_attr = {'readonly':'readonly'}

			elif _mode == 'new':
				ro_attr = None
				group_name          = ""
				group_description   = ""
				group_skel          = ""
				group_permissive    = False


			self.fields['name'] = forms.CharField(
				widget=forms.TextInput(ro_attr),
				max_length=100,
				initial=group_name,
				label=_('Group name'))

			self.fields['description']   = forms.CharField(
				widget= forms.TextInput(attrs=widget_attrs('description', group)),
				label=_("Group description"), 
				initial=group_description,
				help_text=_('Group description (e.g. "Members of group Manager")'),
				max_length=150, 
				required=False)

			print "group_permissive is", group_permissive
			if group is None or group.is_standard:
				self.fields['permissive'] = forms.BooleanField(
					widget= forms.CheckboxInput(attrs=widget_attrs('permissive', group)),
					initial = not group_permissive,
					label=_('Permissive group ?'),
					help_text=_('More information about <a href="http://docs.licorn.org/groups/permissions.en.html#permissiveness-en" target=_blank>permissivness</a>'),
					)

				self.fields['skel'] = forms.ChoiceField(
					widget= forms.Select(attrs=widget_attrs('skel', group)),
					choices = [(s, os.path.basename(s)) for s in LMC.configuration.users.skels ],
					initial = group_skel,
					label=_('Group skel'))



# key : (id, text, active)
def get_group_form_blocks(request):
	group_form_blocks = {
		'gid' : ('general', u'General information', True),
		'standard' : ('standard', u'Users', False),
	}

	if request.user.is_superuser:
		group_form_blocks.update({
			'system' : ('system', u'Systems users', False)
		})

	return group_form_blocks