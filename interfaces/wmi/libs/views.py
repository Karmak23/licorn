# -*- coding: utf-8 -*-
"""
Licorn WMI2 generic views.

:copyright:
	* 2012 Robin Lucbernet <robin@meta-it.fr>

:license: GNU GPL version 2
"""

import os


from django.contrib.auth.decorators import login_required
from django.core.servers.basehttp   import FileWrapper
from django.shortcuts               import *
from django.template.loader         import render_to_string

from licorn.core                    import LMC

def get_group_view_html(group_name):
	return render_to_string('/users/view_group_template.html', {
		'group' : LMC.groups.by_name(group_name)
	})
