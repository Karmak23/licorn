# -*- coding: utf-8 -*-
"""
Licorn foundations: configuration parser - http://docs.licorn.org/

This configuration parser is completely generic. It's based on
:py:mod:`pygments`, and reads any configuration file into an object able to
modify it without altering comments, directive ordering, etc.

It implements directive dependancies (eg. “acl directives come before
http_access directive”) and same-directive ordering (eg. “correct ordering
for moultiple allow,deny directives”), in memory parse-from-strings objects,
2-objects merging (with configurable conflicts behaviour but only
per-object behaviour, not per-directive), and full check of configuration
objects. Obviously it implements save/write.

It is meant to allow automated configuration alteration without interfering
with human editing, as much as possible. See Licorn® extensions which use this
module, for details and philosophy.

.. versionadded:: 1.6

:copyright:
	* 2010-2012 Olivier Cortès <olive@licorn.org>
	* partial 2011-2012 META IT http://meta-it.fr/

:license: GNU GPL version 2

"""

# Python imports
import itertools
from threading import current_thread

# Pygments imports
from pygments.token      import *
from pygments.filters    import RaiseOnErrorTokenFilter
from pygments.formatters import Terminal256Formatter, NullFormatter

# Other Licorn® foundations imports
import exceptions, styles, logging
from styles  import *
from ltrace  import ltrace, ltrace_func, ltrace_var
from ltraces import TRACE_CONFIG

stylize = styles.stylize

class PartialMatch(BaseException):
	""" Used in search methods """

	def __init__(self, match, *args, **kwargs):
		self.match = match
		BaseException.__init__(self, *args, **kwargs)
class ConfigurationToken(object):
	""" Very small and read-only-typed configuration token (the value can be
		changed, not the type; it is a pygments type).

		The R/O implementation lies in python properties.
		The very small nature is thanks to __slots__.

		This class implements :meth:`__eq__` and :meth:`__ne__` methods, which
		are used in :class:`ConfigurationFile` *ordering check* methods to
		compare tokens and quickly (un-)select directives.
	"""
	__slots__ = ('__type', '__value')

	def __init__(self, ttype, value):
		self.__type  = ttype
		self.__value = value
	def __str__(self):
		return self.value
	def __repr__(self):
		return '%s(%s), %s(%s)' % (self.__class__.__name__, self.__type,
									type(self.__value), self.value)
	@property
	def type(self):
		return self.__type
	@property
	def value(self):
		return self.__value
	@value.setter
	def value(self, newval):
		self.__value = newval
	def __eq__(self, other):
		return self.__type == other.type and self.__value == other.value
	def __ne__(self, other):
		return self.__type != other.type or self.__value != other.value
	def to_pygments(self):
		return self.__type, self.__value
class ConfigurationBlock(object):
	""" Represents a standard and usually useless configuration block. Holds
		tokens which are not considered as a real value for a given
		configuration file (typically: Comments), but must be kept for the
		administrator to remain happy when he/she edits the configuration
		file manually. """

	# gentle memory use. We can have a lot of blocks coming from lots of files.
	__slots__ = ( 'value', 'parent', )

	def __init__(self, value, parent):

		self.value  = value
		self.parent = parent
	def __str__(self):
		return ''.join(str(x) for x in self.value)
	def __repr__(self):
		return '%s: %r' % (self.__class__.__name__, self.value)
	@property
	def flatenned(self):
		return self.value
