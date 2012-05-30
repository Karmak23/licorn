# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

ltrace - light procedural trace (debug only)

	set environment variable LICORN_TRACE={all,configuration,core,…} and
	watch your terminal	flooded with information. You can combine values with
	pipes:
		export LICORN_TRACE=all
		export LICORN_TRACE=configuration
		export LICORN_TRACE="configuration|openldap"
		export LICORN_TRACE="users|backends|plugins"
		export LICORN_TRACE="groups|openldap"
		export LICORN_TRACE="machines|dnsmasq"
		(and so on…)

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""
import sys, os, threading, traceback, inspect

from time  import time, localtime, strftime
from types import *

# WARNING: please do not import anything from licorn here, except styles.
import styles
from styles  import *
from ltraces import *

# circumvent the `import *` local namespace duplication limitation.
stylize = styles.stylize

try:
	# If we can output cool formatting with color, we will do it.
	from pygments import highlight
	from pygments.lexers import PythonLexer
	from pygments.formatters import Terminal256Formatter

	lexer = PythonLexer()
	formatter = Terminal256Formatter()

except ImportError:
	# If we can't, just don't crash.
	highlight = lambda x, y, z: x
	lexer     = ''
	formatter = ''

def dump_one(obj_to_dump, long_output=False):
	try:
		return obj_to_dump.dump_status(long_output=long_output)

	except AttributeError:
		if long_output:
			return '%s %s:\n%s' % (
				str(obj_to_dump.__class__),
				stylize(ST_NAME, obj_to_dump.name),
				'\n'.join(['%s(%s): %s' % (
					stylize(ST_ATTR, key),
					type(getattr(obj_to_dump, key)),
					getattr(obj_to_dump, key))
						for key in dir(obj_to_dump)]))
		else:
			return '%s %s: %s' % (
				str(obj_to_dump.__class__),
				stylize(ST_NAME, obj_to_dump.name),
				[ key for key in dir(obj_to_dump)])
def ltrace_dump(*args, **kwargs):
	data = u'\n'.join(dump_one(arg) for arg in args)
	data += u'\n'.join(dump_one(value) for key, value in kwargs)
	return data
def ltrace_fulldump(*args, **kwargs):
	data = u'\n'.join(dump_one(arg, True) for arg in args)
	data += u'\n'.join(dump_one(value, True) for key, value in kwargs)
	return data
def ltrace_dumpstacks(signal=None, frame=None, thread_ident=None):
    id2name = dict((th.ident, th.name) for th in threading.enumerate())
    code = []
    for threadId, stack in sys._current_frames().items():
		if not thread_ident or threadId == thread_ident:
			code.append(_("\n# Thread: {0}({1})").format(id2name[threadId], threadId))
			for filename, lineno, name, line in traceback.extract_stack(stack):
				code.append(_('	File: "{0}", line {1}, in {2}').format(filename, lineno, name))
				if line:
					code.append("	  %s" % (line.strip()))
    return highlight("\n".join(code), lexer, formatter)
def ltrace_time():
	""" close http://dev.licorn.org/ticket/46 """
	t = time()
	return u'[%s%s]' % (
		strftime('%Y/%d/%m %H:%M:%S', localtime(t)), ('%.4f' % (t%1))[1:])
def ltrace_filename_and_lineno():
	"""Returns the current filename,  line number and function name.

		Ideas taken from:

		* http://stackoverflow.com/questions/3056048/filename-and-line-number-of-python-script
		* http://code.activestate.com/recipes/145297-grabbing-the-current-line-number-easily/

	"""

	#for frame, filename, line_num, func, source_code, source_index in inspect.stack():
	stack = inspect.stack()

	# NOTE: we use stack[2], because:
	#	- stack[0] is the current function 'ltrace_filename_and_lineno()' call
	#	- stack[1] is the 'ltrace()' or 'warn_exc()' call
	#	- stack[2] is logically the calling function,
	#		the real one we want informations from.

	return u'%s:%s in %s' % (stylize(ST_PATH, stack[2][1]),
							stylize(ST_COMMENT, stack[2][2]),
							stylize(ST_ATTR, stack[2][3] + u'()'))
def ltrace_function_name():

	#for frame, filename, line_num, func, source_code, source_index in inspect.stack():
	stack = inspect.stack()

	return u'%s (%s:%s)' % (stylize(ST_ATTR, stack[2][3] + u'()'),
							stylize(ST_PATH, stack[2][1]),
							stylize(ST_COMMENT, stack[2][2]))
