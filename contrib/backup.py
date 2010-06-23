# -*- coding: utf-8 -*-
"""
Licorn contrib - http://dev.licorn.org/documentation/contrib

Copyright (C) 2005-2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2

"""

import os, time, re

from licorn.foundations    import logging, exceptions, readers
from licorn.core           import configuration

ssh_cmd    = [ 'ssh',  '-q', '-o', 'PasswordAuthentication no', '-o', 'StrictHostKeyChecking no', '-o', 'BatchMode yes' ]
rsync_cmd  = [ 'rsync', '-q' ]
date_begin = time.strftime("%d/%m/%Y %H:%M:%S", time.gmtime())
date_end   = ""
config     = readers.shell_conf_load_dict(configuration.backup_config_file)

def check_user():
	""" TODO: check if user is root of member of admin group. """
	if True:
		return True
	
	return False
def mail_report():
	#
	# Send mail here !
	#
	pass
def terminate():
	global date_end
	date_end = time.strftime("%d/%m/%Y %H:%M:%S", time.gmtime())

	#
	# close all file descriptors here.
	#
def build_distant_exclude_file(server):

	command = ssh_cmd[:]
	command.extend([ '-o', 'ConnectTimeout 5' ])
	command.append("%s@%s" % (config['DISTANT_USER'], server))
	command.append('echo OK ; . `get config backup_config_file -s` ; if [ -n "$EXTERNAL_EXCLUDE_FILE" -a -e "$EXTERNAL_EXCLUDE_FILE" ]; then cat $EXTERNAL_EXCLUDE_FILE; fi')

	output = os.popen3(command)[1].read().split('\n')

	if 'OK' == output[0]:
		exclude_list = []
		for outline in output[1:]:
			if outline[0] != '#' and outline != "":
				# strip comments and empty lines.
				exclude_list.append(outline)

		local_exclude_file = tempfile.mkstemp(suffix='.txt')
		open(local_exclude_file[1], "w").write('\n'.join(exclude_list))
		del exclude_list

		# return the filename of the temp file containing the exclude list.
		return local_exclude_file[1]

	else:
		raise exceptions.UnreachableError("Server timeout or connection failed (check SSH keys, username and password).")
def compute_needed_space():
	"""Find how much space in kilo-bytes is needed to fully archive the distant system."""

	command = ssh_cmd[:]
	command.append("%s@%s" % (config['DISTANT_USER'], server))
	command.append('licorn-distant-backup --compute-needed-space')

	return os.popen3(command)[1].read()[:-1]

def __compute_needed_space():
	"""Compute the local needed space in Kb. This def is called remotely through SSH."""

	root_dev = re.findall('(/[^\d]*)\d* / ', open('/proc/mounts').read())[0]

	total = 0
	for number in re.findall('%s\s+\d+\s+(\d+)\s' % root_dev, os.popen2('df')[1].read()):
		total += int(number)

	try:
		# if an exclude file is present, substract the space occupied by excluded dirs/files.
		exclude_file = re.findall('EXTERNAL_EXCLUDE_FILE="?([^"])"?', configuration.backup_config_file)[0]

		for line in open(exclude_file, 'r'):
			line = line.strip()
			if line[0] == '#' or line == '':
				continue

			if line[0] == '/':
				path = line
			else:
				# special, because the rsync is done in 2 phases to retain posix ACLs.
				# TODO: configuration.defaults.home_base_path
				path = '/home/' + line

			try:
				space = int(os.popen3('du -kc %s' % path)[1].read().split(' ')[0])
				total -= space
			except:
				# DU failed, probably because the path contained a shell globbing pattern.
				# don't bother now, this is harmless to skip some bytes...
				pass

	except IndexError:
		# when no exclude file, just return the total.
		return total

if not config.has_key('EXTERNAL_BACKUP_EMAIL'):
	config['EXTERNAL_BACKUP_EMAIL'] = 'backups@5sys.fr'


