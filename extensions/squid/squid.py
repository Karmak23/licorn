# -*- coding: utf-8 -*-
"""
Licorn extensions: squid - http://docs.licorn.org/extensions/squid.html

:copyright: 2010 Robin Lucbernet <robinlucbernet@gmail.com>

:license: GNU GPL version 2

"""

import os, re, errno, netifaces

from pygments.token import *
from pygments.lexer import RegexLexer

from licorn.foundations           import logging, settings, exceptions
from licorn.foundations           import process, network, hlstr
from licorn.foundations.styles    import *
from licorn.foundations.ltrace    import ltrace, ltrace_func
from licorn.foundations.ltraces   import *
from licorn.foundations.pyutils   import add_or_dupe_enumeration
from licorn.foundations.constants import services, svccmds, distros, roles, priorities
from licorn.foundations.base      import ObjectSingleton, Enumeration
from licorn.foundations.classes   import ConfigFile
from licorn.foundations.config    import ConfigurationFile, ConfigurationToken

from licorn.core                  import LMC
from licorn.extensions            import ServiceExtension

SQUID_DEFAULT_HTTP_PORT = '3128'

class LicornSquidConfLexer(RegexLexer, ObjectSingleton):
	"""
	Lexer for `squid <http://www.squid-cache.org/>`_ configuration files.

	.. note:: this lexer is the one found in Pygments 0.9, with our own
		additions and enhancements. See https://bitbucket.org/birkenfeld/pygments-main/issue/664/enhancements-for-squidconflexer
		for details.
	"""

	name	  = 'SquidConf'
	aliases   = ['squidconf', 'squid.conf', 'squid']
	filenames = ['squid.conf']
	mimetypes = ['text/x-squidconf']
	flags	  = re.IGNORECASE

	keywords = [ "access_log", "acl", "always_direct", "announce_host",
				 "announce_period", "announce_port", "announce_to",
				 "anonymize_headers", "append_domain", "as_whois_server",
				 "auth_param_basic", "authenticate_children",
				 "authenticate_program", "authenticate_ttl", "broken_posts",
				 "buffered_logs", "cache_access_log", "cache_announce",
				 "cache_dir", "cache_dns_program", "cache_effective_group",
				 "cache_effective_user", "cache_host", "cache_host_acl",
				 "cache_host_domain", "cache_log", "cache_mem",
				 "cache_mem_high", "cache_mem_low", "cache_mgr",
				 "cachemgr_passwd", "cache_peer", "cache_peer_access",
				 "cache_replacement_policy", "cache_stoplist",
				 "cache_stoplist_pattern", "cache_store_log", "cache_swap",
				 "cache_swap_high", "cache_swap_log", "cache_swap_low",
				 "client_db", "client_lifetime", "client_netmask",
				 "connect_timeout", "coredump_dir", "dead_peer_timeout",
				 "debug_options", "delay_access", "delay_class",
				 "delay_initial_bucket_level", "delay_parameters",
				 "delay_pools", "deny_info", "dns_children", "dns_defnames",
				 "dns_nameservers", "dns_testnames", "emulate_httpd_log",
				 "err_html_text", "fake_user_agent", "firewall_ip",
				 "forwarded_for", "forward_snmpd_port", "fqdncache_size",
				 "ftpget_options", "ftpget_program", "ftp_list_width",
				 "ftp_passive", "ftp_user", "half_closed_clients",
				 "header_access", "header_replace", "hierarchy_stoplist",
				 "high_response_time_warning", "high_page_fault_warning", "hosts_file",
				 "htcp_port", "http_access", "http_anonymizer", "httpd_accel",
				 "httpd_accel_host", "httpd_accel_port",
				 "httpd_accel_uses_host_header", "httpd_accel_with_proxy",
				 "http_port", "http_reply_access", "icp_access",
				 "icp_hit_stale", "icp_port", "icp_query_timeout",
				 "ident_lookup", "ident_lookup_access", "ident_timeout",
				 "incoming_http_average", "incoming_icp_average",
				 "inside_firewall", "ipcache_high", "ipcache_low",
				 "ipcache_size", "local_domain", "local_ip", "logfile_rotate",
				 "log_fqdn", "log_icp_queries", "log_mime_hdrs",
				 "maximum_object_size", "maximum_single_addr_tries",
				 "mcast_groups", "mcast_icp_query_timeout", "mcast_miss_addr",
				 "mcast_miss_encode_key", "mcast_miss_port", "memory_pools",
				 "memory_pools_limit", "memory_replacement_policy",
				 "mime_table", "min_http_poll_cnt", "min_icp_poll_cnt",
				 "minimum_direct_hops", "minimum_object_size",
				 "minimum_retry_timeout", "miss_access", "negative_dns_ttl",
				 "negative_ttl", "neighbor_timeout", "neighbor_type_domain",
				 "netdb_high", "netdb_low", "netdb_ping_period",
				 "netdb_ping_rate", "never_direct", "no_cache",
				 "passthrough_proxy", "pconn_timeout", "pid_filename",
				 "pinger_program", "positive_dns_ttl", "prefer_direct",
				 "proxy_auth", "proxy_auth_realm", "query_icmp", "quick_abort",
				 "quick_abort", "quick_abort_max", "quick_abort_min",
				 "quick_abort_pct", "range_offset_limit", "read_timeout",
				 "redirect_children", "redirect_program",
				 "redirect_rewrites_host_header", "reference_age",
				 "reference_age", "refresh_pattern", "reload_into_ims",
				 "request_body_max_size", "request_size", "request_timeout",
				 "shutdown_lifetime", "single_parent_bypass",
				 "siteselect_timeout", "snmp_access", "snmp_incoming_address",
				 "snmp_port", "source_ping", "ssl_proxy",
				 "store_avg_object_size", "store_objects_per_bucket",
				 "strip_query_terms", "swap_level1_dirs", "swap_level2_dirs",
				 "tcp_incoming_address", "tcp_outgoing_address",
				 "tcp_recv_bufsize", "test_reachability", "udp_hit_obj",
				 "udp_hit_obj_size", "udp_incoming_address",
				 "udp_outgoing_address", "unique_hostname", "unlinkd_program",
				 "uri_whitespace", "useragent_log", "visible_hostname",
				 "wais_relay", "wais_relay_host", "wais_relay_port",
				 ]

	opts = [ "proxy-only", "weight", "ttl", "no-query", "default",
			 "round-robin", "multicast-responder", "on", "off", "all",
			 "deny", "allow", "via", "parent", "no-digest", "heap", "lru",
			 "realm", "children", "credentialsttl", "none", "disable",
			 "offline_toggle", "diskd", "q1", "q2",
			 ]

	actions = [ "shutdown", "info", "parameter", "server_list",
				"client_list", r'squid\.conf',
				]

	actions_stats = [ "objects", "vm_objects", "utilization",
					  "ipcache", "fqdncache", "dns", "redirector", "io",
					  "reply_headers", "filedescriptors", "netdb",
					  ]

	actions_log = [ "status", "enable", "disable", "clear"]

	acls = [ "url_regex", "urlpath_regex", "referer_regex", "port",
			 "proto", "req_mime_type", "rep_mime_type", "method",
			 "browser", "user", "src", "dst", "time", "dstdomain", "ident",
			 "snmp_community",
			 ]

	ip_re = hlstr.regex['ip_address']

	def makelistre(list):
		return r'\b(?:'+'|'.join(list)+r')\b'

	tokens = {
		'root': [
			(r'\s+', Whitespace),
			(r'#', Comment, 'comment'),
			(makelistre(keywords), Keyword.Namespace),
			(makelistre(opts), Name.Constant),
			# Actions
			(makelistre(actions), String),
			(r'stats/'+makelistre(actions), String),
			(r'log/'+makelistre(actions)+r'=', String),
			(makelistre(acls), Keyword.Type),
			(ip_re + r'(?:/(?:' + ip_re + r'|\b\d+\b))?', Number.Float),
			(r'(?:\b\d+\b(?:-\b\d+|%)?)', Number),
			(r'\S+', Text),
		],
		'comment': [
			(r'\s*TAG:.*', String.Escape, '#pop'),
			(r'.*', Comment, '#pop'),
		],
	}
