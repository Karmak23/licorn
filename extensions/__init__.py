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
from threading import RLock, Timer

from licorn.foundations           import logging, exceptions
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

		.. versionadded:: 1.2.4
	"""
	def __init__(self, name='extension', controllers_compat=[]):
		CoreModule.__init__(self,
				name=name,
				manager=LMC.extensions,
				controllers_compat=controllers_compat
			)

		#: add a locking capability for multi-thread safety.
		self.lock = RLock()
		assert ltrace('extensions', '| LicornExtension.__init__(%s)' % name)
class ServiceExtension(LicornExtension):
	""" ServiceExtension implements service-related comfort-methods and
		automates calling the :obj:`LMC.system`
		:class:`~licorn.core.system.SystemController` instance service-related
		methods with current extension's arguments pre-set.

		.. versionadded:: 1.2.4
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

		#: just a bool to display a supplemental "please wait" messages for
		#: know long services to acheive operations.
		self.service_long = service_long

		#: to avoid running multiple service calls, and delayed run to
		#: interfere with a newly created one.
		self.command_lock = RLock()

		#: the current delayed command, stored to raise an exception if another
		#: in ran while this one has not yet completed.
		self.planned_operation = None

		#: the reference to the :class:`~threading.Timer` thread, to be able to
		#: wipe old ones to reclaim system resources.
		self.command_thread = None

		#: the delay the timer will wait before trigerring the service command.
		#: any repetition of the same command within this delay will reset it.
		self.delay = 0.5
	def running(self, pid_file):
		""" A convenience wrapper for the :func:`~process.already_running`
			function. """
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
		return self.service_command(command_type)
	def start(self, no_wait=False):
		""" Shortcut method to start our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command`.

			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return self.service_command(svccmds.START)
	def reload(self, no_wait=False):
		""" Shortcut method to reload our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command`.

			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return self.service_command(svccmds.RELOAD)
	def stop(self, no_wait=False):
		""" Shortcut method to stop our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command`.

			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return self.service_command(svccmds.STOP)
	def restart(self, no_wait=False):
		""" Shortcut method to restart our service by calling
			:meth:`~licorn.extensions.ServiceExtension.service_command`.

			:param no_wait: specify if we should wait for service command
				to return, or not. **Currently ignored (not used)** because
				only upstart understands it and we don't implement that level
				of preciseness.
		 """
		return self.service_command(svccmds.RESTART)
	def service_command(self, command_type):
		""" Run a service operation at the system level. This method will
			create a :class:`~threading.Timer` thread with a small delay, to
			optimize batched operations: the service command will not be issued
			if another command (same type) comes while the timer is running.

			This methods
		"""

		assert ltrace(self.name, '| service_command(%s)' % command_type)

		command = ServiceExtension.commands[self.service_type][command_type][:]
		command.insert(ServiceExtension.commands[self.service_type][
							svccmds.POSITION], self.service_name)

		if self.service_long:
			pre_message = ServiceExtension.messages_long[command_type] % (
							stylize(ST_NAME, self.service_name))
		else:
			pre_message = None

		post_message = ServiceExtension.messages[command_type] % (
						stylize(ST_NAME, self.service_name), '%s')

		thread_kwargs = {
				'command'      : command,
				'pre_message'  : pre_message,
				'post_message' : post_message,
				'svcext'       : self
			}

		if self.planned_operation:
			if self.planned_operation != command_type:

				raise exceptions.BadArgumentError('%s: command %s '
					'already in the queue, cannot plan a different '
					'one. Please try again later.' % (self.name,
						svccmds[self.planned_operation]))
			else:
				with self.command_lock:
					# reset the timer.
					self.command_thread.cancel()
					del self.command_thread

					self.command_thread = Timer(self.delay,
								run_service_command, kwargs=thread_kwargs)
					self.command_thread.start()
		else:
			with self.command_lock:
				self.planned_operation = command_type

				assert ltrace(self.name, '| service_command: delaying '
					'operation in case there are others coming after this one.')

				if self.command_thread:
					# wipe any traces of older job to reclaim resources.
					del self.command_thread

				self.command_thread = Timer(self.delay,
								run_service_command, kwargs=thread_kwargs)
				self.command_thread.start()
def run_service_command(command, pre_message=None, post_message=None,
		svcext=None):
	""" This is the "real" function ran by the :class:`~threading.Timer`
		thread, managed by the :meth:`~ServiceExtension.service_command`
		method.

		It is in charge of displaying messages if given, and run the real
		system-level command to execute the service operation.

		.. note:: this function will acquire/release the
			:attr:`ServiceExtension.command_lock` lock, to avoid
			interferences during the service operation (which can be long,
			depending on the service).

		.. versionadded:: 1.2.4
	"""

	assert ltrace('process', '| run_service_command(%s)' % command)

	if svcext is not None:
		svcext.command_lock.acquire()

	if pre_message:
		logging.notice(pre_message)

	# TODO: better format for ret, strip multiple spaces, tabs...
	ret = process.execute(command)[1].strip().replace('\n', '')

	if post_message:
		if ret == '':
			ret = 'OK'

		logging.info(post_message % ret)

	if svcext is not None:
		svcext.planned_operation = None
		svcext.command_lock.release()
