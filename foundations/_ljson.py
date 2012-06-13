# -*- coding: utf-8 -*-
"""
Licorn Foundations: base settings - http://docs.licorn.org/foundations/

Copyright (C) 2011 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

# we offer exactly the same functionnality as python's `json`.
from json import *
from json import dumps as dumps_, dump as dump_, loads as loads_, load as load_

# licorn foundations imports
from base import LicornConfigObject

class LicornEncoder(JSONEncoder):
	""" Encodes like a :class:`~json.JSONEncoder`, but handles any
		:class:`~licorn.foundations.base.LicornConfigObject`: it is
		dumped recursively as a dict. Thus, there is no need (and no
		mean) for a decoder: the dict will be loaded byt the standard
		`json` decoder.

		.. warning:: This class in meant for dumping
			:class:`~licorn.foundations.base.LicornConfigObject` to stdout,
			not for for storing it anywhere, because there is no
			corresponding decoder (and won't be).
	"""
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
	return dumps_(*a, **kw)
def loads(*a, **kw):
	kw['cls'] = LicornEncoder
	return loads_(*a, **kw)
def dump(*a, **kw):
	kw['cls'] = LicornEncoder
	return dump_(*a, **kw)
def load(*a, **kw):
	kw['cls'] = LicornEncoder
	return load_(*a, **kw)
