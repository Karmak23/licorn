# -*- coding: utf-8 -*-
"""
Licorn extensions - http://docs.licorn.org/extensions.html

:copyright: 2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

Extensions can "extend" :ref:`CoreController`s
		(ex. configuration) or :ref:`CoreObject`s (ex. :class:`User` or
		:class:`Group`).

"""

import os

from licorn.foundations           import logging
from licorn.foundations           import process
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton, MixedDictObject
from licorn.foundations.constants import services, svccmds

from licorn.core               import LMC
from licorn.core.classes       import ModulesManager, CoreModule

class ExtensionsManager(Singleton, ModulesManager):
	""" Store and manage all Licorn® extensions instances. For now, this
		manager does nothing more than the
		:class:`~licorn.core.classes.ModulesManager`.

		It just has a fixed name ``extensions`` (to match the
		:obj:`LMC.extensions` attribute where it's stored) and a fixed
		module path (where the current source file is stored).

		.. versionadded:: 1.3
	"""
	def __init__(self):
		assert ltrace('extensions', '| __init__()')
		ModulesManager.__init__(self,
				name='extensions',
				module_type='extension',
				module_path=__path__[0],
				module_sym_path='licorn.extensions'
			)
	def enable_extension(self, name):
		return ModulesManager.enable_module(self, name)
	def disable_extension(self, name):
		return ModulesManager.disable_module(self, name)
class LicornExtension(CoreModule):
	""" The bare minimum attributes and methods for an extension.

		Currently, it just sets the manager argument to the fixed
		:obj:`LMC.extensions` value (the
		:class:`~licorn.extensions.ExtensionsManager` global instance).

		.. versionadded:: 1.3
	"""
	def __init__(self, name='extension', controllers_compat=[]):
		CoreModule.__init__(self,
				name=name,
				manager=LMC.extensions,
				controllers_compat=controllers_compat
			)
		assert ltrace('extensions', '| LicornExtension.__init__(%s)' % name)
class ServiceExtension(LicornExtension):
	""" ServiceExtension implements service-related comfort-methods and
		automates calling the :obj:`LMC.system`
		:class:`~licorn.core.system.SystemController` instance service-related
		methods with current extension's arguments pre-set.

	"""
	#: static dict for service-related commands
	commands = {

		services.UPSTART: {
			#: the position in the list where the service name will be inserted.
			svccmds.POSITION : 1,
			svccmds.START    : ['start' ],
			svccmds.STOP     : ['stop' ],
			svccmds.RESTART  : ['restart' ],
			svccmds.RELOAD   : ['reload' ]
		},

		services.SYSV: {
			svccmds.POSITION : 1,
			svccmds.START    : ['service', 'start'],
			svccmds.STOP     : ['service', 'stop' ],
			svccmds.RESTART  : ['service', 'restart' ],
			svccmds.RELOAD   : ['service', 'reload' ]
		},
	}

	#: static messages displayed on service command execution.
	messages = {
		# TODO: implement exec_type.SUCCESS, .FAILURE, etc.
		svccmds.START    : 'Started service %s (%s).',
		svccmds.STOP     : 'Stopped service %s (%s).',
		svccmds.RESTART  : 'Restarted service %s (%s).',
		svccmds.RELOAD   : 'Reloaded service %s (%s).'
	}

	#: same, for too long services (user must be informed)
	messages_long = {
		# TODO: implement exec_type.SUCCESS, .FAILURE, etc.
		svccmds.START    : 'Starting service %s. Please wait, this can take a while.',
		svccmds.STOP     : 'Stopping service %s. Please wait, this can take a while.',
		svccmds.RESTART  : 'Restarting service %s. Please wait, this can take a while.',
		svccmds.RELOAD   : 'Reloading service %s. Please wait, this can take a while.'
	}

	def __init__(self, name='service_extension', controllers_compat=[],
			service_name=None, service_type=None, service_long=False):
		LicornExtension.__init__(self,
				name=name,
				controllers_compat=controllers_compat
			)
		assert ltrace('extensions', '| ServiceExtension.__init__(%s, %s, %s)' % (
			name, service_name, services[service_type]))

		self.service_name = service_name
		self.service_type = service_type
		self.service_long = service_long
	def running(self, pid_file):
		return process.already_running(pid_file)
	def service(self, command_type, no_wait=False):
		""" Manage our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command` with the
			``command_type`` argument.

			:param command_type: its value should be one from
				:obj:`~licorn.foundations.constants.svccmds` (except
				**UNKNOWN** please, which use is reserved).
			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return ServiceExtension.service_command(
			command_type, self.service_name, self.service_type,
			self.service_long)
	def start(self, no_wait=False):
		""" Shortcut method to start our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command`.

			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return ServiceExtension.service_command(
			svccmds.START, self.service_name, self.service_type,
			self.service_long)
	def reload(self, no_wait=False):
		""" Shortcut method to reload our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command`.

			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return ServiceExtension.service_command(
			svccmds.RELOAD, self.service_name, self.service_type,
			self.service_long)
	def stop(self, no_wait=False):
		""" Shortcut method to stop our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command`.

			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return ServiceExtension.service_command(
			svccmds.STOP, self.service_name, self.service_type,
			self.service_long)
	def restart(self, no_wait=False):
		""" Shortcut method to restart our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command`.

			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return ServiceExtension.service_command(
			svccmds.RESTART, self.service_name, self.service_type,
			self.service_long)
	@staticmethod
	def service_command(command_type, service_name, service_type, service_long):
		""" Execute a command on a given service at the system level and
			display an :func:`~licorn.foundations.logging.info` message.
		"""

		command = ServiceExtension.commands[service_type][command_type][:]
		command.insert(ServiceExtension.commands[service_type][
							svccmds.POSITION], service_name)

		if service_long:
			logging.info(ServiceExtension.messages_long[command_type] %
					stylize(ST_NAME, service_name))

		# TODO: better format for ret, strip multiple spaces, tabs...
		ret = process.execute(command)[1].strip().replace('\n', '')

		logging.notice(ServiceExtension.messages[command_type] % (
				stylize(ST_NAME, service_name), ret))
