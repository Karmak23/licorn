# -*- coding: utf-8 -*-
from django                     import forms
from django.utils.translation   import ugettext as _

from licorn.foundations         import exceptions


class LicornTextbox(forms.Widget):
	""" Special Licorn textbox. Provide parameters to setup 'instant edit/apply'
	mecanism. """

	def __init__(self, instant_url=None, handler=None, handler_id=None, *args, **kwargs):
		super(LicornTextbox, self).__init__(*args, **kwargs)

		# url to contact to edit field
		self.instant_url = instant_url
		# event that will be thrown when edit action is completed
		self.handler     = handler
		# who has to react for this change
		self.handler_id  = handler_id

		if instant_url is not None and (handler is None or handler_id is None):
			raise exceptions.BadArgumentError('You have to set handler and '
				'handler_id.')

	def render(self, name, value, attrs=None):


		if self.instant_url is not None:

			attrs.update({
				'class'            : 'instant',
				'data-instant-url' : self.instant_url
				})

		template = "<input type='text' name='{0}' value='{1}' {2}>"

		return template.format(name, value,
			' '.join([ '{0}=\'{1}\''.format(k,v) for k,v in attrs.iteritems() ]))




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