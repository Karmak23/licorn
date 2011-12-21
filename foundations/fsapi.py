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

import os, posix1e, time, shutil, errno
from stat import *


from licorn.foundations.ltrace    import ltrace, ltrace_func
from licorn.foundations.ltraces   import *
from licorn.foundations           import logging, exceptions, pyutils, process
from licorn.foundations.styles    import *

from licorn.core import LMC

# WARNING: DON'T IMPORT licorn.core.configuration HERE.
# just pass "configuration" as a parameter if you need it somewhere.
# fsapi is meant to to be totally independant of licorn.core.configuration !!

def minifind(path, itype=None, perms=None, mindepth=0, maxdepth=99, exclude=[],
	followlinks=False, followmounts=True, yield_type=False):
	""" Mimic the GNU find behaviour in python. returns an iterator. """

	if mindepth > maxdepth:
		raise  exceptions.BadArgumentError(
			_(u'minifind: mindepth must be <= maxdepth.'))

	if maxdepth > 99:
		raise  exceptions.BadArgumentError(
			_(u'minifind: please do not try to exhaust maxdepth.'))

	assert ltrace_func(TRACE_FSAPI)

	paths_to_walk      = [ path ]
	next_paths_to_walk = []
	current_depth      = 0
	if itype is None:
		itype = (S_IFDIR, S_IFREG)

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
			if e.errno == errno.ENOENT or (e.errno == 13 and entry[-5:] == '.gvfs'):
				logging.warning2(_(u'fsapi.minifind(): error on {0}: {1}').format(stylize(ST_PATH, entry), e))
			else:
				raise e
		else:
			if (current_depth >= mindepth
				and entry_type in itype
				and (perms is None or entry_mode & perms)):
				#ltrace(TRACE_FSAPI, '  minifind(yield=%s)' % entry)

				if yield_type:
					yield (entry, entry_type)

				else:
					yield entry

			#print 'itype %s %s %s' % (entry_type, S_IFLNK, entry_type & S_IFLNK)

			if (entry_type == S_IFLNK and not followlinks) \
				or (os.path.ismount(entry) and not followmounts):
				logging.progress(_(u'minifind(): skipping link or '
					u'mountpoint {0}.').format(stylize(ST_PATH, entry)))
				continue

			if entry_type == S_IFDIR and current_depth < maxdepth:
				try:
					for x in os.listdir(entry):
						if x not in exclude:
							next_paths_to_walk.append("%s/%s" % (entry, x))

						else:
							assert ltrace(TRACE_FSAPI, '  minifind(excluded=%s)' % entry)

				except (IOError, OSError), e:
					if e.errno == errno.ENOENT:
						# happens on recursive delete() applyed on minifind()
						# results: the dir vanishes during the os.listdir().
						logging.warning2(_(u'fsapi.minifind(): error on {0}: {1}').format(stylize(ST_PATH, entry), e))

					else:
						raise e
	assert ltrace_func(TRACE_FSAPI, True)
