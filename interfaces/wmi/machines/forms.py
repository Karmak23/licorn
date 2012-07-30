# -*- coding: utf-8 -*-
from django                       import forms
from django.utils.translation     import ugettext_lazy as _

from django                     import forms
from django.utils.translation   import ugettext as _



class MachineForm(forms.Form):

    def __init__(self, tab=False, *args, **kwargs):
		super(MachineForm, self).__init__(*args, **kwargs)
		self.tab = tab
		self.fields['machine_id']   = forms.CharField(label=_("Machine identifier"), initial='0000000', max_length=64, required=False)
		self.fields['input2']   = forms.CharField(label=_("Input 2"), help_text='100 characters max.', max_length=64, required=False)
		self.fields['input3']   = forms.CharField(label=_("Input 3"), help_text='100 characters max.', max_length=64, required=False)


machine_form_blocks = {
    'machine_id'              : ('general', u'General information'),
    'input3'              : ('second', u'Second Part'),
}