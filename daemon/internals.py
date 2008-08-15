# -*- coding: utf-8 -*-
"""
Licorn Daemon internals.

Copyright (C) 2007-2008 Olivier Cortès <oc@5sys.fr>
Licensed under the terms of the GNU GPL version 2.
"""
import os, time, re, stat, xattr, socket, mimetypes, urlparse, posixpath, urllib, gamin
from collections import deque

# try python2.5 else python2.4
try :  import sqlite3 as sqlite
except ImportError : from pysqlite2 import dbapi2 as sqlite

from Queue              import Queue
from threading          import Thread, Event
from SocketServer       import ThreadingTCPServer, BaseRequestHandler, TCPServer
from BaseHTTPServer	    import BaseHTTPRequestHandler, HTTPServer
from licorn.foundations import fsapi, logging, exceptions, styles, process

### status codes ###
LCN_MSG_STATUS_OK      = 1
LCN_MSG_STATUS_PARTIAL = 2
LCN_MSG_STATUS_ERROR   = 254
LCN_MSG_STATUS_UNAVAIL = 255

LCN_MSG_CMD_QUERY       = 1
LCN_MSG_CMD_STATUS      = 2
LCN_MSG_CMD_REFRESH     = 3
LCN_MSG_CMD_UPDATE      = 4
LCN_MSG_CMD_END_SESSION = 254

### default paths ###
_cache_path  = '/var/cache/licorn/licornd.db'
_socket_path = '/var/run/licornd.sock'
_socket_port = 3355
_http_port   = 3356
_buffer_size = 16*1024
log_path     = '/var/log/licornd.log'
pid_path     = '/var/run/licornd.pid'
wpid_path    = '/var/run/licornd-webadmin.pid'
pname        = 'licornd'

def fork_http_server() :
	try: 
		if os.fork() == 0 :
			# FIXME: drop_privileges() → become setuid('licorn:licorn')

			open(wpid_path,'w').write("%s\n" % os.getpid())
			process.set_name('%s/webadmin' % pname)
			logging.progress("%s/webadmin: starting (pid %d)." % (pname, os.getpid()))
			httpd = TCPServer(('127.0.0.1', _http_port), HTTPRequestHandler)
			httpd.serve_forever()
	except OSError, e: 
		logging.error("%s/webadmin: fork failed: errno %d (%s)." % (pname, e.errno, e.strerror))
	except socket.error, e :
		logging.error("%s/webadmin: socket error %s." % (pname, e))
	except KeyboardInterrupt :
		logging.warning('%s/webadmin: terminating on interrupt signal.' % pname)
		raise SystemExit

### Classes ###
class Client :
	""" Abstraction class to talk to Licorn server through a socket.  """
	def __init__(self, socket_path = _socket_path) :
		self.is_closed = Event()
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# don't. this is bad.
		#self.socket.setblocking(False)
		self.socket.connect(('localhost', _socket_port))
	def EndSession(self) :
		""" Close the socket. Enclose this in an Event() because GTK apps can call us twice or more... """
		if not self.is_closed.isSet() :
			self.socket.sendall('%s:\n' % LCN_MSG_CMD_END_SESSION)
			self.socket.shutdown(socket.SHUT_WR)
			self.socket.recv(3)
			self.socket.close()
			self.is_closed.set()
	def StatusRequest(self) :
		""" Ask the server how beautiful the weather is on its side of the socket. """

		status = LCN_MSG_STATUS_OK
		line   = ''
		load   = 0.0
		nrf    = 0
		nrk    = 0

		# speedup
		s = self.socket

		try :
			s.send("%s:\n" % LCN_MSG_CMD_STATUS)

			while True :
				try :
					buf = s.recv(1)

					if buf == '\n' :
						splitted_line = line.split(':')
						
						try : status = int(splitted_line[0])
						except : raise exceptions.LicornHarvestError('Malformed response from server.')
						
						if status in (LCN_MSG_STATUS_OK, LCN_MSG_STATUS_PARTIAL) :
							load = float(splitted_line[1].split('=')[1])
							nrk  = float(splitted_line[2].split('=')[1])
							nrf  = float(splitted_line[3].split('=')[1])
							break

						elif status == LCN_MSG_STATUS_UNAVAIL :
							raise exceptions.LicornHarvestException("Server unavailable (%s)." % splitted_line[1])

						elif status == LCN_MSG_STATUS_ERROR :
							raise exceptions.LicornHarvestError("Server error (%s)." % splitted_line[1])

						else :
							raise exceptions.LicornHarvestError('Unknown return code from server.')

					else :
						line += buf
					
				except socket.error, e :
					if e[0] == 11 :
						logging.debug("%s: socket is slow, waiting a bit..." % self.__class__)
						time.sleep(0.01)
					else :
						raise exceptions.LicornHarvestError('Socket error %s.' % e)

		except Exception, e :
			raise exceptions.LicornHarvestError(str(e))

		return (status, load, nrk, nrf)
	def UpdateRequest(self, path) :

		status       = LCN_MSG_STATUS_OK
		line         = ''

		# speedup
		s = self.socket

		try :
			s.send("%s:%s:\n" % (LCN_MSG_CMD_UPDATE, path))

			while True :
				try :
					buf = s.recv(1)
					if buf == '\n' :
						splitted_line = line.split(':')
						
						try : status = int(splitted_line[0])
						except : raise exceptions.LicornHarvestError('Malformed response from server.')
						
						if status in (LCN_MSG_STATUS_OK, LCN_MSG_STATUS_PARTIAL) :
							# in update mode, server only answers ok|partial|error, nothing more.
							break

						elif status == LCN_MSG_STATUS_UNAVAIL :
							raise exceptions.LicornHarvestException("Server unavailable (%s)." % splitted_line[1])

						elif status == LCN_MSG_STATUS_ERROR :
							raise exceptions.LicornHarvestError("Server error (%s)." % splitted_line[1])

						else :
							raise exceptions.LicornHarvestError('Unknown return code from server.')

					else :
						line += buf
				except socket.error, e :
					if e[0] == 11 :
						logging.debug("%s: socket is slow, waiting a bit..." % self.__class__)
						time.sleep(0.005)
					else :
						raise exceptions.LicornHarvestError('Socket error (%s).' % e)

		except Exception, e :
			raise exceptions.LicornHarvestError(str(e))

		return status
	def KeywordQueryRequest(self, keywords) :

		if keywords == [] : 
			return (LCN_MSG_STATUS_OK, 0, [])

		status       = LCN_MSG_STATUS_OK
		nr           = 0
		files        = []
		line         = ''
		res_count    = 0
		maxfiles     = -1
		sta_not_recv = True

		# speedup
		s = self.socket

		try :
			s.send("%s:%s:\n" % (LCN_MSG_CMD_QUERY, ','.join(keywords)))

			while True :
				try :
					buf = s.recv(1)
					if buf == '\n' :
						if sta_not_recv :
							splitted_line = line.split(':')
							
							try : status = int(splitted_line[0])
							except : raise exceptions.LicornHarvestError('Malformed response from server.')
							
							if status in (LCN_MSG_STATUS_OK, LCN_MSG_STATUS_PARTIAL) :
								nr = int(splitted_line[1])

							elif status == LCN_MSG_STATUS_UNAVAIL :
								raise exceptions.LicornHarvestException("Server unavailable (%s)." % splitted_line[1])

							elif status == LCN_MSG_STATUS_ERROR :
								raise exceptions.LicornHarvestError("Server error (%s)." % splitted_line[1])

							else :
								raise exceptions.LicornHarvestError('Unknown return code from server.')

							sta_not_recv = False
							if nr == 0 : break

						else : # status line has already been received.
							res_count += 1
							files.append(line)
							if res_count == nr : break

						line = ''
					else :
						line += buf

				except socket.error, e :
					if e[0] == 11 :
						time.sleep(0.05)
					else :
						raise exceptions.LicornHarvestError('Socket error (%s).' % e)

		except Exception, e :
			raise exceptions.LicornHarvestError(str(e))

		return (status, nr, files)

