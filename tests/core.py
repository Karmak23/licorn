#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn testsuite for licorn.core objects.

Copyright (C) 2007-2010 Olivier Cortès <oc@meta-it.fr>
Copyright (C) 2010 Robin Lucbernet <rl@meta-it.fr>

Licensed under the terms of the GNU GPL version 2.
"""

import gettext
gettext.install('licorn', unicode=True)

import sys, os, re, hashlib, tempfile
import gzip, time, shutil

from subprocess                import Popen, PIPE, STDOUT
from traceback                 import print_exc

from licorn.foundations        import logging, exceptions, options, settings
from licorn.foundations        import process, fsapi, pyutils, hlstr
from licorn.foundations.styles import *

from licorn.tests              import *

def prefunc():
	open(state_files['owner'], 'w').write('%s,%s' % (os.getuid(), os.getgid()))

if os.getuid() != 0 or os.geteuid() != 0:
	process.refork_as_root_or_die(process_title='licorn-testsuite',
		prefunc=prefunc)

missing_error=False
for binary in ( '/usr/bin/setfacl', '/usr/bin/attr', '/bin/chmod', '/bin/rm',
	'/usr/bin/touch', '/bin/chown', '/usr/bin/colordiff', '/usr/sbin/slapcat',
	'/usr/bin/getfacl'):
	if not os.path.exists(binary):
		missing_error=True
		logging.warning(_(u'%s does not exist on this system and is '
						u'mandatory for this testsuite.') %
							stylize(ST_PATH, binary))

if missing_error:
	logging.error(_(u'Please install missing packages before continuing.'))

if __name__ == "__main__":

	# init the TS.
	testsuite = Testsuite(name="CLI", state_file=state_files,
					directory_scenarii='data/scenarii',
					clean_func=lambda: True, cmd_display_func=small_cmd_cli)

	from global_tests import *

	# these functions come from global tests.
	test_find_new_indentifier(testsuite)
	test_integrated_help(testsuite)
	test_regexes(testsuite)
	test_short_syntax(testsuite)
	test_exclusions(testsuite)

	# can't be tested any more in background mode, it fails everytime (which
	# is normal because it contains too much moving data).
	#test_status_and_dump()

	for ctx in ('shadow', 'openldap'):
		# these function also come from global tests.
		test_get(ctx, testsuite)
		test_groups(ctx, testsuite)
		test_users(ctx, testsuite)
		test_profiles(ctx, testsuite)
		test_privileges(ctx, testsuite)
		test_imports(ctx, testsuite)

	# last test, this will kill the daemon (and it is intended).
	# NOTE: disabled for now, we must find a way to do it cleaner (in a LXC, in
	# something whatever, but not on my local machine, this is too dangerous!!)
	#test_system()

	# deals with options
	parser            = testsuite_parse_args()
	(options, args)   = parser.parse_args()
	Testsuite.verbose = options.verbose

	if not options.all and not options.list and not options.execute and \
		not options.start_from and not options.start_from and \
		not options.clean and not options.delete_trace and not options.stats:
			sys.argv.append('-a')
			(options, args) = parser.parse_args()

	if options.reload:
		testsuite.clean_state_file()

	if options.list:
		testsuite.get_scenarii()

	if options.execute:
		testsuite.select(options.execute-1)
		testsuite.interactive = True

	if options.start_from:
		testsuite.select(options.start_from, mode='start')

	if options.clean:
		testsuite.clean_scenarii_directory()

	if options.delete_trace:
		testsuite.clean_scenarii_directory(scenario_number=options.delete_trace)

	if options.stats:
		testsuite.get_stats()

	if options.batch_run:
		testsuite.batch_run = True

	if options.interactive:
		testsuite.interactive = True

	if options.all:
		if testsuite.get_state() == None:
			testsuite.select(all=True)
		else:
			testsuite.select(scenario_number=testsuite.get_state(), mode='start')

	def terminate():
		# clean the system
		clean_dir_contents(settings.home_archive_dir)

		testsuite.clean_system()
		# restore initial user backend
		testsuite.restore_user_context()
		# give back all the scenarii tree to calling user.
		uid, gid = [ int(x) for x in \
			open(state_files['owner']).read().strip().split(',') ]
		test_message(_(u'giving back all scenarii data to {0}:{1}.').format(
			stylize(ST_UGID, uid), stylize(ST_UGID, gid)))
		for entry in fsapi.minifind('data', followlinks=True):
			os.chown(entry, uid, gid)

	if options.start_from or options.execute or options.all:
		try :
			for ctx in ('shadow', 'openldap'):
				make_backups(ctx)

			clean_dir_contents(settings.home_archive_dir)

			testsuite.run()
			# compare delete backups
			for ctx in ('shadow','openldap'):
				compare_delete_backups(ctx)
			# TODO: test_concurrent_accesses()

			# no need to do this now, the TS will act smart about it.
			#testsuite.clean_state_file()

			test_message(_(u"Testsuite terminated successfully."))
			test_message(_(u"Don't forget to test massive del/mod/chk with -a "
				u"argument (not tested because too dangerous)"))
			terminate()

		except KeyboardInterrupt:
			test_message(_(u"Cleaning testsuite context, please wait…"))
			terminate()
		#finally:
		#	terminate()
