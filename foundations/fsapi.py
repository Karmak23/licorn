# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

fsapi - File System API

These functions interact with a posix compatible filesystem, to ease common
operations like finding files, recursively checking / changing permissions
and ACLs, making / removing symlinks, and so on.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import os, posix1e
from stat import *

from licorn.foundations.ltrace import ltrace
from licorn.foundations        import logging, exceptions, pyutils, process
from licorn.foundations.styles import *

from licorn.core import LMC

# WARNING: DON'T IMPORT licorn.core.configuration HERE.
# just pass "configuration" as a parameter if you need it somewhere.
# fsapi is meant to to be totally independant of licorn.core.configuration !!

def minifind(path, type=None, perms=None, mindepth=0, maxdepth=99, exclude=[],
	followlinks=False, followmounts=True):
	""" Mimic the GNU find behaviour in python. returns an iterator. """

	if mindepth > maxdepth:
		raise  exceptions.BadArgumentError("mindepth must be <= maxdepth.")

	if maxdepth > 99:
		raise  exceptions.BadArgumentError(
			"please don't try to exhaust maxdepth.")

	assert ltrace('fsapi', '''> minifind(%s, type=%s, mindepth=%s, maxdepth=%s, '''
		'''exclude=%s, followlinks=%s, followmounts=%s)''' % (
			path, type, mindepth, maxdepth, exclude, followlinks, followmounts))

	paths_to_walk      = [ path ]
	next_paths_to_walk = []
	current_depth      = 0
	S_IFSTD            = S_IFDIR | S_IFREG

	while True:

		if paths_to_walk != []:
			entry = paths_to_walk.pop(0)

		elif next_paths_to_walk != []:
			paths_to_walk      = next_paths_to_walk
			next_paths_to_walk = []
			entry              = paths_to_walk.pop(0)
			current_depth     += 1

		else:
			break

		try:
			entry_stat = os.lstat(entry)
			entry_type = entry_stat.st_mode & 0170000
			entry_mode = entry_stat.st_mode & 07777
		except (IOError, OSError), e:
			if e.errno == 2 or (e.errno == 13 and entry[-5:] == '.gvfs'):
				continue
			else:
				raise e
		else:
			if current_depth >= mindepth \
				and ( (type is None and entry_type & S_IFSTD) \
					or entry_type == type) \
				and ( perms is None or (entry_mode & perms) ):
				#ltrace('fsapi', '  minifind(yield=%s)' % entry)
				yield entry

			#print 'type %s %s %s' % (entry_type, S_IFLNK, entry_type & S_IFLNK)

			if (entry_type == S_IFLNK and not followlinks) \
				or (os.path.ismount(entry) and not followmounts):
				logging.progress('minifind(): skipping link or mountpoint %s.' %
					stylize(ST_PATH, entry))
				continue

			if entry_type == S_IFDIR and current_depth < maxdepth:
				try:
					for x in os.listdir(entry):
						if x not in exclude:
							next_paths_to_walk.append("%s/%s" % (entry, x))
						else:
							assert ltrace('fsapi', '  minifind(excluded=%s)' % entry)
				except (IOError, OSError), e:
					if e.errno == 2:
						# happens on recursive delete() applyed on minifind()
						# results: the dir vanishes during the os.listdir().
						continue
					else:
						raise e