def check_dirs_and_contents_perms_and_acls_new(dirs_infos, batch=False,
										auto_answer=None, full_display=True):
	""" General function to check file/directory. """

	assert ltrace_func(TRACE_FSAPI)

	conf_acls = LMC.configuration.acls
	conf_dflt = LMC.configuration.defaults

	def check_one_dir_and_acl(dir_info, batch=batch, auto_answer=auto_answer,
													full_display=full_display):
		path = dir_info['path']

		# Does the file/dir exist ?
		try:
			entry_stat = os.lstat(path)

		except (IOError, OSError), e:
			if e.errno == 13:
				raise exceptions.InsufficientPermissionsError(str(e))

			elif e.errno == 2:

				if batch or logging.ask_for_repair(_(u'Directory %s does not '
								u'exist. Create it?') % stylize(ST_PATH, path),
							auto_answer=auto_answer):

					# NOTE: don't yield path here, this would make the
					# INotifier related thing expect it, and ignore it. And
					# we need the event to propagate, to make the watch manager
					# auto_add the dir.
					#
					# yield path

					os.mkdir(path)

					# we need to re-stat because we use the stat result after
					# this point.
					entry_stat = os.lstat(path)

					if full_display:
						logging.info(_(u'Created directory {0}.').format(
													stylize(ST_PATH, path)))
				else:
					# we cannot continue if dir does not exist.
					raise exceptions.LicornCheckError(_(u'Cannot continue '
						u'checks for directory {0} (was: {1}).').format(
							path, e))
			else:
				# FIXME: do more things to recover from more system errors…
				raise e

		mode = entry_stat.st_mode & 0170000

		# if it is a file
		if mode == S_IFREG:
			if full_display:
				logging.progress(_(u'Checking file %s…') % stylize(ST_PATH, path))

			for event in check_perms(file_type=S_IFREG, dir_info=dir_info,
						batch=batch, auto_answer=auto_answer,
						full_display=full_display):
				yield event

		# if it is a dir
		elif mode == S_IFDIR:
			if full_display:
				logging.progress(_(u'Checking directory %s…') %
										stylize(ST_PATH, path))

			# if the directory ends with '/' that mean that we will only
			# affect the content of the dir.
			# the dir itself will receive default licorn ACL rights (those
			# defined in the configuration)
			if dir_info.path[-1] == '/':
				dir_info_root = dir_info.copy()
				dir_info_root.root_dir_acl  = True
				dir_info_root.root_dir_perm = "%s,g:%s:rwx,%s" % (
										conf_acls.acl_base,
										conf_dflt.admin_group,
										conf_acls.acl_mask)
				dir_info_root.gid = conf_acls.gid

				# now that the "root dir" has its special treatment,
				# prepare dir_info for the rest (its contents)
				dir_info.path = dir_info.path[:-1]

			else:
				dir_info_root = dir_info

			if full_display:
				logging.progress(_(u'Checking {1} on {0}…').format(
						stylize(ST_PATH, path), _(u'ACLs')
							if dir_info.root_dir_acl else _(u'posix perms')))

			# deal with root dir
			for event in check_perms(is_root_dir=True, file_type=S_IFDIR,
							dir_info=dir_info_root, batch=batch,
							auto_answer=auto_answer, full_display=full_display):
				yield event

			if dir_info.files_perm != None or dir_info.dirs_perm != None:
				try:
					exclude_list = dir_info.exclude

				except AttributeError :
					exclude_list = []

			if dir_info.files_perm != None:
				if full_display:
					logging.progress(_(u'Checking {1} on {0} contents…').format(
							stylize(ST_PATH, path), _(u'ACLs')
								if dir_info.content_acl else _(u'posix perms')))

				if dir_info.dirs_perm != None:
					itype = (S_IFREG, S_IFDIR)

				else:
					itype = (S_IFREG,)

				for entry, etype in minifind(path, itype=itype,
									exclude=exclude_list, mindepth=1,
									yield_type=True):

						dir_info.path = entry
						for event in check_perms(file_type=etype,
												dir_info=dir_info,
												batch=batch,
												auto_answer=auto_answer,
												full_display=full_display):
							yield event

		else:
			logging.warning2(_(u'Not touching %s, it is not a file nor a '
														u'directory.') % path)

	# NOTE: below this point, every dir_info must be copy()ed, else next check
	# procedure will fail because we would have changed them in place.

	if dirs_infos != None:

		# first, check default rule, if it exists. /home/groups, /home/archives
		# and such kind of 'base paths' don't have any, and it is perfectly
		# normal... But home dirs and group shared dirs should have one.
		try:
			for event in check_one_dir_and_acl(dirs_infos._default.copy()):
				yield event

		except AttributeError:
			pass

		# check all specials_dirs, those who have custom rules.
		for dir_info in dirs_infos:
			for event in check_one_dir_and_acl(dir_info.copy()):
				yield event
	else:
		raise exceptions.BadArgumentError(
			_(u'You must pass something through dirs_infos to check!'))

	assert ltrace_func(TRACE_FSAPI, True)
def check_utf8_filename(path, batch=False, auto_answer=None, full_display=True):
	try:
		# try to decode the filename to unicode. If this fails, we need
		# to rename the file to something better, else all logging() operation
		# will fail on this file.
		return u'%s' % path

	except UnicodeDecodeError:
		valid_name = path.decode('utf8', 'replace')

		if batch or logging.ask_for_repair(_(u'Invalid utf8 filename '
							u'"{0}". Rename it?').format(
								stylize(ST_PATH, valid_name)),
						auto_answer=auto_answer):

			splitted = os.path.splitext(valid_name)
			new_name = u'{0}{1}{2}'.format(splitted[0],
						_(u' (invalid utf8 filename)'), splitted[1])

			# Avoid overwriting an existing file.
			counter = 1
			while os.path.exists(new_name):
				new_name = u'{0}{1}{2}'.format(splitted[0],
						_(u' (invalid utf8 filename, copy #{0})').format(counter),
						 splitted[1])
				counter += 1

			os.rename(path, new_name)

			if full_display:
				logging.info(_(u'Renamed file {0} to {1}.').format(
									stylize(ST_PATH, valid_name),
									stylize(ST_PATH, new_name)))
			return new_name
		else:
			raise exceptions.LicornCheckError(_(u'File {0} has an invalid utf8 '
				u'filename, it must be renamed before beiing checked further.'))
