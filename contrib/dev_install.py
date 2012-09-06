#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Licorn® developper install script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Meant to be launched from repository root directory,
via the `Makefile` target `devinstall`. It will setup
the local machine to run licorn from the development
directory, making code-changes immediately visible.

When Licorn® is installed like this, you can run the daemons
with `-rvD` arguments, and just hit `[Control-R]` on their
consoles when you change Python code.

.. warning:: this kind of installation is not suitable
	for production environments!

.. note:: This installation script will alter :program:`sudo`
	configuration, but there is no automated way to revert the
	alteration. When deinstalling, you have to do it yourself.
	BTW, the modifications won't hurt, and :program:`sudo`
	remains fully functionnal, even if Licorn® is not installed.

.. versionadded:: 1.3

:copyright:
	* 2012 Olivier Cortès <olive@licorn.org>
	* 2012 META IT - Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 3
"""

import sys, os, re, time, subprocess, getpass, traceback, errno
from threading import Thread

def run_command(cmd, pipe=False):
	if pipe:
		return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

	else:
		return subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].strip()

def getcwd():
	""" The cwd comes from `make devinstall` which bootstraps foundations to
		find the CWD, keeping any eventual symlink, not doing `os.abspath()`.

		If that fails for any reason (
		"""
	for arg in sys.argv:
		if arg.startswith('DEVEL_DIR'):
			return arg.split('=')[1]

	return os.getcwd()

devel_dir      = getcwd()
config_dir     = '/etc/licorn'
share_dir      = '/usr/share/licorn'
distro         = run_command(['lsb_release', '-i', '-s'])
rel_ver        = run_command(['lsb_release', '-r', '-s'])

# licornd depend on these to run.
base_packages  = ('pyro', 'python-pylibacl', 'python-ldap', 'python-xattr',
				'python-netifaces', 'python-dumbnet', 'python-pyip',
				'python-ipcalc', 'python-dbus', 'python-gobject', 'gettext',
				'python-pygments', 'python-apt', 'python-pyinotify',
				'python-sqlite', 'python-cracklib', 'python-pip',
				'python-dmidecode', 'python-libxml2', 'python-dateutil',
				'python-utmp', 'nmap', 'screen',
				# LXC-environment forgotten packages
				'psmisc')

# DEV and test-suite related packages
# separate these, they don't exist on Lucid,
# and are not strictly needed to run Licorn®
dev_packages    = ('git-core', 'git-flow', 'python-py', 'acl', 'attr', 'colordiff')

# build-* are not strictly needed, but in case we need to install C-python
# modules from source (via PIP), they need to be already installed.
build_packages  = ('build-essential', 'python-all-dev', 'debhelper',
				'devscripts', 'dupload')

# NOTE: python-sphinx is not installed, because it's notstrictly
# required (only for doc building), and on "older" distros it will
# pull in a non-wanted old version of Jinja2 < 2.6.

def err(*args):
	""" just print something on stderr. """
	print >> sys.stderr, ' '.join(str(e) for e in args)
def no_fail(*args):
	try:
		#print '>> running', '%s(%s)' % (args[0].__name__, ', '.join(args[1:]))
		args[0](*args[1:])
	except Exception, e:
		if hasattr(e, 'errno'):
			#if e.errno not in (errno.ENOENT, errno.EEXIST):
			err('	ignored', e, 'for command', '%s(%s)' % (
						args[0].__name__, ', '.join(str(a) for a in args[1:])))
			#traceback.print_exc()
		else:
			err('	ignored', e)
			traceback.print_exc()
def symlink(*args):
	""" Encapsulate `os.symlink()` to not fail if the operation
		has already been done on the local system. """
	no_fail(os.symlink, *args)
def unlink(*args):
	""" Encapsulate `os.unlink()` to not fail if the operation
		has already been done on the local system. """
	no_fail(os.unlink, *args)
def makedirs(*args):
	""" Encapsulate `os.makedirs()` to not fail if the operation
		has already been done on the local system. """
	no_fail(os.makedirs, *args)
def execute(*args):
	""" Encapsulate `subprocess.check_output()` to not fail if
		the operation has already been done on the local system. """
	no_fail(run_command, *args)
def _apt_install_cmd(package):
	""" Private. do not use directly. """
	olddebfront = os.environ.get('DEBIAN_FRONTEND', None)
	os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

	out, errors = run_command(['apt-get', 'install',
				'--quiet', '--yes', '--force-yes'] + package, pipe=True)
	if errors:
		err(errors.strip())

	if olddebfront:
		os.environ['DEBIAN_FRONTEND'] = olddebfront
def _pip_install_cmd(package):
	""" Private. do not use directly. """

	out, errors = run_command(['pip', 'install'] + package, pipe=True)
	if errors:
		err(errors.strip())
def apt_install(packages_names):
	#no_fail(_apt_install_cmd, packages_string.split())

	# install them one at a time: in case one fails, the other
	# will be installed. This will be easier to debug when
	# licornd launches and doesn't find a particular one.
	for package in packages_names:
		err('	Installing {0}…'.format(package))
		_apt_install_cmd([package])
def pip_install(packages_names):
	#no_fail(_pip_install_cmd, packages_string.split())
	for package in packages_names:
		err('	Installing {0}…'.format(package))
		_pip_install_cmd([package])
def write_if_not_present(thefile, what_to_write, match_re):
	try:
		if re.search(match_re, open(thefile).read()) is None:
			err('Altering {0}.'.format(thefile))
			with open(thefile, 'ab') as f:
				f.write(what_to_write)

	except (IOError, OSError), e:
		if e.errno == errno.ENOENT:
			dirname, basename = os.path.split(thefile)
			makedirs(dirname)
			with open(thefile, 'ab') as f:
				f.write(what_to_write)
def install_all_packages():
	if distro in ('Ubuntu', 'Debian'):
		err('Downloading and installing packages, please wait…')
		err('	Updating packages sources…')
		run_command(('apt-get', 'update'))

		apt_install(base_packages)
		apt_install(dev_packages)
		apt_install(build_packages)

		# Now that we are sure that python-apt is installed, we can compare
		# release versions in a reliable way.
		from apt_pkg import version_compare
		import apt_pkg
		apt_pkg.init()

		if (distro == 'Ubuntu' and version_compare(rel_ver, '8.04') == 0
			) or (distro == 'Debian' and version_compare(rel_ver, '6.0') < 1):
			pip_install(('pyudev', ))
			unlink('/usr/lib/python2.5/site-packages/licorn')
			symlink(devel_dir, '/usr/lib/python2.5/site-packages/licorn')

		elif (distro == 'Ubuntu' and (
					version_compare(rel_ver, '10.04') == 0
					or version_compare(rel_ver, '10.10') == 0)
				) or (distro == 'Debian' and (
					version_compare(rel_ver, '6.0') >= 0
					and version_compare(rel_ver, '7.0') < 0)):
			pip_install(('pyudev', ))
			unlink('/usr/lib/python2.6/dist-packages/licorn')
			symlink(devel_dir, '/usr/lib/python2.6/dist-packages/licorn')

		elif (distro == 'Ubuntu' and version_compare(rel_ver, '11.04') >= 0
			) or (distro == 'Debian' and version_compare(rel_ver, '7.0') >=0):
			apt_install(('python-pyudev', ))
			unlink('/usr/lib/python2.7/dist-packages/licorn')
			symlink(devel_dir, '/usr/lib/python2.7/dist-packages/licorn')

		else:
			err('Your Ubuntu/Debian distro is not supported anymore. Please consider upgrading.')
	else:
		if '--packages-installed' not in sys.argv:
			err('Your distro is not officially supported. Please install the '
				'following packages and re-run this script with the '
				'`--packages-installed` argument:\n\n', base_packages, other_packages)
			sys.exit(1)
def user_post_installation():
	""" After the root-install part is done, add the local user to licorn
		system groups automatically for a more comfortable sysadmin experience.

		We add the remotessh group, else if openssh is installed, the user won't
		be able to remotely connect, which could be bad ;-)

		.. note:: for user installation, this script is not launched with sudo,
			to be able to catch the UID of the installing user. Thus, we have
			to insert 'sudo' in every command where it is needed.
	"""

	execute(['sudo', 'add', 'group', 'licorn-wmi', '--system' ])
	execute(['sudo', 'add', 'user', getpass.getuser(), 'admins,licorn-wmi,remotessh'])

	# terminate everyone before giving hand to the local John Root.
	execute(['/usr/sbin/licornd', '-k'])
	err('User installation finished.')

	if not '/usr/sbin' in os.environ['PATH'].split(':'):
		err('For a more comfortable experience, you should add `/usr/sbin` to your PATH.')

	sys.exit(0)
def make_symlinks():
	err('Symlinking everything from {0}, please wait…'.format(devel_dir))

	for executable in ('add', 'mod', 'del', 'chk', 'get'):
		unlink('/usr/bin/{0}'.format(executable))
		symlink('{0}/interfaces/cli/{1}.py'.format(devel_dir, executable),
				'/usr/bin/{0}'.format(executable))

	# get rid of current symlinks.
	for pyfile, daemon in (('main', 'licornd'), ('wmi', 'licornd-wmi')):
		unlink('/usr/sbin/{0}'.format(daemon))

		# current dev installs don't get the WMI process,
		# it has been merged back into the main daemon.
		if pyfile != 'wmi':
			symlink('{0}/daemon/{1}.py'.format(devel_dir, pyfile),
				'/usr/sbin/{0}'.format(daemon))

	makedirs(config_dir)
	makedirs(share_dir)

	write_if_not_present('{0}/licorn.conf'.format(config_dir), 'role = SERVER\n', r'\s*role')

	for src, dst in (
			('{0}/config/check.d'.format(devel_dir),
			'{0}/check.d'.format(config_dir)),

			('{0}/config/rdiff-backup-globs.conf'.format(devel_dir),
			'{0}/rdiff-backup-globs.conf'.format(config_dir)),

			('{0}/interfaces/wmi'.format(devel_dir),
			'{0}/wmi'.format(share_dir)),

			('{0}/core/backends/schemas'.format(devel_dir),
			'{0}/schemas'.format(share_dir)),

			('{0}/locale/fr.mo'.format(devel_dir),
			'/usr/share/locale/fr/LC_MESSAGES/licorn.mo'),
		):
		unlink(dst)
		symlink(src, dst)

	write_if_not_present('/etc/sudoers', '\n\n# Licorn® devinstall - do not remove this comment please\nDefaults	env_keep = "DISPLAY LTRACE LICORN_SERVER LICORN_DEBUG"\n%admins	ALL = (ALL:ALL) NOPASSWD: ALL\n', r'Defaults.*LTRACE')
def first_licornd_run():
	from licorn.foundations import process, fsapi

	# unlink the `upgrades` symlink, in case we are doing a fresh re-install
	# from another repository/branch. The daemon will recreate it automatically.
	from licorn.upgrades import upgrades_root
	unlink(upgrades_root)

	err('Launching licornd for the first time to check system configuration. '
										'Please wait, this can take a while…')

	# don't use our execute(), we want the output to shine.
	os.system('/usr/sbin/licornd -rcv')

	err('System installation finished.')

# ======================================================================= MAIN
#
# this script must be run with these arguments in this order (see Makefile):
if '--install-all-packages' in sys.argv:
	install_all_packages()

elif '--user-post-installation' in sys.argv:
	user_post_installation()

elif '--make-symlinks' in sys.argv:
	make_symlinks()

else:
	first_licornd_run()
