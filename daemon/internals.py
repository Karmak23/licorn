# -*- coding: utf-8 -*-
"""
Licorn Daemon internals.

Copyright (C) 2007-2008 Olivier Cortès <oc@5sys.fr>
Licensed under the terms of the GNU GPL version 2.

"""
import os, time, re, stat, xattr, inotify, socket, mimetypes, urlparse, posixpath, urllib

# try python2.5 else python2.4
try :  import sqlite3 as sqlite
except ImportError : from pysqlite2 import dbapi2 as sqlite

from Queue              import Queue
from threading          import Thread, Event
from pyinotify          import ThreadedNotifier, WatchManager, EventsCodes, ProcessEvent
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
	_stopevent    = Event()
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
		if not Cache._stopevent.isSet() :
			logging.progress("%s: stopping thread." % (self.getName()))
			Cache._stopevent.set()
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
		s = Cache._stopevent

		logging.progress('%s: thread running.' % self.getName())

		while not s.isSet() :

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

		if self._stopevent.isSet() :
			raise exceptions.StopException("%s: stopped, can't cache." % self.getName())
	
		if fsapi.is_backup_file(filename) :
			logging.debug("%s: NOT updating cache for %s, it is a backup file." % (self.getName(), styles.stylize(styles.ST_PATH, filename)))
			return

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
class FileSearchServer(Thread) :
	""" Thread which answers to queries sent through unix socket. """
	def __init__(self, pname = '<unknown>') :
		self.name = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		# old socket from a crashed daemon ? 
		# remove it, the ThreadingUnixStreamServer will create it.
		#if os.path.exists(_socket_path) : os.unlink(_socket_path)
		
		self._stopevent = Event()
		self.server     = ThreadingTCPServer(('127.0.0.1', _socket_port), FileSearchRequestHandler)
		self.server.allow_reuse_address = True

		# TODO: the socket is set to non-blocking to be able to gracefully terminate the thread,
		# but this could lead to CPU hogging problems. VERIFY THIS !!
		self.server.socket.setblocking(False)
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		#os.chmod(_socket_path, stat.S_IRUSR|stat.S_IWUSR|stat.S_IRGRP|stat.S_IWGRP|stat.S_IROTH|stat.S_IWOTH)
		while not self._stopevent.isSet() :
			self.server.handle_request()
			time.sleep(0.01)
		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		if not self._stopevent.isSet() :
			logging.progress("%s: stopping thread." % (self.getName()))
			self._stopevent.set()
			self.server.socket.close()
			self.server.server_close()
			if os.path.exists(_socket_path) :
				os.unlink(_socket_path)
class INotifier(ThreadedNotifier):
	""" A Thread which collect INotify events and does what is appropriate with them. """
	def __init__(self, cache, pname = '<unknown>') :

		self.cache = cache

		# needed to watch a bunch of dirs/files
		inotify.max_user_watches.value = 65535

		self.wm = WatchManager()

		self.name = str(self.__class__).rsplit('.', 1)[1].split("'")[0]

		ThreadedNotifier.__init__(self, self.wm, None)
		self.setName("%s/%s" % (pname, self.name))   # can't be passed as argument when instanciating.

		logging.info('%s: set inotify max user watches to %d.' % (self.getName(), inotify.max_user_watches.value))

		self.mask = EventsCodes.IN_CLOSE_WRITE | EventsCodes.IN_CREATE \
			| EventsCodes.IN_MOVED_TO | EventsCodes.IN_MOVED_FROM | EventsCodes.IN_DELETE

		from licorn.core import groups
		groups.Select(groups.FILTER_STANDARD)
			
		for gid in groups.filtered_groups :
			group_home = "/home/%s/%s" % (groups.configuration.groups.names['plural'], groups.groups[gid]['name'])
			wdd        = self.wm.add_watch(group_home, self.mask, 
										proc_fun=ProcessInotifyGroupEvent(self, gid, group_home, self.getName(), self.cache, groups, self.mask),
										rec=True)
			logging.info("%s: added recursive watch for %s." % (self.getName(), styles.stylize(styles.ST_PATH, group_home)))
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		ThreadedNotifier.run(self)
		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		if ThreadedNotifier.isAlive(self) :
			logging.progress("%s: stopping thread." % (self.getName()))
			try :
				ThreadedNotifier.stop(self)
			except KeyError, e :
				logging.warning('%s: KeyError when stopping: %s' % (self.getName(), e))
