# -*- coding: utf-8 -*-
"""
Licorn extensions: OpenSSH - http://docs.licorn.org/extensions/openssh.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

import os

from licorn.foundations           import exceptions, logging
from licorn.foundations           import fsapi, readers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, MixedDictObject
from licorn.foundations.classes   import ConfigFile
from licorn.foundations.constants import services, svccmds

from licorn.core               import LMC
from licorn.extensions         import ServiceExtension

class OpensshExtension(Singleton, ServiceExtension):
	""" Handle [our interesting subset of] OpenSSH configuration and options.
	"""
	def __init__(self):
		assert ltrace('extensions', '| __init__()')
		ServiceExtension.__init__(self,
			name='openssh',
			service_name='ssh',
			service_type=services.UPSTART
		)

		# TODO: parameter service_* from the distro
		# 		if LMC.configuration.distro in (
		#	distros.LICORN,
		#	distros.UBUNTU,
		#	distros.DEBIAN,
		#	distros.REDHAT,
		#	distros.GENTOO,
		#	distros.MANDRIVA,
		#	distros.NOVELL
		#	):

		self.paths.sshd_config = '/etc/ssh/sshd_config'
		self.paths.sshd_binary = '/usr/sbin/sshd'
		self.paths.pid_file    = '/var/run/sshd.pid'
		self.paths.disabler    = '/etc/ssh/sshd_not_to_be_run'

		self.group = 'remotessh'

		self.defaults = {
				'UsePAM'                 : 'yes',
				'StrictMode'             : 'yes',
				'AllowGroups'            : '%s %s' % (
						LMC.configuration.defaults.admin_group,
						self.group
					),
				'PermitRootLogin'        : 'no',
				'PasswordAuthentication' : 'no',
			}
	def initialize(self):
		""" Return True if :program:`sshd` is installed on the local system.
		"""

		if os.path.exists(self.paths.sshd_binary) \
				and os.path.exists(self.paths.sshd_config):
			self.available = True

			self.configuration = ConfigFile(self.paths.sshd_config,
					readers.simple_conf_load_dict)
		else:
			logging.warning2('%s: not available because %s or %s do not exist '
				'on the system.' % (stylize(ST_PATH, self.paths.sshd_binary),
					stylize(ST_PATH, self.paths.sshd_config)))

		return self.available
	def is_enabled(self):
		""" OpenSSH server is enabled when this file does not exist. """

		must_be_running = not os.path.exists(self.paths.disabler)

		if must_be_running:
			# upstart will not start the service twice. thanks, it just
			# works well...
			#and not process.already_running(self.paths.pid_file):
			self.service(svccmds.START)

		return must_be_running
	def check(self, batch=False, auto_answer=None):
		""" check OpenSSH needed things. """

		logging.progress('Checking existence of group %s…' %
				stylize(ST_NAME, self.group))

		need_reload = False

		# TODO if not self.group in LMC.groups.by_name:
		if not LMC.groups.exists(name=self.group):
			need_reload = True
			if batch or logging.ask_for_repair('group %s must be created' %
					stylize(ST_NAME, self.group), auto_answer=auto_answer):
				LMC.groups.AddGroup(name=self.group,
					description=_('Users allowed to connect via SSHd'),
					system=True, batch=True)
			else:
				raise exceptions.LicornCheckError(
						'group %s must exist before continuing.' % self.group)

		logging.progress('Checking good default values in %s…' %
				stylize(ST_PATH, self.paths.sshd_config))

		need_rewrite = False
		for key, value in self.defaults.iteritems():
			if not self.configuration.has(key, value):
				need_rewrite = True
				self.configuration.add(key, value, replace=True)

		if need_rewrite:
			if batch or logging.ask_for_repair('%s must be modified' %
					stylize(ST_PATH, self.paths.sshd_config),
					auto_answer=auto_answer):
				self.configuration.backup()
				self.configuration.save()
				logging.info('Written configuration file %s.' %
					stylize(ST_PATH, self.paths.sshd_config))
			else:
				raise exceptions.LicornCheckError(
						'configuration file %s must be altered to continue.' %
							self.paths.sshd_config)

		if need_reload or need_rewrite:
			self.service(svccmds.RELOAD)
	def enable(self, batch=False, auto_answer=None):
		""" Start ``SSHd``, after having carefully checked all our needed
			parameters and unlinked the service disabler file.
		"""

		self.check(batch=batch, auto_answer=auto_answer)

		# this has to be done as late as possible, thus after the check, to
		# avoid potential races (starting the service from outside Licorn®
		# while we are writing the config file in self.check(), for example).
		os.unlink(self.path.disabler)
		self.service(svccmds.START)
	def disable(self):
		""" Stop the running SSHd and touch the disabler file to make sure
			it is not restarted outside of Licorn®.

			.. note:: TODO: we've got to check this operation is atomic.
				Shouldn't we create the disabler file before stopping the
				service, to be sure no one else can race-start it ?
			"""
		self.service(svccmds.STOP)
		fsapi.touch(self.paths.disabler)
