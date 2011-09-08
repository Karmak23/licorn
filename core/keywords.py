# -*- coding: utf-8 -*-
"""
Licorn core: keywords - http://docs.licorn.org/core/privileges.html

:copyright:
	* 2005-2010 Olivier Cortès <olive@deep-ocean.net>
	* partial 2007 Régis Cobrun <reg53fr@yahoo.fr>

:license: GNU GPL version 2
"""

import xattr, os.path, stat

from licorn.foundations         import exceptions, logging
from licorn.foundations         import fsapi, readers, hlstr, pyutils
from licorn.foundations.styles  import *
from licorn.foundations.ltrace  import ltrace
from licorn.foundations.ltraces import *
from licorn.foundations.base    import Singleton
from licorn.foundations.classes import FileLock

from licorn.core         import LMC
from licorn.core.classes import LockedController

class KeywordsController(Singleton, LockedController):

	init_ok = False
	load_ok = False

	def __init__(self):

		if KeywordsController.init_ok:
			return

		LockedController.__init__(self, 'keywords')

		self.keywords      = {}
		self.changed       = False
		self.licorn_xattr  = "user.Licorn.keywords"

		self.work_path     = os.getenv(
			"LICORN_KEYWORDS_PATH", LMC.configuration.groups.base_path)
		#
		# TODO: work_path could be HOME if fsapi.minifind is configured to follow symlinks, this would be
		# more optimized than to walk /home/groups (because user has small prob to be in all groups).
		#
		# TODO: implement work_path with more than one path (/home/groups:/home/olive:/data/special)
		#

		KeywordsController.init_ok = True
	def load(self):
		if KeywordsController.load_ok:
			return
		else:
			assert ltrace(TRACE_KEYWORDS, '| load()')
			self.reload()
			KeywordsController.load_ok = True
	def __getitem__(self, item):
		return self.keywords[item]
	def __setitem__(self, item, value):
		self.keywords[item]=value
	def reload(self):
		""" reload data from system files / databases. """
		assert ltrace(TRACE_KEYWORDS, '| reload()')

		self.keywords = {}

		def import_keywords(entry):
			if len(entry) == 3:
				temp_kw_dict	= {
							'name'       : entry[0],
							'parent'     : entry[1],
							'description': entry[2]
							}
				self.keywords[temp_kw_dict['name']] = temp_kw_dict

		try:
			map(import_keywords, readers.ug_conf_load_list(
				LMC.configuration.keywords_data_file))
		except IOError, e:
			if e.errno == 2:
				pass
			else:
				raise e

	def keys(self):
		return self.keywords.keys()
	def has_key(self, key):
		return self.keywords.has_key(key)
	def WriteConf(self):
		""" Write the keywords data in appropriate system files."""

		if self.changed :
			logging.progress('%s: saving data structures to disk.' % \
				self.pretty_name)

			lock_file = FileLock(LMC.configuration,
				LMC.configuration.keywords_data_file)

			lock_file.Lock()
			open(LMC.configuration.keywords_data_file , "w").write(
				self.__build_cli_output())
			lock_file.Unlock()

			logging.progress('%s: data structures saved.' % \
				self.pretty_name)

			self.changed = False
	def __build_cli_output(self):
		return '\n'.join(map(lambda x: ':'.join(
					[	self.keywords[x]['name'],
						self.keywords[x]['parent'],
						self.keywords[x]['description']
					]), self.keywords.keys())) + '\n'
	def Export(self):
		""" Export the keywords list to cli format. """
		return self.__build_cli_output()
	def ExportXML(self):
		""" Export the keywords list to Xml format."""
		def build_output(name):
			return """	<keyword>
		<name>%s</name>
		<parent>%s</parent>
		<description>%s</description>
	</keyword>""" % (self.keywords[name]['name'], self.keywords[name]['parent'], self.keywords[name]['description'])

		return """<?xml version='1.0' encoding=\"UTF-8\"?>
<keywords-list>
	%s
</keywords-list>
""" % '\n'.join(map(build_output, self.keywords.keys()))
	def AddKeyword(self, name = None, parent = "", description = ""):
		""" Add a new keyword on the system, provided some checks are OK. """
		if name is None:
			raise exceptions.BadArgumentError(
						_(u'You must specify a keyword name.'))

		if name in self.keywords.keys():
			raise exceptions.AlreadyExistsException(
				"A keyword named « %s » already exists !" % name)

		if parent != "":
			if parent not in self.keywords.keys():
				raise exceptions.BadArgumentError(
					"The parent you specified doesn't exist on this system.")

		if not hlstr.cregex['keyword'].match(name):
			raise exceptions.BadArgumentError(
				_(u'Malformed keyword name "{0}", must match /{1}/i.').format(
					stylize(ST_NAME, name),
					stylize(ST_REGEX, hlstr.regex['keyword'])))

		if not hlstr.cregex['description'].match(description):
			raise exceptions.BadArgumentError(_(u'Malformed keyword '
				'description "{0}", must match /{1}/i.').format(
				stylize(ST_COMMENT, description),
				stylize(ST_REGEX, hlstr.regex['description'])))

		self.keywords[name] = {
			'name': name,
			'parent': parent,
			'description': description
			}

		logging.info('Added keyword %s.' % name)
		self.changed = True
		self.WriteConf()
	def DeleteKeyword(self, name=None, del_children=False, modify_file=True):
		""" Delete a keyword
		"""
		if name is None:
			raise exceptions.BadArgumentError(logging.SYSK_SPECIFY_KEYWORD)

		try:
			children = self.Children(name)
			if children != []:
				if del_children:
					for child in children:
						del(self.keywords[child])
				else:
					raise exceptions.LicornException('''The keyword is a '''
						'''parent which has children. If you want to delete '''
						'''children too, use option --del-children''')
			del(self.keywords[name])

			logging.info('Deleted keyword %s.' % name)
			self.changed = True
			self.WriteConf()

			if modify_file:
				# TODO: affine the path
				self.DeleteKeywordsFromPath(self.work_path, [name],
					recursive=True)
		except KeyError:
			raise exceptions.BadArgumentError(
				"The keyword you specified doesn't exist on this system.")

	def __has_no_parent(self, name):
		""" Has'nt the keyword a parent ? """
		return self.keywords[name]['parent'] == ""
	def Children(self, name):
		""" Give the children of a parent """
		children = []
		for k in self.keywords:
			if self.keywords[k]['parent'] == name:
				children.append(k)
		return children
	def RenameKeyword(self, name, newname):
		""" Rename a keyword (parent or not) """
		def __rename_keyword_from_path(file_path):
			actual_kw = []
			try:
				actual_kw = xattr.getxattr(file_path,
					self.licorn_xattr).split(',')
			except IOError, e:
				if e.errno == 61:
					# No data available (ie self.licorn_xattr is not created)
					pass
				else: raise e
			try:
				i = actual_kw.index(name)
			except ValueError: pass
			else:
				actual_kw[i] = newname
			try:
				xattr.setxattr(file_path, self.licorn_xattr,
					','.join(actual_kw))
			except IOError, e:
				if e.errno == 1:
					# Operation not permitted
					pass
		try:
			self.AddKeyword(newname,
				description=self.keywords[name]['description'])
			for child in self.Children(name):
				self.keywords[child]["parent"] = newname

			# TODO: affine path
			map(
				lambda x: __rename_keyword_from_path(x),
				 fsapi.minifind(self.work_path, type = stat.S_IFREG) )
			self.DeleteKeyword(name, del_children=True, modify_file=False)
			self.WriteConf()
		except KeyError:
			raise exceptions.BadArgumentError(
				"The keyword you specified doesn't exist on this system.")
	def ChangeParent(self, name, parent):
		""" Change keyword's parent """
		try:
			self.keywords[parent]
			self.keywords[name]["parent"] = parent
		except KeyError, e:
			raise exceptions.BadArgumentError(
				"The keyword %s doesn't exist on this system." % str(e))
		self.changed = True
	def RemoveParent(self, name):
		""" Remove parent of the keyword 'name' """
		try:
			self.keywords[name]["parent"] = ""
		except KeyError:
			raise exceptions.BadArgumentError(
				"The keyword you specified doesn't exist on this system.")
		self.changed = True
	def ChangeDescription(self, name, description):
		""" Change the description of a keyword """
		try:
			self.keywords[name]["description"] = description
		except KeyError:
			raise exceptions.BadArgumentError(
				"The keyword you specified doesn't exist on this system.")
		self.changed = True
	def __remove_bad_keywords(self, keywords_list):
		""" Remove parent and inexistant keywords """
		good_keywords = []
		for k in keywords_list:
			try:
				self.keywords[k]
			except KeyError:
				# not a valid keyword, skipped
				continue
			try:
				if self.__has_no_parent(k):
					# root keyword (has no parent), skipped
					continue
			except: pass
			good_keywords.append(k)
		return good_keywords
	def AddKeywordsToPath(self, path, keywords_to_add, recursive=False):
		""" Add keywords to a file or directory files
		"""
		def __add_keywords_to_file(file_path):
			actual_kw = []
			try:
				actual_kw = xattr.getxattr(file_path,
					self.licorn_xattr).split(',')
			except IOError, e:
				if e.errno in (61, 95):
					# No data available (ie self.licorn_xattr is not created) or
					# attr not supported (FS not mounted with user_xattr option)
					logging.warning2('''Can't get current keywords.''',
					once=True)
				else:
					raise e
			keywords_to_add_tmp = list(keywords_to_add)
			keywords_to_add_tmp.extend(actual_kw)
			keywords_to_set = pyutils.list2set(keywords_to_add_tmp)
			try:
				attr = ','.join(self.__remove_bad_keywords(keywords_to_set))
				xattr.setxattr(file_path, self.licorn_xattr, attr)
				logging.info("Applyed %s xattr %s on %s." % (
					stylize(ST_NAME, self.licorn_xattr),
					stylize(ST_ACL, attr),
					stylize(ST_PATH, file_path)))
			except IOError, e:
				if e.errno is (1, 95): # Operation not permitted / not supported
					logging.warning2(
						"Unable to modify %s xattr of %s (was: %s)." % (
						stylize(ST_NAME, self.licorn_xattr),
						stylize(ST_PATH, file_path), e))
				else:
					raise e

		# file case
		if os.path.isfile(path):
			__add_keywords_to_file(path)

		# dir case
		else:
			if recursive: max = 99
			else:         max = 1
			map(lambda x: __add_keywords_to_file(x),
				 fsapi.minifind(path, maxdepth=max, type = stat.S_IFREG))
	def DeleteKeywordsFromPath(self, path, keywords_to_del, recursive=False):
		""" Delete keywords from a file or directory files
		"""
		def __delete_keywords_from_file(file_path):
			actual_kw = []
			try:
				actual_kw = xattr.getxattr(file_path,
					self.licorn_xattr).split(',')
			except IOError, e:
				if e.errno in (61, 95):
					# No data available (ie self.licorn_xattr is not created)
					# or Operation not supported (partition is not mounted
					# with user_xattr option).
					logging.warning2('''Can't get current keywords.''',
					once=True)
					pass
				else: raise e
			keywords_to_set = []
			for k in actual_kw:
				if k not in keywords_to_del:
					keywords_to_set.append(k)
			try:
				if keywords_to_set == []:
					xattr.removexattr(file_path, self.licorn_xattr)
					logging.info("Removed xattr %s from %s." % (
						stylize(ST_NAME, self.licorn_xattr),
						stylize(ST_PATH, file_path)))
				else:
					attr = ','.join(self.__remove_bad_keywords(keywords_to_set))
					xattr.setxattr(file_path, self.licorn_xattr, attr)
					logging.info("Applyed %s xattr %s on %s." % (
						stylize(ST_NAME, self.licorn_xattr),
							stylize(ST_ACL, attr),
							stylize(ST_PATH, file_path)))
			except IOError, e:
				if e.errno in (1, 95): # Operation not permitted / not supported
					logging.warning(
						"Unable to modify %s xattr of %s (was: %s)." % (
							stylize(ST_NAME, self.licorn_xattr),
							stylize(ST_PATH, file_path), e))
				else:
					raise e

		# file case
		if os.path.isfile(path):
			__delete_keywords_from_file(path)

		# directory case
		else:
			if recursive: max = 99
			else:         max = 1

			# TODO: if fsapi.minifind is not configured for cross-mount finding,
			# skip related files if mount point is not mounted with user_xattr.

			map(lambda x: __delete_keywords_from_file(x),
				 fsapi.minifind(path, maxdepth=max, type = stat.S_IFREG))
	def ClearKeywords(self, path, recursive=False):
		""" Delete all keywords from a file or directory files
		"""
		# file case
		if os.path.isfile(path):
			logging.info("remove xattr from %s." %
				stylize(ST_PATH, path))
			xattr.setxattr(path, self.licorn_xattr, "")

		# dir case
		else:
			if recursive: max = 99
			else:         max = 1
			map(lambda x: xattr.setxattr(x, self.licorn_xattr, ""),
				 fsapi.minifind(path, maxdepth=max, type = stat.S_IFREG))
	def GetKeywordsFromPath(self, path):
		""" get user_xattr keywords from a given path. """
		return xattr.getxattr(path, self.licorn_xattr).split(',')
	def SearchPathWithKeywords(self, search_dict):
		""" search_dict {parent: [child_keywords]}
			return list of path which matche with search criteria
		"""
		if search_dict == {}:
			return []
		def search(path):
			""" Determine if the path corresponds to the criteria """
			file_kw = None
			try:
				file_kw = self.GetKeywordsFromPath(path)
			except (IOError,OSError), e:
				if e.errno in (13,61):
					return False

			for parent in search_dict:
				bool = False
				for k in search_dict[parent]:
					bool |= k in file_kw
				if not bool:
					return False
			return True

		# TODO: affine the path
		paths = filter(
			search,
			fsapi.minifind(self.work_path, type = stat.S_IFREG)
			)
		return paths
