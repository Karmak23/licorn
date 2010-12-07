# -*- coding: utf-8 -*-
"""
Licorn foundations: messaging.
classes used for Inter-thread and inter-machines communication through Pyro.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys
import Pyro.core, Pyro.util
from threading import current_thread
# WARNING: don't import logging here (circular loop).
import exceptions
from ltrace    import ltrace
from base      import NamedObject, pyro_protected_attrs
from constants import message_type, verbose, interactions
from ttyutils  import interactive_ask_for_repair

class LicornMessage(Pyro.core.CallbackObjBase):
	def __init__(self, data='empty_message...', my_type=message_type.EMIT, 
		interaction=None, answer=None, auto_answer=None, channel=2):

		Pyro.core.CallbackObjBase.__init__(self)

		assert ltrace('objects', '''| LicornMessage(data=%s,type=%s,interaction=%s,'''
			'''answer=%s,auto_answer=%s,channel=%s)''' % (data, my_type,
			interaction, answer, auto_answer, channel))

		self.data        = data
		self.type        = my_type
		self.interaction = interaction
		self.answer      = answer
		self.auto_answer = auto_answer
		self.channel     = channel
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
		self.addr = ip_address
	def process(self, message, callback):
		""" process a message. """

		if message.type == message_type.EMIT:
			 # We are in the server, the message has just been built.
			# Forward it nearly "as is". Only the message type is changed,
			# to make us know it has been processed one time since emission,
			# and thus the next hop will be the client, which has the task
			# to display it, and eventually get an interactive answer.

			assert ltrace('messaging', '  MessageProcessor.process(EMIT)')

			if message.interaction:

				if message.interaction == interactions.ASK_FOR_REPAIR:

					message.answer = interactive_ask_for_repair(message.data,
						auto_answer=message.auto_answer)
				else:
					assert ltrace('messaging',
						'unsupported interaction type in message %s.' % message)
					message.answer = None

				message.type = message_type.ANSWER
				return callback.process(message, self.getAttrProxy())
			else:
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
