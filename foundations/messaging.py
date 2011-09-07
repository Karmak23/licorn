# -*- coding: utf-8 -*-
"""
	Licorn foundations: messaging
	~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	Classes used for Inter-thread and inter-machines communication through Pyro.

	:copyright: (C) 2010 Olivier Cortès <oc@meta-it.fr>
	:license: Licensed under the terms of the GNU GPL version 2.
"""

import sys, os, getpass
import Pyro.core, Pyro.util
from threading import current_thread
# WARNING: don't import logging here (circular loop).
import exceptions, ttyutils
from ltrace    import ltrace
from base      import NamedObject, pyro_protected_attrs
from constants import message_type, verbose, interactions

class LicornMessage(Pyro.core.CallbackObjBase):
	""" Small message object pushed back and forth between Pyro instances on one
		or more physical machines.
	"""
	def __init__(self, data='empty_message...', my_type=message_type.EMIT,
					interaction=None, answer=None, auto_answer=None, channel=2,
					clear_terminal=False):

		Pyro.core.CallbackObjBase.__init__(self)

		assert ltrace('objects', '''| LicornMessage(data=%s,type=%s,interaction=%s,'''
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
class ListenerObject(object):
	""" note the listener Pyro proxy object in the current thread.
		This is quite a hack but will permit to store it in a centralized manner
		and not forward it everywhere in the code."""
	def set_listener(self, listener):
		current_thread().listener = listener
class MessageProcessor(NamedObject, Pyro.core.CallbackObjBase):
	""" MessageProcessor is not really a controller, thus it doesn't inherit
		from CoreController. Used only for messaging between core objects,
		daemon and other parts of Licorn®.

		It stills belongs to core, though, because this is a central part of
		Licorn® internals. """
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
		assert ltrace('messaging', '| MessageProcessor.__init__(%s, %s)' % (
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

			assert ltrace('messaging', '  MessageProcessor.process(EMIT)')

			if message.interaction:

				if message.interaction == interactions.ASK_FOR_REPAIR:

					message.answer = ttyutils.interactive_ask_for_repair(message.data,
						auto_answer=message.auto_answer)

				elif  message.interaction == interactions.GET_PASSWORD:

					message.answer = getpass.getpass(message.data)

				else:
					assert ltrace('messaging',
						'unsupported interaction type in message %s.' % message)
					message.answer = None

				message.type = message_type.ANSWER
				return callback.process(message, self.getAttrProxy())

			else:
				if message.clear_terminal:
					ttyutils.clear_terminal(MessageProcessor.channels[message.channel])
				MessageProcessor.channels[message.channel].write(message.data)
				message.answer = None

		elif message.type == message_type.ANSWER:
			# We are on the server, this is the answer from the client to
			# ourquestion. Return it directly to the calling process. The
			# message loop ends here.

			assert ltrace('messaging', '  MessageProcessor.process(ANSWER)')

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