class ConfigurationDirective(object):

	# reverse index for quick finding configuration directives
	_by_name = {}

	@classmethod
	def by_name(cls, caller, directive):
		return cls._by_name['%s_%s' % (caller, directive)]

	# gentle memory use. standard configuration files can hold a bunch of directives.
	__slots__ = ('lineno', 'name', 'name_token', 'value', 'parent', 'end_tokens', )

	def __init__(self, lineno, name, value, parent):
		self.parent = parent
		self.lineno = lineno

		# name is a token, let's store the string/unicode value solely
		# for faster access.
		self.name_token = name
		self.name	    = name.value

		self.end_tokens = []

		try:
			# Strip the eventual (error-prone and useless) end-of-line
			# Comment and Whitespace from our real value, but keep them safe
			# for the rendering phase.
			while value[-1].type in self.parent.token_ignored_types:
				self.end_tokens[0:0] = [ value[-1] ]
				del value[-1]

		except IndexError:
			pass

		self.value = value

		index_key = '%s_%s' % (parent, name)

		curvals = self.__class__._by_name.get(index_key, [])
		curvals.append(self)
		self.__class__._by_name[index_key] = curvals
	def __eq__(self, other):
		""" Return ``True`` if the current directive is the same as the other,
			else ``False``.

			.. note::
				* whitespaces are not tested (they can be different, this
				  is not a problem in the vas majority of cases), only names,
				  keywords, values and other sort of valuable things.
				* line-numbers are not tested, because same directives can
				  exist at different places of 2 configurations files without
				  any problem. If you want full equality, test self.lineno too.

		"""

		if self.name != other.name:
			assert ltrace(TRACE_CONFIG, ' %s directive name %s != %s' % (
								self.__class__.__name__, self.name,other.name))
			return False

		# Assuming same lenght of two directives coming from 2 different files
		# is possible because Comments have been stripped out at instanciation.
		if len(self.value) != len(other.value):
			assert ltrace(TRACE_CONFIG, ' %s lengths %s != %s' % (
				self.__class__.__name__, len(self.value), len(other.value)))
			return False

		for one, two in zip(self.value, other.value):

			if one.type != two.type:
				assert ltrace(TRACE_CONFIG, ' %s value type %s != %s' % (
								self.__class__.__name__, one.type, two.type))
				return False

			# we don't care about separators, they can be different in most
			# cases. don't assume the directives are unequal for that.
			if one.type == Whitespace:
				continue

			if one.value != two.value:
				assert ltrace(TRACE_CONFIG, ' %s value content %s != %s' % (
								self.__class__.__name__, one.value, two.value))
				return False

		return True
	def __ne__(self, other):
		""" Return ``True`` if the current directive is NOT the same as the
			other, else ``False``. See :meth:`__eq__` for notes. """

		if self.name != other.name:
			assert ltrace(TRACE_CONFIG, ' %s directive name %s != %s' % (
							self.__class__.__name__, self.name, other.name))
			return True

		# assuming same lenght is possible because comments have been
		# stripped out at ConfigurationDirective instanciation.
		if len(self.value) != len(other.value):
			assert ltrace(TRACE_CONFIG, ' %s lengths %s != %s' % (
				self.__class__.__name__, len(self.value), len(other.value)))
			return True

		for one, two in zip(self.value, other.value):

			if one.type != two.type:
				assert ltrace(TRACE_CONFIG, ' %s value type %s != %s' % (
								self.__class__.__name__, one.type, two.type))
				return True

			# we don't care about separators, they can be different in most
			# cases. don't assume the directives are unequal for that.
			if one.type == Whitespace:
				continue

			if one.value != two.value:
				assert ltrace(TRACE_CONFIG, ' %s value content %s != %s' % (
								self.__class__.__name__, one.value, two.value))
				return True

		return False
	def __str__(self):
		return '%s%s' % (self.name, ''.join(str(x) for x in self.value))
	def __repr__(self):
		return '%s(%s): %r' % (self.__class__.__name__, self.name, self.value)
	@property
	def flatenned(self):
		""" See the current directive as a sequence of simple tokens. """
		yield self.name_token

		for token in self.value:
			yield token

		for token in self.end_tokens:
			yield token
