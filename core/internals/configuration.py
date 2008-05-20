# -*- coding: utf-8 -*-
"""
Licorn core - http://dev.licorn.org/documentation/core

configuration - Unified Configuration API for an entire linux server system

Copyright (C) 2005-2008 Olivier Cortès <oc@5sys.fr>,
Partial Copyright (C) 2005 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""
import sys, os

from   licorn.foundations import logging, exceptions, fsapi, styles
from   privileges         import PrivilegesWhiteList
import readers

class LicornConfigObject : 
	""" a base class just to be able to add/remove custom attributes
		to other custom attributes (build a tree simply).
	"""
	def __str__(self) :
		def strattr (myattr) :
			return "%s = %s" % (str(myattr), str(getattr(self, myattr)))
		return "\n\t\t".join([ strattr(i) for i in self.__dict__ ] )

class LicornConfiguration (object) :
	""" Contains all the underlying system configuration as attributes.
		Defines some methods for modifying the configuration.
		This class is a singleton.
	"""
	__singleton = None
	mta         = None
	users       = None
	groups      = None

	# constants
	# TODO: move these constants into plugins
	DISTRO_UBUNTU   = 1
	DISTRO_LICORN   = DISTRO_UBUNTU
	DISTRO_DEBIAN   = 2
	DISTRO_GENTOO   = 3
	DISTRO_NOVELL   = 4
	DISTRO_REDHAT   = 5
	DISTRO_MANDRIVA = 6

	MAIL_TYPE_VAR_MBOX     = 1
	MAIL_TYPE_VAR_MAILDIR  = 2
	MAIL_TYPE_HOME_MBOX    = 3
	MAIL_TYPE_HOME_MAILDIR = 4
	MAIL_TYPE_HOME_MH      = 5

	SRV_MTA_UNKNOWN    = 0
	SRV_MTA_POSTFIX    = 1
	SRV_MTA_NULLMAILER = 2
	SRV_MTA_EXIM4      = 3
	SRV_MTA_QMAIL      = 4
	SRV_MTA_SENDMAIL   = 5

	SRV_IMAP_COURIER = 1
	SRV_IMAP_CYRUS   = 2
	SRV_IMAP_UW      = 3

	SRV_POP3_COURIER = 1
	SRV_POP3_QPOPPER = 2
	# end constants

	def __new__(cls) :
		"""This is a Singleton Design Pattern."""

		if cls.__singleton is None :
			cls.__singleton = object.__new__(cls)
		
		return cls.__singleton
	def __init__(self) :
		""" Gather underlying system configuration and load it for licorn.* """

		if sys.getdefaultencoding() == "ascii" :
			reload(sys)
			sys.setdefaultencoding("utf-8")

		self.main = {}
		self.app_name = 'Licorn'

		# THIS install_path is used in keywords / keywords gui, not elsewhere.
		# it is a hack to be able to test guis when Licorn is not installed.
		# → this is for developers only.
		self.install_path = os.getenv("LICORN_ROOT", "/usr")
		if self.install_path == '.' :
			self.share_data_dir = '.'
		else :
			self.share_data_dir = "%s/share/licorn" % self.install_path

		try :
			import tempfile
			self.tmp_dir = tempfile.mkdtemp()
	
			self.SetBaseDirsAndFiles()
			self.FindUserDir()
			self.LoadBaseConfiguration()

			self.LoadManagersConfiguration()

			self.Distro()

			self.LoadShells()
			self.LoadSkels()

			self.FindMTA()
			self.FindMailboxType()

			# TODO: monitor configuration files from a thread !

		except exceptions.LicornException, e :
			raise exceptions.BadConfigurationError("Configuration initialization failed:\n\t%s" % e)

	def CleanUp(self) :
		"""This is a sort of destructor. Clean-up before being deleted..."""

		if os.path.exists(self.tmp_dir) :
			import shutil
			# this is safe because tmp_dir was created with tempfile.mkdtemp()
			shutil.rmtree(self.tmp_dir)
	def SetBaseDirsAndFiles(self) :
		""" Find and create temporary, data and working directories."""

		self.mAutoPasswdSize         = 8
		self.config_dir              = "/etc/licorn"
		self.main_config_file        = self.config_dir + "/main.conf"
		self.backup_config_file      = self.config_dir + "/backup.conf"

		# system profiles, compatible with gnome-system-tools
		self.profiles_config_file    = self.config_dir + "/profiles.xml"
		
		self.privileges_whitelist_data_file = self.config_dir + "/privileges-whitelist.conf"
		self.keywords_data_file             = self.config_dir + "/keywords.conf"

		# extensions to /etc/group
		self.extendedgroup_data_file = self.config_dir + "/groups"
		self.home_backup_dir         = "/home/backup"
		self.home_archive_dir        = "/home/archives"

		# TODO: is this to be done by package maintainers or me ?
		self.CreateConfigurationDir()

	def FindUserDir(self) :
		"""if ~/ is writable, use it as user_dir to store some data, else use a tmp_dir."""
		try :
			home = os.environ["HOME"]
		except KeyError :
			home = None

		if home and os.path.exists(home) :
			
			try :
				# if our home exists and we can write in it, assume we are a standard user.
				fakefd = open(home + "/.licorn.fakefile", "w")
				fakefd.close()
				os.unlink(home + "/.licorn.fakefile")
				self.user_dir			= home + "/.licorn"
				self.user_config_file	= self.user_dir + "/config"

			except (OSError, IOError) :
				# we are «apache» or another special user (aesd...), we don't
				# have a home, but need a dir to put lock-files in.
				self.user_dir			= self.tmp_dir
				self.user_config_file	= None
		else :
			# we are «apache» or another special user (aesd...), we don't
			# have a home, but need a dir to put lock-files in.
			self.user_dir			= self.tmp_dir
			self.user_config_file	= None

		self.user_data_dir		= self.user_dir + "/data"

		if not os.path.exists(self.user_dir) :
			try :
				os.makedirs(self.user_data_dir)
				import stat
				os.chmod(self.user_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR )
				logging.info("Automatically created %s." % styles.stylize(styles.ST_PATH, self.user_dir + "[/data]"))
			except OSError, e:
				raise exceptions.LicornRuntimeError("Can't create / chmod %s[/data]:\n\t%s" % (self.user_dir, e))
	def LoadBaseConfiguration(self) :
		"""Load main configuration files."""

		try :
			 self.main = readers.shell_conf_load_dict(self.main_config_file)
		except IOError, e :
			if e.errno != 2 :
				# errno == 2 is "no such file or directory"
				raise e

	def CreateConfigurationDir(self) :
		"""Create the configuration dir if it doesn't exist."""

		if not os.path.exists(self.config_dir) :
			try :
				os.makedirs(self.config_dir)
				logging.info("Automatically created %s." % styles.stylize(styles.ST_PATH, self.config_dir))
			except (IOError,OSError), e :
				# user is not root, forget it !
				pass

	def Distro(self) :
		""" Determine which Linux / BSD / else distro we run on. """

		LicornConfiguration.distro = ""

		if os.name is "posix" :
			if os.path.exists( '/etc/lsb-release' ) :
				lsb_release = readers.shell_conf_load_dict('/etc/lsb-release')

				if lsb_release['DISTRIB_ID'] == 'Licorn' :
					LicornConfiguration.distro = LicornConfiguration.DISTRO_UBUNTU
				elif lsb_release['DISTRIB_ID'] == "Ubuntu" :
					if lsb_release['DISTRIB_CODENAME'] in ('dapper', 'edgy', 'feisty', 'gutsy', 'hardy') :
						LicornConfiguration.distro = LicornConfiguration.DISTRO_UBUNTU
					else :
						raise exceptions.LicornRuntimeError("This Ubuntu version is not yet supported, sorry !")
			
			else :
				# OLD / non-lsb compatible system or BSD
				if  os.path.exists( '/etc/gentoo-release' ) :
					raise exceptions.LicornRuntimeError("Gentoo is not yet supported, sorry !")
				elif  os.path.exists( '/etc/debian_version' ) :
					raise exceptions.LicornRuntimeError("Old Debian systems are not supported, sorry !")
				elif  os.path.exists( '/etc/redhat_release' ) :
					raise exceptions.LicornRuntimeError("RedHat/Mandrake is not yet supported, sorry !")
				else :
					raise exceptions.LicornRuntimeError("Unknown Linux Distro, sorry !")
		else :
			raise exceptions.LicornRuntimeError("Not on a supported system ! Please send a patch ;)")

		del(lsb_release)
	def FindMTA(self) :
		"""detect which is the underlying MTA."""

		LicornConfiguration.mta = None

		piddir   = "/var/run"
		spooldir = "/var/spool"

		#
		# Finding Postfix
		#
	
		if LicornConfiguration.distro == LicornConfiguration.DISTRO_UBUNTU :
			# postfix is chrooted on Ubuntu Dapper.
			if os.path.exists("/var/spool/postfix/pid/master.pid") :
				LicornConfiguration.mta = LicornConfiguration.SRV_MTA_POSTFIX
				return
		else :
			if os.path.exists("%s/postfix.pid" % piddir) :
				LicornConfiguration.mta = LicornConfiguration.SRV_MTA_POSTFIX
				return

		#
		# Finding NullMailer
		# 
		if os.path.exists("%s/nullmailer/trigger" % spooldir) :
			LicornConfiguration.mta = LicornConfiguration.SRV_MTA_NULLMAILER
			return
			
		LicornConfiguration.mta = LicornConfiguration.SRV_MTA_UNKNOWN
		logging.progress("MTA not installed or unsupported, please get in touch with cortex@5sys.fr.")	
	def FindMailboxType(self) :
		"""Find how the underlying system handles Mailboxes (this can be Maidlir, mail spool, and we must find where they are)."""

		# a sane (but arbitrary) default.
		# TODO : detect this from /etc/…
		LicornConfiguration.users.mailbox_auto_create = True

		if LicornConfiguration.mta == LicornConfiguration.SRV_MTA_POSTFIX :

			if LicornConfiguration.distro in (LicornConfiguration.DISTRO_UBUNTU, LicornConfiguration.DISTRO_DEBIAN, LicornConfiguration.DISTRO_GENTOO) :
				postfix_main_cf = readers.shell_conf_load_dict('/etc/postfix/main.cf')
			
			try :
				LicornConfiguration.users.mailbox_base_dir = postfix_main_cf['mailbox_spool']
				LicornConfiguration.users.mailbox_type     = LicornConfiguration.MAIL_TYPE_VAR_MBOX
			except KeyError :
				pass

			try :
				LicornConfiguration.users.mailbox = postfix_main_cf['home_mailbox']

				if LicornConfiguration.users.mailbox[-1:] == '/' :
					LicornConfiguration.users.mailbox_type = LicornConfiguration.MAIL_TYPE_HOME_MAILDIR
				else :
					LicornConfiguration.users.mailbox_type = LicornConfiguration.MAIL_TYPE_HOME_MBOX
				
			except KeyError :
				pass

			logging.debug2("Mailbox type is %d and base is %s." % (LicornConfiguration.users.mailbox_type, LicornConfiguration.users.mailbox))

		elif LicornConfiguration.mta == LicornConfiguration.SRV_MTA_NULLMAILER :

			# mail is not handled on this machine, forget the mailbox creation.
			LicornConfiguration.users.mailbox_auto_create = False

		elif LicornConfiguration.mta == LicornConfiguration.SRV_MTA_UNKNOWN :

			# totally forget about mail things.
			LicornConfiguration.users.mailbox_auto_create = False

		else :

			# totally forget about mail things.
			LicornConfiguration.users.mailbox_auto_create = False
			logging.progress("Mail{box,dir} system not supported yet. Please get in touch with cortex@5sys.fr.")

	def Ldap(self) :
		""" Loads LDAP configuration and parameters, if the system uses it.

			If nsswitch is using ldap, then the system is LDAP centric.
			We assume libnss_ldap is properly configured.
		"""
		#
		# TODO : test everything to avoid bombing if libnss_ldap is not properly
		# configured.
		#

		self.mNsSwitch = {}
		self.mNsSwitch = readers.simple_conf_load_dict_lists("/etc/nsswitch.conf")

		try :
			if 'ldap' in self.mNsSwitch['passwd'] and 'ldap' in self.mNsSwitch['group'] :

				#logging.debug("System is using LDAP for user accounts and groups.")

				self.mLdap				= readers.simple_conf_load_dict("/etc/ldap/ldap.conf")
				self.mLdapEnabled		= True
				self.mNssLdap			= readers.simple_conf_load_dict("/etc/libnss-ldap.conf")

				try :
					#
					# Get the LDAP secret. If we are root or SUDO it will succeed.
					# Else assume we can't bind as manager.
					# In case of any error, display a warning ; it could be a configuration
					# problem, but it could be harmless if it is simply "Joe User" trying
					# to use the program without any privileges.
					# IOError is "permission denied"
					#
					line = open("/etc/ldap.secret").readline()
					self.mLdapSecret = line[:-1]
				except (OSError, IOError) :
					self.mLdapSecret = None
				#
				# TODO : more LDAP sanity checks, and build needed defaults if empty
				# fields can be built from non-empty other (splitting or combinning).
				#
				# NOTE :
				# -> according to ldap.conf(5), HOST / PORT are deprecated in favor of URI.
				# We just stick to URI, it is sufficient for python-ldap.

				try :
					if self.mNssLdap["uri"] is '' :
						raise exceptions.LicornConfigurationError, "required field «uri» is EMPTY in /etc/libnss-ldap.conf !"
				except KeyError, e :
					raise exceptions.LicornConfigurationError, "required field «uri» is NOT SET in /etc/libnss-ldap.conf !"

			else :
				self.mLdapEnabled = False

		except KeyError, e :
			# XXX: encapsulate and raise a licorn exception ?
			raise e
	def LoadShells(self) :
		"""Find valid shells on the local system"""

		self.users.shells = []

		# specialty on Debian / Ubuntu : /etc/shells contains shells that are not installed
		# on the system. What is then the purpose of this file, knowing its definitions :
		# «/etc/shells contains the valid shells on a given system»...
		# specialty 2 : it does not contains /bin/false...

		for shell in readers.very_simple_conf_load_list("/etc/shells") :
			if os.path.exists(shell) :
				self.users.shells.append(shell)

		if "/bin/false" not in self.users.shells :
			self.users.shells.append("/bin/false")

		# hacker trick !
		if os.path.exists("/usr/bin/emacs") :
			self.users.shells.append("/usr/bin/emacs")
	def LoadSkels(self) :
		"""Find skel dirs on the local system."""

		self.users.skels = []

		if os.path.isdir("/etc/skel") :
			self.users.skels.append("/etc/skel")

		import stat

		for skel_path in ("/home/skels", "/usr/share/skels") :
			if os.path.exists(skel_path) :
				try :
					for new_skel in fsapi.minifind(path = skel_path, type = stat.S_IFDIR, mindepth = 2, maxdepth = 2) :
						self.users.skels.append(new_skel)
				except OSError, e:
					logging.warning("Custom skels must have at least %s perms on dirs and %s on files:\n\t%s" % (styles.stylize(styles.ST_MODE, "u+rwx,g+rx,o+rx"), styles.stylize(styles.ST_MODE, "u+rw,g+r,o+r"), e))

	### Users and Groups ###
	def LoadManagersConfiguration(self) :
		""" Load Users and Groups managements configuration. """

		# WARNING: don't change order of these.
		self.SetDefaultNames()
		self.SetUsersDefaults()
		self.SetGroupsDefaults()

		add_user_conf = self.CheckAndLoadAdduserConf()
		LicornConfiguration.users.uid_min         = add_user_conf['FIRST_UID']
		LicornConfiguration.users.uid_max         = add_user_conf['LAST_UID']
		LicornConfiguration.groups.gid_min        = add_user_conf['FIRST_GID']
		LicornConfiguration.groups.gid_max        = add_user_conf['LAST_GID']
		LicornConfiguration.users.system_uid_min  = add_user_conf['FIRST_SYSTEM_UID']
		LicornConfiguration.users.system_uid_max  = add_user_conf['LAST_SYSTEM_UID']
		LicornConfiguration.groups.system_gid_min = add_user_conf['FIRST_SYSTEM_GID']
		LicornConfiguration.groups.system_gid_max = add_user_conf['LAST_SYSTEM_GID']

		# ensure /etc/login.defs complies with /etc/adduser.conf
		self.CheckLoginDefs()

		#
		# WARNING: these values are meant to be used like this :
		#
		#  |<-               privileged              ->|<-                            UN-privileged                           ->|
		#    (reserved IDs)  |<- system users/groups ->|<-  standard users/groups ->|<- system users/groups ->|  (reserved IDs)
		#  |-------//--------|------------//-----------|--------------//------------|-----------//------------|------//---------|      
		#  0            system_*id_min             *id_min                       *id_max             system_*id_max           65535
		#
		# in unprivileged system users/groups, you will typically find www-data, proxy, nogroup, samba machines accounts...
		#

		#
		# The default values are referenced in CheckAndLoadAdduserConf() too.
		#
		for (attr_name, conf_key, fallback) in (
			('home_base_path', 'DHOME',    '/home/users'),
			('default_shell', 'DSHELL',    '/bin/bash'),
			('default_skel',  'SKEL',      '/etc/skel'),
			('default_gid',   'USERS_GID', 100) ) :
			try :
				val = add_user_conf[conf_key]
				setattr(LicornConfiguration.users, attr_name, val)
			except KeyError :
				setattr(LicornConfiguration.users, attr_name, fallback)

		# first guesses to find Mail system.
		LicornConfiguration.users.mailbox_type = 0
		LicornConfiguration.users.mailbox      = ""

		try :
			LicornConfiguration.users.mailbox      = add_user_conf["MAIL_FILE"]
			LicornConfiguration.users.mailbox_type = LicornConfiguration.MAIL_TYPE_HOME_MBOX
		except KeyError :
			pass

		try :
			LicornConfiguration.users.mailbox_base_dir = add_user_conf["MAIL_DIR"]
			LicornConfiguration.users.mailbox_type     = LicornConfiguration.MAIL_TYPE_VAR_MBOX
		except KeyError :
			pass

	def SetDefaultNames(self) :
		""" *HARDCODE* some names before we pull them out into configuration files."""
		
		self.defaults =  LicornConfigObject()

		self.defaults.home_base_path = '/home'

		# WARNING: Don't translate this. This still has to be discussed.
		# TODO: move this into a plugin
		self.defaults.admin_group = 'admins'

		# TODO: autodetect this & see if it not autodetected elsewhere.
		#self.defaults.quota_device = "/dev/hda1"
	def SetUsersDefaults(self) :
		"""Create LicornConfiguration.users attributes and start feeding it."""

		LicornConfiguration.users  = LicornConfigObject()

		# see groupadd(8), coming from addgroup(8)
		LicornConfiguration.users.login_maxlenght = 31

		# the _xxx variables are needed for gettextized interfaces (core and CLI are NOT gettextized)
		LicornConfiguration.users.names = { 
			'singular' : 'user', 
			'plural' :   'users',
			'_singular' : _('user'), 
			'_plural' :   _('users')
			}
	def SetGroupsDefaults(self) :
		"""Create LicornConfiguration.groups attributes and start feeding it."""

		LicornConfiguration.groups = LicornConfigObject()
		LicornConfiguration.groups.guest_prefix = 'gst-'
		LicornConfiguration.groups.resp_prefix = 'rsp-'


		# maxlenght comes from groupadd(8), itself coming from addgroup(8)
		# 31 - len(prefix)
		LicornConfiguration.groups.name_maxlenght = 27

		# the _xxx variables are needed for gettextized interfaces (core and CLI are NOT gettextized)
		LicornConfiguration.groups.names = { 
			'singular' : 'group', 
			'plural' : 'groups',
			'_singular' : _('group'), 
			'_plural' : _('groups')
			}
	
		LicornConfiguration.groups.privileges_whitelist = PrivilegesWhiteList(self.privileges_whitelist_data_file)
	def CheckAndLoadAdduserConf(self, batch = False, auto_answer = None) :
		""" Check the contents of adduser.conf to be compatible with Licorn.
			Alter it, if not.
			Then load it in a way i can be used in LicornConfiguration.
		"""

		adduser_conf       = '/etc/adduser.conf'
		adduser_conf_alter = False
		adduser_data       = open(adduser_conf, 'r').read()
		adduser_dict       = readers.shell_conf_load_dict(data = adduser_data)

		# warning: the order is important: in a default adduser.conf, only {FIRST,LAST}_SYSTEM_UID are
		# present, and we assume this during the file patch.
		defaults = (
			('DHOME',  '/home/users'),
			('DSHELL', '/bin/bash'),
			('SKEL',   '/etc/skel'),
			('GROUPHOMES',  'no'),
			('LETTERHOMES', 'no'),
			('USERGROUPS',  'no'),
			('LAST_GID',  29999),
			('FIRST_GID', 10000),
			('LAST_UID',  29999),
			('FIRST_UID', 1000),
			('LAST_SYSTEM_UID',  999),
			('FIRST_SYSTEM_UID', 100),
			('LAST_SYSTEM_GID',  9999),
			('FIRST_SYSTEM_GID', 100),
			)

		for (directive, value) in defaults :
			if directive in adduser_dict.keys() :
				if type(value) == type(1) :
					if value > adduser_dict[directive] :
						logging.warning('In %s, directive %s should be at least %s, but it is %s.'
							% (styles.stylize(styles.ST_PATH, adduser_conf), directive, value, adduser_dict[directive]))
						import re
						adduser_dict[directive] = value
						adduser_conf_alter      = True
						adduser_data            = re.sub(r'%s=.*' % directive, r'%s=%s' % (directive, value), adduser_data)
				else :
					if value != adduser_dict[directive] :
						logging.warning('In %s, directive %s should be set to %s, but it is %s.'
							% (styles.stylize(styles.ST_PATH, adduser_conf), directive, value, adduser_dict[directive]))
						import re
						adduser_dict[directive] = value
						adduser_conf_alter      = True
						adduser_data            = re.sub(r'%s=.*' % directive, r'%s=%s' % (directive, value), adduser_data)
						
				# else : everything's OK !
			else :
				logging.warning('In %s, directive %s is missing. Setting it to %s.'
					% (styles.stylize(styles.ST_PATH, adduser_conf),directive, value))
				import re
				adduser_dict[directive] = value
				adduser_conf_alter      = True
				adduser_data            = re.sub(r'(LAST_SYSTEM_UID.*)', r'\1\n%s=%s' % (directive, value), adduser_data)

		if adduser_conf_alter :
			if batch or logging.ask_for_repair('%s lacks mandatory configuration directive(s).'
							% styles.stylize(styles.ST_PATH, adduser_conf), auto_answer) :
				try :
					open(adduser_conf, 'w').write(adduser_data)
					logging.notice('Tweaked %s to match Licorn pre-requisites.' 
						% styles.stylize(styles.ST_PATH, adduser_conf))
				except (IOError, OSError), e :
					if e.errno == 13 :
						raise exceptions.LicornRuntimeError('Insufficient permissions. Are you root?\n\t%s' % e)
					else : raise e
			else :
				raise exceptions.LicornRuntimeError( "Modifications in %s are mandatory for Licorn to work properly with other system tools (adduser/useradd). Can't continue without this, sorry!" % adduser_conf)

		return adduser_dict
	def CheckLoginDefs(self, batch = False, auto_answer = None) :
		""" Check /etc/login.defs for compatibility with Licorn.
			Load data, alter it if needed and save the new file.
		"""

		login_defs       = "/etc/login.defs"
		login_defs_alter = False
		login_data       = open(login_defs, 'r').read()
		login_dict       = readers.simple_conf_load_dict(data = login_data)

		defaults = (
			('UID_MIN', LicornConfiguration.users.uid_min),
			('UID_MAX', LicornConfiguration.users.uid_max),
			('GID_MIN', LicornConfiguration.groups.gid_min),
			('GID_MAX', LicornConfiguration.groups.gid_max)
			)

		#
		# We assume login.defs has already all directives inside. This is sane,
		# because without one of them, any system will not run properly.
		#

		for (directive, value) in defaults :
			if login_dict[directive] != value :
				logging.warning('In %s, directive %s should be at least %s, but it is %s.'
					% (styles.stylize(styles.ST_PATH, login_defs), directive, value, login_dict[directive]))
				import re
				login_defs_alter      = True
				login_dict[directive] = value
				login_data            = re.sub(r'%s.*' % directive, r'%s	%s' % (directive, value), login_data)

		if login_defs_alter :
			if batch or logging.ask_for_repair('%s lacks mandatory configuration directive(s).'
							% styles.stylize(styles.ST_PATH, login_defs), auto_answer) :
				try :
					open(login_defs, 'w').write(login_data)
					logging.notice('Tweaked %s to match Licorn pre-requisites.'
						% styles.stylize(styles.ST_PATH, login_defs))			
				except (IOError, OSError), e :
					if e.errno == 13 :
						raise exceptions.LicornRuntimeError('Insufficient permissions. Are you root?\n\t%s' % e)
					else : raise e
			else :
				raise exceptions.LicornRuntimeError( "Modifications in %s are mandatory for Licorn to work properly. Can't continue without this, sorry!" % login_defs)
	def CheckDefaultProfile(self) :
		"""If no profile exists on the system, create a default one with system group "users"."""

		if self.profiles.profiles == [] :
			logging.warning('adding a default profile on the system (this is mandatory for %s to work).' % self.app_name)
			# Create a default profile with 'users' as default primary group, and use the Debian pre-existing group
			# without complaining if it exists.
			# TODO: translate/i18n these names ?
			self.profiles.AddProfile('Users', 'users', 
				shell = LicornConfiguration.users.default_shell,
				skel  = LicornConfiguration.users.default_skel,
				force_existing = True)
				
	### EXPORTS ###
	def Export(self, doreturn = True, args = None, cli_format = None) :
		""" Export «self» (the system configuration) to a human [styles.stylized and] readable form.
			if «doreturn» is True, return a "string", else write output directly to stdout.
		"""

		if args is not None :

			data = ""

			if cli_format == "bourne" :
				cli = { 'prefix' : "export ", 'name' : True, 'equals' : "=", 'suffix' : "" }
			elif  cli_format == "cshell" :
				cli = { 'prefix' : "setenv ", 'name' : True, 'equals' : " ", 'suffix' : "" }
			elif  cli_format == "PHP" :
				cli = { 'prefix' : "$", 'name' : True, 'equals' : "=", 'suffix' : ";" }
			elif  cli_format == "short" :
				cli = { 'prefix' : "", 'name' : False, 'equals' : "=", 'suffix' : "" }
			else :
				raise exceptions.BadArgumentError("Bad CLI output format « %s » !" % cli_format)

			if args[0] == "shells" :
				for shell in self.users.shells :
					data += "%s\n" % shell

			elif args[0] == "skels" :
				for skel in self.users.skels :
					data += "%s\n" % skel

			elif args[0] in ("config_dir", "main_config_file", "backup_config_file", "extendedgroup_data_file", "app_name") :
				
				varname = args[0].upper()

				if args[0] == "config_dir" :
					varval = self.config_dir
				elif args[0] == "main_config_file" :
					varval = self.main_config_file
				elif args[0] == "backup_config_file" :
					varval = self.backup_config_file
				elif args[0] == "extendedgroup_data_file" :
					varval = self.extendedgroup_data_file
				elif args[0] == "app_name" :
					varval = self.app_name

				if cli["name"] :
					data +=	 "%s%s%s\"%s\"%s\n" % (cli["prefix"], varname, cli["equals"], varval, cli["suffix"])
				else :
					data +=	 "%s\n" % (varval)
			else :
				raise NotImplementedError("Sorry, outputing selectively %s is not yet implemented !" % args[0])

		else :
			data = self._export_all()

		if doreturn is True :
			return data
		else :
			sys.stdout.write(data + "\n")
	def _export_all(self) :
		"""Export all configuration data in a visual way."""

		data = "%s\n" % styles.stylize(styles.ST_APPNAME, "LicornConfiguration")

		for attr in dir(self) :
			if attr[0] in '_ABCDEFGHIJKLMNOPQRSTUXWXYZ':
				# skip methods and python internals.
				continue

			# 24 is the len() of the longest attribute name
			data += u"\t\u21b3 %s%s : " % (" " * (32 - len(attr)), styles.stylize(styles.ST_ATTR, attr))

			if attr is 'mLdapSecret' :
				data += "%s\s" % styles.stylize(styles.ST_SECRET, str(self.mLdapSecret))
			elif attr is 'mLdap' :
				data += "\n\t\t" + str(self.mLdap).replace("', " , "',\n\t\t") + "\n"
			elif attr in ( 'mLdapEnabled', 'app_name', 'distro', 'mAutoPasswdSize', 'mCurrentHostname', 'mta') :
				data += "%s\n" % styles.stylize(styles.ST_ATTRVALUE, str(self.__getattribute__(attr)))
				# cf	http://www.reportlab.com/i18n/python_unicode_tutorial.html
				# and	http://web.linuxfr.org/forums/29/9994.html#599760
				# and	http://evanjones.ca/python-utf8.html
			elif attr is 'main' :
				data += "\n\t\t{\n\t\t"
				for name in self.main :
					data += "'" + str(name) + "' : " + str(self.main[name]) + ",\n\t\t"
				data += "}\n"
			elif attr in ('mHznGroup', 'mAddUser', 'mLoginDefs', 'mNssLdap') :
				data += "\n\t\t%s\n" % str(self.__getattribute__(attr)).replace(", " , ",\n\t\t")
			elif attr is 'mNsSwitch' :
				data += "\n\t\t" + str(self.mNsSwitch).replace("], " , "]\n\t\t") + "\n"
			elif attr.endswith('_dir') or attr.endswith('_file') or attr.endswith('_path') :
				data += "%s\n" % str(self.__getattribute__(attr))
			elif attr in ('users', 'groups', 'profiles', 'defaults') :
				data += "\n\t\t%s\n" % str(self.__getattribute__(attr))
			else :
				data += "%s, to be implemented in licorn.core.configuration.Export()\n" % styles.stylize(styles.ST_IMPORTANT, "UNREPRESENTABLE YET")
		return data
	def ExportXML(self) :
		""" Export «self» (the system configuration) to XML. """
		raise NotImplementedError("LicornConfig::ExportXML() not yet implemented !")

	### MODIFY ###
	def ModifyHostname(self, new_hostname) :
		"""Change the hostname of the running system."""

		if new_hostname == self.mCurrentHostname :
			return

		import re
	
		if not re.compile("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", re.IGNORECASE).match(new_hostname) :
			raise exceptions.BadArgumentError("new hostname must be composed only of letters, digits and hyphens, but not starting nor ending with an hyphen !")

		logging.progress("Doing preliminary checks...")
		self.CheckHostname()

		try :
			etc_hostname = file("/etc/hostname", 'w')
			etc_hostname.write(new_hostname)
			etc_hostname.close()
		except (IOError, OSError), e :
			raise exceptions.LicornRuntimeError("can't modify /etc/hostname, verify the file is still clean:\n\t%s)" % e)
	
	### CHECKS ###
	def CheckConfig(self, minimal = True, batch = False, auto_answer = None) :
		"""Check all components of system configuration and repair if asked for."""
		
		self.CheckBaseDirs(minimal, batch, auto_answer)
		self.CheckSystemGroups(minimal, batch, auto_answer)

		# not yet ready.
		#self.CheckHostname(minimal, auto_answer)
	def CheckBaseDirs(self, minimal = True, batch = False, auto_answer = None) :
		"""Check and eventually repair default needed dirs."""

		try :
			os.makedirs(self.users.home_base_path)
		except (OSError, IOError), e :
			if e.errno != 17 :
				raise e

		self.CheckSystemGroups(minimal, batch, auto_answer)

		acl_base      = "u::rwx,g::---,o:---" 
		acl_mask      = "m:rwx"
		acl_admins_ro = "g:%s:r-x" % self.defaults.admin_group
		acl_admins_rw = "g:%s:rwx" % self.defaults.admin_group

		# TODO: add all profiles groups to the access ACL.

		dirs_to_verify = [
			{
				'path'        : "/home/%s" % LicornConfiguration.groups.names['plural'],
				'user'        : 'root',
				'group'       : 'acl',
				'access_acl'  : "%s,%s,g:www-data:--x,g:users:--x,%s" % (acl_base, acl_admins_ro, acl_mask),
				'default_acl' : ""
			} ]

		from licorn.core import groups

		try :
			# batch this because it *has* to be corrected for system to work properly.
			fsapi.check_dirs_and_contents_perms_and_acls(dirs_to_verify, batch = True, allgroups = groups)

		except (IOError, OSError), e :
			if e.errno == 95 :
				# this is the *first* "not supported" error encountered (on config load of first licorn command).
				# try to make the error message kind of explicit and clear, to let administrator know he/she should
				# mount the partition with 'acl' option.
				raise exceptions.LicornRuntimeError("Filesystem must be mounted with `acl' option:\n\t%s" % e)
			else : raise e

		if not minimal :
			dirs_to_verify = [
				{
					'path'             : self.home_backup_dir,
					'user'             : 'root',
					'group'            : 'acl',
					'access_acl'       : "%s,%s,%s" % (acl_base, acl_admins_ro, acl_mask),
					'default_acl'      : "%s,%s,%s" % (acl_base, acl_admins_ro, acl_mask),
					'content_acl' : ("%s,%s,%s" % (acl_base, acl_admins_ro, acl_mask)).replace('r-x', 'r--').replace('rwx', 'rw-'),
				},
				{
					'path'             : self.home_archive_dir,
					'user'             : 'root',
					'group'            : 'acl',
					'access_acl'       : "%s,%s,%s" % (acl_base, acl_admins_rw, acl_mask),
					'default_acl'      : "%s,%s,%s" % (acl_base, acl_admins_rw, acl_mask),
					'content_acl' : ("%s,%s,%s" % (acl_base, acl_admins_rw, acl_mask)).replace('r-x', 'r--').replace('rwx', 'rw-'),
				} ]

			# no need to bother the user for that, correct it automatically anyway.
			fsapi.check_dirs_and_contents_perms_and_acls(dirs_to_verify, batch = True, allgroups = groups)
	def CheckSystemGroups(self, minimal = True, batch = False, auto_answer = None) :
		"""Check if needed groups are present on the system, and repair if asked for."""

		from licorn.core import groups

		if minimal :
			# 'skels', 'remotessh', 'webmestres' [and so on] are not here
			# because they will be added by their respective packages (plugins ?),
			# and they are not strictly needed for Licorn to operate properly.
			needed_groups = [ 'users', 'acl', self.defaults.admin_group ]
			
		else :
			needed_groups = LicornConfiguration.groups.privileges_whitelist

		for group in needed_groups :
			# licorn.system.groups is not loaded yet, and it would create a circular dependancy
			# to import it here, we HAVE to do this manually.
			if not groups.HasGroup(name = group) :
				if batch or logging.ask_for_repair(logging.CONFIG_SYSTEM_GROUP_REQUIRED % styles.stylize(styles.ST_NAME, group), auto_answer) :
					groups.AddGroup(group, system = True)
				else :
					raise exceptions.LicornRuntimeError(
						"The system group « %s » is mandatory but doesn't exist on your system !" % group + "\n"
						+ "Use « licorn-check config --yes » or « licorn-add group --system --name \"%s\" » to solve the problem." % group
						)
	def CheckHostname(self, batch = False, auto_answer = None) :
		""" Check hostname consistency (by DNS/reverse resolution), and check /etc/hosts against flakynesses."""

		import stat
		hosts_mode = os.stat("/etc/hosts").st_mode
		if not stat.S_IMODE(hosts_mode) & stat.S_IROTH :
			#
			# nsswitch will fail to resolve localhost/127.0.0.1 if /etc/hosts don't have sufficient permissions.
			#
			raise exceptions.BadConfigurationError("/etc/hosts must have at least o+r permissions.")


		line = open("/etc/hostname").readline()
		if line[:-1] != self.mCurrentHostname :
			raise exceptions.BadConfigurationError("current hostname and /etc/hostname are not in sync !")

		import socket

		# DNS check for localhost.
		hostname_ip = socket.gethostbyname(self.mCurrentHostname)

		if hostname_ip != '127.0.0.1' :
			raise exceptions.BadConfigurationError("hostname %s doesn't resolve to 127.0.0.1 but to %s, please check /etc/hosts !" % (self.mCurrentHostname, hostname_ip) )

		# reverse DNS check for localhost. We use gethostbyaddr() to allow the hostname
		# to be in the aliases (this is often the case for localhost in /etc/hosts).
		localhost_data = socket.gethostbyaddr('127.0.0.1')

		if not ( self.mCurrentHostname == localhost_data[0]
				or self.mCurrentHostname in localhost_data[1] ) :
			raise exceptions.BadConfigurationError("127.0.0.1 doesn't resolve back to hostname %s, please check /etc/hosts and/or DNS !" % self.mCurrentHostname)

		import licorn.tools.network as network
		
		dns = []
		for ns in network.nameservers() :
			dns.append(ns)
		
		logging.debug2("configuration|DNS: " + str(dns))
		
		# reverse DNS check for eth0
		eth0_ip = network.iface_address('eth0')

		#
		# FIXME : the only simple way to garantee we are on an licorn server is to
		# check dpkg -l | grep licorn-server. We should check this to enforce there is 
		# only 127.0.0.1 in /etc/resolv.conf if licorn-server is installed.
		#

		#
		# FIXME2 : when implementing previous FIXME, we should not but administrator if
		# /etc/licorn_is_installing is present (for example),
		# because during installation not everything is ready to go in production and this
		# is totally normal.
		#


		logging.debug2("configuration|eth0 IP: %s" % eth0_ip)

		try :
			eth0_hostname = socket.gethostbyaddr(eth0_ip)

			logging.debug2('configuration|eth0 hostname: %s' % eth0_hostname)

		except socket.herror, e :
			if e.args[0] == 1 :
				#
				# e.args[0] == h_errno == 1 is «Unknown host»
				# the IP doesn't resolve, we could be on a standalone host (not
				# an Licorn server), we must verify.
				#
				if '127.0.0.1' in dns :
					raise exceptions.BadConfigurationError("can't resolve %s (%s), is the dns server running on 127.0.0.1 ? Else check DNS files syntax !" % (eth0_ip, e.args[1]))
				elif eth0_ip in dns :
					# FIXME put 127.0.0.1 automatically in configuration ?
					raise exceptions.BadConfigurationError("127.0.0.1 *must* be in /etc/resolv.conf on an Licorn server.")
				#
				# if we reach here, this is the end of the function.
				#
		except Exception, e :
			raise exceptions.BadConfigurationError("Problem while resolving %s, please check configuration:\n\terrno %d, %s" % (eth0_ip, e.args[0], e.args[1]))
								
		else :

			# hostname DNS check fro eth0. use [0] (the hostname primary record) to enforce
			# the full [reverse] DNS check is OK. This is needed for modern SMTP servers, SSL
			# web certificates to be validated, among other things.
			eth0_reversed_ip = socket.gethostbyname(eth0_hostname[0])

			if eth0_reversed_ip != eth0_ip :
				if eth0_ip in dns :
					# FIXME put 127.0.0.1 automatically in configuration ?
					raise exceptions.BadConfigurationError("127.0.0.1 *must* be the only nameserver in /etc/resolv.conf on an Licorn server.")
				elif '127.0.0.1' in dns :
					raise exceptions.BadConfigurationError("DNS seems not properly configured (%s doesn't resolve back to itself)." % eth0_ip )
				else :
					logging.warning("DNS not properly configured (%s doesn't resolve to %, but to %s)"% ( eth0_hostname, eth0_ip, eth0_reversed_ip) )

			# everything worked, but it is safer to have 127.0.0.1 as the nameserver, inform administrator.
			if eth0_ip in dns or '127.0.0.1' :
				# FIXME put 127.0.0.1 automatically in configuration ?
				logging.warning("127.0.0.1 should be the only nameserver in /etc/resolv.conf on an Licorn server.")
								
		# FIXME : vérifier que l'ip d'eth0 et son nom ne sont pas codés en dur dans /etc/hosts, 
		# la série de tests sur eth0 aurait pu marcher grâce à ça et donc rien ne dit que la conf DNS est OK...
	def CheckMailboxConfigIntegrity(self, batch = False, auto_answer = None) :
		"""Verify "slaves" configuration files are OK, else repair them."""

		"""
			if mailbox :
				warning(unsupported)
			elif maildir :
				if courier-* :
					if batch or ... :

					else :
						warning()
				else :
					raise unsupported.
			else :
				raise unsupported

		"""

		pass

