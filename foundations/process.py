# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

process - processes / system() / pipe() related functions.

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import os, sys, traceback, pwd, grp, time, signal
from types import *

from licorn.foundations         import exceptions, logging
from licorn.foundations.styles  import *
from licorn.foundations.ltrace  import ltrace, insert_ltrace
from licorn.foundations.ltraces import *
#
# daemon and process functions
#
def daemonize(log_file=None):
	""" UNIX double-fork magic to create a daemon.
		See Stevens' "Advanced Programming in the UNIX Environment"
		for details (ISBN 0201563177).


		.. versionadded:: 1.2.5
			this function doesn't write the pid file anymore. its up to the
			calling process to do it. This makes things much logical in the
			daemon.
	"""

	assert ltrace(TRACE_PROCESS, '> daemonize(%s)' % os.getpid())

	try:
		if os.fork() > 0:
			# exit first parent
			sys.exit(0)

	except OSError, e:
		logging.error("fork #1 failed: errno %d (%s)" % (
			e.errno, e.strerror))

	# decouple from parent environment
	os.chdir("/")
	os.setsid()
	os.umask(0)

	assert ltrace(TRACE_PROCESS, '  daemonize(%s)' % os.getpid())

	# do second fork
	try:
		if os.fork() > 0:
			# exit from second parent
			sys.exit(0)

	except OSError, e:
		logging.error("fork #2 failed: errno %d (%s)" % (
			e.errno, e.strerror))

	assert ltrace(TRACE_PROCESS, '< daemonize(%s)' % os.getpid())

	use_log_file(log_file)
def write_pid_file(pid_file):
	""" write PID into the pidfile. """
	if pid_file:
		with open(pid_file, 'w') as f:
			f.write("%s\n" % os.getpid())
def use_log_file(log_file):
	""" replace stdout/stderr with the logfile.
		stderr becomes /dev/null.
	"""
	if log_file is not None:
		out_log  = file(log_file, 'a')
		dev_null = file('/dev/null', 'r')

		sys.stdout.flush()
		sys.stderr.flush()

		os.close(sys.stdin.fileno())
		os.close(sys.stdout.fileno())
		os.close(sys.stderr.fileno())

		os.dup2(dev_null.fileno(), sys.stdin.fileno())
		os.dup2(out_log.fileno(), sys.stdout.fileno())
		os.dup2(out_log.fileno(), sys.stderr.fileno())
def set_name(name):
	""" Change process name in `ps`, `top`, gnome-system-monitor and al.

		try to use proctitle to change name, else fallback to libc call
		if proctitle not installed. Don't fail if anything goes wrong,
		because changing process name is just a cosmetic hack.

		See:
			http://mail.python.org/pipermail/python-list/2002-July/155471.html
			http://davyd.livejournal.com/166352.html
		"""
	try:
		import ctypes
		ctypes.cdll.LoadLibrary('libc.so.6').prctl(15, name + '\0', 0, 0, 0)
	except Exception, e:
		logging.warning('''Can't set process name (was %s).''' % e)
def get_process_cmdline(process_name):
	""" do equivalent of ps aux and grep the given process, then return its
		command line as a list."""

	for pretendant in execute(['ps', '-U', 'root', '-u', 'root', '-o', 'args='])[0].split(
			"\n")[:-1]:
		#print pretendant
		if pretendant.find(process_name) != -1:
			return pretendant.split(' ')
def already_running(pid_file):
	""" Returns ``True`` if the given pid file exists and the PID recorded in it
		exists in /proc. Else returns ``False``.
	"""
	return os.path.exists(pid_file) and \
		os.path.exists('/proc/' + open(pid_file, 'r').read().strip())
#
# System() / Popen*() convenience wrappers.
#
def syscmd(command, expected_retcode=0):
	""" Execute `command` in a subshell and grab the return value to test it.
		If the test fails, an exception is raised.
		The exception must be an instance of exceptions.SystemCommandError or
		an inherited class.
	"""

	logging.progress('syscmd(): executing "%s" in a subshell.' % command)

	result = os.system(command)
	# res is a 16bit integer, decomposed as:
	#	- a low byte: signal (with its high bit is set if a core was dumped)
	#	- a high byte: the real exit status, if signal is 0
	# see os.wait() documentation for more

	retcode = 0
	signal  = result & 0x00FF
	if signal == 0:
		retcode = (result & 0xFF00) >> 8

	logging.progress('syscmd(): "%s" exited with code %s (%s).' % (command,
		retcode, result))

	if retcode != expected_retcode:
		raise exceptions.SystemCommandError(command, retcode)
	if signal != 0:
		raise exceptions.SystemCommandSignalError(command, signal)
