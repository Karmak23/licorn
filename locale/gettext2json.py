#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import simplejson as enc
import gettext
from traceback import print_exc

if sys.getdefaultencoding() == "ascii":
	reload(sys)
	sys.setdefaultencoding("utf-8")

def gettext_json(domain=None, path=None, lang=None, indent=False):

	try:
		tr = gettext.translation(domain, path, lang)

		# for unknown reasons, instead of having plural entries like
		# key: [sg, pl1...]
		# tr._catalog has (key, n): pln,
		keys = tr._catalog.keys()
		keys.sort()
		ret = {}
		for k in keys:
			v = tr._catalog[k]
			if type(k) is tuple:
				if k[0] not in ret:
					ret[k[0]] = []
				ret[k[0]].append(v)
			else:
				ret[k] = v

		sys.stdout.write(enc.dumps(ret, ensure_ascii=False, indent=indent))
	except IOError:
		print_exc()

if __name__ == '__main__':
	gettext_json(sys.argv[1], sys.argv[2], sys.argv[3].split(','))
