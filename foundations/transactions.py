# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

transactions - Offers transactions mechanisms (begin/end/commit/rollback)

Copyright (C) 2005-2008 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.

"""

from licorn.foundations import process, exceptions, logging

class LicornTransaction :
	""" 2007/11 : This class has still to be really implemented and used wherever it is needed.

	"""
	def __init__ (self, name) :
		self.Begin(name)
		self.rollback_buffer = []
	def Begin(self, name) :
		""" placebo function, which only sets a name to the transaction.
			Eventually the name will be used somewhere in the future.
		"""
		
		assert name is not None and name != ""
	
		self.name = name

		#
		# if we are beginning after beeing already used for a previous transaction,
		# ensure rollback_buffer is empty before continuing.
		#
		if self.rollback_buffer is not None :
			self.rollback_buffer = []
	def Commit(self) :
		""" Commit is just a placebo function, to notice the transaction has been successful.
			We empty the rollback buffer : everything is ok, so nothing more will be rolled
			back.
			This way the same transaction can be reused after a commit(), without the need to
			create another object.
		"""
		self.rollback_buffer = []
	def PushCommand(self, command) :
		""" Add an undo action under the form of a shell command, which will be executed with licorn.foundations.process.syscmd()
		"""
		action = { 'type' : 'syscmd',
					'value' : command }
		self.rollback_buffer.append(action)
	def PushFunction(self, func_name, args = None, dict = None) :
		""" Add an undo action under the form of a python function, which will be executed with func( *args, **dict)
		"""
		action = { type : 'func',
					'value' : func_name,
					'args'	: args,
					'dict'	: dict }

		self.rollback_buffer.append(action)
	def Rollback(self) :
		""" Exectute all actions in the rollback_buffer in reverse order.
		"""
		for action in self.rollback_buffer :
			try :
				type = action['type']

				if type == 'syscmd' :

					process.syscmd(action['value'])

				elif type == 'func' :

					func_name 	= action['value']
					args		= action['args']
					dict		= action['dict']
				
					if callable(func_name) :
						func_name( *args, **dict)
					else :
						raise exceptions.LicornRuntimeError("uncallable rollback function « %s »." % str(func_name))
				else :
					raise exceptions.LicornRuntimeError("unknown type of rollback action « %s »." % str(type))
				
			except exceptions.LicornError, e :
				#
				# An error shouldn't happen during a rollback, this is BAD BAD BAD !
				# stop everything immediately, not to bork the system more.
				# 
				logging.error(str(e))
			except exceptions.LicornException, e :
				#
				# just warn about an exception, but don't halt the procedure.
				# remember we are rolling back, we must finish else the system
				# will be in a bad [undetermined] state.
				#
				logging.warning(str(e))