### Threads ###
class Cache(Thread):
	""" Thread & Singleton cache object to help files and keywords caching through an SQLite database. """
	__singleton   = None
	allkeywords   = None
	localKeywords = {}
	_stop_event   = Event()
	_dbfname      = ''
	_db           = None
	_cursor       = None
	_queue        = Queue()

	def __new__(cls, *args, **kwargs) :
		if cls.__singleton is None :
			cls.__singleton = super(Cache, cls).__new__(cls, *args, **kwargs)
		return cls.__singleton
	def __init__(self, allkeywords = None, pname = '<unknown>', dbfname = _cache_path) :

		self.name = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		if Cache.allkeywords is None :
			if allkeywords is None :
				raise exceptions.BadArgumentError('You must create at least one instance of the cache WITH "allkeywords" parameter set.')
			else :
				Cache.allkeywords = allkeywords

		Cache._dbfname = dbfname
	def stop(self) :
		"""Stop this thread."""
		if not Cache._stop_event.isSet() :
			logging.progress("%s: stopping thread." % (self.getName()))
			Cache._stop_event.set()
			Cache._queue.put((None, None, None))
	def status(self) :
		""" Return statistics as a sequence. """

		c = Cache._cursor

		knb = self.select('SELECT COUNT(*) FROM keywords;')
		fnb = self.select('SELECT COUNT(*) FROM files;')

		return (knb, fnb)
	def setupAndConnectDB(self) :
		""" Create database if needed, or update keywords table if needed, and vacuum some obsolete records if needed. """

		d = os.path.dirname(Cache._dbfname)
		if not os.path.exists(d) :
			os.makedirs(d)
		del d

		Cache._db     = sqlite.connect(Cache._dbfname)
		# prevent string conversion errors from database when filenames are not UTF-8 encoded.
		Cache._db.text_factory = str

		Cache._cursor = Cache._db.cursor()
		c             = Cache._cursor

		syskw = Cache.allkeywords.keywords.keys() # just a speedup

		try :
			c.execute('SELECT kid, kname FROM keywords;')

		except sqlite.OperationalError :
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
			c.execute('SELECT kid,kname FROM keywords;')

			logging.progress('%s: initialized.' % self.getName())

		cache_kw = c.fetchall()
		for (kid, kname) in cache_kw :
			if kname in syskw :
				Cache.localKeywords[kname] = kid
			else :
				# delete keywords which are in cache and have been deleted from system
				# since last DB use.
				c.execute('DELETE FROM keywords WHERE kid=?;', (kid,))
				c.execute('DELETE FROM k_on_f   WHERE kid=?;', (kid,))
				logging.progress("%s: deleted obsolete keyword %s from cache database." % (self.getName(), kname))

		for kname in syskw :
			if kname not in Cache.localKeywords.keys() :
				c.execute('INSERT OR REPLACE INTO keywords(kname) VALUES(?);', (kname,))
				logging.progress("%s: inserted missing keyword %s into cache database." % (self.getName(), kname))

		# this is done once again in self.vacuumDatabase()
		c.execute('DELETE FROM k_on_f WHERE kid NOT IN ( SELECT kid FROM keywords );')
		logging.progress("%s: Removed %d obsolete rows from cache database." % (self.getName(), c.rowcount))

		try : c.execute('COMMIT;')
		except : pass

		logging.progress('%s: keywords loaded.' % self.getName())
	def run(self) :
		""" Set up database if needed and wait for any request in the queue."""

		self.setupAndConnectDB()

		c = Cache._cursor
		q = Cache._queue
		s = Cache._stop_event

		logging.progress('%s: thread running.' % self.getName())

		while not s.isSet() :

			# then process every action
			request, arguments, result = q.get()

			logging.debug2('%s: executing %s %s.' % (self.getName(), request, arguments))

			if request != None :
				c.execute(request, arguments)
				if result :
					for record in c :
						result.put(record)
					logging.debug('%s: terminating request result.' % self.getName())
					result.put(False)

		Cache._db.close()
		logging.progress("%s: thread ended." % (self.getName()))
	def select(self, request, arguments = None) :
		""" Execute a SELECT statement.
			Put a standard SQL request in the queue.
			Wait for the result and yield it, line by line.
		"""
		result = Queue()
		Cache._queue.put((request, arguments or tuple(), result))
		record = result.get()
		while record :
			yield record
			record = result.get()
	def vacuumDatabase(self) :
		"""Try to clean the cache as much as possible, remove unused or obsolete rows and so on."""

		# FIXME don't use the cursor directly, use the select() function to use the Queue power !
		return

		db = sqlite.connect(self.dbFileName)
		# prevent string conversion errors from database when filenames are not UTF-8 encoded.
		db.text_factory = str
		c  = db.cursor()

		# this is done once again in self.InitializeDatabase()
		c.execute('DELETE FROM k_on_f WHERE kid NOT IN ( SELECT kid FROM keywords );')
		logging.progress("%s: Removed %d obsolete rows from cache database." % (self.getName(), c.rowcount))

		c.execute('SELECT fid, fname FROM files;')
		
		files = c.fetchall()
		for (fid, fname) in files :
			if not os.path.exists(fname) :
				c.execute('DELETE FROM k_on_f WHERE fid=?;', (fid,))
				c.execute('DELETE FROM files  WHERE fid=?;', (fid,))
				logging.progress("%s: Removed non existing file %s from cache database." % (self.getName(), fname))

		try : c.execute('COMMIT;')
		except : pass
	def __cache_one_file(self, filename, batch = False, force = False) :
		""" Add a file to the cache. """

		if self._stop_event.isSet() :
			raise exceptions.LicornStopException("%s: stopped, can't cache." % self.getName())
	
		fstat = os.lstat(filename)

		c = Cache._cursor
		q = Cache._queue

		try :
			fid, fname, fmtime = self.select('SELECT fid, fname, fmtime FROM files WHERE fid=?;', (fstat.st_ino,))
		except ValueError :
			fid = None

		if force or fid is None or fmtime != fstat.st_mtime :

			logging.progress("%s: updating cache record for %s." % (self.getName(), styles.stylize(styles.ST_PATH, filename)))

			q.put(('''INSERT OR REPLACE INTO files(fid, fname, fsize, fmtime) VALUES(?,?,?,?);''', 
				(fstat.st_ino, filename, fstat.st_size, fstat.st_mtime), None))

			try :
				attrs = xattr.getxattr(filename, Cache.allkeywords.licorn_xattr).split(',')
				good  = filter(lambda x: x in Cache.allkeywords.keywords.keys(), attrs)
				bad   = filter(lambda x: x not in Cache.allkeywords.keywords.keys(), attrs)

				if bad != [] :
					logging.warning("%s: file %s holds inexistant keyword(s) %s." % (self.getName(), styles.stylize(styles.ST_PATH, filename), bad))

				if good != [] :
					logging.progress("%s: Inserting inode->kw %d->%s." % (self.getName(), fstat.st_ino, good))

					for k in good :
						q.put(('''INSERT OR REPLACE INTO k_on_f(fid, kid) VALUES(?,?);''', (fstat.st_ino, Cache.localKeywords[k]), None))
							
			except (OSError, IOError), e :
				if e.errno not in (2, 61, 95) :
					raise e
				else :
					# FIXME: why delete the entry on err95 ? why not just let the cache as it is ?
					q.put(('''DELETE FROM k_on_f WHERE fid=?;''', (fstat.st_ino,), None))

			try :
				# TODO: get facl / perms and cache them, to answer user requests according to file perms.
				#
				# TODO: why not just return the queries and let the gui verify the user has rights on the file ?
				# if it hasn't, he won't be able to open it any way. but this could be a 
				# security risk, knowing the exact name of the file. SO : the daemon should return only
				# allowed files.
				pass

			except (OSError, IOError), e :
				if e.errno not in (2, 61, 95) :
					raise e
		else :
			logging.progress("%s: not caching %s, up-to-date." % (self.getName(), styles.stylize(styles.ST_PATH, filename)))
	def cache(self, path, force = False) :
		""" Recursively fsapi.minifind() a dir and its subdirs for files and update the cache with data found. """

		logging.progress('%s: Starting to Cache(%s, force=%d).' % (self.getName(), styles.stylize(styles.ST_PATH, path), force))

		try :
			map(lambda x: self.__cache_one_file(x, batch = True, force = force), fsapi.minifind(path, type = stat.S_IFREG))
		except exceptions.LicornStopException :
			logging.info("%s: stop request received, cleaning up." % self.getName())
	def removeEntry(self, path) :
		""" Remove one entry from the cache, one dir or one file. """

		q = Cache._queue

		row = list(self.select('''SELECT fid FROM files WHERE fname=?;''', (path,)))

		if row == [] :
			# we've got a dir...
			for regular_file in self.select('SELECT fid FROM files WHERE fname LIKE ?;', (os.path.dirname(path),)) :
				q.put(('DELETE FROM k_on_f WHERE fid=?;', (regular_file[0],), None))
				q.put(('DELETE FROM files  WHERE fid=?;', (regular_file[0],), None))
				logging.info("%s: removed cache entry for file %s." % (self.getName(), styles.stylize(styles.ST_PATH, regular_file[0])))
		else :
			q.put(('DELETE FROM k_on_f WHERE fid=?;', (row[0]), None))
			q.put(('DELETE FROM files WHERE fid=?;', (row[0]), None))

		logging.info("%s: removed cache entry for %s." % (self.getName(), styles.stylize(styles.ST_PATH, path)))
	def query(self, req) :
		""" Query the cache with some keywords and return some files as a sequence. """

		#nbk   = len(req.split(','))
		
		# TODO : check req against injections, against bad chars (regex)
		# and verify keyword existence...

		# TODO : implement '+' and '|' in incoming request to build a more precise SELECT.
		# EG 'WHERE kname == '<...>' AND kname =='<...>' OR kname = '<...>' AND kname = '<...>'

		return self.select('''
						SELECT files.fname 
						FROM keywords 
							NATURAL JOIN k_on_f 
							NATURAL JOIN files 
						WHERE keywords.kname in (%s) 
						GROUP BY files.fname 
						ORDER BY files.fname;''' % (re.sub(r'(\w+)', r"'\1'", req)))