def check_perms(dir_info, file_type=None, is_root_dir=False,
					batch=False, auto_answer=None, full_display=True):
	""" general function to check if permissions are ok on file/dir """

	assert ltrace_func(TRACE_FSAPI)

	try:
		path = check_utf8_filename(dir_info.path, batch=batch,
											auto_answer=auto_answer,
											full_display=full_display)
	except (OSError, IOError):
		# this can fail if an inotify event is catched on a transient file
		# (just created, just deleted), like mkstemp() ones.
		logging.warning2(_(u'fsapi.check_perms(): exception while checking '
			u'filename validity of {0}.').format(stylize(ST_PATH, path)))
		pyutils.print_exception_if_verbose()
		return

	except exceptions.LicornCheckError:
		if batch:
			return
		else:
			raise

	# get the access_perm and the type of perm (POSIX1E or POSIX) that will be
	# applyed on path
	if file_type == S_IFDIR:
		if is_root_dir:
			access_perm = dir_info.root_dir_perm
			perm_acl    = dir_info.root_dir_acl

		else:
			access_perm = dir_info.dirs_perm
			perm_acl    = dir_info.content_acl
	else:
		access_perm = dir_info.files_perm
		perm_acl    = dir_info.content_acl

		if not perm_acl and access_perm == 00644:
			# fix #545 : NOACL should retain the exec bit on files
			perm = execbits2str(path, check_other=True)
			if perm[0] == "x": # user
				access_perm += S_IXUSR

			if perm[1] == "x": # group
				access_perm += S_IXGRP

			if perm[2] == "x": # other
				access_perm += S_IXOTH

	# if we are going to set POSIX1E acls, check '@GX' or '@UX' vars
	if perm_acl:
		# FIXME : allow @X only.

		try:
			execperms = execbits2str(path)

		except (IOError, OSError):
			# this can fail if an inotify event is catched on a transient file
			# (just created, just deleted), like mkstemp() ones.
			logging.warning2(_(u'fsapi.check_perms(): exception while '
				u'`execbits2str()` on {0}.').format(stylize(ST_PATH, path)))
			pyutils.print_exception_if_verbose()
			return

		if '@GX' in access_perm or '@UX' in access_perm:
			access_perm = access_perm.replace(
							'@GX', execperms[1]).replace(
							'@UX', execperms[0])

		access_perm = posix1e.ACL(text='%s' % access_perm)

	if is_root_dir:
		gid = dir_info.root_gid

	elif dir_info.content_gid is not None:
		gid = dir_info.content_gid

	else:
		gid = dir_info.root_gid

	uid = dir_info.uid

	for event in check_uid_and_gid(path=path,
						uid=uid, gid=gid,
						batch=batch,
						full_display=full_display):
		yield event

	if full_display:
		logging.progress(_(u'Checking {perm_type} of {path}.').format(
				perm_type=_(u'POSIX.1e ACL')
					if perm_acl else _(u'posix perms'),
				path=stylize(ST_PATH, path)))

	if perm_acl:
		# apply posix1e access perm on the file/dir
		try:
			current_perm = posix1e.ACL(file=path)

		except (IOError, OSError), e:
			# this can fail if an inotify event is catched on a transient file
			# (just created, just deleted), like mkstemp() ones.
			logging.warning(_(u"Exception while trying to "
				u"get the posix.1e ACL of {0}.").format(stylize(ST_PATH, path)))
			pyutils.print_exception_if_verbose()
			return

		if current_perm != access_perm:

			if batch or logging.ask_for_repair(
							_(u'Invalid access ACL for {path} '
								u'(it is {current_acl} but '
								u'should be {access_acl}).').format(
								path=stylize(ST_PATH, path),
								current_acl=stylize(ST_BAD,
											_(u'empty')
												if current_perm.to_any_text(
													separator=',',
													options=posix1e.TEXT_ABBREVIATE
													| posix1e.TEXT_SOME_EFFECTIVE) == ''
												else current_perm.to_any_text(
													separator=',',
													options=posix1e.TEXT_ABBREVIATE
													| posix1e.TEXT_SOME_EFFECTIVE)),
								access_acl=stylize(ST_ACL,
												access_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE))),
							auto_answer=auto_answer):

					try:
						# yield the applied event, to be catched in the
						# inotifier part of the core, who will build an
						# expected event from it.
						yield path

						# be sure to pass an str() to acl.applyto(), else it will
						# raise a TypeError if onpath is an unicode string…
						# (checked 2006 08 08 on Ubuntu Dapper)
						# TODO: recheck this, as we don't use any unicode strings
						# anywhere (or we are before the move to using them
						# everywhere).
						posix1e.ACL(acl=access_perm).applyto(str(path),
														posix1e.ACL_TYPE_ACCESS)

						if full_display:
							logging.info(
								_(u'Applyed access ACL '
								u'{access_acl} on {path}.').format(
									access_acl=stylize(ST_ACL,
												access_perm.to_any_text(
													separator=',',
													options=posix1e.TEXT_ABBREVIATE
													| posix1e.TEXT_SOME_EFFECTIVE)),
									path=stylize(ST_PATH, path)))
					except (IOError, OSError), e:
						if e.errno == errno.ENOENT:
							logging.warning2(_(u'fsapi.check_perms(): error '
								u'on {0}: {1}').format(stylize(ST_PATH, path), e))
							return
						else:
							logging.warning(_(u"Exception encoutered while "
											u"trying to set a posix.1e ACL "
											u"on {0}.").format(path))
							pyutils.print_exception_if_verbose()
							return

			else:
				all_went_ok = False

		# if it is a directory, apply default ACLs
		if file_type == S_IFDIR:
			current_default_perm = posix1e.ACL(filedef=path)

			if dir_info.dirs_perm != None and ':' in str(dir_info.dirs_perm):
				default_perm = dir_info.dirs_perm

			else:
				default_perm = dir_info.root_dir_perm

			default_perm = posix1e.ACL(text=default_perm)

			if current_default_perm != default_perm:

				if batch or logging.ask_for_repair(
							_(u'Invalid default ACL for {path} '
							u'(it is {current_acl} but '
							u'should be {access_acl}).').format(
								path=stylize(ST_PATH, path),
								current_acl=stylize(ST_BAD,
									_(u'empty')
										if 	current_default_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE) == ''
										else current_default_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE)),
								access_acl=stylize(ST_ACL,
											default_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE))),
							auto_answer=auto_answer):

					try:
						# yield the applied event, to be catched in the
						# inotifier part of the core, who will build an
						# expected event from it.
						yield path

						# Don't remove str() (see above).
						default_perm.applyto(str(path),
												posix1e.ACL_TYPE_DEFAULT)

						if full_display:
							logging.info(
									_(u'Applyed default ACL {access_acl} '
									u'on {path}.').format(
										path=stylize(ST_PATH, path),
										access_acl=stylize(ST_ACL,
											default_perm.to_any_text(
												separator=',',
												options=posix1e.TEXT_ABBREVIATE
												| posix1e.TEXT_SOME_EFFECTIVE)
									)))
					except (IOError, OSError), e:
						if e.errno == errno.ENOENT:
							logging.warning2(_(u'fsapi.check_perms(): error '
								u'on {0}: {1}').format(stylize(ST_PATH, path), e))
							return

						else:
							logging.warning(_(u"Exception encoutered while "
								u"trying to set a posix.1e default ACL "
								u"on {0}.").format(path))
							pyutils.print_exception_if_verbose()
							return

				else:
					all_went_ok = False
	else:
		# delete previous ACL perms in case of existance
		try:
			extended_acl = has_extended_acl(path)

		except (IOError, OSError), e:
				logging.warning(_(u"Exception while trying to find if {0} "
					u"holds an ACL or not.").format(stylize(ST_PATH, path)))
				pyutils.print_exception_if_verbose()
				return

		if extended_acl:
			# if an ACL is present, this could be what is borking the Unix mode.
			# an ACL is present if it has a mask, else it is just standard posix
			# perms expressed in the ACL grammar. No mask == Not an ACL.

			if batch or logging.ask_for_repair(
							_(u'An ACL is present on {path}, '
							u'but it should not.').format(
								path=stylize(ST_PATH, path)),
							auto_answer=auto_answer):

				try:
					# if it is a directory we need to delete DEFAULT ACLs too
					if file_type == S_IFDIR:

						# yield the applied event, to be catched in the
						# inotifier part of the core, who will build an
						# expected event from it.
						yield path

						posix1e.ACL(text='').applyto(str(path),
												posix1e.ACL_TYPE_DEFAULT)

						if full_display:
							logging.info(_(u'Deleted default ACL from '
								u'{path}.').format(path=stylize(ST_PATH, path)))

					# yield the applied event, to be catched in the
					# inotifier part of the core, who will build an
					# expected event from it.
					yield path

					# delete ACCESS ACLs if it is a file or a directory
					posix1e.ACL(text='').applyto(str(path),
						posix1e.ACL_TYPE_ACCESS)

					if full_display:
						logging.info(_(u'Deleted access ACL from '
							u'{path}.').format(path=stylize(ST_PATH, path)))

				except (IOError, OSError), e:
					logging.warning(_(u"Exception while "
						u"trying to delete the posix.1e ACL "
						u"on {0}.").format(stylize(ST_PATH, path)))
					pyutils.print_exception_if_verbose()
					return

			else:
				all_went_ok = False

		try:
			pathstat     = os.lstat(path)
			current_perm = pathstat.st_mode & 07777

		except (IOError, OSError), e:
			logging.warning(_(u"Exception while "
				u"trying to `lstat()` {0}.").format(stylize(ST_PATH, path)))
			pyutils.print_exception_if_verbose()
			return

		if current_perm != access_perm:

			if batch or logging.ask_for_repair(
							_(u'Invalid POSIX permissions for {path} '
							u'(it is {current_mode} but '
							u'should be {wanted_mode}).').format(
								path=stylize(ST_PATH, path),
								current_mode=stylize(ST_BAD,
									perms2str(current_perm)),
								wanted_mode=stylize(ST_ACL,
									perms2str(access_perm))),
							auto_answer=auto_answer):
					try:
						# yield the applied event, to be catched in the
						# inotifier part of the core, who will build an
						# expected event from it.
						yield path

						os.chmod(path, access_perm)

						if full_display:
							logging.info(_(u'Applyed POSIX permissions '
								u'{wanted_mode} on {path}.').format(
									wanted_mode=stylize(ST_ACL,
										perms2str(access_perm)),
									path=stylize(ST_PATH, path)))

					except (IOError, OSError), e:
						logging.warning(_(u"Exception while "
							u"trying to change posix permissions "
							u"on {0}.").format(stylize(ST_PATH, path)))
						pyutils.print_exception_if_verbose()
						return

			else:
				all_went_ok = False

	assert ltrace_func(TRACE_FSAPI, True)
