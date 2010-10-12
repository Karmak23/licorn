# -*- coding: utf-8 -*-
"""
Licorn core - http://dev.licorn.org/documentation/core

privileges - everything internal to system privileges management

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2005 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2
"""

import Pyro.core

from licorn.foundations         import logging, styles, readers
from licorn.foundations.objects import Singleton

class PrivilegesWhiteList(list, Singleton, Pyro.core.ObjBase):
	""" Manage privileges whitelist. """

	conf_file = ""
	init_ok   = False
	changed   = None
	def __init__(self, configuration, conf_file):
		""" Read the configuration file and populate ourselves. """

		if PrivilegesWhiteList.init_ok:
			return

		Pyro.core.ObjBase.__init__(self)

		self.configuration = configuration
		configuration.set_controller('privileges', self)

		self.conf_file = conf_file
		self.groups    = None
		self.changed   = False

		self.reload()

		PrivilegesWhiteList.init_ok = True
	def __del__(self):
		""" destructor. """
		# just in case it wasn't done before (in batched operations, for example).
		if self.changed :
			self.WriteConf()
	def reload(self):
		""" reload internal data  """

		self[:] = []

		try:
			self.extend(readers.very_simple_conf_load_list(self.conf_file))
		except IOError, e:
			if e.errno == 2:
				pass
			else:
				raise e
		# TODO: si le fichier contient des doublons, faire plutot:
		# map(lambda (x): self.append(x),
		# readers.very_simple_conf_load_list(conf_file))

	def set_groups_controller(self, groups):
		self.groups = groups
		groups.set_privileges_controller(self)
	def add(self, privileges, listener=None):
		"""one-time multi-add method (list as argument)."""
		for priv in privileges:
			self.append(priv, listener=listener)
		self.WriteConf()
	def delete(self, privileges, listener=None):
		"""one-time multi-delete method (list as argument)."""
		for priv in privileges:
			self.remove(priv, listener=listener)
		self.WriteConf()
	def append(self, privilege, listener=None):
		""" Set append like: no doubles."""
		try:
			self.index(privilege)
		except ValueError:
			if self.groups.is_system_group(privilege):
				list.append(self, privilege)
				logging.info('Added privilege %s to whitelist.' %
					styles.stylize(styles.ST_NAME, privilege),
					listener=listener)
			else:
				logging.warning('''group %s can't be promoted as privilege, '''
					'''it is not a system group.''' % \
					styles.stylize(styles.ST_NAME, privilege),
					listener=listener)
		else:
			logging.info("privilege %s already whitelisted, skipped." % \
				styles.stylize(styles.ST_NAME, privilege), listener=listener)
	def remove(self, privilege, listener=None):
		""" Remove without throw of exception """
		try:
			list.remove(self, privilege)
			logging.info('Removed privilege %s from whitelist.' %
				styles.stylize(styles.ST_NAME, privilege),
				listener=listener)
		except ValueError:
			logging.info('''privilege %s is already not present in the '''
				'''whitelist, skipped.''' % \
					styles.stylize(styles.ST_NAME, privilege),
					listener=listener)
	def ExportCLI(self):
		""" present the privileges whitelist on command-line: one by line. """
		return '%s%s' % (
			'\n'.join(self),
			'\n' if len(self)>0 else ''
			)
	def ExportXML(self):
		return '''<?xml version='1.0' encoding=\"UTF-8\"?>
<privileges-whitelist>\n%s%s</privileges-whitelist>\n''' % (
				'\n'.join(['	<privilege>%s</privilege>' % x for x in self]),
				'\n' if len(self)>0 else '')
	def WriteConf(self):
		""" Serialize internal data structures into the configuration file. """
		self.sort()
		open(self.conf_file, 'w').write('%s\n' % '\n'.join(self))
