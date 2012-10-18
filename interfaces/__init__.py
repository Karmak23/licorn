# -*- coding: utf-8 -*-
"""
Licorn interfaces: base classes - http://docs.licorn.org/

:copyright:
	* 2011 Olivier Cortès <oc@meta-it.fr>
	* partial 2011 RobinLucbernet <robinlucbernet@gmail.com>

:license: GNU GPL version 2

"""

import sys, os, time, errno, socket, signal

from threading import current_thread, Thread
import Pyro.core, Pyro.util, Pyro.configuration

from licorn.foundations           import settings, options, logging, exceptions
from licorn.foundations           import pyutils, process, styles, network
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import LicornConfigObject, Singleton
from licorn.foundations.constants import verbose, roles
from licorn.foundations.messaging import MessageProcessor

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

from licorn.core import LMC

class LicornInterfaceBaseApplication:
	def __init__(self, needs_listener=True, message_processor_class=None, start_time=None):

		self.needs_listener = needs_listener
		self.start_time     = start_time or time.time()

		# we won't try to resync more than once per N seconds (see later)
		self.sync_time      = self.start_time

		if message_processor_class is None:
			self.message_processor_class = MessageProcessor

		else:
			self.message_processor_class = message_processor_class

		self.pyroStarted          = False
		self.pyroExit             = False
		self.delayed_daemon_start = False
		self.lmc_connected        = False

		# XXX: this will work correctly in CLI, because this will be done
		# in the main thread, but will not in the WMI where the Application
		# is a separate thread.
		signal.signal(signal.SIGUSR2, self.resync)
	def start_Pyro(self):

		assert ltrace(TRACE_INTERFACES, '  PyroListenerApplication: starting pyro!')

		if __debug__:
			pyro_start_time = time.time()

		self.pyroStarted = True

		# this is important for Pyro to be able to create temp files
		# in a self-writable directory, else it will lamentably fail
		# because default value for PYRO_STORAGE is '.', and the user
		# is not always positionned in a welcomed place.
		Pyro.config.PYRO_STORAGE = os.getenv('HOME', os.path.expanduser('~'))

		Pyro.core.initServer()
		Pyro.core.initClient()

		self.client_daemon = Pyro.core.Daemon()

		# opts._listener is needed for the Interactor
		self.local_listener = self.message_processor_class(verbose=self.opts.verbose
															if hasattr(self, 'opts')
															else options.verbose)

		self.client_daemon.connect(self.local_listener)

		self.msg_thread = Thread(target=self.client_daemon.requestLoop,
									args=(lambda: not self.pyroExit, 0.1))

		self.msg_thread.start()

		assert ltrace(TRACE_TIMINGS, '@pyro_start_delay: %.4fs' % (
										time.time() - pyro_start_time))
	def stop_Pyro(self):
		assert ltrace(TRACE_INTERFACES, ' PyroListenerApplication: stopping Pyro.')
		if self.pyroStarted:
			self.pyroExit = 1
			try:
				self.msg_thread.join()
			except (OSError, IOError), e:
				# this happens in the WMI when restarting in interactive mode.
				if e.errno == errno.EBADF:
					pass
				else:
					raise
	def release_LMC(self):
		assert ltrace(TRACE_INTERFACES, ' PyroListenerApplication: releasing LMC.')
		try:
			LMC.release()
			self.lmc_connected = False

		except:
			logging.exception(_(u'Harmless exception while releasing the LMC.'))
	def resync(self, signum=None, frameno=None):

		if (time.time() - self.sync_time) < 3:
			# don't try to resync a launcher process if it just started,
			# this would create a race, making processes fork-each-other
			# until exhaustion of machine resources.
			return

		self.sync_time = time.time()

		logging.notice(_(u'{0}: {1} received, restarting listener.').format(
								self, stylize(ST_ATTRVALUE, _(u'SIGUSR2'))))

		LMC.release(force=True)
		LMC.connect()

		LMC.system.set_listener(self.local_listener.getAttrProxy())

		if settings.role != roles.SERVER:
			# expose our listener with its public address, not 127.0.0.1, else
			# the remote_output() of the the remote daemon will fail.
			LMC.rwi.set_listener(Pyro.core.PyroURI(
							host=network.find_first_local_ip_address(),
							objectID=self.local_listener.GUID).getAttrProxy())
		else:
			LMC.rwi.set_listener(self.local_listener.getAttrProxy())

		if hasattr(self, 'resync_specific'):
			# Used in the CLI applications, to resync GET sta/evt.
			self.resync_specific(self.opts, self.args, listener=self.local_listener)
	def connect(self, *args, **kwargs):

		if self.lmc_connected:
			return

		if hasattr(self, 'main_pre_connect'):
			assert ltrace(TRACE_INTERFACES, '  run : pre_connect.')
			self.main_pre_connect(*args, **kwargs)

		assert ltrace(TRACE_INTERFACES, '  run : connecting to LMC.')
		LMC.connect(self.delayed_daemon_start)

		# options._rwi is needed for the Interactor
		# 20120918: really ??
		#options._rwi = LMC.rwi

		if hasattr(self, 'main_post_connect'):
			assert ltrace(TRACE_INTERFACES, '  run : post_connect.')
			self.main_post_connect(*args, **kwargs)

		self.lmc_connected = True
	def __parse_arguments(self, *args, **kwargs):
		if hasattr(self, 'main_pre_parse_arguments'):
			assert ltrace(TRACE_INTERFACES, '  run : main_pre_parse_arguments(%s, %s).', args, kwargs)
			self.main_pre_parse_arguments(*args, **kwargs)

		if hasattr(self, 'parse_arguments'):
			assert ltrace(TRACE_INTERFACES, '  run : parse_arguments(%s, %s).', args, kwargs)
			self.opts, self.args = self.parse_arguments(*args, **kwargs)

			options.SetFrom(self.opts)

		if hasattr(self, 'main_post_parse_arguments'):
			assert ltrace(TRACE_INTERFACES, '  run : main_post_parse_arguments(%s, %s).', args, kwargs)
			self.main_post_parse_arguments(*args, **kwargs)
	def stop(self):

		try:
			self.release_LMC()
			self.stop_Pyro()

		except:
			pass

	def run(self, *args, **kwargs):
		""" common run structure for all pyro listener-enabled apps. """

		# This 'utf-8' thing is needed for a bunch of reasons in our code. We do
		# unicode stuff internally and need utf-8 to deal with real world problems.
		# Ascii comes from another age…
		# We need to set this here, because before it was done ONCE by the
		# configuration object, but with the pyro changes, configuration is now only
		# initialized on the daemon side, and CLI doesn't benefit of it.
		if sys.getdefaultencoding() == "ascii":
			reload(sys)
			sys.setdefaultencoding("utf-8")

		try:
			# this is the first thing to do, else all help and usage will get colors
			# even if no_colors is True, because it is parsed too late.
			if "--no-colors" in sys.argv:
				options.SetNoColors(True)

			assert ltrace(TRACE_INTERFACES, '  run : connecting to core.')

			self.__parse_arguments(*args, **kwargs)

			self.connect(*args, **kwargs)

			self.start_Pyro()

			if self.needs_listener:
				# NOTE: an AttrProxy is needed, not a simple Proxy. Because the
				# daemon will check listener.verbose, which is not accessible
				# through a simple Pyro Proxy.
				LMC.system.set_listener(self.local_listener.getAttrProxy())

				if settings.role != roles.SERVER:
					# expose our listener with its public address, not 127.0.0.1, else
					# the remote_output() of the the remote daemon will fail.

					LMC.rwi.set_listener(Pyro.core.PyroURI(
									host=network.find_first_local_ip_address(),
									objectID=self.local_listener.GUID()).getAttrProxy())
				else:
					LMC.rwi.set_listener(self.local_listener.getAttrProxy())

			# not used yet, but kept for future use.
			#server=Pyro.core.getAttrProxyForURI(
			#	"PYROLOC://localhost:%s/msgproc" %
			#		configuration.pyro.port)

			assert ltrace(TRACE_INTERFACES, '  run : main_body({0}, {1})', args, kwargs)

			self.main_body(*args, **kwargs)

		except exceptions.NeedHelpException, e:
			logging.warning(e)
			sys.argv.append("--help")
			self.parse_arguments(*args, **kwargs)

		except KeyboardInterrupt, e:
			sys.stderr.write(u'^C\n')
			t = current_thread()
			if hasattr(t, 'restore_terminal'):
				t.restore_terminal()
			logging.warning(_(u'Interrupted, cleaning up!'))

		except exceptions.LicornError, e:
			logging.error('%s (%s, errno=%s).' % (
				str(e), stylize(ST_SPECIAL, str(e.__class__).replace(
				"<class '",'').replace("'>", '')), e.errno), e.errno,
				full=True if options.verbose > 2 else False,
				tb=''.join(Pyro.util.getPyroTraceback(e)
					if options.verbose > 2 else ''))

		except exceptions.LicornException, e:
			logging.error('%s: %s (errno=%s).' % (
				stylize(ST_SPECIAL, str(e.__class__).replace(
				"<class '",'').replace("'>", '')),
				str(e), e.errno), e.errno, full=True,
				tb=''.join(Pyro.util.getPyroTraceback(e)))

		except Exception, e:
			logging.error('%s: %s.' % (
				stylize(ST_SPECIAL, str(e.__class__).replace(
				"<class '",'').replace("<type '",'').replace("'>", '')),
				str(e)), 254, full=True, tb=''.join(Pyro.util.getPyroTraceback(e)))

		finally:
			self.stop()

		assert ltrace(TRACE_TIMINGS, '@cli_main(): %.4fs' % (
										time.time() - self.start_time))

		assert ltrace(TRACE_INTERFACES, '< cli_main(%s)' % sys.argv[0])