class ACLChecker(Thread):
	""" A Thread which gets paths to check from a Queue, and checks them in time. """
	__singleton = None
	_queue      = Queue(0)
	_stop_event = Event()
	def __new__(cls, *args, **kwargs) :
		if cls.__singleton is None :
			cls.__singleton = super(ACLChecker, cls).__new__(cls, *args, **kwargs)
		return cls.__singleton
	def __init__(self, cache, pname = '<unknown>') :

		self.name  = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		self.cache      = cache

		# will be filled later
		self.inotifier  = None
		self.groups     = None
	def set_inotifier(self, inotifier) :
		self.inotifier = inotifier
	def set_groups(self, groups) :
		self.groups = groups
	def process(self, event):
		""" Process Queue and apply ACL on the fly, then update the cache. """

		path, gid = event

		if path is None: return

		acl = self.groups.BuildGroupACL(gid, path)

		try :
			if os.path.isdir(path) :
				fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl') , -1)
				self.inotifier.just_checked.append(path)
				fsapi.auto_check_posix1e_acl(path, False, acl['default_acl'], acl['default_acl'])
				self.inotifier.just_checked.append(path)
				self.inotifier.just_checked.append(path)
			else :
				fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl'))
				self.inotifier.just_checked.append(path)
				fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')
				self.inotifier.just_checked.append(path)

		except (OSError, IOError), e :
			if e.errno != 2 :
				logging.warning("%s: problem in GAMCreated on %s (was: %s, event=%s)." % (self.getName(), path, e, event))

		#self.cache.cache(path)
	def enqueue(self, path, gid) :
		if self._stop_event.isSet() :
			logging.progress("%s: thread is stopped, not enqueuing %s|%s." % (self.getName(), path, gid))
			return

		self._queue.put((path, gid))
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		Thread.run(self)

		while not self._stop_event.isSet() :
			self.process(self._queue.get())

		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		logging.progress("%s: stopping thread." % (self.getName()))
		self._stop_event.set()
		self._queue.put((None, None))
