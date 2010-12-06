# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

# this @@-tag will be replaced by the package release version.
# this is left to the package maintainer, don't alter it here.
__version__ = '@@VERSION@@'
version     = __version__

import os, sys
from styles    import *
from base      import ObjectSingleton
from ltrace    import ltrace
from constants import verbose

class LicornOptions(ObjectSingleton):
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

		for attr_name in dir(opts):
			if attr_name[0] != '_' and not hasattr(self, attr_name):
				setattr(self, attr_name, getattr(opts, attr_name))
def check_python_modules_dependancies():
	""" verify all required python modules are present on the system. """

	warn_file = '%s/.licorn_dont_warn_optmods' % os.getenv('HOME')

	reqmods = (
		('posix1e',   'python-pylibacl'),
		('gamin',     'python-gamin'),
		('Pyro',      'pyro'),
		('netifaces', 'python-netifaces')
		)

	reqmods_needed = []
	reqpkgs_needed = []

	optmods = (
		('xattr',   'python-xattr'),
		('ldap',    'python-ldap')
		)

	optmods_needed = []
	optpkgs_needed = []

	for modtype, modlist in (('required', reqmods), ('optional', optmods)):
		for mod, pkg in modlist:
			try:
				exec 'import %s\ndel %s' % (mod, mod) in globals(), locals()
			except:
				if modtype == 'required':
					reqmods_needed.append(mod)
					reqpkgs_needed.append(pkg)
				else:
					optmods_needed.append(mod)
					optpkgs_needed.append(pkg)

	for modchkfunc, modfinalfunc, modmsg, modlist, pkglist in (
		(lambda x: not os.path.exists(warn_file),
		lambda x: open(warn_file, 'w').write(str(x)),
		'You may want to install optional python '
			'module%s %s to benefit full functionnality (debian '
			'package%s %s).' + ' %s.\n' % stylize(ST_NOTICE,
				'This is the last time you see this message'),
			optmods_needed, optpkgs_needed),
		(lambda x: True, sys.exit,
			stylize(ST_IMPORTANT, 'You must install') +
			' required python module%s %s (debian '
			'package%s %s) before continuing.\n',
			reqmods_needed, reqpkgs_needed)
		):

		if modchkfunc(modlist) and modlist != []:
			if len(modlist) > 1:
				the_s = 's'
			else:
				the_s = ''
			sys.stderr.write(modmsg % (
				the_s, ', '.join([stylize(ST_NAME, mod) for mod in modlist]),
				the_s, ', '.join([stylize(ST_PATH, pkg) for pkg in pkglist])
				))
			modfinalfunc(1)

check_python_modules_dependancies()
options = LicornOptions()
