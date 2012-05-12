# -*- coding: utf-8 -*-
"""
Licorn Foundations: base settings - http://docs.licorn.org/foundations/

Copyright (C) 2011 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import sys, os, getpass

# ================================================= Licorn® foundations imports
import logging, styles, events
# WARNING: don't import "options", this would produce a circular loop.
from ltrace    import *
from ltraces   import *
from styles    import *
from base      import ObjectSingleton, NamedObject, LicornConfigObject
from constants import roles, priorities

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

import readers, network, exceptions

__all__ = ('settings', )

class LicornSettings(ObjectSingleton, NamedObject, LicornConfigObject):
	def __init__(self, filename=None):
		assert ltrace_func(TRACE_SETTINGS)

		NamedObject.__init__(self, name='settings')
		LicornConfigObject.__init__(self)

		# make both classes happy when rendering str()
		self._name = self.name

		self.experimental_should_be_enabled = False

		self.defaults = LicornConfigObject(parent=self)

		self.defaults.home_base_path = '/home'
		self.defaults.check_homedir_filename = '00_default'

		# default expiration time (float, in seconds) for various things
		# (see core.classes.CoreFSController._expire_events()).
		self.defaults.global_expire_time = 10.0

		# WARNING: Don't translate this group name.
		# TODO: move this into a plugin ? extension ? else ?
		self.defaults.admin_group = 'admins'

		# TODO: autodetect this & see if it not autodetected elsewhere.
		#self.defaults.quota_device = "/dev/hda1"

		self.config_dir           = u'/etc/licorn'
		self.check_config_dir     = self.config_dir + u'/check.d'
		self.main_config_file     = self.config_dir + u'/licorn.conf'

		self.home_backup_dir         = self.defaults.home_base_path + u'/backup'
		self.home_archive_dir        = self.defaults.home_base_path + u'/archives'

		self.__load_factory_settings()

		# on first load, we don't emit the "settings_changed" event.
		# This would be like a false-positive.
		self.reload(emit_event=False)

		events.collect(self)
	def __str__(self):
		return LicornConfigObject.__str__(self)
	def __load_factory_settings(self):
		""" The defaults set here are expected to exist
			by other parts of the programs.

			Note: we use port 299 for pyro. This is completely unusual. Port 299
			doesn't seem to be reserved in a recent /etc/services file, and this
			ensure that we are root when binding the port, and thus provide a
			*small* security guarantee (any attacker but first gain root
			privileges or crash our daemons to bind the port and spoof our
			protocol). """

		assert ltrace(TRACE_SETTINGS, '| load_factory_defaults()')

		self.merge_settings({
			'role'                         : roles.UNSET,
			'pyro.port'                    : int(os.getenv('PYRO_PORT', 299)),
			'backup.interval'              : 86400,   # one day between backups.
			'experimental.enabled'         : self.experimental_should_be_enabled,

			# TODO: move the following directives to where they belong.

			# system profiles, compatible with gnome-system-tools
			'core.profiles.config_file'    : self.config_dir + u'/profiles.xml',
			'core.privileges.config_file'  : self.config_dir + u'/privileges-whitelist.conf',
			'core.keywords.config_file'    : self.config_dir + u'/keywords.conf',
			# extensions to /etc/group
			'backends.shadow.extended_group_file' : self.config_dir + u'/groups',
			'backends.openldap.organization'      : 'Licorn®',
			}, emit_event=False)
	def __convert_settings_values(self):
		assert ltrace(TRACE_SETTINGS, '| BaseDaemon.__convert_settings_values()')

		if self.role not in roles:
			# use upper() to avoid bothering user if he has typed "server"
			# instead of "SERVER". Just be cool when possible.
			if hasattr(roles, self.role.upper()):
				self.role = getattr(roles, self.role.upper())
	def __check_debug_variable(self):
		self.debug = []

		env_variable = os.getenv('LICORN_DEBUG', None)

		if env_variable is not None and os.geteuid() == 0:
			self.debug.extend(d.lower() for d in env_variable.split(','))

			logging.warning(_(u'{0}: internal debug enabled for {1}').format(
						stylize(ST_NAME, 'settings'),
						u', '.join(stylize(ST_NAME, x) for x in self.debug)))
	def check(self):
		""" Check directives which must be set, and values, for correctness. """

		assert ltrace_func(TRACE_SETTINGS)

		self.__check_settings_role()
		self.__check_settings_backup()
		self.__check_debug_variable()
	def __check_settings_role(self):
		""" check the licornd.role directive for correctness. """

		assert ltrace_func(TRACE_SETTINGS)

		if self.role == roles.UNSET or self.role not in roles:
			raise exceptions.BadConfigurationError(_(u'%s is currently '
				u'unset or invalid in %s. Please set it to either %s or '
				u'%s and retry.') % (
					stylize(ST_SPECIAL, 'role'),
					stylize(ST_PATH, self.main_config_file),
					stylize(ST_COMMENT, 'SERVER'),
					stylize(ST_COMMENT, 'CLIENT')
					)
				)
	@events.handler_method
	def configuration_loaded(self, event, *args, **kwargs):
		""" This one needs to be defered until LMC.configuration is loaded,
			else we create a chicken-and-egg problem. """

		if self.role == roles.CLIENT:
			logging.progress(_(u'Trying to find our Licorn® server…'))
			self.server_main_address = network.find_server()
			if self.server_main_address is None:
				logging.error(_(u'Could not find our Licorn® server via '
					u'autodetection. Please contact your network '
					u'administrator or set the {0} environment variable.').format(
					stylize(ST_NAME, 'LICORN_SERVER')))
			logging.notice(_(u'Our Licorn® server is {0}').format(
							stylize(ST_NAME, self.server_main_address)))
	def __check_settings_backup(self):
		""" TODO. """

		if self.backup.interval < 3600 or self.backup.interval > 604800:
			raise exceptions.BadConfigurationError(_(
				u'\n\tinvalid value %s for configuration '
				u'directive %s: must be an integer between '
				u'%s (one hour) and %s (one week).') % (
					stylize(ST_BAD, self.backup.interval),
					stylize(ST_COMMENT, 'backup.interval'),
					stylize(ST_COMMENT, '3600'), stylize(ST_COMMENT, '604800')))
	def merge_settings(self, conf, overwrite=True, emit_event=True):
		""" Build the licorn configuration object from a dict. """

		assert ltrace_func(TRACE_SETTINGS)

		changed = False

		for key in conf.keys():
			subkeys = key.split('.')
			if len(subkeys) > 1:
				curobj = self
				for subkey in subkeys[:-1]:
					if not hasattr(curobj, subkey):
						setattr(curobj, subkey, LicornConfigObject(parent=curobj))
					#down one level.
					curobj = getattr(curobj, subkey)

				if hasattr(curobj, subkeys[-1]):
					if getattr(curobj, subkeys[-1]) != conf[key] and overwrite:
						assert ltrace(TRACE_SETTINGS, '  settings: subkey {0} '
							'changed from {1} to {2}', (ST_NAME, key),
								(ST_ATTR, getattr(curobj, subkeys[-1])),
								(ST_ATTR, conf[key]))
						setattr(curobj, subkeys[-1], conf[key])
						changed = True

				else:
					setattr(curobj, subkeys[-1], conf[key])
					changed = True

			else:
				if hasattr(self, key):
					if getattr(self, key) != conf[key] and overwrite:
						assert ltrace(TRACE_SETTINGS, '  settings: subkey {0} '
							'changed from {1} to {2}', (ST_NAME, key),
								(ST_ATTR, getattr(self, key)),
								(ST_ATTR, conf[key]))
						setattr(self, key, conf[key])
						changed = True

				else:
					setattr(self, key, conf[key])
					changed = True

		if changed and emit_event:
			from licorn.foundations.events import LicornEvent
			LicornEvent('settings_changed').emit()
	def __load_main_config_file(self, emit_event=True):
		"""Load main configuration file, and set mandatory defaults
			if it doesn't exist."""

		assert ltrace_func(TRACE_SETTINGS)

		try:
			self.merge_settings(readers.shell_conf_load_dict(
				self.main_config_file, convert='full'), emit_event=emit_event)

		except IOError, e:
			if e.errno != 2:
				# errno == 2 is "no such file or directory" -> don't worry if
				# main config file isn't here, this is not required.
				raise e

		assert ltrace_func(TRACE_SETTINGS, 1)
	def reload(self, emit_event=True):
		self.__load_main_config_file(emit_event)

		# TODO:
		#self.__load_config_directory()

		self.__convert_settings_values()
		self.check()

		if self.experimental.enabled and os.geteuid() == 0:
			logging.notice(stylize(ST_ATTR, _(u'Experimental features enabled. '
				u'Have fun, but do not break anything%s.') % (
					stylize(ST_IMPORTANT, _(u' (hear me Nibor?)'))
						if getpass.getuser() in ('robin', 'robin2', 'nibor', 'nibor2',
							'lucbernet', 'rlucbernet', 'r.lucbernet', 'robin.lucbernet',
							'tenrebcul', 'ntenrebcul', 'n.tenrebcul', 'nibor.tenrebcul')
						else u'')))

settings = LicornSettings()