class INotifier(Thread):
	""" A Thread which collect INotify events and does what is appropriate with them. """
	__singleton = None
	_stop_event = Event()
	_to_watch   = deque()
	_to_remove  = deque()
	def __new__(cls, *args, **kwargs) :
		if cls.__singleton is None :
			cls.__singleton = super(INotifier, cls).__new__(cls, *args, **kwargs)
		return cls.__singleton
	def __init__(self, checker, cache, pname = '<unknown>') :

		self.name  = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		self.cache      = cache
		self.aclchecker = checker
		checker.set_inotifier(self)
		self.just_checked = []

		self.mon = gamin.WatchMonitor()

		# keep track of watched directories, and func prototypes used 
		# to chk the data inside. this will avoid massive CPU usage, 
		# at the cost of a python dict.
		self.wds = []

		from licorn.core import groups
		groups.Select(groups.FILTER_STANDARD)
		self.groups = groups

		checker.set_groups(groups)

		#self.mon.no_exists()

		for gid in groups.filtered_groups :
			group_home = "%s/%s/%s" % (groups.configuration.defaults.home_base_path,
							groups.configuration.groups.names['plural'], groups.groups[gid]['name'])

			def myfunc(path, event, gid = gid, dirname = group_home) :
				return self.process_event(path, event, gid, dirname)

			self.add_watch(group_home, myfunc)
	def process_event(self, basename, event, gid, dirname):
		""" Process Gamin events and apply ACLs on the fly. """

		if basename[-1] == '/' :
			# we received an event for the root dir of a new watch.
			# this is a duplicate of the parent/new_dir. Just discard
			# it.
			return

		# with Gamin, sometimes it is an abspath, sometimes not.
		# this happens on GAMChanged (observed the two), and 
		# GAMDeleted (observed only abspath).
		if basename[0] == '/' :
			path = basename
		else :
			path = '%s/%s' % (dirname, basename)

		if event == gamin.GAMExists and path in self.wds :
			# skip already watched directories, and /home/groups/*
			return

		if fsapi.is_backup_file(path) :
			logging.debug("%s: discarding Inotify event on %s, it's a backup file." % (self.getName(), styles.stylize(styles.ST_PATH, path)))
			return

		if event in (gamin.GAMExists, gamin.GAMCreated) :

			logging.debug("%s: Inotify %s %s." %  (self.getName(), styles.stylize(styles.ST_MODE, 'GAMCreated/GAMExists'), path))

			try :
				if os.path.isdir(path) :
					self._to_watch.append((path, gid))

				self.aclchecker.enqueue(path, gid)

			except (OSError, IOError), e :
				if e.errno != 2 :
					logging.warning("%s: problem in GAMCreated on %s (was: %s, event=%s)." % (self.getName(), path, e, event))

		elif event == gamin.GAMChanged :

			if path in self.just_checked :
				# skip the first GAMChanged event, it was generated
				# by the CHK in the GAMCreated part.
				self.just_checked.remove(path)
				return

			logging.debug("%s: Inotify %s on %s." %  (self.getName(),
				styles.stylize(styles.ST_URL, 'GAMChanged'), path))

			self.aclchecker.enqueue(path, gid)

		elif event == gamin.GAMMoved :

			logging.progress('%s: Inotify %s, not handled yet %s.' % (self.getName(), 
				styles.stylize(styles.ST_PKGNAME, 'GAMMoved'), styles.stylize(styles.ST_PATH, path)))

		elif event == gamin.GAMDeleted :
			# if a dir is deleted, we will get 2 GAMDeleted events: 
			#  - one for the dir watched (itself deleted)
			#  - one for its parent, signaling its child was deleted.

			logging.debug("%s: Inotify %s for %s." %  (self.getName(), 
				styles.stylize(styles.ST_BAD, 'GAMDeleted'), styles.stylize(styles.ST_PATH, path)))

			# we can't test if the “path” was a dir, it has just been deleted
			# just try to delete it, wait and see. If it was, this will work.
			self._to_remove.append(path)

			# TODO: remove recursively if DIR.
			#self.cache.removeEntry(path)

		elif event in (gamin.GAMEndExist, gamin.GAMAcknowledge) :
			logging.debug('%s: Inotify %s for %s.' % (self.getName(), styles.stylize(styles.ST_REGEX, 'GAMEndExist/GAMAcknowledge'), path))

		else :
			logging.debug('%s: unhandled Inotify event “%s” %s.' % (self.getName(), event, path))
	def add_watch(self, path, func) :

		if path in self.wds :
			return 0

		self.wds.append(path)
		logging.info("%s: %s inotify watch for %s [total: %d]." % (self.getName(),
			styles.stylize(styles.ST_OK, 'adding'),
			styles.stylize(styles.ST_PATH, path),
			len(self.wds)))
		return self.mon.watch_directory(path, func)
	def remove_watch(self, path) :
		if path in self.wds :
			try :
				self.wds.remove(path)
				logging.info("%s: %s inotify watch for %s [left: %d]." % (self.getName(), 
					styles.stylize(styles.ST_BAD, 'removing'),
					styles.stylize(styles.ST_PATH, path),
					len(self.wds)))

				# TODO: recurse subdirs if existing, to remove subwatches
				ret = self.mon.stop_watch(path) 
				return ret
			except gamin.GaminException :
				pass
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		Thread.run(self)

		try :
			already_waited = False
			while not self._stop_event.isSet() :

				while (len(self._to_remove) > 0) :
					# remove as many watches as possible in the same time,
					# to help relieve the daemon.
					self.remove_watch(self._to_remove.pop())

					# don't forget to handle_events(), to flush the GAM queue
					self.mon.handle_events()


				if len(self._to_watch) :
					# add one path at a time, to not stress the daemon, and
					# make new inotified paths come smoother.

					path, gid = self._to_watch.pop()
					def myfunc(path, event, gid = gid, dirname = path) :
						return self.process_event(path, event, gid, dirname)
					self.add_watch(path, myfunc)

					# don't forget to handle_events(), to flush the GAM queue
					self.mon.handle_events()

				while self.mon.event_pending() :
					self.mon.handle_one_event()
					self.mon.handle_events()
					already_waited = False
				else :
					if already_waited :
						self.mon.handle_events()
						time.sleep(0.01)
					else :
						already_waited = True
						self.mon.handle_events()
						time.sleep(0.001)
		except :
			if not self._stop_event.isSet() :
				raise

		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		if Thread.isAlive(self) and not self._stop_event.isSet() :
			logging.progress("%s: stopping thread." % (self.getName()))

			self._stop_event.set()

			while len(self.wds) :
				rep = self.wds.pop()
				logging.info("%s: %s inotify watch for %s [left: %d]." % (self.getName(), 
					styles.stylize(styles.ST_BAD, 'removing'),
					styles.stylize(styles.ST_PATH, rep),
					len(self.wds)))
				self.mon.stop_watch(rep)
				self.mon.handle_events()

			del self.mon

