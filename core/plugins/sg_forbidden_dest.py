# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2006 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Jérémy Milhau "Luka" <jeremilhau@gmail.com>
Licensed under the terms of the GNU GPL version 2

"""

import re, sys, urlparse

from licorn.foundations    import exceptions, readers
from licorn.core           import configuration

_sysConfig = configuration

class ForbiddenDestList:
	forbidden_dest_dict = {}
	def __init__(self):
		self.forbidden_dest_dict["blacklist"] = {
													'urls': readers.very_simple_conf_load_list(_sysConfig.mSquidGuard['BLACKLIST_URLS']),
													'domains': readers.very_simple_conf_load_list(_sysConfig.mSquidGuard['BLACKLIST_DOMAINS'])
												}
		self.forbidden_dest_dict["whitelist"] = {
													'urls': readers.very_simple_conf_load_list(_sysConfig.mSquidGuard['WHITELIST_URLS']),
													'domains': readers.very_simple_conf_load_list(_sysConfig.mSquidGuard['WHITELIST_DOMAINS'])
												}
		self.forbidden_dest_dict["mode"] = self.__get_mode()
	def __is_a_valid_address(self, address):
		""" Return True if 'address' doesn't contain any space or //
		"""
		if address.find(' ') != -1 or address.find('//') != -1 or address == "":
			return False
		return True
	def __is_domain_or_url(self, address):
		""" Return "url" if address is an url
			Return "domain" if address is a domain
		"""
		slash_re = re.compile("/*")
		
		split_addr = urlparse(address)
		
		if slash_re.match(split_addr[2]) is not None:
			return "domain"
		return "url"
	def Export(self, listcolor, urls_or_domains, doreturn=True):
		""" Display the domains and urls list (in a normal output)
		"""
		data = "\n".join(self.forbidden_dest_dict[listcolor][urls_or_domains])
		if doreturn:
			return data
		else:
			sys.stdout.write( data )
	def ExportXML(self, listcolor, urls_or_domains, doreturn=True):
		""" Display the domains and urls list (in a XML output)
		"""
		data = ""
		data += "	<" + urls_or_domains + ">\n"
		for a in self.forbidden_dest_dict[listcolor][urls_or_domains]:
			data += "		<address>" + a + "</address>\n"
		data += "	</" + urls_or_domains + ">\n"
		
		if doreturn:
			return data
		else:
			sys.stdout.write( data )
	def ModifyAddress(self, listcolor, oldaddress, newaddress):
		""" Replace 'oldaddress' with 'newaddress' if 'oldaddress' is found in one of two custom lists
		"""
		self.DeleteAddress(listcolor, oldaddress)
		self.AddAddress(listcolor, newaddress)
	def AddAddress(self, listcolor, address):
		""" Add a domain or an URL. This function make the difference and put the 'address' in the correct list
		"""
		if not self.__is_a_valid_address(address):
			raise exceptions.BadArgumentError, "'" + address + "' is not a valid address"

		# Domain or URL ?
		addr_type = self.__is_domain_or_url(address)

		if addr_type == "url":
			address = str(urlparse(address)[1:2])
		else:
			address = str(urlparse(address)[1])

		# Does this address exist yet ?
		if address in self.forbidden_dest_dict[listcolor][addr_type]:
			raise exceptions.BadArgumentError, "'" + address + "' already exists in forbidden destination list. Unable to add"
		else:
			self.forbidden_dest_dict[listcolor][addr_type].append(address)
	def DeleteAddress(self, listcolor, address):
		""" Delete a domain or an URL
		"""
		#address = clean_address(address)
		if not self.__is_a_valid_address(address):
			raise exceptions.BadArgumentError #print "'" + address + "' is not a valid address"

		# Domain or URL ?
		addr_type = self.__is_domain_or_url(address)

		index = self.forbidden_dest_dict[listcolor][addr_type].index(address)
		del(self.forbidden_dest_dict[listcolor][addr_type][index])
	def SetRedirection(self, url):
		""" Change the url redirection of the acl rule 'default' which stops all forbidden destinations
		"""
		#
		# FIXME: implement this function
		#
		pass
	def GetRedirection(self):
		""" Display the url redirection of the acl rule 'default' which stops all forbidden destinations
		"""
		#
		# FIXME: implement this function
		#
		pass
	def ChangeListMode(self):
		""" Change the filter mode (blacklist or whitelist)
		"""
		if self.forbidden_dest_dict["mode"] == "whitelist":
			self.forbidden_dest_dict["mode"] = "blacklist"
		else:
			self.forbidden_dest_dict["mode"] = "whitelist"
		#
		# FIXME: implement this function
		#
	def __get_mode(self):
		""" Get the active mode (blacklist or whitelist)
		"""
		conffile = open(_sysConfig.mSquidGuard['CONF'], 'r')
		conflines = conffile.readlines()
		
		# Search default acl
		default_re = re.compile("\s*default\s*{")
		i = 0 # index of default {
		for line in conflines:
			if default_re.match(line):
				break
			i += 1
		
		# Search whitelist mark
		re_white = re.compile("\s*pass .* none")
		for line in conflines[i:]:
			# Is it the white line ?
			bmtch = re_white.match(line)
			if bmtch is not None:
				return "whitelist"
		
		return "blacklist"
