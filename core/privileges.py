# -*- coding: utf-8 -*-
"""
Licorn core: privileges - http://docs.licorn.org/core/privileges.html

privileges - everything internal to system privileges management

:copyright:
	* 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	* partial 2005 Régis Cobrun <reg53fr@yahoo.fr>

:license: GNU GPL version 2

"""
import os, tempfile, pyinotify

from threading import Event

from licorn.foundations           import logging, exceptions
from licorn.foundations           import readers
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.ltraces import *
from licorn.foundations.base      import Singleton
from licorn.foundations.constants import filters

from licorn.core         import LMC
from licorn.core.groups  import Group
from licorn.core.classes import LockedController

class PrivilegesWhiteList(Singleton, LockedController):
	""" Manage privileges whitelist.

		.. note:: this Controller can serve as example for configuration file
			watching, using the inotifier and the watch hint (which avoids a
			configuration reload when we rewrite our own file.
	"""

	init_ok       = False
	load_ok       = False

	_licorn_protected_attrs = (
			LockedController._licorn_protected_attrs
			+ [ 'changed', 'conf_file', 'conf_hint' ]
		)

	#: used in RWI.
	@property
	def object_type_str(self):
		return _(u'privilege')
	@property
	def object_id_str(self):
		return _(u'GID')
	@property
	def sort_key(self):
		""" The key (attribute or property) used to sort
			User objects from RWI.select(). """
		return 'name'

	def __init__(self, conf_file=None):
		""" Read the configuration file and populate ourselves. """

		assert ltrace(TRACE_PRIVILEGES, '> PrivilegesWhiteList.__init__(%s)' %
			PrivilegesWhiteList.init_ok)

		if PrivilegesWhiteList.init_ok:
			return

		LockedController.__init__(self, 'privileges')

		if conf_file is None:
			self.conf_file = LMC.configuration.privileges_whitelist_data_file
		else:
			self.conf_file = conf_file

		self.changed = False

		PrivilegesWhiteList.init_ok = True
		assert ltrace(TRACE_PRIVILEGES, '< PrivilegesWhiteList.__init__(%s)' %
			PrivilegesWhiteList.init_ok)
	def load(self):
		if PrivilegesWhiteList.load_ok:
			return
		else:
			assert ltrace(TRACE_PRIVILEGES, '| load()')

			# Make sure our dependancies are OK.
			LMC.groups.load()

			# Then install the configuration file watcher. The hint will be
			# shared between us and the inotifier, to avoid reloading the
			# contents just after we save our own configuration file.
			#
			# The hint must exist before we call reload(), because in case
			# reload() detects an inconsistency, it will call serialize(),
			# which expects the hint to already be here.
			#
			# If an improbable event occurs during the first reload() phase,
			# this is not a problem because we already own the lock, and the
			# INotifier will have to wait until we release it. No race, no
			# collisions. Smart, hopefully.

			with self.lock:
				self.conf_hint = L_inotifier_watch_conf(
														self.conf_file, self)

				# then load our internal data.
				self.reload()

			PrivilegesWhiteList.load_ok = True
	def __del__(self):
		""" destructor. """
		# just in case it wasn't done before (in batched operations, for example).
		if self.changed:
			self.serialize()
	def reload(self, *args, **kwargs):
		""" Reload internal data. the event, *args and **kwargs catch the eventual
			inotify events.

			:param *args: receive an eventual pathname from an inotifier event.
			:param **kwargs: same thing (neither of them are used in any other
				case)
		"""

		with self.lock:

			# Empty us, to start from scratch and be sure that any previous
			# privilege is correcly demoted in the internal data structures.
			for privilege in self:
				privilege.is_privilege = False

			self.clear()

			# then load data from configuration file, and assign privileges
			# to internal groups.
			need_rewrite = False
			try:
				for privilege in readers.very_simple_conf_load_list(self.conf_file):

					try:
						group = LMC.groups.by_name(privilege)

					except KeyError:
						logging.warning(_(u'Skipped privilege {0} refering to '
							'a non-existing group.').format(
								stylize(ST_NAME, privilege)))
						need_rewrite = True
						continue

					if not self.__append(group, display=False):
						need_rewrite = True
						continue

			except IOError, e:
				if e.errno == 2:
					pass
				else:
					raise e

			if need_rewrite:
				# this is needed for serialize() to do its job.
				self.changed = True

				logging.notice(_(u'Rewriting privilege whitelist to remove '
						'non-existing references or duplicates.'))
				self.serialize()
	def add(self, privileges):
		""" One-time multi-add method (list as argument).
			This method doesn't need locking, all sub-methods are already.
		"""
		for priv in privileges:
			self.__append(priv)
		self.serialize()
	def delete(self, privileges):
		""" One-time multi-delete method (list as argument).
			This method doesn't need locking, all sub-methods are already.
		"""
		for priv in privileges:
			self.__remove(priv)
		self.serialize()
	def __append(self, privilege, display=True):
		""" Set append like: no doubles. """

		with self.lock:
			if privilege.name in self:
				logging.info(_(u'Skipped privilege %s, already whitelisted.') %
					stylize(ST_NAME, privilege.name))
				return False
			else:
				if privilege.is_standard or privilege.is_helper or privilege.profile:
					logging.warning(_(u'group %s cannot be promoted as '
						'privilege, it is not a pure system group.') %
						stylize(ST_NAME, privilege.name))
					return False

				else:
					self[privilege.name]   = privilege
					privilege.is_privilege = True
					self.changed           = True

					if display:
						logging.notice(_(u'Added privilege %s to whitelist.') %
							stylize(ST_NAME, privilege.name))
					return True
	def __remove(self, privilege):
		""" Remove without throw of exception """

		assert ltrace(TRACE_PRIVILEGES,'| remove(%s)' % privilege.name)

		#print repr(privilege), self.values()

		with self.lock:
			if privilege.name in self:
				del self[privilege.name]
				privilege.is_privilege = False
				self.changed = True
				logging.info(_(u'Removed privilege %s from whitelist.') %
					stylize(ST_NAME, privilege.name))
				return True

			else:
				logging.info(_(u'Skipped privilege %s, already not present '
					'in the whitelist.') % stylize(ST_NAME, privilege.name))
				return False
	def Select(self, filter_string):
		""" filter self against various criteria and return a list of matching
			privileges. """
		with self.lock:
			privs = self[:]
			filtered_privs = []
			if filters.ALL == filter_string:
				filtered_privs = privs
			return filtered_privs
	def confirm_privilege(self, priv):
		""" return a UID if it exists in the database. """
		if priv in self:
			return priv
		else:
			raise exceptions.DoesntExistException(
				_(u'Privilege {} does not exist').format(priv))
	def guess_one(self, priv):
		if priv in self:
			return priv
	def ExportCLI(self):
		""" present the privileges whitelist on command-line: one by line. """
		with self.lock:
			return '%s%s' % (
				'\n'.join(sorted(self.iterkeys())),
				'\n' if len(self)>0 else ''
				)
	def ExportXML(self):
		with self.lock:
			return '''<?xml version='1.0' encoding=\"UTF-8\"?>
<privileges-whitelist>\n%s%s</privileges-whitelist>\n''' % (
				'\n'.join(['	<privilege>%s</privilege>' % x
						for x in sorted(self.keys())]),
				'\n' if len(self)>0 else '')
	def serialize(self):
		""" Serialize internal data structures into the configuration file. """
		assert ltrace(globals()['TRACE_' + self.name.upper()], '| serialize()')
		with self.lock:
			if self.changed:

				#raise the hint level, so as the MOVED_TO event will make it
				# just back to the state where only ONE event will suffice to
				# trigger it again.
				self.conf_hint += 1

				#print '>> serialize', self.conf_hint

				ftemp, fpath = tempfile.mkstemp(dir=LMC.configuration.config_dir)

				os.write(ftemp, '%s\n' % '\n'.join(sorted(self.iterkeys())))
				os.fchmod(ftemp, 0644)
				os.fchown(ftemp, 0, 0)
				os.close(ftemp)

				os.rename(fpath, self.conf_file)
				self.changed = False