def check_dirs_and_contents_perms_and_acls(dirs_infos, batch=False,
	auto_answer=None, allgroups=None, allusers=None):
	""" Check if a dir exists, else create it and apply ACLs on it eventually.
		dirs_infos should be a n-tuple of dicts, composed like this:
		{
			'path'        : string,
			'type'        : stat.S_IF???,    # what type the "path" should be
			'user'        : 'owner',         # the name, not the uid
			'group'       : 'group',         # the name too,
			'exclude'     : [ … ],         # dirs and files inside 'path' to be excluded from search)

			*and*

			'mode'       : chmod_mode (INT), # always use 00600 for example, not just 600, else it won't work.
			'content_mode': another int,      # mode for files inside 'path'

			*or*

			'access_acl' : string,
			'default_acl': string,
			'content_acl': string,
		}

		if mode and content_mode are present, ACL will be deleted from path and its contents, *_acl will
		not be used and not be checked (Posix mode and posix1e ACLs are mutually exclusive).

		when content_mode is present, it will be applyed on regular files inside 'path'. 'mode' will be
		applyed on dirs inside 'path'.

		When checking ACLs, default_acl will be applyed on dirs as access *and* default acl. 'default_acl'
		will be applyed on dirs inside 'path', and 'content_acl' will be checked against files inside 'path'.

		TODO: 'default_acl' should be checked against files inside 'path', modulo the mask change from
		'rwx' to 'rw-', which will should automagically imply "effective" ACLs computed on the fly.
		"""
	assert ltrace('fsapi', '> check_dirs_and_contents_perms_and_acls('
		'dirs_infos=%s, batch=%s, auto_answer=%s)' % (
			dirs_infos, batch, auto_answer))
	if allusers is None:
		from licorn.core.configuration import LicornConfiguration
		from licorn.core.users import UsersController
		configuration = LicornConfiguration()
		allusers = UsersController(configuration)

	if allgroups is None:
		from licorn.core.groups import GroupsController
		allgroups = GroupsController(allusers.configuration, allusers)

	def check_one_dir_and_acl(dir_info, batch=batch, auto_answer=auto_answer):

		all_went_ok = True
		#assert logging.debug('checking %s' % stylize(ST_PATH, dir_info['path']))

		try:
			if dir_info.has_key('user') and dir_info['user'] != '':
				uid = allusers.login_to_uid(dir_info['user'])
			else:
				uid = -1

			if dir_info.has_key('group') and dir_info['group'] != '':
				gid = allgroups.name_to_gid(dir_info['group'])
			else:
				gid = -1
		except KeyError, e:
			raise exceptions.LicornRuntimeError('''You just encountered a '''
				'''programmer bug. Get in touch with cortex@5sys.fr (was: '''
				'''%s).''' % e)
		except exceptions.LicornRuntimeException, e:
			raise exceptions.LicornRuntimeError('''The uid/gid you want to '''
				'''check against does not exist on this system ! This '''
				'''shouldn't happen and is probably a programmer/packager '''
				'''bug. Get in touch with oc@meta-it.fr (was: %s).''' % e)

		try:
			logging.progress("Checking dir %s…" %
				stylize(ST_PATH, dir_info['path']))
			dirstat = os.lstat(dir_info['path'])

		except OSError, e:
			if e.errno == 13:
				raise exceptions.InsufficientPermissionsError(str(e))
			elif e.errno == 2:
				warn_message = ("Directory %s does not exist." %
					stylize(ST_PATH, dir_info['path']))

				if batch or logging.ask_for_repair(warn_message,
					auto_answer=auto_answer):
					os.mkdir(dir_info['path'])
					dirstat = os.lstat(dir_info['path'])
					batch = True
					logging.info("Created directory %s." %
						stylize(ST_PATH, dir_info['path']))
				else:
					raise exceptions.LicornCheckError(
						"Can't continue checks for directory %s (was: %s)." % (
							dir_info['path'], e) )
			else:
				# FIXME: do more things to recover from more system errors…
				raise e

		if ( dirstat.st_mode & 0170000 ) != S_IFDIR:

			warn_message = (logging.SWKN_DIR_IS_NOT_A_DIR %
				stylize(ST_PATH, dir_info['path']))

			if batch or logging.ask_for_repair(warn_message,
				auto_answer=auto_answer):
				os.unlink(dir_info['path'])
				os.mkdir(dir_info['path'])
				dirstat = os.lstat(dir_info['path'])
				batch = True
				logging.info("Created directory %s." %
					stylize(ST_PATH, dir_info['path']))
			else:
				raise exceptions.LicornCheckError(
					"Can't continue checks for directory %s (was: %s)." % (
						dir_info['path'], e) )

		if dir_info.has_key('mode'):
			logging.progress("Checking %s's posix perms…" %
				stylize(ST_PATH, dir_info['path']))

			all_went_ok &= check_posix_ugid_and_perms(dir_info['path'], uid,
				gid, dir_info['mode'], batch, auto_answer, allgroups, allusers)

			if dir_info.has_key('content_mode'):
				# check the contents of the dir (existing files and directories,
				# except the ones which are excluded), only if the content_mode
				# is set, else skip content check.

				all_went_ok &= check_posix_dir_contents(dir_info, uid, gid,
				batch=batch, auto_answer=auto_answer)

		else:
			logging.progress("Checking %s's ACLs…" %
				stylize(ST_PATH, dir_info['path']))

			# check uid/gid, but don't check the perms (thus -1) because ACLs
			# overrride them.
			all_went_ok &= check_posix_ugid_and_perms(dir_info['path'], uid,
				gid, -1, batch, auto_answer, allgroups, allusers)

			all_went_ok &= check_posix1e_acl(dir_info['path'], False,
				dir_info['access_acl'], dir_info['default_acl'], batch,
				auto_answer)

			if dir_info.has_key('content_acl'):
				# this hack is needed to use check_posix_dir_contents() to check
				# only uid/gid (not perms)
				dir_info['mode']          = -1
				dir_info['content_mode' ] = -1
				# check the contents of the dir (existing files and directories,
				# except the ones which are excluded), only if "content_acl" is
				# set, else skip content check.
				all_went_ok &= check_posix_dir_contents(dir_info, uid, gid,
					batch, auto_answer, allgroups, allusers)
				all_went_ok &= check_posix1e_dir_contents(dir_info, batch,
					auto_answer)

		return all_went_ok

	if dirs_infos:
		if reduce(pyutils.keep_false,
			map(check_one_dir_and_acl, dirs_infos)) is False:
			return False
		else:
			return True

	else:
		raise exceptions.BadArgumentError(
			"You must pass something through dirs_infos to check!")

	assert ltrace('fsapi', '< check_dirs_and_contents_perms_and_acls()')
