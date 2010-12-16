# -*- coding: utf-8 -*-
"""
Licorn Daemon __init__.py

Copyright (C) 2009-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import os, sys, time, signal
dstart_time = time.time()
from Queue import Empty

from licorn.foundations           import options, logging
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.base      import MixedDictObject, Singleton
from licorn.foundations.thread    import _threads, _thcount
from licorn.foundations.pyutils   import format_time_delta

from licorn.core import LMC

class LicornThreads(MixedDictObject, Singleton):
	pass
class LicornQueues(MixedDictObject, Singleton):
	pass
class ChildrenPIDs(MixedDictObject, Singleton):
	pass

# these objects will be global across the daemon and possibly the core,
# usable everywhere.
dthreads = LicornThreads('daemon_threads')
dqueues  = LicornQueues('daemon_queues')

# following objects are used inside the daemon and the WMI process.
dname            = 'licornd'
dchildren         = ChildrenPIDs('daemon_children')
dchildren.wmi_pid = None

def clean_before_terminating(pname):
	""" stop threads and clear pid files. """

	for child in dchildren:
		if child:
			os.kill(child, signal.SIGTERM)
			os.waitpid(child, 0)
			# wipe the PID in case we got Interactor thread trying to kill
			# it later, which will fail if the old pid is kept.
			child = None

	# we are stopping, unlink the pid file. In case anything goes wrong, or a
	# restart, the pid file will thus not block another daemon from starting.
	unlink_pid_file(pname)

	logging.progress("%s: stopping threads." % pname)

	logging.progress("%s: joining queues." % pname)
	for (qname, queue) in dqueues.iteritems():
		assert ltrace('daemon', 'joining queue %s (%d items left).' % (qname,
			queue.qsize()))

		# manually empty the queue by munging all remaining items.
		try:
			obj = queue.get(False)
			queue.task_done()
			while obj:
				obj = queue.get(False)
				queue.task_done()
			# be sure to reput a None object in the queue, to stop the last
			# threads of the pool, waiting for the None we have munged here.
			queue.put(None)
		except Empty:
			pass

	for (thname, th) in dthreads.iteritems():
		assert ltrace('thread', 'stopping thread %s.' % thname)
		if th.is_alive():
			th.stop()

	logging.progress("%s: joining queues." % pname)
	for (qname, queue) in dqueues.iteritems():
		assert ltrace('daemon', 'joining queue %s (%d items left).' % (qname,
			queue.qsize()))
		queue.join()

	logging.progress("%s: joining threads." % pname)

	for (thname, th) in dthreads.items():
		# join threads in the reverse order they were started, and only the not
		# daemonized ones, in case daemons are stuck on blocking socket or
		# anything preventing a quick and gracefull stop.
		if th.daemon:
			assert ltrace('thread', 'skipping daemon thread %s.' % thname)
			pass
		else:
			assert ltrace('thread', 'joining %s.' % thname)
			if th.is_alive():
				assert ltrace('thread',
					"re-stopping thread %s (shouldn't happen)." % thname)
				th.stop()
				time.sleep(0.01)
			th.join()
			del th
			del dthreads[thname]

	try:
		assert ltrace('thread', 'joining interactor thread.')
		dthreads._interactor.stop()
	except AttributeError:
		pass
	else:
		dthreads._interactor.join()

	# display the remaining active threads (presumably stuck hanging on
	# something very blocking).
	assert ltrace('thread', 'after joining all, %s remaining: %s' % (
		_thcount(), _threads()))

	if LMC.configuration:
		LMC.configuration.CleanUp()
def unlink_pid_file(pname):
	""" remove the pid file and bork if any error. """

	if pname[8:11] == 'wmi':
		pid_file = LMC.configuration.licornd.wmi.pid_file
	else:
		pid_file = LMC.configuration.licornd.pid_file

	try:
		if os.path.exists(pid_file):
			os.unlink(pid_file)
	except (OSError, IOError), e:
		logging.warning("%s: can't remove %s (was: %s)." % (pname,
			stylize(ST_PATH, pid_file), e))
def uptime():
	return ' (up %s)' % stylize(ST_COMMENT,
			format_time_delta(time.time() - dstart_time))
def terminate(signum, frame, pname):
	""" Close threads, wipe pid files, clean everything before closing. """

	if signum is None:
		logging.progress("%s: cleaning up and stopping threads…" % \
			pname)
	else:
		logging.notice('%s: signal %s received, shutting down…' % (
			pname, signum))

	if pname[8:14] == 'master':
		clean_before_terminating(pname)
		upt = uptime()
	else:
		# don't display the uptime in children, this is duplicate.
		upt = ''
		LMC.release()

	logging.notice("%s: exiting%s." % (pname, upt))
	sys.exit(0)
def restart(signum, frame, pname):
	logging.notice('%s: SIGUSR1 received, restarting%s.' % (pname, uptime()))

	clean_before_terminating(pname)

	# close every file descriptor (except stdin/out/err, used for logging and
	# on the console). This is needed for Pyro thread to release its socket,
	# else it's done too late and on restart the port can't be rebinded on.
	os.closerange(3, 32)

	cmd = [ 'licornd' ]

	# we need to rebuild all command line options, else the new process will
	# not behave exactly like the old. This could lead it to fork into the
	# background, start the WMI on another socket, or such strange things.
	if options.verbose > 0:
		cmd.append('-%s' % ('v' * (options.verbose-1)))
	if options.wmi_listen_address:
		cmd.extend(['-w', options.wmi_listen_address])
	if not options.wmi_enabled:
		cmd.append('-W')
	if not options.daemon:
		cmd.append('-D')

	os.execvp('licornd', cmd)
def setup_signals_handler(pname):
	""" redirect termination signals to a the function which will clean everything. """

	signal.signal(signal.SIGTERM, lambda x,y: terminate(x, y, pname))
	signal.signal(signal.SIGHUP, lambda x,y: terminate(x, y, pname))

	if pname[8:11] == 'wmi':
		# wmi will receive this signal from master when all threads are started,
		# this will wake it from its signal.pause(). Just ignore it.
		signal.signal(signal.SIGINT, signal.SIG_IGN)
		signal.signal(signal.SIGUSR1, lambda x,y: True)

		# don't ignore the SIGINT, else the WMI doesn't get killed when the
		# master dies.
		#signal.signal(signal.SIGINT, signal.SIG_IGN)
	else:
		signal.signal(signal.SIGINT, lambda x,y: terminate(x, y, pname))
		signal.signal(signal.SIGUSR1, lambda x,y: restart(x, y, pname))

	#signal.signal(signal.SIGCHLD, signal.SIG_IGN)
