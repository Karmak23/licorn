# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2
"""

import os, stat, posix1e, re
import Pyro.core
from time import strftime, gmtime
from threading import RLock

from licorn.foundations           import logging, exceptions
from licorn.foundations           import fsapi, pyutils, hlstr
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton
from licorn.foundations.constants import filters, backend_actions

from licorn.core         import LMC
from licorn.core.classes import CoreController

class GroupsController(Singleton, CoreController):
	""" Manages the groups and the associated shared data on a Linux system. """

	init_ok = False
	load_ok = False

	def __init__ (self, warnings=True):

		assert ltrace('groups', '> GroupsController.__init__(%s)' %
			GroupsController.init_ok)

		if GroupsController.init_ok:
			return

		CoreController.__init__(self, 'groups', warnings)
		self.inotifier = None

		GroupsController.init_ok = True
		assert ltrace('groups', '< GroupsController.__init__(%s)' %
			GroupsController.init_ok)
	def load(self):
		if GroupsController.load_ok:
			return
		else:
			assert ltrace('groups', '| load()')
			# be sure our depency is OK.
			LMC.users.load()
			self.reload()
			LMC.configuration.groups.hidden = self.GetHiddenState()
			GroupsController.load_ok = True
	def __del__(self):
		assert ltrace('groups', '| __del__()')
	def __getitem__(self, item):
		return self.groups[item]
	def __setitem__(self, item, value):
		self.groups[item]=value
	def keys(self):
		with self.lock():
			return self.groups.keys()
	def has_key(self, key):
		with self.lock():
			return self.groups.has_key(key)
	def reload(self):
		""" load or reload internal data structures from files on disk. """

		assert ltrace('groups', '| reload()')

		# lock users too, because we feed the members cache inside.
		with self.lock():
			with LMC.users.lock():
				self.groups     = {}
				self.name_cache = {}

				for backend in self.backends():
					g, c = backend.load_Groups()
					self.groups.update(g)
					self.name_cache.update(c)
	def reload_backend(self, backend_name):
		""" reload only one backend contents (used from inotifier). """
		assert ltrace('groups', '| reload_backend(%s)' % backend_name)

		# lock users too, because we feed the members cache inside.
		with self.lock():
			with LMC.users.lock():
				g, c = LMC.backends[backend_name].load_Groups()
				self.groups.update(g)
				self.name_cache.update(c)
	def GetHiddenState(self):
		""" See if /home/groups is readable or not. """

		try:
			for line in posix1e.ACL(file='%s/%s' % (
				LMC.configuration.defaults.home_base_path,
				LMC.configuration.groups.names.plural)):
				if line.tag_type & posix1e.ACL_GROUP:
					try:
						if line.qualifier == self.name_to_gid(
							LMC.configuration.users.group):
							return not line.permset.read
					except AttributeError:
						# we got AttributeError because name_to_gid() fails,
						# because controller has not yet loaded any data. Get
						# the needed information by another mean.
						import grp
						if line.qualifier == grp.getgrnam(
							LMC.configuration.users.group).gr_gid:
							return not line.permset.read

		except exceptions.DoesntExistsException:
			# the group "users" doesn't exist, or is not yet created.
			return None
		except (IOError, OSError), e:
			if e.errno == 13:
				LicornConfiguration.groups.hidden = None
			elif e.errno != 2:
				# 2 will be corrected in this function
				raise e
	def set_inotifier(self, inotifier):
		self.inotifier = inotifier
	def WriteConf(self, gid=None):
		""" Save Configuration (internal data structure to disk). """

		assert ltrace('groups', '> WriteConf(%s)' % gid)

		with self.lock():
			if gid:
				LMC.backends[
					self.groups[gid]['backend']
					].save_Group(gid, backend_actions.UPDATE)

			else:
				for backend in self.backends():
					backend.save_Groups()

		assert ltrace('groups', '< WriteConf()')
	def Select(self, filter_string):
		""" Filter group accounts on different criteria:
			- 'system groups': show only «system» groups (root, bin, daemon,
				apache…),	not normal group account.
			- 'normal groups': keep only «normal» groups, which includes
				Licorn administrators
			The criteria values are defined in /etc/{login.defs,adduser.conf}
		"""

		filtered_groups = []

		assert ltrace('groups', '> Select(%s)' % filter_string)

		with self.lock():
			if filters.NONE == filter_string:
				filtered_groups = []

			elif type(filter_string) == type([]):
				filtered_groups = filter_string

			elif filters.ALL == filter_string:
				assert ltrace('groups', '> Select(ALL:%s/%s)' % (
					filters.ALL, filter_string))

			elif filters.STANDARD == filter_string:
				assert ltrace('groups', '> Select(STD:%s/%s)' % (
					filters.STD, filter_string))

				filtered_groups.extend(filter(self.is_standard_gid,
					self.groups.keys()))

			elif filters.EMPTY == filter_string:
				assert ltrace('groups', '> Select(EMPTY:%s/%s)' % (
					filters.EMPTY, filter_string))

				filtered_groups.extend(filter(self.is_empty_gid,
					self.groups.keys()))

			elif filters.SYSTEM & filter_string:

				if filters.GUEST == filter_string:
					assert ltrace('groups', '> Select(GST:%s/%s)' % (
						filters.GST, filter_string))
					for gid in self.groups.keys():
						if self.groups[gid]['name'].startswith(
							LMC.configuration.groups.guest_prefix):
							filtered_groups.append(gid)

				elif filters.SYSTEM_RESTRICTED == filter_string:
					ltrace('groups', '> Select(SYSTEM_RESTRICTED:%s/%s)' % (
						filters.SYSTEM_RESTRICTED, filter_string))

					filtered_groups.extend(filter(self.is_restricted_system_gid,
						self.groups.keys()))

				elif filters.SYSTEM_UNRESTRICTED == filter_string:
					ltrace('groups', '> Select(SYSTEM_UNRESTRICTED:%s/%s)' % (
						filters.SYSTEM_UNRESTRICTED, filter_string))

					filtered_groups.extend(filter(
						self.is_unrestricted_system_gid, self.groups.keys()))

				elif filters.RESPONSIBLE == filter_string:
					assert ltrace('groups', '> Select(RSP:%s/%s)' % (
						filters.RSP, filter_string))

					for gid in self.groups.keys():
						if self.groups[gid]['name'].startswith(
							LMC.configuration.groups.resp_prefix):
							filtered_groups.append(gid)

				elif filters.PRIVILEGED == filter_string:
					assert ltrace('groups', '> Select(PRI:%s/%s)' % (
						filters.PRI, filter_string))

					for name in LMC.privileges:
						try:
							filtered_groups.append(
								self.name_to_gid(name))
						except exceptions.DoesntExistsException:
							# this system group doesn't exist on the system
							pass
				else:
					assert ltrace('groups', '> Select(SYS:%s/%s)' % (
						filters.SYS, filter_string))
					filtered_groups.extend(filter(self.is_system_gid,
						self.groups.keys()))

			else:
				gid_re    = re.compile("^gid=(?P<gid>\d+)")
				gid_match = gid_re.match(filter_string)
				if gid_match is not None:
					gid = int(gid_match.group('gid'))
					filtered_groups.append(gid)

		assert ltrace('groups', '< Select(%s)' % filtered_groups)
		return filtered_groups
	def dump(self):
		""" Dump the internal data structures (debug and development use). """

		with self.lock():

			assert ltrace('groups', '| dump()')

			gids = self.groups.keys()
			gids.sort()

			names = self.name_cache.keys()
			names.sort()

			def dump_group(gid):
				return 'groups[%s] (%s) = %s ' % (
					stylize(ST_UGID, gid),
					stylize(ST_NAME, self.groups[gid]['name']),
					str(self.groups[gid]).replace(
					', ', '\n\t').replace('{', '{\n\t').replace('}','\n}'))

			data = '%s:\n%s\n%s:\n%s\n' % (
				stylize(ST_IMPORTANT, 'core.groups'),
				'\n'.join(map(dump_group, gids)),
				stylize(ST_IMPORTANT, 'core.name_cache'),
				'\n'.join(['\t%s: %s' % (key, self.name_cache[key]) \
					for key in names ])
				)

			return data
	def ExportCLI(self, selected=None, long_output=False, no_colors=False):
		""" Export the groups list to human readable (= « get group ») form. """

		with self.lock():
			if selected is None:
				gids = self.groups.keys()
			else:
				gids = selected
			gids.sort()

			assert ltrace('groups', '| ExportCLI(%s)' % gids)

			def ExportOneGroupFromGid(gid, mygroups=self.groups):
				""" Export groups the way UNIX get does, separating with ":" """

				if mygroups[gid]['permissive'] is None:
					group_name = '%s' % stylize(ST_NAME,
						self.groups[gid]['name'])
				elif mygroups[gid]['permissive']:
					group_name = '%s' % stylize(ST_OK,
						self.groups[gid]['name'])
				else:
					group_name = '%s' % stylize(ST_BAD,
						self.groups[gid]['name'])

				accountdata = [
					group_name,
					mygroups[gid]['userPassword'] \
						if mygroups[gid].has_key('userPassword') else '',
					str(gid) ]

				if self.is_system_gid(gid):
					accountdata.extend(
						[
							"",
							",".join(mygroups[gid]['memberUid']),
							mygroups[gid]['description'] \
								if mygroups[gid].has_key('description') else ''
						] )
				else:
					accountdata.extend(
						[
							mygroups[gid]['groupSkel'] \
								if mygroups[gid].has_key('groupSkel') else '',
							",".join(mygroups[gid]['memberUid']),
							mygroups[gid]['description'] \
								if mygroups[gid].has_key('description') else ''
						] )

					if no_colors:
						# if --no-colors is set, we have to display if the group
						# is permissive or not in real words, else user don't get
						# the information because normally it is encoded simply with
						# colors..
						if mygroups[gid]['permissive'] is None:
							accountdata.append("UNKNOWN")
						elif mygroups[gid]['permissive']:
							accountdata.append("permissive")
						else:
							accountdata.append("NOT permissive")

				if long_output:
					accountdata.append('[%s]' % stylize(
						ST_LINK, mygroups[gid]['backend']))

				return ':'.join(accountdata)

			return "\n".join(map(ExportOneGroupFromGid, gids)) + "\n"
	def ExportXML(self, selected=None, long_output=False):
		""" Export the groups list to XML. """

		data = ('''<?xml version='1.0' encoding=\"UTF-8\"?>\n'''
				'''<groups-list>\n''')

		with self.lock():
			if selected is None:
				gids = self.groups.keys()
			else:
				gids = selected
			gids.sort()

			assert ltrace('groups', '| ExportXML(%s)' % gids)

			for gid in gids:
				# TODO: put this into formatted strings.
				group = self.groups[gid]
				data += '''	<group>
			<name>%s</name>
			<gid>%s</gid>%s%s
			<permissive>%s</permissive>\n%s%s%s</group>\n''' % (
				group['name'],
				str(gid),
				'\n		<userPassword>%s</userPassword>' % group['userPassword'] \
					if group.has_key('userPassword') else '',
				'\n		<description>%s</description>' % group['description'] \
					if group.has_key('description') else '',
				'unknown' if group['permissive'] is None \
					else str(group['permissive']),
				'' if self.is_system_gid(gid) \
					else '		<groupSkel>%s</groupSkel>\n' % group['groupSkel'],
				'		<memberUid>%s</memberUid>\n' % \
					','.join(group['memberUid']) if group['memberUid'] != [] \
					else '',
				"		<backend>%s</backend>\n" %  group['backend'] \
					if long_output else ''
				)

			data += "</groups-list>\n"

			return data
	def _validate_fields(self, name, description, groupSkel, listener=None):
		""" apply sane tests on AddGroup needed arguments. """
		if name is None:
			raise exceptions.BadArgumentError("You must specify a group name.")

		if not hlstr.cregex['group_name'].match(name):
			raise exceptions.BadArgumentError(
				"Malformed group name '%s', must match /%s/i." % (name,
				stylize(ST_REGEX, hlstr.regex['group_name'])))

		if len(name) > LMC.configuration.groups.name_maxlenght:
			raise exceptions.LicornRuntimeError('''Group name must be '''
				'''smaller than %d characters.''' % \
					LMC.configuration.groups.name_maxlenght)

		if description is None:
			description = 'members of group “%s”' % name

		elif not hlstr.cregex['description'].match(description):
			raise exceptions.BadArgumentError('''Malformed group description '''
				''''%s', must match /%s/i.'''
				% (description, stylize(
					ST_REGEX, hlstr.regex['description'])))

		if groupSkel is None:
			logging.progress('Using default skel dir %s' %
				LMC.configuration.users.default_skel, listener=listener)
			groupSkel = LMC.configuration.users.default_skel

		elif groupSkel not in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError('''Invalid skel. Valid skels '''
				'''are: %s.''' % LMC.configuration.users.skels)

		return name, description, groupSkel
	def AddGroup(self, name, desired_gid=None, description=None, groupSkel=None,
		system=False, permissive=False, batch=False, force=False,
		listener=None):
		""" Add a Licorn group (the group + the guest/responsible group +
			the shared dir + permissions (ACL)). """

		assert ltrace('groups', '''> AddGroup(name=%s, system=%s, gid=%s, '''
			'''descr=%s, skel=%s, perm=%s)''' % (name, system, desired_gid,
				description, groupSkel, permissive))

		with self.lock():
			name, description, groupSkel = self._validate_fields(name,
				description, groupSkel, listener=listener)

			home = '%s/%s/%s' % (
				LMC.configuration.defaults.home_base_path,
				LMC.configuration.groups.names.plural,
				name)

			# TODO: permit to specify GID.
			# Currently this doesn't seem to be done yet.

			try:
				not_already_exists = True
				gid = self.__add_group(name, system, desired_gid, description,
					groupSkel, batch=batch, force=force, listener=listener)

			except exceptions.AlreadyExistsException, e:
				# don't bork if the group already exists, just continue.
				# some things could be missing (resp- , guest- , shared dir or
				# ACLs), it is a good idea to verify everything is really OK by
				# continuing the creation procedure.
				logging.notice(str(e), listener=listener)
				gid = self.name_to_gid(name)
				not_already_exists = False

		# LOCKS: can be released, because everything after now is FS operations,
		# not needing the internal data structures. It can fail if someone
		# delete a group during the CheckGroups() phase (a little later in this
		# method), but this will be harmless.

		if system:
			if not_already_exists:
				logging.info('Created system group %s (gid=%s).' % (
					stylize(ST_NAME, name),
					stylize(ST_UGID, gid)), listener=listener)

			# system groups don't have shared group dir nor resp-
			# nor guest- nor special ACLs. We stop here.
			assert ltrace('groups', '< AddGroup(name=%s,gid=%d)' % (name, gid))
			return gid, name

		self.groups[gid]['permissive'] = permissive

		try:
			self.CheckGroups([ gid ], minimal=True, batch=True, force=force,
				listener=listener)

			if not_already_exists:
				logging.info('Created %s group %s (gid=%s).' % (
					stylize(ST_OK, 'permissive')
						if self.groups[gid]['permissive'] else
							stylize(ST_BAD, 'not permissive'),
					stylize(ST_NAME, name),
					stylize(ST_UGID, gid)), listener=listener)

		except exceptions.SystemCommandError, e:
			logging.warning("ROLLBACK of group creation: " + str(e),
				listener=listener)

			import shutil
			shutil.rmtree(home)

			try:
				self.__delete_group(name)
			except:
				pass
			try:
				self.__delete_group('%s%s' % (
					LMC.configuration.groups.resp_prefix, name),
					listener=listener)
			except:
				pass
			try:
				self.__delete_group('%s%s' % (
					LMC.configuration.groups.guest_prefix, name),
					listener=listener)
			except:
				pass

			# re-raise, for the calling process to know what happened…
			raise e

		assert ltrace('groups', '< AddGroup(%s): gid %d' % (name, gid))
		if not_already_exists and self.inotifier:
			self.inotifier.add_group_watch(gid)
		return gid, name
	def __add_group(self, name, system, manual_gid=None, description=None,
		groupSkel = "", batch=False, force=False, listener=None):
		""" Add a POSIX group, write the system data files.
			Return the gid of the group created. """

		# LOCKS: No need to use self.lock(), already encapsulated in AddGroup().

		assert ltrace('groups', '''> __add_group(name=%s, system=%s, gid=%s, '''
			'''descr=%s, skel=%s)''' % (name, system, manual_gid, description,
				groupSkel)
			)

		# first verify if GID is not already taken.
		if self.groups.has_key(manual_gid):
			raise exceptions.AlreadyExistsError('''The GID you want (%s) '''
				'''is already taken by another group (%s). Please choose '''
				'''another one.''' % (
					stylize(ST_UGID, manual_gid),
					stylize(ST_NAME,
						self.groups[manual_gid]['name'])))

		# Then verify if the name is not taken too.
		# don't use name_to_gid() else the exception is not KeyError.
		try:
			existing_gid = self.name_cache[name]

			if manual_gid is None:
				# automatic GID selection upon creation.
				if system and self.is_system_gid(existing_gid) \
					or not system and self.is_standard_gid(existing_gid):
					raise exceptions.AlreadyExistsException(
						"The group %s already exists." %
						stylize(ST_NAME, name))
				else:
					raise exceptions.AlreadyExistsError(
						'''The group %s already exists but has not the same '''
						'''type. Please choose another name for your group.'''
						% stylize(ST_NAME, name))
			else:
				assert ltrace('groups', 'manual GID %d specified.' % manual_gid)

				# user has manually specified a GID to affect upon creation.
				if system and self.is_system_gid(existing_gid):
					if existing_gid == manual_gid:
						raise exceptions.AlreadyExistsException(
							"The group %s already exists." %
							stylize(ST_NAME, name))
					else:
						raise exceptions.AlreadyExistsError(
							'''The group %s already exists with a different '''
							'''GID. Please check.''' %
							stylize(ST_NAME, name))
				else:
					raise exceptions.AlreadyExistsError(
						'''The group %s already exists but has not the same '''
						'''type. Please choose another name for your group.'''
						% stylize(ST_NAME, name))
		except KeyError:
			# name doesn't exist, path is clear.
			pass

		# Due to a bug of adduser perl script, we must check that there is
		# no user which has 'name' as login. For details, see
		# https://launchpad.net/distros/ubuntu/+source/adduser/+bug/45970
		if LMC.users.login_cache.has_key(name) and not force:
			raise exceptions.UpstreamBugException('''A user account called '''
				'''%s already exists, this could trigger a bug in the Ubuntu '''
				'''adduser code when deleting the user. Please choose '''
				'''another name for your group, or use --force argument if '''
				'''you really want to add this group on the system.'''
				% stylize(ST_NAME, name))

		# Find a new GID
		if manual_gid is None:
			if system:
				gid = pyutils.next_free(self.groups.keys(),
					LMC.configuration.groups.system_gid_min,
					LMC.configuration.groups.system_gid_max)
			else:
				gid = pyutils.next_free(self.groups.keys(),
					LMC.configuration.groups.gid_min,
					LMC.configuration.groups.gid_max)

			logging.progress('Autogenerated GID for group %s: %s.' % (
				stylize(ST_LOGIN, name),
				stylize(ST_UGID, gid)), listener=listener)
		else:
			if (system and self.is_system_gid(manual_gid)) \
				or (not system and self.is_standard_gid(
					manual_gid)):
					gid = manual_gid
			else:
				raise exceptions.BadArgumentError('''GID out of range '''
					'''for the kind of group you specified. System GID '''
					'''must be between %d and %d, standard GID must be '''
					'''between %d and %d.''' % (
						LMC.configuration.groups.system_gid_min,
						LMC.configuration.groups.system_gid_max,
						LMC.configuration.groups.gid_min,
						LMC.configuration.groups.gid_max)
					)

		# Add group in groups dictionary
		temp_group_dict = {
			'name'        : name,
			'gidNumber'   : gid,
			'userPassword': 'x',
			'memberUid'   : [],
			'description' : description,
			'groupSkel'   : groupSkel,
			'backend'     : self._prefered_backend_name,
			}

		if system:
			# we must fill the permissive status here, else WriteConf() will
			# fail with a KeyError. If not system, this has already been filled.
			temp_group_dict['permissive'] = False
			# no skel for a system group
			temp_group_dict['groupSkel'] = ''

		assert ltrace('groups', '  __add_group in data structures: %s / %s' % (
			gid, name))
		self.groups[gid]      = temp_group_dict
		self.name_cache[name] = gid

		# do not skip the write/save part, else future actions could fail. E.g.
		# when creating a group, skipping save() on rsp/gst group creation will
		# result in unaplicable ACLs because of (yet) non-existing groups in the
		# system files (or backends).
		# DO NOT UNCOMMENT: -- if not batch:
		LMC.backends[
			self.groups[gid]['backend']
			].save_Group(gid, backend_actions.CREATE)

		assert ltrace('groups', '< __add_group(%s): gid %d.'% (name, gid))

		return gid
	def DeleteGroup(self, name=None, gid=None, del_users=False,
		no_archive=False, batch=False, check_profiles=True, listener=None):
		""" Delete an Licorn® group. """

		assert ltrace('groups', '''> DeleteGroup(gid=%s, name=%s, '''
			'''del_users=%s, no_archive=%s, batch=%s, check_profiles=%s)''' % (
			gid, name, del_users, no_archive, batch, check_profiles))

		gid, name = self.resolve_gid_or_name(gid, name)

		assert ltrace('groups', '  DeleteGroup(%s,%s)' % (name, gid))

		# lock everything we *eventually* need, to be sure there are no errors.
		with self.lock():
			with LMC.users.lock():
				with LMC.privileges.lock():
					prim_memb = self.primary_members(gid=gid)

					if prim_memb != [] and not del_users:
						raise exceptions.BadArgumentError('''The group still has '''
							'''members. You must delete them first, or force their '''
							'''automatic deletion with the --del-users option. WARNING: '''
							'''this is a bad idea, use with caution.''')

					if check_profiles and name in LMC.profiles.keys():
						raise exceptions.BadArgumentError('''can't delete group %s, '''
						'''currently associated with profile %s. Please delete the '''
						'''profile, and the group will be deleted too.''' % (
							stylize(ST_NAME, name),
							stylize(ST_NAME,
								LMC.profiles.group_to_name(name))))

					home = '%s/%s/%s' % (
						LMC.configuration.defaults.home_base_path,
						LMC.configuration.groups.names.plural,
						name)

					# Delete the group and its (primary) member(s) even if it is not empty
					if del_users:
						for login in prim_memb:
							LMC.users.DeleteUser(login=login, no_archive=no_archive,
								batch=batch, listener=listener)

					if self.is_system_gid(gid):
						# wipe the group from the privileges if present there.
						if name in LMC.privileges:
							LMC.privileges.delete([name], listener=listener)

						# a system group has no data on disk (no shared directory), just
						# delete its internal data and exit.
						self.__delete_group(name, listener=listener)

						return

					# remove the inotifier watch before deleting the group, else
					# the call will fail, and before archiving group shared
					# data, else it will leave ghost notifies in our gamin
					# daemon, which doesn't need that.
					if self.inotifier:
						self.inotifier.del_group_watch(gid)

					# For a standard group, there are a few steps more :
					# 	- delete the responsible and guest groups,
					#	- then delete the symlinks and the group,
					#	- then the shared data.
					# For responsible and guests symlinks, don't do anything : all symlinks
					# point to <group_name>, not rsp-* / gst-*. No need to duplicate the
					# work.
					self.__delete_group('%s%s' % (
						LMC.configuration.groups.resp_prefix, name),
						listener=listener)
					self.__delete_group('%s%s' % (
						LMC.configuration.groups.guest_prefix, name),
						listener=listener)

					self.CheckGroupSymlinks(gid=gid, name=name, delete=True,
						batch=True, listener=listener)
					self.__delete_group(name, listener=listener)

		# LOCKS: from here, everything is deleted in internal structures, we
		# don't need the locks anymore. The inotifier and the archiving parts
		# can be very long, releasing the locks is good idea.

		# the group information has been wiped out, remove or archive the shared
		# directory. If anything fails now, this is not a real problem, because
		# the system configuration data is safe. At worst, there is an orphaned
		# directory remaining in the arbo, which is harmless.
		if no_archive:
			import shutil
			try:
				shutil.rmtree(home)
			except (IOError, OSError), e:
				if e.errno == 2:
					logging.notice("Can't remove %s, it doesn't exist !" % \
						stylize(ST_PATH, home), listener=listener)
				else:
					raise e
		else:
			# /home/archives must be OK befor moving
			LMC.configuration.check_base_dirs(minimal=True,
				batch=True, listener=listener)

			group_archive_dir = "%s/%s.deleted.%s" % (
				LMC.configuration.home_archive_dir, name,
				strftime("%Y%m%d-%H%M%S", gmtime()))
			try:
				os.rename(home, group_archive_dir)

				logging.info("Archived %s as %s." % (home,
					stylize(ST_PATH, group_archive_dir)),
					listener=listener)

				LMC.configuration.check_archive_dir(
					group_archive_dir, batch=True, listener=listener)
			except OSError, e:
				if e.errno == 2:
					logging.notice("Can't archive %s, it doesn't exist !" % \
						stylize(ST_PATH, home), listener=listener)
				else:
					raise e
	def __delete_group(self, name, listener=None):
		""" Delete a POSIX group."""

		# LOCKS: this method is never called directly, and must always be
		# encapsulated in another, which will acquire self.lock(). This is the
		# case in DeleteGroup().

		assert ltrace('groups', '> __delete_group(%s)' % name)

		try:
			gid = self.name_cache[name]
		except KeyError, e:
			logging.info('''Group %s doesn't exist.''' % stylize(
				ST_NAME, name))
			return

		backend = self.groups[gid]['backend']

		# Remove the group in the groups list of profiles
		LMC.profiles.delete_group_in_profiles(name=name,
			listener=listener)

		# clear the user cache.
		for user in self.groups[gid]['memberUid']:
			try:
				LMC.users[
					LMC.users.login_cache[user]
					]['groups'].remove(name)
			except KeyError:
				logging.warning('skipped non existing user %s' % user)
		try:
			del self.groups[gid]
			del self.name_cache[name]

			LMC.backends[backend].delete_Group(name)

			logging.info(logging.SYSG_DELETED_GROUP % \
				stylize(ST_NAME, name), listener=listener)
		except KeyError:
			logging.warning(logging.SYSG_GROUP_DOESNT_EXIST %
				stylize(ST_NAME, name), listener=listener)

		assert ltrace('groups', '< __delete_group(%s)' % name)
	def RenameGroup(self, name=None, gid=None, new_name=None, listener=None):
		""" Modify the name of a group.

		# FIXME: 1) listener=listener
		# FIXME: 2) with self.lock()
		"""

		raise NotImplementedError(
			"This function is disabled, it is not yet complete.")

		gid, name = self.resolve_gid_or_name(gid, name)

		if new_name is None:
			raise exceptions.BadArgumentError, "You must specify a new name."
		try:
			self.name_to_gid(new_name)

		except exceptions.LicornRuntimeException:
			# new_name is not an existing group

			gid 		= self.name_to_gid(name)
			home		= "%s/%s/%s" % (
				LMC.configuration.defaults.home_base_path,
				LMC.configuration.groups.names.plural,
				self.groups[gid]['name'])
			new_home	= "%s/%s/%s" % (
				LMC.configuration.defaults.home_base_path,
				LMC.configuration.groups.names.plural,
				new_name)

			self.groups[gid]['name'] = new_name

			if not self.is_system_gid(gid):
				tmpname = LMC.configuration.groups.resp_prefix + name
				resp_gid = self.name_to_gid(tmpname)
				self.groups[resp_gid]['name'] = tmpname
				self.name_cache[tmpname] = resp_gid

				tmpname = LMC.configuration.groups.guest_prefix + name
				guest_gid = self.name_to_gid(tmpname)
				self.groups[guest_gid]['name'] = tmpname
				self.name_cache[tmpname] = guest_gid

				del tmpname

				os.rename(home, new_home) # Rename shared dir

				# reapply new ACLs on shared group dir.
				self.CheckGroups( [ gid ], batch=True)

				# delete symlinks to the old name… and create new ones.
				self.CheckGroupSymlinks(gid=gid, oldname=name, batch=True)

			# The name has changed, we have to update profiles
			LMC.profiles.change_group_name_in_profiles(name, new_name)

			# update LMC.users[*]['groups']
			for u in LMC.users:
				try:
					i = LMC.users[u]['groups'].index(name)
				except ValueError:
					 # user u is not in the group which was renamed
					pass
				else:
					LMC.users[u]['groups'][i] = new_name

			LMC.backends[
				self.groups[gid]['backend']
				].save_Group(gid, backend_actions.RENAME)

		#
		# TODO: parse members, and sed -ie ~/.recently_used and other user
		# files… This will not work for OOo files with links to images files
		# (not included in documents), etc.
		#

		else:
			raise exceptions.AlreadyExistsError(
				'''the new name you have choosen, %s, is already taken by '''
				'''another group !''' % \
					stylize(ST_NAME, new_name))
	def ChangeGroupDescription(self, name=None, gid=None, description=None,
		listener=None):
		""" Change the description of a group. #FIXME listener=listener """

		if description is None:
			raise exceptions.BadArgumentError, "You must specify a description"

		with self.lock():
			gid, name = self.resolve_gid_or_name(gid, name)

			self.groups[gid]['description'] = description

			LMC.backends[
				self.groups[gid]['backend']
				].save_Group(gid, backend_actions.UPDATE)

			logging.info('Changed group %s description to "%s".' % (
				stylize(ST_NAME, name),
				stylize(ST_COMMENT, description)
				), listener=listener)
	def ChangeGroupSkel(self, name=None, gid=None, groupSkel=None,
		listener=None):
		""" Change the description of a group. #FIXME listener=listener """

		if groupSkel is None:
			raise exceptions.BadArgumentError, "You must specify a groupSkel"

		if not groupSkel in LMC.configuration.users.skels:
			raise exceptions.DoesntExistsError('''The skel you specified '''
				'''doesn't exist on this system. Valid skels are: %s.''' % \
					str(LMC.configuration.users.skels))

		with self.lock():
			gid, name = self.resolve_gid_or_name(gid, name)

			self.groups[gid]['groupSkel'] = groupSkel

			LMC.backends[
				self.groups[gid]['backend']
				].save_Group(gid, backend_actions.UPDATE)

			logging.info('Changed group %s skel to "%s".' % (
				stylize(ST_NAME, name),
				stylize(ST_COMMENT, groupSkel)
				), listener=listener)
	def AddGrantedProfiles(self, name=None, gid=None, users=None,
		profiles=None, listener=None):
		""" Allow the users of the profiles given to access to the shared dir
			Warning: Don't give [] for profiles, but [""]
		"""

		raise NotImplementedError('to be refreshed.')

		# FIXME: with self.lock()
		gid, name = self.resolve_gid_or_name(gid, name)

		# The profiles exist ? Delete bad profiles
		for p in profiles:
			if p in LMC.profiles:
				# Add the group in groups list of profiles
				if name in LMC.profiles[p]['memberGid']:
					logging.progress(
						"Group %s already in the list of profile %s." % (
						stylize(ST_NAME, name),
						stylize(ST_NAME, p)),
						listener=listener)
				else:
					controllers.profiles.AddGroupsInProfile([name], listener=listener)
					logging.info(
						"Added group %s in the groups list of profile %s." % (
						stylize(ST_NAME, name),
						stylize(ST_NAME, p)),
						listener=listener)
					# Add all 'p''s users in the group 'name'
					_users_to_add = self.__find_group_members(users,
						LMC.profiles[p]['groupName'])
					self.AddUsersInGroup(name, _users_to_add, users,
						listener=listener)
			else:
				logging.warning("Profile %s doesn't exist, ignored." %
					stylize(ST_NAME, p),
					listener=listener)

		# FIXME: is it needed to save() here ? isn't it already done by the
		# profile() and the AddUsersInGroup() calls ?
		LMC.backends[
			self.groups[gid]['backend']
			].save_Group(gid, backend_actions.UPDATE)
	def DeleteGrantedProfiles(self, name=None, gid=None, users=None,
		profiles=None, listener=None):
		""" Disallow the users of the profiles given
			to access to the shared dir. """

		raise NotImplementedError('to be refreshed.')

		# FIXME: with self.lock()
		gid, name = self.resolve_gid_or_name(gid, name)

		# The profiles exist ?
		for p in profiles:
			# Delete the group from groups list of profiles
			if name in controllers.profiles[p]['memberGid']:
				logging.notice("Deleting group '%s' from the profile '%s'." % (
					stylize(ST_NAME, name),
					stylize(ST_NAME, p)),
					listener=listener)
				controllers.profiles.DeleteGroupsFromProfile([name], listener=listener)
				# Delete all 'p''s users from the group 'name'
				_users_to_del = self.__find_group_members(users,
					controllers.profiles[p]['groupName'])
				self.DeleteUsersFromGroup(name, _users_to_del, users,
					listener=listener)
			else:
				logging.info('Group %s already absent from profile %s.' % (
					stylize(ST_NAME, name),
					stylize(ST_NAME, p)),
					listener=listener)

		# FIXME: not already done ??
		self.WriteConf()
	def AddUsersInGroup(self, name=None, gid=None, users_to_add=None,
		batch=False, listener=None):
		""" Add a user list in the group 'name'. """

		assert ltrace('groups', '''> AddUsersInGroup(gid=%s, name=%s, '''
			'''users_to_add=%s, batch=%s)''' % (gid, name, users_to_add, batch))

		if users_to_add is None:
			raise exceptions.BadArgumentError("You must specify a users list")

		# we need to lock users to be sure they don't dissapear during this phase.
		with self.lock():
			with LMC.users.lock():
				gid, name = self.resolve_gid_or_name(gid, name)

				uids_to_add = LMC.users.guess_identifiers(users_to_add,
					listener=listener)

				work_done = False
				u2l = LMC.users.uid_to_login

				for uid in uids_to_add:
					login = u2l(uid)
					if login in self.groups[gid]['memberUid']:
						logging.progress(
							"User %s is already a member of %s, skipped." % (
							stylize(ST_LOGIN, login),
							stylize(ST_NAME, name)),
							listener=listener)
					else:
						self.groups[gid]['memberUid'].append(login)
						self.groups[gid]['memberUid'].sort()
						# update the users cache.
						LMC.users[uid]['groups'].append(name)
						LMC.users[uid]['groups'].sort()
						logging.info("Added user %s to members of %s." % (
							stylize(ST_LOGIN, login),
							stylize(ST_NAME, name)),
							listener=listener)

						if batch:
							work_done = True
						else:
							#
							# save the group after each user addition.
							# this is a quite expansive operation, it seems to me quite
							# superflous, but you can make bets on security and
							# reliability.
							#
							LMC.backends[
								self.groups[gid]['backend']
								].save_Group(gid, backend_actions.UPDATE)

							#self.reload_admins_group_in_validator(name)

						if self.is_standard_gid(gid):
							# create the symlink to the shared group dir
							# in the user's home dir.
							link_basename = self.groups[gid]['name']
						elif name.startswith(
							LMC.configuration.groups.resp_prefix):
							# fix #587: make symlinks for resps and guests too.
							link_basename = \
								self.groups[gid]['name'].replace(
								LMC.configuration.groups.resp_prefix,
								"", 1)
						elif name.startswith(
							LMC.configuration.groups.guest_prefix):
							link_basename = \
								self.groups[gid]['name'].replace(
								LMC.configuration.groups.guest_prefix,
								"", 1)
						else:
							# this is a system group, don't make any symlink !
							continue

						# brutal fix for #43, batched for convenience.
						self.AddUsersInGroup(name='users', users_to_add=[ uid ],
							batch=True, listener=listener)

						link_src = os.path.join(
							LMC.configuration.defaults.home_base_path,
							LMC.configuration.groups.names.plural,
							link_basename)
						link_dst = os.path.join(
							LMC.users[uid]['homeDirectory'],
							link_basename)
						fsapi.make_symlink(link_src, link_dst, batch=batch,
							listener=listener)

				if batch and work_done:
					# save the group after having added all users. This seems more fine
					# than saving between each addition
					LMC.backends[
						self.groups[gid]['backend']
						].save_Group(gid, backend_actions.UPDATE)

					#self.reload_admins_group_in_validator(name)

		assert ltrace('groups', '< AddUsersInGroup()')
	def reload_admins_group_in_validator(self, name):
		""" Reload a LicornPyroValidator class attribute in the CommandListener
			thread, to be sure the foreign list of members of group "admins" is
			up-to-date. This is needed because there are so many calls to the
			validator that """
		# FIXME: this doesn't belong here, but it is the only way to start
		# that I found.
		if name == 'admins':
			# update the list of admins group member in the connection
			# validator of the daemon.
			from licorn.daemon.internals.cmdlistener import LicornPyroValidator
			LicornPyroValidator.reload()
	def DeleteUsersFromGroup(self, name=None, gid=None, users_to_del=None,
		batch=False, listener=None):
		""" Delete a users list in the group 'name'. """

		assert ltrace('groups', '''> DeleteUsersFromGroup(gid=%s, name=%s,
			users_to_del=%s, batch=%s)''' % (gid, name, users_to_del, batch))

		if users_to_del is None:
			raise exceptions.BadArgumentError("You must specify a users list")

		gid, name = self.resolve_gid_or_name(gid, name)

		uids_to_del = LMC.users.guess_identifiers(users_to_del,
			listener=listener)

		logging.progress("Going to remove users %s from group %s." % (
			stylize(ST_NAME, str(uids_to_del)),
			stylize(ST_NAME, name)),
			listener=listener)

		work_done = False
		u2l = LMC.users.uid_to_login

		for uid in uids_to_del:

			login = u2l(uid)
			if login in self.groups[gid]['memberUid']:
				self.groups[gid]['memberUid'].remove(login)

				# update the users cache
				LMC.users[uid]['groups'].remove(name)

				logging.info("Removed user %s from members of %s." % (
					stylize(ST_LOGIN, login),
					stylize(ST_NAME, name)),
					listener=listener)

				if batch:
					work_done = True
				else:
					LMC.backends[
						self.groups[gid]['backend']
						].save_Group(gid, backend_actions.UPDATE)

					#self.reload_admins_group_in_validator(name)

				if not self.is_system_gid(gid):
					# delete the shared group dir symlink in user's home.
					link_src = os.path.join(
						LMC.configuration.defaults.home_base_path,
						LMC.configuration.groups.names.plural,
						self.groups[gid]['name'])

					for link in fsapi.minifind(
						LMC.users[uid]['homeDirectory'],
						maxdepth=2, type=stat.S_IFLNK):
						try:
							if os.path.abspath(os.readlink(link)) == link_src:
								os.unlink(link)
								logging.info("Deleted symlink %s." %
									stylize(ST_LINK, link),
									listener=listener)
						except (IOError, OSError), e:
							if e.errno == 2:
								# this is a broken link, readlink failed…
								pass
							else:
								raise exceptions.LicornRuntimeError(
									"Unable to delete symlink %s (was: %s)." % (
										stylize(ST_LINK, link),
										str(e)))
			else:
				logging.info(
					"User %s is already not a member of %s, skipped." % (
						stylize(ST_LOGIN, login),
						stylize(ST_NAME, name)),
						listener=listener)

		if batch and work_done:
			LMC.backends[
				self.groups[gid]['backend']
				].save_Group(gid, backend_actions.UPDATE)

			#self.reload_admins_group_in_validator(name)

		assert ltrace('groups', '< DeleteUsersFromGroup()')
	def BuildGroupACL(self, gid, path=''):
		""" Return an ACL triolet (a dict) used later to check something
			in the group shared dir.

			NOTE: the "@GE" and "@UE" strings will be later replaced by individual
			execution bits of certain files which must be kept executable.

			NOT locked, because called from methods which already lock.

			gid: the GID for which we are building the ACL.
			path: a unicode string, the name of a file/dir (or subdir) relative
				from group_home (this will help affining the ACL).
				EG: path can be 'toto.odt', 'somedir',
				'public_html/images/logo.img'.
		"""

		group = self.groups[gid]['name']

		if self.groups[gid]['permissive']:
			group_default_acl = "rwx"
			group_file_acl    = "rw@GE"
		else:
			group_default_acl = "r-x"
			group_file_acl    = "r-@GE"

		acl_base      = "u::rwx,g::---,o:---,g:%s:rwx,g:%s:r-x,g:%s:rwx" % (
			LMC.configuration.defaults.admin_group,
			LMC.configuration.groups.guest_prefix + group,
			LMC.configuration.groups.resp_prefix + group)
		file_acl_base = \
			"u::rw@UE,g::---,o:---,g:%s:rw@GE,g:%s:r-@GE,g:%s:rw@GE" % (
			LMC.configuration.defaults.admin_group,
			LMC.configuration.groups.guest_prefix + group,
			LMC.configuration.groups.resp_prefix + group)
		acl_mask      = "m:rwx"
		file_acl_mask = "m:rw@GE"

		if path.find('public_html') == 0:
			return {
					'group'     : 'acl',
					'access_acl': '%s,g:%s:rwx,g:www-data:r-x,%s' % (
						acl_base, group, acl_mask),
					'default_acl': '%s,g:%s:%s,g:www-data:r-x,%s' % (
						acl_base, group, group_default_acl, acl_mask),
					'content_acl': '%s,g:%s:%s,g:www-data:r--,%s' % (
						file_acl_base, group, group_file_acl, file_acl_mask),
					'exclude'   : []
				}
		else:
			return {
					'group'     : 'acl',
					'access_acl': '%s,g:%s:rwx,g:www-data:--x,%s' % (
						acl_base, group, acl_mask),
					'default_acl': '%s,g:%s:%s,%s' % (
						acl_base, group, group_default_acl, acl_mask),
					'content_acl': '%s,g:%s:%s,%s' % (
						file_acl_base, group, group_file_acl, file_acl_mask),
					'exclude'   : [ 'public_html' ]
				}
	def CheckAssociatedSystemGroups(self, name=None, gid=None, minimal=True,
		batch=False, auto_answer=None, force=False, listener=None):
		"""Check the system groups that a standard group needs to be valid.	For
			example, a group "MountainBoard" needs 2 system groups,
			rsp-MountainBoard and gst-MountainBoard for its ACLs on the group
			shared dir.

			NOT locked because called from already locked methods.

			name/gid: the standard group to verify depended upon system groups.
			minimal: if True, only the system groups are checked. Else, symlinks
				in the homes of standard group members and responsibles are also
				checked (can be long, depending on the number of members).
			batch: correct all errors without prompting.
			auto_answer: an eventual pre-typed answer to a preceding question
				asked outside of this method, forwarded to apply same answer to
				all questions.
			force: not used directly in this method, but forwarded to called
				methods which can use it.
			listener: the pyro client to send messages to.
		"""

		gid, name = self.resolve_gid_or_name(gid, name)

		all_went_ok = True

		with self.lock():
			for (prefix, title) in (
				(LMC.configuration.groups.resp_prefix, "responsibles"),
				(LMC.configuration.groups.guest_prefix, "guests")
				):

				group_name = prefix + name
				logging.progress("Checking system group %s…" %
					stylize(ST_NAME, group_name),
					listener=listener)

				try:
					# FIXME: (convert this into an LicornKeyError ?) and use
					# name_to_gid() inside of direct cache access.
					prefix_gid = self.name_cache[group_name]

				except KeyError:
					warn_message = logging.SYSG_SYSTEM_GROUP_REQUIRED % (
						stylize(ST_NAME, group_name),
						stylize(ST_NAME, name))

					if batch or logging.ask_for_repair(warn_message,
						auto_answer, listener=listener):
						try:
							temp_gid = self.__add_group(group_name,
								system=True, manual_gid=None,
								description="%s of group “%s”" % (title, name),
								groupSkel="", batch=batch, force=force)
							prefix_gid = temp_gid
							del temp_gid

							logging.info("Created system group %s (gid=%s)." %
								(stylize(ST_NAME, group_name),
								stylize(ST_UGID, prefix_gid)),
								listener=listener)
						except exceptions.AlreadyExistsException, e:
							logging.notice(str(e), listener=listener)
							pass
					else:
						logging.warning(warn_message, listener=listener)
						all_went_ok &= False

			# WARNING: don't even try to remove() group_name from the list of
			# groups_to_check. This will not behave as expected because
			# groups_to_check is used with map() and not a standard for() loop.
			# This will skip some groups, which will not be checked !! BAD !


			# LOCKS: the following part can be very long and blocking for the
			# rest of the world. we do it ouside locks, and damn'it it it fails,
			# I consider it harmless.

			if not minimal:
				all_went_ok &= self.CheckGroupSymlinks(gid=prefix_gid,
					strip_prefix=prefix, batch=batch, auto_answer=auto_answer,
					listener=listener)

		return all_went_ok
	def __check_group(self, gid=None, name=None, minimal=True, batch=False,
		auto_answer=None, force=False, listener=None):
		""" Check a group (the real implementation, private: don't call directly
			but use CheckGroups() instead). Will verify the various needed
			conditions for a Licorn® group to be valid, and then check all
			entries in the shared group directory.

			PARTIALLY locked, because very long to run (depending on the shared
			group dir size). Harmless if the unlocked part fails.

			gid/name: the group to check.
			minimal: don't check member's symlinks to shared group dir if True
			batch: correct all errors without prompting.
			auto_answer: an eventual pre-typed answer to a preceding question
				asked outside of this method, forwarded to apply same answer to
				all questions.
			force: not used directly in this method, but forwarded to called
				methods which can use it.
			listener: the pyro client to send messages to.
		"""

		assert ltrace('groups', '> __check_group(gid=%s,name=%s)' % (
			stylize(ST_UGID, gid),
			stylize(ST_NAME, name)))

		with self.lock():
			gid, name = self.resolve_gid_or_name(gid, name)

			all_went_ok = True

			if self.is_system_gid(gid):
				return True

			logging.progress("Checking group %s…" %
				stylize(ST_NAME, name), listener=listener)

			all_went_ok &= self.CheckAssociatedSystemGroups(
				name=name, minimal=minimal, batch=batch,
				auto_answer=auto_answer, force=force, listener=listener)

			group_home_acl = self.BuildGroupACL(gid)

		group_home = "%s/%s/%s" % (
			LMC.configuration.defaults.home_base_path,
			LMC.configuration.groups.names.plural, name)
		group_home_acl['path'] = group_home

		if os.path.exists("%s/public_html" % group_home):
			group_home_acl['exclude'] = [ 'public_html' ]

		# follow the symlink for the group home, only if link destination is a
		# dir. This allows administrator to put big group dirs on different
		# volumes (fixes #66).

		if os.path.islink(group_home):
			if os.path.exists(group_home) \
				and os.path.isdir(os.path.realpath(group_home)):
				group_home = os.path.realpath(group_home)
				group_home_acl['path']  = group_home

		# check only the group home dir (not its contents), its uid/gid and its
		# (default) ACL. To check a dir without its content, just delete the
		# content_acl or content_mode dictionnary key.

		try:
			logging.progress("Checking shared group dir %s…" %
				stylize(ST_PATH, group_home), listener=listener)
			group_home_only         = group_home_acl.copy()
			group_home_only['path'] = group_home
			group_home_only['user'] = 'root'
			del group_home_only['content_acl']
			all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
				[ group_home_only ], batch, auto_answer, self, LMC.users,
				listener=listener)

		except exceptions.LicornCheckError:
			logging.warning(
				"Shared group dir %s is missing, please repair this first." %
				stylize(ST_PATH, group_home), listener=listener)
			return False

		# check the contents of the group home dir, without checking UID (fix
		# old #520. This is necessary for non-permissive groups to be
		# functionnal). this will recheck the home dir, but this 2nd check does
		# less than the previous. The previous is necessary, and this one is
		# unavoidable due to fsapi.check_dirs_and_contents_perms_and_acls()
		# conception.
		logging.progress("Checking shared group dir contents…",
			listener=listener)
		all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
			[ group_home_acl ], batch, auto_answer, self, LMC.users,
			listener=listener)

		if os.path.exists("%s/public_html" % group_home):
			public_html             = "%s/public_html" % group_home
			public_html_acl         = self.BuildGroupACL(gid, 'public_html')
			public_html_acl['path'] =  public_html

			try:
				logging.progress("Checking shared dir %s…" % \
					stylize(ST_PATH, public_html),
					listener=listener)
				public_html_only         = public_html_acl.copy()
				public_html_only['path'] = public_html
				public_html_only['user'] = 'root'
				del public_html_only['content_acl']
				all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
					[ public_html_only ],
					batch, auto_answer, self, LMC.users, listener=listener)

			except exceptions.LicornCheckError:
				logging.warning(
					"Shared dir %s is missing, please repair this first." \
					% stylize(ST_PATH, public_html),
					listener=listener)
				return False

			# check only ~group/public_html and its contents, without checking
			# the UID, too.
			all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls(
				[ public_html_acl ], batch, auto_answer, self, LMC.users,
				listener=listener)

		if not minimal:
			logging.progress(
				"Checking %s symlinks in members homes, this can be long…"  %
					stylize(ST_NAME, name), listener=listener)
			all_went_ok &= self.CheckGroupSymlinks(gid=gid, batch=batch,
				auto_answer=auto_answer, listener=listener)

			# TODO: if extended / not minimal: all group members' homes are OK
			# (recursive CheckUsers recursif)
			# WARNING: be carefull of recursive multicalls, when calling
			# CheckGroups, which calls CheckUsers, which could call
			# CheckGroups()… use minimal=True as argument here, don't forward
			# the current "minimal" value.

		assert ltrace('groups', '< __check_group(%s)' % all_went_ok)

		return all_went_ok
	def check_nonexisting_users(self, batch=False, auto_answer=None,
		listener=None):
		""" Go through all groups, find members which are referenced but
			don't really exist on the system, and wipe them.

			LOCKED to be thread-safe for groups and users.

			batch: correct all errors without prompting.
			auto_answer: an eventual pre-typed answer to a preceding question
				asked outside of this method, forwarded to apply same answer to
				all questions.
			listener: the pyro client to send messages to.
		"""

		assert ltrace('groups', '> check_nonexisting_users(batch=%s)' % batch)

		with self.lock():
			with LMC.users.lock():
				for gid in self.groups:
					to_remove = set()

					logging.progress('''Checking for dangling references in group %s.'''
						% stylize(ST_NAME,
							self.groups[gid]['name']),
						listener=listener)

					for member in self.groups[gid]['memberUid']:
						if not LMC.users.login_cache.has_key(member):
							if batch or logging.ask_for_repair('''User %s is '''
								'''referenced in members of group %s but doesn't '''
								'''really exist on the system. Remove this dangling '''
								'''reference?''' % \
									(stylize(ST_BAD, member),
									stylize(ST_NAME,
										self.groups[gid]['name'])),
								auto_answer=auto_answer, listener=listener):
								# don't directly remove member from members,
								# it will immediately stop the for_loop. Instead, note
								# the reference to remove, to do it a bit later.
								logging.info('''Removed dangling reference to '''
									'''non-existing user %s in group %s.''' % (
									stylize(ST_BAD, member),
									stylize(ST_NAME,
										self.groups[gid]['name'])),
									listener=listener)
								to_remove.add(member)

					if to_remove != set():
						for member in to_remove:
							self.groups[gid]['memberUid'].remove(member)
							self.WriteConf(gid)

		assert ltrace('groups', '< check_nonexisting_users()')
	def CheckGroups(self, gids_to_check, minimal=True, batch=False,
		auto_answer=None, force=False, listener=None):
		""" Check groups, groups dependancies and groups-related caches. If a
			given group is not system, check it's shared dir, the depended upon
			system groups, and eventually the members symlinks.

			NOT locked because subparts are, where needed.

			gids_to_check: a list of GIDs to check. If you don't have GIDs but
				group names, use name_to_gid() before.
			minimal: don't check group symlinks in member's homes if True.
			batch: correct all errors without prompting.
			auto_answer: an eventual pre-typed answer to a preceding question
				asked outside of this method, forwarded to apply same answer to
				all questions.
			force: not used directly in this method, but forwarded to called
				methods which can use it.
			listener: the pyro client to send messages to.
		"""

		assert ltrace('groups', '''> CheckGroups(gids_to_check=%s, minimal=%s, '''
			'''batch=%s, force=%s)''' %	(gids_to_check, minimal, batch, force))

		if not minimal:
			self.check_nonexisting_users(batch=batch, auto_answer=auto_answer,
				listener=listener)

		# dependancy: base dirs must be OK before checking groups shared dirs.
		LMC.configuration.check_base_dirs(minimal=minimal, batch=batch,
			auto_answer=auto_answer, listener=listener)

		def _chk(gid):
			assert ltrace('groups', '| CheckGroups._chk(%s)' % gid)
			return self.__check_group(gid=gid, minimal=minimal, batch=batch,
				auto_answer=auto_answer, force=force, listener=listener)

		if reduce(pyutils.keep_false, map(_chk, gids_to_check)) is False:
			# don't test just "if reduce(…):", the result could be None and
			# everything is OK when None
			raise exceptions.LicornCheckError(
				"Some group(s) check(s) didn't pass, or weren't corrected.")

		assert ltrace('groups', '< CheckGroups()')
	def CheckGroupSymlinks(self, name=None, gid=None, oldname=None,
		delete=False, strip_prefix=None, batch=False, auto_answer=None,
		listener=None):
		""" For each member of a group, verify member has a symlink to the
			shared group dir inside his home (or under level 2 directory). If
			not, create the link. Eventually delete links pointing to the old
			group name if it is set.

			NOT locked because can be long, and harmless if fails.
		"""

		gid, name = self.resolve_gid_or_name(gid, name)

		all_went_ok = True

		for user in self.groups[gid]['memberUid']:

			try:
				uid = LMC.users.login_to_uid(user)
			except exceptions.DoesntExistsException:
				logging.notice('Skipped non existing group member %s.' %
					stylize(ST_NAME, user), listener=listener)
				continue

			link_not_found = True

			if strip_prefix is None:
				link_basename = name
			else:
				link_basename = \
					name.replace(strip_prefix,
						'', 1)

			link_src = os.path.join(
				LMC.configuration.defaults.home_base_path,
				LMC.configuration.groups.names.plural,
				link_basename)

			link_dst = os.path.join(
				LMC.users[uid]['homeDirectory'],
				link_basename)

			if oldname:
				link_src_old = os.path.join(
					LMC.configuration.defaults.home_base_path,
					LMC.configuration.groups.names.plural,
					oldname)
			else:
				link_src_old = None

			for link in fsapi.minifind(
				LMC.users[uid]['homeDirectory'], maxdepth=2,
					type=stat.S_IFLNK):
				try:
					link_src_abs = os.path.abspath(os.readlink(link))
					if link_src_abs == link_src:
						if delete:
							try:
								os.unlink(link)
								logging.info("Deleted symlink %s." %
									stylize(ST_LINK, link),
									listener=listener)
							except (IOError, OSError), e:
								if e.errno != 2:
									raise exceptions.LicornRuntimeError(
									"Unable to delete symlink %s (was: %s)." % (
									stylize(ST_LINK, link),
									str(e)))
						else:
							link_not_found = False
				except (IOError, OSError), e:
					# TODO: verify there's no bug in this logic ? pida
					# signaled an error I didn't previously notice.
					# if e.errno == 2 and link_src_old and \
					# link_dst_old == os.readlink(link):
					if e.errno == 2 and link_src_old \
						and link_src_old == os.readlink(link):
						# delete links to old group name.
						os.unlink(link)
						logging.info("Deleted old symlink %s." %
							stylize(ST_LINK, link),
							listener=listener)
					else:
						# errno == 2 is a broken link, don't bother.
						raise exceptions.LicornRuntimeError(
							"Unable to read symlink %s (error was: %s)." % (
								link, str(e)))

			if link_not_found and not delete:
				warn_message = logging.SYSG_USER_LACKS_SYMLINK % (
					stylize(ST_LOGIN, user),
					stylize(ST_NAME, link_basename))

				if batch or logging.ask_for_repair(warn_message, auto_answer,
					listener=listener):
					fsapi.make_symlink(link_src, link_dst, batch=batch,
						auto_answer=auto_answer, listener=listener)
				else:
					logging.warning(warn_message, listener=listener)
					all_went_ok = False

		return all_went_ok
	def SetSharedDirPermissiveness(self, gid=None, name=None, permissive=True,
		listener=None):
		""" Set permissive or not permissive the shared directory of
			the group 'name'.

			LOCKED because we assume we don't want a group to be deleted /
			modified during this operation, which is very quick.
		"""

		assert ltrace('groups', '''> SetSharedDirPermissivenes(gid=%s, name=%s, '''
			'''permissive=%s)''' % (gid, name, permissive))

		with self.lock():
			gid, name = self.resolve_gid_or_name(gid, name)

			if permissive:
				qualif = ''
			else:
				qualif = 'not '

			logging.progress('''Setting permissive=%s for group %s ('''
				'''original is %s).''' % (
				stylize(ST_OK if permissive else ST_BAD, permissive),
				stylize(ST_NAME, name),
				stylize(ST_OK if self.groups[gid]['permissive'] else ST_BAD,
					self.groups[gid]['permissive'])),
				listener=listener)

			if self.groups[gid]['permissive'] != permissive:
				self.groups[gid]['permissive'] = permissive

				# auto-apply the new permissiveness
				self.CheckGroups([ gid ], batch=True, listener=listener)
				logging.info('Changed group %s permissive state to %s.' % (
					stylize(ST_NAME, name),
					stylize(ST_OK if permissive else ST_BAD, permissive)
				), listener=listener)
			else:
				logging.info('Group %s is already %spermissive.' % (
					stylize(ST_NAME, name), qualif),
					listener=listener)
	def is_permissive(self, gid, name, listener=None):
		""" Return True if the shared dir of the group is permissive.

			This method MUST be called with the 2 arguments GID and name.

			WARNING: don't use self.resolve_gid_or_name() here. This method is
			used very early, from the GroupsController.__init__(), when groups
			are in the process of beiing loaded. The resolve*() calls will fail.

			LOCKED because very important.

			gid and name are mandatory, this function won't resolve them.
			listener: the pyro client to send messages to.
		"""

		with self.lock():
			if self.is_system_gid(gid):
				return None

			home = '%s/%s/%s' % (
				LMC.configuration.defaults.home_base_path,
				LMC.configuration.groups.names.plural,
				name)

			try:
				# only check default ACLs, which is what we need for
				# testing permissiveness.
				for line in posix1e.ACL(filedef=home):
					if line.tag_type & posix1e.ACL_GROUP:
						if line.qualifier == gid:
							return line.permset.write
			except IOError, e:
				if e.errno == 13:
					raise exceptions.InsufficientPermissionsError(str(e))
				elif e.errno == 2:
					if self.warnings:
						logging.warning('''Shared dir %s doesn't exist, please '''
							'''run "licorn-check group --name %s" to fix.''' % (
								stylize(ST_PATH, home),
								stylize(ST_NAME, name)), once=True,
								listener=listener)
				else:
					raise exceptions.LicornIOError("IO error on %s (was: %s)." %
						(home, e))
			except ImportError, e:
				logging.warning(logging.MODULE_POSIX1E_IMPORT_ERROR % e, once=True,
				listener=listener)
				return None

	# LOCKS: subsequent methods are not locked because vey fast and read-only.
	# We assume that calling methods already lock the data structures, to avoid
	# many acquire()/release() cycles which could slow down the operations.
	def confirm_gid(self, gid):
		""" verify a GID or raise DoesntExists. """
		try:
			return self.groups[gid]['gidNumber']
		except KeyError:
			try:
				# try to int(), in case this is a call from cli_select(), which
				# gets only strings.
				return self.groups[int(gid)]['gidNumber']
			except ValueError:
				raise exceptions.DoesntExistsException(
					"GID %s doesn't exist" % gid)
	def resolve_gid_or_name(self, gid, name):
		""" method used every where to get gid / name of a group object to
			do something onto. a non existing gid / name will raise an
			exception from the gid_to_name() / name_to_gid() methods."""

		if name is None and gid is None:
			raise exceptions.BadArgumentError(
				"You must specify a name or GID to resolve from.")

		assert ltrace('groups', '| resolve_gid_or_name(gid=%s, name=%s)' % (gid, name))

		# we cannot just test "if gid:" because with root(0) this doesn't work.
		if gid is not None:
			name = self.gid_to_name(gid)
		else:
			gid = self.name_to_gid(name)
		return (gid, name)
	def guess_identifier(self, value):
		""" Try to guess everything of a group from a
			single and unknonw-typed info. """
		try:
			gid = int(value)
			self.gid_to_name(gid)
			assert ltrace('groups', '| guess_identifier: int(%s) -> %s' % (
				value, gid))
		except ValueError, e:
			gid = self.name_to_gid(value)
			assert ltrace('groups', '| guess_identifier: name_to_gid(%s) -> %s'
				% (value, gid))

		return gid
	def guess_identifiers(self, value_list, listener=None):
		""" return a list of valid and existing GIDs, given a list of 'things'
		 to validate existence of (can be GIDs or names). """
		valid_ids=set()
		for value in value_list:
			try:
				valid_ids.add(self.guess_identifier(value))
			except exceptions.DoesntExistsException:
				logging.notice("Skipped non-existing group name or GID '%s'." %
					stylize(ST_NAME,value), listener=listener)
		return list(valid_ids)
	def exists(self, name=None, gid=None):
		"""Return true if the group or gid exists on the system. """

		assert ltrace('groups', '|  exists(name=%s, gid=%s)' % (name, gid))

		if name:
			return self.name_cache.has_key(name)

		if gid:
			return self.groups.has_key(gid)

		raise exceptions.BadArgumentError(
			"You must specify a GID or a name to test existence of.")
	def primary_members(self, gid=None, name=None):
		"""Get the list of users which are in group 'name'."""
		ru = []

		gid, name = self.resolve_gid_or_name(gid, name)

		for u in LMC.users.keys():
			if LMC.users[u]['gidNumber'] == gid:
				ru.append(LMC.users[u]['login'])
		return ru
	def auxilliary_members(self, gid=None, name=None):
		""" Return all members of a group, which are not members of this group
			in their primary group."""

		# TODO: really verify, for each user, that their member ship is not
		# duplicated between primary and auxilliary groups.

		gid, name = self.resolve_gid_or_name(gid, name)

		return self.groups[gid]['memberUid']
	def all_members(self, gid=None, name=None):
		"""Return all members of a given group name."""

		gid, name = self.resolve_gid_or_name(gid, name)

		member_list = self.primary_members(gid=gid)
		member_list.extend(self.auxilliary_members(gid=gid))
		return member_list
	def gid_to_name(self, gid):
		""" Return the group name for a given GID."""
		try:
			return self.groups[gid]['name']
		except KeyError:
			raise exceptions.DoesntExistsException(
				"GID %s doesn't exist" % gid)
	def name_to_gid(self, name):
		""" Return the gid of the group 'name'."""
		try:
			assert ltrace('groups', '| name_to_gid(%s) -> %s' % (
				name, self.name_cache[name]))
			# use the cache, Luke !
			return self.name_cache[name]
		except KeyError:
			raise exceptions.DoesntExistsException(
				"Group %s doesn't exist" % name)
	def is_system_gid(self, gid):
		""" Return true if gid is system. """
		return gid < LMC.configuration.groups.gid_min \
			or gid > LMC.configuration.groups.gid_max
	def is_standard_gid(self, gid):
		""" Return true if gid is standard (not system). """
		return gid >= LMC.configuration.groups.gid_min \
			and gid <= LMC.configuration.groups.gid_max
	def is_system_group(self, name):
		""" Return true if group is system. """
		try:
			return self.is_system_gid(
				self.name_to_gid(name))
		except KeyError:
			raise exceptions.DoesntExistsException(
				"The group '%s' doesn't exist." % name)
	def is_standard_group(self, name):
		""" Return true if group is standard (not system). """
		try:
			return self.is_standard_gid(
				self.name_to_gid(name))
		except KeyError:
			raise exceptions.DoesntExistsException(
				"The group '%s' doesn't exist." % name)
	def is_privilege(self, name=None, gid=None):
		""" return True if a given GID or group name is recorded as a privilege,
			else False, or raise an error if called without any argument."""

		if name:
			return name in LMC.privileges
		if gid:
			return self.groups[gid]['name'] in LMC.privileges

		raise exceptions.BadArgumentError(
			"You must specify a GID or name to test as a privilege.")
	def is_restricted_system_gid(self, gid):
		""" Return true if gid is system, but outside the range of Licorn®
			controlled GIDs."""
		return gid < LMC.configuration.groups.system_gid_min \
			and gid > LMC.configuration.groups.gid_max
	def is_restricted_system_name(self, group_name):
		""" return true if login is system, but outside the range of Licorn®
			controlled UIDs. """
		try:
			return self.is_restricted_system_gid(
				self.name_cache[group_name])
		except KeyError:
			raise exceptions.DoesntExistsException(
				logging.SYSG_GROUP_DOESNT_EXIST % group_name)
	def is_unrestricted_system_gid(self, gid):
		""" Return true if gid is system, but outside the range of Licorn®
			controlled GIDs."""
		return gid > LMC.configuration.groups.system_gid_min \
			and gid < LMC.configuration.groups.gid_max
	def is_unrestricted_system_name(self, group_name):
		""" return true if login is system, but outside the range of Licorn®
			controlled UIDs. """
		try:
			return self.is_unrestricted_system_gid(
				self.name_cache[group_name])
		except KeyError:
			raise exceptions.DoesntExistsException(
				logging.SYSG_GROUP_DOESNT_EXIST % group_name)
	def is_empty_gid(self, gid):
		""" return True if GID is empty (has no members) """
		return self.is_standard_gid(gid) \
			and self.groups[gid]['memberUid'] == []
	def is_empty_group(self, name):
		""" return True if group is empty (has no members) """
		return self.is_empty_gid(
			self.name_to_gid(name))
	def make_name(self, inputname=None):
		""" Make a valid login from  user's firstname and lastname."""

		maxlenght = LMC.configuration.groups.name_maxlenght
		groupname = inputname

		groupname = hlstr.validate_name(groupname, maxlenght = maxlenght)

		if not hlstr.cregex['group_name'].match(groupname):
			raise exceptions.BadArgumentError(
				'''Can't build a valid UNIX group name (got %s, '''
				'''which doesn't verify %s) with the string you '''
				'''provided "%s".''' % (
					groupname, hlstr.regex['group_name'], inputname) )

		# TODO: verify if the group doesn't already exist.
		#while potential in UsersController.users:
		return groupname