def check_dirs_and_contents_perms_and_acls_new(dirs_infos, batch=False,
	auto_answer=None):
	""" general function to check file/dir """

	assert ltrace('fsapi', '> check_dirs_and_contents_perms_and_acls_new('
		'dirs_infos=%s, batch=%s, auto_answer=%s)' % (
			dirs_infos, batch, auto_answer))

	def check_one_dir_and_acl(dir_info, batch=batch, auto_answer=auto_answer):
		all_went_ok = True
		# save desired user and group owner of the file/dir
		try:
			if dir_info.user:
				uid = dir_info['user']
			else:
				uid = -1
			if dir_info.group and dir_info.group != '':
				gid = dir_info['group']
			else:
				gid = -1
		except KeyError, e:
			raise exceptions.LicornRuntimeError('''You just encountered a '''
				'''programmer bug. Get in touch with robin@licorn.org (was: '''
				'''%s).''' % e)
		except exceptions.LicornRuntimeException, e:
			raise exceptions.LicornRuntimeError('''The uid/gid you want to '''
				'''check against does not exist on this system ! This '''
				'''shouldn't happen and is probably a programmer/packager '''
				'''bug. Get in touch with dev@licorn.org (was: %s).''' % e)

		# Does the file/dir exist ?
		try:
			entry_stat = os.lstat(dir_info['path'])
		except OSError, e:
			if e.errno == 13:
				raise exceptions.InsufficientPermissionsError(str(e))
			elif e.errno == 2:
				warn_message = ("Directory %s does not exist." %
					styles.stylize(styles.ST_PATH, dir_info['path']))

				if batch or logging.ask_for_repair(warn_message, auto_answer,
					listener=listener):
					os.mkdir(dir_info['path'])
					dirstat = os.lstat(dir_info['path'])
					batch = True
					logging.info("Created directory %s." %
						styles.stylize(styles.ST_PATH, dir_info['path']),
						listener=listener)
				else:
					# we cannot continue if dir does not exist.
					raise exceptions.LicornCheckError(
						"Can't continue checks for directory %s (was: %s)." % (
							dir_info['path'], e) )
			else:
				# FIXME: do more things to recover from more system errors…
				raise e

		# if it is a file
		if ( entry_stat.st_mode & 0170000 ) == S_IFREG:
			logging.progress("Checking file %s…" %
				stylize(ST_PATH, dir_info['path']))
			if dir_info.files_perm and dir_info.user \
				and dir_info.group:
				check_perms(
					file_type=S_IFREG,
					dir_info=dir_info,
					batch=batch)

		# if it is a dir
		elif ( entry_stat.st_mode & 0170000 ) == S_IFDIR:
			logging.progress("Checking dir %s…" %
				stylize(ST_PATH, dir_info['path']))
			# if the directory ends with '/' that mean that we will only
			# affect the content of the dir.
			# the dir itself will receive default licorn ACL rights (those
			# defined in the configuration)
			if dir_info.path[-1] == '/':
				dir_info_root = dir_info.copy()
				dir_info_root.root_dir_acl = True
				dir_info_root.root_dir_perm = "%s,g:%s:rwx,%s" % (
					LMC.configuration.acls.acl_base,
					LMC.configuration.defaults.admin_group,
					LMC.configuration.acls.acl_mask)
				dir_info_root.group = "acl"

				# now that the "root dir" has its special treatment,
				# prepare dir_info for the rest (its contents)
				dir_info.path = dir_info.path[:-1]
			else:
				dir_info_root = dir_info

			logging.progress("Checking %s's %s…" % (
				stylize(ST_PATH, dir_info['path']),
				"ACLs" if dir_info.root_dir_acl else "posix perms"))
			# deal with root dir
			check_perms(
				is_root_dir=True,
				file_type=S_IFDIR,
				dir_info=dir_info_root,
				batch=batch)

			if dir_info.files_perm != None or dir_info.dirs_perm != None:
				try:
					exclude_list = dir_info.exclude
				except AttributeError :
					exclude_list = []

			if dir_info.files_perm != None:
				logging.progress("Checking %s's contents %s…" % (
					stylize(ST_PATH, dir_info['path']),
					'ACLs' if dir_info.content_acl else 'posix perms'))

				if dir_info.dirs_perm != None:
					dir_path = dir_info['path']
					for dir in minifind(dir_path, exclude=exclude_list, mindepth=1,
						type=S_IFDIR):
						dir_info.path=dir
						check_perms(
							file_type=S_IFDIR,
							dir_info=dir_info,
							batch=batch)

				# deal with files inside root dir
				for file in minifind(dir_path, exclude=exclude_list, mindepth=1,
					type=S_IFREG):
						dir_info.path = file
						check_perms(
						file_type=S_IFREG,
						dir_info=dir_info,
						batch=batch)

		else:
			logging.warning('''The type of %s is not recognised by the '''
				'''check_user() function.''' % dir_info['path'])
		return all_went_ok

	if dirs_infos != None:
		# first, check user_home
		try:
			check_one_dir_and_acl(dirs_infos._default)
		except AttributeError:
			pass
		# check all specials_dirs
		for dir_info in dirs_infos:
			if check_one_dir_and_acl(dir_info) is False:
				return False
		else:
			return True

	else:
		raise exceptions.BadArgumentError(
			"You must pass something through dirs_infos to check!")

	assert ltrace('fsapi', '< check_dirs_and_contents_perms_and_acls_new()')