class FileSearchServer(Thread) :
	""" Thread which answers to queries sent through unix socket. """
	def __init__(self, pname = '<unknown>') :
		self.name = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		# old socket from a crashed daemon ? 
		# remove it, the ThreadingUnixStreamServer will create it.
		#if os.path.exists(_socket_path) : os.unlink(_socket_path)
		
		self._stop_event = Event()
		self.server     = ThreadingTCPServer(('127.0.0.1', _socket_port), FileSearchRequestHandler)
		self.server.allow_reuse_address = True

		# TODO: the socket is set to non-blocking to be able to gracefully terminate the thread,
		# but this could lead to CPU hogging problems. VERIFY THIS !!
		self.server.socket.setblocking(False)
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		#os.chmod(_socket_path, stat.S_IRUSR|stat.S_IWUSR|stat.S_IRGRP|stat.S_IWGRP|stat.S_IROTH|stat.S_IWOTH)
		while not self._stop_event.isSet() :
			self.server.handle_request()
			time.sleep(0.01)
		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		if not self._stop_event.isSet() :
			logging.progress("%s: stopping thread." % (self.getName()))
			self._stop_event.set()
			self.server.socket.close()
			self.server.server_close()
			if os.path.exists(_socket_path) :
				os.unlink(_socket_path)