def execute(command, input_data='', dry_run=None):
	""" Execute a command (passed as a list or tuple) and roughly pipe some
		data into the executed program.
	Return the (eventual) stdout and stderr in a tuple. """

	assert ltrace(TRACE_PROCESS, 'execute(%s)%s, dry_run=%s.' % (command,
		' with input_data="%s"' % input_data if input_data != '' else '', dry_run))

	from subprocess import Popen, PIPE

	if dry_run:
		logging.notice(_(u'{0:s}: dry_run({1}){2}.').format(
			stylize(ST_NAME, u'execute'),
			stylize(ST_COMMENT, u' '.join(command)),
			_(u' → sleep({0})').format(dry_run)))

		if type(dry_run) in (IntType, LongType, FloatType):
			time.sleep(float(dry_run))

		return ('', '')

	if input_data != '':
		p = Popen(command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE,
			close_fds=True)
		return p.communicate(input_data)
	else:
		p = Popen(command, shell=False, stdout=PIPE, stderr=PIPE,
			close_fds=True)
		return p.communicate()
def execute_remote(ipaddr, command):
	""" Exectute command on a machine with SSH. """

	return execute(['ssh', '-f', '-t', '-oPasswordAuthentication=no',
		'-l', 'alt', ipaddr, command])
def whoami():
	''' Return current UNIX user. Do it with traditionnal syscalls, because the
		rest of Licorn® is not initialized if we run this function. '''
	#from subprocess import Popen, PIPE
	#return (Popen(['/usr/bin/whoami'], stdout=PIPE).communicate()[0])[:-1]
	return pwd.getpwuid(os.getuid()).pw_name
def refork_as_root_or_die(process_title='licorn-generic', prefunc=None,
	group='admins'):
	""" check if current user is root. if not, check if he/she is member of
		group "admins" and then refork ourselves with sudo, to gain root
		privileges, needed for Licorn® daemon.
		Do it with traditionnal syscalls, because the rest of Licorn® is not
		initialized if we run this function. """

	try:
		gmembers = grp.getgrnam(group).gr_mem

	except KeyError:
		logging.error('''group %s doesn't exist and we are not root, '''
			'''aborting. Please manually relaunch this program with root '''
			'''privileges for the group to be created.''' % group)

	if pwd.getpwuid(os.getuid()).pw_name in gmembers:

		cmd = [process_title]
		cmd.extend(insert_ltrace())

		cmd.extend(sys.argv)

		if prefunc != None:
			prefunc()

		logging.progress(_(u'Exec\'ing ourselves with sudo to gain root '
				u'privileges (execvp(%s)).') % cmd)

		os.execvp('sudo', cmd)

	else:
		raise exceptions.LicornRuntimeError(_(u'You are not a member of group '
			u'%s, cannot do anything for you, sorry!') % group)
def get_traceback():
	return traceback.format_list(traceback.extract_tb(sys.exc_info()[2]))
def fork_licorn_daemon(pid_to_wake=None):
	""" Start the Licorn® daemon (fork it). """

	try:
		logging.progress(_(u'Forking licornd.'))
		if os.fork() == 0:
			# NOTE: we need to force a replace, in case the existing daemon is
			# in a bad posture, eg. stuck in a restart procedure: it's not
			# responding to the calling CLI process, but in the wait for a
			# restart. This the current starting daemon will fail, then the
			# waiting CLI will not be awaken and will timeout and show the
			# "connect timeout, something is bad" message to the administrator,
			# which will be a totally false-negative situation because
			# meanwhile the restarting daemon will be ready in a perfect
			# state.
			# All of this is a timing problem, and I hope the soft
			# :arg:`--replace` flag will solve this corner-case situation.
			args = ['licornd', '--replace']

			if pid_to_wake:
				args.extend(['--pid-to-wake', str(pid_to_wake)])

			os.execvp('licornd', args)

	except (IOError, OSError), e:
		logging.error(_(u'licornd fork failed: errno %d (%s).') % (e.errno,
			e.strerror))
