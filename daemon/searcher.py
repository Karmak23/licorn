# -*- coding: utf-8 -*-
"""
Licorn Daemon Searcher interface.
The searcher is responsible of talking to clients which ask for files, tags, etc.
It works through a Unix socket on the local machine.

Copyright (C) 2007-2009 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, time

from threading          import Thread, Event
from SocketServer       import ThreadingTCPServer, BaseRequestHandler

from licorn.foundations import logging, exceptions, styles
from licorn.daemon.core import dname, socket_path, searcher_port

class SearcherClient:
	""" Abstraction class to talk to the Licorn searcher through a socket.  """
	def __init__(self, socket_path = socket_path):
		self.is_closed = Event()
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# don't. this is bad.
		#self.socket.setblocking(False)
		self.socket.connect(('localhost', searcher_port))
	def EndSession(self):
		""" Close the socket. Enclose this in an Event() because GTK apps can call us twice or more… """
		if not self.is_closed.isSet():
			self.socket.sendall('%s:\n' % LCN_MSG_CMD_END_SESSION)
			self.socket.shutdown(socket.SHUT_WR)
			self.socket.recv(3)
			self.socket.close()
			self.is_closed.set()
	def StatusRequest(self):
		""" Ask the server how beautiful the weather is on its side of the socket. """

		status = LCN_MSG_STATUS_OK
		line   = ''
		load   = 0.0
		nrf    = 0
		nrk    = 0

		# speedup
		s = self.socket

		try:
			s.send("%s:\n" % LCN_MSG_CMD_STATUS)

			while True:
				try:
					buf = s.recv(1)

					if buf == '\n':
						splitted_line = line.split(':')

						try: status = int(splitted_line[0])
						except: raise exceptions.LicornHarvestError('Malformed response from server.')

						if status in (LCN_MSG_STATUS_OK, LCN_MSG_STATUS_PARTIAL):
							load = float(splitted_line[1].split('=')[1])
							nrk  = float(splitted_line[2].split('=')[1])
							nrf  = float(splitted_line[3].split('=')[1])
							break

						elif status == LCN_MSG_STATUS_UNAVAIL:
							raise exceptions.LicornHarvestException("Server unavailable (%s)." % splitted_line[1])

						elif status == LCN_MSG_STATUS_ERROR:
							raise exceptions.LicornHarvestError("Server error (%s)." % splitted_line[1])

						else:
							raise exceptions.LicornHarvestError('Unknown return code from server.')

					else:
						line += buf

				except socket.error, e:
					if e[0] == 11:
						assert logging.debug("%s: socket is slow, waiting a bit…" % self.__class__)
						time.sleep(0.01)
					else:
						raise exceptions.LicornHarvestError('Socket error %s.' % e)

		except Exception, e:
			raise exceptions.LicornHarvestError(str(e))

		return (status, load, nrk, nrf)
	def UpdateRequest(self, path):

		status       = LCN_MSG_STATUS_OK
		line         = ''

		# speedup
		s = self.socket

		try:
			s.send("%s:%s:\n" % (LCN_MSG_CMD_UPDATE, path))

			while True:
				try:
					buf = s.recv(1)
					if buf == '\n':
						splitted_line = line.split(':')

						try: status = int(splitted_line[0])
						except: raise exceptions.LicornHarvestError('Malformed response from server.')

						if status in (LCN_MSG_STATUS_OK, LCN_MSG_STATUS_PARTIAL):
							# in update mode, server only answers ok|partial|error, nothing more.
							break

						elif status == LCN_MSG_STATUS_UNAVAIL:
							raise exceptions.LicornHarvestException("Server unavailable (%s)." % splitted_line[1])

						elif status == LCN_MSG_STATUS_ERROR:
							raise exceptions.LicornHarvestError("Server error (%s)." % splitted_line[1])

						else:
							raise exceptions.LicornHarvestError('Unknown return code from server.')

					else:
						line += buf
				except socket.error, e:
					if e[0] == 11:
						assert logging.debug("%s: socket is slow, waiting a bit…" % self.__class__)
						time.sleep(0.005)
					else:
						raise exceptions.LicornHarvestError('Socket error (%s).' % e)

		except Exception, e:
			raise exceptions.LicornHarvestError(str(e))

		return status
	def KeywordQueryRequest(self, keywords):

		if keywords == []:
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

		try:
			s.send("%s:%s:\n" % (LCN_MSG_CMD_QUERY, ','.join(keywords)))

			while True:
				try:
					buf = s.recv(1)
					if buf == '\n':
						if sta_not_recv:
							splitted_line = line.split(':')

							try: status = int(splitted_line[0])
							except: raise exceptions.LicornHarvestError('Malformed response from server.')

							if status in (LCN_MSG_STATUS_OK, LCN_MSG_STATUS_PARTIAL):
								nr = int(splitted_line[1])

							elif status == LCN_MSG_STATUS_UNAVAIL:
								raise exceptions.LicornHarvestException("Server unavailable (%s)." % splitted_line[1])

							elif status == LCN_MSG_STATUS_ERROR:
								raise exceptions.LicornHarvestError("Server error (%s)." % splitted_line[1])

							else:
								raise exceptions.LicornHarvestError('Unknown return code from server.')

							sta_not_recv = False
							if nr == 0: break

						else: # status line has already been received.
							res_count += 1
							files.append(line)
							if res_count == nr: break

						line = ''
					else:
						line += buf

				except socket.error, e:
					if e[0] == 11:
						time.sleep(0.05)
					else:
						raise exceptions.LicornHarvestError('Socket error (%s).' % e)

		except Exception, e:
			raise exceptions.LicornHarvestError(str(e))

		return (status, nr, files)

# FIXME: convert this to LicornThread.
class FileSearchServer(Thread):
	""" Thread which answers to file/tag queries sent through unix socket. """
	def __init__(self, pname = dname):

		Thread.__init__(self)

		self.name = "%s/%s" % (
			pname, str(self.__class__).rsplit('.', 1)[1].split("'")[0])

		# old socket from a crashed daemon ?
		# remove it, the ThreadingUnixStreamServer will create it.
		#if os.path.exists(socket_path): os.unlink(socket_path)

		self._stop_event = Event()
		self.server     = ThreadingTCPServer(('127.0.0.1', searcher_port), FileSearchRequestHandler)
		self.server.allow_reuse_address = True

		# TODO: the socket is set to non-blocking to be able to gracefully terminate the thread,
		# but this could lead to CPU hogging problems. VERIFY THIS !!
		self.server.socket.setblocking(False)
	def run(self):
		logging.progress("%s: thread running." % (self.getName()))
		#os.chmod(socket_path, stat.S_IRUSR|stat.S_IWUSR|stat.S_IRGRP|stat.S_IWGRP|stat.S_IROTH|stat.S_IWOTH)
		while not self._stop_event.isSet():
			self.server.handle_request()
			time.sleep(0.01)
		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self):
		if not self._stop_event.isSet():
			logging.progress("%s: stopping thread." % (self.getName()))
			self._stop_event.set()
			self.server.socket.close()
			self.server.server_close()
			if os.path.exists(socket_path):
				os.unlink(socket_path)
class FileSearchRequestHandler(BaseRequestHandler):
	""" Reads commands from a socket and execute actions related to keywords cache database. """
	def findCallingUid(self):
		"""TODO: do syscalls instead of forking a netstat and a ps."""
		pid = re.findall(r'127.0.0.1:%d\s+127.0.0.1:%d\s+ESTABLISHED(\d+)/' % (self.client_address[1], searcher_port),
			os.popen2(['netstat', '-antp'])[1].read())[0]
		return os.popen2(['ps', '-p', pid, '-o', 'uid='])[1].read().strip()

	def handle(self):
		""" Handle a request from the socket. WARNING: This function is WEAK (in QUERY phase)."""

		self.name     = str(self.__class__).rsplit('.', 1)[1].split("'")[0]

		self.username = self.findCallingUid()

		logging.progress("%s: starting new session with client %s:%s (uid %s)." \
			% (self.name, self.client_address[0], self.client_address[1], styles.stylize(styles.ST_NAME, self.username)))

		buf        = ''
		line       = ''
		self.cache = Cache()

		try:
			while True:
				buf = self.request.recv(1)

				if buf == '\n':

					self.load = float(open('/proc/loadavg').read().split(' ')[0])

					if self.load > 10.0:
						logging.progress("%s: server is loaded, not handling request %s." % (self.name, styles.stylize(styles.ST_PATH, line)))
						self.request.send("%s:loaded:\n" % LCN_MSG_STATUS_UNAVAIL)
					else:

						req = line.split(':')
						logging.progress("%s: handling request %s from client %s:%s." \
							% (self.name, styles.stylize(styles.ST_PATH, req), self.client_address[0], self.client_address[1]))

						try:
							cmd = int(req[0])
							if   cmd == LCN_MSG_CMD_QUERY:
								self.HandleQueryRequest(req)
							elif cmd == LCN_MSG_CMD_UPDATE:
								self.HandleUpdateRequest(req[1])
							elif cmd == LCN_MSG_CMD_REFRESH:
								self.HandleRefreshRequest()
							elif cmd == LCN_MSG_CMD_STATUS:
								self.HandleStatusRequest()
							elif cmd == LCN_MSG_CMD_END_SESSION:
								logging.progress("%s: Ending session with client %s:%s." % (self.name, self.client_address[0], self.client_address[1]))
								self.request.send('%s:\n' % LCN_MSG_STATUS_OK)
								self.request.close()
								break
							else:
								logging.progress("%s: Unknown request command %s from client %s:%s." \
									% (self.name, styles.stylize(styles.ST_PATH, cmd), self.client_address[0], self.client_address[1]))
								self.request.send("%s:unknown_command:\n" % LCN_MSG_STATUS_ERROR)
								self.request.close()
								break
						except ValueError:
							logging.warning('%s: Malformed request command %s from client %s:%s.' \
								% (self.name, req[0], self.client_address[0], self.client_address[1]))
							self.request.send("%s:unknown_command:\n" % LCN_MSG_STATUS_ERROR)
							self.request.close()
							break

					line = ''
					logging.progress("%s: waiting for next request from client %s:%s." % (self.name, self.client_address[0], self.client_address[1]))
				else:
					line += buf

		except socket.error, e:
			raise exceptions.LicornHarvestError('Socket error %s with client %s:%s.' % (e, self.client_address[0], self.client_address[1]))
	def HandleQueryRequest(self, req):
		""" Run a keyword query against the cache and return eventual results through the socket."""

		try:
			# TODO: get authorized paths of caller (from uid and gids) then
			# if root query() without filter
			# else query() with filter

			# TODO: if Queue.notEmpty():
			#
			#if self.cache.refreshing: msg = LCN_MSG_STATUS_PARTIAL
			#else:                     msg = LCN_MSG_STATUS_OK

			assert logging.debug("%s/HandleQueryRequest(): querying cache." % self.name)

			result = self.cache.query(req[1])

			assert logging.debug("%s/HandleQueryRequest(): sending result to client." % self.name)

			self.request.send("%s:%d:\n" % (msg, len(result)))
			map(lambda x: self.request.send("%s\n" % x[0]), result)

		except sqlite.OperationalError, e:
			logging.warning('%s/HandleQueryRequest(): Database error (%s).' % (self.name, e))
			self.request.send("%s:database_error:\n" % LCN_MSG_STATUS_UNAVAIL)
	def HandleStatusRequest(self):
		""" Return som status information through the socket. """

		try:
			assert logging.debug("%s/HandleStatusRequest(): getting status from cache." % self.name)

			(knb, fnb) = self.cache.status()

			msg = '%s:load=%s:keywords=%s:files=%s:\n' % (LCN_MSG_STATUS_OK, self.load, knb, fnb)

		except sqlite.OperationalError, e:
			logging.warning('%s/HandleStatusRequest(): Database error (%s).' % (self.name, e))
			msg = '%s:load=%s:::\n' % (LCN_MSG_STATUS_PARTIAL, self.load)

		assert logging.debug("%s/HandleStatusRequest(): sending cache status." % self.name)

		self.request.send(msg)
	def HandleRefreshRequest(self):
		""" Lauch a Thread that will refresh all the database. Totally unefficient, but needed sometimes,
			Since the keywords don't affect file atime/mtime, and daemon could have missed some modifications. """

		#if refresh_lock.acquire(blocking = False):

		#	refresh = Refresher()
		#	refresh.start()

			# don't release the refresh_lock, refresher thread will do it.

		#	self.request.send("STARTED:please wait:\n")

		#else:
		#	self.request.send("UNAVAIL:locked:\n")

		pass
	def HandleUpdateRequest(self, path):
		""" Handle an update request from a client: update the cache."""

		# TODO: verify authorizations to avoid DoS.


		if os.path.exists(path):

			logging.progress("%s/HandleUpdateRequest(): updating cache for %s." % (self.name, styles.stylize(styles.ST_PATH, path)))

			# TODO: if Queue.notEmpty():
			#
			#if self.cache.refreshing: status = LCN_MSG_STATUS_PARTIAL
			#else:                     status = LCN_MSG_STATUS_OK

			# always update a dir, fsapi.minifind() will not fail if it is a file.
			self.cache.cache(path, force = True)

			logging.progress("%s: cache updated for %s, ACKing client." % (self.name, styles.stylize(styles.ST_PATH, path)))

			self.request.send('%s:\n' % status)

		else:
			logging.progress("%s/HandleUpdateRequest(): NOT updating cache for %s, path does not exist." % (self.name, styles.stylize(styles.ST_PATH, path)))
			self.request.send('%s:path_does_not_exist:\n' % (LCN_MSG_STATUS_ERROR))