class ConfigurationFile(object):
	""" High level view of a configuration file, tokenized with the help of
		pygments. Pygments is totally used out of its original scope, because
		we don't use it for syntax highlightning at all, but for
		"better than bare-text" configuration-file manipulations.

		:param lexer: a pygments derivated lexer, used to tokenize our
			configuration file. The lexer can have 2 specials attributes (not
			known from pygments, specific to Licorn®):
			* ``directives_needing_order``: a list of unicode string
			  (directives names) for which value order matters. This means
			  that if we encounter these directives more than once, the order
			  of their values will be taken in account to determine if 2
			  directives are the same or not.
			  To illustrate: in :file:`squid.conf`, we've got multiple "acl"
			  lines, for which order doesn't matter (they are just definitions).
			  But for ``http_access`` directives, the order in which you write
			  them really matters (``deny all`` followed by ``allow localnet``
			  makes the proxy deny every connection, whereas ``allow localnet``
			  followed by ``deny all`` does what we want.
			  ``directives_needing_order`` will thus contain ``http_access``,
			  to be sure that the configuration file has the default values
			  in the good order, compared to our reference configuration data.
			* ``directives_dependancies``: a dictionary of unicode strings
			  (directives names) pointing to lists of unicode strings (other
			  directives names), to make them depend on each other. This will
			  help when parsing the configuration file, to check for directives
			  which are written in the wrong order.
			  To illustrate and follow our previous example, we will use
			  ``{ 'http_access': ('acl',), 'icp_access': ('acl',) }``, because
			  all ``acl`` directives must be written *before* any access
			  directives (which need them to be defined prior to using them).
			  This parameter is used only at loading time to detect configuration
			  errors. We do not dynamically reorder file contents yet (I know
			  this would be quite cool).
			* ``token_ignored_types``: an optional list of pygments token types,
			  which are considered useless if encountered in a configuration
			  directive. We use them to avoid considering end-of-line comments
			  as directive value. Default value if not set is
			  ``(Whitespace, Comment)``. Setting it to anything other depends
			  on your lexer contents and states (see the squid lexer for
			  an example).
			* ``new_directive_types``: an optional list of pygments token
			  types, implying that whenever one of them is found means that a
			  new directive must be created (this is the only way to
			  distinguish the previous directive from the next one. Default
			  value if not set is ``(Keyword, )``. Setting it to anything other
			  depends on your lexer contents and states (see the squid lexer
			  for an example).

		:param filename: a string (possibly ``None`` if you build a
			:class:`ConfigurationFile` from a string in memory) containing
			the full (absolute) path of the configuration file we are
			controlling/abstracting.

		:param text: a unicode string (possibly ``None``) holding the full
			contents of a configuration. This parameter is used when building
			:class:`ConfigurationFile` instances in memory.

		:param snipplet: a boolean telling if the ``filename`` or ``text`` is
			a snipplet or a “real” configuration file. If it's a snipplet, a
			number of checks will be relaxed because snipplets are incomplete
			by nature.

		.. note:: the :class:`ConfigurationFile` holds many “views” of its
			contents, to speed up manipulations and ease runtime modifications
			and tests:
			* an ordered list of all blocks, used to rewrite itself when needed.
			  With this view, the written file will be the exact replica of
			  the file on disk (with comments, etc).
			* an ordered list of all directives, to be able to manipulate them
			  quickly in a higher-level way. This avoids the comments and
			  blank-line pseudo-directives (from the `pygments` point of view).
			* a dictionnary of directives for which content order matters:
			  those whose name can be repeated with different values,
			  typically “acl” related directives, which all start with the same
			  keyword (just an example). This view is used in comparisons
			  methods, mainly.

		.. versionadded:: this class was created during the 1.3 development
			cycle but never found its way to the stable branch. It has been
			finished and integrated into the 1.6 instead.
	"""

	# These can be overridden in sub-classes, and it's encouraged.
	token_ignored_types         = (Whitespace, Comment, )
	new_directive_types         = (Keyword, )
	directives_needing_order    = []
	directives_dependancies     = {}

	def __init__(self, lexer, filename=None, text=None, snipplet=False, caller=None):
		self.blocks                   = []
		self.directives               = []
		self.ordered_directives       = {}
		self.filename                 = filename
		self.text                     = text
		self.lexer                    = lexer
		self.snipplet                 = snipplet
		self.__caller                 = caller

		# TODO: integrate the Inotifier's hint,
		# to avoid false-positive reload on write.

		self.__changed = False
		self.load()
	@property
	def changed(self):
		return self.__changed
	@changed.setter
	def changed(self, changed):

		if changed is True:
			self.__changed = True
			return

		raise RuntimeError(u'Cannot set `changed` to `False` manually, '
					u'this must be done from the `save()` method only!')

	@property
	def _caller(self):
		""" read-only property, returning the name of the caller (as a string).
			The caller can be a thread, a module, another Licorn® object
			instance, whatever.

			If it is None (not set at creation of the current :class:`ConfigFile`)
			instance, the name of the current thread will be returned.
		"""
		return self.__caller or current_thread().name
	def __str__(self):
		return u'%s @0x%x for %s via %s' % (self.__class__.__name__, id(self),
								self.filename or 'in_memory', self.lexer)
	def __eq__(self, other):
		""" Return ``True`` if 2 configuration files are equals, which means:
			* they have the same number of configuration directives, and each
			  of them have the same value.
			* all ordered directives are the same, compared ordered.
			* all other directives are the same.

			.. note:: the names of the compared configuration files can be
				  different, this doesn't affect the equality. You can compare
				  a file on disk with an in-memory instance, too.
		"""

		if len(self.directives) != len(other.directives):
			assert ltrace(TRACE_CONFIG, 'different by number of directives {0} '
				'!= {1}.'.format(len(self.directives), len(other.directives)))
			return False

		if self.directives_needing_order:
			if self.directives_needing_order is True:

				compare_sorted  = False
				compare_ordered = False

				# the only comparison needed is done here.
				for one, two in zip(self.directives, other.directives):
					if one != two:
						assert ltrace(TRACE_CONFIG, 'different [unsorted,'
							'unordered] because {0} != {1}.'.format(one, two))
						return False

			else:
				compare_sorted  = True
				compare_ordered = True
		else:
			compare_sorted  = True
			compare_ordered = False

		if compare_sorted:
			for one, two in zip(sorted(self.directives, key=str),
								sorted(other.directives, key=str)):
				if one != two:
					assert ltrace(TRACE_CONFIG, 'different [sorted] because '
												'{0} != {1}.'.format(one, two))
					return False

		if compare_ordered:
			if len(self.ordered_directives) != len(other.ordered_directives):
				assert ltrace(TRACE_CONFIG, 'different [ordered] because not '
										'same number of ordered directives.')
				return False

			for dirname in self.directives_needing_order:
				if dirname in self.ordered_directives:
					if dirname in other.ordered_directives:
						for dir1, dir2 in zip(self.ordered_directives[dirname],
												other.ordered_directives[dirname]):
							if dir1 != dir2:
								assert ltrace(TRACE_CONFIG, 'different [ordered] '
									'because {0} != {1}.'.format(dir1, dir2))
								return False
					else:
						return False
				else:
					if dirname in other.ordered_directives:
						assert ltrace(TRACE_CONFIG, 'different [ordered] because '
								'{0} not in {2}.'.format(dirname, other))
						return False

					else:
						continue

		# If we reach here, nothing has been found different.
		return True
	def __ne__(self, other):
		""" Return ``True`` if 2 configuration files are the same which means:
			* they have the same number of configuration directives, and each
			  of them have the same value.

			.. note:: the names of the compared configuration files can be
				  different, this doesn't affect the equality.
			* """

		if len(self.directives) != len(other.directives):
			return True

		if self.directives_needing_order:
			if self.directives_needing_order is True:

				compare_sorted  = False
				compare_ordered = False

				# the only comparison needed is done here.
				for one, two in zip(self.directives, other.directives):
					if one != two:
						return True

			else:
				compare_sorted  = True
				compare_ordered = True
		else:
			compare_sorted  = True
			compare_ordered = False

		if compare_sorted:
			for one, two in zip(sorted(self.directives, key=str),
								sorted(other.directives, key=str)):
				if one != two:
					return True

		if compare_ordered:
			if len(self.ordered_directives) != len(other.ordered_directives):
				return True

			for dirname in self.directives_needing_order:
				if dirname in self.ordered_directives:
					if dirname in other.ordered_directives:
						for dir1, dir2 in zip(self.ordered_directives[dirname],
												other.ordered_directives[dirname]):
							if dir1 != dir2:
								return True
					else:
						return True
				else:
					if dirname in other.ordered_directives:
						return True
					else:
						continue

		# if we reach here, nothing has been found different.
		return False
	def load(self):
		""" Open the configuration file and "lex it", then store the tokens
			inside us.

			After that, chech directive order and dependancies. Any error or
			exception will be raised barely: the file must be correct before
			beiing used. We have currently no way to automatically check a
			broken configuration file, this is the human's work, be he
			system administrator or package maintainer.
		"""

		# Always raise an exception when a syntax error is encountered.
		# NOTE: not a good idea for now, we will crash!
		#self.lexer.add_filter(RaiseOnErrorTokenFilter())

		self.__load_from_tokens(self.lexer.get_tokens(self.text or
								open(self.filename,'rb').read()))

		self.__check_duplicates()
		self.__check_ordering()
		self.__check_dependancies()
	def __default_append_func(self, directive):
		self.directives.append(directive)

		if directive.name in self.directives_needing_order:
			ordered = self.ordered_directives.get(directive.name, [])
			ordered.append(directive)
			self.ordered_directives[directive.name] = ordered
	def __find_append_func(self):

		if self.directives_needing_order:
			# If directives_needing_order is True, every single line must be
			# in the same order; `__eq__()` will simply use self.directives
			# without reordering it to compare 2 configuration files.
			if self.directives_needing_order is True:
				return self.directives.append

			# If only a subset of directives have their order which matter,
			# we store every directive as usual (contents will be compared
			# the same way), and keep a reference in a dictionnary from
			# which only the order of these directives will be compared.
			# This hoppefully speeds up the comparisons in this kind of
			# "semi-ordered-directives" mode.
			else:
				return self.__default_append_func

		else:
			return self.directives.append
	def __check_duplicates(self):
		# Check duplicate lines, else we could end with some, coming
		# from manual errors and `index*()` methods will only return
		# the first match of them.

		logging.warning2('Please implement foundations.config.ConfigurationFile.__check_duplicates()!')
	def __check_ordering(self):

		for directive_name in self.directives_needing_order:

			if not directive_name in self.ordered_directives:
				# No need to check order for this kind of directive, we
				# have none of them in the current configuration snipplet.
				continue

			try:
				getattr(self, '_order_check_' + directive_name)(
										self.ordered_directives[directive_name])

			except AttributeError:
				# We don't try/except this one: either the current class has a
				# dedicated checker method, either it has a generic checker one.
				# But it should have at least one of them.
				getattr(self, '_order_check_generic')(directive_name,
									self.ordered_directives[directive_name])
	def __check_dependancies(self):
		#resolved = pyutils.resolve_dependancies_from_dict_strings(self.directives_dependancies)

		for directive_name, depended_on_directives \
								in self.directives_dependancies.iteritems():

			for directive in self.directives:
				if directive_name == directive.name:
					# we've got the first occurrence of our dependant directive.

					for other_directive_name in depended_on_directives:

						for other_directive in reversed(self.directives):
							if other_directive_name == other_directive.name:
								# we've got the last of depended-upon directive.

								if directive.lineno < other_directive.lineno:

									# TODO: try to correct the problem ? By
									# moving the culprit(s) just before the
									# dependancy, in the same order if there
									# are many ?
									# This is not the same job, I think. It
									# would complexify a lot this class. Later.

									raise exceptions.BadConfigurationError(
										_(u'{0}: all {1} directives (last '
											'encountered: {2}, line {3}) should be '
											'located before all {4} directives '
											'(first encoutered: {5}, line {6}), '
											'in {7}.').format(
											stylize(ST_NAME, self._caller),
											stylize(ST_ATTR, other_directive_name),
											stylize(ST_COMMENT, str(other_directive)),
											stylize(ST_UGID, other_directive.lineno),
											stylize(ST_ATTR, directive_name),
											stylize(ST_COMMENT, str(directive)),
											stylize(ST_UGID, directive.lineno),
											stylize(ST_PATH, self.filename)))

								# the directives come ordered. If the last
								# "other" comes after the "first" dependant,
								# everything is OK. Avoid useless-costly testing.
								break
					# idem
					break
	def __load_from_tokens(self, tokensource):
		""" Read tokens one by one and try to group them into higher-level
			groups (directives, comments, etc). This method is basically the
			same as the ``format()`` method of a `Pygments` ``Formatter``.

			:param tokensource: an iterable of tuples (token_type, value), where
				token_type is a pygments token class. See
				http://pygments.org/docs/tokens/ for details.
		"""

		assert ltrace_func(TRACE_CONFIG)

		append_func = self.__find_append_func()

		# store the line count (guessed from the tokens contents). This will
		# allow better display of parse errors, and knowing the order of
		# configuration directives (higher-level than just tokens).
		linecount = 1

		stack = []

		def append_block_or_directive(last=False):
			""" create a directive if current stack contents imply that one
				should be created, else create a standard configuration block.
			"""
			if stack[0].type in self.new_directive_types:
				append_func(ConfigurationDirective(linecount,
										name=stack[0],
										value=(stack[1:] if last else stack[1:-1])
											if len(stack) > 1 else (),
										parent=self))

				self.blocks.append(self.directives[-1])

			else:
				self.blocks.append(ConfigurationBlock(stack[:-1],
									parent=self))

		for ttype, value in tokensource:
			stack.append(ConfigurationToken(ttype, value))

			# if current token type implies creating a new directive, try to.
			if ttype in self.new_directive_types and linecount > 1:

				# reset for next line.
				append_block_or_directive()

				# keep the very last token on the stack, it's the current one.
				# It has been stacked at the very beginning of the loop (a
				# little too early ;-) ), and hasn't been picked by
				# append_block_or_directive(); so don't loose it on the way.
				stack = [ stack[-1] ]

			# count lines passing by, independantly of directives and other
			# blocks beeing tracked. This one is tricky, because newlines can
			# be part of comments values (or anything other), depending on the
			# lexer used to parse.
			linecount += (len(value.split('\n')) - 1)

		# don't forget the last line!
		if stack != []:
			append_block_or_directive(last=True)
	def has(self, directive=None, match_value=True, directive_name=None):
		""" Return ``True`` if a directive is already held in the current
			instance.

			:param directive: a :class:`ConfigurationDirective` instance. The
				return value is highly dependant of the following parameter.
				See below for details.

			:param match_value: if ``True`` (which the default), a
				full search against the specified directive will be performed;
				if the method returns ``True``, you can assume *exact* match.
				If ``False``, you cannot assume that the directive isn't
				present: it could be, with a different value.
				If ``False``, the search is roughly equivalent to a directive
				name match only (see below). This is just another way of doing
				the same thing.

			:param directive_name: a unicode string instance, containing a
				directive name. The first encountered directive returns
				``True``, whatever the value is. If the method returns
				``False``, you can assume there is *no* directive at all
				by that name.

		"""

		if directive:
			for d in self.directives:
				if match_value:
					if d == directive:
						return True
				else:
					if d.name == directive.name:
						return True
			return False

		if directive_name:
			for d in self.directives:
				if d.name == directive_name:
					return True
			return False

		raise ValueError('no directive nor directive_name was specified.')
	def find(self, directive=None, match_value=True, raise_partial=False, directive_name=None):
		""" This method does roughly (but not exactly) the same thing as the
			:meth:`has` one, but it returns the matched directive when found.

			If :param:`raise_partial` is ``True`` and a partial match (only the
			name is found), the method raises the directive found, instead
			of returning it. This can be felt quite strange but it's an easy
			way to indicate the match is not the exact one. Exact matches take
			precedence on partial ones; thus if a partial match is raised, you
			can assume that the configuration file doesn't include the exact
			match anywhere. Use the method like this::

			try:
				result = conf_file.find(Directive(...), raise_partial=True)

			except ConfigurationDirective, partial_match:
				# do something with the partial match if you want.

			except ValueError:
				# no directive by that name either.

			else:
				# do something when exact match is found.
			"""
		if directive:
			partial = None

			for d in self.directives:

				if match_value:
					if d == directive:
						return d

					elif d.name == directive.name and partial is None:
						partial = d

				else:
					if d.name == directive.name:
						return d

			if raise_partial and partial:
				raise PartialMatch(partial)

			raise ValueError(_(u'Directive {0} not found in {1}.').format(directive, repr(self)))

		if directive_name:
			for d in self.directives:
				if d.name == directive_name:
					return d

			raise ValueError('%s not found in %r.' % (directive_name, self))

		raise ValueError('no directive nor directive_name was specified.')
	def index(self, directive):
		""" Given a :param:`ConfigurationDirective` (already parsed, coming
			from another :class:`ConfigurationFile` for example), return the
			index of the first occurence of the same directive in the
			current :class:`ConfigurationFile` instance.

			Raises :class:`ValueError` if not found.

			.. note:: this method doesn't work on comments. It won't find them,
				even if they are present, because it search only **directives**.
		"""
		for d in self.directives:
			if d == directive:
				return self.blocks.index(d)

		raise ValueError('%s not found in %r.' % (directive, self))
	def index_first(self, directive_name):
		""" Given a directive name (as a string), return the
			index of the first occurence of the directive with the same name
			(whatever the value) in the current :class:`ConfigurationFile`
			instance.

			Raises :class:`ValueError` if not found.

			.. note:: this method doesn't work on comments. It won't find them,
				even if they are present, because it search only **directives**.

		"""
		for d in self.directives:
			if d.name == directive_name:
				return self.blocks.index(d)

		raise ValueError('%s not found in %r.' % (directive_name, self))
	def index_last(self, directive_name):
		""" See the :meth:`index_first` method. This one do the same, starting
			from the end of :class:`ConfigurationFile`. """

		for d in reversed(self.directives):
			if d.name == directive_name:
				return self.blocks.index(d)

		raise ValueError('%s not found in %r.' % (directive_name, self))
	def add(self, directive):
		pass
	def remove(self, directive):
		pass
	def remove_at(self, position):
		""" Remove the directive at :param:`position`. No check at all is done.

			This method is used by :meth:`wipe` a lot. See there for more
			explanations.
		"""
		assert ltrace_func(TRACE_CONFIG)

		directive = self.blocks[position]

		# Update ordered directives if this one belongs to them.
		if directive.name in self.ordered_directives:
			self.ordered_directives[directive.name].remove(directive)

		# Remove from the directives.
		self.directives.remove(directive)

		# Then remove from the "all" blocks.
		del self.blocks[position]

		# Note that we changed.
		self.changed = True
	def insert_at(self, position, directive, sub_pos=None):
		""" Insert in the current configuration, at a given position.

			:param position: an integer, passed verbatim to the :meth:`~list.insert`
				method of our internal list.

			:param directive: a :class:`ConfigurationDirective` instance.

			:param sub_pos: an integer index in the ``ordered_directives``
				sub-list. It must be set to something valid when inserting a
				directive which belongs to an ordered kind, else this method
				will not insert it, and will raise
				a :class:`~foundations.exceptions.LicornRuntimeError`
				exception instead.

			.. versionchanged:: this method was implemented for 1.6.
		"""

		assert ltrace_func(TRACE_CONFIG)

		# Update ordered directives if this one belongs to them.
		if directive.name in self.ordered_directives:
			if sub_pos is None:
				raise exceptions.LicornRuntimeError('sub_pos should be filled '
										'when inserting an ordered directive.')

			self.ordered_directives[directive.name].insert(sub_pos, directive)

		# Insert in the directives. Costly, but quick-search is at this price.
		self.directives.insert(self.directives.index(self.blocks[position]),
								directive)

		# Then insert in the "all" blocks.
		self.blocks.insert(position, directive)

		# Note that we changed.
		self.changed = True
	def insert_before(self, directive):
		pass
	def insert_after(self, directive):
		pass
	def insert_before_first(self, directive_name, directive):
		pass
	def insert_before_last(self, directive_name, directive):
		pass
	def insert_after_first(self, directive_name, directive):
		pass
	def insert_after_last(self, directive_name, directive):
		pass
	def merge(self, other, on_conflicts=None, batch=False, auto_answer=None):
		""" Try to merge another instance of :class:`ConfigurationFile` into
			the current instance, beiing smart in the process. When 2 directives
			conflict, do whatever is specified by the :param:`on_conflicts`
			parameter.

			:param other: the other :class:`ConfigurationFile` instance from
				which we want to merge.

			:param on_conflicts: a string describing what to do when a conflict
				is encountered during the merge operation. Default value is
				``raise``. Accepted values are:
				* ``raise``: raise a MergeConflictException.
				* ``overwrite`` or ``replace``: overwrite the current value
				  inside us, with the value from ``other`` configuration file.
				* ``ignore``, ``keep`` or ``pass``: ignore the value from
				  ``other`` and keep ours.

			:param batch: the Licorn® standard ``batch`` parameter. Helps
				automatically applying the decision of ``on_conflicts``, else
				the question (if any) is raised interactively, which is not
				everytime what you need. Can be ``True`` or ``False`` (default).

			:param auto_answer: the Licorn® standard parameter. Contains an
				optional and eventual previous answer that the user entered. Can
				be ``None`` (ask the the question; default value), ``True`` or
				``False``.

			.. todo:: merge comment blocks. As of current version, we only
				merge directives, keep our own comments and forget "other's"
				stand-alone comments (comments included in merged directives
				gets merged, as part of the directive).

			..versionadded:: 1.6
		"""

		for directive_to_merge in other.directives:
			try:
				self.index(directive_to_merge)

			except ValueError:
				# We don't have it, go merging.
				self.__merge_one_directive(directive_to_merge)

		return self.changed
	def __merge_one_directive(self, directive):

		assert ltrace_func(TRACE_CONFIG)

		# By default, we insert new directives at the end of file.
		best_insert_index = len(self.blocks)
		best_sub_position = None

		# Then we try to find a better position, earlier in the file.
		if directive.name in self.ordered_directives:
			try:
				best_insert_index, \
					best_sub_position = getattr(self, '_insert_index_for_'
														+ directive.name)(
															directive,
															self.ordered_directives[
																directive.name])

			except AttributeError:
				try:
					best_insert_index, \
						best_sub_position = getattr(self, '_insert_index_generic')(
													directive.name,
													directive,
													self.ordered_directives[
														directive.name])

				except AttributeError:
					try:
						# When no better match can be determined via dedicated
						# methods, insert at the end of the ordered block
						# (= after the last ordered directive). This could
						# eventually lead to errors in the configuration file,
						# but this problem should be known by the developer
						# of the sub-class.
						best_insert_index = self.index_last(directive.name)
						best_sub_position = len(self.ordered_directives[
														directive.name])

					except ValueError:
						# The current configuration does not include any
						# directive of that kind. The one we insert is the
						# first. Just continue, the dependancy search will
						# insert it before all dependants directives.
						#
						# If this kind of directive has no dependants, it
						# will be inserted at the end like any other kind.
						pass

		# No need to test dependancies if the directive was ordered, the
		# insert postition is already the best we can find: it's in the
		# block of ordered directives, which has already been checked at
		# file load to be in good order. Thus the 'else'.
		else:
			for dependant_name, dependancies in self.directives_dependancies.iteritems():

				if directive.name == dependant_name:
					for dep_name in dependancies:
						try:
							# Try to insert the new directive after the last
							# of this dependants block. If there are many
							# dependants block, we will try each, to be sure
							# the new is inserted after all of them.
							better_attempt = self.index_last(dep_name) + 1

						except ValueError:
							continue

						# The new directive must be inserted *after* all of
						# its dependants, thus '>' instead of '<'.
						if better_attempt > best_insert_index:
							best_insert_index = better_attempt

				# If directive is a "dependant" one, no need to test against
				# dependancies of the current rule: the directive won't depend
				# on itself. Thus the 'elif'.
				elif directive.name in dependancies:

					# Find the first dependant occurence, and insert just before.
					try:
						better_attempt = self.index_first(dependant_name) - 1

					except ValueError:
						continue

					# Testing dependants, we must insert *before* all of them.
					if better_attempt < best_insert_index:
						best_insert_index = better_attempt

					# Don't break the loop: in case the directive we're merging
					# is a dependancy of more than one others, all of them must be
					# tested to be sure we insert in the file before the first of
					# the earliest of them all.
					# As dependancies are not ordered in any way between each
					# other in the file and in the current instance internal data
					# structures, we have no mean to do this faster.
					#break

		self.insert_at(best_insert_index, directive, best_sub_position)
	def wipe(self, other, on_conflicts=None, batch=False, auto_answer=None):
		""" Remove other's directives from us. Parameters are the same as in
			the :meth:`merge` method: :meth:`wipe` is its pure opposite.

			.. warning:: This method doesn't check that the file is in a good
				shape, functionnaly speaking, after directives have been wiped.
				Eg. you can easily remove an essential part of the configuration
				and make the underlying service unusable. It's up to the caller
				to be sure nothing critical is removed, or something to replace
				it is resinserted after the wipe.

			.. note:: This method won't alter comments in the current instance.

				This means that even after some directives have been wiped from
				self, we could still hold the related comments, which will be
				useless and potentially non-sense or counter-sense in the file
				written on disk.

				Comments are put in place by humans, Licorn®
				doesn't use them at all. I think the solution lies on the human
				side. As comments are not linked to directives in any fashion,
				I couldn't figure any reliable way to remove them.
		"""

		for directive_to_wipe in other.directives:
			try:
				position = self.index(directive_to_wipe)

			except ValueError:
				# We already don't have it, continue.
				continue

			else:
				self.__wipe_one_directive(position)
	def __wipe_one_directive(self, position):
		""" This method exists just because it has a merge() counterpart.
			Internally it does nothing more than :meth:`remove_at` for the
			moment, because we don't check dependancies and such at wipe time.
		"""

		self.remove_at(position)
	def output(self):
		Terminal256Formatter(encoding='utf-8').format(
											(token.to_pygments() for token in
												itertools.chain.from_iterable(
													b.flatenned
													for b in self.blocks)),
											sys.stderr)
	def to_string(self):
		return u''.join(unicode(token) for token in
										itertools.chain.from_iterable(
											b.flatenned for b in self.blocks))
	def __save(self, filename=None):
		""" Write the configuration file contents back to the disk,
			encapsulated with a Filelock.
		"""

		if filename is None:
			filename = self._filename

		assert ltrace_func(TRACE_CONFIG)

		data = self.to_string()

		with FileLock(self, filename):
			open(filename, 'w').write(data)

			ftempp, fpathp = tempfile.mkstemp(dir=os.path.dirname(filename))

			os.write(ftempp, data)

			# FIXME: implement these ch* calls properly, with dynamic
			# values taken from the original file we are replacing.
			os.fchmod(ftempp, 0644)
			#os.fchown(ftempp, 0, 0)

			os.close(ftempp)

			# TODO: implement the INotifier Hint…
			#self.__hint_pwd += 1

			os.rename(fpathp, filename)
	def save(self, filename=None, batch=False, auto_answer=None):
		""" If the configuration file changed, backup the current file on disk,
			and save the current data into a new version (same name).

			If the current instance is a "memory-only" one, and no filename
			is given, raise an exception.
		"""

		if filename is None:
			filename = self.filename

		if self.changed:
			if filename:
				if batch or logging.ask_for_repair(_(u'{0}: system file {1} '
							u'must be modified for the configuration to be '
							u'complete. Do it?').format(
								stylize(ST_NAME, self._caller),
								stylize(ST_PATH, self._filename)),
							auto_answer=auto_answer):

					fsapi.backup_file(filename)
					self.__save(filename)

					# Alter the property via the underlying private attribute,
					# else modifications are not allowed.
					self.__changed = False

					logging.notice(_(u'{0}: altered configuration file {1}.').format(
											stylize(ST_NAME, self._caller),
											stylize(ST_PATH, self._filename)))

				else:
					raise exceptions.LicornModuleError(_(u'{0}: configuration '
							u'file {1} must be altered to continue.').format(
								self._caller, self._filename))

			else:
				raise exceptions.LicornRuntimeError(_(u'%s: cannot save a '
								u'file without any filename!') % self.name)

__all__ = ('ConfigurationFile', 'ConfigurationDirective',
			'ConfigurationBlock', 'ConfigurationToken',
			'PartialMatch',)
