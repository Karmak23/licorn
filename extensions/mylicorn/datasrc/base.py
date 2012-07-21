# -*- coding: utf-8 -*-
"""
Licorn® MyLicorn data sources

:copyright: (C) 2012 Olivier Cortès <olive@licorn.org>
:license: GNU GPL version 2

"""
import os, uuid, hashlib, random, errno, json

from licorn.foundations        import settings, exceptions, logging, styles
from licorn.foundations.styles import *

stylize = styles.stylize

def randint(arg=None, min=65535, max=131070):
	return random.randint(min, max)
def sha1(arg=None):
	return hashlib.sha1(arg).hexdigest()
def uuid4(arg=None):
	return uuid.uuid4().hex

class IdentityDict(object):
	def __getitem__(self, key):
		return key
class AnonymDataMapping(object):
	""" Acts like a dict, but generates new random value for non-existing keys.
		Allows to keep the anonymisation IDs across runs, thus data is considered
		half-anonymised: no real IDs/names/login are transmitted, but habbits
		and behavior of a single object can still be observed, because the object
		always gets the same anonymised ID.

		:param klass: the Python object class for which we will anonymise data.
			Used to determine the filename where the mappings are saved.

		:param genfunc: a callable used to generate a new anonym key. defaults to
			:func:`simple` which generate random Integers between 65535 and 131070
			(ideal for UIDs/GIDs). Other callables offered are :func:`sha1` which
			returns a SHA1 hexadecimal digest, and :func:`uuid4` which returns
			an UUID4 hexadecimal digest. Any callable which accepts an argument
			named ``arg`` and returns and Integer or a string will do the job.

		.. versionadded:: 1.5
	"""
	base_path = os.path.join(settings.data_dir, 'anon')

	def __init__(self, klass, full=False, genfunc=None):

		self.__path = os.path.join(AnonymDataMapping.base_path, klass.__name__ + '.map')

		self.full    = full
		self.genfunc = genfunc or randint

		if full:
			self.save = self.__no_save

		else:
			self.save = self.__real_save

		if not os.path.exists(self.__path):
			# We don't save the file until we've
			# got some real data to put in it.
			self.map = {}

		else:
			with open(self.__path) as f:
				self.map = json.load(f)

			if self.genfunc.__name__ != self.map['__genfunc__']:
				raise exceptions.LicornRuntimeError(_(u'Another genfunc is '
					u'already registered for this anonymous data mapping: '
					u'old="{0}", new="{1}". This will certainly produce '
					u'errors on the remote data collector side.').format(
						self.map['__genfunc__'],
						self.genfunc.__name__))
	def __no_save(self):
		# don't save anything for fully anonymized data.
		pass
	def __real_save(self):
		# be sure the genfunc is saved
		self.map['__genfunc__'] =self.genfunc.__name__

		with open(self.__path, 'w') as f:
			json.dump(self.map, f)
	def __getitem__(self, key):
		try:
			return self.map[key]

		except KeyError:
			# the non-anonym data has no mapping yet for this key.
			# Create one and save it immediately to disk.
			value = self.genfunc(key)

			# Be sure anonymized values don't collide. With the
			# randint() generator, this could be more times than
			# we think. Others will simply not enter the `while`.
			while value in self.map.itervalues():
				value = self.genfunc(key)

			self.map[key] = value
			self.save()

			return value

	@property
	def path(self):
		return self.__path
	def clear(self):
		self.map.clear()
		try:
			os.unlink(self.__path)

		except (IOError, OSError), e:
			if e.errno != errno.ENOENT:
				raise
class DataSource(object):
	def __init__(self, *args, **kwargs):

		self.pretty_name    = stylize(ST_NAME, self.__class__.__name__)
		self.anonymise      = kwargs.pop('anonymize', False)
		self.anonymise_full = kwargs.pop('anonymize_full', False)
		self.anon_genfunc   = kwargs.pop('anon_genfunc', None)

		if self.anonymise:
			self.anonmap = AnonymDataMapping(self.__class__,
												full=self.anonymise_full,
												genfunc=self.anon_genfunc)
		else:
			self.anonmap = IdentityDict()

if not os.path.exists(AnonymDataMapping.base_path):
	os.makedirs(AnonymDataMapping.base_path)
	logging.info(_(u'{0}: created directory {1}.').format(
								stylize(ST_NAME, __name__),
								stylize(ST_PATH, AnonymDataMapping.base_path)))

__all__ = ('AnonymDataMapping', 'DataSource', 'randint', 'sha1', 'uuid4')
