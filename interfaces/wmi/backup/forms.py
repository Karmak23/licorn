# -*- coding: utf-8 -*-

from django                     import forms
from django.utils.translation   import ugettext as _

class ForceBackupRunForm(forms.Form):
	force = forms.BooleanField(label=_('Force a backup to be run even if the last is recent.'), required=False)

	# not ready for production yet.
	#volume = forms.ChoiceField(choices = ,	initial = ,
	#			label=_('Volume on which to run backup'))