def check_uid_and_gid(path, uid=-1, gid=-1, batch=None, auto_answer=None,
														full_display=True):
	""" function that check the uid and gid of a file or a dir. """

	users = LMC.users
	groups = LMC.groups

	if full_display:
		logging.progress(_(u'Checking POSIX uid/gid/perms of %s.') %
													stylize(ST_PATH, path))
	try:
		pathstat = os.lstat(path)

	except (IOError, OSError), e:
			# causes of this error:
			#     - this is a race condition: the dir/file has been deleted
			#		between the minifind() and the check_*() call.
			#		Don't blow out on this.
			#     - when we explicitely want to check a path which does not
			#		exist because it has not been created yet (eg: ~/.dmrc
			#		on a brand new user account).
		logging.warning(_(u"Exception while trying to `lstat()` "
						u"{0}.").format(stylize(ST_PATH, path)))
		pyutils.print_exception_if_verbose()
		return

	# if one or both of the uid or gid are empty, don't check it, use the
	# current one present in the file meta-data.
	if uid == -1:
		uid = pathstat.st_uid
		try:
			desired_login = users[uid].login

		except KeyError:
			desired_login = 'root'
			uid           = 0
	else:
		try:
			desired_login = users.uid_to_login(uid)

		except exceptions.DoesntExistException:
			desired_login = 'root'
			uid           = 0

	if gid == -1:
		gid = pathstat.st_gid
		try:
			desired_group = groups[gid].name

		except KeyError:
			desired_group = gid
	else:
		desired_group = groups.gid_to_name(gid)

	if pathstat.st_uid != uid or pathstat.st_gid != gid:

		if batch or logging.ask_for_repair(_(u'Invalid owership for {0}: '
						u'currently {1}:{2} but should be {3}:{4}. '
						u'Correct it?').format(
							stylize(ST_PATH, path),
							stylize(ST_BAD, users[pathstat.st_uid].login
								if pathstat.st_uid in users.iterkeys()
								else str(pathstat.st_uid)),
							stylize(ST_BAD, groups[pathstat.st_gid].name
								if pathstat.st_uid in groups.iterkeys()
								else str(pathstat.st_gid)),
							stylize(ST_UGID, desired_login),
							stylize(ST_UGID, desired_group),
						),
						auto_answer=auto_answer):

			try:
				# yield the applied event, to be catched in the
				# inotifier part of the core, who will build an
				# expected event from it.
				yield path

				os.chown(path, uid, gid)

				if full_display:
					logging.info(_(u'Changed owner of {0} '
									u'to {1}:{2}.').format(
										stylize(ST_PATH, path),
										stylize(ST_UGID, desired_login),
										stylize(ST_UGID, desired_group)))

			except (IOError, OSError), e:
				if e.errno == 2: return
				else: raise e

			return
		else:
			logging.warning2(_(u'Invalid owership for {0}: '
						u'currently {1}:{2} but should be {3}:{4}.').format(
					stylize(ST_PATH, path),
					stylize(ST_BAD, LMC.users[pathstat.st_uid].login
						if pathstat.st_uid in LMC.users.iterkeys()
						else str(pathstat.st_uid)),
					stylize(ST_BAD, LMC.groups[pathstat.st_gid].name
						if pathstat.st_uid in LMC.groups.iterkeys()
						else str(pathstat.st_gid)),
					stylize(ST_UGID, desired_login),
					stylize(ST_UGID, desired_group),
				))
			return
