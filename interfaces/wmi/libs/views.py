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

@login_required
def download(request, _file, *args, **kwargs):
	""" download a file, can only be in '/tmp' else download is refused 
	from : http://djangosnippets.org/snippets/365/ """

	if _file.startswith('/tmp/'):
		filename = os.path.join(_file)
		wrapper = FileWrapper(file(filename))
		response = HttpResponse(wrapper, content_type='text/plain')
		response['Content-Length'] = os.path.getsize(filename)
		response['Content-Disposition'] = 'attachment; filename={0}'.format('Custom_export')
		return response
	else:
		return HttpResponse('Bad file speficied')