def check_perms(dir_info, file_type=None, is_root_dir=False, batch=None,
	auto_answer=None):
	""" general function to check is permissions are ok on file/dir """
	assert ltrace('fsapi', '> check_perms(dir_info=%s, file_type=%s, '
		'is_root_dir=%s, batch=%s, auto_answer=%s' % (
			dir_info, file_type, is_root_dir, batch, auto_answer))
	if file_type is S_IFDIR:
		if is_root_dir:
			access_perm = dir_info.root_dir_perm
			perm_acl = dir_info.root_dir_acl
		else:
			access_perm = dir_info.dirs_perm
			perm_acl = dir_info.content_acl
	else:
		access_perm = dir_info.files_perm
		perm_acl = dir_info.content_acl

	if perm_acl:
		# FIXME : allow @X only.
		execperms = execbits2str(dir_info.path)
		if '@GX' in access_perm or '@UX' in access_perm:
			access_perm = str(access_perm).replace('@GX', execperms[1]).replace(
				'@UX', execperms[0])
		access_perm = posix1e.ACL(text='%s' % access_perm)

	check_uid_and_gid(path=dir_info.path,
		uid=LMC.users.guess_identifier(dir_info.user),
		gid=LMC.groups.guess_identifier(dir_info.group if not perm_acl
			else 'acl'), batch = batch)

	logging.progress("Checking %s of %s." % (
		"posix1e ACL" if perm_acl else "posix perms",
		stylize(ST_PATH, dir_info.path)))

	if perm_acl:
		# apply posix1e access perm on the file/dir
		current_perm = posix1e.ACL(file=dir_info.path)

		if current_perm != access_perm:

			current_perm_text = str(current_perm).replace("\n", ",").replace(
				"group:","g:").replace("user:","u:").replace(
				"other::","o:").replace("mask::","m:")[:-1]
			access_perm_text = str(access_perm).replace("\n", ",").replace(
				"group:","g:").replace("user:","u:").replace(
				"other::","o:").replace("mask::","m:")[:-1]

			warn_message = logging.SWKN_INVALID_ACL % ("Access",
				stylize(ST_PATH, dir_info.path),
				stylize(ST_BAD, current_perm_text),
				stylize(ST_ACL, access_perm_text))

			if batch or logging.ask_for_repair(warn_message,
				auto_answer=auto_answer):
					# be sure to pass an str() to acl.applyto(), else it will
					# raise a TypeError if onpath is an unicode string…
					# (checked 2006 08 08 on Ubuntu Dapper)
					posix1e.ACL(acl=access_perm).applyto(str(dir_info.path),
						posix1e.ACL_TYPE_ACCESS)
					logging.info("Applyed access ACL %s on %s." % (
						stylize(ST_ACL, access_perm_text),
						stylize(ST_PATH, dir_info.path)))
			else:
				all_went_ok = False

		# if it is a directory, apply default ACLs
		if file_type is S_IFDIR:
			current_default_perm = posix1e.ACL(filedef=dir_info.path)
			if dir_info.dirs_perm != None and ':' in str(dir_info.dirs_perm):
				default_perm = dir_info.dirs_perm
			else:
				default_perm = dir_info.root_dir_perm
			default_perm = posix1e.ACL(text=default_perm)
			if current_default_perm != default_perm:

				current_perm_text = str(current_default_perm).replace(
					"\n", ",").replace("group:","g:").replace(
					"user:","u:").replace("other::","o:").replace(
					"mask::","m:")[:-1]
				access_perm_text = str(default_perm).replace("\n", ",").replace(
					"group:","g:").replace("user:","u:").replace(
					"other::","o:").replace("mask::","m:")[:-1]

				warn_message = logging.SWKN_INVALID_ACL % ("Default",
					stylize(ST_PATH, dir_info.path),
					stylize(ST_BAD, current_perm_text),
					stylize(ST_ACL, access_perm_text))

				if batch or logging.ask_for_repair(warn_message,
					auto_answer=auto_answer):
					default_perm.applyto(str(dir_info.path),
						posix1e.ACL_TYPE_DEFAULT)
					logging.info("Applyed default ACL %s on %s." % (
						stylize(ST_ACL, access_perm_text),
						stylize(ST_PATH, dir_info.path)))
				else:
					all_went_ok = False
	else:
		# delete previus ACL perms in case of existance
		if has_extended_acl(dir_info.path):
			# if an ACL is present, this could be what is borking the Unix mode.
			# an ACL is present if it has a mask, else it is just standard posix
			# perms expressed in the ACL grammar. No mask == Not an ACL.

			warn_message = "An ACL is present on %s, but it should not." \
				% stylize(ST_PATH, dir_info.path)
			if batch or logging.ask_for_repair(warn_message,
				auto_answer=auto_answer):
				# if it is a directory we need to delete DEFAULT ACLs too
				if file_type is S_IFDIR:
					posix1e.ACL(text="").applyto(str(dir_info.path),
						posix1e.ACL_TYPE_DEFAULT)
					logging.info("Deleted default ACL from %s." %
						stylize(ST_PATH, dir_info.path))
				# delete ACCESS ACLs if it is a file or a directory
				posix1e.ACL(text="").applyto(str(dir_info.path),
					posix1e.ACL_TYPE_ACCESS)
				logging.info("Deleted access ACL from %s." %
					stylize(ST_PATH, dir_info.path))
			else:
				all_went_ok = False
		pathstat = os.lstat(dir_info.path)
		current_perm = pathstat.st_mode & 07777
		if current_perm != access_perm:
			current_perm_txt     = perms2str(current_perm)
			access_perms_txt    = perms2str(access_perm)
			warn_message = logging.SWKN_INVALID_MODE % (
				stylize(ST_PATH, dir_info.path),
				stylize(ST_BAD, current_perm_txt),
				stylize(ST_ACL, access_perms_txt))

			if batch or logging.ask_for_repair(warn_message,
				auto_answer=auto_answer):
					os.chmod(dir_info.path, access_perm)
					logging.info("Applyed perms %s on %s." % (
						stylize(ST_ACL, access_perms_txt),
						stylize(ST_PATH, dir_info.path)))
			else:
				all_went_ok = False

	assert ltrace('fsapi', '< check_perms()')
def check_uid_and_gid(path, uid=-1, gid=1, batch=None, auto_answer=None):
	""" function that check the uid and gid of a fieml or a dir. """
	logging.progress("Checking posix uid/gid/perms of %s." %
		stylize(ST_PATH, path))
	try:
		pathstat = os.lstat(path)
	except OSError, e:
		if e.errno == 2:
			# causes of this error:
			#     - this is a race condition: the dir/file has been deleted between the minifind()
			#       and the check_*() call. Don't blow out on this.
			#     - when we explicitely want to check a path which does not exist because it has not
			#       been created yet (eg: ~/.dmrc on a brand new user account).
			return True
		else:
			raise e

	# if one or both of the uid or gid are empty, don't check it, use the
	# current one present in the file meta-data.
	if uid == -1:
		uid = pathstat.st_uid
		try:
			desired_login = LMC.users[uid]['login']
		except KeyError:
			desired_login = str(uid)
	else:
		desired_login = LMC.users.uid_to_login(uid)

	if gid == -1:
		gid = pathstat.st_gid
		try:
			desired_group = LMC.groups[gid]['name']
		except KeyError:
			desired_group = str(gid)
	else:
		desired_group = LMC.groups[gid]['name']

	if pathstat.st_uid != uid or pathstat.st_gid != gid:

		try:
			current_login = LMC.users[pathstat.st_uid]['login']
		except KeyError:
			current_login = str(pathstat.st_uid)

		try:
			current_group = LMC.groups[pathstat.st_gid]['name']
		except KeyError:
			current_group = str(pathstat.st_gid)

		warn_message = logging.SWKN_DIR_BAD_OWNERSHIP \
				% (
					stylize(ST_PATH, path),
					stylize(ST_BAD, current_login),
					stylize(ST_BAD, current_group),
					stylize(ST_UGID, desired_login),
					stylize(ST_UGID, desired_group),
				)

		if batch or logging.ask_for_repair(warn_message,
			auto_answer=auto_answer):
			os.chown(path, uid, gid)
			logging.info("Changed owner of %s from %s:%s to %s:%s." % (
				stylize(ST_PATH, path),
				stylize(ST_UGID, current_login),
				stylize(ST_UGID, current_group),
				stylize(ST_UGID, desired_login),
				stylize(ST_UGID, desired_group)))
		else:
			all_went_ok = False

