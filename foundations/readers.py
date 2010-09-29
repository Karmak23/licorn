# -*- coding: utf-8 -*-
"""
Licorn system configuration reader.

The present module rassembles a set of tools to ease the parsing of known
configuration files:
	* classic ^PARAM value$ (login.defs, ldap.conf)
	* classic ^PARAM=value$
	* other special types: smb.conf / lts.conf, squidguard.conf...


Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2
"""

import os, re
from xml.dom                    import minidom
from xml                        import dom as xmldom
from xml.parsers                import expat
from licorn.foundations         import exceptions

def to_type_semi(value):
	"""Find the right type of value and convert it, but not for all types. """
	if value.isdigit():
		return int(value)
	else:
		return value

def to_type_full(value):
	"""Find the right type of value and convert it. """
	if value.isdigit():
		return int(value)
	elif value.lower() in ('no', 'false'):
		return False
	elif value.lower() in ('yes', 'true'):
		return True
	else:
		return value

to_type = {
	'semi':	to_type_semi,
	'full': to_type_full
	}

def very_simple_conf_load_list(filename):
	""" Read a very simple file (one value per line)
		and return a list built from the values.
		Typical use case: /var/lib/squidguard/db/customblacklist/urls,
		/etc/shells, /etc/licorn/privileges-whitelist.conf
	"""

	retlist = []

	def parse_line(line):
		if line[0] != '#' and line != '\n':
			retlist.append(line.strip())

	map(parse_line, open(filename , 'r'))

	return retlist
def	simple_conf_load_dict(filename=None, data=None, convert='semi'):
	""" Read a simple configuration file ("param value" on each line)
		and return a dictionary of param->value filled with the directives
		contained in the configuration file.

		Warning, for performance optimisation in later comparisons, digit
		values are converted to int().

		Typical use case: /etc/login.defs, /etc/ldap/ldap.conf
	"""
	confdict = {}
	conf_re	 = re.compile("^\s*(?P<param>\w+)\s+(?P<value>(\S+\s*)+)$")

	def parse_fields(line):
		directive = conf_re.match(line)
		if directive:
			dicts = directive.groupdict()
			key = dicts['param']
			confdict[key] = to_type[convert](dicts['value'])

	if filename:
		data = open(filename , "r").read()

	map(parse_fields, data.split('\n'))

	return confdict
def	simple_conf_load_dict_lists(filename):
	""" Read a simple configuration file ("param value1 [value2 ...]" on each line)
		and return a dictionary of param -> [ list of values ] filled with the directives
		contained in the configuration file.

		Typical use case: /etc/nsswitch.conf
	"""
	confdict = {}
	conf_re	 = re.compile("^\s*(?P<database>\w+):(?P<types>(\s+[\[=\]\w]+)+)\s*$")

	def parse_fields(line):
		directive = conf_re.match(line[:-1])
		if directive:
			key = directive.group("database")
			types = re.findall('[\[=\]\w]+', directive.group("types"))
			confdict[key] = types

	map(parse_fields, open(filename, "r" ))

	return confdict
def	shell_conf_load_dict(filename=None, data=None, convert='semi'):
	""" Read a shell configuration file with variables (VAR=value on each line)
		return a dictionary of param->value filled with the variables.

		Typical use case: /etc/licorn/names.conf, /etc/adduser.conf, /etc/licorn/licorn.conf
	"""
	confdict = {}
	conf_re	 = re.compile("^\s*(?P<param>[\w.]+)\s*=\s*[\"]?(?P<value>[^\"]+)[\"]?\s*$", re.LOCALE | re.UNICODE)

	def parse_fields(line):
		directive = conf_re.match(line)
		if directive:
			dicts = directive.groupdict()
			key = dicts['param']
			confdict[key] = to_type[convert](dicts['value'])
			#sys.stderr.write('found directive %s → %s.\n' % (key, dicts['value']))

	if filename:
		data = open(filename , "r").read()

	map(parse_fields, data.split('\n'))

	return confdict
def ug_conf_load_list(filename):
	""" Read a configuration file and return a list -> list of value
		Typical use case: /etc/passwd, /etc/group, /etc/licorn/group{s}
	"""
	return map(lambda x: x[:-1].split(":"), open(filename , "r"))
def	dnsmasq_read_conf(filename=None, data=None, convert='semi'):
	""" Read a dnsmasq.conf file into a dict, using these conversion patterns:

			single-named-directive           -> s-n-d = True
			named-directive=single-value     -> n-d = s-v
			named-directive=/file/name       -> n-d = /f/n
			named-directive=/value1/value2/  -> n-d = [value1, value2]
			                                 -> n-d_sep = '/'
			named-directive=value1,value2    -> n-d = [value1, value2]
			                                 -> n-d_sep = ','

		If a named-directive is repeated (typical for "dhcp-host"), the
		different values are added to a list, instead of overwriting.
	"""

	from licorn.foundations.pyutils import masq_list, add_or_dupe
	from licorn.foundations.hlstr   import cregex

	def parse_fields(line):
		""" barely parse a directive into a simple but usable object. """
		try:
			if cregex['conf_comment'].match(line) != None:
				# skip empty lines & comments
				return

			name, value = line.split('=')
			if value.find(','):
				add_or_dupe(confdict, name, masq_list(name,
					value.split(','), ','))
			elif value.find('/'):
				if os.path.exists(value):
					add_or_dupe(confdict, name, value)
				else:
					add_or_dupe(confdict, name, masq_list(name,
						value.split('/'), '/'))
			else:
				pass
		except ValueError:
			add_or_dupe(confdict, line, True)

	if filename:
		data = open(filename , "r").read()

	confdict = {}

	map(parse_fields, data.split('\n'))

	return confdict
