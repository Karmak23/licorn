# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2007 Olivier Cortès <oc@5sys.fr>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""

import xattr, os.path, stat

from licorn.foundations    import exceptions, logging, hlstr, pyutils, file_locks
from licorn.core.internals import readers


class KeywordsList :
	
	keywords = {}
	configuration = None
	licorn_xattr = "user.Licorn.keywords"
	work_path = None
	
	def __init__(self, configuration) :
		
		self.configuration = configuration
		self.work_path     = os.getenv("LICORN_KEYWORDS_PATH", "/home/%s" % configuration.groups.names['plural'])
		#
		# TODO : work_path could be HOME if fsapi.minifind is configured to follow symlinks, this would be
		# more optimized than to walk /home/groups (because user has small prob to be in all groups).
		# 
		# TODO : implement work_path with more than one path (/home/groups:/home/olive:/data/special)
		#
		
		def import_keywords(entry) :
			if len(entry) == 3 :
				temp_kw_dict	= {
							'name'         : entry[0],
							'parent'       : entry[1],
							'description'  : entry[2]
							}
				self.keywords[temp_kw_dict['name']] = temp_kw_dict
			
		try:
			map(import_keywords, readers.ug_conf_load_list(configuration.keywords_data_file))
		except IOError, e :
			if e.errno == 2 :
				pass
			else : 
				raise e
	def WriteConf(self) :
		""" Write the keywords data in appropriate system files.""" 
		lock_file = file_locks.FileLock(self.configuration, self.configuration.keywords_data_file)

		lock_file.Lock()
		open(self.configuration.keywords_data_file , "w").write(self.__build_cli_output())
		lock_file.Unlock()
	def __build_cli_output(self) :
		return '\n'.join(map(lambda x: ':'.join(
					[	self.keywords[x]['name'],
						self.keywords[x]['parent'],
						self.keywords[x]['description']
					]), self.keywords.keys())) + '\n'
	def Export(self) :
		""" Export the keywords list to cli format. """
		return self.__build_cli_output()
	def ExportXML(self) :
		""" Export the keywords list to Xml format."""
		def build_output(name) :
			return """	<keyword>
		<name>%s</name>
		<parent>%s</parent>
		<description>%s</description>
	</keyword>""" % (self.keywords[name]['name'], self.keywords[name]['parent'], self.keywords[name]['description'])
			
		return """<?xml version='1.0' encoding=\"UTF-8\"?>
<keywords-list>
	%s
</keywords-list>
""" % '\n'.join(map(build_output,self.keywords.keys()))
	def AddKeyword(self, name = None, parent = "", description = "") :
		""" Add a new keyword on the system, provided some checks are OK. """
		if name is None :
			raise exceptions.BadArgumentError(logging.SYSK_SPECIFY_KEYWORD)
		
		if name in self.keywords.keys() :
			raise exceptions.AlreadyExistsException, "A keyword named « %s » already exists !" % name
			
		if parent != "" :
			if parent not in self.keywords.keys() :
				raise exceptions.BadArgumentError("The parent you specified doesn't exist on this system.")

		from licorn import system as hzsys

		if not hlstr.cregex['keyword'].match(name) :
			raise exceptions.BadArgumentError(logging.SYSK_MALFORMED_KEYWORD % (name, styles.stylize(styles.ST_REGEX, hlstr.regex['keyword'])))

		if not hlstr.cregex['description'].match(description) :
			raise exceptions.BadArgumentError, SYSK_MALFORMED_DESCR % (description, styles.stylize(styles.ST_REGEX, hlstr.regex['description']))

		self.keywords[name] = { 'name' : name, 'parent' : parent, 'description' : description }
		self.WriteConf()
	def DeleteKeyword(self, name=None, del_children=False, modify_file=True) :
		"""
		"""
		if name is None :
			raise exceptions.BadArgumentError(logging.SYSK_SPECIFY_KEYWORD)
		
		try :
			children = self.Children(name)
			if children != [] :
				if del_children :
					for child in children :
						del(self.keywords[child])
				else :
					raise exceptions.LicornException("The keyword is a parent which has children. If you want to delete children too, use option --del-children")
			del(self.keywords[name])
			
			if modify_file :
				# TODO : affine the path
				self.DeleteKeywordsFromPath(self.work_path, [name], recursive=True)
		except KeyError :
			raise exceptions.BadArgumentError("The keyword you specified doesn't exist on this system.")
		else :
			self.WriteConf()
	def __has_no_parent(self, name) :
		""" Has'nt the keyword a parent ? """
		return self.keywords[name]['parent'] == ""
	def Children(self, name) :
		""" Give the children of a parent """
		children = []
		for k in self.keywords :
			if self.keywords[k]['parent'] == name :
				children.append(k)
		return children
	def RenameKeyword(self, name, newname) :
		""" Rename a keyword (parent or not) """
		def __rename_keyword_from_path(file_path) :
			actual_kw = []
			try :
				actual_kw = xattr.getxattr(file_path, self.licorn_xattr).split(',')
			except IOError, e :
				if e.errno == 61 : # No data available (ie self.licorn_xattr is not created)
					pass
				else : raise e
			try :
				i = actual_kw.index(name)
			except ValueError : pass
			else :
				actual_kw[i] = newname
			try :
				xattr.setxattr(file_path, self.licorn_xattr, ','.join(actual_kw))
			except IOError, e:
				if e.errno == 1 : # Operation not permitted
					pass
		try :
			self.AddKeyword(newname, description=self.keywords[name]['description'])
			for child in self.Children(name) :
				self.keywords[child]["parent"] = newname

			# TODO : affine path
			map(
				lambda x: __rename_keyword_from_path(x),
				 fsapi.minifind(self.work_path, type = stat.S_IFREG) )
			self.DeleteKeyword(name, del_children=True, modify_file=False)
		except KeyError :
			raise exceptions.BadArgumentError("The keyword you specified doesn't exist on this system.")
	def ChangeParent(self, name, parent) :
		""" Change keyword's parent """
		try :
			self.keywords[parent]
			self.keywords[name]["parent"] = parent
		except KeyError, e :
			raise exceptions.BadArgumentError("The keyword %s doesn't exist on this system." % str(e))
		self.WriteConf()
	def RemoveParent(self, name) :
		""" Remove parent of the keyword 'name' """
		try :
			self.keywords[name]["parent"] = ""
		except KeyError, e :
			raise exceptions.BadArgumentError("The keyword you specified doesn't exist on this system.")
		self.WriteConf()
	def ChangeDescription(self, name, description) :
		""" Change the description of a keyword """
		try :
			self.keywords[name]["description"] = description
		except KeyError, e :
			raise exceptions.BadArgumentError("The keyword you specified doesn't exist on this system.")
		self.WriteConf()
	def __remove_bad_keywords(self, keywords_list) :
		""" Remove parent and inexistant keywords """
		good_keywords = []
		for k in keywords_list :
			try :
				self.keywords[k]
			except KeyError :
				# not a valid keyword, skipped
				continue
			try :
				if self.__has_no_parent(k) :
					# root keyword (has no parent), skipped
					continue
			except : pass
			good_keywords.append(k)
		return good_keywords
	def AddKeywordsToPath(self, path, keywords_to_add, recursive=False) :
		""" Add keywords to a file or directory files
		"""
		def __add_keywords_to_file(file_path) :
			actual_kw = []
			try :
				actual_kw = xattr.getxattr(file_path, self.licorn_xattr).split(',')
			except IOError, e :
				if e.errno in (61, 95) : # No data available (ie self.licorn_xattr is not created) / not supported
					pass
				else : raise e
			keywords_to_add_tmp = list(keywords_to_add)
			keywords_to_add_tmp.extend(actual_kw)
			keywords_to_set = pyutils.list2set(keywords_to_add_tmp)
			try :
				attr = ','.join(self.__remove_bad_keywords(keywords_to_set))
				xattr.setxattr(file_path, self.licorn_xattr, attr)
				logging.info("Applyed %s xattr %s on %s." % (styles.stylize(styles.ST_NAME, self.licorn_xattr), styles.stylize(styles.ST_ACL, attr), styles.stylize(styles.ST_PATH, file_path)))
			except IOError, e:
				if e.errno is (1, 95) : # Operation not permitted / not supported
					logging.warning("Unable to modify %s xattr of %s (was: %s)." % (styles.stylize(styles.ST_NAME, self.licorn_xattr), styles.stylize(styles.ST_PATH, file_path), e))
				else :
					raise e
					
		# file case
		if os.path.isfile(path) :
			__add_keywords_to_file(path)
			
		# dir case
		else :
			if recursive : max = 99
			else :         max = 1
			map(
				lambda x: __add_keywords_to_file(x),
				 fsapi.minifind(path, maxdepth=max, type = stat.S_IFREG) )
	def DeleteKeywordsFromPath(self, path, keywords_to_del, recursive=False) :
		""" Delete keywords from a file or directory files
		"""	
		def __delete_keywords_from_file(file_path) :
			actual_kw = []
			try :
				actual_kw = xattr.getxattr(file_path, self.licorn_xattr).split(',')
			except IOError, e :
				if e.errno in (61, 95) :
					# No data available (ie self.licorn_xattr is not created)
					# or Operation not supported (partition is not mounted with user_xattr)
					pass
				else : raise e
			keywords_to_set = []
			for k in actual_kw :
				if k not in keywords_to_del :
					keywords_to_set.append(k)
			try :
				if keywords_to_set == [] :
					xattr.removexattr(file_path, self.licorn_xattr)
					logging.info("Removed xattr %s from %s." % (styles.stylize(styles.ST_NAME, self.licorn_xattr), styles.stylize(styles.ST_PATH, file_path)))
				else :
					attr = ','.join(self.__remove_bad_keywords(keywords_to_set))
					xattr.setxattr(file_path, self.licorn_xattr, attr)
					logging.info("Applyed %s xattr %s on %s." % (styles.stylize(styles.ST_NAME, self.licorn_xattr), styles.stylize(styles.ST_ACL, attr), styles.stylize(styles.ST_PATH, file_path)))
			except IOError, e :
				if e.errno in (1, 95) : # Operation not permitted / not supported
					logging.warning("Unable to modify %s xattr of %s (was: %s)." % (styles.stylize(styles.ST_NAME, self.licorn_xattr), styles.stylize(styles.ST_PATH, file_path), e))
				else :
					raise e
			
		# file case
		if os.path.isfile(path) :
			__delete_keywords_from_file(path)
			
		# dir case
		else :
			if recursive : max = 99
			else :         max = 1

			#
			# TODO : if fsapi.minifind is not configured for cross-mount finding,
			# skip appropriate files if mount point is not mounted with user_xattr.
			#

			map(
				lambda x: __delete_keywords_from_file(x),
				 fsapi.minifind(path, maxdepth=max, type = stat.S_IFREG) )
	def ClearKeywords(self, path, recursive=False) :
		""" Delete all keywords from a file or directory files
		"""
		# file case
		if os.path.isfile(path) :
			logging.info("remove xattr from %s." % styles.stylize(styles.ST_PATH, path))
			xattr.setxattr(path, self.licorn_xattr, "")
			
		# dir case
		else :
			if recursive : max = 99
			else :         max = 1
			map(
				lambda x: xattr.setxattr(x, self.licorn_xattr, ""),
				 fsapi.minifind(path, maxdepth=max, type = stat.S_IFREG) )
	def GetKeywordsFromPath(self, path) :
		"""
		"""
		return xattr.getxattr(path, self.licorn_xattr).split(',')
	def SearchPathWithKeywords(self, search_dict) :
		""" search_dict {parent : [child_keywords]}
			return list of path which matche with search criteria
		"""
		if search_dict == {} :
			return []
		def search(path) :
			""" Determine if the path corresponds to the criteria """
			file_kw = None
			try :
				file_kw = self.GetKeywordsFromPath(path)
			except (IOError,OSError), e :
				if e.errno in (13,61) :
					return False
					
			for parent in search_dict :
				bool = False
				for k in search_dict[parent] :
					bool |= k in file_kw
				if not bool :
					return False
			return True
		
		# TODO : affine the path
		paths = filter(
			search,
			fsapi.minifind(self.work_path, type = stat.S_IFREG)
			)
		return paths
