# -*- coding: utf-8 -*-
"""
	Licorn foundations: messaging
	~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	Classes used for Inter-thread and inter-machines communication through Pyro.

	:copyright: (C) 2010 Olivier Cortès <oc@meta-it.fr>
	:license: Licensed under the terms of the GNU GPL version 2.
"""

import sys, os, getpass, time, code, rlcompleter, uuid, __builtin__
import Pyro.core, Pyro.util, Pyro.configuration

from threading import current_thread, enumerate

# WARNING: don't import logging here (circular loop).
import exceptions, ttyutils, pyutils
from _options  import options
from styles    import *
from ltrace    import *
from ltraces   import *
from threads   import RLock
from base      import NamedObject, pyro_protected_attrs
from constants import message_type, verbose, interactions

def remote_output(text_message, clear_terminal=False, *args, **kwargs):
	""" Output a text message remotely, in CLI caller process, whose
		reference is stored in :obj:`current_thread().listener`. """
	try:
		return current_thread().listener.process(
			LicornMessage(data=text_message,
							channel=kwargs.pop('_message_channel_', 1),
							clear_terminal=clear_terminal, **kwargs),
			options.msgproc.getProxy())
	except AttributeError:
		import logging
		logging.exception(_(u'{0}.remote_output() aborted, no listener '
							u'registered'), current_thread().name)
class LicornMessage(Pyro.core.CallbackObjBase):
	""" Small message object pushed back and forth between Pyro instances on one
		or more physical machines.
	"""
	def __init__(self, data='empty_message...', my_type=message_type.EMIT,
					interaction=None, answer=None, auto_answer=None, channel=2,
					clear_terminal=False, char_delay=None, word_delay=None,
					**kwargs):

		Pyro.core.CallbackObjBase.__init__(self)

		assert ltrace(TRACE_OBJECTS, '''| LicornMessage(data=%s,type=%s,interaction=%s,'''
			'''answer=%s,auto_answer=%s,channel=%s)''' % (data, my_type,
			interaction, answer, auto_answer, channel))

		#: the message data as str()
		self.data        = data

		#: the message type as foundations.constants.messages_type
		self.type        = my_type

		#: the interaction type (if any), as foundations.constants.interactions_type
		self.interaction = interaction

		#: the answer to the original message, as str()
		self.answer      = answer

		#: an eventual auto answer, as bool()
		self.auto_answer = auto_answer

		#: the channel to push the message to, as sys.std{out,err}
		self.channel     = channel

		self.clear_terminal = clear_terminal

		# fancy things, not used a lot.
		self.char_delay = char_delay
		self.word_delay = word_delay
