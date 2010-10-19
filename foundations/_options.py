# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

options - options and preferences shared accross all python modules.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

#
# WARNING: Don't import 'logging' here ! this will introduce a circular loop.
# if you need to debug this module, please use "print" statements. And thus
# try to keep this class as small as possible !
#

from objects   import Singleton
from ltrace    import ltrace
from constants import verbose

class LicornOptions(Singleton):
	""" This Options class is meant to share options / preferences globally
		accross all python modules loaded in a single session of any Licorn App.

		This is useful for logging options typically, like verbosity level.

		This class is a singleton (this is needed for it to work as expected).
	"""

	no_colors   = False

	def __init__(self) :
		assert ltrace('options', '| __init__()')
		self.msgproc = None
		self.verbose = verbose.NOTICE

	def SetVerbose(self, level):
		""" Change verbose parameter. """
		assert ltrace('options', '| SetVerbose(%s)' % verbose)
		self.verbose = level
	def SetQuiet(self):
		""" Change verbose parameter. """
		self.verbose = verbose.QUIET
	def SetNoColors(self, no_colors=True):
		""" Change color output parameter. """
		assert ltrace('options', '| SetNoColors(%s)' % no_colors)
		self.no_colors = no_colors
	def SetFrom(self, opts):
		""" Change parameters, from an object given by an argparser """
		assert ltrace('options', '| SetFrom(%s)' % opts)

		self.SetNoColors(opts.no_colors)
		self.SetVerbose(opts.verbose)
		# put future functions here…
