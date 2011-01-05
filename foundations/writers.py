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

import plistlib
import xml.etree.ElementTree as ET

def	shell_conf_write_from_dict(data, filename):
	""" Read a shell configuration file with variables (VAR=value on each line)
		return a dictionary of param->value filled with the variables.

		Typical use case: /etc/licorn/names.conf, /etc/adduser.conf, /etc/licorn/licorn.conf
	"""

	with open(filename , 'w') as filehandle:
		filehandle.write('\n'.join(
			[ '%s=%s' % (key, value)
				for key, value in data.items()
			]) + '\n'
		)

def xml_write_from_tree(tree, filename):
	return tree.write(filename)

def plist_write_from_dict(data, filename):
	return plistlib.writePlist(data, filename)