class ListenerObject(object):
	""" This class is about:
		* the listener Pyro proxy object in the current thread: this
			"listener" refers to the remote client connected to the current
			instance; this listener will receive all output from the current
			thread running one or more method on the server-side.
		* the "by-thread" gettext implementation, permitting every daemon
			thread to output messages in the languages of the connected client.
	"""

	class BufferedInterpreter(code.InteractiveInterpreter):
		""" This one comes from rfoo, verbatim. I tried to implement it another way,
			but the rffo way is really cool.
			http://code.google.com/p/rfoo/
		"""
		def __init__(self, *args, **kwargs):
			code.InteractiveInterpreter.__init__(self, *args, **kwargs)
			self.output_buffer = ''
		def write(self, data):
			self.output_buffer += data

	def noop(self):
		""" No-op function, called when remotely connecting to Pyro, to check if
			link is OK between the server and the client: Pyro is lazy and
			without this call we can't really know if the connection is
			established, or if there is a server listening on the remote side!
		"""
		assert ltrace_func(TRACE_MESSAGING)
		return True
	def set_listener(self, listener):
		""" We will store the reference to the client-side listener as an
			attribute of the current thread, for any server-side output to
			go to him.

			:param listener: the client-side Pyro proxy for the client-side
				:class:`MessageProcessor` instance.
		"""
		current_thread().listener = listener
	def setup_listener_gettext(self):
		""" define a "_" attribute on the current thread, based on languages
			known by the current daemon instance. The "_" will be called,
			afterwise, by the global "_" builtin, which will look for it in
			every running thread.
		"""
		th = current_thread()

		try:
			th._ = th._licornd.langs[th.listener.lang].ugettext

		except KeyError:
			# the daemon doesn't have the client lang installed. Not a problem.
			# Still, make a shortcut to the daemon's default translator to
			# avoid trigerring an exception at every call of our translator
			# wrapper.
			th._ = __builtin__.__dict__['_orig__']
	def set_listener_verbose(self, listener, verbose_level):
		""" Adjust in real-time the verbosity of the listener proxy,
			server-side. This method is called by the client, to reflect its
			verbosity level, which can be switched in real-time too.

			As the output are really done on the server-side, because the
			client just "listens" to server-side output, the verbosity level
			must be really changed here.

			.. note:: the verbosity level is protected by a :class:`RLock`, to
			avoid reading it in the output-thread, while changing it in another
			thread (for each client connection, there might be multiple threads
			on the server, depending on the operation).
		"""

		found = None

		with options.monitor_lock:
			# we need to search: the current thread is not necessarily the
			# one which is operating for the client-side, in which the
			# original verbose_level has been set.
			for t in enumerate():
				if hasattr(t, 'listener') and t.listener == listener:
					found = t
					break

		if found:
			with found.monitor_lock:
				found.listener.verbose = verbose_level

	# ========================================= CLI "GET" surrounding functions

	def register_monitor(self, facilities):

		# we have to import 'logging' not at the top of the module
		import logging

		self.setup_listener_gettext()

		t = current_thread()

		t.monitor_facilities = ltrace_str_to_int(facilities)

		t.monitor_uuid = uuid.uuid4()

		logging.notice(_(u'New trace session started with UUID {0}, '
			u'facilities {1}.').format(stylize(ST_UGID, t.monitor_uuid),
				stylize(ST_COMMENT, facilities)))

		# The monitor_lock avoids collisions on listener.verbose
		# modifications while a flood of messages are beiing sent
		# on the wire. Having a per-thread lock avoids locking
		# the master `options.monitor_lock` from the client side
		# when only one monitor changes its verbose level. This
		# is more fine grained.
		t.monitor_lock = RLock()

		with options.monitor_lock:
			options.monitor_listeners.append(t)

		# return the UUID of the thread, so that the remote side
		# can detach easily when it terminates.
		return t.monitor_uuid
	def unregister_monitor(self, muuid):

		# we have to import 'logging' not at the top of the module
		import logging

		self.setup_listener_gettext()

		found = None

		with options.monitor_lock:
			for t in options.monitor_listeners[:]:
				if t.monitor_uuid == muuid:
					found = t
					options.monitor_listeners.remove(t)
					break

		if found:
			del t.monitor_facilities
			del t.monitor_uuid
			del t.monitor_lock

		else:
			logging.warning(_(u'Monitor listener with UUID %s not found!') % muuid)

		logging.notice(_(u'Trace session UUID {0} ended.').format(
													stylize(ST_UGID, muuid)))

	# ====================================== Licornd remote interactive console

	def console_start(self, is_tty=True):
		# we have to import 'logging' not at the top of the module
		import logging, events

		# other foundations
		from workers import workers

		# import things that we need in the remote console
		from licorn.core   import version, LMC
		from threads       import RLock, Event

		# This is a little too much
		#self._console_namespace = sys._getframe(1).f_globals

		self._console_isatty    = is_tty
		self._console_namespace = {
				'version'       : version,
				'daemon'        : self.licornd,
				'queues'        : workers.queues,
				'threads'       : self.licornd.threads,
				'uptime'        : self.licornd.uptime,
				'LMC'           : LMC,
				'dump'          : ltrace_dump,
				'fulldump'      : ltrace_fulldump,
				'dumpstacks'    : ltrace_dumpstacks,
				'options'       : options,
				'RLock'         : RLock,
				'Event'         : Event,
				'workers'       : workers,
				'events'        : events,
				'LicornEvent'   : events.LicornEvent,
			}

		self._console_interpreter = self.__class__.BufferedInterpreter(
														self._console_namespace)
		self._console_completer   = rlcompleter.Completer(self._console_namespace)

		t = current_thread()

		logging.notice(_(u'{0}: Interactive console requested by {1} '
			u'from {2}.').format(self.licornd,
			stylize(ST_NAME, t._licorn_remote_user),
			stylize(ST_ADDRESS, '%s:%s' % (t._licorn_remote_address,
											t._licorn_remote_port))),
											to_listener=False)
		if is_tty:
			remote_output(_(u'Welcome into licornd\'s arcanes…') + '\n',
									clear_terminal=True, char_delay=0.025)
		else:
			remote_output(_(u'>>> Entered batched remote console.') + '\n',
							_message_channel_=2)
	def console_stop(self):
		# we have to import 'logging' not at the top of the module
		import logging

		t = current_thread()

		logging.notice(_(u'{0}: Interactive console terminated by {1} '
							u'from {2}.').format(self.licornd,
									stylize(ST_NAME, t._licorn_remote_user),
									stylize(ST_ADDRESS, '%s:%s' % (
											t._licorn_remote_address,
											t._licorn_remote_port))),
											to_listener=False)

		if self._console_isatty:
			# NOTE: there are console non-breakable spaces at choosen
			# places in the sentences for enhanced graphical effect.
			remote_output(_(u'Welcome back to Real World™. Have a nice day!')
													+ u'\n', word_delay=0.25)
		else:
			remote_output(_(u'>>> batched remote console terminated.') + '\n',
							_message_channel_=2)

	def console_complete(self, phrase, state):
		return self._console_completer.complete(phrase, state)
	def console_runsource(self, source, filename=None):
		"""Variation of InteractiveConsole which returns expression
		result as second element of returned tuple.
		"""

		if filename is None:
			filename = '<remote_console_input>'

		# Inject a global variable to capture expression result.
		# This implies the fix for http://dev.licorn.org/ticket/582
		self._console_namespace['_console_result_'] = None

		try:
			# In case of an expression, capture result.
			compile(source, filename, 'eval')
			source = '_console_result_ = ' + source

		except SyntaxError:
			pass

		more = self._console_interpreter.runsource(source, filename)
		result = self._console_namespace.pop('_console_result_')

		if more is True:
			# nothing to display, just return, for the remote side to continue.
			return True, ''

		output = self._console_interpreter.output_buffer
		self._console_interpreter.output_buffer = ''

		if result is not None:
		# NOTE: don't pprint, it avoids the ascii-escaped strings to be
		# interpreted correctly.
		#	result = pprint.pformat(result)
			output += str(result) + '\n'

		return False, output