def check_posix1e_dir_contents(dir_info, batch=False, auto_answer=None):
	"""TODO."""
	all_went_ok = True

	try:
		exclude_list = dir_info['exclude']
	except KeyError:
		exclude_list = []

	logging.progress("Checking %s's contents ACLs…" %
		stylize(ST_PATH, dir_info['path']))

	try:
		if reduce(pyutils.keep_false, map(lambda x: check_posix1e_acl(x, False,
			dir_info['default_acl'], dir_info['default_acl'], batch=batch,
			auto_answer=auto_answer),
			 minifind(dir_info['path'], exclude=exclude_list, mindepth=1,
				type=S_IFDIR))) is False:
			all_went_ok = False

	except TypeError:
		# TypeError: reduce() of empty sequence with no initial value
		# happens when shared dir has no directory at all in it (except
		# public_html which is excluded).
		logging.progress('no subdir to check in %s.' %
			stylize(ST_PATH, dir_info['path']))

	try:
		if reduce(pyutils.keep_false, map(
			lambda x: check_posix1e_acl(x, True, dir_info['content_acl'], "",
				batch=batch, auto_answer=auto_answer),
			minifind(dir_info['path'], exclude=exclude_list, mindepth=1,
				type=S_IFREG))) is False:
			all_went_ok = False
	except TypeError:
		# same here if there are no files…
		logging.progress('no files to check in %s.' %
			stylize(ST_PATH, dir_info['path']))

	return all_went_ok
def check_posix_dir_contents(dir_info, uid, gid, batch=False, auto_answer=None,
	allgroups=None, allusers=None, mode='mode'):
	"""TODO."""

	all_went_ok = True

	logging.progress("Checking %s's contents posix perms…" %
		stylize(ST_PATH, dir_info['path']))

	if dir_info.has_key('exclude'):
		exclude_list = dir_info['exclude']
	else:
		exclude_list = []
	try:
		if reduce(pyutils.keep_false, map(
			lambda x: check_posix_ugid_and_perms(x, uid, gid, dir_info[mode],
				batch, auto_answer, allgroups, allusers),
			 minifind(dir_info['path'], exclude=exclude_list, mindepth=1,
				type=S_IFDIR))) is False:
			all_went_ok = False
	except TypeError:
		# TypeError: reduce() of empty sequence with no initial value
		# happens when shared dir has no directory at all in it (except
		# public_html which is excluded).
		pass
	try:
		if reduce(pyutils.keep_false, map(
			lambda x: check_posix_ugid_and_perms(x, uid, gid,
				dir_info['content_mode'], batch, auto_answer, allgroups,
				allusers),
			minifind(dir_info['path'], exclude=exclude_list, mindepth=1,
				type=S_IFREG))) is False:
			all_went_ok = False
	except TypeError:
		# same exception if there are no files…
		pass
	return all_went_ok