### Request Handlers and Event Processors ###
class HTTPRequestHandler(BaseHTTPRequestHandler) :
	def do_HEAD(self) :
		f = self.send_head()
		if f :
			f.close()
	def do_GET(self) :
		f = self.send_head()
		if f :
			if type(f) in (type(""), type(u'')) :
				self.wfile.write(f)
			else :
				buf = f.read(_buffer_size)
				while buf :
					self.wfile.write(buf)
					buf = f.read(_buffer_size)
				f.close()
	def do_POST(self) :
		""" Handle POST data and create a dict to be used later."""

		# TODO: protect ourselves against POST flood : if (too_much_data) : send_header('BAD BAD') and stop()
		
		post_data = self.rfile.read(int(self.headers.getheader('content-length')))

		post_data = post_data.split('&')
		self.post_args = {}
		for var in post_data :
			key, value = var.split('=')

			if value != '' :
				value = urllib.unquote_plus(value)

			if self.post_args.has_key(key) :
				if type(self.post_args[key]) == type('') :
					self.post_args[key] = [ self.post_args[key], value ]
				else :
					self.post_args[key].append(value)
			else :
				self.post_args[key] = value
			
		#print '%s' % self.post_args

		self.do_GET()
	def send_head(self) :
		"""Common code for HEAD/GET/POST commands.

		This sends the response code and MIME headers.

		Return value is either a file object (which has to be copied
		to the outputfile by the caller unless the command was HEAD,
		and must be closed by the caller under all circumstances), or
		None, in which case the caller has nothing further to do.

		"""

		#logging.progress('serving HTTP Request: %s.' % self.path)
		
		retdata = None

		if self.authorization() :
			try :
				retdata = self.serve_virtual_uri()
			except exceptions.LicornWebException :
				retdata = self.serve_local_file()

		self.end_headers()
		return retdata
	def authorization(self) :
		""" Return True if authorization exists AND user is authorized."""

		return True

		authorization = self.headers.getheader("authorization")
		if authorization :
			authorization = authorization.split()
			if len(authorization) == 2:
				import base64, binascii
				if authorization[0].lower() == "basic":
					try:
						authorization = base64.decodestring(authorization[1])
					except binascii.Error:
						pass
					else:
						authorization = authorization.split(':')
						if len(authorization) == 2 :
							#
							# TODO: authorization code goes here.
							#
							return True
		return False
	def format_post_args(self) :
		""" Prepare POST data for exec statement."""

		# TODO: verify there is no other injection problem than the '"' !!

		postargs = []
		for key, val in self.post_args.items() :
			if type(val) == type('') :
				postargs.append('%s = "%s"' % (key,val.replace('"', '\"')))
			else :
				postargs.append('%s = %s' % (key, val))

		return postargs
	def serve_virtual_uri(self) :
		"""Serve dynamic URIs with our own code, and create pages on the fly.

		TODO: integrate a caching mechanism, if it is needed, at least for /*/lists.
		Note: the caching mechanism needs love to verify it is really needed. This is
		a webadmin interface (used by only a few persons), and there are not many things
		to compute in these /list/ commands. Caching is probably not really needed…"""

		retdata = None
		rettype = 'text'

		import licorn.interfaces.web as web

		if self.path == '/' :
			retdata = web.base.index(self.path)

		else :
			# remove the last '/' (useless for us, even it if is semantic for a dir/)
			if self.path[-1] == '/' :
				self.path = self.path[:-1]
			# remove the first '/' before splitting (it is senseless here).
			args = self.path[1:].split('/')

			if len(args) == 1 :
				args.append('main')
			elif args[1] == 'list' :
				args[1] = 'main'

			if args[0] in dir(web) :
				logging.progress("Serving %s %s." % (self.path, args))

				if hasattr(self, 'post_args') :
					py_code = 'retdata = web.%s.%s("%s" %s %s)' % (args[0], args[1], self.path,
						', "%s",' % '","'.join(args[2:]) if len(args)>2 else ', ',
						', '.join(self.format_post_args()) )
				else :
					py_code = 'retdata = web.%s.%s("%s" %s)' % (args[0], args[1], self.path, 
						', "%s",' % '","'.join(args[2:]) if len(args)>2 else '')

				try :
					#print "Exec'ing %s." % py_code
					exec py_code

				except (AttributeError, NameError), e :
					# this warning is needed as long as send_head() will produce a 404 for ANY error.
					# when it will able to distinguish between bad requests and real 404, this warning
					# will disapear.
					logging.warning("Exec: %s." % e)
					self.send_error(500, "Internal server error or bad request.")
			else :
				# not a web.* module
				raise exceptions.LicornWebException('Bad base request (probably a regular file request).')
						
		if retdata :
			self.send_response(200)

			if rettype == 'img' :
				self.send_header("Content-type", 'image/png')
			else :
				self.send_header("Content-type", 'text/html; charset=utf-8')
				self.send_header("Pragma", "no-cache")

			self.send_header("Content-Length", len(retdata))

		return retdata
	def serve_local_file(self) :
		""" Serve a local file (image, css, js...) if it exists. """

		retdata = None

		path = self.translate_path(self.path)

		if os.path.exists(path) :
			#logging.progress('serving file: %s.' % path)

			ctype = self.guess_type(path)

			if ctype.startswith('text/') :
				mode = 'r'
			else :
				mode = 'rb'

			try :
				retdata = open(path, mode)

			except (IOError, OSError), e :
				if e.errno == 13 :
					self.send_error(403, "Forbidden.")
				else :
					self.send_error(500, "Internal server error")

		else :
			self.send_error(404, "Not found.")

		if retdata :
			self.send_response(200)
			self.send_header("Content-type", ctype)

			fs = os.fstat(retdata.fileno())
			self.send_header("Content-Length", str(fs[6]))
			self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))

		return retdata
	def guess_type(self, path) :
		"""Guess the type of a file.

		Argument is a PATH (a filename).

		Return value is a string of the form type/subtype,
		usable for a MIME Content-type header.

		The default implementation looks the file's extension
		up in the table self.extensions_map, using application/octet-stream
		as a default; however it would be permissible (if
		slow) to look inside the data to make a better guess.
		"""
		base, ext = posixpath.splitext(path)
		if ext in self.extensions_map:
			return self.extensions_map[ext]
		ext = ext.lower()
		if ext in self.extensions_map:
			return self.extensions_map[ext]
		else:
			return self.extensions_map['']
	def translate_path(self, path) :
		"""Translate a /-separated PATH to the local filename syntax.

		Components that mean special things to the local file system
		(e.g. drive or directory names) are ignored.
		XXX They should probably be diagnosed.

		"""
		# abandon query parameters
		path = urlparse.urlparse(path)[2]
		path = posixpath.normpath(urllib.unquote(path))
		words = path.split('/')
		words = filter(None, words)
		if os.getenv('LICORN_DEVEL') :
			path = os.getcwd()
		else :
			path = '/usr/share/licorn/webadmin'
		for word in words :
			drive, word = os.path.splitdrive(word)
			head, word = os.path.split(word)
			if word in (os.curdir, os.pardir): continue
			path = os.path.join(path, word)
		return path

	#
	# TODO: implement and override BaseHTTPRequestHandler.log_{request,error,message}(), to
	# put logs into logfiles, like apache2 does ({access,error}.log). See
	# /usr/lib/python2.5/BaseHTTPServer.py for details.
	#

	#
	# Static code follows.
	#
	if not mimetypes.inited:
		mimetypes.init() # try to read system mime.types
	extensions_map = mimetypes.types_map.copy()
	extensions_map.update({
		'': 'application/octet-stream', # Default
        })