def make_symlink(link_src, link_dst, batch=False, auto_answer=None):
	"""Try to make a symlink cleverly."""
	try:
		os.symlink(link_src, link_dst)
		logging.info(_(u'Created symlink {link}, pointing to {orig}.').format(
							link=stylize(ST_LINK, link_dst),
							orig=stylize(ST_PATH, link_src)))
	except OSError, e:
		if e.errno == 17:
			# 17 == file exists
			if os.path.islink(link_dst):
				try:
					read_link = os.path.abspath(os.readlink(link_dst))

					if read_link != link_src:
						if os.path.exists(read_link):
							if batch or logging.ask_for_repair(
											_(u'A symlink {link} '
											u'already exists, but points '
											u'to {dest}, instead of {good}. '
											u'Correct it?').format(
											link=stylize(ST_LINK, link_dst),
											dest=stylize(ST_PATH, read_link),
											good=stylize(ST_PATH, link_src)
										),
										auto_answer=auto_answer):

								os.unlink(link_dst)
								os.symlink(link_src, link_dst)

								logging.info(_(u'Overwritten symlink {link} '
										u'with destination {good} '
										u'instead of {dest}.').format(
										link=stylize(ST_LINK, link_dst),
										good=stylize(ST_PATH, link_src),
										dest=stylize(ST_PATH, read_link))
									)
							else:
								raise exceptions.LicornRuntimeException(
									_(u'Cannot create symlink {0} to {1}!').format(
										link_dst, link_src))
						else:
							# TODO: should we ask the question ? This isn't
							# really needed, as the link is broken.
							# Just replace it and don't bother the administrator.
							logging.info(_(u'Symlink {link} is currently '
									u'broken, pointing to non-existing '
									u'target {dest}); making it point '
									u'to {good}.').format(
										link=stylize(ST_LINK, link_dst),
										dest=stylize(ST_PATH, read_link),
										good=stylize(ST_PATH, link_src)
									)
								)
							os.unlink(link_dst)
							os.symlink(link_src, link_dst)

				except OSError, e:
					if e.errno == 2:
						# no such file or directory, link has disapeared…
						os.symlink(link_src, link_dst)
						logging.info(_(u'Repaired vanished symlink %s.') %
											stylize(ST_LINK, link_dst))
			else:
				if batch or logging.ask_for_repair(_(u'{link} already '
								u'exists but it is not a symlink, thus '
								u'it does not point to {dest}. '
								u'Rename and replace it with '
								u'a correct symlink?').format(
									link=stylize(ST_LINK, link_dst),
									dest=stylize(ST_PATH, link_src)
								),
								auto_answer=auto_answer):

					pathname, ext = os.path.splitext(link_dst)
					newname = _(u'{0} ({1} conflict){2}').format(pathname,
							time.strftime(_(u'%d %m %Y at %H:%M:%S')), ext)
					os.rename(link_dst, newname)
					os.symlink(link_src, link_dst)

					logging.info(_(u'Renamed {link} to {newname} '
							u'and replaced it by a symlink '
							u'pointing to {dest}.').format(
								link=stylize(ST_LINK, link_dst),
								newname=stylize(ST_PATH, newname),
								dest=stylize(ST_PATH, link_src)
							)
						)
				else:
					raise exceptions.LicornRuntimeException(_(u'While making '
						u'symlink to {dest}, the destination {link} '
						u'already exists and is not a link.').format(
							dest=link_src, link=link_dst))
