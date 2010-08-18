# -*- coding: utf-8 -*-
"""
Licorn core - http://dev.licorn.org/documentation/core

privileges - everything internal to system privileges management

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2005 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""

import sys, os

from licorn.foundations         import logging, exceptions, hlstr, styles, readers
from licorn.foundations.objects import Singleton



class PrivilegesWhiteList(list, Singleton):
	""" Manage privileges whitelist. """
	conf_file = ""
	changed = None
	def __init__(self, configuration, conf_file):
		""" Read the configuration file and populate ourselves. """
		self.configuration = configuration
		self.conf_file = conf_file
		self.changed   = False
		try:
			self.extend(readers.very_simple_conf_load_list(conf_file))
		except IOError, e:
			if e.errno == 2:
				pass
			else:
				raise e
		# TODO: si le fichier contient des doublons, faire plutot:
		# map(lambda (x): self.append(x),
		# readers.very_simple_conf_load_list(conf_file))
	def __del__(self):
		""" destructor. """
		# just in case it wasn't done before (in batched operations, for example).
		if self.changed :
			self.WriteConf()
	def append(self, privilege):
		""" Set append like: no doubles."""
		try:
			self.index(privilege)
		except ValueError:
			from licorn.core.groups import GroupsController
			groups = GroupsController(self.configuration)
			if groups.is_system_group(privilege):
				list.append(self, privilege)
			else:
				logging.warning("%s is not a privilege." % \
					styles.stylize(styles.ST_NAME, privilege))
		else:
			logging.info("privilege %s already whitelisted, skipped." % \
				styles.stylize(styles.ST_NAME, privilege))
	def remove(self, privilege):
		""" Remove without throw of exception """
		try:
			list.remove(self, privilege)
		except ValueError:
			logging.warning(
				"privilege %s doesn't exist in the whiteliste, skipped." % \
					styles.stylize(styles.ST_NAME, privilege))
	def WriteConf(self):
		""" Serialize internal data structures into the configuration file. """
		open(self.conf_file, "w").write("%s\n" % "\n".join(self))
