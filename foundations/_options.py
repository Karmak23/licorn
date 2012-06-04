# -*- coding: utf-8 -*-
"""
Licorn Foundations: options - http://docs.licorn.org/foundations/

Copyright (C) 2011 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

# Licorn's RLock
from threads   import RLock
from base      import ObjectSingleton
from ltrace    import *
from ltraces   import *
from constants import verbose

__all__ = ('options', )

class LicornOptions(ObjectSingleton):
	""" This Options class is meant to share options / preferences globally
		accross all python modules loaded in a single session of any Licorn App.

		This is useful for logging options typically, like verbosity level.

		This class is a singleton (this is needed for it to work as expected).
	"""

	no_colors = False

	def __init__(self) :
		assert ltrace(TRACE_OPTIONS, '| __init__()')
		self.msgproc = None
		self.verbose = verbose.NOTICE

		# a list of threads which receive monitored events.
		self.monitor_listeners = []

		# this will help dealing with multi-thread concurrency when clients
		# (un-)register them-selves while monitor messages are beiing processed.
		self.monitor_lock = RLock()

	def SetVerbose(self, level):
		""" Change verbose parameter. """
		assert ltrace(TRACE_OPTIONS, '| SetVerbose(%s)' % level)
		self.verbose = level
	def SetQuiet(self):
		""" Change verbose parameter. """
		self.verbose = verbose.QUIET
	def SetNoColors(self, no_colors=True):
		""" Change color output parameter. """
		assert ltrace(TRACE_OPTIONS, '| SetNoColors(%s)' % no_colors)
		self.no_colors = no_colors
	def SetFrom(self, opts):
		""" Change parameters, from an object given by an argparser """
		assert ltrace(TRACE_OPTIONS, '| SetFrom(%s)' % opts)

		self.SetNoColors(opts.no_colors)
		self.SetVerbose(opts.verbose)
		# put future functions here…

		for attr_name in dir(opts):
			if attr_name[0] != '_' and not hasattr(self, attr_name):
				setattr(self, attr_name, getattr(opts, attr_name))

options = LicornOptions()