class MessageProcessor(NamedObject, Pyro.core.CallbackObjBase):
	""" MessageProcessor  is used for messaging between core objects,
		daemon and Licorn® clients.
	"""
	channels = {
		1:	sys.stdout,
		2:	sys.stderr,
		}
	_licorn_protected_attrs = (
			NamedObject._licorn_protected_attrs
			+ pyro_protected_attrs
		)
	def __init__(self, verbose=verbose.NOTICE, ip_address=None):
		NamedObject.__init__(self, name='msgproc')
		Pyro.core.CallbackObjBase.__init__(self)
		assert ltrace(TRACE_MESSAGING, '| MessageProcessor.__init__(%s, %s)' % (
			verbose, ip_address))

		self.verbose = verbose
		self.lang    = os.getenv('LANG', None)

		#: IP address of initial message sender, if provided, as str('X.X.X.X')
		self.addr = ip_address
	def process(self, message, callback):
		""" process a message and sends answer via callback if needed. """

		if message.type == message_type.EMIT:
			# We are in the server, the message has just been built.
			# Forward it nearly "as is". Only the message type is changed,
			# to make us know it has been processed one time since emission,
			# and thus the next hop will be the client, which has the task
			# to display it, and eventually get an interactive answer.

			assert ltrace(TRACE_MESSAGING, '  MessageProcessor.process(EMIT)')

			if message.interaction:

				if message.interaction == interactions.ASK_FOR_REPAIR:

					message.answer = ttyutils.interactive_ask_for_repair(message.data,
						auto_answer=message.auto_answer)

				elif  message.interaction == interactions.GET_PASSWORD:

					message.answer = getpass.getpass(message.data)

				else:
					assert ltrace(TRACE_MESSAGING,
						'unsupported interaction type in message %s.' % message)
					message.answer = None

				message.type = message_type.ANSWER
				return callback.process(message, self.getAttrProxy())

			else:
				if message.clear_terminal:
					ttyutils.clear_terminal(MessageProcessor.channels[message.channel])

				chan_flush = MessageProcessor.channels[message.channel].flush
				chan_write = MessageProcessor.channels[message.channel].write

				if message.word_delay:
					delay = message.word_delay
					for word in message.data.split(' '):
						chan_write(word + ('' if word.endswith('\n') else ' '))
						chan_flush()
						time.sleep(delay)

				elif message.char_delay:
					delay = message.char_delay
					for char in message.data:
						chan_write(char)
						chan_flush()
						time.sleep(min(delay*4, 0.4) if char == ' ' else delay)

				else:
					chan_write(message.data)

				message.answer = None

		elif message.type == message_type.ANSWER:
			# We are on the server, this is the answer from the client to
			# ourquestion. Return it directly to the calling process. The
			# message loop ends here.

			assert ltrace(TRACE_MESSAGING, '  MessageProcessor.process(ANSWER)')

			#message.channel.write(message.data)
			return message.answer
		elif message.type == message_type.PUSH_STATUS:

			# FIXME: is this really needed ? will the status be really pushed by this way ?
			from licorn.core         import LMC
			LMC.machines.update_status(mid=message.sender,
				status=message.status)

		else:
			raise exceptions.LicornRuntimeException('''Unrecognized message '''
				'''type %s for message %s.''' % (message.type, message))
