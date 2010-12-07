	# -*- coding: utf-8 -*-
"""
Licorn core - http://dev.licorn.org/documentation/core

configuration - Unified Configuration API for an entire linux server system

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2005 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2
"""

import sys, os, re, socket
from gettext import gettext as _

from licorn.foundations           import logging, exceptions
from licorn.foundations           import readers, fsapi, network
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import distros, servers, mailboxes, \
											licornd_roles
from licorn.foundations.base      import LicornConfigObject, Singleton, \
											Enumeration, FsapiObject
from licorn.foundations.classes   import FileLock

from licorn.core         import LMC
from licorn.core.classes import GiantLockProtectedObject

class LicornConfiguration(Singleton, GiantLockProtectedObject):
	""" Contains all the underlying system configuration as attributes.
		Defines some methods for modifying the configuration.
	"""

	# bypass multiple init and del calls (we are a singleton)
	init_ok     = False
	del_ok      = False

	def __init__(self, minimal=False, batch=False):
		""" Gather underlying system configuration and load it for licorn.* """

		if LicornConfiguration.init_ok:
			return

		assert ltrace('configuration', '> __init__(minimal=%s, batch=%s)' % (
			minimal, batch))

		GiantLockProtectedObject.__init__(self, name='configuration')

		self.app_name = 'Licorn®'

		self.mta = None
		self.ssh = None

		# THIS install_path is used in keywords / keywords gui, not elsewhere.
		# it is a hack to be able to test guis when Licorn is not installed.
		# → this is for developers only.
		self.install_path = os.getenv("LICORN_ROOT", "/usr")
		if self.install_path == '.':
			self.share_data_dir = '.'
		else:
			self.share_data_dir = "%s/share/licorn" % self.install_path

		try:
			import tempfile
			self.tmp_dir = tempfile.mkdtemp()

			# WARNING: beside this point, order of method is VERY important,
			# their contents depend on each other.

			# WARNING: don't change order of these.
			self.SetUsersDefaults()
			self.SetGroupsDefaults()

			self.SetBaseDirsAndFiles()
			self.FindUserDir()

			if not minimal:
				self.load1(batch=batch)
			# must be done to find a way to find our network server.
			self.FindDistro()

			if not minimal:
				self.load2(batch=batch)

			# this has to be done LAST, in order to eventually override any
			# other configuration directive (eventually coming from
			# Ubuntu/Debian, too).
			self.load_configuration_from_main_config_file()
			self.load_missing_directives_from_factory_defaults()

			self.convert_configuration_values()
			self.check_configuration_directives()

			if not minimal:
				self.load3(batch=batch)

		except exceptions.LicornException, e:
			raise exceptions.BadConfigurationError(
				'''Configuration initialization failed: %s''' % e)

		LicornConfiguration.init_ok = True
		assert ltrace('configuration', '< __init__()')
	def load(self, batch=False):
		""" just a compatibility method. """
		self.load1(batch=batch)
		self.load2(batch=batch)
		self.load3(batch=batch)
	def load1(self, batch=False):
		self.LoadManagersConfiguration(batch=batch)
		self.set_acl_defaults()
	def load2(self, batch=False):
		self.LoadShells()
		self.LoadSkels()
		self.detect_services()
		self.network_infos()
	def load3(self, batch=False):
		self.load_nsswitch()
		# TODO: monitor configuration files from a thread !

	#
	# make LicornConfiguration object be usable as a context manager.
	#
	def __enter__(self):
		pass
	def __exit__(self, type, value, tb):
		self.CleanUp()
	def set_controller(self, name, controller):
		#setattr(LMC, name, controller)
		pass
	def CleanUp(self, listener=None):
		"""This is a sort of destructor. Clean-up before being deleted…"""

		if LicornConfiguration.del_ok:
			return

		assert ltrace('configuration', '> CleanUp(%s)' %
			LicornConfiguration.del_ok)

		try:
			import shutil
			# this is safe because tmp_dir was created with tempfile.mkdtemp()
			shutil.rmtree(self.tmp_dir)
		except (OSError, IOError), e:
			if e.errno == 2:
				logging.warning2('''Temporary directory %s has vanished '''
					'''during run, or already been wiped by another process.'''
					% self.tmp_dir, listener=listener)
			else:
				raise e

		LicornConfiguration.del_ok = True
		assert ltrace('configuration', '< CleanUp()')
	def SetBaseDirsAndFiles(self):
		""" Find and create temporary, data and working directories."""

		assert ltrace('configuration', '> SetBaseDirsAndFiles()')

		self.config_dir              = "/etc/licorn"
		self.check_config_dir        = self.config_dir + "/check.d"
		self.main_config_file        = self.config_dir + "/licorn.conf"
		self.backup_config_file      = self.config_dir + "/backup.conf"

		# system profiles, compatible with gnome-system-tools
		self.profiles_config_file    = self.config_dir + "/profiles.xml"

		self.privileges_whitelist_data_file = (
			self.config_dir + "/privileges-whitelist.conf")
		self.keywords_data_file = self.config_dir + "/keywords.conf"

		# extensions to /etc/group
		self.extendedgroup_data_file = self.config_dir + "/groups"

		self.SetDefaultNamesAndPaths()

		self.home_backup_dir         = (
			"%s/backup" % self.defaults.home_base_path)
		self.home_archive_dir        = (
			"%s/archives" % self.defaults.home_base_path)

		# TODO: is this to be done by package maintainers or me ?
		self.CreateConfigurationDir()

		assert ltrace('configuration', '< SetBaseDirsAndFiles()')
	def FindUserDir(self):
		""" if ~/ is writable, use it as user_dir to store some data, else
			use a tmp_dir."""
		try:
			home = os.environ["HOME"]
		except KeyError:
			home = None

		if home and os.path.exists(home):

			try:
				# if our home exists and we can write in it,
				# assume we are a standard user.
				fakefd = open(home + "/.licorn.fakefile", "w")
				fakefd.close()
				os.unlink(home + "/.licorn.fakefile")
				self.user_dir			= home + "/.licorn"
				self.user_config_file	= self.user_dir + "/config"

			except (OSError, IOError):
				# we are «apache» or another special user (aesd…), we don't
				# have a home, but need a dir to put lock-files in.
				self.user_dir			= self.tmp_dir
				self.user_config_file	= None
		else:
			# we are «apache» or another special user (aesd…), we don't
			# have a home, but need a dir to put lock-files in.
			self.user_dir			= self.tmp_dir
			self.user_config_file	= None

		self.user_data_dir		= self.user_dir + "/data"

		if not os.path.exists(self.user_dir):
			try:
				os.makedirs(self.user_data_dir)
				import stat
				os.chmod(self.user_dir,
					stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR )
				logging.info("Automatically created %s." % \
					stylize(ST_PATH, self.user_dir + "[/data]"))
			except OSError, e:
				raise exceptions.LicornRuntimeError(
					'''Can't create / chmod %s[/data]:\n\t%s''' % (
						self.user_dir, e))
	def _load_configuration(self, conf):
		""" Build the licorn configuration object from a dict. """

		assert ltrace('configuration', '| _load_configuration(%s)' % conf)

		for key in conf.keys():
			subkeys = key.split('.')
			if len(subkeys) > 1:
				curobj = self
				level  = 1
				for subkey in subkeys[:-1]:
					if not hasattr(curobj, subkey):
						setattr(curobj, subkey, LicornConfigObject(level=level))
					#down one level.
					curobj = getattr(curobj, subkey)
					level += 1
				if not hasattr(curobj, subkeys[-1]):
					setattr(curobj, subkeys[-1], conf[key])
			else:
				if not hasattr(self, key):
					setattr(self, key,conf[key])
	def noop(self):
		""" No-op function, called when connecting pyro, to check if link
		is OK betwwen the server and the client. """
		assert ltrace('configuration', '| noop(True)')
		return True
	def load_missing_directives_from_factory_defaults(self):
		""" The defaults set here are expected to exist
			by other parts of the programs.

			Note: we use port 299 for pyro. This is completely unusual. Port 299
			doesn't seem to be reserved in a recent /etc/services file, and this
			ensure that we are root when binding the port, and thus provide a
			*small* security guarantee (any attacker but first gain root
			privileges or crash our daemons to bind the port and spoof our
			protocol). """

		assert ltrace('configuration', '| load_missing_directives_from_factory_defaults()')

		mandatory_dict = {
			'licornd.role'                 : licornd_roles.UNSET,
			'licornd.pyro.port'            : os.getenv('PYRO_PORT', 299),
			# don't set in case there is no eth0 on the system.
			#'licornd.pyro.listen_address': 'if:eth0'
			'licornd.threads.pool_members' : 5,
			'licornd.threads.wipe_time'    : 600,   # 10 minutes
			'licornd.syncer.port'          : 3344,
			'licornd.searcher.port'        : 3355,
			'licornd.buffer_size'          : 16*1024,
			'licornd.log_file'             : '/var/log/licornd.log',
			'licornd.pid_file'             : '/var/run/licornd.pid',
			'licornd.cache_file'           : '/var/cache/licorn/licornd.db',
			'licornd.socket_path'          : '/var/run/licornd.sock',
			'licornd.inotifier.enabled'    : True,
			'licornd.wmi.enabled'          : True,
			'licornd.wmi.group'            : 'licorn-wmi',
			'licornd.wmi.listen_address'   : 'localhost',
			'licornd.wmi.port'             : 3356,
			'licornd.wmi.pid_file'         : '/var/run/licornd-wmi.pid',
			'licornd.wmi.log_file'         : '/var/log/licornd-wmi.log',
			'experimental.enabled'         : False,
			}

		self._load_configuration(mandatory_dict)
	def convert_configuration_values(self):
		""" take components of human written configuration directive, and
		convert them to machine-friendly values. """

		assert ltrace('configuration', '| convert_configuration_values()')

		if self.licornd.role not in licornd_roles:
			# use upper() to avoid bothering user if he has typed "server"
			# instead of "SERVER". Just be cool when possible.
			if hasattr(licornd_roles, self.licornd.role.upper()):
				self.licornd.role = getattr(licornd_roles,
					self.licornd.role.upper())

		if hasattr(self.licornd.pyro, 'listen_address'):
			if self.licornd.pyro.listen_address[:3] == 'if:' \
				or self.licornd.pyro.listen_address[:6] == 'iface:':
					try:
						self.licornd.pyro.listen_address = \
							network.interface_address(
								self.licornd.pyro.listen_address.split(':')[1])
					except (IOError, OSError), e:
						raise exceptions.BadConfigurationError(
							'''Problem getting interface %s address (was: '''
							'''%s).''' % (
								self.licornd.pyro.listen_address.split(':')[1],
								e)
							)
			else:
				try:
					# validate the IP address
					socket.inet_aton(self.licornd.pyro.listen_address)
				except socket.error:
					try:
						socket.gethostbyname(self.licornd.pyro.listen_address)
						# keep the hostname, it resolves.
					except socket.gaierror:
						raise exceptions.BadConfigurationError('Bad IP address '
							'or hostname %s. Please check the syntax.' %
							self.licornd.pyro.listen_address)
			# TODO: check if the IP or the hostname is really on the local host.
			# check if self.licornd.pyro.listen_address \
			# in [ network.interface_address(x) for x in network.list_interfaces() ]
	def check_configuration_directives(self):
		""" Check directives which must be set, and values, for correctness. """

		assert ltrace('configuration', '| check_configuration_directives()')

		self.check_directive_daemon_role()
		self.check_directive_daemon_threads()
	def check_directive_daemon_role(self):
		""" check the licornd.role directive for correctness. """

		assert ltrace('configuration', '| check_directive_daemon_role()')

		if self.licornd.role == licornd_roles.UNSET or \
			self.licornd.role not in licornd_roles:
			raise exceptions.BadConfigurationError('''%s is currently '''
				'''unset or invalid in %s. Please set it to either %s or '''
				'''%s and retry.''' % (
					stylize(ST_SPECIAL, 'licornd.role'),
					stylize(ST_PATH, self.main_config_file),
					stylize(ST_COMMENT, 'SERVER'),
					stylize(ST_COMMENT, 'CLIENT')
					)
				)
		elif self.licornd.role == licornd_roles.CLIENT:
			self.server_main_address = network.find_server(self)
	def check_directive_daemon_threads(self):
		""" check the pingers number for correctness. """
		assert ltrace('configuration', '| check_directive_daemon_threads()')

		raise_pinger_exception = False
		pingers = self.licornd.threads.pool_members
		try:
			# be sure this is an int().
			pingers = int(pingers)
		except ValueError:
			raise_pinger_exception = True
		else:
			if pingers < 0:
				pingers = abs(pingers)

			if pingers > 25:
				raise_pinger_exception = True

		if raise_pinger_exception:
			raise exceptions.BadConfigurationError('''invalid value "%s" '''
				'''for %s configuration directive: it must be an integer '''
				'''between 0 and 25.''' (
					stylize(ST_COMMENT, pingers),
					stylize(ST_ , 'licornd.threads.pool_members')))

	def load_configuration_from_main_config_file(self):
		"""Load main configuration file, and set mandatory defaults
			if it doesn't exist."""

		assert ltrace('configuration',
			'> load_configuration_from_main_config_file()')

		try:
			self._load_configuration(readers.shell_conf_load_dict(
				self.main_config_file,
				convert='full'))
		except IOError, e:
			if e.errno != 2:
				# errno == 2 is "no such file or directory" -> don't worry if
				# main config file isn't here, this is not required.
				raise e

		assert ltrace('configuration', '< load_configuration_from_main_config_file()')
	def load_nsswitch(self):
		""" Load the NS switch file. """

		self.nsswitch = (
			readers.simple_conf_load_dict_lists('/etc/nsswitch.conf'))
	def save_nsswitch(self):
		""" write the nsswitch.conf file. This method is meant to be called by
		a backend which has modified. """

		assert ltrace('configuration', '| save_nsswitch()')

		nss_data = ''

		for key in self.nsswitch:
			nss_data += '%s:%s%s\n' % (key,
			' ' * (15-len(key)),
			' '.join(self.nsswitch[key]))

		nss_lock = FileLock(self, '/etc/nsswitch.conf')
		nss_lock.Lock()
		open('/etc/nsswitch.conf', 'w').write(nss_data)
		nss_lock.Unlock()
	def CreateConfigurationDir(self):
		"""Create the configuration dir if it doesn't exist."""

		if not os.path.exists(self.config_dir):
			try:
				os.makedirs(self.config_dir)
				logging.info("Automatically created %s." % \
					stylize(ST_PATH, self.config_dir))
			except (IOError,OSError):
				# user is not root, forget it !
				pass
	def FindDistro(self):
		""" Determine which Linux / BSD / else distro we run on. """

		self.distro = None

		if os.name is "posix":
			if os.path.exists( '/etc/lsb-release' ):
				lsb_release = readers.shell_conf_load_dict('/etc/lsb-release')

				if lsb_release['DISTRIB_ID'] == 'Licorn':
					self.distro = distros.UBUNTU
				elif lsb_release['DISTRIB_ID'] == "Ubuntu":
					if lsb_release['DISTRIB_CODENAME'] in ('maverick', 'lucid',
						'karmik', 'jaunty'):
						self.distro = distros.UBUNTU
					else:
						raise exceptions.LicornRuntimeError(
							'''This Ubuntu version is not '''
							'''supported, sorry !''')
			else:
				# OLD / non-lsb compatible system or BSD
				if  os.path.exists( '/etc/gentoo-release' ):
					raise exceptions.LicornRuntimeError(
						"Gentoo is not yet supported, sorry !")
				elif  os.path.exists( '/etc/debian_version' ):
					raise exceptions.LicornRuntimeError(
						"Old Debian systems are not supported, sorry !")
				elif  os.path.exists( '/etc/SuSE-release' ) \
					or os.path.exists( '/etc/suse-release' ):
					raise exceptions.LicornRuntimeError(
						"SuSE are not yet supported, sorry !")
				elif  os.path.exists( '/etc/redhat_release' ) \
					or os.path.exists( '/etc/redhat-release' ):
					raise exceptions.LicornRuntimeError(
						"RedHat/Mandriva is not yet supported, sorry !")
				else:
					raise exceptions.LicornRuntimeError(
						"Unknown Linux Distro, sorry !")
		else:
			raise exceptions.LicornRuntimeError(
				"Not on a supported system ! Please send a patch ;-)")

		del(lsb_release)
	def detect_services(self):
		""" Concentrates all calls for service detection on the current system
		"""
		self.detect_OpenSSH()

		self.FindMTA()
		self.FindMailboxType()
	def detect_OpenSSH(self):
		""" OpenSSH related code.
			 - search for OpenSSHd configuration.
			 - if found, verify remotessh group exists.
			 - TODO: implement sshd_config modifications to include
				'AllowGroups remotessh'
		"""
		self.ssh = LicornConfigObject()

		#piddir   = "/var/run"
		#spooldir = "/var/spool"

		#
		# Finding Postfix
		#

		if self.distro in (
			distros.LICORN,
			distros.UBUNTU,
			distros.DEBIAN,
			distros.REDHAT,
			distros.GENTOO,
			distros.MANDRIVA,
			distros.NOVELL
			):

			if os.path.exists("/etc/ssh/sshd_config"):
				self.ssh.enabled = True
				self.ssh.group = 'remotessh'

			else:
				self.ssh.enabled = False

		else:
			logging.progress(_("SSH detection not supported yet on your system."
				"Please get in touch with %s." % \
				LicornConfiguration.developers_address))

		return self.ssh.enabled
	def check_OpenSSH(self, batch=False, auto_answer=None):
		""" Verify mandatory defaults for OpenSSHd. """
		if not self.ssh.enabled:
			return

		logging.progress('Checking existence of group %s…' %
			stylize(ST_NAME, self.ssh.group))

		if not LMC.groups.exists(name=self.ssh.group):
			LMC.groups.AddGroup(name=self.ssh.group,
				description=_('Users allowed to connect via SSHd'),
				system=True, batch=True)
	def FindMTA(self):
		"""detect which is the underlying MTA."""

		self.mta = None

		piddir   = "/var/run"
		spooldir = "/var/spool"

		#
		# Finding Postfix
		#

		if self.distro == distros.UBUNTU:
			# postfix is chrooted on Ubuntu Dapper.
			if os.path.exists("/var/spool/postfix/pid/master.pid"):
				self.mta = servers.MTA_POSTFIX
				return
		else:
			if os.path.exists("%s/postfix.pid" % piddir):
				self.mta = servers.MTA_POSTFIX
				return

		#
		# Finding NullMailer
		#
		if os.path.exists("%s/nullmailer/trigger" % spooldir):
			self.mta = servers.MTA_NULLMAILER
			return

		self.mta = servers.MTA_UNKNOWN
		logging.progress('''MTA not installed or unsupported, please get in '''
			'''touch with dev@licorn.org.''')
	def FindMailboxType(self):
		"""Find how the underlying system handles Mailboxes
			(this can be Maidlir, mail spool,
			and we must find where they are)."""

		# a sane (but arbitrary) default.
		# TODO: detect this from /etc/…
		self.users.mailbox_auto_create = True
		self.users.mailbox = None
		self.users.mailbox_type = mailboxes.NONE

		if self.mta == servers.MTA_POSTFIX:

			if self.distro in (distros.UBUNTU,
				distros.DEBIAN,
				distros.GENTOO):
				postfix_main_cf = \
					readers.shell_conf_load_dict('/etc/postfix/main.cf')

			try:
				self.users.mailbox_base_dir = \
					postfix_main_cf['mailbox_spool']
				self.users.mailbox_type     = \
					mailboxes.VAR_MBOX
			except KeyError:
				pass

			try:
				self.users.mailbox = \
					postfix_main_cf['home_mailbox']

				if self.users.mailbox[-1:] == '/':
					self.users.mailbox_type = \
						mailboxes.HOME_MAILDIR
				else:
					self.users.mailbox_type = \
						mailboxes.HOME_MBOX

			except KeyError:
				pass

			assert logging.debug2("Mailbox type is %d and base is %s." % (
				self.users.mailbox_type,
				self.users.mailbox))

		elif self.mta == servers.MTA_NULLMAILER:

			# mail is not handled on this machine, forget the mailbox creation.
			self.users.mailbox_auto_create = False

		elif self.mta == servers.MTA_UNKNOWN:

			# totally forget about mail things.
			self.users.mailbox_auto_create = False

		else:
			# totally forget about mail things.
			self.users.mailbox_auto_create = False
			logging.progress('''Mail{box,dir} system not supported yet. '''
				'''Please get in touch with dev@licorn.org.''')
	def LoadShells(self):
		"""Find valid shells on the local system"""

		self.users.shells = []

		# specialty on Debian / Ubuntu: /etc/shells contains shells that
		# are not installed on the system. What is then the purpose of this
		# file, knowing its definitions:
		# «/etc/shells contains the valid shells on a given system»…
		# specialty 2: it does not contains /bin/false…

		for shell in readers.very_simple_conf_load_list("/etc/shells"):
			if os.path.exists(shell):
				self.users.shells.append(shell)

		if "/bin/false" not in self.users.shells:
			self.users.shells.append("/bin/false")

		# hacker trick !
		if os.path.exists("/usr/bin/emacs"):
			self.users.shells.append("/usr/bin/emacs")
	def LoadSkels(self):
		"""Find skel dirs on the local system."""

		self.users.skels = []

		if os.path.isdir("/etc/skel"):
			self.users.skels.append("/etc/skel")

		import stat

		for skel_path in ("%s/skels" % \
			self.defaults.home_base_path, "/usr/share/skels"):
			if os.path.exists(skel_path):
				try:
					for new_skel in fsapi.minifind(path=skel_path,
						type=stat.S_IFDIR, mindepth=2, maxdepth=2):
						self.users.skels.append(new_skel)
				except OSError, e:
					logging.warning('''Custom skels must have at least %s '''
						'''perms on dirs and %s on files:\n\t%s''' % (
							stylize(ST_MODE,
								"u+rwx,g+rx,o+rx"),
							stylize(ST_MODE,
								"u+rw,g+r,o+r"), e))

	### Users and Groups ###
	def LoadManagersConfiguration(self, batch=False, auto_answer=None,
		listener=None):
		""" Load Users and Groups managements configuration. """

		assert ltrace('configuration', '> LoadManagersConfiguration(batch=%s)' %
			batch)

		# defaults to False, because this is mostly annoying. Administrator must
		# have a good reason to hide groups.
		self.groups.hidden = None

		add_user_conf = self.CheckAndLoadAdduserConf(batch=batch,
			auto_answer=auto_answer, listener=listener)
		self.users.min_passwd_size = 8
		self.users.uid_min         = add_user_conf['FIRST_UID']
		self.users.uid_max         = add_user_conf['LAST_UID']
		self.groups.gid_min        = add_user_conf['FIRST_GID']
		self.groups.gid_max        = add_user_conf['LAST_GID']
		self.users.system_uid_min  = \
			add_user_conf['FIRST_SYSTEM_UID']
		self.users.system_uid_max  = \
			add_user_conf['LAST_SYSTEM_UID']
		self.groups.system_gid_min = \
			add_user_conf['FIRST_SYSTEM_GID']
		self.groups.system_gid_max = \
			add_user_conf['LAST_SYSTEM_GID']

		# fix #74: map uid/gid above 300/500, to avoid interfering with
		# Ubuntu/Debian/RedHat/whatever system users/groups. This will raise
		# chances for uid/gid synchronization between servers (or client/server)
		# to success (avoid a machine's system users/groups to take identical
		# uid/gid of another machine system users/groups ; whatever the name).
		if self.users.system_uid_min < 300:
			self.users.system_uid_min = 300
		if self.groups.system_gid_min < 300:
			self.groups.system_gid_min = 300

		#
		# WARNING: these values are meant to be used like this:
		#
		#  |<-               privileged              ->|<-                            UN-privileged                           ->|
		#    (reserved IDs)  |<- system users/groups ->|<-  standard users/groups ->|<- system users/groups ->|  (reserved IDs)
		#  |-------//--------|------------//-----------|--------------//------------|-----------//------------|------//---------|
		#  0            system_*id_min             *id_min                       *id_max             system_*id_max           65535
		#
		# in unprivileged system users/groups, you will typically find www-data, proxy, nogroup, samba machines accounts…
		#

		#
		# The default values are referenced in CheckAndLoadAdduserConf() too.
		#
		for (attr_name, conf_key) in (
			('base_path', 'DHOME'),
			('default_shell', 'DSHELL'),
			('default_skel',  'SKEL'),
			('default_gid',   'USERS_GID')
			):
			val = add_user_conf[conf_key]
			setattr(self.users, attr_name, val)

		# first guesses to find Mail system.
		self.users.mailbox_type = 0
		self.users.mailbox      = ""

		try:
			self.users.mailbox      = add_user_conf["MAIL_FILE"]
			self.users.mailbox_type = \
				mailboxes.HOME_MBOX
		except KeyError:
			pass

		try:
			self.users.mailbox_base_dir = \
				add_user_conf["MAIL_DIR"]
			self.users.mailbox_type     = \
				mailboxes.VAR_MBOX
		except KeyError:
			pass

		# ensure /etc/login.defs  and /etc/defaults/useradd comply with
		# /etc/adduser.conf tweaked for Licorn®.
		self.CheckLoginDefs(batch=batch, auto_answer=auto_answer,
			listener=listener)
		self.CheckUserAdd(batch=batch, auto_answer=auto_answer,
			listener=listener)

		assert ltrace('configuration', '< LoadManagersConfiguration()')
	def SetDefaultNamesAndPaths(self):
		""" *HARDCODE* some names before we pull them out
			into configuration files."""

		self.defaults = Enumeration()

		self.defaults.home_base_path = '/home'
		self.defaults.check_homedir_filename = '00_default'

		# WARNING: Don't translate this. This still has to be discussed.
		# TODO: move this into a plugin
		self.defaults.admin_group = 'admins'

		# TODO: autodetect this & see if it not autodetected elsewhere.
		#self.defaults.quota_device = "/dev/hda1"
	def SetUsersDefaults(self):
		"""Create self.users attributes and start feeding it."""

		self.users = LicornConfigObject()

		# config dir
		self.users.config_dir = '.licorn'
		self.users.check_config_file = self.users.config_dir + '/check.conf'

		self.users.group = 'users'

		# FIXME: don't hardcode this (this will come from the apache extension)
		self.users.apache_dir = 'public_html'

		# see groupadd(8), coming from addgroup(8)
		self.users.login_maxlenght = 31

		# the _xxx variables are needed for gettextized interfaces
		# (core and CLI are NOT gettextized)
		self.users.names = LicornConfigObject()
		self.users.names.singular = 'user'
		self.users.names.plural = 'users'
		self.users.names._singular = _('user')
		self.users.names._plural = _('users')
	def SetGroupsDefaults(self):
		"""Create self.groups attributes and start feeding it."""

		self.groups = LicornConfigObject()
		self.groups.apache_dir = self.users.apache_dir

		self.groups.guest_prefix = 'gst-'
		self.groups.resp_prefix = 'rsp-'

		# maxlenght comes from groupadd(8), itself coming from addgroup(8)
		# 31 - len(prefix)
		self.groups.name_maxlenght = 27

		# the _xxx variables are needed for gettextized interfaces
		# (core and CLI are NOT gettextized)
		self.groups.names = LicornConfigObject()
		self.groups.names.singular = 'group'
		self.groups.names.plural = 'groups'
		self.groups.names._singular = _('group')
		self.groups.names._plural = _('groups')
	def set_acl_defaults(self):
		""" Prepare the basic ACL configuration inside us. """

		assert ltrace("configuration", '| set_acl_defaults()')

		self.acls = LicornConfigObject()
		self.acls.group = 'acl'
		self.acls.groups_dir = "%s/%s" % (
			self.defaults.home_base_path,
			self.groups.names.plural)
		self.acls.acl_base = 'u::rwx,g::---,o:---'
		self.acls.acl_mask = 'm:rwx'
		self.acls.acl_admins_ro = 'g:%s:r-x' % \
			self.defaults.admin_group
		self.acls.acl_admins_rw = 'g:%s:rwx' % \
			self.defaults.admin_group
		self.acls.acl_users = '--x' \
			if self.groups.hidden else 'r-x'
		self.acls.file_acl_base = 'u::rw@UX,g::---,o:---'
		self.acls.acl_restrictive_mask = 'm:r-x'
		self.acls.file_acl_mask = 'm:rw@GX'
		self.acls.file_acl_restrictive_mask = 'm:rw@GX'


	def CheckAndLoadAdduserConf(self, batch=False, auto_answer=None,
		listener=None):
		""" Check the contents of adduser.conf to be compatible with Licorn.
			Alter it, if not.
			Then load it in a way i can be used in LicornConfiguration.
		"""

		assert ltrace('configuration', '> CheckAndLoadAdduserConf(batch=%s)' %
			batch)

		adduser_conf       = '/etc/adduser.conf'
		adduser_conf_alter = False
		adduser_data       = open(adduser_conf, 'r').read()
		adduser_dict       = readers.shell_conf_load_dict(data=adduser_data)

		# warning: the order is important: in a default adduser.conf,
		# only {FIRST,LAST}_SYSTEM_UID are
		# present, and we assume this during the file patch.
		defaults = (
			('DHOME', '%s/users' % \
				self.defaults.home_base_path),
			('DSHELL', '/bin/bash'),
			('SKEL',   '/etc/skel'),
			('GROUPHOMES',  'no'),
			('LETTERHOMES', 'no'),
			('USERGROUPS',  'no'),
			('USERS_GID', 100),
			('LAST_GID',  29999),
			('FIRST_GID', 10000),
			('LAST_UID',  29999),
			('FIRST_UID', 1000),
			('LAST_SYSTEM_UID',  999),
			('FIRST_SYSTEM_UID', 100),
			('LAST_SYSTEM_GID',  9999),
			('FIRST_SYSTEM_GID', 100),
			)

		for (directive, value) in defaults:
			if directive in adduser_dict.keys():
				if type(value) == type(1):
					if value > adduser_dict[directive]:
						logging.warning('''In %s, directive %s should be at '''
							'''least %s, but it is %s.'''
							% (stylize(ST_PATH, adduser_conf),
								directive, value, adduser_dict[directive]),
								listener=listener)
						adduser_dict[directive] = value
						adduser_conf_alter      = True
						adduser_data            = re.sub(r'%s=.*' % directive,
							r'%s=%s' % (directive, value), adduser_data)
				else:
					if value != adduser_dict[directive]:
						logging.warning('''In %s, directive %s should be set '''
							'''to %s, but it is %s.''' % (
								stylize(ST_PATH, adduser_conf),
								directive, value, adduser_dict[directive]),
								listener=listener)
						adduser_dict[directive] = value
						adduser_conf_alter      = True
						adduser_data            = re.sub(r'%s=.*' % directive,
							r'%s=%s' % (directive, value), adduser_data)

				# else: everything's OK !
			else:
				logging.warning(
					'''In %s, directive %s is missing. Setting it to %s.'''
					% (stylize(ST_PATH, adduser_conf),
						directive, value), listener=listener)
				adduser_dict[directive] = value
				adduser_conf_alter      = True
				adduser_data            = re.sub(r'(LAST_SYSTEM_UID.*)',
					r'\1\n%s=%s' % (directive, value), adduser_data)

		if adduser_conf_alter:
			if batch or logging.ask_for_repair(
				'''%s lacks mandatory configuration directive(s).'''
							% stylize(ST_PATH, adduser_conf),
								auto_answer, listener=listener):
				try:
					fsapi.backup_file(adduser_conf)
					open(adduser_conf, 'w').write(adduser_data)
					logging.notice('Tweaked %s to match Licorn® pre-requisites.'
						% stylize(ST_PATH, adduser_conf),
						listener=listener)
				except (IOError, OSError), e:
					if e.errno == 13:
						raise exceptions.LicornRuntimeError(
							'''Insufficient permissions. '''
							'''Are you root?\n\t%s''' % e)
					else: raise e
			else:
				raise exceptions.LicornRuntimeError('''Modifications in %s '''
					'''are mandatory for Licorn to work properly with other '''
					'''system tools (adduser/useradd). Can't continue '''
					'''without this, sorry!''' % adduser_conf)

		assert ltrace('configuration', '< CheckAndLoadAdduserConf(%s)' %
			adduser_dict)

		return adduser_dict
	def CheckLoginDefs(self, batch=False, auto_answer=None, listener=None):
		""" Check /etc/login.defs for compatibility with Licorn.
			Load data, alter it if needed and save the new file.
		"""

		assert ltrace('configuration', '| CheckLoginDefs(batch=%s)' % batch)

		self.check_system_file_generic(filename="/etc/login.defs",
			reader=readers.simple_conf_load_dict,
			defaults=(
				('UID_MIN', self.users.uid_min),
				('UID_MAX', self.users.uid_max),
				('GID_MIN', self.groups.gid_min),
				('GID_MAX', self.groups.gid_max),
				('SYS_GID_MAX', self.groups.system_gid_max),
				('SYS_GID_MIN', self.groups.system_gid_min),
				('SYS_UID_MAX', self.users.system_uid_max),
				('SYS_UID_MIN', self.users.system_uid_min),
				('USERGROUPS_ENAB', 'no'),
				('CREATE_HOME', 'yes')
			),
			separator='	',
			batch=batch, auto_answer=auto_answer, listener=listener)
	def CheckUserAdd(self, batch=False, auto_answer=None, listener=None):
		""" Check /etc/defaults/useradd if it exists, for compatibility with
			Licorn®.
		"""

		assert ltrace('configuration', '| CheckUserAdd(batch=%s)' % batch)

		self.check_system_file_generic(filename="/etc/default/useradd",
			reader=readers.shell_conf_load_dict,
			defaults=(
				('GROUP', self.users.default_gid),
				('HOME', self.users.base_path)
			),
			separator='=', check_exists=True,
			batch=batch, auto_answer=auto_answer, listener=listener)
	def check_system_file_generic(self, filename, reader, defaults, separator,
		check_exists=False, batch=False, auto_answer=None, listener=None):

		assert ltrace('configuration', '''> check_system_file_generic('''
			'''filename=%s, separator='%s', batch=%s)''' % (filename, separator,
			batch))

		if check_exists and not os.path.exists(filename):
			logging.warning2('''%s doesn't exist on this system.''' % filename,
				listener=listener)
			return

		alter_file = False
		file_data  = open(filename, 'r').read()
		data_dict  = reader(data=file_data)

		for (directive, value) in defaults:
			try:
				if data_dict[directive] != value:
					logging.warning('''In %s, directive %s should be %s,'''
						''' but it is %s.''' % (
							stylize(ST_PATH, filename),
							directive, value, data_dict[directive]),
							listener=listener)
					alter_file           = True
					data_dict[directive] = value
					file_data            = re.sub(r'%s.*' % directive,
						r'%s%s%s' % (directive, separator, value), file_data)
			except KeyError:
				logging.warning('''In %s, directive %s isn't present but '''
					'''should be, with value %s.''' % (
						stylize(ST_PATH, filename),
						directive, value),
						listener=listener)
				alter_file           = True
				data_dict[directive] = value
				file_data += '%s%s%s\n' % (directive, separator, value)

		if alter_file:
			if batch or logging.ask_for_repair(
				'''%s should be altered to be in sync with Licorn®. Fix it ?'''
				% stylize(ST_PATH, filename), auto_answer,
				listener=listener):
				try:
					fsapi.backup_file(filename)
					open(filename, 'w').write(file_data)
					logging.notice('Tweaked %s to match Licorn® pre-requisites.'
						% stylize(ST_PATH, filename),
						listener=listener)
				except (IOError, OSError), e:
					if e.errno == 13:
						raise exceptions.LicornRuntimeError(
							'''Insufficient permissions. '''
							'''Are you root?\n\t%s''' % e)
					else:
						raise e
			else:
				raise exceptions.LicornRuntimeError('''Modifications in %s '''
					'''are mandatory for Licorn to work properly. Can't '''
					'''continue without this, sorry!''' % filename)
		assert ltrace('configuration', '< check_system_file_generic()')
	### EXPORTS ###
	def Export(self, doreturn=True, args=None, cli_format='short'):
		""" Export «self» (the system configuration) to a human
			[stylized and] readable form.
			if «doreturn» is True, return a "string", else write output
			directly to stdout.
		"""

		if args is not None:
			data = ""

			if cli_format == "bourne":
				cli = {
					'prefix': "export ",
					'name': True,
					'equals': "=",
					'suffix': ""
					}
			elif  cli_format == "cshell":
				cli = {
					'prefix': "setenv ",
					'name': True,
					'equals': " ",
					'suffix': ""
					}
			elif  cli_format == "PHP":
				cli = {
					'prefix': "$",
					'name': True,
					'equals': "=",
					'suffix': ";"
					}
			elif  cli_format == "short":
				cli = {
					'prefix': "",
					'name': False,
					'equals': "=",
					'suffix': ""
					}
			else:
				raise exceptions.BadArgumentError(
					"Bad CLI output format « %s » !" % cli_format)

			if args[0] == "shells":
				for shell in self.users.shells:
					data += "%s\n" % shell

			elif args[0] == "skels":
				for skel in self.users.skels:
					data += "%s\n" % skel

			elif args[0] == 'backends':
				for b in LMC.backends:
					data += '%s(%s%s%s)\n' % (b.name,
						stylize(ST_INFO, 'U') \
						if b.name == LMC.users._prefered_backend_name else '',
						stylize(ST_INFO, 'G') \
						if b.name == LMC.groups._prefered_backend_name else '',
						stylize(ST_INFO, 'M') \
						if b.name == LMC.machines._prefered_backend_name else '',
						)
				for b in LMC.backends._available_backends:
					data += '%s\n' % b.name

			elif args[0] in ("config_dir", "main_config_file",
				"backup_config_file", "extendedgroup_data_file", "app_name"):

				varname = args[0].upper()

				if args[0] == "config_dir":
					varval = self.config_dir
				elif args[0] == "main_config_file":
					varval = self.main_config_file
				elif args[0] == "backup_config_file":
					varval = self.backup_config_file
				elif args[0] == "extendedgroup_data_file":
					varval = self.extendedgroup_data_file

				elif args[0] == "app_name":
					varval = self.app_name

				if cli["name"]:
					data +=	 "%s%s%s\"%s\"%s\n" % (
						cli["prefix"],
						varname,
						cli["equals"],
						varval,
						cli["suffix"]
						)
				else:
					data +=	 "%s\n" % (varval)
			elif args[0] in ('sysgroups', 'system_groups', 'system-groups'):

				for group in self.defaults.needed_groups:
					data += "%s\n" % stylize(ST_SECRET, group)

				data += "%s\n" % stylize(ST_SECRET,
					self.defaults.admin_group)

				for priv in LMC.privileges:
					data += "%s\n" % priv

			elif args[0] in ('priv', 'privs', 'privileges'):

				for priv in LMC.privileges:
					data += "%s\n" % priv

			else:
				raise NotImplementedError(
					"Sorry, outputing selectively %s is not yet implemented !" \
						% args[0])

		else:
			data = self._export_all()

		if doreturn is True:
			return data
		else:
			sys.stdout.write(data + "\n")
	def _export_all(self):
		"""Export all configuration data in a visual way."""

		data = "%s\n" % stylize(ST_APPNAME, "LicornConfiguration")

		items = self.items()
		items.sort()

		for aname, attr in items:

			if aname in ('tmp_dir'):
				continue

			#if callable(getattr(self, attr)) \
			#	or attr[0] in '_ABCDEFGHIJKLMNOPQRSTUVWXYZ' \
			#	or attr in ('name', 'tmp_dir', 'init_ok', 'del_ok',
			#		'objectGUID', 'lastUsed', 'delegate', 'daemon'):
			# skip methods, python internals, pyro internals and
			# too-much-moving targets which bork the testsuite.
			#	continue

			data += u"\u21b3 %s: " % stylize(ST_ATTR, aname)

			if aname is 'app_name':
				data += "%s\n" % stylize(ST_ATTRVALUE, attr)
			elif aname is 'mta':
				data += "%s\n" % stylize(ST_ATTRVALUE, servers[attr])
			elif aname is 'distro':
				data += "%s\n" % stylize(ST_ATTRVALUE, distros[attr])
				# cf http://www.reportlab.com/i18n/python_unicode_tutorial.html
				# and http://web.linuxfr.org/forums/29/9994.html#599760
				# and http://evanjones.ca/python-utf8.html
			elif aname.endswith('_dir') or aname.endswith('_file') \
				or aname.endswith('_path') :
				data += "%s\n" % stylize(ST_PATH, attr)
			elif type(attr) == type(LicornConfigObject()):
				data += "\n%s" % str(attr)
			elif type(attr) in (
				type([]), type(''), type(()), type({})):
				data += "\n\t%s\n" % str(attr)
			else:
				data += ('''%s, to be implemented in '''
					'''licorn.core.configuration.Export()\n''') % \
					stylize(ST_IMPORTANT, "UNREPRESENTABLE YET")

		return data
	def ExportXML(self):
		""" Export «self» (the system configuration) to XML. """
		raise NotImplementedError(
			'''LicornConfig::ExportXML() not yet implemented !''')
	def network_infos(self):
		self.network = LicornConfigObject()

		# reference the method, to be sure to return always the current
		# real interfaces of the machine.
		self.network.interfaces = network.interfaces
		self.network.local_ip_addresses = network.local_ip_addresses
	### MODIFY ###
	def ModifyHostname(self, new_hostname):
		"""Change the hostname of the running system."""

		if new_hostname == self.mCurrentHostname:
			return

		if not re.compile("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
			re.IGNORECASE).match(new_hostname):
			raise exceptions.BadArgumentError(
				'''new hostname must be composed only of letters, digits and '''
				'''hyphens, but not starting nor ending with an hyphen !''')

		logging.progress("Doing preliminary checks…")
		self.CheckHostname()

		try:
			etc_hostname = file("/etc/hostname", 'w')
			etc_hostname.write(new_hostname)
			etc_hostname.close()
		except (IOError, OSError), e:
			raise exceptions.LicornRuntimeError(
				'''can't modify /etc/hostname, verify the file is still '''
				'''clean:\n\t%s)''' % e)

	### CHECKS ###
	def check(self, minimal=True, batch=False, auto_answer=None, listener=None):
		""" Check all components of system configuration and repair
		if asked for."""

		assert ltrace('configuration', '> check()')

		self.check_base_dirs(minimal=minimal, batch=batch,
			auto_answer=auto_answer, listener=listener)

		self.check_OpenSSH(batch=batch, auto_answer=auto_answer)

		# not yet ready.
		#self.CheckHostname(minimal, auto_answer)
		assert ltrace('configuration', '< check()')
	def check_base_dirs(self, minimal=True, batch=False, auto_answer=None,
		listener=None):
		"""Check and eventually repair default needed dirs."""

		assert ltrace('configuration', '> check_base_dirs()')

		try:
			os.makedirs(self.users.base_path)
		except (OSError, IOError), e:
			if e.errno != 17:
				raise e

		self.CheckSystemGroups(minimal=minimal, batch=batch,
			auto_answer=auto_answer, listener=listener)

		p = self.acls

		dirs_to_verify = []
		dir_info = FsapiObject(name="groups_dir")
		dir_info.path = p.groups_dir
		dir_info.user = 'root'
		dir_info.group = 'acl'
		dir_info.root_dir_perm = "%s,%s,g:www-data:--x,g:users:%s,%s" % (
				p.acl_base, p.acl_admins_ro,
				p.acl_users, p.acl_mask)
		dir_info.root_dir_acl = True

		dirs_to_verify.append(dir_info)

		dir_info = FsapiObject(name="home_backup")
		dir_info.path = self.home_backup_dir
		dir_info.user = 'root'
		dir_info.group = 'acl'
		dir_info.root_dir_perm = "%s,%s,%s" % (p.acl_base,
				p.acl_admins_ro, p.acl_mask),
		dir_info.dirs_perm = "%s,%s,%s" % (p.acl_base,
				p.acl_admins_ro, p.acl_mask)
		if not minimal:
			# check the contents of these dirs, too (fixes #95)
			dir_info.files_perm = ("%s,%s,%s" % (
				p.acl_base, p.acl_admins_ro, p.acl_mask)
				).replace('r-x', 'r--').replace('rwx', 'rw-')
		dir_info.content_acl = True
		dir_info.root_dir_acl = True

		dirs_to_verify.append(dir_info)
		"""home_backup_dir_info = {
						'path'      : self.home_backup_dir,
						'user'      : 'root',
						'group'     : 'acl',
						'access_acl': "%s,%s,%s" % (p.acl_base,
							p.acl_admins_ro, p.acl_mask),
						'default_acl': "%s,%s,%s" % (p.acl_base,
							p.acl_admins_ro, p.acl_mask)
						}
						if not minimal:
						# check the contents of these dirs, too (fixes #95)
						home_backup_dir_info['content_acl'] = ("%s,%s,%s" % (
							p.acl_base, p.acl_admins_ro, p.acl_mask)
							).replace('r-x', 'r--').replace('rwx', 'rw-')
			"""


		"""	dirs_to_verify = [ {
			'path'      : p.groups_dir,
			'user'      : 'root',
			'group'     : 'acl',
			'access_acl': "%s,%s,g:www-data:--x,g:users:%s,%s" % (
				p.acl_base, p.acl_admins_ro,
				p.acl_users, p.acl_mask),
			'default_acl': ""
			} ]"""

		try:
			# batch this because it *has* to be corrected
			# for system to work properly.
			all_went_ok = True

			all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls_new(
				dirs_to_verify, batch=True,	listener=listener)

			all_went_ok &= self.check_archive_dir(batch=batch,
				auto_answer=auto_answer, listener=listener)

		except (IOError, OSError), e:
			if e.errno == 95:
				# this is the *first* "not supported" error encountered (on
				# config load of first licorn command). Try to make the error
				# message kind of explicit and clear, to let administrator know
				# he/she should mount the partition with 'acl' option.
				raise exceptions.LicornRuntimeError(
					'''Filesystem must be mounted with 'acl' option:\n\t%s''' \
						% e)
			else:
				logging.warning(e)
				raise e

		"""	home_backup_dir_info = {
			'path'      : self.home_backup_dir,
			'user'      : 'root',
			'group'     : 'acl',
			'access_acl': "%s,%s,%s" % (p.acl_base,
				p.acl_admins_ro, p.acl_mask),
			'default_acl': "%s,%s,%s" % (p.acl_base,
				p.acl_admins_ro, p.acl_mask)
			}

		if not minimal:
			# check the contents of these dirs, too (fixes #95)
			home_backup_dir_info['content_acl'] = ("%s,%s,%s" % (
				p.acl_base, p.acl_admins_ro, p.acl_mask)
				).replace('r-x', 'r--').replace('rwx', 'rw-')

		all_went_ok = True

		all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
			[ home_backup_dir_info ], batch=True,
			allgroups=LMC.groups, allusers=LMC.users,
			listener=listener)

		all_went_ok &= self.check_archive_dir(batch=batch,
			auto_answer=auto_answer, listener=listener)"""

		assert ltrace('configuration', '< check_base_dirs(%s)' % all_went_ok)
		return all_went_ok
	def check_archive_dir(self, subdir=None, minimal=True, batch=False,
		auto_answer=None, listener=None):
		""" Check only the archive dir, and eventually even only one of its
			subdir. """

		assert ltrace('configuration', '> check_archive_dir(%s)' % subdir)

		p = self.acls

		dirs_to_verify = []

		dir_info = FsapiObject(name="home_archive")
		dir_info.path = self.home_archive_dir
		dir_info.user = 'root'
		dir_info.group = 'acl'
		dir_info.root_dir_acl = True
		dir_info.content_acl = True
		dir_info.root_dir_perm = "%s,%s,%s" % (
			p.acl_base, p.acl_admins_rw, p.acl_mask)
		dir_info.dirs_perm = "%s,%s,%s" % (
			p.acl_base, p.acl_admins_rw, p.acl_mask)
		if not minimal:
			dir_info.files_perm = ("%s,%s,%s" % (
				p.acl_base, p.acl_admins_rw, p.acl_mask)
				).replace('r-x', 'r--').replace('rwx', 'rw-')

		dirs_to_verify.append(dir_info)
		"""home_archive_dir_info = {
			'path'       : self.home_archive_dir,
			'user'       : 'root',
			'group'      : 'acl',
			'access_acl' : "%s,%s,%s" % (
				p.acl_base, p.acl_admins_rw, p.acl_mask),
			'default_acl': "%s,%s,%s" % (
				p.acl_base, p.acl_admins_rw, p.acl_mask),
			}"""

		if subdir is not None:

			if os.path.dirname(subdir) == self.home_archive_dir:

				subdir_info = FsapiObject(name="home_archive_subdir")
				subdir_info.path = self.home_archive_dir
				subdir_info.user = 'root'
				subdir_info.group = 'acl'
				subdir_info.root_dir_acl = True
				subdir_info.content_acl = True
				subdir_info.root_dir_perm = "%s,%s,%s" % (
						p.acl_base, p.acl_admins_rw, p.acl_mask)
				subdir_info.dirs_perm = "%s,%s,%s" % (
						p.acl_base, p.acl_admins_rw, p.acl_mask)
				subdir_info.files_perm = ("%s,%s,%s" % (
					p.acl_base, p.acl_admins_rw, p.acl_mask)
					).replace('r-x', 'r--').replace('rwx', 'rw-')

				"""subdir_info = {
					'path'       : self.home_archive_dir,
					'user'       : 'root',
					'group'      : 'acl',
					'access_acl' : "%s,%s,%s" % (
						p.acl_base, p.acl_admins_rw, p.acl_mask),
					'default_acl': "%s,%s,%s" % (
						p.acl_base, p.acl_admins_rw, p.acl_mask),
					'content_acl': ("%s,%s,%s" % (
						p.acl_base, p.acl_admins_rw, p.acl_mask)
							).replace('r-x', 'r--').replace('rwx', 'rw-')
					}"""
			else:
				logging.warning(
					'the subdir you specified is not inside %s, skipped.' %
						stylize(ST_PATH, self.home_archive_dir),
						listener=listener)
				subdir=False

		"""elif not minimal:
			home_archive_dir_info['content_acl'] = ("%s,%s,%s" % (
				p.acl_base, p.acl_admins_rw, p.acl_mask)
				).replace('r-x', 'r--').replace('rwx', 'rw-')"""

		#dirs_to_verify = [ home_archive_dir_info ]

		if subdir is not None:
			dirs_to_verify.append(subdir_info)

		assert ltrace('configuration', ''''< check_archive_dir(return '''
			'''fsapi.check_dirs_and_contents_perms_and_acls(…))''')

		return fsapi.check_dirs_and_contents_perms_and_acls_new(dirs_to_verify,
			batch=batch, auto_answer=auto_answer, listener=listener)
	def CheckSystemGroups(self, minimal=True, batch=False, auto_answer=None,
		listener=None):
		"""Check if needed groups are present on the system, and repair
			if asked for."""

		assert ltrace('configuration',
			'> CheckSystemGroups(minimal=%s, batch=%s)' % (minimal, batch))

		needed_groups = [ self.users.group, self.acls.group,
			self.defaults.admin_group ]

		if not minimal:
			needed_groups.extend([ group for group in LMC.privileges
				if group not in needed_groups])
			# 'skels', 'remotessh', 'webmestres' [and so on] are not here
			# because they will be added by their respective packages
			# (plugins ?), and they are not strictly needed for Licorn to
			# operate properly.

		for group in needed_groups:
			logging.progress('Checking existence of group %s…' %
				stylize(ST_NAME, group))

			# licorn.core.groups is not loaded yet, and it would create a
			# circular dependancy to import it now. We HAVE to do this manually.
			if not LMC.groups.exists(name=group):
				if batch or logging.ask_for_repair(
					logging.CONFIG_SYSTEM_GROUP_REQUIRED % \
						stylize(ST_NAME, group), auto_answer,
						listener=listener):
					if group == self.users.group and self.distro in (
						distros.UBUNTU, distros.DEBIAN):

						# this is a special case: on deb.*, the "users" group
						# has a reserved gid of 100. Many programs rely on this.
						gid = 100
					else:
						gid = None

					LMC.groups.AddGroup(group, system=True,
						desired_gid=gid, listener=listener)
					del gid
				else:
					raise exceptions.LicornRuntimeError(
						'''The system group « %s » is mandatory but doesn't '''
						''' exist on your system !\nUse « licorn-check '''
						'''config --yes » or « licorn-add group --system '''
						'''--name "%s" » to solve the problem.''' % (
							group, group)
						)

		assert ltrace('configuration', '< CheckSystemGroups()')
	def CheckHostname(self, batch = False, auto_answer = None):
		""" Check hostname consistency (by DNS/reverse resolution),
			and check /etc/hosts against flakynesses."""

		import stat
		hosts_mode = os.stat("/etc/hosts").st_mode
		if not stat.S_IMODE(hosts_mode) & stat.S_IROTH:
			#
			# nsswitch will fail to resolve localhost/127.0.0.1 if
			# /etc/hosts don't have sufficient permissions.
			#
			raise exceptions.BadConfigurationError(
				'''/etc/hosts must have at least o+r permissions.''')


		line = open("/etc/hostname").readline()
		if line[:-1] != self.mCurrentHostname:
			raise exceptions.BadConfigurationError(
				'''current hostname and /etc/hostname are not in sync !''')

		import socket

		# DNS check for localhost.
		hostname_ip = socket.gethostbyname(self.mCurrentHostname)

		if hostname_ip != '127.0.0.1':
			raise exceptions.BadConfigurationError(
				'''hostname %s doesn't resolve to 127.0.0.1 but to %s, '''
				'''please check /etc/hosts !''' % (
					self.mCurrentHostname, hostname_ip) )

		# reverse DNS check for localhost. We use gethostbyaddr() to allow
		# the hostname to be in the aliases (this is often the case for
		# localhost in /etc/hosts).
		localhost_data = socket.gethostbyaddr('127.0.0.1')

		if not ( self.mCurrentHostname == localhost_data[0]
				or self.mCurrentHostname in localhost_data[1] ):
			raise exceptions.BadConfigurationError(
				'''127.0.0.1 doesn't resolve back to hostname %s, please '''
				'''check /etc/hosts and/or DNS !''' % self.mCurrentHostname)

		import licorn.tools.network as network

		dns = []
		for ns in network.nameservers():
			dns.append(ns)

		assert logging.debug2("configuration|DNS: " + str(dns))

		# reverse DNS check for eth0
		eth0_ip = network.iface_address('eth0')

		#
		# FIXME: the only simple way to garantee we are on an licorn server is
		# to check dpkg -l | grep licorn-server. We should check this to enforce
		# there is only 127.0.0.1 in /etc/resolv.conf if licorn-server is
		# installed.
		#

		#
		# FIXME2: when implementing previous FIXME, we should not but
		# administrator if /etc/licorn_is_installing is present (for example),
		# because during installation not everything is ready to go in
		# production and this is totally normal.
		#

		assert logging.debug2("configuration|eth0 IP: %s" % eth0_ip)

		try:
			eth0_hostname = socket.gethostbyaddr(eth0_ip)

			assert logging.debug2('configuration|eth0 hostname: %s' % eth0_hostname)

		except socket.herror, e:
			if e.args[0] == 1:
				#
				# e.args[0] == h_errno == 1 is «Unknown host»
				# the IP doesn't resolve, we could be on a standalone host (not
				# an Licorn server), we must verify.
				#
				if '127.0.0.1' in dns:
					raise exceptions.BadConfigurationError('''can't resolve '''
						'''%s (%s), is the dns server running on 127.0.0.1? '''
						'''Else check DNS files syntax !''' % (
							eth0_ip, e.args[1]))
				elif eth0_ip in dns:
					# FIXME put 127.0.0.1 automatically in configuration ?
					raise exceptions.BadConfigurationError(
						'''127.0.0.1 *must* be in /etc/resolv.conf on an '''
						'''Licorn server.''')
				#
				# if we reach here, this is the end of the function.
				#
		except Exception, e:
			raise exceptions.BadConfigurationError(
				'''Problem while resolving %s, please check '''
				'''configuration:\n\terrno %d, %s''' % (
					eth0_ip, e.args[0], e.args[1]))

		else:

			# hostname DNS check fro eth0. use [0] (the hostname primary record)
			# to enforce the full [reverse] DNS check is OK. This is needed for
			# modern SMTP servers, SSL web certificates to be validated, among
			# other things.
			eth0_reversed_ip = socket.gethostbyname(eth0_hostname[0])

			if eth0_reversed_ip != eth0_ip:
				if eth0_ip in dns:
					# FIXME put 127.0.0.1 automatically in configuration ?
					raise exceptions.BadConfigurationError(
						'''127.0.0.1 *must* be the only nameserver in '''
						'''/etc/resolv.conf on an Licorn server.''')
				elif '127.0.0.1' in dns:
					raise exceptions.BadConfigurationError(
						'''DNS seems not properly configured (%s doesn't '''
						'''resolve back to itself).''' % eth0_ip)
				else:
					logging.warning(
						'''DNS not properly configured (%s doesn't resolve '''
						'''to %, but to %s)''' % (
							eth0_hostname, eth0_ip, eth0_reversed_ip))

			# everything worked, but it is safer to have 127.0.0.1 as the
			# nameserver, inform administrator.
			if eth0_ip in dns or '127.0.0.1':
				# FIXME put 127.0.0.1 automatically in configuration ?
				logging.warning('''127.0.0.1 should be the only nameserver '''
					'''in /etc/resolv.conf on an Licorn server.''')

		# FIXME: vérifier que l'ip d'eth0 et son nom ne sont pas codés en dur
		# dans /etc/hosts, la série de tests sur eth0 aurait pu marcher grâce
		# à ça et donc rien ne dit que la conf DNS est OK…
	def CheckMailboxConfigIntegrity(self, batch=False, auto_answer=None):
		"""Verify "slaves" configuration files are OK, else repair them."""

		"""
			if mailbox:
				warning(unsupported)
			elif maildir:
				if courier-*:
					if batch or …:

					else:
						warning()
				else:
					raise unsupported.
			else:
				raise unsupported

		"""

		pass
	def SetHiddenGroups(self, hidden=True, listener=None):
		""" Set (un-)restrictive mode on the groups base directory. """

		self.groups.hidden = hidden
		self.check_base_dirs(batch=True, listener=listener)
