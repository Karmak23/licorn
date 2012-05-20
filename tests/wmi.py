#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn testsuite for licorn.wmi objects.

Copyright (C) 2007-2010 Olivier Cortès <oc@meta-it.fr>
Copyright (C) 2010 Robin Lucbernet <rl@meta-it.fr>

Licensed under the terms of the GNU GPL version 2.
"""

import gettext
gettext.install('licorn', unicode=True)

import os, sys, curses, re, gzip
import urllib2, urllib, httplib, hashlib
import tempfile, base64
from subprocess                import Popen, PIPE, STDOUT

from licorn.foundations        import logging, exceptions
from licorn.foundations        import ttyutils, process
from licorn.foundations.styles import *

from licorn.tests import *

from licorn.core.configuration import LicornConfiguration

configuration = LicornConfiguration()

""" parameters to connect to the wmi """
WMI_url  = 'https://localhost:3356'
username = 'wmitest'
password = 'wmitest'

class Scenario:
	def __init__(self, cmds, descr=None):
		self.cmds = {}
		self.cmd_counter = 0
		for cmd in cmds:
			self.cmds[self.cmd_counter] = cmd
			self.cmd_counter += 1
		self.descr = descr
		self.counter = None
		self.hash = hashlib.sha1("%s-%s" % (str(cmds),descr)).hexdigest()
		self.base_path = "data/wmitest/%s" % self.hash
	def set_number(self, num):
		""" set a number to the scenario. """
		self.counter = num
	def ask_for_webbrowser(self, output=None,file1=None, file2=None, mode='single'):
		""" if --webbrowser options, diplay an invitation to display html
		page result in a browser. """
		# display only one page.
		if mode == 'single' and output != None:
			if logging.ask_for_repair('''Do you want to see the html page '''
			''' in a webbrowser ?'''):
				handle, tmpfilename = tempfile.mkstemp()
				open(tmpfilename, 'w').write(output)
				p = Popen(['chromium-browser', tmpfilename], stdout=PIPE)
		# display two pages (new and old version)
		if mode == 'multi' and file1 != None and file2 != None:
			if logging.ask_for_repair('''Do you want to see the 2 html pages '''
			''' in a webbrowser ? (the first page opened is the new result)'''):
				p = Popen(['chromium-browser', file1, file2], stdout=PIPE)
	def runCommand(self, cmd, cmdnum):
		""" run the command """
		output = strip_moving_data(execute(cmd))
		if output != None:
			# Does a scenario exist with the same hash ?
			if os.path.exists('%s/%s' % (self.base_path, cmdnum)):
				if os.path.exists('%s/%s/out.txt.gz' % (self.base_path, cmdnum)):
					ref_output = gzip.open('%s/%s/out.txt.gz' %
						(self.base_path, cmdnum), 'r').read()
					gz_file = True
				else:
					ref_output = open('%s/%s/out.txt' %
						(self.base_path, cmdnum)).read()
					gz_file = False
				if ref_output != output:
					ttyutils.clear_term()
					handle, tmpfilename = tempfile.mkstemp()
					if gz_file:
						handle2, tmpfilename2 = tempfile.mkstemp()
						open(tmpfilename2, 'w').write(ref_output)
					open(tmpfilename, 'w').write(strip_moving_data(output))
					diff_output = process.execute(['diff', '-u',
						tmpfilename2 if gz_file else
							'%s/%s/out.txt' % (self.base_path, cmdnum),
						tmpfilename])[0]
					logging.warning(
						'''%s\ncommand #%s/%s failed (sce#%s).\n%s''' % (
						diff_output,stylize(ST_OK, cmdnum),
						stylize(ST_OK, len(self.cmds)),
						stylize(ST_OK, self.counter),
						self.show_commands(highlight_num=cmdnum-1)))
					if options.webbrowser:
						self.ask_for_webbrowser(file1=tmpfilename,file2=tmpfilename2,
							mode='multi')
					if logging.ask_for_repair('''Should I keep the new '''
						'''trace as reference for future runs?'''):
						self.SaveOutput(cmdnum, output)
					else:
						raise exceptions.LicornRuntimeException(
							'command "%s" failed.\nPath: %s.' % (
								testsuite.cmdfmt(self.cmds[cmdnum-1]), '%s/%s/*' % (
									self.base_path, cmdnum)))
				else:
					logging.notice('command #%d \'%s\' completed successfully.' % (
					cmdnum, stylize(ST_NAME,small_cmd_wmi(self.cmds[cmdnum-1]))))
			else:
				ttyutils.clear_term()
				logging.notice('''%s\n\nno reference output for scenario %s : %s (cmd %s/%s)'''
					'''\n\n%s''' % (
						strip_moving_data(output),
						self.counter,
						self.descr,
						cmdnum,
						len(self.cmds),
						self.show_commands(highlight_num=cmdnum-1)))
				if options.webbrowser:
					self.ask_for_webbrowser(output=output)
				if logging.ask_for_repair('''is this output good to keep as '''
					'''reference for future runs?'''):
					# Save the output for future references and comparisons
					self.SaveOutput(cmdnum, output)
				else:
					logging.error('''you MUST have a reference output; please '''
						'''fix code or rerun this test.''')
	def Run(self):
		""" run the scenario """
		logging.notice('Running scenario %s : %s' % (
			stylize(ST_NAME, self.counter),
			stylize(ST_NAME, self.descr)))
		cmd_counter = 1
		for cmd in self.cmds:
			self.runCommand(self.cmds[cmd_counter-1],cmd_counter)
			cmd_counter += 1
		logging.notice('End run scenario %s : %s' % (
			stylize(ST_NAME, self.counter),
			stylize(ST_NAME, self.descr)))
	def show_commands(self, highlight_num):
		""" output all commands, to get an history of the current scenario,
			and higlight the current one. """
		data = ''
		cmdcounter = 0
		for cmd in self.cmds:
			if cmdcounter < highlight_num:
				data += '	%s\n' % testsuite.cmdfmt(self.cmds[cmdcounter],
					prefix='  ')
			elif cmdcounter == highlight_num:
				data += '	%s\n' % testsuite.cmdfmt_big(self.cmds[cmdcounter],
					prefix='> ')
			elif cmdcounter > highlight_num:
				data += '	%s%s\n' % (
					testsuite.cmdfmt(self.cmds[cmdcounter],
						prefix='  '),
					'\n	%s' % testsuite.cmdfmt(u'[…]', prefix='  ') \
						if len(self.cmds) > cmdcounter+1 \
						else '')
				break
			cmdcounter += 1
		return data
	def SaveOutput(self, cmdnum, output):
		""" save output of the command """
		try:
			os.makedirs('%s/%s' % (self.base_path, cmdnum))
		except (OSError, IOError), e:
			if e.errno != 17:
				raise e
		if len(output) > 1024:
			file = gzip.GzipFile(
				filename='%s/%s/out.txt.gz' % (self.base_path, cmdnum),
				mode='wb',
				compresslevel=9)
		else:
			file = open('%s/%s/out.txt' % (self.base_path, cmdnum), 'w')
		file.write(strip_moving_data(output))
		file.close()

def translate_command(commands):
	""" translate scenario commands to URLs for WMI. """
	# possible cmds :
	#	GET home
	#	GET users
	#	GET groups
	#	ADD/MOD/DEL users
	#	ADD/MOD/DEL groups
	# 	LOCK/UNLOCK users
	# 	LOCK/UNLOCK groups (for permissive argument)
	cmd = []
	if commands[0] == 'GET':
		cmd.append('GET')
		possible_request = ['home', 'users', 'groups']
	elif commands[0] in ['ADD', 'MOD', 'DEL']:
		cmd.append('POST')
		possible_request = ['users', 'groups']
	elif commands[0] in ['LOCK', 'UNLOCK']:
		cmd.append('POST')
		possible_request = ['users', 'groups']
	else:
		raise exceptions.BadArgumentError('''The command %s is not '''
		'''allowed in this context. Allowed arguments are : %s''' %
			(stylize(ST_BAD,commands[1]),
			(stylize(ST_NAME,['GET','ADD','DEL','MOD']))))
	if commands[1] in possible_request:
		request = "/" + commands[1] if commands[1] != 'home' else ''
		action = ''
		if commands[0] == 'ADD':
			action = '/create'
		elif commands[0] == 'DEL':
			action = '/delete'
		elif commands[0] == 'MOD':
			action = '/record'
		elif commands[0] == "LOCK":
			action = '/lock'
		elif commands[0] == "UNLOCK":
			action = '/unlock'
		link_to_file = WMI_url + request + action
		cmd.append(link_to_file)

		if commands[0] not in ['GET']:
			try:
				cmd.append(commands[2])
			except:
				raise exceptions.BadArgumentError('''You need to specify '''
				'''arguments for the command : %s''' %
				stylize(ST_NAME,commands))
	else:
		raise exceptions.BadArgumentError('''The argument %s is not '''
		'''allowed in this context. Allowed arguments are : %s''' %
			(stylize(ST_BAD,commands[1]),
			(stylize(ST_NAME,possible_request))))
	return cmd


def execute(cmd):
	""" execute a command. """
	command = translate_command(cmd)
	try:
		try:
			data=urllib.urlencode(command[2])
		except IndexError:
			data=None
		req = urllib2.Request(command[1], data if data != None else None)
		# send authentification
		base64string = base64.encodestring(
			'%s:%s' % (username, password))[:-1]
		authheader = "Basic %s" % base64string
		req.add_header("Authorization", authheader)
		# get the code of the page
		handle = urllib2.urlopen(req)
		output = handle.read()
		return output
	except urllib2.URLError, e:
		logging.warning('error on url %s (was %s ; headers:%s).' % (
			stylize(ST_URL, command[1]), e, stylize(ST_BAD, e.headers)))
	except httplib.BadStatusLine, e:
		logging.warning('bad status line on url %s (was %s).' % (
			stylize(ST_URL, command[1]), e))
def clean_system():
	""" clean the system. """
	test_message('''cleaning system from previous runs.''')
	for argument in (
		['user', '''user_test,user_test2,user_test3,user_test4,toto,tototest,'''
		'''user_test5''',
			 '--no-archive', '-v' ],
		['group', '''group_test,group_test2,group_test3''',
			'--no-archive', '-v' ],
		):
		p = Popen([ 'python' ] + [ '../interfaces/cli' + '/del.py'] + argument,
			stdout=PIPE, stderr=STDOUT)
		output = p.stdout.read()
	test_message('''system cleaned from previous testsuite runs.''')
def browse_url(url):
	urls = get_all_urls(url)
def get_all_urls(start_url):
	""" browse urls of the testsuite in order to find dead links """
	urls = set()
	urls_to_walk = set([start_url])
	while True:
		if urls_to_walk != set():
			url_to_walk = urls_to_walk.pop()
		else:
			break
		try:
			if Testsuite.verbose:
				logging.notice('walking across url = %s' % url_to_walk)
			req = urllib2.Request(url_to_walk)
			base64string = base64.encodestring(
				'%s:%s' % (username, password))[:-1]
			authheader = "Basic %s" % base64string
			req.add_header("Authorization", authheader)
			handle = urllib2.urlopen(req)
			output = handle.read()
		except urllib2.URLError, e:
			logging.warning('error on url %s (was %s).' % (
				stylize(ST_URL, url_to_walk), e))
		except httplib.BadStatusLine, e:
			logging.warning('bad status line on url %s (was %s).' % (
				stylize(ST_URL, url_to_walk), e))
		else:
			for m in re.finditer(r'''<a href=['"]([^"']*)['"][^>]*>''', output):
				url = m.group(1)
				if url[0:6].lower() != 'mailto' and url not in  ('/', '#') \
					and url.lower().find('dev.licorn.org') == -1:
					prefix = ''
					if url[0:6].lower().find('http://') == -1:
						prefix = WMI_url

					final_url = '%s%s' % (prefix, m.group(1))
					if final_url not in urls:
						if Testsuite.verbose:
							logging.notice('GOT new url = %s' % final_url)
						urls.add(final_url)
						urls_to_walk.add(final_url)
	return urls

def strip_moving_data(output):
	""" strip dates from warnings and traces, else outputs and references
	always compare false ."""
	return re.sub(
        r'''(\d\d? years?, )?(\d\d? months?, )?(\d\d? days?, )?'''
        '''(\d{1,2} hours?, )?(\d\d? mins?, )?\d\d? secs?''', r' [UPTIME] ',
		re.sub(
			r'(load average:).*(</td>)', r'\1 [LOAD AVERAGE] \2',
			re.sub(
				r'''(<div id="timer">Core execution time:).*(&nbsp;seconds.'''
				'''</div>)''', r'\1 [CORE EXECUTION TIME] \2',
				re.sub(
					r'(Physical\smemory:).*\stotal,(<br />)',
					r'\1 [PHYSICAL MEMORY] \2',
					re.sub(
						r'''\d\.\d\d\s(Gb\sfor\sprograms,|Gb\sfor\scache,'''
						'''|Gb\sfor\sbuffers.)''', r' [PHYSICAL MEMORY] \1',
						re.sub(
							r'(Virtual\smemory:).*\.(</td>)',
							r'\1 [VIRTUAL MEMORY] \2',
							re.sub(r'''(Users:)\s<strong>\d</strong>\stotal,'''
							'''\s<strong>\d\scurrently\sconnected</strong>\.''',
								r'\1 [USERS]',
								re.sub(r'''(\.\d\d\d\d\d\d\d\d-\d\d\d\d\d\d|'''
								'''\[\d\d\d\d/\d\d/\d\d\s\d\d:\d\d:\d\d\.\d\d'''
								'''\d\d\]\s)''', r'[D/T] ',
								output))))))))
uname='user_test'
gname='group_test'
upw='password'

def test_get(testsuite):
	""" tests on gets. """
	testsuite.add_scenario(Scenario([
		[ 'GET', 'home' ],
		[ 'GET', 'users' ],
		[ 'GET', 'groups' ],
		],
		descr="test various get"
		))
def test_users(testsuite):
	""" tests on users. """
	testsuite.add_scenario(Scenario([
		# should be OK
		[ 'ADD', 'users', { 'loginShell' : '/bin/bash',
							'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# should fail (already exists)
		[ 'ADD', 'users', { 'loginShell' : '/bin/bash',
							'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# should fail (invalid shell)
		[ 'ADD', 'users', { 'loginShell' : '/bin/no_shell',
							'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# should be OK
		[ 'ADD', 'users', {	'loginShell' : '/bin/sh',
							'login' : '%s2' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		[ 'ADD', 'groups', {'name'	:	'%s' % gname,
							'skel'	:	'/etc/skel' }],
		# should be OK
		[ 'ADD', 'users', { 'gecos' : 'toto test',
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# should be OK
		[ 'ADD', 'users', { 'login' : '%s5' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# should be OK
		[ 'ADD', 'users', { 'loginShell' : '/bin/bash',
							'firstname' : 'test firstname',
							'lastname' : 'test lastname',
							'standard_groups_dest' : '%s' % gname,
							'login' : '%s3' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		[ 'GET', 'groups' ],
		[ 'ADD', 'groups', {'name' : '%s2' % gname,
							'skel' : '/etc/skel' }],
		# add a user with two different groups
		[ 'ADD', 'users', { 'loginShell' : '/bin/bash',
							'standard_groups_dest' : '%s,%s2' % (gname,gname),
							'login' : '%s4' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		[ 'GET', 'groups' ],
		[ 'DEL', 'groups', {'name' : '%s' % gname,
							'sure' : True }],
		[ 'DEL', 'groups', {'name' : '%s2' % gname,
							'sure' : True }],
		[ 'DEL', 'users', { 'login' : '%s' % uname,
							'sure' : True}],
		[ 'DEL', 'users', { 'login' : '%s2' % uname,
							'sure' : True }],
		[ 'DEL', 'users', { 'login' : '%s3' % uname,
							'sure' : True }],
		[ 'DEL', 'users', { 'login' : '%s4' % uname,
							'sure' : True }],
		[ 'DEL', 'users', { 'login' : '%s5' % uname,
							'sure' : True }],
		[ 'DEL', 'users', { 'login' : 'tototest',
							'sure' : True }],
		],
		descr="add user by different way and with different parameters"
		))

	testsuite.add_scenario(Scenario([
		[ 'ADD', 'users', { 'login':'%s' % uname,
							'password':'%s' % upw,
							'password_confirm':'%s' % upw }],
		[ 'MOD', 'users', { 'login':'%s' % uname,
							'gecos':'testGECOS',
							'loginShell':'/bin/bash',}],
		[ 'MOD', 'users', { 'login':'%s' % uname,
							'gecos':'testGECOS',
							'loginShell':'/bin/sh',}],
		[ 'LOCK', 'users', { 'login': '%s' % uname,
							 'sure':True }],
		[ 'UNLOCK', 'users', { 'login': '%s' % uname,
							 'sure':True }],
		[ 'DEL', 'users', { 'login':'%s' % uname,
							'sure':True }],
		],
		descr="modify a user"
		))

	testsuite.add_scenario(Scenario([
		# every args not given
		[ 'ADD', 'users', { 'gecos' : 'toto'}],
		[ 'ADD', 'users', { 'gecos' : 'toto 2'}],
		[ 'ADD', 'users', { 'login' : '%s' % uname }],
		[ 'ADD', 'users', {	'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		[ 'ADD', 'users', { 'loginShell' : '/bin/bash'}],
		# try to fake loginShell
		[ 'ADD', 'users', { 'loginShell' : '`cat /etc/password`'}],
		[ 'ADD', 'users', { 'loginShell' : "exec(['cat /etc/password']) in globals(), locals()"}],
		[ 'ADD', 'users', { 'loginShell' : '`cat /etc/password`',
							'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		[ 'ADD', 'users', { 'loginShell' : "exec(['cat /etc/password']) in globals(), locals()",
							'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		[ 'ADD', 'users', { 'loginShell' : "os.system('print \'/bin/sh\'')",
							'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# false shell + user root
		[ 'ADD', 'users', { 'loginShell' : '/bin/false',
							'login' : 'root',
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# everything correct but user root
		[ 'ADD', 'users', { 'loginShell' : '/bin/bash',
							'login' : 'root',
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# passwords mismatch
		[ 'ADD', 'users', { 'loginShell' : '/bin/bash',
							'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%sZZ' % upw }],
		],
		descr="test situations where add_user() should fail"
		))

	testsuite.add_scenario(Scenario([
		# without sure
		[ 'DEL', 'users', { 'login' : 'root' }],
		# try to del system user
		[ 'DEL', 'users', { 'login' : 'root',
							'sure' : True }],
		# try to fake login
		[ 'DEL', 'users', { 'login' : '`cat /etc/passwd`',
							'sure' : True }],
		],
		descr="test situations where del_user() should fail"
		))

	testsuite.add_scenario(Scenario([
		[ 'ADD', 'users', { 'loginShell':'/bin/bash',
							'login':'%s' % uname,
							'password':'%s' % upw,
							'password_confirm':'%s' % upw }],
		# without all necessary args
		[ 'MOD', 'users', { 'loginShell' : '/bin/sh' }],
		[ 'MOD', 'users', { 'login' : '%s' % uname }],
		[ 'MOD', 'users', { 'firstname' : 'Robin' }],
		[ 'MOD', 'users', { 'lastname' : 'Nibor' }],
		[ 'MOD', 'users', { 'standard_groups_source' : '%s' % gname }],
		[ 'MOD', 'users', { 'privileged_groups_source' : '%s' % gname }],
		[ 'MOD', 'users', { 'responsible_groups_source' : '%s' % gname }],
		[ 'MOD', 'users', { 'guest_groups_source' : '%s' % gname }],
		[ 'MOD', 'users', { 'standard_groups_dest' : '%s' % gname }],
		[ 'MOD', 'users', { 'privileged_groups_dest' : '%s' % gname }],
		[ 'MOD', 'users', { 'responsible_groups_dest' : '%s' % gname }],
		[ 'MOD', 'users', { 'guest_groups_dest' : '%s' % gname }],
		# try to delete/add user from/to nonexisting groups
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'standard_groups_source' : 'thisGroupDoesntExist'}],
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'privileged_groups_source' : 'thisGroupDoesntExist'}],
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'responsible_groups_source' : 'thisGroupDoesntExist'}],
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'guest_groups_source' : 'thisGroupDoesntExist'}],
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'standard_groups_dest' : 'thisGroupDoesntExist'}],
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'privileged_groups_dest' : 'thisGroupDoesntExist'}],
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'responsible_groups_dest' : 'thisGroupDoesntExist'}],
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'guest_groups_dest' : 'thisGroupDoesntExist'}],
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'standard_groups_source' : 'thisGroupDoesntExist',
							'privileged_groups_source' : 'thisGroupDoesntExist',
							'responsible_groups_source' : 'thisGroupDoesntExist',
							'guest_groups_source' : 'thisGroupDoesntExist',
							'standard_groups_dest' : 'thisGroupDoesntExist',
							'privileged_groups_dest' : 'thisGroupDoesntExist',
							'responsible_groups_dest' : 'thisGroupDoesntExist',
							'guest_groups_dest' : 'thisGroupDoesntExist'}],
		# mod a system account
		[ 'MOD', 'users', { 'login' : 'root',
							'loginShell' : '/bin/sh'}],
		# with uncorrect shell
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'loginShell' : '/bin/bad_shell'}],
		# passwords mismatch
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'password' : 'XXXXXXXX'}],
		# passwords mismatch
		[ 'MOD', 'users', { 'login' : '%s' % uname,
							'password' : 'XXXXXXXX',
							'password_confirm':'%s' % upw}],
		[ 'DEL', 'users', { 'login' : '%s' % uname,
							'sure' : True }],
		],
		descr="test situations where mod_user() should fail"
		))
def test_groups(testsuite):
	""" tests on groups. """
	testsuite.add_scenario(Scenario([
		# should be OK
		[ 'ADD', 'groups', {'name' : '%s' % gname,
							'skel' : '/etc/skel',
							'description' : 'testDesc',
							'permissive' : True }],
		#should fail (invalid skel)
		[ 'ADD', 'groups', {'name' : '%s2' % gname,
							'skel' : '/etc/skel2',
							'description' : 'testDesc2' }],
		#should be OK
		[ 'ADD', 'groups', {'name' : '%s2' % gname,
							'skel' : '/etc/skel',
							'description' : 'testDesc2' }],
		[ 'UNLOCK', 'groups', {'name' : '%s2' % gname,
							   'sure' : True}],
		[ 'LOCK', 'groups', {'name' : '%s2' % gname,
							 'sure' : True}],
		[ 'ADD', 'groups', {'name' : '%s3' % gname,
							'skel' : '/etc/skel',
							'description' : 'testDesc3' }],
		[ 'DEL', 'groups', {'name' : '%s' % gname,
							'sure' : True }],
		[ 'DEL', 'groups', {'name' : '%s2' % gname,
							'sure' : True }],
		[ 'DEL', 'groups', {'name' : '%s3' % gname,
							'sure' : True }],

		],
		descr="add groups by different way and with different parameters"
		))

	testsuite.add_scenario(Scenario([
		[ 'ADD', 'groups', {'name' : '%s' % gname,
							'skel' : '/etc/skel',
							'description' : 'testDesc',
							'permissive' : True }],
		[ 'ADD', 'groups', {'name' : '%s2' % gname,
							'skel' : '/etc/skel',
							'description' : 'testDesc2' }],
		[ 'ADD', 'groups', {'name' : '%s3' % gname,
							'skel' : '/etc/skel',
							'description' : 'testDesc2',
							'permissive' : False }],
		[ 'DEL', 'groups', {'name' : '%s' % gname,
							'sure' : False }],
		[ 'DEL', 'groups', {'name' : '%s' % gname,
							'sure' : True }],
		[ 'DEL', 'groups', {'name' : '%s2' % gname,
							'sure' : True }],
		[ 'DEL', 'groups', {'name' : '%s3' % gname,
							'sure' : True }],
		],
		descr="test permissive/not permissive on groups"
		))
	testsuite.add_scenario(Scenario([
		[ 'ADD', 'groups', {'name' : '%s' % gname,
							'skel' : '/etc/skel' }],
		[ 'ADD', 'users', { 'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		[ 'ADD', 'users', { 'login' : '%s2' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'description' : 'testDesc2' }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'permissive' : True }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'permissive' : False }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'members_dest' : '%s' % uname }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'members_source' : '%s' % uname }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'members_dest' : '%s,%s2' % (uname,uname) }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'members_source' : '%s,%s2' % (uname,uname) }],
		[ 'DEL', 'users', {'login' : '%s' % uname,
							'sure' : True }],
		[ 'DEL', 'users', {'login' : '%s2' % uname,
							'sure' : True }],
		[ 'DEL', 'groups', {'name' : '%s' % gname,
							'sure' : True }],
		],
		descr="modify on groups"
		))
	testsuite.add_scenario(Scenario([
		# every args not given
		[ 'ADD', 'groups', { 'name' : 'toto'}],
		[ 'ADD', 'groups', { 'name' : 'toto 2'}],
		[ 'ADD', 'groups', { 'name' : '%s' % gname }],
		[ 'ADD', 'groups', { 'skel' : '/etc/skeldoesntexist' }],
		[ 'ADD', 'groups', { 'skel' : '`cat /etc/passwd`' }],
		[ 'ADD', 'groups', { 'permissive' : '`echo True;`' }],
		[ 'ADD', 'groups', { 'permissive' : "os.system('print True')" }],
		[ 'ADD', 'groups', { 'description' : 'blabla' }],
		# bad args
		#[ 'ADD', 'groups', {'name' : '%s' % gname,
		#					'skel' : '/etc/skel',
		#					'description' : 'testDesc',
		#					'permissive' : "`cat /etc/passwd`" }],
		[ 'ADD', 'groups', {'name' : 'root',
							'skel' : '/etc/skel',
							'description' : 'testDesc',
							'permissive' : False }],
		[ 'ADD', 'groups', {'name' : '%s' % gname,
							'skel' : '/etc/skeldoesntexist',
							'description' : 'testDesc',
							'permissive' : False }],
		[ 'ADD', 'groups', {'name' : '%s' % gname,
							'skel' : '/etc/skel',
							'description' : '`cat /var/log/apt/history.log',
							'permissive' : False }],
		],
		descr="test situations where add_group() should fail"
		))

	testsuite.add_scenario(Scenario([
		# without sure
		[ 'DEL', 'groups', { 'name' : 'root' }],
		# try to del system user
		[ 'DEL', 'groups', { 'name' : 'root',
							'sure' : True }],
		# try to fake name
		[ 'DEL', 'groups', { 'login' : '`cat /etc/passwd`',
							'sure' : True }],
		],
		descr="test situations where del_group() should fail"
		))

	testsuite.add_scenario(Scenario([
		[ 'ADD', 'groups', {'name' : '%s' % gname,
							'skel' : '/etc/skel'}],
		[ 'ADD', 'users', { 'login' : '%s' % uname,
							'password' : '%s' % upw,
							'password_confirm' : '%s' % upw }],
		# without all necessary args
		#[ 'MOD', 'groups', { 'name' : '%s' % gname }],
		[ 'MOD', 'groups', { 'skel' : '/etc/skel' }],
		[ 'MOD', 'groups', { 'permissive' : True }],
		[ 'MOD', 'groups', { 'description' : 'This is a descr' }],
		[ 'MOD', 'groups', { 'members_source' : '%s' % uname }],
		[ 'MOD', 'groups', { 'resps_source' : '%s' % uname }],
		[ 'MOD', 'groups', { 'guests_source' : '%s' % uname }],
		[ 'MOD', 'groups', { 'members_dest' : '%s' % uname }],
		[ 'MOD', 'groups', { 'resps_dest' : '%s' % uname }],
		[ 'MOD', 'groups', { 'guests_dest' : '%s' % uname }],
		# try to delete/add non-existing user from/to group
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'members_source' : 'userdoesntexist' }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'resps_source' : 'userdoesntexist' }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'guests_source' : 'userdoesntexist' }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'members_dest' : 'userdoesntexist' }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'resps_dest' : 'userdoesntexist' }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'guests_dest' : 'userdoesntexist' }],
		# try to modify system group
		[ 'MOD', 'groups', {'name' : 'root',
							'members_dest' : '%s' % uname }],
		[ 'MOD', 'groups', {'name' : 'root',
							'members_source' : '%s' % uname }],
		# try to fake args
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'description' : '`cat /etc/passwd`' }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'skel' : '/etc/skelldoesntexist' }],
		[ 'MOD', 'groups', {'name' : '%s' % gname,
							'permissive' : '/etc/skelldoesntexist' }],
		[ 'DEL', 'users', {'login' : '%s' % uname,
							'sure' : True }],
		[ 'DEL', 'groups', {'name' : '%s' % gname,
							'sure' : True }],
		],
		descr="test situations where mod_groups() should fail"
		))

if __name__ == "__main__":

	parser = testsuite_parse_args()
	parser.add_option("-w", "--webbrowser", action="store_true",
		dest="webbrowser", default = False,
		help="ask to view the html page result of commands")
	parser.add_option("-b", "--browse", dest="url_to_follow", help='''browse '''
		'''url (and all links in url) in order to find dead link''')

	(options, args) = parser.parse_args()
	Testsuite.verbose = options.verbose

	# initialise the testsuite
	state_files = {
		'scenarii':	'data/.wmitest',
		}
	testsuite = Testsuite(name="WMI", state_file=state_files,
		directory_scenarii='data/wmitest',
		clean_func=clean_system, cmd_display_func=small_cmd_wmi)
	# add scenarii to the testsuite
	test_get(testsuite)
	test_users(testsuite)
	test_groups(testsuite)
	# deals with options
	if not options.all and not options.list and not options.execute and \
		not options.start_from and not options.start_from and \
		not options.url_to_follow and not options.clean and \
		not options.delete_trace and not options.stats:
			sys.argv.append('-a')
			(options, args) = parser.parse_args()
	if options.reload:
		testsuite.clean_state_file()
	if options.list:
		testsuite.get_scenarii()
	if options.execute:
		testsuite.select(options.execute-1)
	if options.start_from:
		testsuite.select(options.start_from, mode='start')
	if options.url_to_follow:
		if options.url_to_follow.lower().find(WMI_url) != -1 or \
		options.url_to_follow == 'home':
			browse_url(options.url_to_follow if options.url_to_follow != 'home' else WMI_url)
		else:
			logging.warning("Invalid url.")
	if options.clean:
		testsuite.clean_scenarii_directory()
	if options.delete_trace:
		testsuite.clean_scenarii_directory(scenario_number=options.delete_trace)
	if options.stats:
		testsuite.get_stats()
	if options.all:
		if testsuite.get_state() == None:
			testsuite.select(all=True)
		else:
			testsuite.select(scenario_number=testsuite.get_state(),mode='start')
	if options.execute or options.start_from or options.all:
		process.execute(['add', 'user', 'wmitest', '-p', 'wmitest', '-G',
			settings.licornd.wmi.group, '-S', '/bin/false'])
		try:
			testsuite.run()
			test_message("Testsuite terminated successfully.")
		finally:
			# delete the user
			process.execute(['del', 'user', 'wmitest', '--no-archive'])
