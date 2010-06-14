# -*- coding: utf-8 -*-
"""
Licorn Daemon Cache.
The cache centralize data coming from and going to other threads (ACLChecker, Inotifier, Searcher).
It is built on top of a SQLite database.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, xattr, stat, re

# try python2.5 else python2.4
try:  import sqlite3 as sqlite
except ImportError: from pysqlite2 import dbapi2 as sqlite

from Queue              import Queue
from threading          import Thread, Event

from licorn.foundations         import logging, exceptions, styles, fsapi
from licorn.foundations.objects import Singleton
from licorn.daemon.core         import dname, cache_path

# FIXME: convert this to LicornThread.
class Cache(Thread, Singleton):
	""" Thread cache object to help files and keywords caching through an SQLite database. """
	allkeywords   = None
	localKeywords = {}
	_stop_event   = Event()
	_dbfname      = ''
	_db           = None
	_cursor       = None
	_queue        = Queue()

	def __init__(self, allkeywords = None, pname = dname, dbfname = cache_path):

		self.name = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		if Cache.allkeywords is None:
			if allkeywords is None:
				raise exceptions.BadArgumentError('You must create at least one instance of the cache WITH "allkeywords" parameter set.')
			else:
				Cache.allkeywords = allkeywords

		Cache._dbfname = dbfname
	def stop(self):
		"""Stop this thread."""
		if not Cache._stop_event.isSet():
			logging.progress("%s: stopping thread." % (self.getName()))
			Cache._stop_event.set()
			Cache._queue.put((None, None, None))
	def status(self):
		""" Return statistics as a sequence. """

		knb = self.select('SELECT COUNT(*) FROM keywords;')
		fnb = self.select('SELECT COUNT(*) FROM files;')

		return (knb, fnb)
	def setupAndConnectDB(self):
		""" Create database if needed, or update keywords table if needed, and vacuum some obsolete records if needed. """

		d = os.path.dirname(Cache._dbfname)
		if not os.path.exists(d):
			os.makedirs(d)
		del d

		Cache._db     = sqlite.connect(Cache._dbfname)
		# prevent string conversion errors from database when filenames are not UTF-8 encoded.
		Cache._db.text_factory = str

		Cache._cursor = Cache._db.cursor()
		c             = Cache._cursor

		syskw = Cache.allkeywords.keywords.keys() # just a speedup

		try:
			c.execute('SELECT kid, kname FROM keywords;')

		except sqlite.OperationalError:
			# create DB and insert current system keywords inside
			# then select them immediately to make things appear
			# like there has been no Exception.
			c.executescript('''
	CREATE TABLE files (
	fid	INTEGER PRIMARY KEY,
	fname TEXT,
	fsize integer,
	fmtime integer
	);

	CREATE TABLE groups (
	gid INTEGER PRIMARY KEY,
	gname TEXT
	);

	CREATE TABLE g_on_f (
	fid INTEGER,
	gid INTEGER,
	PRIMARY KEY(fid, gid)
	);

	CREATE TABLE keywords (
	kid INTEGER PRIMARY KEY,
	kname TEXT
	);

	CREATE TABLE k_on_f (
	fid INTEGER,
	kid INTEGER,
	PRIMARY KEY(fid, kid)
	);''')
			c.executemany('''INSERT OR REPLACE INTO keywords(kname) VALUES(?);''', [ (k,) for k in syskw ])
			c.execute('SELECT kid, kname FROM keywords;')

			logging.progress('%s: initialized.' % self.getName())

		cache_kw = c.fetchall()
		for (kid, kname) in cache_kw:
			if kname in syskw:
				Cache.localKeywords[kname] = kid
			else:
				# delete keywords which are in cache and have been deleted from system
				# since last DB use.
				c.execute('DELETE FROM keywords WHERE kid=?;', (kid,))
				c.execute('DELETE FROM k_on_f   WHERE kid=?;', (kid,))
				logging.progress("%s: deleted obsolete keyword %s from cache database." % (self.getName(), kname))

		for kname in syskw:
			if kname not in Cache.localKeywords.keys():
				c.execute('INSERT OR REPLACE INTO keywords(kname) VALUES(?);', (kname,))
				logging.progress("%s: inserted missing keyword %s into cache database." % (self.getName(), kname))

		# this is done once again in self.vacuumDatabase()
		c.execute('DELETE FROM k_on_f WHERE kid NOT IN ( SELECT kid FROM keywords );')
		logging.progress("%s: Removed %d obsolete rows from cache database." % (self.getName(), c.rowcount))

		try: c.execute('COMMIT;')
		except: pass

		logging.progress('%s: keywords loaded.' % self.getName())
	def run(self):
		""" Set up database if needed and wait for any request in the queue."""

		self.setupAndConnectDB()

		c = Cache._cursor
		q = Cache._queue
		s = Cache._stop_event

		logging.progress('%s: thread running.' % self.getName())

		while not s.isSet():

			# then process every action
			request, arguments, result = q.get()

			logging.debug2('%s: executing %s %s.' % (self.getName(), request, arguments))

			if request != None:
				c.execute(request, arguments)
				if result:
					for record in c:
						result.put(record)
					logging.debug('%s: terminating request result.' % self.getName())
					result.put(False)

		Cache._db.close()
		logging.progress("%s: thread ended." % (self.getName()))
	def select(self, request, arguments = None):
		""" Execute a SELECT statement.
			Put a standard SQL request in the queue.
			Wait for the result and yield it, line by line.
		"""
		result = Queue()
		Cache._queue.put((request, arguments or tuple(), result))
		record = result.get()
		while record:
			yield record
			record = result.get()
	def vacuumDatabase(self):
		"""Try to clean the cache as much as possible, remove unused or obsolete rows and so on."""

		# FIXME don't use the cursor directly, use the select() function to use the Queue power !
		return

		db = sqlite.connect(Cache._dbfname)
		# prevent string conversion errors from database when filenames are not UTF-8 encoded.
		db.text_factory = str
		c  = db.cursor()

		# this is done once again in self.InitializeDatabase()
		c.execute('DELETE FROM k_on_f WHERE kid NOT IN ( SELECT kid FROM keywords );')
		logging.progress("%s: Removed %d obsolete rows from cache database." % (self.getName(), c.rowcount))

		c.execute('SELECT fid, fname FROM files;')

		files = c.fetchall()
		for (fid, fname) in files:
			if not os.path.exists(fname):
				c.execute('DELETE FROM k_on_f WHERE fid=?;', (fid,))
				c.execute('DELETE FROM files  WHERE fid=?;', (fid,))
				logging.progress("%s: Removed non existing file %s from cache database." % (self.getName(), fname))

		try: c.execute('COMMIT;')
		except: pass
	def __cache_one_file(self, filename, batch = False, force = False):
		""" Add a file to the cache. """

		if self._stop_event.isSet():
			raise exceptions.LicornStopException("%s: stopped, can't cache." % self.getName())

		fstat = os.lstat(filename)

		q = Cache._queue

		try:
			fid, fname, fmtime = self.select('SELECT fid, fname, fmtime FROM files WHERE fid=?;', (fstat.st_ino,))
		except ValueError:
			fid = None

		if force or fid is None or fmtime != fstat.st_mtime:

			logging.progress("%s: updating cache record for %s." % (self.getName(), styles.stylize(styles.ST_PATH, filename)))

			q.put(('''INSERT OR REPLACE INTO files(fid, fname, fsize, fmtime) VALUES(?,?,?,?);''',
				(fstat.st_ino, filename, fstat.st_size, fstat.st_mtime), None))

			try:
				attrs = xattr.getxattr(filename, Cache.allkeywords.licorn_xattr).split(',')
				good  = filter(lambda x: x in Cache.allkeywords.keywords.keys(), attrs)
				bad   = filter(lambda x: x not in Cache.allkeywords.keywords.keys(), attrs)

				if bad != []:
					logging.warning("%s: file %s holds inexistant keyword(s) %s." % (self.getName(), styles.stylize(styles.ST_PATH, filename), bad))

				if good != []:
					logging.progress("%s: Inserting inode->kw %d->%s." % (self.getName(), fstat.st_ino, good))

					for k in good:
						q.put(('''INSERT OR REPLACE INTO k_on_f(fid, kid) VALUES(?,?);''', (fstat.st_ino, Cache.localKeywords[k]), None))

			except (OSError, IOError), e:
				if e.errno not in (2, 61, 95):
					raise e
				else:
					# FIXME: why delete the entry on err95 ? why not just let the cache as it is ?
					q.put(('''DELETE FROM k_on_f WHERE fid=?;''', (fstat.st_ino,), None))

			try:
				# TODO: get facl / perms and cache them, to answer user requests according to file perms.
				#
				# TODO: why not just return the queries and let the gui verify the user has rights on the file ?
				# if it hasn't, he won't be able to open it any way. but this could be a
				# security risk, knowing the exact name of the file. SO: the daemon should return only
				# allowed files.
				pass

			except (OSError, IOError), e:
				if e.errno not in (2, 61, 95):
					raise e
		else:
			logging.progress("%s: not caching %s, up-to-date." % (self.getName(), styles.stylize(styles.ST_PATH, filename)))
	def cache(self, path, force = False):
		""" Recursively fsapi.minifind() a dir and its subdirs for files and update the cache with data found. """

		logging.progress('%s: Starting to Cache(%s, force=%d).' % (self.getName(), styles.stylize(styles.ST_PATH, path), force))

		try:
			map(lambda x: self.__cache_one_file(x, batch = True, force = force), fsapi.minifind(path, type = stat.S_IFREG))
		except exceptions.LicornStopException:
			logging.info("%s: stop request received, cleaning up." % self.getName())
	def removeEntry(self, path):
		""" Remove one entry from the cache, one dir or one file. """

		q = Cache._queue

		row = list(self.select('''SELECT fid FROM files WHERE fname=?;''', (path,)))

		if row == []:
			# we've got a dir...
			for regular_file in self.select('SELECT fid FROM files WHERE fname LIKE ?;', (os.path.dirname(path),)):
				q.put(('DELETE FROM k_on_f WHERE fid=?;', (regular_file[0],), None))
				q.put(('DELETE FROM files  WHERE fid=?;', (regular_file[0],), None))
				logging.info("%s: removed cache entry for file %s." % (self.getName(), styles.stylize(styles.ST_PATH, regular_file[0])))
		else:
			q.put(('DELETE FROM k_on_f WHERE fid=?;', (row[0]), None))
			q.put(('DELETE FROM files WHERE fid=?;', (row[0]), None))

		logging.info("%s: removed cache entry for %s." % (self.getName(), styles.stylize(styles.ST_PATH, path)))
	def query(self, req):
		""" Query the cache with some keywords and return some files as a sequence. """

		#nbk   = len(req.split(','))

		# TODO: check req against injections, against bad chars (regex)
		# and verify keyword existence...

		# TODO: implement '+' and '|' in incoming request to build a more precise SELECT.
		# EG 'WHERE kname == '<...>' AND kname =='<...>' OR kname = '<...>' AND kname = '<...>'

		return self.select('''
						SELECT files.fname
						FROM keywords
							NATURAL JOIN k_on_f
							NATURAL JOIN files
						WHERE keywords.kname in (%s)
						GROUP BY files.fname
						ORDER BY files.fname;''' % (re.sub(r'(\w+)', r"'\1'", req)))
