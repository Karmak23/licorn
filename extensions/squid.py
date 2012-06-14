# -*- coding: utf-8 -*-
"""
Licorn extensions: squid - http://docs.licorn.org/extensions/squid.html

:copyright: 2010 Robin Lucbernet <robinlucbernet@gmail.com>

:license: GNU GPL version 2

"""

import os, netifaces

from licorn.foundations           import logging, exceptions, settings
from licorn.foundations           import readers, process, network
from licorn.foundations.ltrace    import *
from licorn.foundations.styles    import *
from licorn.foundations.ltraces   import *
from licorn.foundations.base      import ObjectSingleton, Enumeration
from licorn.foundations.classes   import ConfigFile
from licorn.foundations.pyutils   import add_or_dupe_enumeration
from licorn.foundations.constants import services, svccmds, priorities, roles, distros

from licorn.core                  import LMC
from licorn.extensions            import ServiceExtension

class SquidExtension(ObjectSingleton, ServiceExtension):
	""" A proxy extension using squid.

		On the server:

			- if config file present, the extension is available.
			- else non-available.

		On a client:

			- always avalaible.
		 	- enabled if extension is also enabled on the server.


		.. note:: On Ubuntu there is no distinction between available and
			enabled because we have no way to make the service not start at
			system boot. Thus, if available, this extension **is** enabled.


	"""

	def __init__(self):

		ServiceExtension.__init__(self,
			name='squid',
			service_name='squid',
			service_type=services.UPSTART
							if LMC.configuration.distro == distros.UBUNTU
							else services.SYSV
		)
		assert ltrace_func(TRACE_EXTENSIONS)
		self.server_only=False

		# no particular controller for this extension, it is a
		# standalone one (no data, just configuration).
		self.controllers_compat = []

		# we could be squid v2 or v3.

		self.service_name      = 'squid'
		self.paths.squid_conf  = '/etc/squid/squid.conf'
		self.paths.squid3_conf = '/etc/squid3/squid.conf'
		self.paths.squid_bin   = '/usr/sbin/squid'
		self.paths.squid3_bin  = '/usr/sbin/squid3'
		self.paths.squid_pid   = '/var/run/squid.pid'

		self.defaults_conf = self.get_defaults_conf()

		self.unwanted_default_conf = [
			('acl', 'localnet src 10.0.0.0/8	# RFC1918 possible internal network'),
			('acl', 'localnet src 172.16.0.0/12	# RFC1918 possible internal network'),
			('acl', 'localnet src 192.168.0.0/16	# RFC1918 possible internal network'),
			('icp_access', 'allow localnet'),
		]

		self.wanted_default_conf = [
			('access_log', '/var/log/squid/access.log squid'),
			# 24Gb proxy spool dir
			('cache_dir', 'ufs /var/spool/squid 24576 64 128'),
			# 16Gb maximum object size -> we cache DVDs ISO if needed
			('maximum_object_size', '16777216'),
			('access_log', '/var/log/squid/access.log squid'),
			('acl', 'all src all'),
			('acl', 'manager proto cache_object'),
			('acl', 'localhost src 127.0.0.0/8'),
			('acl', 'to_localhost dst 127.0.0.0/8 0.0.0.0/32'),
			('acl', 'SSL_ports port 443'),
			('acl', 'SSL_ports port 563'),
			('acl', 'SSL_ports port 873'),
			('acl', 'Safe_ports port 80'),
			('acl', 'Safe_ports port 21'),
			('acl', 'Safe_ports port 443'),
			('acl', 'Safe_ports port 70'),
			('acl', 'Safe_ports port 210'),
			('acl', 'Safe_ports port 1025-65535'),
			('acl', 'Safe_ports port 280'),
			('acl', 'Safe_ports port 488'),
			('acl', 'Safe_ports port 591'),
			('acl', 'Safe_ports port 777'),
			('acl', 'Safe_ports port 631'),
			('acl', 'Safe_ports port 873'),
			('acl', 'Safe_ports port 901'),
			('acl', 'purge method PURGE'),
			('acl', 'CONNECT method CONNECT'),
			('acl', 'shoutcast rep_header X-HTTP09-First-Line ^ICY.[0-9]'),
			('acl', 'apache rep_header Server ^Apache'),
			('broken_vary_encoding', 'allow apache'),
			('coredump_dir', '/var/spool/squid'),
			('extension_methods', 'REPORT MERGE MKACTIVITY CHECKOUT'),
			('hierarchy_stoplist', 'cgi-bin ?'),
			('hosts_file', '/etc/hosts'),
			('http_access', 'allow manager localhost'),
			('http_access', 'deny manager'),
			('http_access', 'allow purge localhost'),
			('http_access', 'deny purge'),
			('http_access', 'deny !Safe_ports'),
			('http_access', 'deny CONNECT !SSL_ports'),
			('http_access', 'deny all'),
			('http_access', 'allow localhost'),
			('http_access', 'allow localnetwork'),
			('http_access', 'deny all'),
			('http_port', self.defaults_conf.port),
			('icp_access', 'allow localnetwork'),
			('icp_access', 'deny all'),
			('refresh_pattern', '^ftp:           1440    20%     10080'),
			('refresh_pattern', '^gopher:        1440    0%      1440'),
			('refresh_pattern', "-i (/cgi-bin/|\?) 0     0%      0")
		]

		if settings.role == roles.SERVER:
			self.defaults = Enumeration()
			for network in self.defaults_conf.subnet:
				add_or_dupe_enumeration(self.defaults, 'acl',
										'localnetwork src %s' % network),
			for key, value in self.wanted_default_conf:
				add_or_dupe_enumeration(self.defaults, key, value)

		# TODO: add peers here. iterate other licorn servers on the same LAN
		# and add a 'cache_peer sibling' directive for them. Then, make them
		# reflect this change and add us to their siblings list.

	def get_defaults_conf(self):
		""" TODO """

		assert ltrace_func(TRACE_SQUID)

		conf_dict = Enumeration()
		conf_dict['port']            = '3128'
		conf_dict['client_file']     = '/etc/environment'
		conf_dict['apt_conf']        = '/etc/apt/apt.conf.d/00proxy'
		conf_dict['client_cmd_http'] = 'http_proxy'
		conf_dict['client_cmd_ftp']  = 'ftp_proxy'

		if settings.role == roles.SERVER:
			conf_dict['subnet'] = []

			for iface in network.interfaces():
				iface_infos = netifaces.ifaddresses(iface)
				if 2 in iface_infos:
					subnet = '%s.0/%s' % (
						iface_infos[2][0]['addr'].rsplit('.', 1)[0],
						network.netmask2prefix(
							iface_infos[2][0]['netmask']))
					conf_dict['subnet'].append(subnet)

			conf_dict['config_file'] = '/etc/squid/squid.conf'
			conf_dict['host'] = '127.0.0.1'

		else:
			conf_dict['host'] = LMC.configuration.server_main_address

		conf_dict['client_cmd_value_http'] = '"http://%s:%s/"' % (
			conf_dict['host'], conf_dict['port'])

		conf_dict['client_cmd_value_ftp'] = '"ftp://%s:%s/"' % (
			conf_dict['host'], conf_dict['port'])

		conf_dict['apt_cmd_http'] = 'Acquire::http::Proxy'
		conf_dict['apt_cmd_http_value'] = '"http://%s:%s/";' % (
			conf_dict['host'], conf_dict['port'])
		conf_dict['apt_cmd_ftp'] = 'Acquire::ftp::Proxy'
		conf_dict['apt_cmd_ftp_value'] = '"ftp://%s:%s/";' % (
			conf_dict['host'], conf_dict['port'])

		return conf_dict
	def initialize(self):
		""" TODO """
		assert ltrace(globals()['TRACE_' + self.name.upper()], '> initialize()')

		if settings.role == roles.SERVER:

			if os.path.exists(self.paths.squid_bin):
				self.available = True

				self.configuration = ConfigFile(self.paths.squid_conf,
							name='squid', separator=' ', caller=self.name)

			elif os.path.exists(self.paths.squid3_bin):
				self.available = True

				self.service_name = 'squid3'
				self.service_type =	services.SYSV

				self.configuration = ConfigFile(self.paths.squid3_conf,
							name='squid', separator=' ', caller=self.name)

			else:
				logging.warning2(_(u'{0}: not available because {1} '
					'do not exist on the system.').format(
						stylize(ST_NAME, self.name),
						stylize(ST_PATH, self.paths.squid_bin)))
				self.remove_configuration(batch=True)

		else:
			# squid extension is always available on clients.
			self.available = True
		assert ltrace(globals()['TRACE_' + self.name.upper()], '< initialize()')
		return self.available
	def is_enabled(self):
		""" Squid extension is enabled when squid's pid file exists and the
			process runs.

			.. note:: as stated above, the service **MUST** be running if
				installed. This method starts it if needed.
		"""
		if self.available:
			if not self.running(self.paths.squid_pid):
				self.service(svccmds.START)

			logging.info(_(u'{0}: started extension, managing {1} service '
				'({2}).').format(
					stylize(ST_NAME, self.name),
					stylize(ST_NAME, self.service_name),
					(_(u'pid=%s') % stylize(ST_UGID,
						open(self.paths.squid_pid).read().strip()))
							if os.path.exists(self.paths.squid_pid)
							else stylize(ST_COMMENT, _('Starting up'))))
			return True
		else:
			return False
	def update_client(self, batch=False, auto_answer=None):
		""" update the client, make the client connecting through the proxy if
		the extension is enabled.
			We need to set/unset several parameters in different places :

				- environment parameter 'http_proxy' for current process and
					sub-process.
				- 'http_proxy' in /etc/environment to set this env param for
					future logged-in user.
				- deal with gconf to set proxy for gnome apps.
				- params in apt configuration
		"""
		assert ltrace(globals()['TRACE_' + self.name.upper()], '> update_client(batch=%s, auto_answer=%s)' %
			(batch, auto_answer))

		env_file = ConfigFile(self.defaults_conf.client_file,
								separator='=', caller=self.name)
		env_need_rewrite = False

		if self.enabled:

			# set variables for the current environment
			os.putenv(self.defaults_conf.client_cmd_http,
				self.defaults_conf.client_cmd_value_http)

			os.putenv(self.defaults_conf.client_cmd_http.upper(),
				self.defaults_conf.client_cmd_value_http)

			os.putenv(self.defaults_conf.client_cmd_ftp,
				self.defaults_conf.client_cmd_value_ftp)

			os.putenv(self.defaults_conf.client_cmd_ftp.upper(),
				self.defaults_conf.client_cmd_value_ftp)

			# set 'http_proxy' in /etc/environment
			for cmd, value in (
				(self.defaults_conf.client_cmd_http,
				self.defaults_conf.client_cmd_value_http),
				(self.defaults_conf.client_cmd_http.upper(),
				self.defaults_conf.client_cmd_value_http),
				(self.defaults_conf.client_cmd_ftp.upper(),
				self.defaults_conf.client_cmd_value_ftp),
				(self.defaults_conf.client_cmd_ftp,
				self.defaults_conf.client_cmd_value_ftp)):

				if env_file.has('export ' + cmd):
					if env_file['export ' + cmd] != value:

						env_need_rewrite = True
						env_file.add(key='export ' + cmd,
							value=value, replace=True)
				else:
					env_need_rewrite = True
					env_file.add(key='export ' + cmd,
						value=value)

			if env_need_rewrite:
				env_file.backup_and_save(batch=batch, auto_answer=auto_answer)

			if os.path.exists('/usr/bin/gconftool-2'):

				# set mandatory proxy params for gnome.
				gconf_values = (
					['string', '--set', '/system/http_proxy/host',
						self.defaults_conf.host ],
					[ 'string', '--set', '/system/proxy/ftp_host',
						self.defaults_conf.host ],
					[ 'string', '--set', '/system/proxy/mode', 'manual' ],
					[ 'bool', '--set', '/system/http_proxy/use_http_proxy', 'true'],
					[ 'int', '--set', '/system/http_proxy/port',
						str(self.defaults_conf.port) ],
					[ 'int', '--set', '/system/proxy/ftp_port',
						str(self.defaults_conf.port) ] )
					# TODO : addresses in ignore_host.
					#[ 'list', '--set', '/system/http_proxy/ignore_hosts', '[]',
					#'--list-type',  'string'])
				base_command = [ 'gconftool-2', '--direct', '--config-source',
					'xml:readwrite:/etc/gconf/gconf.xml.mandatory', '--type' ]

				for gconf_value in gconf_values:
					command = base_command[:]
					command.extend(gconf_value)

					process.execute(command)

			# set params in apt conf
			apt_file = ConfigFile(self.defaults_conf.apt_conf,
									separator=' ', caller=self.name)
			apt_need_rewrite = False

			if not apt_file.has(key=self.defaults_conf.apt_cmd_http):
				apt_need_rewrite = True
				apt_file.add(key=self.defaults_conf.apt_cmd_http,
					value=self.defaults_conf.apt_cmd_http_value)

			if not apt_file.has(key=self.defaults_conf.apt_cmd_ftp):
				apt_need_rewrite = True
				apt_file.add(key=self.defaults_conf.apt_cmd_ftp,
					value=self.defaults_conf.apt_cmd_ftp_value)

			if apt_need_rewrite:
				apt_file.backup_and_save(batch=batch, auto_answer=auto_answer)

		else:
			self.remove_configuration()

		assert ltrace(globals()['TRACE_' + self.name.upper()], '< update_client()' )
	def check(self, batch=False, auto_answer=None):
		""" check if *stricly needed* values are in the configuration file.
		if they are not, the extension will not be enabled

			needed squid params:
				- general:
					- http_port: squid port.
				- security:
					- acl all src all
					- acl localnetwork src 192.168.0.0/24 : range  of machines
						allowed to connect to the proxy server.
					- acl localhost src 127.0.0.1 : allow the server to
						connect through the proxy
					- http_access allow localhost : allow access to the server.
					- http_access allow localnetwork : allow access to the
						server.
					- http_access deny all : disable access to others.
		"""
		assert ltrace_func(TRACE_SQUID)

		if settings.role == roles.SERVER:
			logging.progress('Checking good default values in %s…' %
									stylize(ST_PATH, self.paths.squid_conf))

			need_rewrite = False

			for key, value in self.defaults.iteritems():
				if hasattr(value, '__iter__'):
					for v in value:
						if not self.configuration.has(key, v):
							need_rewrite = True
							self.configuration.add(key, v)
				else:
					if not self.configuration.has(key, value):
						need_rewrite = True
						self.configuration.add(key, value)

			# remove unwanted conf
			for key, value in self.unwanted_default_conf:
				if self.configuration.has(key, value=value):
					self.configuration.remove(key, value=value)

			if need_rewrite:
				self.configuration.backup_and_save(batch=batch, auto_answer=auto_answer)
				self.service(svccmds.RELOAD)

		# finally, update system to deal or not with the extension.
		self.update_client(batch=batch, auto_answer=auto_answer)

		assert ltrace(globals()['TRACE_' + self.name.upper()], '< check()' )
		return True
	def remove_configuration(self, batch=False, auto_answer=None):
		""" TODO """
		env_file = ConfigFile(self.defaults_conf.client_file,
								separator='=', caller=self.name)
		env_need_rewrite = False

		# unset env param
		os.putenv(self.defaults_conf.client_cmd_http, '')
		os.putenv(self.defaults_conf.client_cmd_ftp, '')

		# unset 'http_proxy' in /etc/environment
		for cmd in (self.defaults_conf.client_cmd_http,
					self.defaults_conf.client_cmd_http.upper(),
					self.defaults_conf.client_cmd_ftp,
					self.defaults_conf.client_cmd_ftp.upper()):

			if env_file.has(cmd):
				env_file.remove(key=cmd)
				env_need_rewrite = True

			if env_file.has('export ' + cmd):
				env_file.remove(key='export ' + cmd)
				env_need_rewrite = True

		if os.path.exists('/usr/bin/gconftool-2'):
			# unset gnome proxy configuration
			for file in ('xml:readwrite:/etc/gconf/gconf.xml.mandatory',
				'xml:readwrite:/etc/gconf/gconf.xml.defaults'):
				process.execute(['gconftool-2', '--direct', '--config-source',
					file, '--recursive-unset', '/system/http_proxy'])
				process.execute(['gconftool-2', '--direct', '--config-source',
					file, '--recursive-unset', '/system/proxy'])

		# unset apt conf params
		if os.path.exists(self.defaults_conf.apt_conf):
			os.unlink(self.defaults_conf.apt_conf)

		if env_need_rewrite:
			env_file.backup_and_save(batch=batch, auto_answer=auto_answer)

	def enable(self, batch=False, auto_answer=None):
		""" TODO """
		self.check(batch=batch, auto_answer=auto_answer)
		self.service(svccmds.START)
		self.enabled = True
		return True
	def disable(self):
		# TODO : self.remove_configuration()
		self.service(svccmds.STOP)
		self.enabled = False
		return True
