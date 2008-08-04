
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
class INotifier_gamin(Thread):
	""" A Thread which collect INotify events and does what is appropriate with them. """
	def __init__(self, cache, pname = '<unknown>') :

		self.name  = str(self.__class__).rsplit('.', 1)[1].split("'")[0]
		Thread.__init__(self, name = "%s/%s" % (pname, self.name))

		self.cache        = cache
		self.mon          = gamin.WatchMonitor()


		# keep track of watched directories, and func prototypes used 
		# to chk the data inside. this will avoid massive CPU usage, 
		# at the cost of a python dict.
		self.wds          = []

		# this list will record if a dir/file has just been checked.
		# because chk'ing the path will generate an GAMChanged event,
		# and we don't wan't the file/dir to be checked twice.
		self.just_checked = []

		from licorn.core import groups
		groups.Select(groups.FILTER_STANDARD)
		self.groups = groups

		#self.mon.no_exists()

		for gid in groups.filtered_groups :

			if groups.groups[gid]['name'] in ('Meta', 'meta-rss', 'meta-project', 'Licorn') :
				continue

			group_home = "%s/%s/%s" % (groups.configuration.defaults.home_base_path,
							groups.configuration.groups.names['plural'], groups.groups[gid]['name'])

			def myfunc(path, event, gid = gid, dirname = group_home) :
				return self.process_event(path, event, gid, dirname)

			self.add_watch(group_home, myfunc)
	def process_event(self, basename, event, gid, dirname):
		""" Process Gamin events and apply ACLs on the fly. """

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

		if event in (gamin.GAMExists, gamin.GAMCreated) :

			logging.progress("%s: Inotify %s %s." %  (self.getName(), styles.stylize(styles.ST_MODE, 'GAMExists/GAMCreated'), path))

			#acl = self.groups.BuildGroupACL(gid, path[len(dirname):])

			try :
				if os.path.isdir(path) :
					# add a watch, with the func of the parent dir.
					def myfunc(path, event, gid = gid, dirname = path) :
						return self.process_event(path, event, gid, dirname)
					self.add_watch(path, myfunc)

					#fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl') , -1)
					#fsapi.auto_check_posix1e_acl(path, False, acl['default_acl'], acl['default_acl'])
						

				else :
					pass
					#fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl'))
					#fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')

			except (OSError, IOError), e :
				if e.errno != 2 :
					logging.warning("%s: problem in GAMCreated on %s (was: %s, event=%s)." % (self.getName(), path, e, event))

			self.cache.cache(path)

		elif event == gamin.GAMChanged :

			if path in self.just_checked :
				# skip the first GAMChanged event, it was generated
				# by the CHK in the GAMCreated part.
				self.just_checked.remove(path)
				return

			logging.progress("%s: Inotify %s on %s." %  (self.getName(),
				styles.stylize(styles.ST_URL, 'GAMChanged'), path))
			return

			acl = self.groups.BuildGroupACL(gid, path[len(dirname):])

			try :
				# 2 times, because 2 system calls imply 2 GAM events
				self.just_checked.append(path)
				self.just_checked.append(path)

				if os.path.isdir(path) :
					fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl') , -1)
					fsapi.auto_check_posix1e_acl(path, False, acl['default_acl'], acl['default_acl'])

				elif os.path.isfile(path) :
					fsapi.auto_check_posix_ugid_and_perms(path, -1, self.groups.name_to_gid('acl'))
					fsapi.auto_check_posix1e_acl(path, True, acl['content_acl'], '')

			except (OSError, IOError), e :
					if e.errno != 2 :
						logging.warning("%s: problem in GAMChanged() on %s (was: %s, event=%s)." % (self.getName(), path, e, event))

			# update cached entries.
			self.cache.cache(path)

		elif event == gamin.GAMMoved :

			logging.progress('%s: Inotify %s, not handled yet %s.' % (self.getName(), 
				styles.stylize(styles.ST_PKGNAME, 'GAMMoved'), styles.stylize(styles.ST_PATH, path)))

		elif event == gamin.GAMDeleted :
			# if a dir is deleted, we will get 2 GAMDeleted events: 
			#  - one for the dir watched (itself deleted)
			#  - one for its parent, signaling its child was deleted.

			logging.progress("%s: Inotify %s for %s." %  (self.getName(), 
				styles.stylize(styles.ST_BAD, 'GAMDeleted'), styles.stylize(styles.ST_PATH, path)))
			return

			# we can't test if the “path” was a dir, it has just been deleted
			# just try to delete it, wait and see. If it was, this will work.
			self.remove_watch(path)

			# TODO: remove recursively if DIR.
			self.cache.removeEntry(path)

		elif event in (gamin.GAMEndExist, gamin.GAMAcknowledge) :
			pass

		else :
			logging.progress('%s: unhandled Inotify event “%s” %s.' % (self.getName(), event, path))

		# just for debug
		#logging.notice(self.wds)
	def add_watch(self, path, func) :
		logging.progress("%s: %s inotify watch for %s." % (self.getName(), styles.stylize(styles.ST_OK, 'adding'), styles.stylize(styles.ST_PATH, path)))

		if path in self.wds :
			return 0

		self.wds.append(path)
		return self.mon.watch_directory(path, func)
	def remove_watch(self, path) :

		if path in self.wds :
			logging.progress("%s: %s inotify watch for %s." % (self.getName(), 
				styles.stylize(styles.ST_BAD, 'removing'), styles.stylize(styles.ST_PATH, path)))

			# TODO: recurse subdirs if existing, to remove subwatches

			self.wds.remove(path)
			return self.mon.stop_watch(path) 

		return 0
	def run(self) :
		logging.progress("%s: thread running." % (self.getName()))
		Thread.run(self)

		try :
			while True :
				self.mon.handle_events()
				time.sleep(0.1)
		except AttributeError, e :
			# thread has stopped, self.mon does not exists anymore
			pass
		logging.progress("%s: thread ended." % (self.getName()))
	def stop(self) :
		if Thread.isAlive(self) :
			logging.progress("%s: stopping thread." % (self.getName()))
			try :
				for group in self.wds :
					self.mon.stop_watch(group)

				del self.mon
			except Exception, e :
				logging.warning('%s: Exception when stopping: %s' % (self.getName(), e))
class INotifier_pyinotify(ThreadedNotifier):
	""" A Thread which collect INotify events and does what is appropriate with them. """
	def __init__(self, cache, pname = '<unknown>') :

		self.cache = cache

		# needed to watch a bunch of dirs/files
		inotify.max_user_watches.value = 65535

		self.wm = WatchManager()

		self.name = str(self.__class__).rsplit('.', 1)[1].split("'")[0]

		ThreadedNotifier.__init__(self, self.wm, logging.notice)
		self.setName("%s/%s" % (pname, self.name))   # can't be passed as argument when instanciating.

		logging.info('%s: set inotify max user watches to %d.' % (self.getName(), inotify.max_user_watches.value))

		self.mask = EventsCodes.IN_CLOSE_WRITE | EventsCodes.IN_CREATE \
			| EventsCodes.IN_MOVED_TO | EventsCodes.IN_MOVED_FROM | EventsCodes.IN_DELETE

		from licorn.core import groups
		groups.Select(groups.FILTER_STANDARD)
			
		for gid in groups.filtered_groups :
			group_home = "%s/%s/%s" % (groups.configuration.defaults.home_base_path,
							groups.configuration.groups.names['plural'], groups.groups[gid]['name'])
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
