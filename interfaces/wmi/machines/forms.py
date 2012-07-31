# -*- coding: utf-8 -*-
from django                       import forms
from django.utils.translation     import ugettext_lazy as _

from django                     import forms
from django.utils.translation   import ugettext as _

class LicornTextbox(forms.Widget):
	def __init__(self, instant_apply_url=None, handler=None, handler_id=None, *args, **kwargs):
		super(LicornTextbox, self).__init__(*args, **kwargs)

		self.instant_apply_url     = instant_apply_url
		self.handler = handler
		self.handler_id = handler_id

	def render(self, name, value, attrs=None):
		return "<input type='text' name='{0}' value='{1}' {2} {3}>".format(
			name, value, 
			' '.join([ '{0}=\'{1}\''.format(k,v) for k,v in attrs.iteritems() ]),
			'class=\'instant_apply_textbox\' data-instant-url=\'{0}\' data-handler=\'{1}\' data-handler-id=\'{2}\''.format(
				self.instant_apply_url, self.handler, self.handler_id) if self.instant_apply_url is not None else "")

class MachineForm(forms.Form):

    def __init__(self, machine, tab=False,*args, **kwargs):
		super(MachineForm, self).__init__(*args, **kwargs)
		self.tab = tab
		self.fields['machine_id']  = forms.CharField(
			label=_("Machine identifier"),
			initial=machine.mid,
			max_length=64,
			required=False)

		self.fields['machine_hostname']   = forms.CharField(
			widget= LicornTextbox(
					instant_apply_url='/machines/instant_edit/{0}/hostname/'.format(machine.mid), 
					handler='machine_hostname_changed',
					handler_id=machine.mid),
			label=_("Hostname"), 
			initial=machine.hostname,
			help_text='Human readable machine\'s name in the network', 
			max_length=64, 
			required=False)
		self.fields['input3']   = forms.CharField(label=_("Input 3"), help_text='100 characters max.', max_length=64, required=False)


# key : (id, text, active)
machine_form_blocks = {
    'machine_id'              : ('general', u'General information', True),
    'input3'              : ('second', u'Second Part', False),

}