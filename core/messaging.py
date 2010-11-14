# -*- coding: utf-8 -*-
"""
Licorn foundations: messaging.
classes used for Inter-thread and inter-machines communication through Pyro.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import sys, os, time
import Pyro.core, Pyro.util

from licorn.foundations           import options, logging, exceptions
from licorn.foundations.ltrace    import ltrace
from licorn.foundations.constants import message_type, verbose, interactions
from licorn.foundations.ttyutils  import interactive_ask_for_repair

from licorn.core         import LMC
from licorn.core.objects import LicornBaseObject

class MessageProcessor(LicornBaseObject, Pyro.core.CallbackObjBase):
	channels = {
		1:	sys.stdout,
		2:	sys.stderr,
		}

	def __init__(self, verbose=verbose.NOTICE, ip_address=None):
		Pyro.core.CallbackObjBase.__init__(self)
		LicornBaseObject.__init__(self, 'msgproc')

		self.verbose = verbose
		self.addr = ip_address
		assert ltrace('objects', '| MessageProcessor(%s)' % self.verbose)
	def set_controllers(self, controllers):
		self.controllers = controllers
	def process(self, message, callback):
		""" process a message. """

		if message.type == message_type.EMIT:
			# We are in the server, the message has just been built.
			# Forward it nearly "as is". Only the message type is changed,
			# to make us know it has been processed one time since emission,
			# and thus the next hop will be the client, which has the task
			# to display it, and eventually get an interactive answer.

			assert ltrace('objects', '  MessageProcessor.process(EMIT)')

			if message.interaction:

				if message.interaction == interactions.ASK_FOR_REPAIR:

					message.answer = interactive_ask_for_repair(message.data,
						auto_answer=message.auto_answer)
				else:
					assert ltrace('objects',
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

			assert ltrace('objects', '  MessageProcessor.process(ANSWER)')

			#message.channel.write(message.data)
			return message.answer
		elif message.type == message_type.PUSH_STATUS:

			self.controllers.machines.update_status(mid=message.sender,
				status=message.status)

		else:
			raise exceptions.LicornRuntimeException('''Unrecognized message '''
				'''type %s for message %s.''' % (message.type, message))