def	dnsmasq_read_leases(filename=None, data=None, convert='semi'):
	""" Read the dnsmasq lease file into a dict indexed on mac addresses.
		if multiple leases for a same MAC are found, the one with the most
		recent expiry time is kept.

		for reference:
		http://lists.thekelleys.org.uk/pipermail/dnsmasq-discuss/2005q1/000143.html
	"""

	from licorn.foundations.hlstr import cregex

	def parse_fields(line):

		if cregex['conf_comment'].match(line) != None:
			# skip empty lines & comments
			return

		expiry, mac, ipaddr, hostname, clientid = line.split(' ')

		if (not confdict.has_key(mac)) or expiry > confdict[mac]['expiry']:
				confdict[mac] = {
					'hostname':	hostname,
					'ip': ipaddr,
					'clientid': clientid,
					'expiry': expiry
				}

	if filename:
		data = open(filename , "r").read()

	confdict = {}

	map(parse_fields, data.split('\n'))

	return confdict
def profiles_conf_dict(filename):
	""" Read a user profiles file (XML format) and return a dictionary
		of profilename -> (dictionary of param -> value)
	"""
	try:
		if os.lstat(filename).st_size == 0:
			return {}

		dom = minidom.parse(filename)
		confdict = {}

		def parse_profile(profile):
			name = getProfileData(profile, "name").pop()
			comment = getProfileData(profile, "description").pop()
			skel_dir = getProfileData(profile, "profileSkel").pop()
			shell = getProfileData(profile, "profileShell").pop()
			primarygroup = getProfileData(profile, "groupName").pop()
			# «groups» XML tag, contains nothing except «group» children
			try:
				groupselement = profile.getElementsByTagName("memberGid").pop()
				# many groups, keep a list, don't pop()
				groups = getProfileData(groupselement, "groupName")
			except IndexError:
				# this profile has no default groups to set users in.
				# this is awesome, but this could be normal.
				groups = []

			quota = getProfileData(profile, "profileQuota").pop()

			groups.sort()

			confdict[primarygroup] = {
				'name': name,
				'description': comment,
				'profileSkel': skel_dir,
				'groupName': primarygroup,
				'memberGid': groups,
				'profileQuota': quota,
				'profileShell': shell
				}

		map(parse_profile, dom.getElementsByTagName("profile"))

		return confdict
	except exceptions.CorruptFileError, e:
		e.SetFilename(filename)
		raise e
	except xmldom.DOMException, e:
		raise exceptions.CorruptFileError(filename, str(e))
	except expat.ExpatError, e:
		raise exceptions.CorruptFileError(filename, str(e))
	except (OSError, IOError):
		# FIXME: do something when there is no profiles on the system...
		return {}
def getProfileData(rootelement, leaftag, isoptional=False):
	""" Return a list of content of a leaftag (tag which has no child)
		which has rootelement as parent.
	"""
	empty_allowed_tags = [ 'description' ]
	data = []
	tags = rootelement.getElementsByTagName(leaftag)

	if tags == [] and rootelement.nodeName != "memberGid":
		raise exceptions.CorruptFileError(reason="The tag <" + leaftag + "> was not found.")

	for e in tags:
		for node in e.childNodes:
			if node.parentNode.parentNode == rootelement: # needed to ignore the other levels
				data.append(unicode(node.data))

	if data == []:
		if leaftag not in empty_allowed_tags and rootelement.nodeName != "memberGid":
			raise exceptions.CorruptFileError(reason="The tag <" + leaftag + "> must not have an empty value.")
		else:
			data = ['']

	return data
def timeconstraints_conf_dict(filename):
	""" Read the squiGuard configuration file and return a dictionary of timespacename -> (dictionnary of param -> value)
	"""
	confdict	= {}
	declaration_re		= re.compile("^\s*time\s*(?P<name>\w*)\s*{")
	entry_re			= re.compile("^\s*weekly\s*(?P<weekdays>[smtwhfa]{1,7})\s*(?P<starthours>\d\d):(?P<startminutes>\d\d)-(?P<endhours>\d\d):(?P<endminutes>\d\d)\s*")

	acl_found = "" # The acl we are parsing (in order to find redirection
	acl_re		= re.compile("^\s*\w*\s*outside\s*(?P<timespace>\w*)\s*{")
	redirection_re		= re.compile("^\s*redirect\s*(?P<url>.*)\s*")
	conffile	= open( filename , "r" )

	inblock = False # Are we in a timespace block ?
	name = "" # timespace name

	for line in conffile:
		# Search time constraints
		if inblock:
			mo_e = entry_re.match(line)
			if mo_e is not None: # An entry is found
				entry = mo_e.groupdict()
				confdict[name]["constraints"].append(entry)
		mo_d = declaration_re.match(line)
		if mo_d is not None: # A declaration is found
			inblock = True
			name = mo_d.groupdict()["name"]
			confdict[name] = {"constraints": []}

		# Search redirections in acl
		if acl_found != "":
			mo_r = redirection_re.match(line)
			if mo_r is not None:
				url = mo_r.groupdict()["url"]
				confdict[acl_found]["redirection"] = url
				acl_found = ""
		mo_a = acl_re.match(line)
		if mo_a is not None:
			acl_found = mo_a.groupdict()["timespace"]
	return confdict