def find_network_client_uid(orig_port, client_port, local=True):
	""" will only work on localhost, and on linux, from a root process...

	As a general recommendation, use strace(1) to answer this kind of
	question. Run "strace -o tmp netstat", then inspect tmp to find out
	how netstat obtained the information it reported.

	As Sybren suggests, this can all be answered from /proc. For a
	process you are interested in, list /proc/<pid>/fd (using os.listdir),
	then read the contents of all links (using os.readlink). If the link
	value starts with "[socket:", it's a socket. Then search
	/proc/net/tcp for the ID. The line containing the ID will have
	the information you want.

	---------------------------------------------------------------------------

	/proc/net/tcp and /proc/net/tcp6

	These /proc interfaces provide information about currently active TCP
	connections, and are implemented by tcp_get_info() in net/ipv4/tcp_ipv4.c and
	tcp6_get_info() in net/ipv6/tcp_ipv6.c, respectively.

	It will first list all listening TCP sockets, and next list all established
	TCP connections. A typical entry of /proc/net/tcp would look like this (split
	up into 3 parts because of the length of the line):

	46: 010310AC:9C4C 030310AC:1770 01
	| | | | | |--> connection state
	| | | | |------> remote TCP port number
	| | | |-------------> remote IPv4 address
	| | |--------------------> local TCP port number
	| |---------------------------> local IPv4 address
	|----------------------------------> number of entry

	00000150:00000000 01:00000019 00000000
	| | | | |--> number of unrecovered RTO timeouts
	| | | |----------> number of jiffies until timer expires
	| | |----------------> timer_active (see below)
	| |----------------------> receive-queue
	|-------------------------------> transmit-queue

	1000 0 54165785 4 cd1e6040 25 4 27 3 -1
	| | | | | | | | | |--> slow start size threshold,
	| | | | | | | | | or -1 if the treshold
	| | | | | | | | | is >= 0xFFFF
	| | | | | | | | |----> sending congestion window
	| | | | | | | |-------> (ack.quick<<1)|ack.pingpong
	| | | | | | |---------> Predicted tick of soft clock
	| | | | | | (delayed ACK control data)
	| | | | | |------------> retransmit timeout
	| | | | |------------------> location of socket in memory
	| | | |-----------------------> socket reference count
	| | |-----------------------------> inode
	| |----------------------------------> unanswered 0-window probes
	|---------------------------------------------> uid

	timer_active:
	0 no timer is pending
	1 retransmit-timer is pending
	2 another timer (e.g. delayed ack or keepalive) is pending
	3 this is a socket in TIME_WAIT state. Not all field will contain data.
	4 zero window probe timer is pending

	---------------------------------------------------------------------------

	old method (with fork & regex...):

	return int(execute(['ps', '-p',
		re.findall(r'127.0.[01].1:%d\s+127.0.[01].1:%d\s+ESTABLISHED\s*(\d+)/' % (
			client_port, orig_port),
			execute(['netstat', '-antp'])[0])[0], '-o', 'uid='])[0].strip())
	"""
	first_try = True

	local_addr1 = '0100007F'
	local_addr2 = '0101007F'

	while True:
		for line in open('/proc/net/tcp').readlines()[1:]:
			values = line.split()
			# values:
			# conn_no, local_addr, remote_addr, conn_status, tx_rx_queues,
			# tm_when, retransmit, uid, timeout, inode, other_values

			#print ('--> %s %s / %s %s' % (values[1], values[2],
			#	('0100007F:%x' % client_port).upper(),
			#	('0101007F:%x' % client_port).upper()))
			laddr, lport = values[1].split(':')
			raddr, rport = values[2].split(':')

			if local:
				if ('%x' % client_port).upper() == lport \
					and laddr in (local_addr1, local_addr2):
					return int(values[7])
			else:
				if ('%x' % client_port).upper() == lport:
					return int(values[7])

		if first_try:
			# The problem *could* be we are too fast for the kernel to update
			# /proc/net/tcp. Wait and try again one time before giving up.
			time.sleep(0.01)
			first_try = False
		else:
			break
	raise IndexError(_(u"Cannot find client 127.0.0.1:{0} or 127.0.1.1:{0} in "
					u"/proc/net/tcp!").format(client_port))
