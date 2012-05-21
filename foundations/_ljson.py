# -*- coding: utf-8 -*-
"""
Licorn Foundations: base settings - http://docs.licorn.org/foundations/

Copyright (C) 2011 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

# we offer exactly the same functionnality as python's `json`.
from json import *
from json import dumps as dumps_orig_

# licorn foundations imports
from base import LicornConfigObject

class LicornEncoder(JSONEncoder):
	def default(self, obj):
		def lco_dump(obj):
			return dict((key, lco_dump(value) 
								if isinstance(value, LicornConfigObject)
								else value
						)
					for key, value in obj.iteritems())
		if isinstance(obj, LicornConfigObject):
			return lco_dump(obj)
		return self.encode(obj)

def dumps(*a, **kw):
	kw['cls'] = LicornEncoder
	return dumps_orig_(*a, **kw)