def remove_directory(path):
	""" Remove a directory hierarchy. But first, rename it to something
		quite convoluted, in case the system (or administrator) wants to
		reuse the exact same name in the same place.

		.. warning:: TODO: the renaming part is left to be implemented.

		.. versionadded:: 1.3
	"""

	try:
		shutil.rmtree(path)
	except (IOError, OSError), e:
		if e.errno == 2:
			logging.info(_(u'Cannot remove %s, it does not exist!') %
													stylize(ST_PATH, path))
		else:
			raise e
def archive_directory(path, orig_name='unknown'):
	"""
		Archive a directory and all its contents in :file:`/home/archives`.

		.. warning:: this function needs `LMC.configuration` to be initialized
			before beiing called. This is a special case and will probably
			change in the near future.

		.. versionadded:: 1.3
	"""

	# /home/archives must be OK before moving
	LMC.configuration.check_base_dirs(minimal=True,	batch=True)

	group_archive_dir = "%s/%s.deleted.%s" % (
		LMC.configuration.home_archive_dir, orig_name,
		time.strftime("%Y%m%d-%H%M%S", time.gmtime()))
	try:
		os.rename(path, group_archive_dir)

		logging.info(_(u"Archived {0} as {1}.").format(
			stylize(ST_PATH, path),
			stylize(ST_PATH, group_archive_dir)))

		LMC.configuration.check_archive_dir(group_archive_dir, batch=True,
													full_display=__debug__)
	except OSError, e:
		if e.errno == 2:
			logging.info(_(u'Cannot archive %s, it does not exist!') %
				stylize(ST_PATH, path))
		else:
			raise e