def ltrace_frame_informations(with_var_info=False, func=repr, full=False, level=None):
	""" Returns informations about the current calling function.	"""

	if level is None:
		level = 1

	try:
		#for frame, filename, line_num, func, source_code, source_index in inspect.stack():
		stack = inspect.stack()

	except IndexError:
		# we just hit https://github.com/hmarr/django-debug-toolbar-mongo/pull/9
		# because we are called from inside a Jinja2 template.
		return _(u'stack frame unavailable in runtime-compiled code.')

	# we allow calling with e.g `level = 99` or `level = -1`,
	# for unlimited stack retrieval and display.
	if level >= len(stack) or level < 0:
		# We substract 2 because later we compute `xrange(3, 2 + level)`
		level = len(stack) - 2

	if full:
		def print_var(var):
			try:
				length = ', len=%s' % stylize(ST_VALUE, len(var))

			except:
				length = ''

			return '%s [class=%s%s]' % (stylize(ST_VALUE, func(var)),
				stylize(ST_ATTR, var.__class__.__name__), length)
	else:
		def print_var(var):
			return func(var)

	# args is a list of the argument
	# names (it may contain nested lists). varargs and keywords are the
	# names of the * and ** arguments or None. locals is the locals
	# dictionary of the given frame.

	if with_var_info:
		# stack[1] is the `ltrace_var()` call
		args, varargs, keywords, flocals = inspect.getargvalues(stack[1][0])

		return u'%s%s\t\t%s' % (
				# the *args of the `ltrace_var()` or `lprint()` call.
				# Use `repr()`.
				u', '.join(print_var(value) for value in flocals[varargs])
							if varargs else u'',

				# the **kwargs of the `ltrace_var()` or `lprint()` call. Use `repr()`
				u', '.join(u'%s=%s' % (stylize(ST_NAME, key), print_var(value))
						for key, value in flocals[keywords].iteritems())
							if keywords else u'',

				',\n'.join(stylize(ST_DEBUG, 'in %s (%s:%s)' % (
						# the name of the surrounding function
						stack[lev][3],
						# the filename of the surrounding function
						stack[lev][1],
						# the line number from the ltrace call (not the def of the calling function)
						stack[lev][2]
						)
					# we can trace the call from outside the original caller
					# if needed.
					) for lev in range(2, 2 + level))
			)
	else:
		# NOTE: we use stack[2], because:
		#	- stack[0] is the current function 'ltrace_frame_informations()' call
		#	- stack[1] is the 'ltrace()' or 'warn_exc()' call
		#	- stack[2] is logically the calling function,
		#		the real one we want informations from.
		args, varargs, keywords, flocals = inspect.getargvalues(stack[2][0])

		return u'%s(%s%s%s%s%s) in %s:%s%s' % (
				# name of the calling function
				stylize(ST_ATTR, stack[2][3]),

				# NOTE: we use repr() because in `__init__()`
				# methods `str()` might crash because the objects
				# are not yet fully initialized and can miss
				# attributes used in their `__str__()`.
				u', '.join(u'%s=%s' % (stylize(ST_NAME, var_name),
						print_var(flocals[var_name])) for var_name in args),

				# just a comma, to separate the first named args from *a and **kw.
				u', ' if (args and (varargs != [] or keywords != [])) else u'',

				# the *args. Use `repr()`
				u', '.join(print_var(value) for value in flocals[varargs])
						if varargs else u'',

				# just a comma, to separate *a and **kw.
				u', ' if (varargs != [] and keywords != []) else u'',

				# the **kwargs. use `repr()`
				u', '.join(u'%s=%s' % (stylize(ST_NAME, key), print_var(value))
						for key, value in flocals[keywords].iteritems())
							if keywords else u'',

				# filename of called function
				stylize(ST_PATH, stack[2][1]),
				#line number of called function
				stylize(ST_COMMENT, stack[2][2]),

				(
					u'\n\t\tfrom %s' % u'\n\t\tfrom '.join(
						u'%s:%s' % (
							stylize(ST_PATH, stack[lev][1]),
							stylize(ST_COMMENT, stack[lev][2])
						) for lev in xrange(3, 2 + level)
					)
				) if level > 1 else u''
			)
