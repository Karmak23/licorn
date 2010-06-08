# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

process - processes / system() / pipe() related functions.

Copyright (C) 2007 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2

"""

import os, sys
from licorn.foundations import exceptions, logging

# daemon and process functions
def daemonize(logfile, pidfile):
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

	out_log  = file(logfile, 'a')
	dev_null = file('/dev/null', 'r')
	
	sys.stdout.flush()
	sys.stderr.flush()
	
	os.close(sys.stdin.fileno())
	os.close(sys.stdout.fileno())
	os.close(sys.stderr.fileno())

	os.dup2(dev_null.fileno(), sys.stdin.fileno())
	os.dup2(out_log.fileno(), sys.stdout.fileno())
	os.dup2(out_log.fileno(), sys.stderr.fileno())

	open(pidfile,'w').write("%s\n" % os.getpid())
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
		import proctitle
		proctitle.ProcTitle()[0:] = name
	except ImportError:
		try:
			import dl
			dl.open('/lib/libc.so.6').call('prctl', 15, name + '\0', 0, 0, 0)
		except: 
			pass
def already_running(pidfile):
		return os.path.exists(pidfile) and open(pidfile, 'r').readline()[:-1] in os.popen2( [ 'ps', '-U', 'root', '-u', 'root', '-o', 'pid=' ] )[1].read().split("\n")[:-1]

# System() / Popen*() convenience wrappers.
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
def pipecmd(data, command):
	""" Roughly pipe some data into a program. Return the (eventual) stdout and stderr merged into an array. """

	logging.debug('''pipecmd(): piping "%s" into "%s".''' % (data, command))

	if sys.version_info[0:2] == (2, 6):
		from subprocess import Popen, PIPE
		
		p = Popen(command, shell=False,
          stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)

		(out, err) = p.communicate(data)

		return err

	else:
		(pin, pout, perr) = os.popen3(command)
	
		if None in (pin, pout, perr):
			raise exceptions.SystemCommandError('pipecmd(): command "%s" failed to start !' % command)

		pin.write(data)
		pin.flush()
		pin.close()

		# forget the output.
		pout.read()

		return perr.read()
