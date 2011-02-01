# -*- coding: utf-8 -*-
"""
Licorn core: groups - http://docs.licorn.org/core/groups.html

:copyright:
	* 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	* partial 2010 Robin Lucbernet <robinlucbernet@gmail.com>
	* partial 2006 Régis Cobrun <reg53fr@yahoo.fr>

:license: GNU GPL version 2

"""

import os, stat, posix1e, re, time

from licorn.foundations           import logging, exceptions
from licorn.foundations           import fsapi, pyutils, hlstr
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import Singleton,Enumeration
from licorn.foundations.constants import filters, backend_actions

from licorn.core         import LMC
from licorn.core.classes import CoreFSController

class GroupsController(Singleton, CoreFSController):
	""" Manages the groups and the associated shared data on a Linux system.
	"""

	init_ok = False
	load_ok = False

	def __init__ (self, warnings=True):

		assert ltrace('groups', '> GroupsController.__init__(%s)' %
			GroupsController.init_ok)

		if GroupsController.init_ok:
			return
		CoreFSController.__init__(self, 'groups')
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

				for backend in self.backends:
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
				for backend in self.backends:
					backend.save_Groups()

		assert ltrace('groups', '< WriteConf()')
	def Select(self, filter_string):
		""" Filter group accounts on different criteria.
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

				elif filters.NOT_GUEST == filter_string:
					assert ltrace('groups', '> Select(GST:%s/%s)' % (
						filters.NOT_GST, filter_string))
					for gid in self.groups.keys():
						if not self.groups[gid]['name'].startswith(
							LMC.configuration.groups.guest_prefix):
							filtered_groups.append(gid)

				elif filters.SYSTEM_RESTRICTED == filter_string:
					assert ltrace('groups', '> Select(SYSTEM_RESTRICTED:%s/%s)' % (
						filters.SYSTEM_RESTRICTED, filter_string))

					filtered_groups.extend(filter(self.is_restricted_system_gid,
						self.groups.keys()))

				elif filters.SYSTEM_UNRESTRICTED == filter_string:
					assert ltrace('groups', '> Select(SYSTEM_UNRESTRICTED:%s/%s)' % (
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

				elif filters.NOT_RESPONSIBLE == filter_string:
					assert ltrace('groups', '> Select(RSP:%s/%s)' % (
						filters.NOT_RSP, filter_string))

					for gid in self.groups.keys():
						if not self.groups[gid]['name'].startswith(
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

				elif filters.NOT_PRIVILEGED == filter_string:
					assert ltrace('groups', '> Select(PRI:%s/%s)' % (
						filters.NOT_PRI, filter_string))
					for gid in self.groups.keys():
						if self.groups[gid]['name'] not in LMC.privileges:
							filtered_groups.append(gid)
				else:
					assert ltrace('groups', '> Select(SYS:%s/%s)' % (
						filters.SYS, filter_string))
					filtered_groups.extend(filter(self.is_system_gid,
						self.groups.keys()))

			elif filters.NOT_SYSTEM == filter_string:
				assert ltrace('groups', '> Select(PRI:%s/%s)' % (
					filters.NOT_SYS, filter_string))
				for gid in self.groups.keys():
					if not self.is_system_gid(gid):
						filtered_groups.append(gid)

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
	def _validate_fields(self, name, description, groupSkel):
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
			description = _('Members of group “%s”') % name

		elif not hlstr.cregex['description'].match(description):
			raise exceptions.BadArgumentError('''Malformed group description '''
				''''%s', must match /%s/i.'''
				% (description, stylize(
					ST_REGEX, hlstr.regex['description'])))

		if groupSkel is None:
			logging.progress('Using default skel dir %s' %
				LMC.configuration.users.default_skel)
			groupSkel = LMC.configuration.users.default_skel

		elif groupSkel not in LMC.configuration.users.skels:
			raise exceptions.BadArgumentError('''Invalid skel. Valid skels '''
				'''are: %s.''' % LMC.configuration.users.skels)

		return name, description, groupSkel

	def AddGroup(self, name, desired_gid=None, description=None, groupSkel=None,
		system=False, permissive=False, backend=None, users_to_add=[],
		batch=False, force=False):
		""" Add a Licorn group (the group + the guest/responsible group +
			the shared dir + permissions (ACL)). """

		assert ltrace('groups', '''> AddGroup(name=%s, system=%s, gid=%s, '''
			'''descr=%s, skel=%s, perm=%s)''' % (name, system, desired_gid,
				description, groupSkel, permissive))

		with self.lock():
			name, description, groupSkel = self._validate_fields(name,
				description, groupSkel)

			# FIXME: the GID could be taken, this could introduce
			# inconsistencies between the controller and extensions data.
			self.run_hooks('group_pre_add', gid=desired_gid,
											name=name, description=description)

			home = '%s/%s/%s' % (
				LMC.configuration.defaults.home_base_path,
				LMC.configuration.groups.names.plural,
				name)

			try:
				not_already_exists = True
				gid = self.__add_group(name, system, desired_gid, description,
					groupSkel, backend=backend, batch=batch, force=force)

			except exceptions.AlreadyExistsException, e:
				# don't bork if the group already exists, just continue.
				# some things could be missing (resp- , guest- , shared dir or
				# ACLs), it is a good idea to verify everything is really OK by
				# continuing the creation procedure.
				logging.info(str(e))
				gid = self.name_to_gid(name)
				not_already_exists = False
			else:
				# run this only if the group doesn't already exist, else
				# it gets written twice in extensions data.
				self.run_hooks('group_post_add', gid=gid, name=name,
								description=description, system=system)

		# LOCKS: can be released, because everything after now is FS operations,
		# not needing the internal data structures. It can fail if someone
		# delete a group during the CheckGroups() phase (a little later in this
		# method), but this will be harmless.

		if system:
			if not_already_exists:
				logging.notice(_(u'Created system group {0} '
					'(gid={1}).').format(stylize(ST_NAME, name),
					stylize(ST_UGID, gid)))

			# last operation before returning.
			self.AddUsersInGroup(gid=gid, users_to_add=users_to_add)

			# system groups don't have shared group dir nor resp-
			# nor guest- nor special ACLs. We stop here.
			assert ltrace('groups', '< AddGroup(name=%s,gid=%d)' % (name, gid))
			return gid, name

		self.groups[gid]['permissive'] = permissive

		try:
			self.CheckGroups([ gid ], minimal=True, batch=True, force=force)

			if not_already_exists:
				logging.notice(_(u'Created {0} group {1} (gid={2}).').format(
					stylize(ST_OK, _(u'permissive'))
						if self.groups[gid]['permissive'] else
							stylize(ST_BAD, _(u'not permissive')),
					stylize(ST_NAME, name),
					stylize(ST_UGID, gid)))

		except exceptions.SystemCommandError, e:
			logging.warning("ROLLBACK of group creation: " + str(e))

			import shutil
			shutil.rmtree(home)

			try:
				self.__delete_group(name)
			except:
				pass
			try:
				self.__delete_group('%s%s' % (
					LMC.configuration.groups.resp_prefix, name))
			except:
				pass
			try:
				self.__delete_group('%s%s' % (
					LMC.configuration.groups.guest_prefix, name))
			except:
				pass

			# re-raise, for the calling process to know what happened…
			raise e

		else:
			self.AddUsersInGroup(gid=gid, users_to_add=users_to_add)

		assert ltrace('groups', '< AddGroup(%s): gid %d' % (name, gid))
		if not_already_exists and self.inotifier:
			self.inotifier.add_group_watch(gid)
		return gid, name
	def __add_group(self, name, system, manual_gid=None, description=None,
		groupSkel = "", backend=None, batch=False, force=False):
		""" Add a POSIX group, write the system data files.
			Return the gid of the group created. """

		# LOCKS: No need to use self.lock(), already encapsulated in AddGroup().

		assert ltrace('groups', '''> __add_group(name=%s, system=%s, gid=%s, '''
			'''descr=%s, skel=%s)''' % (name, system, manual_gid, description,
				groupSkel)
			)

		if backend and backend not in LMC.backends.keys():
			raise exceptions.BadArgumentError('wrong backend %s, must be in %s.'
				% (stylize(ST_BAD, backend),
				stylize(ST_OK, ', '.join([x.name for x in self.backends]))))

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
				stylize(ST_UGID, gid)))
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
			'backend'     : backend if backend else self._prefered_backend_name,
			}

		if system:
			# we must fill the permissive status here, else WriteConf() will
			# fail with a KeyError. If not system, this has already been filled.
			temp_group_dict['permissive'] = None
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
		no_archive=False, batch=False, check_profiles=True):
		""" Delete an Licorn® group. """

		assert ltrace('groups', '''> DeleteGroup(gid=%s, name=%s, '''
			'''del_users=%s, no_archive=%s, batch=%s, check_profiles=%s)''' % (
			gid, name, del_users, no_archive, batch, check_profiles))

		gid, name = self.resolve_gid_or_name(gid, name)

		self.run_hooks('group_pre_del', gid=gid, name=name,
											system=self.is_system_gid(gid))

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
								batch=batch)

					if self.is_system_gid(gid):
						# wipe the group from the privileges if present there.
						if name in LMC.privileges:
							LMC.privileges.delete([name])

						# a system group has no data on disk (no shared directory), just
						# delete its internal data and exit.
						self.__delete_group(name)

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
						LMC.configuration.groups.resp_prefix, name))
					self.__delete_group('%s%s' % (
						LMC.configuration.groups.guest_prefix, name))

					self.CheckGroupSymlinks(gid=gid, name=name, delete=True,
						batch=True)
					self.__delete_group(name)

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
					logging.info(_(u'Cannot remove %s, it does not exist!') %
						stylize(ST_PATH, home))
				else:
					raise e
		else:
			# /home/archives must be OK befor moving
			LMC.configuration.check_base_dirs(minimal=True,
				batch=True)

			group_archive_dir = "%s/%s.deleted.%s" % (
				LMC.configuration.home_archive_dir, name,
				time.strftime("%Y%m%d-%H%M%S", time.gmtime()))
			try:
				os.rename(home, group_archive_dir)

				logging.info(_(u"Archived {0} as {1}.").format(home,
					stylize(ST_PATH, group_archive_dir)))

				LMC.configuration.check_archive_dir(
					group_archive_dir, batch=True)
			except OSError, e:
				if e.errno == 2:
					logging.info(_(u'Cannot archive %s, it does not exist!') %
						stylize(ST_PATH, home))
				else:
					raise e
	def __delete_group(self, name):
		""" Delete a POSIX group."""

		# LOCKS: this method is never called directly, and must always be
		# encapsulated in another, which will acquire self.lock(). This is the
		# case in DeleteGroup().

		assert ltrace('groups', '> __delete_group(%s)' % name)

		try:
			gid = self.name_cache[name]
		except KeyError:
			logging.info(_(u'Group %s does not exist.') % stylize(
				ST_NAME, name))
			return

		backend = self.groups[gid]['backend']

		system = self.is_system_gid(gid)

		# Remove the group in the groups list of profiles
		LMC.profiles.delete_group_in_profiles(name=name)

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

			logging.notice(_(u'Deleted {0}group {1}.').format(
				_(u'system ') if system else '', stylize(ST_NAME, name)))
		except KeyError:
			logging.warning(_(u'The group %s does not exist.') %
				stylize(ST_NAME, name))

		assert ltrace('groups', '< __delete_group(%s)' % name)
	def RenameGroup(self, name=None, gid=None, new_name=None):
		""" Modify the name of a group.

		# TODO: with self.lock()
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
	def ChangeGroupDescription(self, name=None, gid=None, description=None):
		""" Change the description of a group. """

		if description is None:
			raise exceptions.BadArgumentError, "You must specify a description"

		with self.lock():
			gid, name = self.resolve_gid_or_name(gid, name)

			self.groups[gid]['description'] = description

			LMC.backends[
				self.groups[gid]['backend']
				].save_Group(gid, backend_actions.UPDATE)

			logging.notice('Changed group %s description to "%s".' % (
				stylize(ST_NAME, name),
				stylize(ST_COMMENT, description)
				))
	def ChangeGroupSkel(self, name=None, gid=None, groupSkel=None):
		""" Change the description of a group. """

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

			logging.notice('Changed group %s skel to "%s".' % (
				stylize(ST_NAME, name),
				stylize(ST_COMMENT, groupSkel)
				))
	def AddGrantedProfiles(self, name=None, gid=None, users=None,
		profiles=None):
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
					logging.info(_(u'Group {0} already in the list '
						'of profile {1}.').format(stylize(ST_NAME, name),
						stylize(ST_NAME, p)))
				else:
					controllers.profiles.AddGroupsInProfile([name])
					logging.notice(
						"Added group %s in the groups list of profile %s." % (
						stylize(ST_NAME, name),
						stylize(ST_NAME, p)))
					# Add all 'p''s users in the group 'name'
					_users_to_add = self.__find_group_members(users,
						LMC.profiles[p]['groupName'])
					self.AddUsersInGroup(name, _users_to_add, users)
			else:
				logging.warning("Profile %s doesn't exist, ignored." %
					stylize(ST_NAME, p))

		# FIXME: is it needed to save() here ? isn't it already done by the
		# profile() and the AddUsersInGroup() calls ?
		LMC.backends[
			self.groups[gid]['backend']
			].save_Group(gid, backend_actions.UPDATE)
	def DeleteGrantedProfiles(self, name=None, gid=None, users=None,
		profiles=None):
		""" Disallow the users of the profiles given
			to access to the shared dir. """

		raise NotImplementedError('to be refreshed.')

		# FIXME: with self.lock()
		gid, name = self.resolve_gid_or_name(gid, name)

		# The profiles exist ?
		for p in profiles:
			# Delete the group from groups list of profiles
			if name in controllers.profiles[p]['memberGid']:
				logging.progress(_(u'Deleting group %s from the profile %s.') %
					( stylize(ST_NAME, name), stylize(ST_NAME, p)))
				controllers.profiles.DeleteGroupsFromProfile([name])
				# Delete all 'p''s users from the group 'name'
				_users_to_del = self.__find_group_members(users,
					controllers.profiles[p]['groupName'])
				self.DeleteUsersFromGroup(name, _users_to_del, users)
			else:
				logging.info(_(u'Group {0} already absent from '
					'profile {1}.').format(
					stylize(ST_NAME, name),
					stylize(ST_NAME, p)))

		# FIXME: not already done ??
		self.WriteConf()
	def AddUsersInGroup(self, name=None, gid=None, users_to_add=None,
		force=False, batch=False):
		""" Add a user list in the group 'name'. """

		assert ltrace('groups', '''> AddUsersInGroup(gid=%s, name=%s, '''
			'''users_to_add=%s, batch=%s)''' % (gid, name, users_to_add, batch))

		if users_to_add is None:
			raise exceptions.BadArgumentError("You must specify a users list")

		resp_prefix  = LMC.configuration.groups.resp_prefix
		guest_prefix = LMC.configuration.groups.guest_prefix

		# we need to lock users to be sure they don't dissapear during this phase.
		with self.lock():
			with LMC.users.lock():
				gid, name = self.resolve_gid_or_name(gid, name)

				# this attribute will be passed to hooks callbacks to ease deals.
				system = self.is_system_gid(gid)
				uids_to_add = LMC.users.guess_identifiers(users_to_add)

				work_done = False
				u2l = LMC.users.uid_to_login

				for uid in uids_to_add:
					login = u2l(uid)
					if login in self.groups[gid]['memberUid']:
						logging.info(_(u'User {0} is already a member '
							'of {1}, skipped.').format(
							stylize(ST_LOGIN, login),
							stylize(ST_NAME, name)))
					else:
						if system:
							if name.startswith(resp_prefix):
								# current group is a rsp-*

								if login in self.groups[
										self.name_to_gid(
												name[len(resp_prefix):])
											]['memberUid']:
									# we are promoting a standard member to
									# responsible, no need to --force. Simply
									# delete from standard group first, to
									# avoid ACLs conflicts.
									self.DeleteUsersFromGroup(name=
										name[len(resp_prefix):],
										users_to_del=[uid])

								elif login in self.groups[
										self.name_to_gid(guest_prefix +
												name[len(resp_prefix):])
											]['memberUid']:
									# Trying to promote a guest to responsible,
									# just delete him/her from guest group
									# to avoid ACLs conflicts.

									self.DeleteUsersFromGroup(name=
											guest_prefix
											+ name[len(resp_prefix):],
											users_to_del=[uid])

							elif name.startswith(guest_prefix):
								# current group is a gst-*

								if login in self.groups[
										self.name_to_gid(
												name[len(guest_prefix):])
											]['memberUid']:
									# user is standard member, we need to demote
									# him/her, thus need the --force flag.

									if force:
										# demote user from std to gst
										self.DeleteUsersFromGroup(name=
												name[len(resp_prefix):],
												users_to_del=[uid])
									else:
										raise exceptions.BadArgumentError(
											'cannot demote user %s from '
											'standard membership to guest '
											'without --force flag.' %
											stylize(ST_LOGIN, login))

								elif login in self.groups[
										self.name_to_gid(resp_prefix +
												name[len(guest_prefix):])
											]['memberUid']:
									# user is currently responsible. Demoting
									# to guest is an unusual situation, we need
									# to --force.

									if force:
										# demote user from rsp to gst
										self.DeleteUsersFromGroup(name=
												resp_prefix
												+ name[len(guest_prefix):],
												users_to_del=[uid])
									else:
										raise exceptions.BadArgumentError(
											'cannot demote user %s from '
											'responsible to guest '
											'without --force flag.' %
											stylize(ST_LOGIN, login))
							#else:
							# this is a system group, but not affialiated to
							# any standard group, thus no particular condition
							# applies: nothing to do.

						else:
							# standard group, check rsp & gst memberships

							if login in self.groups[
									self.name_to_gid(guest_prefix + name)
										]['memberUid']:
								# we are promoting a guest to standard
								# membership, no need to --force. Simply
								# delete from guest group first, to
								# avoid ACLs conflicts.
								self.DeleteUsersFromGroup(
									name=guest_prefix + name,
									users_to_del=[uid])

							elif login in self.groups[
									self.name_to_gid(resp_prefix + name)
										]['memberUid']:
								# we are trying to demote a responsible to
								# standard membership, we need to --force.

								if force:
									# --force is given: demote user!
									# Delete the user from standard group to
									# avoid ACLs conflicts.

									self.DeleteUsersFromGroup(name=
										resp_prefix + name,
										users_to_del=[uid])
								else:
									raise exceptions.BadArgumentError(
										'cannot demote user %s from '
										'responsible to standard membership '
										'without --force flag.'%
										stylize(ST_LOGIN, login))
							#else:
							#
							# user is not a guest or responsible of the group,
							# just a brand new member. Nothing to check.

						# #440 conditions are now verified and enforced, we
						# can make the user member of the desired group.

						self.groups[gid]['memberUid'].append(login)
						self.groups[gid]['memberUid'].sort()
						# update the users cache.
						LMC.users[uid]['groups'].append(name)
						LMC.users[uid]['groups'].sort()
						logging.notice(_(u'Added user {0} to members '
							'of group {1}.').format(stylize(ST_LOGIN, login),
							stylize(ST_NAME, name)))

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
							batch=True)

						link_src = os.path.join(
							LMC.configuration.defaults.home_base_path,
							LMC.configuration.groups.names.plural,
							link_basename)
						link_dst = os.path.join(
							LMC.users[uid]['homeDirectory'],
							link_basename)

						fsapi.make_symlink(link_src, link_dst, batch=batch)

						self.run_hooks('group_post_add_user',
							gid=gid, name=name, system=system,
							uid=uid, login=login)

				if batch and work_done:
					# save the group after having added all users. This seems more fine
					# than saving between each addition
					LMC.backends[
						self.groups[gid]['backend']
						].save_Group(gid, backend_actions.UPDATE)

					#self.reload_admins_group_in_validator(name)

		assert ltrace('groups', '< AddUsersInGroup()')
	def DeleteUsersFromGroup(self, name=None, gid=None, users_to_del=None,
		batch=False):
		""" Delete a users list in the group 'name'. """

		assert ltrace('groups', '''> DeleteUsersFromGroup(gid=%s, name=%s,
			users_to_del=%s, batch=%s)''' % (gid, name, users_to_del, batch))

		if users_to_del is None:
			raise exceptions.BadArgumentError("You must specify a users list")

		# we need to lock users to be sure they don't dissapear during this phase.
		with self.lock():
			with LMC.users.lock():
				gid, name = self.resolve_gid_or_name(gid, name)

				# this attribute will be passed to hooks callbacks to ease deals.
				system = self.is_system_gid(gid)

				uids_to_del = LMC.users.guess_identifiers(users_to_del)

				logging.progress("Going to remove users %s from group %s." % (
					stylize(ST_NAME, str(uids_to_del)),
					stylize(ST_NAME, name)))

				work_done = False
				u2l = LMC.users.uid_to_login

				for uid in uids_to_del:

					login = u2l(uid)

					self.run_hooks('group_pre_del_user', gid=gid, name=name,
							system=system, uid=uid, login=login)

					if login in self.groups[gid]['memberUid']:
						self.groups[gid]['memberUid'].remove(login)

						# update the users cache
						LMC.users[uid]['groups'].remove(name)

						logging.notice(_(u'Removed user {0} from members '
							'of group {1}.').format(stylize(ST_LOGIN, login),
							stylize(ST_NAME, name)))

						if batch:
							work_done = True
						else:
							LMC.backends[
								self.groups[gid]['backend']
								].save_Group(gid, backend_actions.UPDATE)

							# NOTE: this is not needed, the validator holds
							# a direct reference to this group members.
							#self.reload_admins_group_in_validator(name)

						if self.is_standard_gid(gid):
							# create the symlink to the shared group dir
							# in the user's home dir.
							link_basename = self.groups[gid]['name']
						elif name.startswith(
							LMC.configuration.groups.resp_prefix):
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
							# this is a normal system group, don't try to
							# remove any symlink !
							continue

						link_src = os.path.join(
							LMC.configuration.defaults.home_base_path,
							LMC.configuration.groups.names.plural,
							link_basename)

						for link in fsapi.minifind(
							LMC.users[uid]['homeDirectory'],
							maxdepth=2, type=stat.S_IFLNK):
							try:
								if os.path.abspath(
										os.readlink(link)) == link_src:
									os.unlink(link)
									logging.info(_(u'Deleted symlink %s.') %
										stylize(ST_LINK, link))
							except (IOError, OSError), e:
								if e.errno == 2:
									# this is a broken link,
									# readlink failed…
									pass
								else:
									raise exceptions.LicornRuntimeError(
										"Unable to delete symlink "
										"%s (was: %s)." % (
											stylize(ST_LINK, link),
											str(e)))
					else:
						logging.info(_(u'Skipped user {0}, already not '
							'a member of group {1}').format(
								stylize(ST_LOGIN, login),
								stylize(ST_NAME, name)))

		if batch and work_done:
			LMC.backends[
				self.groups[gid]['backend']
				].save_Group(gid, backend_actions.UPDATE)

			#self.reload_admins_group_in_validator(name)

		assert ltrace('groups', '< DeleteUsersFromGroup()')
	def BuildGroupACL(self, gid, path=''):
		""" Return an ACL triolet (a dict) used later to check something
			in the group shared dir.

			NOTE: the "@GX" and "@UX" strings will be later replaced by individual
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
			group_file_acl    = "rw@GX"
		else:
			group_default_acl = "r-x"
			group_file_acl    = "r-@GX"

		acl_base      = "u::rwx,g::---,o:---,g:%s:rwx,g:%s:r-x,g:%s:rwx" % (
			LMC.configuration.defaults.admin_group,
			LMC.configuration.groups.guest_prefix + group,
			LMC.configuration.groups.resp_prefix + group)
		file_acl_base = \
			"u::rw@UX,g::---,o:---,g:%s:rw@GX,g:%s:r-@GX,g:%s:rw@GX" % (
			LMC.configuration.defaults.admin_group,
			LMC.configuration.groups.guest_prefix + group,
			LMC.configuration.groups.resp_prefix + group)
		acl_mask      = "m:rwx"
		file_acl_mask = "m:rw@GX"

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
		batch=False, auto_answer=None, force=False):
		"""Check the system groups that a standard group needs to be valid.	For
			example, a group "MountainBoard" needs 2 system groups,
			rsp-MountainBoard and gst-MountainBoard for its ACLs on the group
			shared dir.

			NOT locked because called from already locked methods.

			:param name:
			:param gid: the standard group to verify depended upon system groups.
			:param minimal: if True, only the system groups are checked. Else,
							symlinks in the homes of standard group members and
							responsibles are also checked (can be long,
							depending on the number of members).
			:param batch: correct all errors without prompting.
			:param auto_answer: an eventual pre-typed answer to a preceding
								question asked outside of this method, forwarded
								to apply same answer to all questions.
			:param force: not used directly in this method, but forwarded to
							called methods which can use it.
		"""

		gid, name = self.resolve_gid_or_name(gid, name)

		all_went_ok = True

		with self.lock():
			for (prefix, title) in (
				(LMC.configuration.groups.resp_prefix, _(u"responsibles")),
				(LMC.configuration.groups.guest_prefix, _(u"guests"))
				):

				group_name = prefix + name
				logging.progress("Checking system group %s…" %
					stylize(ST_NAME, group_name))

				try:
					# FIXME: (convert this into an LicornKeyError ?) and use
					# name_to_gid() inside of direct cache access.
					prefix_gid = self.name_cache[group_name]

				except KeyError:
					warn_message = _(u'The system group {0} is required '
						'for the group {1} to be fully operationnal.').format(
						stylize(ST_NAME, group_name),
						stylize(ST_NAME, name))

					if batch or logging.ask_for_repair(warn_message,
						auto_answer):
						try:
							temp_gid = self.__add_group(group_name,
								system=True, manual_gid=None,
								description=_(u'{0} of group “{1}”').format(
											title, name),
								groupSkel='',
								backend=self.groups[gid]['backend'],
								batch=batch, force=force)
							prefix_gid = temp_gid
							del temp_gid

							logging.notice(_(u'Created system group {0}'
								'(gid={1}).').format(
									stylize(ST_NAME, group_name),
									stylize(ST_UGID, prefix_gid)))
						except exceptions.AlreadyExistsException, e:
							logging.info(str(e))
							pass
					else:
						logging.warning(warn_message)
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
					strip_prefix=prefix, batch=batch, auto_answer=auto_answer)

		return all_went_ok
	def __check_system_group(self, gid=None, name=None, minimal=True,
							batch=False, auto_answer=None):
		""" Check superflous and mandatory attributes of a system group. """

		gid, name = self.resolve_gid_or_name(gid, name)

		assert ltrace(self.name, '| __check_system_group(%s, %s)' % (gid, name))

		group = self.groups[gid]

		logging.progress(_(u'Checking system specific attributes '
				'for group {0}…').format(stylize(ST_NAME, name))
			)

		update = False

		# any system group should not have a skel, this is particularly useless.
		if 'groupSkel' in group and group['groupSkel'] != '':
			update = True
			del group['groupSkel']

			logging.info(_(u'Removed superfluous attribute {0} '
				'of system group {1}').format(
					stylize(ST_ATTR, 'groupSkel'),
					stylize(ST_NAME, name))
				)
		# Licorn® system groups should have at least a default description.
		# restricted system groups are not enforced on that point.
		if not self.is_restricted_system_gid(gid):
			if 'description' not in group:
				update = True
				group['description'] = _(u'Members of group “%s”') % name

				logging.info(_(u'Added missing {0} attribute with a '
					'default value for system group {1}.').format(
						stylize(ST_ATTR, 'description'),
						stylize(ST_NAME, name))
					)

		if update:
			if (batch or logging.ask_for_repair(_('Do you want to commit '
				'these changes to the system (highly recommended)?'),
				auto_answer=auto_answer)):

				LMC.backends[group['backend']].save_Group(gid,
														backend_actions.UPDATE)
				return True
			else:
				logging.warning(_(u'Corrections of system group '
					'{0} not commited').format(name))
				return False
		return True
	def __check_group(self, gid=None, name=None, minimal=True, batch=False,
		auto_answer=None, force=False):
		""" Check a group (the real implementation, private: don't call directly
			but use CheckGroups() instead). Will verify the various needed
			conditions for a Licorn® group to be valid, and then check all
			entries in the shared group directory.

			PARTIALLY locked, because very long to run (depending on the shared
			group dir size). Harmless if the unlocked part fails.

			:param gid/name: the group to check.
			:param minimal: don't check member's symlinks to shared group dir if True
			:param batch: correct all errors without prompting.
			:param auto_answer: an eventual pre-typed answer to a preceding question
				asked outside of this method, forwarded to apply same answer to
				all questions.
			:param force: not used directly in this method, but forwarded to called
				methods which can use it.
		"""

		assert ltrace('groups', '> __check_group(gid=%s,name=%s)' % (
			stylize(ST_UGID, gid),
			stylize(ST_NAME, name)))

		with self.lock():
			gid, name = self.resolve_gid_or_name(gid, name)

			all_went_ok = True

			if self.is_system_gid(gid):
				return self.__check_system_group(gid, minimal=minimal,
					batch=batch, auto_answer=auto_answer)

			logging.progress(_(u"Checking group {0}…").format(
					stylize(ST_NAME, name))
				)

			all_went_ok &= self.CheckAssociatedSystemGroups(
				name=name, minimal=minimal, batch=batch,
				auto_answer=auto_answer, force=force)

		group_home = "%s/%s/%s" % (
			LMC.configuration.defaults.home_base_path,
			LMC.configuration.groups.names.plural, name)

		# follow the symlink for the group home, only if link destination is a
		# dir. This allows administrator to put big group dirs on different
		# volumes (fixes #66).
		if os.path.islink(group_home):
			if os.path.exists(group_home) \
				and os.path.isdir(os.path.realpath(group_home)):
				group_home = os.path.realpath(group_home)

		# FIXME : We shouldn't check if the dir exists here, it is done
		# in fsapi.check_one_dir_and_acl() but we need to do it because
		# we set uid and gid to -1 so we need to access to path stats
		# in ACLRule.check_dir().
		# check if home group exists before doing anything.
		if not os.path.exists(group_home):
			if batch or logging.ask_for_repair("Directory %s doesn't exists on "
				"the system, this is mandatory create it?" %
					stylize(ST_PATH, group_home), auto_answer=auto_answer):
				os.mkdir(group_home)
				logging.info("Created directory %s." %
						stylize(ST_PATH, group_home))
			else:
				raise exceptions.LicornCheckError("Directory %s doesn't exists "
					"on the system, this is mandatory. The check procedure has "
					"been %s" % (
						stylize(ST_PATH, group_home),
						stylize(ST_BAD, "stopped")))

		# load the rules defined by user and merge them with templates rules.
		rules = self.load_rules(group_home + '/' +
			LMC.configuration.users.check_config_file,
			# user_uid et user_gid are set to -1 to don't touch to current uid and
			# gid owners of the group.
			object_info=Enumeration(home=group_home, user_uid=-1, user_gid=-1),
			identifier=gid,
			vars_to_replace=(
					('@GROUP', name),
					('@GW', 'w' if self.groups[gid]['permissive'] else '-')
				)
			)

		# run the check
		try:
			if rules != None:
				all_went_ok &= fsapi.check_dirs_and_contents_perms_and_acls_new(
					rules, batch=batch, auto_answer=auto_answer)
		except exceptions.DoesntExistsException, e:
			logging.warning(e)

		if not minimal:
			logging.progress(
				"Checking %s symlinks in members homes, this can be long…"  %
					stylize(ST_NAME, name))
			all_went_ok &= self.CheckGroupSymlinks(gid=gid, batch=batch,
				auto_answer=auto_answer)

			# TODO: if extended / not minimal: all group members' homes are OK
			# (recursive CheckUsers recursif)
			# WARNING: be carefull of recursive multicalls, when calling
			# CheckGroups, which calls CheckUsers, which could call
			# CheckGroups()… use minimal=True as argument here, don't forward
			# the current "minimal" value.

		assert ltrace('groups', '< __check_group(%s)' % all_went_ok)

		return all_went_ok
	def check_nonexisting_users(self, batch=False, auto_answer=None):
		""" Go through all groups, find members which are referenced but
			don't really exist on the system, and wipe them.

			LOCKED to be thread-safe for groups and users.

			batch: correct all errors without prompting.
			auto_answer: an eventual pre-typed answer to a preceding question
				asked outside of this method, forwarded to apply same answer to
				all questions.
		"""

		assert ltrace('groups', '> check_nonexisting_users(batch=%s)' % batch)

		with self.lock():
			with LMC.users.lock():
				for gid in sorted(self.groups):
					to_remove = set()

					logging.progress('Checking for dangling references '
						'in group %s.' % stylize(ST_NAME,
							self.groups[gid]['name']))

					for member in self.groups[gid]['memberUid']:
						if not LMC.users.login_cache.has_key(member):
							if batch or logging.ask_for_repair('''User %s is '''
								'''referenced in _members of group %s but doesn't '''
								'''really exist on the system. Remove this dangling '''
								'''reference?''' % \
									(stylize(ST_BAD, member),
									stylize(ST_NAME,
										self.groups[gid]['name'])),
									auto_answer=auto_answer):
								# don't directly remove member from members,
								# it will immediately stop the for_loop. Instead, note
								# the reference to remove, to do it a bit later.
								to_remove.add(member)

								logging.info(_(u'Removed dangling reference '
									'to non-existing user {0} in '
									'group {1}.').format(
									stylize(ST_BAD, member),
									stylize(ST_NAME,
										self.groups[gid]['name'])))

					if to_remove != set():
						for member in to_remove:
							self.groups[gid]['memberUid'].remove(member)
							self.WriteConf(gid)

		assert ltrace('groups', '< check_nonexisting_users()')
	def _fast_check_group(self, gid, path):
		""" check a file in a group and apply its perm without any confirmation

			:param gid: id of the group where the file is located
			:param path: path of the modified file/dir
		"""
		assert ltrace('groups', "> _fast_check_group(gid=%s, path=%s)" %
			(gid, path))

		group = self[gid]

		try:
			group_home = group['group_home']
		except KeyError:
			group_home = group['group_home'] = "%s/%s/%s" % (
				LMC.configuration.defaults.home_base_path,
				LMC.configuration.groups.names.plural, self[gid]['name'])

		try:
			rules = group['special_rules']

		except KeyError:
			rules = self.load_rules(group_home + '/' +
				LMC.configuration.users.check_config_file,
				object_info=Enumeration(home=group_home,
										user_uid=-1, user_gid=-1),
				identifier=gid,
				vars_to_replace=(
						('@GROUP', self.gid_to_name(gid)),
						('@GW', 'w' if self.groups[gid]['permissive'] else '-')
					)
				)
		else:
			assert ltrace('groups', "Skipped: rules from %s were already "
			"loaded, we do not reload them in the fast check procedure." %
				group_home + '/' + 	LMC.configuration.users.check_config_file)

		rule_name  = path[len(group_home)+1:].split('/')[0]

		try:
			entry_stat = os.lstat(path)
		except (IOError, OSError), e:
			if e.errno == 2:
				# bail out if path has disappeared since we were called.
				return
			else:
				raise

		# find the special rule applicable on the path.
		is_root_dir = False
		# if the path has a special rule, load it
		if rule_name in rules:
			dir_info = rules[rule_name].copy()
		# else take the default one
		else:
			dir_info = rules._default.copy()
			if rule_name is '':
				is_root_dir = True

		# the dir_info.path has to be the path of the checked file
		dir_info.path = path

		if path[-1] == '/':
			path = path[:-1]

		# deal with owners
		# uid owner of the path is:
		#	- 'root' = 0 if path is group home
		#	- unchanged if it is not the group home
		# gid owner of the path is:
		#	- 'acl' if an acl will be set to the path.
		#	- the primary group of the user owner of the path, if uid will not
		#		be changed.
		#	- 'acl' if we don't keep the same uid.
		if path == group_home:
			dir_info.uid = 0
		else:
			dir_info.uid = -1

		if ':' in dir_info.root_dir_perm or ',' in dir_info.root_dir_perm:
			dir_info.gid = LMC.groups.name_to_gid(LMC.configuration.acls.group)
		else:
			if dir_info.uid == -1:
				dir_info.gid = LMC.users[entry_stat.st_uid]['gidNumber']
			else:
				dir_info.gid = LMC.groups.name_to_gid(
											LMC.configuration.acls.group)

		# get the type of the path (file or dir)
		if ( entry_stat.st_mode & 0170000 ) == stat.S_IFREG:
			file_type = stat.S_IFREG
		else:
			file_type = stat.S_IFDIR

		# run the check
		fsapi.check_perms(dir_info, batch=True,	file_type=file_type,
			is_root_dir=is_root_dir, full_display=False)

		assert ltrace('groups', '< _fast_check_group')
	def CheckGroups(self, gids_to_check, minimal=True, batch=False,
		auto_answer=None, force=False):
		""" Check groups, groups dependancies and groups-related caches. If a
			given group is not system, check it's shared dir, the depended upon
			system groups, and eventually the members symlinks.

			NOT locked because subparts are, where needed.

			:param gids_to_check: a list of GIDs to check. If you don't have
									GIDs but group names, use name_to_gid()
									before.
			:param minimal: don't check group symlinks in member's homes if True.
			:param batch: correct all errors without prompting.
			:param auto_answer: an eventual pre-typed answer to a preceding
								question asked outside of this method, forwarded
								to apply same answer to all questions.
			:param force: not used directly in this method, but forwarded to
							called methods which can use it.
		"""

		assert ltrace('groups', '''> CheckGroups(gids_to_check=%s, minimal=%s, '''
			'''batch=%s, force=%s)''' %	(gids_to_check, minimal, batch, force))

		if not minimal:
			self.check_nonexisting_users(batch=batch, auto_answer=auto_answer)

		def _chk(gid):
			assert ltrace('groups', '| CheckGroups._chk(%s)' % gid)
			return self.__check_group(gid=gid, minimal=minimal, batch=batch,
				auto_answer=auto_answer, force=force)

		if reduce(pyutils.keep_false, map(_chk, gids_to_check)) is False:
			# don't test just "if reduce(…):", the result could be None and
			# everything is OK when None
			raise exceptions.LicornCheckError(
				"Some group(s) check(s) didn't pass, or weren't corrected.")

		assert ltrace('groups', '< CheckGroups()')
	def CheckGroupSymlinks(self, name=None, gid=None, oldname=None,
		delete=False, strip_prefix=None, batch=False, auto_answer=None):
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
					stylize(ST_NAME, user))
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
								logging.info(_(u'Deleted symlink %s.') %
									stylize(ST_LINK, link))
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
						logging.info(_(u'Deleted old symlink %s.') %
							stylize(ST_LINK, link))
					else:
						# errno == 2 is a broken link, don't bother.
						raise exceptions.LicornRuntimeError(
							"Unable to read symlink %s (error was: %s)." % (
								link, str(e)))

			if link_not_found and not delete:
				warn_message = _(u'User {0} lacks the symlink to '
					'group {1} shared dir. Create it?').format(
					stylize(ST_LOGIN, user),
					stylize(ST_NAME, link_basename))

				if batch or logging.ask_for_repair(warn_message, auto_answer):
					fsapi.make_symlink(link_src, link_dst, batch=batch,
						auto_answer=auto_answer)
				else:
					logging.warning(warn_message)
					all_went_ok = False

		return all_went_ok
	def SetSharedDirPermissiveness(self, gid=None, name=None, permissive=True):
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
				qualif = _(u'')
			else:
				qualif = _(u'not ')

			logging.progress('''Setting permissive=%s for group %s ('''
				'''original is %s).''' % (
				stylize(ST_OK if permissive else ST_BAD, permissive),
				stylize(ST_NAME, name),
				stylize(ST_OK if self.groups[gid]['permissive'] else ST_BAD,
					self.groups[gid]['permissive'])))

			if self.groups[gid]['permissive'] != permissive:
				self.groups[gid]['permissive'] = permissive

				# auto-apply the new permissiveness
				self.CheckGroups([ gid ], batch=True)
				logging.info(_(u'Switched group {0} permissive '
					'state to {1}.').format(stylize(ST_NAME, name),
					stylize(ST_OK if permissive else ST_BAD, _(u'True')
						if permissive else _(u'False'))
					)
				)
			else:
				logging.info(_(u'Group {0} is already {1}permissive.').format(
					stylize(ST_NAME, name), qualif))
	def move_to_backend(self, gid, new_backend, force=False,
			internal_operation=False):
		""" Move a group from a backend to another, with extreme care. Any
			occurring exception will cancel the operation.

			Moving a standard group will begin by moving

			Moving a restricted system group will fail if argument ``force``
			is ``False``. This is not recommended anyway, groups <= 300 are
			handled by distros maintainer, you'd better not touch them.

		"""
		if new_backend not in LMC.backends.keys():
			raise exceptions.DoesntExistsException("Backend %s doesn't exist "
				"or in not enabled." % new_backend)

		group_name = self.groups[gid]['name']
		old_backend = self.groups[gid]['backend']

		if old_backend == new_backend:
			logging.info(_(u'Skipped move of group {0}, '
				'already stored in backend {1}.').format(
					stylize(ST_NAME, group_name),
					stylize(ST_NAME, new_backend)))
			return True

		if self.is_restricted_system_gid(gid) and not force:
			logging.warning("Skipped move of restricted system group %s "
				"(please use %s if you really want to do this, "
				"but it is strongly not recommended)." % (
					stylize(ST_NAME, group_name),
					stylize(ST_DEFAULT, '--force')))
			return

		if (group_name.startswith(LMC.configuration.groups.resp_prefix) or
			group_name.startswith(LMC.configuration.groups.guest_prefix)) \
			and not internal_operation:
				raise exceptions.BadArgumentError("Can't move an associated "
					"system group without moving its standard group too. "
					"Please move the standard group instead, if this is "
					"what you meant.")

		if self.is_standard_gid(gid):

			if not self.move_to_backend(
				self.name_to_gid(LMC.configuration.groups.resp_prefix
					+ group_name), new_backend, internal_operation=True):

				logging.warning('Skipped move of group %s to backend %s '
					'because move of associated responsible system group '
						'failed.' % (group_name, new_backend))
				return

			if not self.move_to_backend(
				self.name_to_gid(LMC.configuration.groups.guest_prefix
					+ group_name), new_backend, internal_operation=True):

				# pray this works, else we're in big trouble, a shoot in a
				# foot and a golden shoe on the other.
				self.move_to_backend(
					self.name_to_gid(LMC.configuration.groups.resp_prefix
						+ group_name), old_backend)

				logging.warning('Skipped move of group %s to backend %s '
					'because move of associated system guest group '
						'failed.' % (group_name, new_backend))
				return

		try:
			# we must change the backend, else iterating backends (like Shadow)
			# will not save the new group.
			self.groups[gid]['backend'] = new_backend
			LMC.backends[new_backend].save_Group(gid, backend_actions.CREATE)

		except KeyboardInterrupt, e:
			logging.warning("Exception %s happened while trying to move group "
				"%s from %s to %s, aborting (group left unchanged)." % (e,
				group_name, old_backend, new_backend))

			try:
				# restore old situation.
				self.groups[gid]['backend'] = old_backend
				LMC.backends[new_backend].delete_Group(group_name)
			except:
				pass

			return False
		else:
			# the copy operation is successfull, make it a real move.
			LMC.backends[old_backend].delete_Group(group_name)

			logging.info(_(u'Moved group {0} from backend {1} to {2}.').format(
				stylize(ST_NAME, group_name), stylize(ST_NAME, old_backend),
				stylize(ST_NAME, new_backend)))
			return True
	def is_permissive(self, gid, name):
		""" Return True if the shared dir of the group is permissive.

			This method MUST be called with the 2 arguments GID and name.

			WARNING: don't use self.resolve_gid_or_name() here. This method is
			used very early, from the GroupsController.__init__(), when groups
			are in the process of beiing loaded. The resolve*() calls will fail.

			LOCKED because very important.

			gid and name are mandatory, this function won't resolve them.
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
								stylize(ST_NAME, name)), once=True)
				else:
					raise exceptions.LicornIOError("IO error on %s (was: %s)." %
						(home, e))
			except ImportError, e:
				logging.warning(logging.MODULE_POSIX1E_IMPORT_ERROR % e, once=True)
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
		except ValueError:
			gid = self.name_to_gid(value)
			assert ltrace('groups', '| guess_identifier: name_to_gid(%s) -> %s'
				% (value, gid))

		return gid
	def guess_identifiers(self, value_list):
		""" return a list of valid and existing GIDs, given a list of 'things'
		 to validate existence of (can be GIDs or names). """
		valid_ids=set()
		for value in value_list:
			try:
				valid_ids.add(self.guess_identifier(value))
			except exceptions.DoesntExistsException:
				logging.info(_(u'Skipped non-existing group name or GID %s.') %
					stylize(ST_NAME,value))
		return list(valid_ids)
	def exists(self, name=None, gid=None):
		"""Return true if the group or gid exists on the system. """

		assert ltrace('groups', '|  exists(name=%s, gid=%s)' % (name, gid))

		if name:
			return name in self.name_cache

		if gid:
			return gid in self.groups

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
			or gid > LMC.configuration.groups.gid_max
	def is_restricted_system_name(self, group_name):
		""" return true if login is system, but outside the range of Licorn®
			controlled UIDs. """
		try:
			return self.is_restricted_system_gid(
				self.name_cache[group_name])
		except KeyError:
			raise exceptions.DoesntExistsException(
				_(u'Group %s does not exist.') % stylize(ST_NAME, name))
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
				_(u'Group %s does not exist.') % stylize(ST_NAME, name))
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
	def _wmi_protected_group(self, name, complete=True):
		if complete:
			return self.is_system_group(name) and not (
				name.startswith(LMC.configuration.groups.resp_prefix)
				or name.startswith(LMC.configuration.groups.guest_prefix))
		else:
			return self.is_system_group(name) and not (
				name.startswith(LMC.configuration.groups.resp_prefix)
				or name.startswith(LMC.configuration.groups.guest_prefix)
				) and not self.is_privilege(name)