class LicornSquidConfigurationFile(ConfigurationFile):
	""" Implements the Squid specific things, on top of the
		generic :class:`~foundations.config.ConfigurationFile` class.

		In particular, the directive order checking methods, required for the
		generic class to check the parsed configuration files or snipplets.

		.. versionadded:: This subclass class was added for the 1.6
			first-real-use implementation.
	"""
	#: We mutualize the lexer between all instances, this avoids consuming memory.
	class_lexer = LicornSquidConfLexer()

	directives_needing_order = (u'http_access',
								u'icp_access',
								u'refresh_pattern')

	directives_dependancies = {
		u'icp_access'  : (u'acl', ),
		u'http_access' : (u'acl', ),
	}

	token_ignored_types = (Whitespace, Comment, String.Escape, )
	new_directive_types = (Keyword.Namespace, )

	def __init__(self, *args, **kwargs):
		ConfigurationFile.__init__(self, lexer=self.__class__.class_lexer, *args, **kwargs)
	def _order_check_common_allow_deny(self, directive_name, directives, special_value=None):
		""" basic check: if last directive is "deny", check that its value is
			"all" and that all other are of the form "allow …" (but not "all"),
			and vice-versa for "deny, allow". """

		if special_value is None:
			# WARNING: 'all' is a constant, not a `Token.Text`.
			# This depends on the lexer contents declaration, BTW.
			special_value = ConfigurationToken(Token.Name.Constant, u'all')

		_allow   = ConfigurationToken(Token.Name.Constant, u'allow')
		_deny    = ConfigurationToken(Token.Name.Constant, u'deny')

		last_value = directives[-1].value

		if not (_allow in last_value or _deny in last_value):
			raise exceptions.BadConfigurationError(_(u'{0}: last "{1}" '
					u'directive must be an "allow" or a "deny" one.').format(
									self.filename, directive_name))

		elif special_value not in last_value:
			if len(directives) > 1 and not self.snipplet:
				raise exceptions.BadConfigurationError(_(u'{0}: last "{1}" '
									u'directive must concern "{2}".').format(
										self.filename, directive_name,
										special_value.value))
	def _order_check_http_access(self, directives):

		# The "manager" part stands alone, it must be checked on its own.
		mandirs  = []
		_manager = ConfigurationToken(Token.Text, u'manager')

		for directive in directives:
			if _manager in directive.value:
				mandirs.append(directive)

		# TODO: this is not feature complete and will fail to check correctly,
		# because 'http_access allow manager localhost' can be last and the
		# test will only check "allow manager" which is True. It should check
		# that they are the only values, not only that they are present.
		if mandirs and not self.snipplet:
			self._order_check_common_allow_deny('http_access', mandirs, _manager)

		if len(directives) > 1 and not self.snipplet:
			self._order_check_common_allow_deny('http_access', directives)
	def _order_check_icp_access(self, directives):
		if len(directives) > 1 and not self.snipplet:
			self._order_check_common_allow_deny('icp_access', directives)
	def _order_check_refresh_pattern(self, directives):
		""" Basic check: refresh_pattern '.' must be the last. """

		if len(directives) > 1 and not self.snipplet:
			if not ConfigurationToken(Token.Text, u'.') in directives[-1].value:
				raise exceptions.BadConfigurationError(_(u'{0}: last "refresh_'
						u'pattern" directive must be for URL "." (dot).').format(
							self.filename))
	def _insert_index_generic(self, directive_name, directive, directives):

		if directives:
			# Insert before the last directive of that kind. This should
			# insert just before any "*_access deny all", "*_access allow all"
			# or "refresh_pattern .", which should be sufficiently precise to
			# make squid not deny localnet or allow anyone (reference: #558).
			#
			# The second value tells insert() where to put the directive in
			# the subset of ordered directives. This is obvious in *this*
			# implementation, but could be different in others.
			return self.blocks.index(directives[-1]), -1

		# No directive of that kind, just insert at the start of the file.
		# No need for complex computations, dependancy checking in the main
		# method will affinate this result afterwards if needed.
		return 0, 0
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
			system boot (once squid is installed, there is no
			:file:`/etc/default/squid` or whatever file where we could
			disable the daemon start). Thus, if available (in server mode),
			this extension **is** enabled.

		.. versionchanged:: 1.6, added the pygments-based configuration parser
			and reworkded the extension to work with `squid2` and `squid3`.
	"""

	def __init__(self):

		ServiceExtension.__init__(self,
			name='squid',
			service_name='squid',

			#: The service type will be more precisely detected
			#: in :meth:`initialize`, depending on the squid version.
			service_type=services.UPSTART
							if LMC.configuration.distro == distros.UBUNTU
							else services.SYSV
		)
		assert ltrace_func(TRACE_EXTENSIONS)
		self.server_only = False

		# No particular controller for this extension, it is a
		# standalone one (no data, just configuration).
		self.controllers_compat = []

		self.defaults = Enumeration()

		# Common data
		self.service_name      = 'squid'
		self.paths.squid_pid   = '/var/run/squid.pid'

		# Squid 2
		self.paths.squid_conf  = '/etc/squid/squid.conf'
		self.paths.squid_bin   = '/usr/sbin/squid'

		# Squid 3
		self.paths.squid3_conf = '/etc/squid3/squid.conf'
		self.paths.squid3_bin  = '/usr/sbin/squid3'
	def initialize(self):
		""" TODO """
		assert ltrace_func(TRACE_SQUID)

		self.version   = None
		self.available = False

		if settings.role == roles.SERVER:
			if os.path.exists(self.paths.squid_bin):
				self.available = True
				self.version   = 2

			elif os.path.exists(self.paths.squid3_bin):
				self.available = True

				# Ubuntu (event 12.04.1) and Debian manage
				# Squid 3 via `service` (not `upstart`).
				self.service_type  = services.SYSV
				self.version       = 3
				self.service_name  = 'squid3'

			else:
				logging.warning2(_(u'{0}: not available because {1} '
					'is not installed (neither version 2 nor 3).').format(
						self.pretty_name, stylize(ST_NAME, 'squid')))

				# in case Squid was deinstalled recently, we should clean.
				self.remove_client_configuration(batch=True)

		else:
			# Squid extension is always available on clients. What it will
			# do depends on server squid extension beiing enabled or not.
			self.available = True

		assert ltrace_func(TRACE_SQUID, 1)
		return self.available
	def update_client_configuration(self, batch=False, auto_answer=None):
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

		assert ltrace_func(TRACE_SQUID)

		if not self.available or not self.enabled:
			return

		self.__build_external_configuration_defaults(minimal=False)

		self.__setup_shell_environment(batch, auto_answer)

		self.__setup_etc_environment(batch, auto_answer)

		if os.path.exists('/usr/bin/gconftool-2'):
			self.__setup_gconf(batch, auto_answer)

		if LMC.configuration.distro in (distros.UBUNTU, distros.DEBIAN):
			self.__setup_apt(batch, auto_answer)

		assert ltrace_func(TRACE_SQUID, 1)
	def remove_client_configuration(self, batch=False, auto_answer=None):
		""" Clean the system from local Squid usage. """

		self.__build_external_configuration_defaults()

		self.__unset_shell_environment(batch, auto_answer)

		self.__unset_etc_environment(batch, auto_answer)

		if os.path.exists('/usr/bin/gconftool-2'):
			self.__unset_gconf(batch, auto_answer)

		if LMC.configuration.distro in (distros.UBUNTU, distros.DEBIAN):
			self.__unset_apt(batch, auto_answer)
	def __build_external_configuration_defaults(self, minimal=True):

		# This will setup different things, based on the current "role". This
		# is the first thing to do because everything else (CLIENT and SERVER)
		# depends on this.
		#
		# NOTE: we need this method to be run even if the extension is not 
		# available, to clean the system from eventual old stuff.

		assert ltrace_func(TRACE_SQUID)

		# Keep the enumeration handy.
		conf = self.defaults
	
		# Shell environment variables.
		conf.client_file     = '/etc/environment'
		conf.client_cmd_http = 'http_proxy'
		conf.client_cmd_ftp  = 'ftp_proxy'

		if LMC.configuration.distro in (distros.UBUNTU, distros.DEBIAN):
			# APT configuration
			conf.apt_conf     = '/etc/apt/apt.conf.d/00proxy'
			conf.apt_cmd_http = 'Acquire::http::Proxy'
			conf.apt_cmd_ftp  = 'Acquire::ftp::Proxy'

		if settings.role == roles.SERVER:
			conf.host   = '127.0.0.1'
			conf.subnet = []

			for iface in network.interfaces():
				iface_infos = netifaces.ifaddresses(iface)

				if 2 in iface_infos:
					conf.subnet.append('%s.0/%s' % (
						iface_infos[2][0]['addr'].rsplit('.', 1)[0],
						network.netmask2prefix(iface_infos[2][0]['netmask'])))

		else:
			conf.host = settings.server_main_address

		if not minimal:
			# Shell / environment configuration must not have double-quotes
			conf.client_cmd_http_value = 'http://%s:%s/' % (conf.host, conf.port)
			conf.client_cmd_ftp_value  = 'ftp://%s:%s/'  % (conf.host, conf.port)
	
			# Whereas APT configuration needs double-quotes
			conf.apt_cmd_http_value = '"http://%s:%s/";' % (conf.host, conf.port)
			conf.apt_cmd_ftp_value  = '"ftp://%s:%s/";'  % (conf.host, conf.port)
	def __squid_configuration_defaults(self):

		datadir = self.paths.data_dir
		opjoin  = os.path.join

		def pre_parse(filename):
			return open(opjoin(datadir, filename)).read().format(
									spool_dir='/var/spool/squid'
												if self.version in (2, None)
												else '/var/spool/squid3',
									log_dir='/var/log/squid'
												if self.version in (2, None)
												else '/var/log/squid3',
									http_port=self.defaults.port,
									localnet=' '.join(self.defaults.subnet))

		# TODO: add peers here. iterate other licorn servers on the same LAN
		# and add a 'cache_peer sibling' directive for them. Then, make them
		# reflect this change and add us to their siblings list.

		directives_for_v2 = pre_parse('squid.v2.conf')
		directives_for_v3 = pre_parse('squid.v3.conf')

		if self.version in (2, None):
			to_add = directives_for_v2
			to_del = directives_for_v3

		else:
			to_add = directives_for_v3
			to_del = directives_for_v2

		for filename2str, action, partial, conflict, snipplet in (
				(pre_parse('squid.common.conf'),       'merge', False,    None,      False),
				(pre_parse('squid.replacements.conf'), 'merge', True,    'replace',  True),
				(pre_parse('squid.licorn_lan_1.conf'), 'merge', True,    'replace',  True),
				(pre_parse('squid.licorn_lan_2.conf'), 'merge', False,    None,      True),
				(to_add,                               'merge', False,    None,      True),
				(to_del,                               'wipe',  False,    None,      True),
			):
			yield filename2str, action, partial, conflict, snipplet
	def check(self, batch=False, auto_answer=None, full_display=True):
		""" .. todo:: write this description. """
		
		if not self.available:
			self.remove_client_configuration(batch, auto_answer)
			return

		# Implicit: if self.enabled: (we are always enabled if available)
		if settings.role != roles.SERVER:
			logging.progress(_(u'{0}: not checking anything in CLIENT '
											u'mode.').format(self.pretty_name))
			return

		LSCF = LicornSquidConfigurationFile

		logging.progress(_(u'{0}: checking Squid\'s current '
									u'configuration…').format(self.pretty_name))

		# This instance will be loaded on checks and unloaded at the end,
		# ensuring that any manual alteration while licornd is running will
		# be taken in account. This avoids useless memory consumption, too.
		current_configuration = LSCF(filename=self.paths.squid_conf
												if self.version == 2
												else self.paths.squid3_conf,
										caller=self.name)

		try:
			self.defaults.port = str(current_configuration.find(
											directive_name='http_port').value)

		except ValueError:
			self.defaults.port = '3128'

		# Update the local system to deal or not with the extension,
		# regarding related "client" configuration (APT, Shell
		# environment, etc).
		#
		# NOTE: this method will setup the remaining part of our internal 
		# configuration, which is needed as a base for 
		# self.__squid_configuration_defaults(). 
		self.update_client_configuration(batch=batch, auto_answer=auto_answer)

		for (text, action, partial, conflict, snipplet
								) in self.__squid_configuration_defaults():
			getattr(current_configuration, action)(
										LSCF(text=text, snipplet=snipplet),
										partial_match=partial,
										on_conflict=conflict)

		if current_configuration.changed:
			# TODO: if batch or logging.ask_for_repair(…)
			current_configuration.save(batch=batch, auto_answer=auto_answer)
			self.service(svccmds.RELOAD)
		
	def __setup_shell_environment(self, batch=False, auto_answer=None):

		os.environ[self.defaults.client_cmd_http]         = self.defaults.client_cmd_http_value
		os.environ[self.defaults.client_cmd_ftp]          = self.defaults.client_cmd_ftp_value
		os.environ[self.defaults.client_cmd_http.upper()] = self.defaults.client_cmd_http_value
		os.environ[self.defaults.client_cmd_ftp.upper()]  = self.defaults.client_cmd_ftp_value

		logging.progress(_(u'{0}: updated variables in our own '
									u'environment…').format(self.pretty_name))
	def __setup_etc_environment(self, batch=False, auto_answer=None):
		env_file = ConfigFile(self.defaults.client_file,
								separator='=', caller=self.name)
		env_need_rewrite = False

		# set 'http_proxy' in /etc/environment
		for cmd, value in (
				(self.defaults.client_cmd_http,	        self.defaults.client_cmd_http_value),
				(self.defaults.client_cmd_http.upper(), self.defaults.client_cmd_http_value),
				(self.defaults.client_cmd_ftp,          self.defaults.client_cmd_ftp_value),
				(self.defaults.client_cmd_ftp.upper(),  self.defaults.client_cmd_ftp_value),
			):

			# HEADS UP: we enclose values in double quotes; this is intended.
			if env_file.has('export ' + cmd):
				if env_file['export ' + cmd] != value:

					env_need_rewrite = True
					env_file.add(key='export ' + cmd,
									value='"%s"' % value, replace=True)
			else:
				env_need_rewrite = True
				env_file.add(key='export ' + cmd,
								value='"%s"' % value)

		if env_need_rewrite:
			env_file.backup_and_save(batch=batch, auto_answer=auto_answer)
	def __setup_gconf(self, batch=False, auto_answer=None):

				# set mandatory proxy params for gnome.
				gconf_values = (
					['string', '--set', '/system/http_proxy/host',
						self.defaults.host ],
					[ 'string', '--set', '/system/proxy/ftp_host',
						self.defaults.host ],
					[ 'string', '--set', '/system/proxy/mode', 'manual' ],
					[ 'bool', '--set', '/system/http_proxy/use_http_proxy', 'true'],
					[ 'int', '--set', '/system/http_proxy/port',
						str(self.defaults.port) ],
					[ 'int', '--set', '/system/proxy/ftp_port',
						str(self.defaults.port) ] )
					# TODO : addresses in ignore_host.
					#[ 'list', '--set', '/system/http_proxy/ignore_hosts', '[]',
					#'--list-type',  'string'])
				base_command = [ 'gconftool-2', '--direct', '--config-source',
					'xml:readwrite:/etc/gconf/gconf.xml.mandatory', '--type' ]

				for gconf_value in gconf_values:
					command = base_command[:]
					command.extend(gconf_value)

					process.execute(command)
	def __setup_apt(self, batch=False, auto_answer=None):

			# set params in apt conf
			apt_file = ConfigFile(self.defaults.apt_conf,
									separator=' ', caller=self.name)
			apt_need_rewrite = False

			if not apt_file.has(key=self.defaults.apt_cmd_http):
				apt_need_rewrite = True
				apt_file.add(key=self.defaults.apt_cmd_http,
					value=self.defaults.apt_cmd_http_value)

			if not apt_file.has(key=self.defaults.apt_cmd_ftp):
				apt_need_rewrite = True
				apt_file.add(key=self.defaults.apt_cmd_ftp,
					value=self.defaults.apt_cmd_ftp_value)

			if apt_need_rewrite:
				apt_file.backup_and_save(batch=batch, auto_answer=auto_answer)
	def __unset_shell_environment(self, batch=False, auto_answer=None):

		for var in (self.defaults.client_cmd_http,
					self.defaults.client_cmd_ftp,
					self.defaults.client_cmd_http.upper(),
					self.defaults.client_cmd_ftp.upper()):

			try:
				del os.environ[var]

			except KeyError:
				# the ENV variable is not set.
				pass
	def __unset_etc_environment(self, batch=False, auto_answer=None):
		env_file = ConfigFile(self.defaults.client_file,
								separator='=', caller=self.name)
		env_need_rewrite = False

		# unset current environment variables
		os.putenv(self.defaults.client_cmd_http, '')
		os.putenv(self.defaults.client_cmd_ftp, '')

		# unset 'http_proxy' in /etc/environment
		for cmd in (self.defaults.client_cmd_http,
					self.defaults.client_cmd_http.upper(),
					self.defaults.client_cmd_ftp,
					self.defaults.client_cmd_ftp.upper()):

			if env_file.has(cmd):
				env_file.remove(key=cmd)
				env_need_rewrite = True

			if env_file.has('export ' + cmd):
				env_file.remove(key='export ' + cmd)
				env_need_rewrite = True

		if env_need_rewrite:
			env_file.backup_and_save(batch=batch, auto_answer=auto_answer)
	def __unset_gconf(self, batch=False, auto_answer=None):
			# unset gnome proxy configuration
		for dir_path in ('xml:readwrite:/etc/gconf/gconf.xml.mandatory',
				'xml:readwrite:/etc/gconf/gconf.xml.defaults'):
				process.execute(['gconftool-2', '--direct', '--config-source',
				dir_path, '--recursive-unset', '/system/http_proxy'])
				process.execute(['gconftool-2', '--direct', '--config-source',
				dir_path, '--recursive-unset', '/system/proxy'])
	def __unset_apt(self, batch=False, auto_answer=None):

		# Unset APT configuration parameters, don't bother if they don't exist.
		try:
			os.unlink(self.defaults.apt_conf)

		except (IOError, OSError), e:
			if e.errno != errno.ENOENT:
				raise

__all__ = ('SquidExtension', 'LicornSquidConfigurationFile', 'LicornSquidConfLexer')
