# -*- coding: utf-8 -*-
from django                     import forms
from django.utils.translation   import ugettext as _

from licorn.foundations         import exceptions


class MachineForm(forms.Form):

    def __init__(self, machine, tab=False,*args, **kwargs):
		super(MachineForm, self).__init__(*args, **kwargs)
		self.tab = tab

		# SECTION 1
		self.fields['1_machine_id']  = forms.CharField(
			label=_("Machine identifier"),
			initial=machine.mid,
			max_length=64,
			required=False)

		self.fields['machine_hostname']   = forms.CharField(
			widget= LicornTextbox(
					instant_url='/machines/instant_edit/{0}/hostname/'.format(machine.mid), 
					handler='machine_hostname_changed',
					handler_id=machine.mid),
			label=_("Hostname"), 
			initial=machine.hostname,
			help_text='Human readable machine\'s name in the network', 
			max_length=64, 
			required=False)

		# SECTION 2
		self.fields['2_input3']   = forms.CharField(label=_("Input 3"), help_text='100 characters max.', max_length=64, required=False)

		# SECTION 3
		self.fields['3_input4']   = forms.CharField(label=_("Input 4"), max_length=64, required=True)


# key : (id, text, active)
machine_form_blocks = {
    '1_machine_id' : ('general', u'General information', True),
    '2_input3'     : ('second', u'Second Part', False),
    '3_input4'     : ('third', u'Thrid Part', False),

}