# various unordered functions, which still need to find a more elegant home.

def has_extended_acl(pathname):
	# return True if the posix1e representation of pathname's ACL has a MASK.
	for acl_entry in posix1e.ACL(file = pathname):
		if acl_entry.tag_type == posix1e.ACL_MASK:
			return True
	return False

# use pylibacl 0.4.0 accelerated C function if possible.
if hasattr(posix1e, 'HAS_EXTENDED_CHECK'):
	if posix1e.HAS_EXTENDED_CHECK:
		has_extended_acl = posix1e.has_extended

def backup_file(filename):
	""" make a backup of a given file. """
	bckp_ext='.licorn.bak'
	backup_name = filename + bckp_ext
	open(backup_name, 'w').write(open(filename).read())
	os.chmod(backup_name, os.lstat(filename).st_mode)
	logging.progress(_(u'Backed up {orig} as {backup}.').format(
			orig=stylize(ST_PATH, filename),
			backup=stylize(ST_COMMENT, backup_name)))
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
def execbits2str(filename, check_other=False):
	"""Find if a file has executable bits and return (only) then as
		a list of strings, used later to build an ACL permission string.

		TODO: as these exec perms are used for ACLs only, should not
		we avoid testing setuid and setgid bits ? what does setguid
		means in a posix1e ACL ?
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

	if check_other:
		# exec bit for other ?
		if fileperms & S_IXOTH:
			execperms.append('x')
		else:
			execperms.append('-')

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
def touch(fname, times=None):
	""" this touch reimplementation comes from
	`http://stackoverflow.com/questions/1158076/implement-touch-using-python`_
	and I find it great.
	"""
	with file(fname, 'a'):
		os.utime(fname, times)
