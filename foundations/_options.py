# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

options - options and preferences shared accross all python modules.

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

#
# WARNING: Don't import 'logging' here ! this will introduce a circular loop.
# if you need to debug this module, please use "print" statements. And thus 
# try to keep this class as small as possible !
#

class LicornOptions :
	""" This Options class is meant to share options / preferences globally
		accross all python modules loaded in a single session of any Licorn App.

		This is useful for logging options typically, like verbosity level.

		This class is a singleton (this is needed for it to work as expected).
	"""

	VLEVEL_QUIET    = 0
	VLEVEL_NOTICE   = 1
	VLEVEL_INFO     = 2
	VLEVEL_PROGRESS = 3
	VLEVEL_DEBUG    = 4
	VLEVEL_DEBUG2   = 5

	__singleton = None
	no_colors   = False
	verbose     = VLEVEL_NOTICE

	def __new__(cls) :
		"""This is a Singleton Design Pattern."""

		if cls.__singleton is None :
			cls.__singleton = object.__new__(cls)
		
		return cls.__singleton
	def SetVerbose(self, verbose) :
		LicornOptions.verbose = verbose
	def SetQuiet(self) :
		LicornOptions.verbose = LicornOptions.VLEVEL_QUIET
	def SetNoColors(self, no_colors = True) :
		LicornOptions.no_colors = no_colors
	def SetFrom(self, opts) :
		self.SetNoColors(opts.no_colors)
		self.SetVerbose(opts.verbose)
		# put future functions here...


