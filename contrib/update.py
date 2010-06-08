# -*- coding: utf-8 -*-
"""
Licorn service update infrastructure.

Copyright (C) 2007-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2

This program conforms to:
sftp://licorn.org/documentation/specifications/update-licorn-star.dia


"""
import os, re

from licorn           import logging, exceptions
from licorn.constants import *


class ServiceUpdateController (object):
	"""
		A class to configure/reconfigure/check/update Unix services configuration.
		You must derive this class, and implement some of its methods in your subclass,
		for the whole thing to work.
		
		Implement these in subclasses:
		===============================

		bool base_checks()			# totally optional;
		# checks basic things (if service is installed for instance).
		# displays warnings if something is wrong and raise LicornRuntimeError.
		# returns True if everything OK.
	
		bool service_enabled()
		bool service_running()
		start_service()				# optional, we have a sane default
		stop_service()				# optional, we have a sane default
		restart_service()			# optional, we have a sane default
		reload_service()			# optional, we have a sane default
	
		bool need_first_configuration()	# optional
		configure_first_time()			# needed if need_first_configuration() exists.

		bool need_manual_configuration()	# optional, will stop here if return False.
		manual_configuration_message		# required if previous func exists.

		# subparts can be only one part if appropriate, if your service is simple
		# to configure. multiparts helps when configuring complex services, to speed 
		# up when reconfiguration is not needed.
		
		subparts = [part1, part2, part3, ...]

		# each subpart must have 2 methods. these are checked in consistency_ckecks().
		bool part1_need_reconfigure()
		part1_reconfigure()

		bool part2_need_reconfiguration()
		part2_reconfigure()

		bool *_need_reconfiguration()
		*_reconfigure()

		[...]
	"""

	def __init__ (self, name, init_script, default_conf = None):
		object.__init__(self)
		
		self.start   = False
		self.restart = False
		self.reload  = False # NOT USED YET

		self.name         = name
		self.init_script  = init_script
		self.default_conf = default_conf
		self.subparts     = []

	def start_service (self):
		os.system("%s start" % self.init_script)
	def stop_service (self):
		os.system("%s stop" % self.init_script)
	def restart_service (self):
		os.system("%s restart" % self.init_script)
	def reload_service (self):
		os.system("%s reload" % self.init_script)
	def consistency_ckecks (self):
		
		for part in self.subparts:
			if not ( hasattr(self, '%s_need_reconfiguration' % part) and hasattr(self, '%s_reconfigure' % part)):
				raise exceptions.LicornRuntimeError("class %s: subpart %s lacks one method in ( %s_need_reconfiguration, %s_reconfigure)" % (self.__name__, part, part, part))
			
		return True
	def run (self):
		try:
			self.consistency_ckecks()

			if hasattr(self, 'base_checks'):
				self.base_checks()

			if self.service_enabled():

				if self.service_running():

					self.check_reconfiguration()

				else:
					
					self.check_configuration()	

			else: 
				self.check_configuration()

			
			if self.start:
				self.start_service()

			if self.restart:
				self.restart_service()

		except exceptions.LicornManualConfigurationException, e:
			logging.notice(e)
		except exceptions.LicornRuntimeException, e:
			logging.warning(e)
	def check_configuration (self):

		if hasattr(self, 'need_first_configuration') and self.need_first_configuration():

			self.start = True
			self.configure_first_time()
		
		elif hasattr(self, 'need_manual_configuration') and self.need_manual_configuration():
			raise exceptions.LicornManualConfigurationException(self.manual_configuration_message)

		else:

			self.check_reconfiguration()
	def check_reconfiguration (self):

		for part in self.subparts:
			if getattr(self, '%s_need_reconfiguration' % part) ():
				self.restart = True
				getattr(self, '%s_reconfigure' % part) ()

	def grep_wq(self, path, pattern):
		""" NOT USED YET. """
		return ( re.match(pattern, open(path).read()) != None )

