#!/usr/bin/python -OO
# -*- coding: utf-8 -*-

import sys, os, curses, re
from subprocess                import Popen, PIPE, STDOUT
from licorn.foundations        import pyutils, styles, logging, exceptions
from licorn.core.configuration import LicornConfiguration

configuration = LicornConfiguration()

if __debug__:
	PYTHON = [ 'python' ]
	verbose=True
else:
	# don't forget first ' '
	PYTHON = [ 'python', '-OO' ]
	verbose=False

CLIPATH='../interfaces/cli'
ADD   =PYTHON + [ CLIPATH + '/add.py']
DELETE=PYTHON + [ CLIPATH + '/del.py']
MODIFY=PYTHON + [ CLIPATH + '/mod.py']
GETENT=PYTHON + [ CLIPATH + '/get.py']
CHECK =PYTHON + [ CLIPATH + '/chk.py']

system_files = ( 'passwd', 'shadow', 'group', 'gshadow', 'adduser.conf',
				'login.defs', 'licorn/main.conf', 'licorn/group',
				'licorn/profiles.xml')

bkp_ext = 'licorn'

if len(sys.argv) > 1:
	args = sys.argv[1:]
else:
	args = []

for binary in ( '/usr/bin/setfacl', '/usr/bin/attr', '/bin/chmod', '/bin/rm',
	'/usr/bin/touch', '/bin/chown', '/usr/bin/colordiff' ):
	if not os.path.exists(binary):
		logging.error('%s does not exist on this system and is mandatory for this testsuite.' % binary)

curses.setupterm()
clear = curses.tigetstr('clear')

def clear_term():
	sys.stdout.write(clear)
	sys.stdout.flush()

def cmdfmt(cmd):
	'''convert a sequence to a colorized string.'''
	return styles.stylize(styles.ST_NAME, ' '.join(cmd))

def test_message(msg):
	""" display a message to stderr. """
	sys.stderr.write("%s>>> %s%s\n"
		% (styles.colors[styles.ST_LOG], msg, styles.colors[styles.ST_NO]) )

def log_and_exec (command, inverse_test=False, result_code=0, comment="",
	verb=verbose):
	"""Display a command, execute it, and exit if soemthing went wrong."""

	#if not command.startswith('colordiff'):
	#	command += ' %s' % ' '.join(args)

	sys.stderr.write("%s>>> running %s%s%s\n" % (styles.colors[styles.ST_LOG],
		styles.colors[styles.ST_PATH], command, styles.colors[styles.ST_NO]))

	output, retcode = execute(command)
	must_exit = False

	#
	# TODO: implement a precise test on a precise exit value.
	# for example, when you try to add a group with an invalid name,
	# licorn-add should exit (e.g.) 34. We must test on this precise
	# value and not on != 0, because if something wrong but *other* than
	# errno 34 happened, we won't know it if we don't check carefully the
	# program output.
	#

	if inverse_test:
		if retcode != result_code:
			must_exit = True
	else:
		if retcode != 0:
			must_exit = True

	if must_exit:
		if inverse_test:
			test = ("	%s→ it should have failed with reason: %s%s%s\n"
				% (styles.colors[styles.ST_PATH], styles.colors[styles.ST_BAD],
					comment, styles.colors[styles.ST_NO]))
		else:
			test = ""

		sys.stderr.write("	%s→ return code of command: %s%d%s (expected: %d)%s\n%s	→ log follows:\n"
			% (	styles.colors[styles.ST_LOG], styles.colors[styles.ST_BAD],
				retcode, styles.colors[styles.ST_LOG], result_code,
				styles.colors[styles.ST_NO], test) )
		sys.stderr.write(output)
		sys.stderr.write(
			"The last command failed to execute, or return something wrong !\n")
		raise SystemExit(retcode)

	if verb:
		sys.stderr.write(output)