def check_posix_ugid_and_perms(onpath, uid=-1, gid=-1, perms=-1, batch=False,
	auto_answer=None, allgroups=None, allusers=None):
	"""Check if some path has some desired perms, repair if told to do so."""
	if onpath in ("", None):
		raise exceptions.BadArgumentError(
			"The path you want to check perms on must not be empty !")
	if allusers is None:
		from licorn.core.configuration import LicornConfiguration
		from licorn.core.users import UsersController
		configuration = LicornConfiguration()
		allusers = LMC.users(configuration)
	if allgroups is None:
		from licorn.core.groups import GroupsController
		allgroups = GroupsController(allusers.configuration, allusers)
	all_went_ok = True

	logging.progress("Checking posix uid/gid/perms of %s." %
		stylize(ST_PATH, onpath))

	try:
		pathstat = os.lstat(onpath)
	except OSError, e:
		if e.errno == 2:
			# causes of this error:
			#     - this is a race condition: the dir/file has been deleted between the minifind()
			#       and the check_*() call. Don't blow out on this.
			#     - when we explicitely want to check a path which does not exist because it has not
			#       been created yet (eg: ~/.dmrc on a brand new user account).
			return True
		else:
			raise e

	# if one or both of the uid or gid are empty, don't check it, use the
	# current one present in the file meta-data.
	if uid == -1:
		uid = pathstat.st_uid
		try:
			desired_login = allusers[uid]['login']
		except KeyError:
			desired_login = str(uid)
	else:
		desired_login = allusers[uid]['login']

	if gid == -1:
		gid = pathstat.st_gid
		try:
			desired_group = allgroups[gid]['name']
		except KeyError:
			desired_group = str(gid)
	else:
		desired_group = allgroups[gid]['name']

	if pathstat.st_uid != uid or pathstat.st_gid != gid:

		try:
			current_login = allusers[pathstat.st_uid]['login']
		except KeyError:
			current_login = str(pathstat.st_uid)

		try:
			current_group = allgroups[pathstat.st_gid]['name']
		except KeyError:
			current_group = str(pathstat.st_gid)

		warn_message = logging.SWKN_DIR_BAD_OWNERSHIP \
				% (
					stylize(ST_PATH, onpath),
					stylize(ST_BAD, current_login),
					stylize(ST_BAD, current_group),
					stylize(ST_UGID, desired_login),
					stylize(ST_UGID, desired_group),
				)

		if batch or logging.ask_for_repair(warn_message,
			auto_answer=auto_answer):
			os.chown(onpath, uid, gid)
			logging.info("Changed owner of %s from %s:%s to %s:%s." % (
				stylize(ST_PATH, onpath),
				stylize(ST_UGID, current_login),
				stylize(ST_UGID, current_group),
				stylize(ST_UGID, desired_login),
				stylize(ST_UGID, desired_group)))
		else:
			all_went_ok = False

	if perms == -1:
		# stop here, we just wanted to check uid/gid
		return all_went_ok

	if has_extended_acl(onpath):
		# if an ACL is present, this could be what is borking the Unix mode.
		# an ACL is present if it has a mask, else it is just standard posix
		# perms expressed in the ACL grammar. No mask == Not an ACL.

		#assert logging.debug2("pathacl = %s, perms = %s (%s)." %
		# (str(pathacl), perms2str(perms, acl_form = True),
		# str(pathacl).find("mask::")))

		warn_message = "An ACL is present on %s, but it should not." \
			% stylize(ST_PATH, onpath)

		if batch or logging.ask_for_repair(warn_message,
			auto_answer=auto_answer):
			posix1e.ACL(text="").applyto(str(onpath))

			if pathstat.st_mode & 0170000 == S_IFDIR:
				posix1e.ACL(text="").applyto(str(onpath),
					posix1e.ACL_TYPE_DEFAULT)

			logging.info("Deleted ACL from %s." %
				stylize(ST_PATH, onpath))

			# redo the stat, to get the current posix mode.
			pathstat = os.lstat(onpath)

			# enter batch mode: if there was an ACL, the std posix perms will be false in 99%
			# of the cases, because the ACL has modified the group perms with the mask content.
			# Thus, don't bother the administrator with another question, just correct the posix perms.
			#
			# As perms check is the only thing left to do in this function after the present ACL check,
			# setting batch to True locally here won't accidentally batch other checks.
			batch = True
		else:
			all_went_ok = False

	# now that we are sure that there isn't any ACLs on the file/dir, continue checking.
	mode = pathstat.st_mode & 07777

	#assert logging.debug2("Comparing desired %d and current %d on %s." % (perms, mode, onpath))
	if perms != mode:
		mode_txt     = perms2str(mode)
		perms_txt    = perms2str(perms)
		warn_message = logging.SWKN_INVALID_MODE % (
			stylize(ST_PATH, onpath),
			stylize(ST_BAD, mode_txt),
			stylize(ST_ACL, perms_txt))

		if batch or logging.ask_for_repair(warn_message,
			auto_answer=auto_answer):
				os.chmod(onpath, perms)
				logging.info("Applyed perms %s on %s." % (
					stylize(ST_ACL, perms_txt),
					stylize(ST_PATH, onpath)))
		else:
			all_went_ok = False

	return all_went_ok
def auto_check_posix_ugid_and_perms(onpath, uid=-1, gid=-1, perms=-1):
	"""	Auto-Check-And-Apply if some path has some desired perms, repair if told to do so.
		This is an automatic version of check_posix_ugid_and_perms() function. """

	try:
		pathstat = os.lstat(onpath)

		if uid == -1:
			uid = pathstat.st_uid
		if gid == -1:
			gid = pathstat.st_gid

		if pathstat.st_uid != uid or pathstat.st_gid != gid:
			os.chown(onpath, uid, gid)
			logging.progress("Auto-changed owner of %s to %s:%s." %
				(onpath, uid, gid))

		if perms == -1:
			return True

		if has_extended_acl(onpath):
			posix1e.ACL(text="").applyto(str(onpath))
			if pathstat.st_mode & 0170000 == S_IFDIR:
				posix1e.ACL(text="").applyto(str(onpath),
					posix1e.ACL_TYPE_DEFAULT)

			logging.progress("Auto-deleted ACL from %s." % onpath)
			pathstat = os.lstat(onpath)

		mode = pathstat.st_mode & 07777

		if perms != mode:
			os.chmod(onpath, perms)
			logging.progress("Auto-applyed perms %s on %s." % (perms, onpath))

	except (IOError, OSError), e:
		if e.errno != 2:
			raise e

	return True
