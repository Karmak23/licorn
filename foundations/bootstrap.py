# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

bootstrap - the very base.

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/
:license: GNU GPL version 2
"""

import sys, os, inspect, traceback

def getcwd():
	""" We can't rely on `os.getcwd()`: it will resolve the CWD if it is a
	symlink. We don't always want that. For example in developer
	installations, we want to be able to have many licorn repos
	in ~/source and symlink the current to ~/source/licorn. This way,
	we run `make devinstall` from there, only once.
	"""

	try:
		# The quickest method, if my shell supports it.
		return os.environ['PWD']

	except KeyError:
		try:
			# `pwd` doesn't resolve the CWD either. Thanks.
			return run_command(['pwd'])

		except:
			# if all of this fails, we will rely on `os.getcwd()`.
			# Not cool, but at least it doesn't crash.
			return os.getcwd()
def setup_sys_path():
	""" To be able to run foundations modules as scripts in various developper
		install configurations.

		Taken from http://stackoverflow.com/questions/279237/python-import-a-module-from-a-folder

		.. note:: we do not run `os.path.abspath()` on the current folder path,
			to preserve symlinking.
	"""
	current_folder = os.path.normpath(os.path.join(getcwd(),
			os.path.split(inspect.getfile(inspect.currentframe()))[0]))

	if current_folder != '' and current_folder not in sys.path:
		sys.path.insert(0, current_folder)
def setup_utf8():
	""" We need to set the system encoding to utf-8. I know that this is
		officially unsupported at least on Python 2.x installations, but which
		system uses only 'ascii' nowadays?? Everything we do is utf8.
	"""
	if sys.getdefaultencoding() == "ascii":
		reload(sys)
		sys.setdefaultencoding("utf-8")
def setup_gettext():
	""" Import gettext for all licorn code, and setup unicode.
		this is particularly needed to avoid #531 and all other kind
		of equivalent problems.
	"""

	import gettext
	gettext.install('licorn', unicode=True)
def check_python_modules_dependancies():
	""" verify all required python modules are present on the system. """

	warn_file = '%s/.licorn_dont_warn_optmods' % os.getenv('HOME', '/root')

	reqmods = (
		(u'gettext',   u'python-gettext'),
		(u'posix1e',   u'python-pylibacl'),
		(u'Pyro',      u'pyro'),
		(u'gobject',   u'python-gobject'),
		(u'netifaces', u'python-netifaces'),
		(u'ping',      u'python-pyip'),
		(u'ipcalc',    u'python-ipcalc'),
		(u'dumbnet',   u'python-dumbnet'),
		(u'pyudev',    u'python-pyudev'),
		(u'apt_pkg',   u'python-apt'),
		(u'crack',     u'python-cracklib'),
		(u'sqlite',    u'python-sqlite'),
		(u'pygments',  u'python-pygments'),
		(u'pyinotify', u'python-pyinotify'),
		(u'dbus',      u'python-dbus'),
		)

	reqmods_needed = []
	reqpkgs_needed = []

	optmods = (
		(u'xattr',    u'python-xattr'),
		(u'ldap',     u'python-ldap')
		# plistlib, uuid don't need to be checked, they're part of standard
		# python dist-packages.
		)

	optmods_needed = []
	optpkgs_needed = []

	for modtype, modlist in (('required', reqmods), ('optional', optmods)):
		for mod, pkg in modlist:
			try:
				exec ('import %s' % mod) in globals(), locals()

			except ImportError:
				traceback.print_exc()

				if modtype == 'required':
					reqmods_needed.append(mod)
					reqpkgs_needed.append(pkg)
				else:
					optmods_needed.append(mod)
					optpkgs_needed.append(pkg)

			else:
				exec ('del %s' % mod) in globals(), locals()

	for modchkfunc, modfinalfunc, modmsg, modlist, pkglist in (
		(lambda x: not os.path.exists(warn_file),
		lambda x: open(warn_file, 'w').write(str(x)),
			_(u'You may want to install optional python '
				u'module{0} {1} to benefit of full functionnality (debian '
				u'package{2} {3}). As this is optional, you will not see this '
				u'message again.\n'),
			optmods_needed, optpkgs_needed),
		(lambda x: True, sys.exit,
			_(u'You must install required python module{0} {1} (Debian/PIP '
			u'package{2} {3}) before continuing.\n'),
			reqmods_needed, reqpkgs_needed)
		):

		need_exit = False
		if modchkfunc(modlist) and modlist != []:
			if len(modlist) > 1:
				the_s = u's'
			else:
				the_s = ''
			sys.stderr.write(modmsg.format(
				the_s, u', '.join(modlist),
				the_s, u', '.join(pkglist)
				))
			modfinalfunc(1)
			need_exit = True
	if need_exit:
		os.exit(1)
def bootstrap():
	setup_utf8()
	setup_gettext()
	check_python_modules_dependancies()

	# not needed in normal conditions.
	#setup_sys_path()

# do the bootstrap, we we are first imported.
bootstrap()

# export a method for fsapi.
__all__ = ('getcwd', )

if __name__ == "__main__":
	sys.stdout.write(getcwd())