def lprint(*args, **kwargs):
	""" This function is unconditionnal (no use of `ltrace_level`), it's used
		only in development phases.

		We can now avoid the use of 'print' statements, replacing them with
		`lprint(...)`. Yeah !

		In development pre-commit phases, the use of this function will help
		removing them, because they advertise themselves from where they are
		called in the code.
	"""
	sys.stderr.write(u'%s %s\n' % (stylize(ST_IMPORTANT, '>>'),
	ltrace_frame_informations(with_var_info=True, func=str, full=True)))

	# stay compatible with assert, as all other `ltrace` functions.
	return True
def ltrace(module, message, *args):
	if  ltrace_level & module:
		if args:
			message = message.format(*(stylize(*x)
										if type(x) == TupleType
											and len(x) == 2
											and type(x[0]) == IntType
										else x
										for x in args))

		sys.stderr.write(u'%s %s: <%s> %s\n' % (
			stylize(ST_COMMENT, u'   %s' % ltrace_time()),
			stylize(ST_DEBUG, u'TRACE ' + module.name.rjust(TRACES_MAXWIDTH)),
			ltrace_filename_and_lineno(), message))
	return True
def ltrace_var(module, *args, **kwargs):
	if  ltrace_level & module:
		sys.stderr.write(u'%s %s: %s\n' % (
			stylize(ST_COMMENT, u'   %s' % ltrace_time()),
			stylize(ST_DEBUG, u'TRACE ' + module.name.rjust(TRACES_MAXWIDTH)),
			ltrace_frame_informations(with_var_info=True)))
	return True
def ltrace_func(module, at_exit=False, devel=False, level=None):

	if level is None:
		level = 1

	if  devel or (ltrace_level & module):
		if at_exit:
			sys.stderr.write(u'%s %s: < %s\n' % (
				stylize(ST_COMMENT, u'   %s' % ltrace_time()),
				stylize(ST_DEBUG, u'TRACE ' + module.name.rjust(TRACES_MAXWIDTH)),
				# at exit, we display just the function name.
				ltrace_function_name()))

		else:
			sys.stderr.write(u'%s %s: > %s\n' % (
				stylize(ST_COMMENT, u'   %s' % ltrace_time()),
				stylize(ST_DEBUG, u'TRACE ' + module.name.rjust(TRACES_MAXWIDTH)),
				# at enter, we dump all arguments of the function which is called.
				ltrace_frame_informations(level=level)))
	return True
def ltrace_locks(*args):
	if  ltrace_level & TRACE_LOCKS:
		if args:
			message = u', '.join(stylize(*x)
										if type(x) == TupleType
											and len(x) == 2
											and type(x[0]) == IntType
										else str(x)
										for x in args)
		else:
			message = u''

		sys.stderr.write(u'%s %s: <%s> %s\n' % (
			stylize(ST_COMMENT, u'   %s' % ltrace_time()),
			stylize(ST_DEBUG, u'TRACE ' + TRACE_LOCKS.name.rjust(TRACES_MAXWIDTH)),
			ltrace_filename_and_lineno(), message))
	return True

# the new LTRACE env variable takes precedence, then we try the old one
# LICORN_TRACE.
new_trace = os.getenv('LTRACE', None)
old_trace = os.getenv('LICORN_TRACE', None)

if new_trace != None or old_trace != None:

	if new_trace:
		env_trace = new_trace

	else:
		env_trace = old_trace

	ltrace_level = ltrace_str_to_int(env_trace)

	def insert_ltrace():
		# in trace mode, use python interpreter directly to avoid the -OO
		# inserted in all our executables.
		sys.stderr.write(_(u'Licorn®: {0} for {1}\n').format(
					stylize(ST_IMPORTANT, 'LTRACE enabled'),
					stylize(ST_COMMENT, env_trace)))
		return [ 'python' ]
else:
	ltrace_level = 0
	def insert_ltrace():
		return []

# this module is meant to be 'import *'ed
__all__ = ('ltrace_level', 'insert_ltrace', 'ltrace_time',
			# `dump_one()` is not exported
			'ltrace_dump', 'ltrace_fulldump', 'ltrace_dumpstacks',
			'ltrace_frame_informations', 'ltrace_filename_and_lineno',
			'ltrace_function_name', 'lprint', 'ltrace', 'ltrace_var',
			'ltrace_locks', 'ltrace_func')
