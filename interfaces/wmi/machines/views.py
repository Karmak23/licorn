# -*- coding: utf-8 -*-

from django.utils.translation     import ugettext_lazy as _
from django.template.loader       import render_to_string
from django.shortcuts             import *

from licorn.foundations           import exceptions, logging, settings
from licorn.foundations           import hlstr, pyutils
from licorn.foundations.base      import Enumeration, LicornConfigObject
from licorn.foundations.constants import filters, relation, host_status, host_types
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core import LMC

from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import staff_only

# FIXME: OLD!! MOVE FUNCTIONS to new interfaces.wmi.libs.utils.
from licorn.interfaces.wmi.libs                import old_utils as w

import wmi_data

@staff_only
def main(request, sort="login", order="asc", select=None, **kwargs):

	assert ltrace_func(TRACE_DJANGO)

	machines_list = utils.select('machines', default_selection=host_status.ONLINE)

	return render(request, 'machines/index.html', {
			'machines_list'        : machines_list,
			'get_host_status_html' : wmi_data.get_host_status_html,
			'get_host_os_html'     : wmi_data.get_host_os_html,
			'get_host_type_html'   : wmi_data.get_host_type_html
		})

@staff_only
def scan(request, *args, **kwargs):

	assert ltrace_func(TRACE_DJANGO)

	LMC.machines.scan_network()
	return HttpResponse('Processing network scan')