class InitialCollector(Thread) :
	""" Thread which collects initial data to build internal database, then run RPC listener to ease database updates. """
	def __init__(self, allkeywords, cache, pname = '<unknown>') :
		self.name = str(self.__class__).rsplit('.', 1)[1].split("'")[0]

		Thread.__init__(self, name = "%s/%s" % (pname, self.name))
		self.allkeywords = allkeywords
		self.cache = cache
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		self.cache.cache(self.allkeywords.work_path)
		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		pass

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
class ProcessInotifyGroupEvent(ProcessEvent):
	""" Thread that receives inotify events and applies posix perms and posix1e ACLs on the fly."""

	def __init__(self, notifier, gid, group_path, tname, cache, allgroups, mask) :
		self.notifier  = notifier 
		self.gid       = gid
		self.home      = group_path
		self.cache     = cache
		self.tname     = tname
		self.allgroups = allgroups
		self.mask      = mask
	def process_IN_CREATE(self, event) :
		if event.is_dir :
			fullpath = os.path.join(event.path, event.name)
			logging.debug("%s: Inotify EVENT / %s CREATED." %  (self.tname, fullpath))
			acl = self.allgroups.BuildGroupACL(self.gid, fullpath[len(self.home):])
			try :
				fsapi.check_posix_ugid_and_perms(fullpath, -1, self.allgroups.name_to_gid('acl') , -1, batch = True, auto_answer = True, allgroups = self.allgroups)
				fsapi.check_posix1e_acl(fullpath, False, acl['default_acl'], acl['default_acl'], batch = True, auto_answer = True)

				# watch this new subdir too...
				self.notifier.wm.add_watch(fullpath, self.mask, proc_fun=self, rec=True)
				logging.info("%s: added new recursive watch for %s." % (self.tname, styles.stylize(styles.ST_PATH, fullpath)))

			except (OSError, IOError), e :
				if e.errno != 2 :
					logging.warning("%s: problem in process_IN_CREATE() on %s (was: %s, event=%s)." % (self.tname, fullpath, e, event))

			self.cache.cache(fullpath)
		else :
			# TODO : what to do if it is a file ? handled by _CLOSE_WRITE ?
			pass
	def process_IN_CLOSE_WRITE(self, event) :
		fullpath = os.path.join(event.path, event.name)
		logging.debug("%s: Inotify EVENT / %s CLOSE_WRITE." %  (self.tname, fullpath))
		if os.path.isfile(fullpath) :
			acl = self.allgroups.BuildGroupACL(self.gid, fullpath[len(self.home):])

			try :
				fsapi.check_posix_ugid_and_perms(fullpath, -1, self.allgroups.name_to_gid('acl'), batch = True, auto_answer = True, allgroups = self.allgroups)
				fsapi.check_posix1e_acl(fullpath, True, acl['content_acl'], '', batch = True, auto_answer = True)
			except (OSError, IOError), e :
					if e.errno != 2 :
						logging.warning("%s: problem in process_IN_CLOSE_WRITE() on %s (was: %s, event=%s)." % (self.tname, fullpath, e, event))
			self.cache.cache(fullpath)
	def process_IN_DELETE(self, event) :
		fullpath = os.path.join(event.path, event.name)
		logging.debug("%s: Inotify EVENT / %s DELETED." %  (self.tname, styles.stylize(styles.ST_PATH, fullpath)))
		try: 
			self.notifier.wm.rm_watch(self.notifier.wm.get_wd(fullpath), rec=True)
			logging.info("%s: removed watch for %s." % (self.tname, styles.stylize(styles.ST_PATH, fullpath)))
		except Exception, e :
			logging.warning("%s: problem in process_IN_DELETE() on %s (was: %s, event=%s)." % (self.tname, fullpath, e, event))

		self.cache.removeEntry(fullpath)
	def process_IN_MOVED_FROM(self, event) :
		fullpath = os.path.join(event.path, event.name)
		logging.debug("%s: Inotify EVENT / %s MOVED FROM." % (self.tname, fullpath))
		try : 
			self.notifier.wm.rm_watch(self.notifier.wm.get_wd(fullpath), rec=True)
			logging.info("%s: removed watch for %s." % (self.tname, styles.stylize(styles.ST_PATH, fullpath)))

		except Exception, e :
			logging.warning("%s: problem in process_IN_MOVED_FROM() on %s (was: %s, event=%s)." % (self.tname, fullpath, e, event))

		self.cache.removeEntry(fullpath)
	def process_IN_MOVED_TO(self, event) :
		fullpath = os.path.join(event.path, event.name)
		logging.debug("%s: Inotify EVENT / %s MOVED." %  (self.tname, fullpath))
		acl = self.allgroups.BuildGroupACL(self.gid, fullpath[len(self.home):])

		try :
			if event.is_dir :
				fsapi.check_posix_ugid_and_perms(fullpath, -1, self.allgroups.name_to_gid('acl') , -1, batch = True, auto_answer = True, allgroups = self.allgroups)
				fsapi.check_posix1e_acl(fullpath, False, acl['default_acl'], acl['default_acl'], batch = True, auto_answer = True)
				dir_info = {	
					"path"         : fullpath,
					"type"         : stat.S_IFDIR,
					"mode"         : -1,
					"content_mode" : -1,
					"access_acl"   : acl['default_acl'],
					"default_acl"  : acl['default_acl'],
					"content_acl"  : acl['content_acl']
					}

				fsapi.check_posix_dir_contents(dir_info, -1, self.allgroups.name_to_gid(acl['group']), batch = True, auto_answer = True)
				fsapi.check_posix1e_dir_contents(dir_info, batch = True, auto_answer = True)

				# watch this new subdir too...
				self.notifier.wm.add_watch(fullpath, self.mask, proc_fun=self, rec=True)
				logging.info("%s: added new recursive watch for %s." % (self.tname, styles.stylize(styles.ST_PATH, fullpath)))
				self.cache.cache(fullpath)

			elif os.path.isfile(fullpath) :
				fsapi.check_posix_ugid_and_perms(fullpath, -1, self.allgroups.name_to_gid('acl'), batch = True, auto_answer = True, allgroups = self.allgroups)
				fsapi.check_posix1e_acl(fullpath, True, acl['content_acl'], '', batch = True, auto_answer = True)
				self.cache.cache(fullpath)
		
			# don't check symlinks, sockets and al.

		except (OSError, IOError), e :
			if e.errno != 2 :
				logging.warning("%s: problem in process_IN_MOVED_TO() on %s (was: %s, event=%s)." % (self.tname, fullpath, e, event))
	def process_IN_IGNORED(self, event) : pass
