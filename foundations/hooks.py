# -*- coding: utf-8 -*-
"""
Licorn hook system.

Every src/*.py or module/sub-module can register one or
more function to be called on these events.

Copyright 2006-2008 (C) Olivier Cortès <oc@5sys.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import sys
from licorn.foundations import exceptions, styles


# TODO: make this module create a singleton object, else this will not work as expected...

_hooks = {	'onError'     : [],
			'onInterrupt' : [],		
			'onQuit'      : [],
			'onLoad'      : [],
			'onSuccess'   : [],
		}

def register_event(event) :
	""" Add a new event to the event table.
	"""

	global _hooks

	if event in _hooks.keys() :
		raise exceptions.LicornHookEventException('Event "%s" already exists in the event table.' % event)
	else :
		_hooks[event] = []
def unregister_event(event) :
	""" Remove an event from the event table.
	"""

	global _hooks

	if event in _hooks.keys() :
		if _hooks[event] != [] :
			from licorn.foundations import logging
			logging.warning('''When removing event '%s', hooks list not empty !''' % event)

		del _hooks[event]
	else :
		raise exceptions.LicornHookEventException('''Event "%s" doesn't exist in the events table.''' % event)
		
def register_hook(event, func_name, args = None, dict = None) :
	""" Add a function to be called when an event happens.
		args and dict will be used as « func_name ( *args, **dict ) », like in the
		old apply() method.
	"""
	if event in _hooks.keys() :
		_hooks[event].append( { 'func_name' : func_name, 'args' : args, 'dict' : dict } )
	else :
		raise exceptions.LicornHookEventError('''Event "%s" doesn't exist in the events table.''' % event)
def unregister_hook( event, func_name ) :
	""" Search for func_name in event's hooks, and delete it.
	"""
	found = False
	counter = 0
	for hook in _hooks[event] :
		if hook['func_name'] == func_name :
			found = counter
			break
		counter+=1
	if found :
		del _hooks[event][found]

def run_hooks(event) :

	assert event is not None

	if event in _hooks.keys() :

		for hook in _hooks[event] :
			try :
				hook_func = hook['func_name']
				hook_args = hook['args']
				hook_dict = hook['dict']

				if callable(hook_func) :
					hook_func( *hook_args, **hook_dict)
				else :
					# don't fail if some hooks are uncallable, others must be called !
					from licorn.foundations import logging
					logging.warning('uncallable hook : ' + str(hook_func))
		
			except exceptions.LicornException, e :
				#
				# we can't call licorn.error(), else run_hooks() will we called 
				# recursively if we've just been called by licorn.error() ('onError' event).
				# 
				# TODO: now we can do it if we priorly remove the 'onError' Event, but this 
				# is a little hackish and not very semantic. Think about it before implementing.

				sys.stderr.write(styles.stylize(styles.ST_BAD, 'BAD, BAD : exception raised from inside an "%s" hook : %s.'% (styles.stylize(styles.ST_HOOK, event), str(e))) + "\n")
				sys.exit(127)

	else :
		from licorn.foundations import logging
		logging.warning("run_hook(): Event '%s' doesn't exist in the events table !")