class FileSearchRequestHandler(BaseRequestHandler) :
	""" Reads commands from a socket and execute actions related to keywords cache database. """
	def findCallingUid(self) :
		"""TODO: do syscalls instead of forking a netstat and a ps."""
		pid = re.findall(r'127.0.0.1:%d\s+127.0.0.1:%d\s+ESTABLISHED(\d+)/' % (self.client_address[1], _socket_port),
			os.popen2(['netstat', '-antp'])[1].read())[0]
		return os.popen2(['ps', '-p', pid, '-o', 'uid='])[1].read().strip()
	
	def handle(self) :
		""" Handle a request from the socket. WARNING : This function is WEAK (in QUERY phase)."""

		self.name     = str(self.__class__).rsplit('.', 1)[1].split("'")[0]

		self.username = self.findCallingUid()

		logging.progress("%s: starting new session with client %s:%s (uid %s)." \
			% (self.name, self.client_address[0], self.client_address[1], styles.stylize(styles.ST_NAME, self.username)))

		buf        = ''
		line       = ''
		self.cache = Cache()

		try : 
			while True :
				buf = self.request.recv(1)

				if buf == '\n' :

					self.load = float(open('/proc/loadavg').read().split(' ')[0])

					if self.load > 10.0 :
						logging.progress("%s: server is loaded, not handling request %s." % (self.name, styles.stylize(styles.ST_PATH, line)))
						self.request.send("%s:loaded:\n" % LCN_MSG_STATUS_UNAVAIL)
					else :

						req = line.split(':')	
						logging.progress("%s: handling request %s from client %s:%s." \
							% (self.name, styles.stylize(styles.ST_PATH, req), self.client_address[0], self.client_address[1]))

						try :
							cmd = int(req[0])
							if   cmd == LCN_MSG_CMD_QUERY : 
								self.HandleQueryRequest(req)
							elif cmd == LCN_MSG_CMD_UPDATE :
								self.HandleUpdateRequest(req[1])
							elif cmd == LCN_MSG_CMD_REFRESH :
								self.HandleRefreshRequest()
							elif cmd == LCN_MSG_CMD_STATUS :
								self.HandleStatusRequest()
							elif cmd == LCN_MSG_CMD_END_SESSION :
								logging.progress("%s: Ending session with client %s:%s." % (self.name, self.client_address[0], self.client_address[1]))
								self.request.send('%s:\n' % LCN_MSG_STATUS_OK)
								self.request.close()
								break
							else :
								logging.progress("%s: Unknown request command %s from client %s:%s." \
									% (self.name, styles.stylize(styles.ST_PATH, cmd), self.client_address[0], self.client_address[1]))
								self.request.send("%s:unknown_command:\n" % LCN_MSG_STATUS_ERROR)
								self.request.close()
								break
						except ValueError :
							logging.warning('%s: Malformed request command %s from client %s:%s.' \
								% (self.name, req[0], self.client_address[0], self.client_address[1]))
							self.request.send("%s:unknown_command:\n" % LCN_MSG_STATUS_ERROR)
							self.request.close()
							break

					line = ''
					logging.progress("%s: waiting for next request from client %s:%s." % (self.name, self.client_address[0], self.client_address[1]))
				else :
					line += buf

		except socket.error, e :
			raise exceptions.LicornHarvestError('Socket error %s with client %s:%s.' % (e, self.client_address[0], self.client_address[1]))
	def HandleQueryRequest(self, req) :
		""" Run a keyword query against the cache and return eventual results through the socket."""

		try :
			# TODO : get authorized paths of caller (from uid and gids) then
			# if root query() without filter
			# else query() with filter

			# TODO: if Queue.notEmpty() :
			#
			#if self.cache.refreshing : msg = LCN_MSG_STATUS_PARTIAL
			#else :                     msg = LCN_MSG_STATUS_OK

			logging.debug("%s/HandleQueryRequest(): querying cache." % self.name)

			result = self.cache.query(req[1])

			logging.debug("%s/HandleQueryRequest(): sending result to client." % self.name)

			self.request.send("%s:%d:\n" % (msg, len(result)))
			map(lambda x: self.request.send("%s\n" % x[0]), result)

		except sqlite.OperationalError, e : 
			logging.warning('%s/HandleQueryRequest(): Database error (%s).' % (self.name, e))
			self.request.send("%s:database_error:\n" % LCN_MSG_STATUS_UNAVAIL)
	def HandleStatusRequest(self) :
		""" Return som status information through the socket. """

		try :
			logging.debug("%s/HandleStatusRequest(): getting status from cache." % self.name)

			(knb, fnb) = self.cache.status()

			msg = '%s:load=%s:keywords=%s:files=%s:\n' % (LCN_MSG_STATUS_OK, self.load, knb, fnb)

		except sqlite.OperationalError, e :
			logging.warning('%s/HandleStatusRequest(): Database error (%s).' % (self.name, e))
			msg = '%s:load=%s:::\n' % (LCN_MSG_STATUS_PARTIAL, self.load)

		logging.debug("%s/HandleStatusRequest(): sending cache status." % self.name)

		self.request.send(msg)
	def HandleRefreshRequest(self) :
		""" Lauch a Thread that will refresh all the database. Totally unefficient, but needed sometimes,
			Since the keywords don't affect file atime/mtime, and daemon could have missed some modifications. """

		#if refresh_lock.acquire(blocking = False) :

		#	refresh = Refresher()
		#	refresh.start()

			# don't release the refresh_lock, refresher thread will do it.

		#	self.request.send("STARTED:please wait:\n")

		#else :
		#	self.request.send("UNAVAIL:locked:\n")
		
		pass
	def HandleUpdateRequest(self, path) :
		""" Handle an update request from a client : update the cache."""

		# TODO : verify authorizations to avoid DoS.


		if os.path.exists(path) :

			logging.progress("%s/HandleUpdateRequest(): updating cache for %s." % (self.name, styles.stylize(styles.ST_PATH, path)))
			
			# TODO: if Queue.notEmpty() :
			#
			#if self.cache.refreshing : status = LCN_MSG_STATUS_PARTIAL
			#else :                     status = LCN_MSG_STATUS_OK

			# always update a dir, fsapi.minifind() will not fail if it is a file.
			self.cache.cache(path, force = True)

			logging.progress("%s: cache updated for %s, ACKing client." % (self.name, styles.stylize(styles.ST_PATH, path)))

			self.request.send('%s:\n' % status)

		else :
			logging.progress("%s/HandleUpdateRequest(): NOT updating cache for %s, path does not exist." % (self.name, styles.stylize(styles.ST_PATH, path)))
			self.request.send('%s:path_does_not_exist:\n' % (LCN_MSG_STATUS_ERROR))
