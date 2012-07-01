# -*- coding: utf-8 -*-
"""
Licorn core: configuration - http://docs.licorn.org/core/configuration.html

Unified Configuration API for an entire linux server system

:copyright:
	* 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	* partial 2010 Robin Lucbernet <robinlucbernet@gmail.com>
	* partial 2005 Régis Cobrun <reg53fr@yahoo.fr>

:license: GNU GPL version 2

"""

import sys, os, re, dmidecode, uuid, Pyro.core
from licorn.foundations.threads import RLock

from licorn.foundations           import logging, exceptions, settings
from licorn.foundations           import readers, fsapi, network, events, hlstr
from licorn.foundations.events    import LicornEvent
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.constants import distros, servers, mailboxes
from licorn.foundations.base      import LicornConfigObject, Singleton, \
											MixedDictObject, pyro_protected_attrs
from licorn.foundations.classes   import FileLock

from licorn.core                import LMC
from licorn.core.classes        import CoreModule

class LicornConfiguration(Singleton, MixedDictObject, Pyro.core.ObjBase):
	""" Contains all the underlying system configuration as attributes.
		Defines some methods for modifying the configuration.
	"""

	# bypass multiple init and del calls (we are a singleton)
	init_ok = False
	del_ok  = False

	_licorn_protected_attrs = MixedDictObject._licorn_protected_attrs + pyro_protected_attrs

	def __init__(self, minimal=False, batch=False):
		""" Gather underlying system configuration and load it for licorn.* """

		if LicornConfiguration.init_ok:
			return

		assert ltrace_func(TRACE_CONFIGURATION)

		Pyro.core.ObjBase.__init__(self)
		MixedDictObject.__init__(self, name='configuration')

		LicornEvent('configuration_initialises', configuration=self, synchronous=True).emit()

		self.app_name = 'Licorn®'

		# this lock is used only by inotifier for now.
		self.lock = RLock()

		self.mta = None

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

			self.SetUsersDefaults()
			self.SetGroupsDefaults()

			self.FindUserDir()

			LicornEvent('configuration_loads', configuration=self, synchronous=True).emit()

			if not minimal:
				self.load1(batch=batch)

			# must be done to find a way to find our network server.
			self.FindDistro()

			if not minimal:
				self.load2(batch=batch)

			self.import_settings()

			if not minimal:
				self.load3(batch=batch)

			LicornEvent('configuration_loaded', configuration=self, synchronous=True).emit()

		except exceptions.LicornException, e:
			raise exceptions.BadConfigurationError(_(u'Configuration '
										u'initialization failed: %s') % e)

		events.collect(self)

		LicornConfiguration.init_ok = True
		assert ltrace(TRACE_CONFIGURATION, '< __init__()')
	def import_settings(self):
		self.settings = settings
	def load(self, batch=False):
		""" just a compatibility method. """
		self.load1(batch=batch)
		self.load2(batch=batch)
		self.load3(batch=batch)
	def load1(self, batch=False):
		self.load_system_uuid()
		self.LoadManagersConfiguration(batch=batch)
		self.set_acl_defaults()
	def load2(self, batch=False):
		self.LoadShells()
		self.LoadSkels()
		self.detect_services()
		self.network_infos()
	def load3(self, batch=False):
		self.load_nsswitch()
	def _inotifier_install_watches(self, inotifier=None):
		""" settings watches are setup in foundations.settings. """
		pass
	def __configuration_file_changed(self, pathname):
		""" nothing yet. """
		pass
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
	def CleanUp(self):
		"""This is a sort of destructor. Clean-up before being deleted…"""

		if LicornConfiguration.del_ok:
			return

		assert ltrace(TRACE_CONFIGURATION, '> CleanUp(%s)' %
			LicornConfiguration.del_ok)

		try:
			import shutil
			# this is safe because tmp_dir was created with tempfile.mkdtemp()
			shutil.rmtree(self.tmp_dir)
		except (OSError, IOError), e:
			if e.errno == 2:
				logging.warning2(_(u'Temporary directory %s has vanished '
					u'during run, or already been wiped by another process.')
					% self.tmp_dir)
			else:
				raise e

		LicornConfiguration.del_ok = True
		assert ltrace(TRACE_CONFIGURATION, '< CleanUp()')
	def load_system_uuid(self):
		""" Get the hardware system UUID from `dmidecode`, or generate a random
			new one and store it for future uses. """

		not_found = True

		for root in dmidecode.system().itervalues():
			try:
				self.system_uuid = root['data']['UUID'].replace('-', '').lower()

			except:
				continue

			else:
				not_found = False
				break

		# Get warnings here, to avoid them beiing freely printed to console
		# everywhere, from every call, which is purely annoying. Eg:
		#
		# del group 10000
		# * [2012/01/07 11:57:09.8499] Le groupe ou GID "10000" inexistant ou invalide a été ignoré.
		#
		# ** COLLECTED WARNINGS **
		# /dev/mem: Permission denied
		# No SMBIOS nor DMI entry point found, sorry.
		# ** END OF WARNINGS **
		#
		# NOTE: there is a similar call in `foundations.bootstrap`
		logging.warning2(dmidecode.get_warnings())
		dmidecode.clear_warnings()

		if not_found:

			uuid_data_file = os.path.join(settings.data_dir, 'system_uuid.txt')

			if os.path.exists(uuid_data_file):
				# fallback to the previously generated UUID.

				self.system_uuid = open(uuid_data_file).read().strip()

			else:
				# If no previous already exists, create a new one and store it.

				self.system_uuid = uuid.uuid4().hex

				with open(uuid_data_file, 'w') as f:
					f.write('%s\n' % self.system_uuid)

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
				raise exceptions.LicornRuntimeError(_(u'Cannot create or '
					u'change owner of {0}[/data]:\n\t{1}').format(
						self.user_dir, e))
	def noop(self):
		""" No-op function, called when connecting pyro, to check if link
		is OK betwwen the server and the client. """
		assert ltrace(TRACE_CONFIGURATION, '| noop(True)')
		return True
	def load_nsswitch(self):
		""" Load the NS switch file. """

		self.nsswitch = (
			readers.simple_conf_load_dict_lists('/etc/nsswitch.conf'))
	def save_nsswitch(self):
		""" write the nsswitch.conf file. This method is meant to be called by
		a backend which has modified. """

		assert ltrace(TRACE_CONFIGURATION, '| save_nsswitch()')

		nss_data = ''

		for key in self.nsswitch:
			nss_data += '%s:%s%s\n' % (key,
			' ' * (15-len(key)),
			' '.join(self.nsswitch[key]))

		nss_lock = FileLock(self, '/etc/nsswitch.conf')
		nss_lock.Lock()
		open('/etc/nsswitch.conf', 'w').write(nss_data)
		nss_lock.Unlock()
	def FindDistro(self):
		""" Determine which Linux / BSD / else distro we run on. """

		self.distro = None

		if os.name is "posix":
			try:
				import lsb_release

			except ImportError:
				# OLD / non-lsb compatible system or BSD
				if os.path.exists('/etc/gentoo-release'):
					raise exceptions.LicornRuntimeError(
						"Gentoo is not yet supported, sorry !")
				elif  os.path.exists('/etc/SuSE-release') \
					or os.path.exists( '/etc/suse-release' ):
					raise exceptions.LicornRuntimeError(
						"SuSE are not yet supported, sorry !")
				elif  os.path.exists('/etc/redhat_release') \
					or os.path.exists('/etc/redhat-release'):
					raise exceptions.LicornRuntimeError(
						"RedHat/Mandriva is not yet supported, sorry !")
				else:
					raise exceptions.LicornRuntimeError(_(u'You are running an '
						u'unknown or unsupported non-LSB but POSIX Operating '
						u'System. Please get in '
						u'touch with {0} developpers, and consider submitting '
						u'a patch to make your system officially supported.'
						).format(stylize(ST_APPNAME, self.app_name)))

			distro_info          = lsb_release.get_distro_information()
			self.distro_id       = distro_info['ID']
			self.distro_codename = distro_info['CODENAME']

			if distro_info['ID'] in ('Licorn', 'Ubuntu'):
				self.distro = distros.UBUNTU

				codename = distro_info['CODENAME']

				if codename in ('lucid', 'maverick', 'natty', 'oneiric', ):
					# nothing special to do here.
					pass

				elif codename in ('precise', ):
					settings.experimental_should_be_enabled = True

				elif codename in ( 'hardy', 'intrepid', 'jaunty', 'karmik'):
					logging.warning(_(u'Your Ubuntu version "{0}" is '
						'no longer supported by {1} developpers nor Canonical. '
						'You should consider upgrading to a newer '
						'one.').format(
							stylize(ST_NAME, codename),
							stylize(ST_APPNAME, self.app_name)))

				elif codename in ('warty', 'hoary',
					'breezy', 'dapper', 'edgy', 'feisty', 'gutsy'):
					logging.warning(_(u'Greetings old-timer :-) Does {0} '
						u'still run on your aged Ubuntu version "{1}"? '
						u'Anyway it is no longer supported by {0} '
						u'developpers. Even Canonical nor Ubuntu community '
						u'does not support it anymore. You should very '
						u'strongly consider upgrading to a newer version.'
						).format(
							stylize(ST_APPNAME, self.app_name),
							stylize(ST_NAME, codename)))

				else:
					raise exceptions.LicornRuntimeError(_(u'This Ubuntu '
						u'version "{0}" is not [yet] supported, sorry !').format(
							stylize(ST_NAME, codename)))

			elif distro_info['ID'] in ('Debian', ):
				self.distro = distros.DEBIAN

				codename = distro_info['CODENAME']

				if codename in ('squeeze', ):
					# nothing special, just a supported distro.
					pass

				elif codename in ('wheezy', 'sid', ):
					settings.experimental_should_be_enabled = True

				elif codename in ('etch', 'lenny', ):
					logging.warning(_(u'Your Debian version ("{0}") is '
						u'no longer supported by {1} developpers nor Debian. '
						u'You should consider upgrading to a newer '
						u'one.').format(
							stylize(ST_NAME, codename),
							stylize(ST_APPNAME, self.app_name)))

				elif codename in ('buzz', 'rex', 'bo', 'hamm', 'slink',
									'potato', 'woody', 'sarge'):
					logging.warning(_(u'Greetings old-timer :-) Does {0} '
						u'still run on your aged Debian version "{1}"? '
						u'Anyway it is no longer supported by {0} '
						u'developpers. Even Debian community '
						u'does not support it anymore. You should very '
						u'strongly consider upgrading to a newer version.'
						).format(
							stylize(ST_APPNAME, self.app_name),
							stylize(ST_NAME, codename)))

				else:
					raise exceptions.LicornRuntimeError(_(u'This Debian '
						u'version "{0}" is not [yet] supported, sorry !').format(
							stylize(ST_NAME, codename)))

			else:
				raise exceptions.LicornRuntimeError(_(u'Your LSB distro '
					u'is not yet supported. This should be trivial to '
					u'implement, but this is still to be done, sorry!'))

			self.distro_version = distro_info['RELEASE']

		else:
			raise exceptions.LicornRuntimeError(
				"Not on a supported system ! Please send a patch ;-)")

		del lsb_release, distro_info
	def detect_services(self):
		""" Concentrates all calls for service detection on the current system
		"""
		self.FindMTA()
		self.FindMailboxType()
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
		logging.progress(_(u'MTA not installed or unsupported.'))
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
			logging.progress(_(u'Mail{box,dir} system not supported yet. '
				u'Please get in touch with dev@licorn.org.'))
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
			settings.defaults.home_base_path, "/usr/share/skels"):
			if os.path.exists(skel_path):
				try:
					for new_skel in fsapi.minifind(path=skel_path,
						itype=(stat.S_IFDIR,), mindepth=2, maxdepth=2):
						self.users.skels.append(new_skel)
				except OSError, e:
					logging.warning(_(u'Custom skels must have at least {0} '
						u'perms on dirs and {1} on files:\n\t{2}').format(
							stylize(ST_MODE, u'u+rwx,g+rx,o+rx'),
							stylize(ST_MODE, u'u+rw,g+r,o+r'), e))

	### Users and Groups ###
	def LoadManagersConfiguration(self, batch=False, auto_answer=None):
		""" Load Users and Groups managements configuration. """

		assert ltrace(TRACE_CONFIGURATION, '> LoadManagersConfiguration(batch=%s)' %
			batch)

		# The "hidden groups" feature (chmod 710 on /home/groups) defaults to
		# False, because it is just annoying in real life. Administrator must
		# have a good reason to hide groups from users.
		self.groups.hidden_default = False

		# "None" means "unknown value", and will be filled when GroupsController
		# load()s. If the current state cannot be determined, the value
		# "hidden_default" will be used instead; this allows the admin to
		# overide the default in the configuration file (the 'real' status is
		# always modified 'live' on the FS, and not stored anywhere else).
		self.groups.hidden = None

		add_user_conf = self.CheckAndLoadAdduserConf(batch=batch,
											auto_answer=auto_answer)
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
		self.CheckLoginDefs(batch=batch, auto_answer=auto_answer)
		self.CheckUserAdd(batch=batch, auto_answer=auto_answer)

		assert ltrace(TRACE_CONFIGURATION, '< LoadManagersConfiguration()')
	def SetUsersDefaults(self):
		"""Create self.users attributes and start feeding it."""

		self.users = LicornConfigObject()

		# config dir
		self.users.config_dir = '.licorn'
		self.users.check_config_file = self.users.config_dir + '/check.conf'

		self.users.group = 'users'

		# see groupadd(8), coming from addgroup(8)
		self.users.login_maxlenght = 31

		# FIXME: still needed now that all threads are i18n capable?
		self.users._singular = _('user')
		self.users._plural = _('users')

		# FIXME: don't hardcode these (this will come from the apache extension)
		self.users.apache_dir = 'public_html'
	def SetGroupsDefaults(self):
		"""Create self.groups attributes and start feeding it."""

		self.groups = LicornConfigObject()
		self.groups.base_path  = settings.defaults.home_base_path + '/groups'

		self.groups.check_config_file_suffix = '.check.conf'

		self.groups.guest_prefix = 'gst-'
		self.groups.resp_prefix = 'rsp-'

		# maxlenght comes from groupadd(8), itself coming from addgroup(8)
		# 31 - len(prefix)
		self.groups.name_maxlenght = 27

		# FIXME: still needed now that all threads are i18n capable?
		self.groups._singular = _('group')
		self.groups._plural   = _('groups')

		# FIXME: should come from the apache extension too.
		self.groups.apache_dir = self.users.apache_dir
	def set_acl_defaults(self):
		""" Prepare the basic ACL configuration inside us. """

		assert ltrace(TRACE_CONFIGURATION, '| set_acl_defaults()')

		self.acls = LicornConfigObject()
		self.acls.group = 'acl'

		# this one will be filled later, when GroupsController is instanciated.
		self.acls.gid = 0

		self.acls.acl_base      = 'u::rwx,g::---,o:---'
		self.acls.acl_mask      = 'm:rwx'
		self.acls.acl_admins_ro = 'g:%s:r-x' % settings.defaults.admin_group
		self.acls.acl_admins_rw = 'g:%s:rwx' % settings.defaults.admin_group
		self.acls.acl_users     = '--x' if self.groups.hidden else 'r-x'
		self.acls.file_acl_base = 'u::rw@UX,g::---,o:---'
		self.acls.acl_restrictive_mask = 'm:r-x'
		self.acls.file_acl_mask = 'm:rw@GX'
		self.acls.file_acl_restrictive_mask = 'm:rw@GX'
		self.acls.group_acl_base = ('u::rwx,g::---,o:---,g:%s:rwx,'
							'g:%s@GROUP:r-x,g:%s@GROUP:rwx,g:@GROUP:rwx') % (
								settings.defaults.admin_group,
								self.groups.guest_prefix,
								self.groups.resp_prefix)
		self.acls.group_file_acl_base = ('u::rw@UX,g::---,o:---,g:%s:rw@GX,'
							'g:%s@GROUP:r-@GX,g:%s@GROUP:rw@GX,g:@GROUP:r@GW@GX')%(
								settings.defaults.admin_group,
								self.groups.guest_prefix,
								self.groups.resp_prefix)
	def CheckAndLoadAdduserConf(self, batch=False, auto_answer=None):
		""" Check the contents of adduser.conf to be compatible with Licorn.
			Alter it, if not.
			Then load it in a way i can be used in LicornConfiguration.
		"""

		assert ltrace_func(TRACE_CONFIGURATION)

		adduser_conf       = '/etc/adduser.conf'
		adduser_conf_alter = False
		adduser_data       = open(adduser_conf, 'r').read()
		adduser_dict       = readers.shell_conf_load_dict(data=adduser_data)

		# warning: the order is important: in a default adduser.conf,
		# only {FIRST,LAST}_SYSTEM_UID are
		# present, and we assume this during the file patch.
		defaults = (
			('DHOME', '%s/users' % \
				settings.defaults.home_base_path),
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
						logging.warning(_(u'In {0}, directive {1} should be '
							u'at least {2}, but it is {3}.').format(
								stylize(ST_PATH, adduser_conf),
								directive, value, adduser_dict[directive]))
						adduser_dict[directive] = value
						adduser_conf_alter      = True
						adduser_data            = re.sub(r'%s=.*' % directive,
							r'%s=%s' % (directive, value), adduser_data)
				else:
					if value != adduser_dict[directive]:
						logging.warning(_(u'In {0}, directive {1} should be '
							u'set to {2}, but it is {3}.').format(
								stylize(ST_PATH, adduser_conf),
								directive, value, adduser_dict[directive]))
						adduser_dict[directive] = value
						adduser_conf_alter      = True
						adduser_data            = re.sub(r'%s=.*' % directive,
							r'%s=%s' % (directive, value), adduser_data)

				# else: everything's OK !
			else:
				logging.warning(_(u'In {0}, directive {1} is missing. Setting it to {2}.').format(
						stylize(ST_PATH, adduser_conf),	directive, value))

				adduser_dict[directive] = value
				adduser_conf_alter      = True
				adduser_data            = re.sub(r'(LAST_SYSTEM_UID.*)',
												r'\1\n%s=%s' % (directive, value),
												adduser_data)

		if adduser_conf_alter:
			if batch or logging.ask_for_repair(_(u'{0} lacks mandatory '
									u'configuration directive(s).').format(
										stylize(ST_PATH, adduser_conf)),
								auto_answer):
				try:
					fsapi.backup_file(adduser_conf)
					open(adduser_conf, 'w').write(adduser_data)

					logging.notice(_(u'Altered {0} to match Licorn® '
						u'pre-requisites.').format(stylize(ST_PATH, adduser_conf)))

				except (IOError, OSError), e:
					if e.errno == 13:
						raise exceptions.LicornRuntimeError(_(u'Insufficient '
							u'permissions. Are you root?\n\t%s') % e)
					else: raise e
			else:
				raise exceptions.LicornRuntimeError(_(u'Modifications in %s '
					u'are mandatory for Licorn® to work properly with other '
					u'system tools (adduser/useradd). Cannot continue '
					u'without this, sorry!') % adduser_conf)

		assert ltrace_func(TRACE_CONFIGURATION, 1)

		return adduser_dict
	def CheckLoginDefs(self, batch=False, auto_answer=None):
		""" Check /etc/login.defs for compatibility with Licorn.
			Load data, alter it if needed and save the new file.
		"""

		assert ltrace_func(TRACE_CONFIGURATION)

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
			batch=batch, auto_answer=auto_answer)
	def CheckUserAdd(self, batch=False, auto_answer=None):
		""" Check /etc/defaults/useradd if it exists, for compatibility with
			Licorn®.
		"""

		assert ltrace_func(TRACE_CONFIGURATION)

		self.check_system_file_generic(filename="/etc/default/useradd",
			reader=readers.shell_conf_load_dict,
			defaults=(
				('GROUP', self.users.default_gid),
				('HOME', self.users.base_path)
			),
			separator='=', check_exists=True,
			batch=batch, auto_answer=auto_answer)
	def check_system_file_generic(self, filename, reader, defaults, separator,
		check_exists=False, batch=False, auto_answer=None):

		assert ltrace_func(TRACE_CONFIGURATION)

		if check_exists and not os.path.exists(filename):
			logging.warning(_(u'%s does not exist on this system!') % filename)
			return

		alter_file = False
		file_data  = open(filename, 'r').read()
		data_dict  = reader(data=file_data)

		for (directive, value) in defaults:
			try:
				if data_dict[directive] != value:
					logging.warning(_(u'In {0}, directive {1} should be {2}, '
										u'but it is {3}.').format(
											stylize(ST_PATH, filename),
											directive, value,
											data_dict[directive]))
					alter_file           = True
					data_dict[directive] = value
					file_data            = re.sub(r'%s.*' % directive,
												r'%s%s%s' % (directive, separator, value),
												file_data)
			except KeyError:
				logging.warning(_(u'In {0}, directive {1} is not present but '
									u'should be, with value {2}.').format(
										stylize(ST_PATH, filename),
										directive, value))
				alter_file           = True
				data_dict[directive] = value
				file_data += '%s%s%s\n' % (directive, separator, value)

		if alter_file:
			if batch or logging.ask_for_repair(_(u'{0} should be altered to work '
												u'with Licorn®. Fix it?').format(
													stylize(ST_PATH, filename)),
							auto_answer):
				try:
					fsapi.backup_file(filename)
					open(filename, 'w').write(file_data)

					logging.notice(_(u'Altered {0} to match Licorn® '
							u'pre-requisites.').format(
								stylize(ST_PATH, filename)))

				except (IOError, OSError), e:
					if e.errno == 13:
						raise exceptions.LicornRuntimeError(_(u'Insufficient '
							u'permissions. Are you root?\n\t%s') % e)
					else:
						raise e
			else:
				raise exceptions.LicornRuntimeError(_(u'Modifications in %s '
					u'are mandatory for Licorn® to work properly. Cannot '
					u'continue without this, sorry!') % filename)

		assert ltrace_func(TRACE_CONFIGURATION, 1)
	### EXPORTS ###
	def Export(self, doreturn=True, args=None, cli_format='short'):
		""" Export «self» (the system configuration) to a human
			[stylized and] readable form.
			if «doreturn» is True, return a "string", else write output
			directly to stdout.
		"""

		if args:
			data = u''

			if cli_format in ('bourne', 'bash'):
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
				raise exceptions.BadArgumentError(_(u'Bad CLI output '
											u'format "%s"!') % cli_format)

			words = {
				'app_name'                : _(u'Application name'),
				'backends'                : _(u'Storage backends for Core objects'),
				'config_dir'              : _(u'Application main configuration directory'),
				'extendedgroup_data_file' : _(u'Filename of extended group data'),
				'extensions'              : _(u'Application extensions (available add-ons)'),
				'help'                    : _(u'This current help'),
				'main_config_file'        : _(u'Application main configuration filename'),
				'privileges'              : _(u'System groups tagged as privileges'),
				'shells'                  : _(u'System valid shells when creating a new user'),
				'skels'                   : _(u'System valid skels to apply on a user account'),
				'system-groups'           : _(u'Mandatory system groups for {0}').format(stylize(ST_APPNAME, self.app_name)),
				 }

			word = hlstr.word_match(args[0], words.keys())

			if word is None:
				raise exceptions.BadArgument(_(u'Sorry, "%s" is not a '
											u'recognized keyword.') % args[0])

			if word == 'help':
				data += u'%s\n%s\n' % (
								_(u'Valid keywords for {0} (fuzzy '
									u'matching):').format(
										stylize(ST_COMMENT,
											u'get config <keyword>')),
								u'\n'.join(_(u'{0}: {1}').format(
									stylize(ST_NAME, k.rjust(max(len(x) for x in words))), v)
										for k,v in words.iteritems()))

			elif word == 'shells':
				for shell in self.users.shells:
					data += u'%s\n' % shell

			elif word == 'skels':
				for skel in self.users.skels:
					data += u'%s\n' % skel

			elif word == 'backends':

				for b in LMC.backends:
					data += u'%s(%s%s%s%s)\n' % (
						str(b),
						stylize(ST_INFO, u'U')
							if LMC.users._prefered_backend != None
								and b.name == LMC.users._prefered_backend.name
							else u'',
						stylize(ST_INFO, u'G')
							if LMC.groups._prefered_backend != None
								and b.name == LMC.groups._prefered_backend.name
							else u'',
						stylize(ST_INFO, u'M')
							if LMC.machines._prefered_backend != None
								and b.name == LMC.machines._prefered_backend.name
							else u'',
						(stylize(ST_INFO, u'T')
							if LMC.tasks._prefered_backend != None
								and b.name == LMC.tasks._prefered_backend.name
							else u'') if hasattr(LMC, 'tasks') else u'',
						)

			elif word == 'extensions':
				data += u'\n'.join(str(e) for e in LMC.extensions) + u'\n'

			# TODO: update this code for 'settings' use...
			elif word in ('config_dir', 'main_config_file',
						'extendedgroup_data_file', 'app_name'):

				varname = word.upper()

				if word == 'config_dir':
					varval = self.config_dir

				elif word == 'main_config_file':
					varval = self.main_config_file

				elif word == 'extendedgroup_data_file':
					varval = self.extendedgroup_data_file

				elif word == 'app_name':
					varval = self.app_name

				if cli['name']:
					data +=	 '%s%s%s"%s"%s\n' % (
						cli['prefix'],
						varname,
						cli['equals'],
						varval,
						cli['suffix']
						)
				else:
					data +=	 '%s\n' % (varval)

			elif word == 'system-groups':

				data += u'%s\n' % u'\n'.join((self.acls.group,
											settings.defaults.admin_group))

				if LMC.privileges.keys():
					data += u'%s\n' % u'\n'.join(x.name for x in LMC.privileges)

			elif word == 'privileges':
				data += u'%s\n' % u'\n'.join(x.name for x in LMC.privileges)

		else:
			data = self._export_all()

		if doreturn is True:
			return data

		else:
			sys.stdout.write(data + "\n")
	def _export_all(self):
		"""Export all configuration data in a visual way."""

		data = "%s\n" % stylize(ST_APPNAME, "LicornConfiguration")

		items = self.items() + [
					(backend.name, backend)
					for backend in LMC.backends
				] + [
					(extension.name, extension)
					for extension in LMC.extensions
				]
		items.sort()

		for aname, attr in items:
			if aname in ('tmp_dir', 'lock'):
				continue

			#if callable(getattr(self, attr)) \
			#	or attr[0] in '_ABCDEFGHIJKLMNOPQRSTUVWXYZ' \
			#	or attr in ('name', 'tmp_dir', 'init_ok', 'del_ok',
			#		'objectGUID', 'lastUsed', 'delegate', 'daemon'):
			# skip methods, python internals, pyro internals and
			# too-much-moving targets which bork the testsuite.
			#	continue

			if isinstance(attr, CoreModule):
				data += getattr(attr, '_cli_get_configuration')()
				continue

			data += u"\u21b3 %s: " % stylize(ST_ATTR, aname)

			if aname in ('app_name', 'distro_version'):
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
			elif issubclass(attr.__class__, CoreModule):
				data += "\n%s" % str(attr)
			else:
				data += ('%s, to be implemented in '
					'licorn.core.configuration.Export()\n') % \
					stylize(ST_IMPORTANT, "UNREPRESENTABLE YET")

		return data
	def ExportXML(self):
		""" Export «self» (the system configuration) to XML. """
		raise NotImplementedError(u'LicornConfig::ExportXML() not yet implemented !')
	def network_infos(self):
		self.network = LicornConfigObject()

		# reference the method, to be sure to return always the current
		# real interfaces of the machine.
		self.network.interfaces = network.interfaces
		self.network.local_ip_addresses = network.local_ip_addresses
		self.network.hostname = network.get_local_hostname
	### MODIFY ###
	def ModifyHostname(self, new_hostname):
		"""Change the hostname of the running system."""

		if new_hostname == self.mCurrentHostname:
			return

		if not re.compile("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
			re.IGNORECASE).match(new_hostname):
			raise exceptions.BadArgumentError(_(u'New hostname must be '
				u'composed only of letters, digits and hyphens, but not '
				u'starting nor ending with an hyphen !'))

		logging.progress("Doing preliminary checks…")
		self.CheckHostname()

		try:
			etc_hostname = file("/etc/hostname", 'w')
			etc_hostname.write(new_hostname)
			etc_hostname.close()
		except (IOError, OSError), e:
			raise exceptions.LicornRuntimeError(_(u'Cannot modify '
				u'/etc/hostname, verify the file is still clean:\n\t%s)') % e)

	### CHECKS ###
	def check(self, minimal=True, batch=False, auto_answer=None):
		""" Check all components of system configuration and repair
		if asked for.

		.. note:: for developers: the contents of this method need to stay
				in sync with :meth:`groups_loaded`, they basically do the
				same things.
		"""

		assert ltrace(TRACE_CONFIGURATION, '> check()')

		self.check_system_groups(minimal=minimal, batch=batch,
								auto_answer=auto_answer)

		self.check_base_dirs(minimal=minimal, batch=batch,
								auto_answer=auto_answer)

		# not yet ready.
		#self.CheckHostname(minimal, auto_answer)
		assert ltrace(TRACE_CONFIGURATION, '< check()')
	def check_base_dirs(self, minimal=True, batch=False, auto_answer=None):
		"""Check and eventually repair default needed dirs."""

		assert ltrace_func(TRACE_CONFIGURATION)

		try:
			os.makedirs(self.users.base_path)

		except (OSError, IOError), e:
			if e.errno != 17:
				raise e

		acls_conf = self.acls

		dirs_to_verify = []

		dirs_to_verify.append(
			fsapi.FsapiObject(name='home',
						path=settings.defaults.home_base_path,
						uid=0, gid=0,
						root_dir_perm=00755))

		dirs_to_verify.append(
			fsapi.FsapiObject(name='home_users',
						path=self.users.base_path,
						uid=0, gid=acls_conf.gid,
						root_dir_acl=True,
						root_dir_perm = '%s,%s,g:www-data:--x,g:users:%s,%s' % (
							acls_conf.acl_base,
							acls_conf.acl_admins_ro,
							acls_conf.acl_users,
							acls_conf.acl_mask)))

		dirs_to_verify.append(
			fsapi.FsapiObject(name='home_groups',
						path=self.groups.base_path,
						uid=0, gid=acls_conf.gid,
						root_dir_acl=True,
						root_dir_perm = '%s,%s,g:www-data:--x,g:users:%s,%s' % (
							acls_conf.acl_base,
							acls_conf.acl_admins_ro,
							acls_conf.acl_users,
							acls_conf.acl_mask)))

		dirs_to_verify.append(
			fsapi.FsapiObject(name='home_backups',
						path=settings.home_backup_dir,
						uid=0, gid=acls_conf.gid,
						root_dir_acl=True,
						root_dir_perm='%s,%s,%s' % (
							acls_conf.acl_base,
							acls_conf.acl_admins_ro,
							acls_conf.acl_mask),
						content_acl=True,
						dirs_perm='%s,%s,%s' % (
							acls_conf.acl_base,
							acls_conf.acl_admins_ro,
							acls_conf.acl_mask),
						files_perm=None
							if minimal
							else ('%s,%s,%s' % (
									acls_conf.acl_base,
									acls_conf.acl_admins_ro,
									acls_conf.acl_mask)
										).replace('r-x', 'r--'
										).replace('rwx', 'rw-')))

		try:
			for uyp in fsapi.check_dirs_and_contents_perms_and_acls_new(
						dirs_to_verify, batch=batch, auto_answer=auto_answer):
				pass
		except (IOError, OSError), e:
			if e.errno == 95:
				# this is the *first* "not supported" error encountered (on
				# config load of first licorn command). Try to make the error
				# message kind of explicit and clear, to let administrator know
				# he/she should mount the partition with 'acl' option.
				raise exceptions.LicornRuntimeError(_(u'Filesystem must be '
					u'mounted with "acl" option:\n\t%s') % e)
			else:
				raise
		except TypeError:
			# nothing to check (fsapi.... returned None and yielded nothing).
			pass

		self.check_archive_dir(batch=batch,	auto_answer=auto_answer)

		assert ltrace(TRACE_CONFIGURATION, '< check_base_dirs()')
	def check_archive_dir(self, subdir=None, minimal=True, batch=False,
		auto_answer=None, full_display=True):
		""" Check only the archive dir, and eventually even only one of its
			subdir. """

		assert ltrace(TRACE_CONFIGURATION, '> check_archive_dir(%s)' % subdir)

		acls_conf = self.acls

		home_archive = fsapi.FsapiObject(name='home_archive')
		home_archive.path = settings.home_archive_dir
		# FIXME: don't hardcode 'acl' here.
		home_archive.group = LMC.groups.by_name('acl').gidNumber
		home_archive.user = 0
		home_archive.root_dir_acl = True
		home_archive.root_dir_perm = "%s,%s,%s" % (
			acls_conf.acl_base, acls_conf.acl_admins_rw, acls_conf.acl_mask)

		if subdir:
			if os.path.dirname(subdir) == settings.home_archive_dir:
				home_archive.content_acl = True
				home_archive.dirs_perm = "%s,%s,%s" % (
					acls_conf.acl_base, acls_conf.acl_admins_rw,
					acls_conf.acl_mask)
				home_archive.files_perm = ("%s,%s,%s" % (
					acls_conf.acl_base, acls_conf.acl_admins_rw,
					acls_conf.acl_mask)
						).replace('r-x', 'r--').replace('rwx', 'rw-')
			else:
				logging.warning(
					'the subdir you specified is not inside %s, skipped.' %
						styles.stylize(styles.ST_PATH, settings.home_archive_dir))
				subdir=False

		try:
			for ignored_event in fsapi.check_dirs_and_contents_perms_and_acls_new(
							[home_archive], batch=batch, auto_answer=auto_answer,
							full_display=full_display):
				pass
		except TypeError:
			# nothing to check (fsapi.... returned None and yielded nothing).
			pass
	def check_system_groups(self, minimal=True, batch=False, auto_answer=None):
		"""Check if needed groups are present on the system, and repair
			if asked for."""

		assert ltrace_func(TRACE_CONFIGURATION)

		needed_groups = [ self.users.group, self.acls.group,
							settings.defaults.admin_group ]

		if not minimal:
			needed_groups.extend([ group for group in LMC.privileges.iterkeys()
				if group not in needed_groups
					and group not in LMC.groups.names])
			# 'skels', 'webmestres' [and so on] are not here
			# because they will be added by their respective packages
			# (plugins ?), and they are not strictly needed for Licorn to
			# operate properly.

		for group in needed_groups:
			logging.progress(_(u'Checking existence of group %s…') %
									stylize(ST_NAME, group))

			# licorn.core.groups is not loaded yet, and it would create a
			# circular dependancy to import it now. We HAVE to do this manually.
			if not LMC.groups.exists(name=group):
				if batch or logging.ask_for_repair(_(u'The system group %s is '
					'mandatory for the system to work properly, but it does '
					'not exist yet.') % stylize(ST_NAME, group), auto_answer):
					if group == self.users.group and self.distro in (
						distros.UBUNTU, distros.DEBIAN):

						# this is a special case: on deb.*, the "users" group
						# has a reserved gid of 100. Many programs rely on this.
						gid = 100
					else:
						gid = None

					LMC.groups.add_Group(name=group, system=True,
															desired_gid=gid)
					del gid
				else:
					raise exceptions.LicornRuntimeError(_(u'The system group '
						u'"{0}" is mandatory but does not exist on your '
						u'system !\nUse "chk config" or "add group --system '
						u'--name {0}" to fix the problem before '
						u'continuing.').format(group))

		assert ltrace_func(TRACE_CONFIGURATION, 1)
	@events.handler_method
	def groups_loaded(self, *args, **kwargs):
		""" `core.configuration` needs to do some basic chech when groups are loaded.

			.. note:: for developers: the contents of this event handler need to stay
				in sync with :meth:`check`, they basically do the same things.
		"""

		groups = kwargs.pop('groups')

		self.check_system_groups(batch=True)

		self.groups.hidden = groups.get_hidden_state()

		# cache this here for faster access in check methods
		self.acls.gid = groups.by_name(self.acls.group).gidNumber

		self.check_base_dirs(batch=True)
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
			raise exceptions.BadConfigurationError(_(u'/etc/hosts must have '
				u'at least o+r permissions.'))

		line = open("/etc/hostname").readline()

		if line[:-1] != self.mCurrentHostname:
			raise exceptions.BadConfigurationError(_(u'Current hostname '
				u'and /etc/hostname are not in sync!'))

		import socket

		# DNS check for localhost.
		hostname_ip = socket.gethostbyname(self.mCurrentHostname)

		if hostname_ip != '127.0.0.1':
			raise exceptions.BadConfigurationError(_(u'Hostname {0} does not '
				u'resolve to 127.0.0.1 but to {1}, please check '
				u'/etc/hosts!').format(self.mCurrentHostname, hostname_ip))

		# reverse DNS check for localhost. We use gethostbyaddr() to allow
		# the hostname to be in the aliases (this is often the case for
		# localhost in /etc/hosts).
		localhost_data = socket.gethostbyaddr('127.0.0.1')

		if not ( self.mCurrentHostname == localhost_data[0]
				or self.mCurrentHostname in localhost_data[1] ):
			raise exceptions.BadConfigurationError(_(u'127.0.0.1 does not '
				u'resolve back to hostname %s, please check /etc/hosts '
				u'and/or DNS !') % self.mCurrentHostname)

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
					raise exceptions.BadConfigurationError(_(u'Cannot resolve '
						u'{0} ({1}), is the DNS server running on 127.0.0.1? '
						u'Else check DNS files syntax !').format(eth0_ip,
							e.args[1]))

				elif eth0_ip in dns:
					# FIXME put 127.0.0.1 automatically in configuration ?
					raise exceptions.BadConfigurationError(_(u'127.0.0.1 '
						u'*must* be in /etc/resolv.conf on a Licorn® server.'))
				#
				# if we reach here, this is the end of the function.
				#
		except Exception, e:
			raise exceptions.BadConfigurationError(_(u'Problem while '
				u'resolving {0}, please check your configuration:\n\terrno '
				u'{1}, {2}').format(eth0_ip, e.args[0], e.args[1]))

		else:

			# hostname DNS check fro eth0. use [0] (the hostname primary record)
			# to enforce the full [reverse] DNS check is OK. This is needed for
			# modern SMTP servers, SSL web certificates to be validated, among
			# other things.
			eth0_reversed_ip = socket.gethostbyname(eth0_hostname[0])

			if eth0_reversed_ip != eth0_ip:
				if eth0_ip in dns:
					# FIXME put 127.0.0.1 automatically in configuration ?
					raise exceptions.BadConfigurationError(_(u'127.0.0.1 '
						u'*must* be the only nameserver in /etc/resolv.conf '
						u'on a Licorn® server.'))

				elif '127.0.0.1' in dns:
					raise exceptions.BadConfigurationError(_(u'DNS does not '
						u'seem properly configured (%s does not resolve '
						u'back to itself).') % eth0_ip)

				else:
					logging.warning(_(u'DNS is not properly configured ({0} '
						u'does not resolve to {1}, but to {2}).').format(
							eth0_hostname, eth0_ip, eth0_reversed_ip))

			# everything worked, but it is safer to have 127.0.0.1 as the
			# nameserver, inform administrator.
			if eth0_ip in dns or '127.0.0.1':
				# FIXME put 127.0.0.1 automatically in configuration ?
				logging.warning(_(u'127.0.0.1 should be the only nameserver '
					u'in /etc/resolv.conf on a Licorn® server.'))

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
	def SetHiddenGroups(self, hidden=True):
		""" Set (un-)restrictive mode on the groups base directory. """

		self.groups.hidden = hidden
		self.check_base_dirs(batch=True)