def check_posix1e_acl(onpath, path_is_file, access_acl_text="",
	default_acl_text="", batch=False, auto_answer=None):
	"""Check if a [default] acl is present on a given path, repair if not and asked for.

	Note: ACL aren't apply on symlinks (on ext2/ext3), they apply on the destination of
	the link, which could be bad when the destination is outside a particular
	directory tree. This problem does not arise when working on XFS. I don't know
	about reiserfs. Anyway this is a good idea to skip symlinks, because setting
	an ACL on a symlink has no real justification though.

	see http://acl.bestbits.at/pipermail/acl-devel/2001-December/000834.html
	"""

	if onpath in ("", None):
		raise exceptions.BadArgumentError("The path you want to check ACL on must not be empty !")

	if access_acl_text is "" and default_acl_text is "":
		raise exceptions.BadArgumentError("You have to give at at least one of access or default ACL to check on %s !" % onpath)

	if path_is_file:
		execperms       = execbits2str(onpath)
		#assert logging.debug2("Exec perms are %s before replacement." % execperms)
		access_acl_text = access_acl_text.replace('@GX', execperms[1]).replace('@UX', execperms[0])

	logging.progress("Checking posix1e ACL of %s." %
		stylize(ST_PATH, onpath))

	all_went_ok = True

	for (desired_acl_text, is_default, acl_type) in (
		(access_acl_text, False, posix1e.ACL_TYPE_ACCESS),
		(default_acl_text, True, posix1e.ACL_TYPE_DEFAULT)
		):

		# if an ACL is "", the corresponding value will be deleted from the file,
		# this is a desired behaviour, to delete superfluous ACLs.
		try:
			desired_acl = posix1e.ACL(text=desired_acl_text)
		except NameError, e:
			logging.warning(logging.MODULE_POSIX1E_IMPORT_ERROR % e, once=True)
			return True
		except (OSError,IOError), e:
			logging.warning('''Unable to create ACL object on %s (the system '''
				'''may miss some needed groups), creating an empty one (was: '''
				'''%s, desired_acl=%s).''' % (onpath, e, desired_acl_text))
			# FIXME: why not exit here ? why create an empty ACL ?
			desired_acl = posix1e.ACL()

		if is_default:
			if path_is_file:
				continue
			else:
				# only test/apply default ACL on directories.
				acl_qualif = "Default"
				acl_value  = posix1e.ACL(filedef=onpath)
		else:
			acl_qualif = "Access"
			acl_value  = posix1e.ACL(file=onpath)

		#
		# Warning: the next test REQUIRE pylibacl >= 0.3.0.
		# else, the test will always fail, because Python will only
		# compare ACL objects basically, and they WILL be different.
		#

		if acl_value != desired_acl:

			acl_value_text = str(acl_value).replace("\n", ",").replace(
				"group:","g:").replace("user:","u:").replace(
				"other::","o:").replace("mask::","m:")[:-1]

			if acl_value_text == "":
				acl_value_text = "none"

			warn_message = logging.SWKN_INVALID_ACL % (acl_qualif,
				stylize(ST_PATH, onpath),
				stylize(ST_BAD, acl_value_text),
				stylize(ST_ACL, desired_acl_text))

			if batch or logging.ask_for_repair(warn_message,
				auto_answer=auto_answer):
					# be sure to pass an str() to acl.applyto(), else it will
					# raise a TypeError if onpath is an unicode string…
					# (checked 2006 08 08 on Ubuntu Dapper)
					desired_acl.applyto(str(onpath), acl_type)
					logging.info("Applyed %s ACL %s on %s." % (
						acl_qualif,
						stylize(ST_ACL, desired_acl_text),
						stylize(ST_PATH, onpath)))
			else:
				all_went_ok = False

	return all_went_ok
def auto_check_posix1e_acl(onpath, path_is_file, access_acl_text="",
	default_acl_text=""):
	"""	Auto_check (don't ask questions) if a [default] acl is present on a
		given path, repair if not and asked for.
		This is a fast version of the check_posix1e_acl() function, without
			any confirmations.
	"""

	if path_is_file:
		execperms       = execbits2str(onpath)
		access_acl_text = access_acl_text.replace('@GX', execperms[1]).replace('@UX', execperms[0])

	for (desired_acl_text, is_default, acl_type) in (
		(access_acl_text, False, posix1e.ACL_TYPE_ACCESS),
		(default_acl_text, True, posix1e.ACL_TYPE_DEFAULT)
		):

		if is_default:
			if path_is_file:
				continue
			else:
				acl_value  = posix1e.ACL(filedef=onpath)
		else:
			acl_value  = posix1e.ACL(file=onpath)

		desired_acl = posix1e.ACL(text = desired_acl_text)

		if acl_value != desired_acl:
			desired_acl.applyto(str(onpath), acl_type)
			logging.progress('Auto-applyed ACL type %s on %s.' %
				(acl_type, onpath))

	return True
def make_symlink(link_src, link_dst, batch=False, auto_answer=None):
	"""Try to make a symlink cleverly."""
	try:
		os.symlink(link_src, link_dst)
		logging.info("Created symlink %s, pointing to %s." % (
			stylize(ST_LINK, link_dst),
			stylize(ST_PATH, link_src)))
	except OSError, e:
		if e.errno == 17:
			# 17 == file exists
			if os.path.islink(link_dst):
				try:
					read_link = os.path.abspath(os.readlink(link_dst))

					if read_link != link_src:
						if os.path.exists(read_link):
							warn_message = ('''A symlink %s already exists '''
								'''but badly points to %s, instead of %s. '''
								'''Correct it? ''' % (
									stylize(ST_LINK, link_dst),
									stylize(ST_PATH, read_link),
									stylize(ST_PATH, link_src)))

							if batch or logging.ask_for_repair(warn_message,
								auto_answer=auto_answer):
								os.unlink(link_dst)
								os.symlink(link_src, link_dst)
								logging.info('''Overwritten symlink %s with '''
									'''destination %s instead of %s.''' % (
									stylize(ST_LINK, link_dst),
									stylize(ST_PATH, link_src),
									stylize(ST_PATH, read_link)))
							else:
								raise exceptions.LicornRuntimeException(
									"Can't create symlink %s to %s!" % (
										link_dst, link_src))
						else:
							# TODO: should we ask the question ? This isn't
							# really needed, as the link is broken.
							# Just replace it and don't bother the administrator.
							logging.info('''Symlink %s is currently broken '''
								'''(pointing to non-existing target %s) ; '''
								'''making it point to %s.''' % (
								stylize(ST_LINK, link_dst),
								stylize(ST_PATH, read_link),
								stylize(ST_PATH, link_src)))
							os.unlink(link_dst)
							os.symlink(link_src, link_dst)

				except OSError, e:
					if e.errno == 2:
						# no such file or directory, link has disapeared…
						os.symlink(link_src, link_dst)
						logging.info("Repaired vanished symlink %s." %
							stylize(ST_LINK, link_dst))
			else:

				# TODO / WARNING: we need to investigate a bit more: if current
				# link_src is a file, overwriting it could be very bad (e.g.
				# user could loose a document). This is the same for a
				# directory, modulo the user could loose much more than just a
				# document. We should scan the dir and replace it only if empty
				# (idem for the file), and rename it (thus find a unique name,
				# like 'the file.autosave.XXXXXX.txt' where XXXXXX is a random
				# string…)

				warn_message = ('''%s already exists but it isn't a symlink, '''
					'''thus doesn't point to %s. Replace it with a correct '''
					'''symlink?''' % (
						stylize(ST_LINK, link_dst),
						stylize(ST_PATH, link_src)))

				if batch or ask_for_repair(warn_message,
					auto_answer=auto_answer):
					os.unlink(link_dst)
					os.symlink(link_src, link_dst)
					logging.info('''Replaced dir/file %s with destination %s '''
						'''instead of %s.''' % (
						stylize(ST_LINK, link_dst),
						stylize(ST_PATH, link_src),
						stylize(ST_PATH, read_link)))
				else:
					raise exceptions.LicornRuntimeException('''While making '''
						'''symlink to %s, the destination %s already exists '''
						'''and is not a link.''' % (link_src, link_dst))

