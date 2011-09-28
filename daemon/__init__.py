# -*- coding: utf-8 -*-
"""
Licorn Daemon - http://docs.licorn.org/daemon/index.html

:copyright: 2009-2010 Olivier Cortès <olive@deep-ocean.net>

:license: GNU GPL version 2

"""

#: import gettext for all licorn code, and setup utf-8 codeset.
#: this is particularly needed to avoid #531 and all other kind
#: of equivalent problems.
import gettext
gettext.install('licorn', unicode=True)

import sys, os, signal, termios

from threading   import current_thread

from licorn.foundations           import options, logging, exceptions
from licorn.foundations           import process, pyutils, ttyutils
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace, insert_ltrace, dump, fulldump
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import NamedObject, MixedDictObject, EnumDict, Singleton
from licorn.foundations.thread    import _threads, _thcount
from licorn.foundations.constants import verbose


class LicornThreads(MixedDictObject, Singleton):
	pass
class LicornQueues(MixedDictObject, Singleton):
	pass

class InternalEvent(NamedObject):
	def __init__(self, _event_name, *args, **kwargs):
		NamedObject.__init__(self, _event_name)

		if 'synchronous' in kwargs:
			self.synchronous = kwargs['synchronous']
			del kwargs['synchronous']
		else:
			self.synchronous = False

		if 'callback' in kwargs:
			self.callback = kwargs['callback']
			del kwargs['callback']
		else:
			self.callback = None

		self.args        = args
		self.kwargs      = kwargs

roles = EnumDict('licornd_roles', from_dict={
		'UNSET':  1,
		'SERVER': 2,
		'CLIENT': 3
	})

priorities = EnumDict('service_priorities', from_dict={
		'LOW':  20,
		'NORMAL': 10,
		'HIGH': 0
	})

