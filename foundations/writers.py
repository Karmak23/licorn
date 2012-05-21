# -*- coding: utf-8 -*-
"""
Licorn system configuration writers.

The present module rassembles a set of tools to ease the writing of known
configuration files:
	* classic ^PARAM value$ (login.defs, ldap.conf)
	* classic ^PARAM=value$
	* other special types: smb.conf / lts.conf, squidguard.conf…

:copyright:
	* 2010 Olivier Cortès <oc@meta-it.fr>

:license: GNU GPL version 2

"""

import os, plistlib, tempfile
import xml.etree.ElementTree as ET

import fsapi

def	shell_conf_write_from_dict(data, filename, mode=0644, uid=0, gid=0):
	""" Read a shell configuration file with variables (VAR=value on each line)
		return a dictionary of param->value filled with the variables.

		Typical use case: /etc/licorn/names.conf, /etc/adduser.conf, /etc/licorn/licorn.conf
	"""

	fsapi.backup_file(filename)

	ftemp, fpath = tempfile.mkstemp(dir=os.path.dirname(filename))

	os.write(ftemp, '%s\n' % '\n'.join('%s=%s' % (key, value)
									for key, value in data.iteritems()))

	os.fchmod(ftemp, mode)
	os.fchown(ftemp, uid, gid)
	os.close(ftemp)

	os.rename(fpath, filename)

def xml_write_from_tree(tree, filename, mode=0644, uid=0, gid=0):

	fsapi.backup_file(filename)

	ftemp, fpath = tempfile.mkstemp(dir=os.path.dirname(filename))

	os.write(ftemp, ET.tostring(tree.getroot(), encoding='utf-8'))
	os.fchmod(ftemp, mode)
	os.fchown(ftemp, uid, gid)
	os.close(ftemp)

	os.rename(fpath, filename)

def plist_write_from_dict(data, filename):
	return plistlib.writePlist(data, filename)
