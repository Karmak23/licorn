# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

fsapi test - testsuite for fsapi

:copyright:
	* 2012 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

import os, stat, py.test

from licorn.foundations import logging, exceptions, process, fsapi

fname  = '/tmp/test.licorn.ts'
fname2 = '/tmp/test2.licorn.ts'

def unlink_test_files():
	for f in (fname, fname + fsapi.backup_ext):
		try:
			os.unlink(f)

		except:
			#logging.exception('Cannot remove {0}', f)
			pass
def pytest_configure(config):
	unlink_test_files()
def pytest_unconfigure(config):
	unlink_test_files()

def test_touch():
	fsapi.touch(fname)
	assert os.path.exists(fname)
	assert os.stat(fname).st_size == 0
def test_remove_files():

	fsapi.touch(fname)

	# should succeed
	fsapi.remove_files(fname)
	assert not os.path.exists(fname)

	# should succeed too, because removing a non-present file is OK for us.
	fsapi.remove_files(fname)
def test_clone_stat():
	fsapi.touch(fname)

	for f in ('/etc/group', 'at.deny', 'default.ini'):
		if os.path.exists(f):
			fsapi.clone_stat(f, fname)
			ss = os.stat(f)
			ds = os.stat(fname)

			# st_ino, st_ctime and st_size won't be the same, obviously.
			# We can't compare stat() results directly.
			assert ds.st_mode == ss.st_mode
			assert ds.st_dev  == ss.st_dev
			assert ds.st_uid  == ss.st_uid
			assert ds.st_gid  == ss.st_gid

			if hasattr(os, 'utime'):
				# This fails! why ?
				#assert ds.st_atime == ss.st_atime
				assert ds.st_mtime == ss.st_mtime
def test_backup_file():

	fsapi.touch(fname)
	fsapi.backup_file(fname)

	# test file contents; the stat should have been tested by test_clone_stat()
	assert os.path.exists(fname + fsapi.backup_ext)
	assert open(fname).read() == open(fname + fsapi.backup_ext).read()
def test_has_flags_immutable():
	""" Test the chflags part. """

	if os.getuid():
		raise RuntimeError('This test must be run as ROOT, else it cannot succeed.')

	fsapi.touch(fname)

	assert fsapi.has_flags(fname, [stat.SF_IMMUTABLE]) == False

	process.execute(['chattr', '+i', fname])

	assert fsapi.has_flags(fname, [stat.SF_IMMUTABLE]) == True

	process.execute(['chattr', '-i', fname])

	assert fsapi.has_flags(fname, [stat.SF_IMMUTABLE]) == False

