# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2010 Olivier Cortès <olive@deep-ocean.net>,
Licensed under the terms of the GNU GPL version 2
"""

import os, sys
import Pyro.core

from time import time, strftime, gmtime, localtime

from licorn.foundations           import logging, exceptions, process, hlstr
from licorn.foundations           import pyutils, styles
from licorn.foundations.objects   import Singleton
from licorn.foundations.constants import host_status, filters
from licorn.foundations.ltrace    import ltrace

class MachinesController(Singleton, Pyro.core.ObjBase):

	init_ok         = False

	machines        = None # (dictionary)
	hostname_cache  = None # (dictionary)

	# cross-references to other common objects
	configuration = None # (LicornConfiguration)
	groups        = None # (GroupsController)

	def __init__(self, configuration):
		""" Create the machine accounts list from the underlying system.
			The arguments are None only for get (ie Export and ExportXml) """

		if MachinesController.init_ok:
			return

		Pyro.core.ObjBase.__init__(self)

		self.nmap_cmd_base = [ 'nmap', '-n', '-T5', '-sP', '-oG',	'-' ]

		if self.configuration is None:
			self.configuration = configuration

		self.backends = self.configuration.backends

		if self.machines is None:
			self.reload()

		MachinesController.init_ok = True
	def __getitem__(self, item):
		return self.machines[item]
	def __setitem__(self, item, value):
		self.machines[item]=value
	def keys(self):
		return self.machines.keys()
	def has_key(self, key):
		return self.machines.has_key(key)
	def reload(self):
		""" Load (or reload) the data structures from the system files. """

		assert ltrace('machines', '| reload()')

		self.machines       = {}
		self.hostname_cache = {}

		for bkey in self.backends:
			if bkey=='prefered':
				continue
			assert ltrace('machines', '  reload(%s)' % bkey)
			self.backends[bkey].set_machines_controller(self)
			m, c = self.backends[bkey].load_machines()

			self.machines.update(m)
			self.hostname_cache.update(c)

		# don't do this here, this will speed up daemon boot, and will be done
		# in the next 30 seconds anyway.
		#self.update_statuses()
	def update_statuses(self, listener=None, *args, **kwargs):
		""" run across all IPs and find which machines are up or down. """
		nmap_cmd = self.nmap_cmd_base[:]
		nmap_cmd.extend(self.machines.keys())

		assert ltrace('machines', '> update_statuses(%s)' % ' '.join(nmap_cmd))

		try:
			nmap_status = process.execute(nmap_cmd)[0]
		except (IOError, OSError), e:
			if e.errno == 2:
				logging.warning2('''nmap is not installed on this system, '''
					'''can't ping machines''', once=True)
			else:
				raise e
		else:
			for status_line in nmap_status.splitlines():
				splitted = status_line.split()
				if splitted[0] == '#':
					continue
				if splitted[4] == 'Up':
						self.machines[splitted[1]]['status'] = host_status.ACTIVE
				elif splitted[4] == 'Down':
						self.machines[splitted[1]]['status'] = host_status.OFFLINE
	def set_groups_controller(self, groups):
		self.groups = groups
	def WriteConf(self, mid=None):
		""" Write the machine data in appropriate system files."""

		assert ltrace('machines', 'saving data structures to disk.')

		if mid:
			self.backends[
				self.machines[mid]['backend']
				].save_one_machine(mid)
		else:
			for bkey in self.backends.keys():
				if bkey=='prefered':
					continue
				self.backends[bkey].save_machines()
	def Select(self, filter_string):
		""" Filter machine accounts on different criteria. """

		filtered_machines = []

		mids = self.machines.keys()
		mids.sort()

		def keep_mid_if_status(mid, status=None):
			#print('mid: %s, status: %s, keep if %s' % (
			#	mid, self.machines[mid]['status'], status))
			if self.machines[mid]['status'] == status:
				filtered_machines.append(mid)

		if None == filter_string:
			filtered_machines = []

		elif host_status.ONLINE & filter_string:

			if host_status.ACTIVE & filter_string:
				def keep_mid_if_active(mid):
					return keep_mid_if_status(mid, status=host_status.ACTIVE)
				map(keep_mid_if_active, mids)

			if host_status.IDLE & filter_string:
				def keep_mid_if_idle(mid):
					return keep_mid_if_status(mid, status=host_status.IDLE)
				map(keep_mid_if_idle, mids)

			if host_status.ASLEEP & filter_string:
				def keep_mid_if_asleep(mid):
					return keep_mid_if_status(mid, status=host_status.ASLEEP)
				map(keep_mid_if_asleep, mids)

		else:
			import re
			mid_re = re.compile("^mid=(?P<mid>\d+)")
			mid = mid_re.match(filter_string)
			if mid is not None:
				mid = int(mid.group('mid'))
				filtered_machines.append(mid)

		return filtered_machines
	def AddMachine(self, lastname = None, firstname = None, password = None,
		primary_group=None, profile=None, skel=None, hostname=None, gecos=None,
		system = False, batch=False, force=False):
		"""Add a machine and return his/her (mid, hostname, pass)."""

		raise NotImplementedError('to be rewritten')

		logging.debug("Going to create a machine…")

		if hostname is None:
			if firstname is None or lastname is None:
				raise exceptions.BadArgumentError(
					logging.SYSU_SPECIFY_LGN_FST_LST)
			else:
				hostname_autogenerated = True
				hostname = self.make_hostname(lastname, firstname)
		else:
			hostname_autogenerated = False

		if gecos is None:
			gecos_autogenerated = True

			if firstname is None or lastname is None:
				gecos = "Compte %s" % hostname
			else:
				gecos = "%s %s" % (firstname, lastname.upper())
		else:
			gecos_autogenerated = False

			if firstname and lastname:
				raise exceptions.BadArgumentError(
					logging.SYSU_SPECIFY_LF_OR_GECOS)
			# else: all is OK, we have a hostname and a GECOS field

		# FIXME: in rare cases, we could discard some machine data ; e.g. if we got
		# a GECOS and *only* a firstname, the firstname will be discarded. We
		# should display a warning, or ask the admin.

		if not hlstr.cregex['hostname'].match(hostname):
			if hostname_autogenerated:
				raise exceptions.LicornRuntimeError(
					"Can't build a valid hostname (%s) with the " \
					"firstname/lastname (%s/%s) you provided." % (
					hostname, firstname, lastname) )
			else:
				raise exceptions.BadArgumentError(
					logging.SYSU_MALFORMED_LOGIN % (
						hostname, styles.stylize(styles.ST_REGEX,
						hlstr.regex['hostname'])))

		if not hostname_autogenerated and \
			len(hostname) > self.configuration.machines.hostname_maxlenght:
			raise exceptions.LicornRuntimeError(
				"Login too long (%d characters," \
				" but must be shorter or equal than %d)." % (
					len(hostname),
					self.configuration.machines.hostname_maxlenght) )

		if not hlstr.cregex['description'].match(gecos):
			if gecos_autogenerated:
				raise exceptions.LicornRuntimeError(
					"Can't build a valid GECOS (%s) with the" \
					" firstname/lastname (%s/%s) or hostname you provided." % (
						gecos, firstname, lastname) )
			else:
				raise exceptions.BadArgumentError(
					logging.SYSU_MALFORMED_GECOS % (
						gecos, styles.stylize(styles.ST_REGEX,
						hlstr.regex['description']) ) )

		if primary_group:
			pg_gid = self.groups.name_to_gid(primary_group)

		if skel and skel not in self.configuration.machines.skels:
			raise exceptions.BadArgumentError(
				"The skel you specified doesn't exist on this system." \
				" Valid skels are: %s." % \
					self.configuration.machines.skels)

		tmp_machine_dict = {}

		# Verify existance of machine
		for mid in self.machines:
			if self.machines[mid]['hostname'] == hostname:
				raise exceptions.AlreadyExistsException, \
					"A machine named « %s » already exists !" % hostname
				#
				# TODO ? continue creation if not a system account, to verify
				# everything is OK in the homedir, in the ACLs, etc.
				#
				# FIXME: verify everything besides the hostname before shouting
				# the machine already exists.
		#
		# Due to a bug of addmachine/delmachine perl script, we must check that there
		# is no group which the same name than the hostname. There should not
		# already be a system group with the same name (we are just going to
		# create it…), but it could be a system inconsistency, so go on to
		# recover from it.
		#
		# {add,del}machine logic is:
		#	- a system account must always have a system group as primary group,
		# 		else if will be «nogroup» if not specified.
		#   - when deleting a system account, a corresponding system group will
		#		be deleted if existing.
		#	- no restrictions for a standard account
		#
		# the bug is that in case 2, delmachine will delete the group even if this
		#  is a standard group (which is bad). This could happen with:
		#	addgroup toto
		#	addmachine --system toto --ingroup root
		#	delmachine --system toto
		#	(group toto is deleted but it shouldn't be ! And it is deleted
		#	without *any* message !!)
		#
		for gid in self.groups.groups:
			if self.groups.groups[gid]['name'] == hostname and not force:
				raise exceptions.UpstreamBugException, \
					"A group named `%s' exists on the system," \
					" this could eventually conflict in Debian/Ubuntu system" \
					" tools. Please choose another machine's hostname, or use " \
					"--force argument if you really want to add this machine " \
					"on the system." % hostname

		if password is None:
			# TODO: call cracklib2 to verify passwd strenght.
			password = hlstr.generate_password(
				self.configuration.users.min_passwd_size)
			logging.notice(logging.SYSU_AUTOGEN_PASSWD % (
				styles.stylize(styles.ST_LOGIN, hostname),
				styles.stylize(styles.ST_SECRET, password) ) )

		groups_to_add_machine_to = []

		skel_to_apply = "/etc/skel"
		# 3 cases:
		if profile is not None:
			# Apply the profile after having created the home dir.
			try:
				tmp_machine_dict['hostnameShell'] = \
					self.profiles.profiles[profile]['shell']
				tmp_machine_dict['gidNumber'] = \
					self.groups.name_to_gid(
					self.profiles.profiles[profile]['primary_group'])
				# fix #58.
				tmp_machine_dict['homeDirectory'] = ("%s/%s" % (
					self.configuration.machines.base_path, hostname))

				if self.profiles.profiles[profile]['groups'] != []:
					groups_to_add_machine_to = \
						self.profiles.profiles[profile]['groups']

					# don't directly add the machine to the groups. prepare the
					# groups to use the Licorn API later, to create the groups
					# symlinks while adding machine to them.
					#
					# machineadd_options.append("-G " + ",".join(
					# self.profiles.profiles[profile]['groups']))

				if skel is None:
					skel_to_apply = \
						self.profiles.profiles[profile]['skel_dir']
			except KeyError, e:
				# fix #292
				raise exceptions.LicornRuntimeError(
					"The profile %s does not exist on this system (was: %s) !" \
						% (profile, e))
		elif primary_group is not None:

			tmp_machine_dict['gidNumber']     = pg_gid
			tmp_machine_dict['hostnameShell']    = \
				self.configuration.machines.default_shell
			tmp_machine_dict['homeDirectory'] = "%s/%s" % (
				self.configuration.machines.base_path, hostname)

			# FIXME: use is_valid_skel() ?
			if skel is None and \
				os.path.isdir(
					self.groups.groups[pg_gid]['groupSkel']):
				skel_to_apply = \
					self.groups.groups[pg_gid]['groupSkel']

		else:
			tmp_machine_dict['gidNumber'] = \
				self.configuration.machines.default_gid
			tmp_machine_dict['hostnameShell'] = \
				self.configuration.machines.default_shell
			tmp_machine_dict['homeDirectory'] = "%s/%s" % (
				self.configuration.machines.base_path, hostname)
			# if skel is None, system default skel will be applied

		# FIXME: is this necessary here ? not done before ?
		if skel is not None:
			skel_to_apply = skel

		if system:
			mid = pyutils.next_free(self.machines.keys(),
				self.configuration.machines.system_mid_min,
				self.configuration.machines.system_mid_max)
		else:
			mid = pyutils.next_free(self.machines.keys(),
				self.configuration.machines.mid_min,
				self.configuration.machines.mid_max)

		tmp_machine_dict['machinePassword'] = \
			self.backends['prefered'].compute_password(password)

		tmp_machine_dict['shadowLastChange'] = str(int(time()/86400))

		# create home directory and apply skel
		if not os.path.exists(tmp_machine_dict['homeDirectory']):
			import shutil
			# copytree automatically creates tmp_machine_dict['homeDirectory']
			shutil.copytree(skel_to_apply, tmp_machine_dict['homeDirectory'])
		#
		# else: the home directory already exists, we don't overwrite it
		#

		tmp_machine_dict['midNumber']      = mid
		tmp_machine_dict['gecos']          = gecos
		tmp_machine_dict['hostname']       = hostname
		# prepare the groups cache.
		tmp_machine_dict['groups']         = []
		tmp_machine_dict['shadowInactive'] = ''
		tmp_machine_dict['shadowWarning']  = 7
		tmp_machine_dict['shadowExpire']   = ''
		tmp_machine_dict['shadowMin']      = 0
		tmp_machine_dict['shadowMax']      = 99999
		tmp_machine_dict['shadowFlag']     = ''
		tmp_machine_dict['backend']        = \
			self.backends['unix'].name if system else \
			self.backends['prefered'].name

		# Add machine in internal list and in the cache
		self.machines[mid]         = tmp_machine_dict
		self.hostname_cache[hostname] = mid

		#
		# we can't skip the WriteConf(), because this would break Samba stuff,
		# and AddMachinesInGroup stuff too:
		# Samba needs Unix account to be present in /etc/* before creating the
		# Samba account. We thus can't delay the WriteConf() call, even if we
		# are in batch / import machines mode. This is roughly the same with group
		# Additions: the machine must be present, prior to additions.
		#
		# DO NOT UNCOMMENT -- if not batch:
		self.machines[mid]['action'] = 'create'
		self.backends[
			self.machines[mid]['backend']
			].save_machine(mid)

		# Samba: add Samba machine account.
		# TODO: put this into a module.
		try:
			sys.stderr.write(process.execute(['smbpasswd', '-a', hostname, '-s'],
				'%s\n%s\n' % (password, password),)[1])
		except (IOError, OSError), e:
			if e.errno not in (2, 32):
				raise e

		if groups_to_add_machine_to != []:

			logging.debug("machine %s is going to be added to %s." % (
				styles.stylize(styles.ST_LOGIN, hostname), groups_to_add_machine_to))

			for group in groups_to_add_machine_to:
				self.groups.AddMachinesInGroup(group, [hostname])

		# Set quota
		if profile is not None:
			try:
				pass
				#os.popen2( [ 'quotatool', '-u', str(mid), '-b', self.configuration.defaults.quota_device, '-l' '%sMB' % self.profiles.profiles[profile]['quota'] ] )[1].read()
				#logging.warning("quotas are disabled !")
				# XXX: Quotatool can return 2 without apparent reason
				# (the quota is etablished) !
			except exceptions.LicornException, e:
				logging.warning( "ROLLBACK create machine because '%s'." % str(e))
				self.DeleteMachine(hostname, True)
				return (False, False, False)

		self.CheckMachines([ hostname ], batch = True)

		logging.info(logging.SYSU_CREATED_USER % (
			styles.stylize(styles.ST_LOGIN, hostname),
			styles.stylize(styles.ST_UGID, mid)))

		return (mid, hostname, password)
	def DeleteMachine(self, hostname=None, no_archive=False, mid=None, batch=False):
		""" Delete a machine """

		raise NotImplementedError('to be rewritten')

		if hostname is None and mid is None:
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LGN_OR_UID)

		if mid is None:
			mid = self.hostname_to_mid(hostname)

		elif hostname is None:
			# «hostname» is needed for delmachine system command.
			hostname = self.machines[mid]["hostname"]

		assert ltrace('machines', "| DeleteMachine() %s(%s), groups %s." % (
			hostname, str(mid), self.machines[mid]['groups']) )

		# Delete machine from his groups
		# '[:]' to fix #14, see
		# http://docs.python.org/tut/node6.html#SECTION006200000000000000000
		for group in self.machines[mid]['groups'].copy():
			self.groups.RemoveMachinesFromGroup(group, [ hostname ],
				batch=True)

		try:
			# samba stuff
			sys.stderr.write(process.execute(['smbpasswd', '-x', hostname])[1])
		except (IOError, OSError), e:
			if e.errno not in (2, 32):
				raise e

		# keep the homedir path, to backup it if requested.
		homedir = self.machines[mid]["homeDirectory"]

		# keep the backend, to notice the deletion
		backend = self.machines[mid]['backend']

		# Delete machine from machines list
		del(self.hostname_cache[hostname])
		del(self.machines[mid])
		logging.info(logging.SYSU_DELETED_USER % \
			styles.stylize(styles.ST_LOGIN, hostname))

		# TODO: try/except and reload the machine if unable to delete it
		# delete the machine in the backend after deleting it locally, else
		# Unix backend will not know what to delete (this is quite a hack).
		self.backends[backend].delete_machine(hostname)

		# machine is now wiped out from the system.
		# Last thing to do is to delete or archive the HOME dir.

		if no_archive:
			import shutil
			try:
				shutil.rmtree(homedir)
			except OSError, e:
				logging.warning("Problem deleting home dir %s (was: %s)" % (
					styles.stylize(styles.ST_PATH, homedir), e))

		else:
			self.configuration.check_base_dirs(minimal = True,
				batch = True)
			machine_archive_dir = "%s/%s.deleted.%s" % (
				self.configuration.home_archive_dir,
				hostname, strftime("%Y%m%d-%H%M%S", gmtime()))
			try:
				os.rename(homedir, machine_archive_dir)
				logging.info(logging.SYSU_ARCHIVED_USER % (homedir,
					styles.stylize(styles.ST_PATH, machine_archive_dir)))
			except OSError, e:
				if e.errno == 2:
					logging.warning(
						"Home dir %s doesn't exist, thus not archived." % \
							styles.stylize(styles.ST_PATH, homedir))
				else:
					raise e
	def ChangeMachinePassword(self, hostname, password = None, display = False):
		""" Change the password of a machine
		"""
		if hostname is None:
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)
		if password is None:
			password = hlstr.generate_password(
				self.configuration.users.min_passwd_size)
		elif password == "":
			logging.warning(logging.SYSU_SET_EMPTY_PASSWD % \
				styles.stylize(styles.ST_LOGIN, hostname))
			#
			# SECURITY concern: if password is empty, shouldn't we
			# automatically remove machine from remotessh ?
			#

		mid = self.hostname_to_mid(hostname)

		self.machines[mid]['machinePassword'] = \
		self.backends[
			self.machines[mid]['backend']
			].compute_password(password)

		# 3600*24 to have the number of days since epoch (fixes #57).
		self.machines[mid]['shadowLastChange'] = str(
			int(time()/86400) )

		self.machines[mid]['action'] = 'update'
		self.backends[
			self.machines[mid]['backend']
			].save_machine(mid)

		if display:
			logging.notice("Set machine %s's password to %s." % (
				styles.stylize(styles.ST_NAME, hostname),
				styles.stylize(styles.ST_IMPORTANT, password)))
		else:
			logging.info('Changed password for machine %s.' % \
				styles.stylize(styles.ST_NAME, hostname))

		try:
			# samba stuff
			sys.stderr.write(process.execute(['smbpasswd', hostname, '-s'],
				"%s\n%s\n" % (password, password))[1])
		except (IOError, OSError), e:
			if e.errno != 32:
				raise e
	def ChangeMachineGecos(self, hostname, gecos = ""):
		""" Change the gecos of a machine
		"""
		if hostname is None:
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)

		if not hlstr.cregex['description'].match(gecos):
			raise exceptions.BadArgumentError(logging.SYSU_MALFORMED_GECOS % (
				gecos,
				styles.stylize(styles.ST_REGEX, hlstr.regex['description'])))

		mid = self.hostname_to_mid(hostname)
		self.machines[mid]['gecos'] = gecos

		self.machines[mid]['action'] = 'update'
		self.backends[
			self.machines[mid]['backend']
			].save_machine(mid)
	def ChangeMachineShell(self, hostname, shell = ""):
		""" Change the shell of a machine. """
		if hostname is None:
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)

		mid = self.hostname_to_mid(hostname)

		if shell not in self.configuration.machines.shells:
			raise exceptions.LicornRuntimeError(
				"Invalid shell ! valid shells are %s." % \
					self.configuration.machines.shells)

		self.machines[mid]['hostnameShell'] = shell

		self.machines[mid]['action'] = 'update'
		self.backends[
			self.machines[mid]['backend']
			].save_machine(mid)
	def LockAccount(self, hostname, lock = True):
		"""(Un)Lock a machine account."""
		if hostname is None:
			raise exceptions.BadArgumentError(logging.SYSU_SPECIFY_LOGIN)

		#
		# TODO: lock the shell (not just the password), else SSH connections
		# with private/public keys could still be usable. As an alternative,
		# we could just remove machine from remotessh group, which seems to be
		# a Licorn prerequisite.
		#

		# update internal data structures.
		mid = self.hostname_to_mid(hostname)

		if lock:
			self.machines[mid]['machinePassword'] = '!' + \
				self.machines[mid]['machinePassword']
			logging.info('Locked machine account %s.' % \
				styles.stylize(styles.ST_LOGIN, hostname))
		else:
			self.machines[mid]['machinePassword'] = \
				self.machines[mid]['machinePassword'][1:]
			logging.info('Unlocked machine account %s.' % \
				styles.stylize(styles.ST_LOGIN, hostname))
		self.machines[mid]['locked'] = lock


		self.machines[mid]['action'] = 'update'
		self.backends[
			self.machines[mid]['backend']
			].save_machine(mid)
	def ExportCLI(self, selected=None, long_output=False):
		""" Export the machine accounts list to human readable («passwd») form.
		"""
		if selected is None:
			mids = self.machines.keys()
		else:
			mids = selected
		mids.sort()

		assert ltrace('machines', '| ExportCLI(%s)' % mids)

		m = self.machines

		def build_cli_output_machine_data(mid):

			account = [	styles.stylize(styles.ST_NAME \
							if m[mid]['managed'] else styles.ST_SPECIAL,
							m[mid]['hostname']),
						styles.stylize(styles.ST_OK, 'Online') \
								if m[mid]['status'] == host_status.ACTIVE \
								else styles.stylize(styles.ST_BAD, 'Offline'),
						'managed' if m[mid]['managed'] \
								else 'floating',
						str(mid),
						str(m[mid]['ether']),
						styles.stylize(styles.ST_ATTR,
							strftime('%Y-%d-%m %H:%M:%S',
							localtime(float(m[mid]['expiry'])))) \
							if m[mid]['expiry'] else '',
						]
			return '/'.join(account)

		data = '\n'.join(map(build_cli_output_machine_data, mids)) + '\n'

		return data
	def ExportCSV(self, selected=None, long_output=False):
		"""Export the machine accounts list to CSV."""

		raise NotImplementedError('to be rewritten')

		if selected is None:
			mids = self.machines.keys()
		else:
			mids = selected
		mids.sort()

		assert ltrace('machines', '| ExportCSV(%s)' % mids)

		def build_csv_output_licorn(mid):
			return ';'.join(
				[	self.machines[mid]['gecos'],
					self.machines[mid]['hostname'],
					str(self.machines[mid]['gidNumber']),
					','.join(self.machines[mid]['groups']) ]
				)

		data = '\n'.join(map(build_csv_output_licorn, mids)) +'\n'

		return data
	def ExportXML(self, selected=None, long_output=False):
		""" Export the machine accounts list to XML. """

		if selected is None:
			mids = self.machines.keys()
		else:
			mids = selected
		mids.sort()

		assert ltrace('machines', '| ExportXML(%s)' % mids)

		m = self.machines

		def build_xml_output_machine_data(mid):
			data = '''	<machine>
		<hostname>%s</hostname>
		<mid>%s</mid>
		<floating>%s</floating>
		<status>%s</status>
		<ether>%s</ether>
		<expiry>%s</expiry>\n''' % (
					m[mid]['hostname'],
					mid,
					m[mid]['floating'],
					m[mid]['status'],
					m[mid]['ether'],
					m[mid]['expiry'] if m[mid]['expiry'] else ''
				)

			return data + "	</machine>"

		data = "<?xml version='1.0' encoding=\"UTF-8\"?>\n<machines-list>\n" \
			+ '\n'.join(map(build_xml_output_machine_data, mids)) \
			+ "\n</machines-list>\n"

		return data
	def shutdown(self, mid=None, hostname=None, warn_users=True, listener=None):
		""" Shutdown a machine, after having warned the connected user(s) if
			asked to."""

		mid, hostname = self.resolve_mid_or_hostname(mid, hostname)

		if warn_users:
			command = (r'''export DISPLAY=":0"; '''
				r'''sudo su -l '''
				r'''`w | grep -E 'tty.\s+:0' | awk '{print $1}'` '''
				r'''-c 'zenity --warning --text="le système va être arrêté dans '''
				r'''une minute exactement, merci de bien vouloir enregistrer '''
				r'''votre travail et de fermer votre session."'&''')
		else:
			command = ''

		command += '''sudo shutdown -r +1'''

		process.execute_remote(mid, command)

		logging.info('shut down machine %s.' % hostname, listener=listener)
	def is_alt(self, mid=None, hostname=None):
		""" Return True if the machine is an ALT client, else False. """

		mid, hostname = self.resolve_mid_or_hostname(mid,hostname)
		try:
			return self.machines[mid]['ether'].lower().startswith(
				'00:e0:f4:')
		except KeyError:
			return False
	def confirm_mid(self, mid):
		""" verify a MID or raise DoesntExists. """
		try:
			return self.machines[mid]['ip']
		except KeyError:
			raise exceptions.DoesntExistsException(
				"MID %s doesn't exist" % mid)
	def resolve_mid_or_hostname(self, mid=None, hostname=None):
		""" method used every where to get mid / hostname of a group object to
			do something onto. a non existing mid / hostname will raise an
			exception from the other methods methods."""

		if hostname is None and mid is None:
			raise exceptions.BadArgumentError(
				"You must specify a hotname or a MID to resolve from.")

		assert ltrace('groups', '| resolve_mid_or_hostname(mid=%s, hostname=%s)' % (
			mid, hostname))

		# we cannot just test "if gid:" because with root(0) this doesn't work.
		if mid is not None:
			hostname = self.mid_to_hostname(mid)
		else:
			mid = self.hostname_to_mid(hostname)
		return (mid, hostname)
	def exists(self, mid=None, hostname=None):
		if mid:
			return self.machines.has_key(mid)
		if hostname:
			return self.hostname_cache.has_key(hostname)

		raise exceptions.BadArgumentError(
			"You must specify a MID or a hostname to test existence of.")
	def hostname_to_mid(self, hostname):
		""" Return the mid of the machine 'hostname'. """
		try:
			# use the cache, Luke !
			return self.hostname_cache[hostname]
		except KeyError:
			try:
				int(hostname)
				logging.warning("You passed an mid to hostname_to_mid():"
					" %d (guess its hostname is « %s » )." % (
						hostname, self.machines[hostname]['hostname']))
			except ValueError:
				pass

			raise exceptions.LicornRuntimeException(
				_('''machine %s doesn't exist.''') % hostname)
	def mid_to_hostname(self, mid):
		""" Return the hostname for a given IP."""
		try:
			return self.machines[mid]['hostname']
		except KeyError:
			raise exceptions.DoesntExistsException(
				"MID %s doesn't exist" % mid)
	def guess_identifier(self, value):
		""" Try to guess everything of a machine from a
			single and unknown-typed info. """
		try:
			self.mid_to_hostname(value)
			mid = value
		except exceptions.DoesntExistsException, e:
			mid = self.mid_to_hostname(value)
		return mid
	def guess_identifiers(self, value_list):

		valid_ids=set()
		for value in value_list:
			try:
				valid_ids.add(self.guess_identifier(value))
			except exceptions.DoesntExistsException:
				logging.notice("Skipped non-existing hostname or MID '%s'." %
					styles.stylize(styles.ST_NAME, value))
		return valid_ids
	def make_hostname(self, inputhostname=None):
		""" Make a valid hostname from what we're given. """

		if inputhostname is None:
			raise exceptions.BadArgumentError(
				_('''You must pass a hostname to verify!'''))

		# use provided hostname and verify it.
		hostname = hlstr.validate_name(str(inputhostname),
			maxlenght = self.configuration.machines.hostname_maxlenght)

		if not hlstr.cregex['hostname'].match(hostname):
			raise exceptions.LicornRuntimeError(
				_('''Can't build a valid hostname (got %s, which doesn't'''
				''' verify %s)''') % (
					inputhostname, hlstr.regex['hostname']))

		return hostname
