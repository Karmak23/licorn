# -*- coding: utf-8 -*-
"""
Licorn Foundations LDAP small objects.

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2.
"""

import os, ldap
import string
from ldif import LDIFParser

def list_dict(l):
	"""
	return a dictionary with all items of l being the keys of the dictionary
	"""
	d = {}
	for i in l:
		d[i]=None
	return d
def addModlist(entry, ignore_attr_types=None):
	"""Build modify list for call of method LDAPObject.add().

	This is rougly a copy of ldap.modlist.addModlist() version 2.3.10,
	modified to handle non iterable attributes. This is to avoid parsing our
	entries twice (once for creating iterable attributes, once for addModlist).
	"""
	ignore_attr_types = list_dict(map(string.lower, (ignore_attr_types or [])))
	modlist = []
	for attrtype in entry.keys():
		if ignore_attr_types.has_key(string.lower(attrtype)):
			continue

		# first, see if the object is iterable or not. If it is, remove
		# empty values, and completely remove empty iterable objects. Else,
		# remove empty non iterable objects, and if they are not empty,
		# convert them to an iterable because LDAP assumes they are.
		if hasattr(entry[attrtype],'__iter__'):

			# this is a bit over-enginiered because everything is already
			# verified to be not None at load time, and *Controllers never
			# produce empty attributes (as far as I remember). But verifying
			# one more time just before recording change is a sane behavior.
			attrvaluelist = filter(lambda x: x!=None, entry[attrtype])
			if attrvaluelist:
				modlist.append((attrtype, entry[attrtype]))
		elif entry[attrtype]:
			modlist.append((attrtype, [ str(entry[attrtype]) ]))
	return modlist
def modifyModlist(old_entry, new_entry, ignore_attr_types=None,
	ignore_oldexistent=0):
	"""
	Build differential modify list for calling
		LDAPObject.modify()/modify_s()

	This is rougly a copy of ldap.modlist.addModlist() version 2.3.10,
	modified to handle non iterable attributes. This is to avoid parsing our
	entries twice (once for creating iterable attributes, once for
	modifyModlist).

	old_entry
			Dictionary holding the old entry
	new_entry
			Dictionary holding what the new entry should be
	ignore_attr_types
			List of attribute type names to be ignored completely
	ignore_oldexistent
			If non-zero attribute type names which are in old_entry
			but are not found in new_entry at all are not deleted.
			This is handy for situations where your application
			sets attribute value to '' for deleting an attribute.
			In most cases leave zero.
	"""
	ignore_attr_types = list_dict(map(string.lower,(ignore_attr_types or [])))
	modlist = []
	attrtype_lower_map = {}
	for a in old_entry.keys():
		attrtype_lower_map[string.lower(a)] = a
	for attrtype in new_entry.keys():
		attrtype_lower = string.lower(attrtype)
		if ignore_attr_types.has_key(attrtype_lower):
			# This attribute type is ignored
			continue

		# convert all attributes to iterable objects (the rest of the
		# function assumes it is).
		if not hasattr(new_entry[attrtype], '__iter__'):
			new_entry[attrtype] = [ str(new_entry[attrtype]) ]

		# Filter away null-strings
		new_value = filter(lambda x: x!=None, new_entry[attrtype])
		if attrtype_lower_map.has_key(attrtype_lower):
			old_value = old_entry.get(attrtype_lower_map[attrtype_lower], [])
			old_value = filter(lambda x: x!=None, old_value)
			del attrtype_lower_map[attrtype_lower]
		else:
			old_value = []
		if not old_value and new_value:
			# Add a new attribute to entry
			modlist.append((ldap.MOD_ADD, attrtype, new_value))
		elif old_value and new_value:
			# Replace existing attribute
			replace_attr_value = len(old_value)!=len(new_value)
			if not replace_attr_value:
				old_value_dict=list_dict(old_value)
				new_value_dict=list_dict(new_value)
				delete_values = []
				for v in old_value:
					if not new_value_dict.has_key(v):
						replace_attr_value = 1
						break
				add_values = []
				if not replace_attr_value:
					for v in new_value:
						if not old_value_dict.has_key(v):
							replace_attr_value = 1
							break
			if replace_attr_value:
				modlist.append((ldap.MOD_DELETE, attrtype, None))
				modlist.append((ldap.MOD_ADD, attrtype, new_value))
		elif old_value and not new_value:
			# Completely delete an existing attribute
			modlist.append((ldap.MOD_DELETE, attrtype, None))
	if not ignore_oldexistent:
		# Remove all attributes of old_entry which are not present
		# in new_entry at all
		for a in attrtype_lower_map.keys():
			if ignore_attr_types.has_key(a):
				# This attribute type is ignored
				continue
			attrtype = attrtype_lower_map[a]
			modlist.append((ldap.MOD_DELETE, attrtype, None))
	return modlist # modifyModlist()
class LicornSmallLDIFParser(LDIFParser):
	def __init__(self, input_name):
		LDIFParser.__init__(self, open('%s/schemas/%s.ldif' % (
			os.path.dirname(__file__),input_name), 'r'))

		#print '%s/schemas/%s.ldif' % (
		#	os.path.dirname(__file__),input_name)

		self.__lcn_data = []
	def handle(self, dn, entry):
		self.__lcn_data.append((dn,entry))
	def get(self):
		self.parse()
		return self.__lcn_data