def execute(cmd):
	#logging.notice('running %s.' % ' '.join(cmd))
	p4 = Popen(cmd, shell=False,
		  stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
	output = p4.stdout.read()
	retcode = p4.wait()
	return output, retcode
def strip_dates(str):
	""" strip dates from warnings and traces, else outputs and references
	always compare false ."""
	return re.sub(r'\s\[\d\d\d\d/\d\d/\d\d\s\d\d:\d\d:\d\d\.\d\d\d\d\]\s',
		r' [D/T] ', str)

class FunctionnalTest:
	counter = 0

	def __init__(self, cmd, pre_cmds=[], chk_cmds=[], manual_output=False,
		reference_cmd=[], context='std'):

		if type(cmd) == type(''):
			self.cmd = cmd.split(' ')
		else:
			self.cmd = cmd

		self.pre_cmds      = pre_cmds
		self.chk_cmds      = chk_cmds
		self.reference_cmd = reference_cmd
		self.context       = context
		self.manual_output = manual_output
		FunctionnalTest.counter += 1
	def Prepare(self, cmd):
		""" Run commands mandatory for func_test to succeed. """

		make_path = lambda x: ('_'.join(x)).replace('../', '').replace('//','_').replace('/','_')

		out_path = 'data/'

		if self.reference_cmd != []:
			out_path += 'ref_%s/' % make_path(self.reference_cmd)

		if self.pre_cmds != []:
			logging.progress('preparing system for cmd %s.' % cmd)
			for cmd in self.pre_cmds:
				out_path += 'pre_%s/' % make_path(cmd)
				# shouldn't this turned into a FunctionnalTest either ?
				execute(cmd)

		out_path += 'cmd_%s/context_%s' % (make_path(cmd), self.context)
		self.ref_output_file = '%s/out.txt' % out_path
		self.ref_code_file   = '%s/code.txt' % out_path

	def SaveOutput(self, output, code):

		try:
			os.makedirs(os.path.dirname(self.ref_output_file))
		except (OSError, IOError), e:
			if e.errno != 17:
				raise e

		open(self.ref_output_file, 'w').write(strip_dates(output))
		#logging.notice('written output file %s.' % self.ref_output_file)

		open(self.ref_code_file, 'w').write(str(code))
		#logging.notice('written code reference in %s.' % self.ref_code_file)

	def PrepareReferenceOutput(self, cmd):

		if os.path.exists(self.ref_output_file):
			return (open(self.ref_output_file).read(),
				int(open(self.ref_code_file).read()))
		else:
			clear_term()
			logging.notice('no reference output for cmd #%d "%s" [%scontext=%s], creating one…' % (
			FunctionnalTest.counter, cmdfmt(cmd),
				'referer=%s, ' % cmdfmt(self.reference_cmd) \
					if self.reference_cmd != [] else '',
				self.context))

			output, retcode = execute(cmd)

			sys.stderr.write(strip_dates(output))

			if logging.ask_for_repair('is this output good to keep as reference for future runs?'):
				# Save the output AND the return code for future references and comparisons
				self.SaveOutput(output, retcode)
				# return them for current test, strip_dates to avoid an
				# immediate false negative.
				return (strip_dates(output), retcode)
			else:
				logging.error('you MUST have a reference output; please fix code or rerun this test.')
	def RunAndCheck(self, cmd, batch = False, inverse_test=False):
		ref_output, ref_code = self.PrepareReferenceOutput(cmd)

		output, retcode = execute(cmd)

		bad_run = False
		message = ''

		if retcode != ref_code:
			logging.warning('command "%s" failed (retcode %d instead of %d).\nPath: %s' % (
				cmdfmt(cmd), retcode, ref_code, self.ref_code_file))
			if batch or logging.ask_for_repair(
				'Should I keep the new return code as reference for future runs?'):
				self.SaveOutput(output, retcode)
			else:
				raise exceptions.LicornRuntimeException(
					'command "%s" failed.\nPath: %s.' % (cmdfmt(cmd), self.ref_output_file))

		if ref_output != strip_dates(output):
			# TODO: tempfile -> write -> colordiff
			logging.warning('command "%s" failed.\nPath: %s.\n%s New output follows:' % (
				cmdfmt(cmd), self.ref_output_file, '-' * 50))
			sys.stdout.write(strip_dates(output) + ('-' * 50) + '\n')

			if batch or logging.ask_for_repair(
				'Should I keep this new trace as reference for future runs?'):
				self.SaveOutput(output, retcode)
			else:
				raise exceptions.LicornRuntimeException(
					'command "%s" failed.\nPath: %s.' % (cmdfmt(cmd), self.ref_output_file))

		logging.notice('command #%d "%s" completed successfully [%scontext=%s,retcode=%d].' % (
			FunctionnalTest.counter, cmdfmt(cmd),
				'referer=%s, ' % cmdfmt(self.reference_cmd) \
					if self.reference_cmd != [] else '',
				self.context, retcode))
	def Run(self, options=[], batch=False, inverse_test=False):

		#test_message('running #%d "%s".' % (FunctionnalTest.counter, cmdfmt(self.cmd)))

		if self.manual_output:
			if batch:
				logging.warning('batch mode, cmd "%s" not tested !' % \
					cmdfmt(self.cmd))
			else:
				clear_term()
				test_message('running #%d "%s" for manual check…' % (
					FunctionnalTest.counter, cmdfmt(self.cmd)))
				sys.stderr.write(execute(self.cmd)[0])
				return logging.ask_for_repair(
					'does this output seems right to you for this command?')
		else:
			# run the command once, without any options.
			self.Prepare(self.cmd)
			self.RunAndCheck(self.cmd, batch=batch, inverse_test=inverse_test)
			for chk_cmd in self.chk_cmds:
				FunctionnalTest(chk_cmd, reference_cmd=self.cmd).Run()

			for option in options:
				# XXX: turn this into another FunctionnalTest() instance ?
				FunctionnalTest.counter += 1
				self.Prepare(self.cmd + option)
				self.RunAndCheck(self.cmd + option, batch=batch,
					inverse_test=inverse_test)
				for chk_cmd in self.chk_cmds:
					FunctionnalTest(chk_cmd, reference_cmd=self.cmd).Run()

def test_integrated_help ():
	"""Test extensively argmarser contents and intergated help."""

	test_message('testing integrated help.')

	for program in (GETENT, ADD, MODIFY, DELETE, CHECK):

		FunctionnalTest(program).Run(options = [['-h'], ['--help']])

		if program == ADD:
			modes = [ 'user', 'users', 'group', 'profile' ]
		elif program == MODIFY:
			modes = [ 'configuration', 'user', 'group', 'profile' ]
		elif program == DELETE:
			modes = [ 'user', 'group', 'groups', 'profile' ]
		elif program == GETENT:
			modes = ['user', 'users', 'passwd', 'group', 'groups', 'profiles',
				'configuration' ]
		elif program == CHECK:
			modes = ['user', 'users', 'group', 'groups', 'profile', 'profiles',
				'configuration' ]

		for mode in modes:
			if program == GETENT and mode == 'configuration':
				FunctionnalTest(program + [mode]).Run()
			else:
				FunctionnalTest(program + [mode]).Run(options = [['-h'],
					['--help']])

	test_message('integrated help testing finished.')

def test_get(context):
	"""Test GET a lot."""

	test_message('''starting get tests.''')

	for category in [ 'config_dir', 'main_config_file',
		'extendedgroup_data_file' ]:
		for mode in [ '', '-s', '-b', '--bourne-shell', '-c', '--c-shell',
			'-p', '--php-code' ]:
			FunctionnalTest(GETENT + [ 'configuration', category, mode ],
				context=context).Run()

	for category in [ 'skels', 'shells', 'backends' ]:
		FunctionnalTest(GETENT + [ 'config', category ], context=context).Run()

	commands = (
		# users
		GETENT + [ "users" ],
		GETENT + [ "users", "--xml" ],
		GETENT + [ "users", "--long" ],
		GETENT + [ "users", "--long", "--xml" ],
		GETENT + [ "users", "--all" ],
		GETENT + [ "users", "--xml", "--all" ],
		GETENT + [ "users", "--all", "--long" ],
		GETENT + [ "users", "--xml", "--all", "--long" ],
		# groups
		GETENT + [ "groups" ],
		GETENT + [ "groups", "--xml" ],
		GETENT + [ "groups", "--long" ],
		GETENT + [ "groups", "--long", "--xml" ],
		GETENT + [ "groups", "--xml", "--all" ],
		GETENT + [ "groups", "--xml", "--all", "--long" ],
		GETENT + [ "groups", "--xml", "--guests" ],
		GETENT + [ "groups", "--xml", "--guests", "--long " ],
		GETENT + [ "groups", "--xml", "--responsibles" ],
		GETENT + [ "groups", "--xml", "--responsibles", "--long" ],
		GETENT + [ "groups", "--xml", "--privileged" ],
		GETENT + [ "groups", "--xml", "--privileged", "--long" ],
		# Profiles
		GETENT + [ "profiles" ],
		GETENT + [ "profiles", "--xml" ],
		)

	for command in commands:
		FunctionnalTest(command, context=context)

	test_message('''`get` tests finished.''')

def test_find_new_indentifier():
	#test_message('''starting identifier routines tests.''')
	assert(pyutils.next_free([5,6,48,2,1,4], 5, 30) == 7)
	assert(pyutils.next_free([5,6,48,2,1,4], 1, 30) == 3)
	assert(pyutils.next_free([1,3], 1, 30) == 2)
	try:
		pyutils.next_free([1,2], 1, 2)
	except:
		assert(True) # good behaviour
	else:
		assert(False)

	assert(pyutils.next_free([1,2], 1, 30) == 3)
	assert(pyutils.next_free([1,2,4,5], 3, 5) == 3)
	#test_message('''identifier routines tests finished.''')
def test_regexes():
	""" Try funky strings to make regexes fail (they should not)."""

	# TODO: test regexes directly from defs in licorn.core....

	test_message('''starting regexes tests.''')
	regexes_commands = []

	# groups related
	regexes_commands.extend([
		ADD   + [ 'group', "--name='_-  -_'"],
		CHECK + [ 'group', "--name='_-  -_'"],
		ADD   + [ 'group', "--name=';-)'"],
		ADD   + [ 'group', "--name='^_^'"],
		ADD   + [ 'group', "--name='le copain des groupes'"],
		CHECK + [ 'group', '-v', "--name='le copain des groupes'"],
		ADD   + [ 'group', "--name='héhéhé'"],
		ADD   + [ 'group', "--name='%(\`ls -la /etc/passwd\`)'"],
		ADD   + [ 'group', "--name='echo print coucou | python | nothing'"],
		ADD   + [ 'group', "--name='**/*-'"],
		CHECK + [ 'group', '-v', "--name='**/*-'"]
		])

	# users related
	regexes_commands.extend([
		ADD + [ 'user', "--login='_-  -_'"],
		ADD + [ 'user', "--login=';-)'"],
		ADD + [ 'user', "--login='^_^'"],
		ADD + [ 'user', "--login='le copain des utilisateurs'"],
		ADD + [ 'user', "--login='héhéhé'"],
		ADD + [ 'user', "--login='%(\`ls -la /etc/passwd\`)'"],
		ADD + [ 'user', "--login='echo print coucou | python'"],
		ADD + [ 'user', "--login='**/*-'"]
		])

	for cmd in regexes_commands:
		FunctionnalTest(cmd).Run()

	# TODO: profiles ?

	test_message('''regexes tests finished.''')

def clean_system():
	""" Remove all stuff to make the system clean, testsuite-wise."""

	test_message('''cleaning system from previous runs.''')

	# delete them first in case of a previous failed testsuite run.
	# don't check exit codes or such, this will be done later.

	for argument in (
		['user', 'toto'],
		['user', 'tutu'],
		['user', 'tata'],
		['user', '--login=utilisager.normal'],
		['user', '--login=test.responsibilly'],
		['user', '--login=utilicateur.accentue'],
		['profile', '--group=utilisagers', '--del-users', '--no-archive'],
		['profile', '--group=responsibilisateurs', '--del-users',
			'--no-archive'],
		['group', '--name=test_users_A'],
		['group', '--name=test_users_B'],
		['group', '--name=groupeA'],
		['group', '--name=B-Group_Test'],
		['group', '--name=groupe_a_skel']
	):

		execute(DELETE + argument)

		os.system('rm -rf %s/* %s/*' % (configuration.home_backup_dir,
			configuration.home_archive_dir))

	test_message('''system cleaned from previous testsuite runs.''')

def make_backups(mode):
	"""Make backup of important system files before messing them up ;-) """

	if mode == 'unix':
		for file in system_files:
			if os.path.exists('/etc/%s' % file):
				execute(['cp', '-f', '/etc/' + file,
					'/tmp/%s.bak.%s' % (file.replace('/', '_'), bkp_ext)])

	elif mode == 'ldap':
		execute(['slapcat', '-l', '/tmp/backup.1.ldif'])

	else:
		logging.error('backup mode not understood.')

	test_message('''made backups of system config files.''')
def compare_delete_backups(mode):
	test_message('''comparing backups of system files after tests for side-effects alterations.''')

	if mode == 'unix':

		for file in system_files:
			if os.path.exists('/etc/%s' % file):
				log_and_exec(['/usr/bin/colordiff', '/etc/%s' % file,
					'/tmp/%s.bak.%s' % (file.replace('/', '_'), bkp_ext)], False,
				comment="should not display any diff (system has been cleaned).",
				verb = True)
				execute(['rm', '/tmp/%s.bak.%s' % (file.replace('/', '_'), bkp_ext)])

	elif mode == 'ldap':
		execute(['slapcat', '-l', '/tmp/backup.2.ldif'])
		log_and_exec(['/usr/bin/colordiff', '/tmp/backup.1.ldif', '/tmp/backup.2.ldif'],
			False,
			comment="should not display any diff (system has been cleaned).",
			verb = True)
		execute(['rm', '/tmp/backup.1.ldif', '/tmp/backup.2.ldif'])

	else:
		logging.error('backup mode not understood.')

	test_message('''system config files backup comparison finished successfully.''')

def test_groups(context):
	"""Test ADD/MOD/DEL on groups in various ways."""

	test_message('''starting groups related tests.''')

	group_name = 'groupeA'

	def gen_chk_acls_cmds(group):

		return [ 'getfacl', '-R', '%s/%s/%s' % (
		configuration.defaults.home_base_path,
		configuration.groups.names['plural'],
		group) ]

	FunctionnalTest(
		ADD + [ 'group', '--name=%s' % group_name ],
		chk_cmds = [ gen_chk_acls_cmds(group_name) ],
		context=context+'+already').Run()

	# re-run the ADD command and verify it fails.
	FunctionnalTest(
		ADD + [ 'group', '--name=%s' % group_name ],
		chk_cmds = [ gen_chk_acls_cmds(group_name) ],
		context=context).Run(inverse_test=True)

	# completeny remove the shared group dir and verify CHK repairs it.
	remove_group_cmds = [ "rm", "-rf", "%s/%s/%s" % (
		configuration.defaults.home_base_path,
		configuration.groups.names['plural'],
		group_name), ">/dev/null", "2>&1" ]

	# idem with public_html shared subdir.
	remove_group_html_cmds = [ "rm", "-rf",
		"%s/%s/%s/public_html" % (
		configuration.defaults.home_base_path,
		configuration.groups.names['plural'],
		group_name), ">/dev/null", "2>&1" ]

	# remove the posix ACLs and let CHK correct everything (after having
	# declared an error first with --auto-no).
	remove_group_acls_cmds = [ "setfacl", "-R", "-b", "%s/%s/%s" % (
		configuration.defaults.home_base_path,
		configuration.groups.names['plural'],
		group_name), ">/dev/null", "2>&1" ]

	# idem for public_html subdir.
	remove_group_html_acls_cmds = [ "setfacl", "-R", "-b",
		"%s/%s/%s/public_html" % (
		configuration.defaults.home_base_path,
		configuration.groups.names['plural'],
		group_name), ">/dev/null", "2>&1" ]

	bad_chown_group_cmds = ['chown', 'bin:daemon', '%s/%s/%s/public_html' % (
		configuration.defaults.home_base_path,
		configuration.groups.names['plural'],
		group_name),
		'>/dev/null', '2>&1']

	for pre_cmd in (remove_group_cmds, remove_group_html_cmds,
		remove_group_acls_cmds, remove_group_html_acls_cmds,
		bad_chown_group_cmds):

		for subopt in ('--auto-no', '--auto-yes', '-b'):
			FunctionnalTest(
				CHECK + [ 'group', '--name=%s' % group_name, subopt],
				pre_cmds = [ remove_group_acls_cmds],
				chk_cmds = [ gen_chk_acls_cmds(group_name) ],
				context=context).Run(options = [['-v'], ['-ve'], ['-vv'], ['-vve']])

	# should fail
	FunctionnalTest(MODIFY + [ "group", "--name=%s" % group_name,
		"--skel=/etc/doesntexist" ],context=context).Run()

	# delete it from the system, not to pollute
	FunctionnalTest(DELETE + [ 'group', '--name', group_name, '--del-users',
		'--no-archive'], context=context).Run()

	group_name = 'B-Group_Test'

	FunctionnalTest(ADD + [ 'group', "--name=%s" % group_name, "--system" ],
		context=context).Run()

	# should produce nothing
	FunctionnalTest(CHECK + [ "group", "-v", "--name=%s" % group_name],
		context=context).Run()

	FunctionnalTest(DELETE + ["group", "--name", group_name],
		context=context).Run()
	# FIXME: verify /etc/group /etc/licorn/groups /home/groupes/...

	# should fail because group is not present anymore.
	FunctionnalTest(CHECK + [ "group", "-v", "--name=%s" % group_name ],
		context=context).Run()

	group_name = "groupe_a_skel"

	FunctionnalTest(ADD + [ "group", "--name=%s" % group_name,
		'''--description="Le groupe C s'il vous plaît..."''' ],
		context=context).Run()

	# should display a message saying that the group is already not permissive...
	FunctionnalTest(MODIFY + [ "group", '--name=%s' % group_name,
		'--not-permissive' ], chk_cmds = [ gen_chk_acls_cmds(group_name) ],
		context=context).Run()

	# should change ACLs.
	FunctionnalTest(MODIFY + [ "group", "--name=%s" % group_name,
		"--permissive" ], chk_cmds = [ gen_chk_acls_cmds(group_name) ],
		context=context).Run()

	# another message saying that the group is already permissive.
	FunctionnalTest(MODIFY + [ "group", "--name=%s" % group_name,
		"--permissive" ], context=context+'+already').Run()

	# NOT YET
	#log_and_exec(ADD + " group --name=groupeE --gid=1520")

	# RENAME IS NOT SUPPORTED YET !!
	#log_and_exec(MODIFY + " group --name=TestGroup_A --rename=leTestGroup_A/etc/power")

	# FIXME: get members of group for later verifications...
	FunctionnalTest(DELETE + ["group", "--name", group_name, '--del-users',
		'--no-archive'],
		context=context).Run()
	# FIXME: verify deletion of groups + deletion of users...

	# already deleted, should fail...
	FunctionnalTest(DELETE + ["group", "--name", group_name],
		context=context+'+already').Run()

	# FIXME: get members.
	#log_and_exec(DELETE + " group --name=groupeD --del-users")
	# FIXME: idem last group, verify users account were archived, shared dir ws archived.

	#os.system("rm -rf %s >/dev/null 2>&1" % ("/home/" + configuration.groups.names['plural'] + "/groupeD") )

	FunctionnalTest(ADD + ["group", "--name=%s" % group_name, "--skel=/etc/skel",
		"--description='Vive les skel'"], context=context).Run()

	FunctionnalTest(DELETE + ["group", "--name", group_name],
		context=context).Run()
	# FIXME: verify /etc/group /etc/licorn/groups /home/groupes/...

	test_message('''groups related tests finished.''')
def test_users():
	"""Test ADD/MOD/DEL on user accounts in various ways."""

	test_message('''starting users related tests.''')

	log_and_exec(ADD + " group --name test_users_A --description 'groupe créé pour la suite de tests sur les utilisateurs, vous pouvez effacer'")
	log_and_exec(ADD + " profile --name Utilisagers --group utilisagers --comment 'profil normal créé pour la suite de tests utilisateurs'")
	log_and_exec(ADD + " profile --name Responsibilisateurs --group responsibilisateurs --groups cdrom,lpadmin,plugdev,audio,video,scanner,fuse --comment 'profil power user créé pour la suite de tests utilisateurs.'")

	log_and_exec(ADD + " group --name test_users_B --description 'groupe créé pour la suite de tests sur les utilisateurs, vous pouvez effacer'")

	os.system(GETENT + " groups")
	os.system(GETENT + " profiles")

	log_and_exec(ADD + " user --firstname Utiliçateur --lastname Accentué")
	log_and_exec(ADD + " user --gecos 'Utilisateur Accentué n°2'", True, 12,
		comment = "can't build a login from only a GECOS field.")
	log_and_exec(ADD + " user --login utilisager.normal --profile utilisagers")

	log_and_exec(MODIFY + " user --login=utilisager.normal -v --add-groups test_users_A")
	log_and_exec(MODIFY + " user --login=utilisager.normal -v --add-groups test_users_B")

	# should produce nothing, because nothing is wrong.
	log_and_exec(CHECK + " group -v --name test_users_B")

	os.system("rm ~utilisager.normal/test_users_A")

	# all must be OK, extended checks are not enabled, the program will not "see" the missing link.
	log_and_exec(CHECK + " group -v --name test_users_A")

	# the link to group_A isn't here !
	log_and_exec(CHECK + " group -vv --name test_users_A --extended --auto-no",
		True, 7, comment = "a user lacks a symlink.")
	log_and_exec(CHECK + " group -vv --name test_users_A --extended --auto-yes")

	# the same check, but checking from users.py
	#os.system("rm ~utilisager.normal/test_users_A")
	#log_and_exec(CHECK + " user --name utilisager.normal")
	# not yet implemented
	#log_and_exec(CHECK + " user --name utilisager.normal --extended --auto-no", True, 7, comment="user lacks symlink")
	#log_and_exec(CHECK + " user --name utilisager.normal --extended --auto-yes")

	# checking for Maildir repair capacity...
	if configuration.users.mailbox_type == configuration.MAIL_TYPE_HOME_MAILDIR:
		os.system("rm -rf ~utilisager.normal/" + configuration.users.mailbox)
		log_and_exec(CHECK + " user -v --name utilisager.normal --auto-no",
			True, 7, comment="user lacks ~/" + configuration.users.mailbox)
		log_and_exec(CHECK + " user -v --name utilisager.normal --auto-yes")

	os.system("touch ~utilisager.normal/.dmrc ; chmod 666  ~utilisager.normal/.dmrc")
	log_and_exec(CHECK + " user -v --name utilisager.normal --auto-yes")

	os.system("mv -f ~utilisager.normal/test_users_B ~utilisager.normal/mon_groupe_B_préféré")
	# all must be ok, the link is just renamed...
	log_and_exec(CHECK + " group -vv --name test_users_B --extended")

	# FIXME: verify the user can create things in shared group dirs.

	log_and_exec(MODIFY + " user --login=utilisager.normal --del-groups test_users_A")

	# should fail
	log_and_exec(MODIFY + " user --login=utilisager.normal --del-groups test_users_A",
		comment = "already not a member.")

	log_and_exec(ADD + " user --login test.responsibilly --profile responsibilisateurs")

	log_and_exec(MODIFY + " profile --group utilisagers --add-groups cdrom")
	log_and_exec(MODIFY + " profile --group utilisagers --add-groups cdrom,test_users_B")

	log_and_exec(MODIFY + " profile --group utilisagers --apply-groups")


	log_and_exec(MODIFY + " profile --group responsibilisateurs --add-groups plugdev,audio,test_users_A")
	log_and_exec(MODIFY + " profile --group responsibilisateurs --del-groups audio")

	log_and_exec(MODIFY + " profile --group responsibilisateurs --apply-groups")

	# clean the system
	log_and_exec(DELETE + " user --login utilicateur.accentue")
	log_and_exec(DELETE + " user --login utilisateur.accentuen2",
		True, 5, comment = "this user has *NOT* been created previously.")
	log_and_exec(DELETE + " profile -vvv --group utilisagers --del-users --no-archive")

	#os.system(GETENT + " users")

	log_and_exec(DELETE + " profile --group responsibilisateurs", True, 12,
		comment = "there are still some users in the pri group of this profile.")
	log_and_exec(DELETE + " group --name=test_users_A --del-users --no-archive")

	log_and_exec(DELETE + " user --login test.responsibilly")
	# this should work now that the last user has been deleted
	log_and_exec(DELETE + " profile --group responsibilisateurs")
	log_and_exec(DELETE + " group --name=test_users_B -vv")

	# already deleted before
	#log_and_exec(DELETE + " user --login utilisager.normal")
	#log_and_exec(DELETE + " user --login test.responsibilly")
	test_message('''users related tests finished.''')
def test_imports():
	"""Test massive user accounts imports."""

	os.system(DELETE + " profile --group utilisagers         --del-users --no-archive")
	os.system(DELETE + " profile --group responsibilisateurs --del-users --no-archive")
	log_and_exec(GETENT + " groups --empty | cut -d\":\" -f 1 | xargs -I% " + DELETE + " group --name % --no-archive")

	log_and_exec(ADD + " profile --name Utilisagers         --group utilisagers                                                                 --comment 'profil normal créé pour la suite de tests utilisateurs'")
	log_and_exec(ADD + " profile --name Responsibilisateurs --group responsibilisateurs --groups cdrom,lpadmin,plugdev,audio,video,scanner,fuse --comment 'profil power user créé pour la suite de tests utilisateurs.'")

	log_and_exec(ADD + " users --filename ./testsuite/tests_users.csv", True,
		12, comment = "You should specify a profile")

	log_and_exec(ADD + " users --filename ./testsuite/tests_users.csv --profile utilisagers")
	log_and_exec(ADD + " users --filename ./testsuite/tests_users.csv --profile utilisagers --lastname-column 1 --firstname-column 0")
	log_and_exec("time " + ADD + " users --filename ./testsuite/tests_users.csv --profile utilisagers --lastname-column 1 --firstname-column 0 --confirm-import")
	log_and_exec(ADD + " users --filename ./testsuite/tests_resps.csv --profile responsibilisateurs")
	log_and_exec(ADD + " users --filename ./testsuite/tests_resps.csv --profile responsibilisateurs --lastname-column 1 --firstname-column 0")
	log_and_exec("time " + ADD + " users --filename ./testsuite/tests_resps.csv --profile responsibilisateurs --lastname-column 1 --firstname-column 0 --confirm-import")

	# activer les 2 lignes suivantes pour importer 860 utilisateurs de Latresne...
	log_and_exec(ADD + " users --filename ./testsuite/tests_users2.csv --profile utilisagers")
	log_and_exec("time " + ADD + " users --filename ./testsuite/tests_users2.csv --profile utilisagers --confirm-import")

	os.system("sleep 5")
	log_and_exec(DELETE + " profile --group utilisagers         --del-users --no-archive")
	log_and_exec(DELETE + " profile --group responsibilisateurs --del-users --no-archive")

	log_and_exec(GETENT + " groups --empty | cut -d\":\" -f 1 | xargs -I% " + DELETE + " group --name % --no-archive")
def test_profiles():
	"""Test the applying feature of profiles."""

	test_message('''starting profiles related tests.''')
	log_and_exec(ADD + " profile --name Utilisagers --group utilisagers --comment 'profil normal créé pour la suite de tests utilisateurs'")
	log_and_exec(ADD + " profile --name Responsibilisateurs --group responsibilisateurs --groups cdrom,lpadmin,plugdev,audio,video,scanner,fuse --comment 'profil power user créé pour la suite de tests utilisateurs.'")

	log_and_exec(ADD + " user toto --profile utilisagers")
	log_and_exec(ADD + " user tutu --profile utilisagers")
	log_and_exec(ADD + " user tata --profile utilisagers")

	log_and_exec(MODIFY + " profile --group utilisagers --apply-groups --to-groups utilisagers")
	log_and_exec(MODIFY + " profile --group utilisagers --apply-groups --to-members")
	log_and_exec(MODIFY + " profile --group utilisagers --apply-skel --to-users toto --auto-no")
	log_and_exec(MODIFY + " profile --group utilisagers --apply-skel --to-users toto --batch")
	log_and_exec(MODIFY + " profile --group utilisagers --apply-group --to-users toto")
	log_and_exec(MODIFY + " profile --group utilisagers --apply-all --to-users toto")
	log_and_exec(MODIFY + " profile --group utilisagers --apply-all --to-users toto")
	log_and_exec(MODIFY + " profile --group utilisagers --apply-all --to-all")

	log_and_exec(DELETE + " profile --group responsibilisateurs --no-archive")
	log_and_exec(DELETE + " user toto --no-archive")

	log_and_exec(DELETE + " profile --group utilisagers --del-users --no-archive")

	test_message('''profiles related tests finished.''')
def to_be_implemented():
	""" TO BE DONE !
		#
		# Profiles
		#

		# doit planter pour le groupe
		log_and_exec $ADD profile --name=profileA --group=a

		# doit planter pour le groupe kjsdqsdf
		log_and_exec $ADD profile --name=profileB --group=b --comment="le profil b" --shell=/bin/bash --quota=26 --groups=cdrom,kjsdqsdf,audio --skeldir=/etc/skel && exit 1

		# doit planter pour le skel pas un répertoire, pour le groupe jfgdghf
		log_and_exec $MODIFY profile --name=profileA --rename=theprofile --rename-primary-group=theprofile --comment=modify --shell=/bin/sh --skel=/etc/power --quota=10 --add-groups=cdrom,remote,qsdfgkh --del-groups=cdrom,jfgdghf

		log_and_exec $DELETE profile --name=profileB --del-users --no-archive

		log_and_exec $DELETE profile --name=profileeD
		log_and_exec $MODIFY profile --name=profileeC --not-permissive
		log_and_exec $ADD profile --name=theprofile
		log_and_exec $MODIFY profile --name=theprofile --skel=/etc/doesntexist
	}

	"""
	pass


if __name__ == "__main__":

	#
	# Unit Tests
	#

	test_find_new_indentifier()

	clean_system()

	#
	# Functionnal Tests
	#

	test_integrated_help()

	#test_check_config()

	test_regexes()

	test_message('testing Unix backend.')

	if execute(['mod', 'config', '-B', 'ldap'])[1] == 0:
		make_backups('unix')
		FunctionnalTest(GETENT + ['config'], context='unix').Run(
			options=[['backends']])
		test_get('unix')
		test_groups('unix')
		#test_users()
		#test_imports()
		#test_profiles()
		compare_delete_backups('unix')
		clean_system()

	test_message('testing LDAP backend.')

	if execute(['mod', 'config', '-b', 'ldap'])[1] == 0:
		make_backups('ldap')
		FunctionnalTest(GETENT + ['config'], context='ldap').Run(
			options=[['backends']])
		test_get('ldap')
		test_groups('ldap')
		#test_users()
		#test_imports()
		#test_profiles()
		compare_delete_backups('ldap')
		clean_system()

	# TODO: test_concurrent_accesses()

	print("\n%s Testsuite terminated successfully.\n" % styles.stylize(styles.ST_OK, "VICTORY !"))
