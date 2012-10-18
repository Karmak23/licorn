# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

bootstrap - the very base.

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT http://meta-it.fr/
:license: GNU GPL version 2
"""

import sys, os, codecs, inspect, traceback

try:
	# avoid nasty and totally useless warnings (fixes #810)
	# This is needed only on Ubuntu 10.10 (and perhaps other
	# "old" distros I haven't tested yet.
	import pkg_resources

except:
	pass

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
			# `pwd` doesn't run `realpath()` on the CWD. It's what we want.
			return os.system('pwd')

		except:
			# If all of this fails, we will rely on `os.getcwd()`. It does
			# realpath() on the CWD. This is not cool, but at least we won't
			# crash.
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
	""" We need to set the system encoding and stdout/stderr to utf-8.
		I already know that this is officially unsupported at least on
		Python 2.x installations, but many strings in Licorn® have UTF-8
		characters inside. Our terminal	emulators are all utf-8 natively,
		and outputing UTF-8 to log files never hurted anyone. Distros we
		support are all UTF-8 enabled at the lower level.

		If for some reason you would want another encoding, just define the
		PYTHONIOENCODING environment variable. This will probably hurt though,
		because many things in Licorn® assume a modern UTF-8 underlying OS.

		Some discussions:

		- http://drj11.wordpress.com/2007/05/14/python-how-is-sysstdoutencoding-chosen/
		- http://www.haypocalc.com/wiki/Python_Unicode (in french)
		- http://stackoverflow.com/questions/1473577/writing-unicode-strings-via-sys-stdout-in-python
		- http://stackoverflow.com/questions/492483/setting-the-correct-encoding-when-piping-stdout-in-python
		- http://stackoverflow.com/questions/4374455/how-to-set-sys-stdout-encoding-in-python-3
	"""

	# WARNING: 'UTF-8' is OK, 'utf-8' is not. It borks the ipython
	# shell prompt and readline() doesn't work anymore.
	default_encoding = os.getenv('PYTHONIOENCODING', 'UTF-8')

	if sys.getdefaultencoding() != default_encoding:
		reload(sys)
		sys.setdefaultencoding(default_encoding)

	if sys.stdout.encoding != default_encoding:
		sys.stdout = codecs.getwriter(default_encoding)(sys.stdout)

	if sys.stderr.encoding != default_encoding:
		sys.stderr = codecs.getwriter(default_encoding)(sys.stderr)

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

	def nothing():
		return True

	def clear_dmidecode(module):
		""" See `core.configuration` for WHY we do that. """

		# here, we don't need to print warnings: we are just testing
		# if the module can be imported. Avoid polluting the display
		# with useless false-negative messages.
		try:
			module.get_warnings()
			module.clear_warnings()

		except AttributeError:
			# Old module version, see `core.configuration` for details.
			pass

	reqmods = (
		(u'gettext',   u'python-gettext',	None),
		(u'posix1e',   u'python-pylibacl',	None),
		(u'Pyro',      u'pyro',				None),
		(u'gobject',   u'python-gobject',	None),
		(u'netifaces', u'python-netifaces',	None),
		(u'ping',      u'python-pyip',		None),
		(u'ipcalc',    u'python-ipcalc',	None),
		(u'dumbnet',   u'python-dumbnet',	None),
		(u'pyudev',    u'python-pyudev',	None),
		(u'apt_pkg',   u'python-apt',		None),
		(u'crack',     u'python-cracklib',	None),
		(u'sqlite',    u'python-sqlite',	None),
		(u'pygments',  u'python-pygments',	None),
		(u'pyinotify', u'python-pyinotify',	None),
		(u'dbus',      u'python-dbus',		None),
		(u'dateutil',  u'python-dateutil',	None),
		(u'pybonjour', u'pybonjour',		None),
		(u'dmidecode', u'python-dmidecode',	clear_dmidecode),
		# dmidecode needs libxml2 and even on Ubuntu 12.04, there is
		# no valid dependancy in the debian package. Gosh!
		(u'libxml2',   u'python-libxml2',	None),
		)

	# for more dependancies (needed by the WMI) see `upgrades/…`

	reqmods_needed = []
	reqpkgs_needed = []

	optmods = (
		(u'xattr',    u'python-xattr',		None),
		(u'ldap',     u'python-ldap',		None),
		(u'utmp',     u'python-utmp',		None),
		# The modules `plistlib`, `uuid`,
		# don't need to be checked, they're part of standard
		# python dist-packages.
		)

	optmods_needed = []
	optpkgs_needed = []

	for modtype, modlist in (('required', reqmods), ('optional', optmods)):
		for mod, pkg, postfunc in modlist:
			try:
				module = __import__(mod, globals(), locals())

			except ImportError:
				traceback.print_exc()

				if modtype == 'required':
					reqmods_needed.append(mod)
					reqpkgs_needed.append(pkg)

				else:
					optmods_needed.append(mod)
					optpkgs_needed.append(pkg)

			else:
				if postfunc:
					postfunc(module)
				del module

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

	if os.geteuid() == 0:
		# test dependancies only if root. normal users in CLI
		# commands don't need that bunch of imports, they should
		# already be there when root (or equiv) installed Licorn®.
		check_python_modules_dependancies()

	# not needed in normal conditions.
	#setup_sys_path()

# do the bootstrap, we we are first imported.
bootstrap()

# export a method for fsapi.
__all__ = ('getcwd', )

if __name__ == "__main__":
	sys.stdout.write(getcwd())