# various unordered functions, which still need to find a more elegant home.

def has_extended_acl(pathname):
	# return True if the posix1e representation of pathname's ACL has a MASK.
	for acl_entry in posix1e.ACL(file = pathname):
		if acl_entry.tag_type is posix1e.ACL_MASK:
			return True
	return False

# use pylibacl 0.4.0 accelerated C function if possible.
if hasattr(posix1e, 'HAS_EXTENDED_CHECK'):
	if posix1e.HAS_EXTENDED_CHECK:
		has_extended_acl = posix1e.has_extended

def backup_file(filename):
	""" make a backup of a given file. """
	bckp_ext='.licorn.bak'
	open('%s%s' % (filename, bckp_ext), 'w').write(open(filename).read())
	logging.notice('Backed up %s as %s.' % (
		stylize(ST_PATH, filename),
		stylize(ST_COMMENT, '%s%s' % (filename, bckp_ext)))
		)
def is_backup_file(filename):
	"""Return true if file is a backup file (~,.bak,…)."""
	if filename[-1] == '~':
		return True
	if filename[-4:] in ('.bak', '.old', '.swp'):
		return True
	return False
def get_file_encoding(filename):
	""" Try to find the encoding of a given file.
		(python's file.encoding is not very reliable, or I don't use use it like I should).

		TODO: use python mime module to do this ?
	"""

	# file -b: brief (the file name is not printed)
	encoding = process.execute(['file', '-b', filename])[0][:-1].split(' ')

	if encoding[0] == "ISO-8859":
		ret_encoding = "ISO-8859-15"
	elif encoding[0] == "UTF-8" and encoding[1] == "Unicode":
		ret_encoding = "UTF-8"
	elif encoding[0] == "Non-ISO" and encoding[1] == "extended-ASCII":
		# FIXME: find the correct encoding when a file comme from Windows ?
		ret_encoding = None
	else:
		ret_encoding = None

	return ret_encoding
def execbits2str(filename):
	"""Find if a file has executable bits and return (only) then as a list of strings, used later to build an ACL permission string.

		TODO: as these exec perms are used for ACLs only, should not we avoid testing setuid and setgid bits ? what does setguid means in a posix1e ACL ?
	"""

	fileperms = os.lstat(filename).st_mode & 07777
	execperms = []

	# exec bit for owner ?
	if fileperms & S_IXUSR:
		execperms.append('x')
	else:
		execperms.append('-')

	# exec bit for group ?
	if fileperms & S_IXGRP:
		execperms.append('x')
	else:
		execperms.append('-')

	# skip exec bit for other, not used in our ACLs.

	return execperms
def perms2str(perms, acl_form = False):
	""" Convert an int mode to a readable string like "ls" does.  """

	string = ''

	# USER

	if acl_form:
		string += "user::"

	if perms & S_IRUSR:
		string += 'r'
	else:
		string += '-'

	if perms & S_IWUSR:
		string += 'w'
	else:
		string += '-'

	if perms & S_IXUSR:
		if perms & S_ISUID:
			string += 's'
		else:
			string += 'x'
	else:
		if perms & S_ISUID:
			string += 'S'
		else:
			string += '-'

	if acl_form:
		string += "\ngroup::"

	# GROUP

	if perms & S_IRGRP:
		string += 'r'
	else:
		string += '-'

	if perms & S_IWGRP:
		string += 'w'
	else:
		string += '-'

	if perms & S_IXGRP:
		if perms & S_ISGID:
			string += 's'
		else:
			string += 'x'
	else:
		if perms & S_ISGID:
			string += 'S'
		else:
			string += '-'

	if acl_form:
		string += "\nother::"

	# OTHER

	if perms & S_IROTH:
		string += 'r'
	else:
		string += '-'

	if perms & S_IWOTH:
		string += 'w'
	else:
		string += '-'

	if perms & S_IXOTH:
		if perms & S_ISVTX:
			string += 't'
		else:
			string += 'x'
	else:
		if perms & S_ISVTX:
			string += 'T'
		else:
			string += '-'

	if acl_form:
		string += "\n"

	return string