# LicornDaemonInteractor is an object dedicated to user interaction when the
# daemon is started in the foreground.
class LicornDaemonInteractor(ttyutils.LicornInteractor):
	def __init__(self, daemon):

		assert ltrace(TRACE_INTERACTOR, '| LicornDaemonInteractor.__init__()')

		super(LicornDaemonInteractor, self).__init__('interactor')

		self.long_output   = False
		self.daemon        = daemon
		self.terminate     = self.daemon.terminate
		self.pname         = daemon.name

		self.handled_chars = {
			'f'   : self.toggle_long_output,
			'l'   : self.toggle_long_output,
			'c'   : self.garbage_collection,
			'w'   : self.show_watches,
			't'   : self.show_threads,
			'v'   : self.raise_verbose_level,
			'q'   : self.lower_verbose_level,
			'' : self.send_sigusr1_signal,	# ^R (refresh / reload)
			'' : self.dump_daemon_status,	# ^T (display status; idea from BSD, ZSH)
			' '   : self.clear_then_dump_status,
			''  : self.clear_then_dump_status, # ^Y (display status after clearing the screen
			'i'   : self.interact,
			}
		self.avoid_help = (' ', )
	def toggle_long_output(self):
		self.long_output = not self.long_output

		logging.notice(_(u'{0}: switched '
			u'long_output status to {1}.').format(
				self.name, _(u'enabled')
					if self.long_output
					else _(u'disabled')))
	toggle_long_output.__doc__ = _(u'toggle [dump status] long ouput on or off')
	def garbage_collection(self):
		sys.stderr.write(_(u'Console-initiated '
			u'garbage collection and dead thread '
			u'cleaning.') + '\n')

		self.daemon.clean_objects()
	garbage_collection.__doc__ = _(u'operate a manual garbage collection in '
									u'the daemon\'s memory, and run other '
									u'clean-related things')
	def show_watches(self):
		w = self.daemon.threads.INotifier._wm.watches

		sys.stderr.write('\n'.join(repr(watch)
			for key, watch in w)
			+ 'total: %d watches\n' % len(w))
	show_watches.__doc__ = _(u'show the INotifier watches (WARNING: this '
							u'can flood your terminal)')
	def show_threads(self):
		sys.stderr.write(_(u'{0} active threads: '
			u'{1}').format(
				_thcount(), _threads()) + '\n')
	show_threads.__doc__ = _(u'show all threads names and their current status')
	def raise_verbose_level(self):
		if options.verbose < verbose.DEBUG:
			options.verbose += 1

			self.daemon.options.verbose += 1

			logging.notice(_(u'{0}: increased '
				u'verbosity level to '
				u'{1}.').format(self.name,
					stylize(ST_COMMENT,
						verbose[options.verbose])))

		else:
			logging.notice(_(u'{0}: verbosity '
				u'level already at the maximum '
				u'value ({1}).').format(
					self.name, stylize(ST_COMMENT,
						verbose[options.verbose])))
	raise_verbose_level.__doc__ = _(u'increase the daemon console verbosity level')
	def lower_verbose_level(self):
		if options.verbose > verbose.NOTICE:
			options.verbose -= 1

			self.daemon.options.verbose -= 1

			logging.notice(_(u'{0}: decreased '
				u'verbosity level to '
				u'{1}.').format(self.name,
					stylize(ST_COMMENT,
						verbose[options.verbose])))

		else:
			logging.notice(_(u'{0}: verbosity '
				u'level already at the minimum '
				u'value ({1}).').format(
					self.name, stylize(ST_COMMENT,
						verbose[options.verbose])))
	lower_verbose_level.__doc__ = _(u'decrease the daemon console verbosity level')
	def send_sigusr1_signal(self):
		#sys.stderr.write('\n')
		self.restore_terminal()
		os.kill(os.getpid(), signal.SIGUSR1)
	send_sigusr1_signal.__doc__ = _(u'{0}: Send URS1 signal (and '
									u'consequently reload daemon)').format(
										stylize(ST_OK, 'Control-R'))
	def dump_daemon_status(self):
		sys.stderr.write(self.daemon.dump_status(
			long_output=self.long_output))
	dump_daemon_status.__doc__ = _(u'{0}: dump daemon status').format(
										stylize(ST_OK, 'Control-T'))
	def clear_then_dump_status(self):
		ttyutils.clear_terminal(sys.stderr)
		sys.stderr.write(self.daemon.dump_status(
			long_output=self.long_output))
	clear_then_dump_status.__doc__ = _(u'{0} or {1}: dump daemon status '
										u'after having cleared the '
										u'screen').format(
											stylize(ST_OK, _(u'Space')),
											stylize(ST_OK, 'Control-Y'))
	def interact(self):
		logging.notice(_('%s: Entering interactive mode. '
			'Welcome into licornd\'s arcanes…') % self.name)

		# trap SIGINT to avoid shutting down the daemon by
		# mistake. Now Control-C is used to reset the
		# current line in the interactor.
		def interruption(x, y):
			raise KeyboardInterrupt

		signal.signal(signal.SIGINT, interruption)

		from licorn.core import version, LMC

		# NOTE: we intentionnaly restrict the interpreter
		# environment, else it
		interpreter = self.__class__.HistoryConsole(
			locals={
				'version'       : version,
				'daemon'        : self.daemon,
				'queues'        : self.daemon.queues,
				'threads'       : self.daemon.threads,
				'uptime'        : self.daemon.uptime,
				'LMC'           : LMC,
				'dump'          : dump,
				'fulldump'      : fulldump,
				'options'       : options,
				},
			filename="<licornd_console>",
			histfile=os.path.expanduser('~/.licorn/licornd_history'))

		# put the TTY in standard mode (echo on).
		self.restore_terminal()
		sys.ps1 = u'licornd> '
		sys.ps2 = u'...'
		interpreter.init_history()

		interpreter.interact(
				banner=_(u'Licorn® {0}, Python {1} '
						u'on {2}').format(version,
							sys.version.replace('\n', ''),
							sys.platform))

		interpreter.save_history()

		# restore signal and terminal handling
		signal.signal(signal.SIGINT,
			lambda x, y: self.daemon.terminate)

		# take the TTY back into command mode.
		self.prepare_terminal()

		logging.notice(_(u'%s: leaving interactive mode. '
			u'Welcome back to Real World™.') % self.name)
	interact.__doc__ = _(u'Run an interactive console')
