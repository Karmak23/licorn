# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

process - processes / system() / pipe() related functions.

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

import os
import sys

from licorn.foundations        import exceptions
from licorn.foundations        import logging
from licorn.foundations.ltrace import ltrace
#
# daemon and process functions
#
def daemonize(log_file, pid_file):
	""" UNIX double-fork magic to create a daemon.
		See Stevens' "Advanced Programming in the UNIX Environment"
		for details (ISBN 0201563177)."""

	try:
		if os.fork() > 0:
			# exit first parent
			sys.exit(0)
	except OSError, e:
		sys.stderr.write("fork #1 failed: errno %d (%s)" % (e.errno, e.strerror))
		sys.exit(1)

	# decouple from parent environment
	os.chdir("/")
	os.setsid()
	os.umask(0)

	# do second fork
	try:
		if os.fork() > 0:
			# exit from second parent
			sys.exit(0)
	except OSError, e:
		sys.stderr.write("fork #2 failed: errno %d (%s)" % (e.errno, e.strerror))
		sys.exit(1)

	use_log_file(log_file)
	write_pid_file(pid_file)
def write_pid_file(pid_file):
	""" write PID into the pidfile. """
	open(pid_file,'w').write("%s\n" % os.getpid())
def use_log_file(log_file):
	""" replace stdout/stderr with the logfile.
		stderr becomes /dev/null.
	"""
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
	except exception, e:
		logging.warning('''Can't set process name (was %s).''' % e)
def already_running(pid_file):
	""" WARNING: this only works for root user... """
	return os.path.exists(pid_file) and \
		 get_pid(pid_file) in \
			os.popen2( [ 'ps', '-U', 'root', '-u', 'root', '-o', 'pid=' ]
			)[1].read().split("\n")[:-1]
def get_pid(pid_file):
	'''return the PID included in the pidfile. '''
	return open(pid_file, 'r').readline()[:-1]
#
# System() / Popen*() convenience wrappers.
#
def syscmd(command, expected_retcode = 0):
	""" Execute `command` in a subshell and grab the return value to test it.
		If the test fails, an exception is raised.
		The exception must be an instance of exceptions.SystemCommandError or an inherited class.
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

	logging.progress('syscmd(): "%s" exited with code %s (%s).' % (command, retcode, result))

	if retcode != expected_retcode:
		raise exceptions.SystemCommandError(command, retcode)
	if signal != 0:
		raise exceptions.SystemCommandSignalError(command, signal)
def execute(command, input_data = ''):
	""" Roughly pipe some data into a program.
	Return the (eventual) stdout and stderr in a tuple. """

	ltrace('process', '''execute(%s)%s.''' % (command,
		' with input_data="%s"' % input_data if input_data != '' else ''))

	from subprocess import Popen, PIPE

	if input_data != '':
		p = Popen(command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE,
			close_fds=True)
		return p.communicate(input_data)
	else:
		p = Popen(command, shell=False, stdout=PIPE, stderr=PIPE,
			close_fds=True)
		return p.communicate()
def whoami():
	''' Return current UNIX user. '''
	from subprocess import Popen, PIPE
	return (Popen(['/usr/bin/whoami'], stdout=PIPE).communicate()[0])[:-1]

