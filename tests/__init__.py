# -*- coding: utf-8 -*-
"""
Licorn Testsuites basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Copyright (C) 2010 Robin Lucbernet <rl@meta-it.fr>

Licensed under the terms of the GNU GPL version 2.

"""
import os, curses, re, sys, shutil
from licorn.foundations        import logging, process
from licorn.foundations.styles import *

from licorn.core import LMC

LMC.connect()
configuration = LMC.configuration

class Testsuite:
	verbose = False
	def __init__(self, name, directory_scenarii,
		clean_func, state_file, cmd_display_func):
		self.name=name
		self.list_scenario = []
		self.selected_scenario = []
		self.directory_scenarii=directory_scenarii
		self.clean_system=clean_func
		self.cmd_display_func = cmd_display_func
		self.state_file=state_file
		# save the current context to restaure it at the end of the testsuite
		backends =  [ line for line in process.execute(['get', 'config',
					'backends'])[0].split('\n') if 'U' in line ]
		reduce(lambda x,y: x if y == '' else y, backends)
		self.user_context = backends[0].split('(')[0]
		self.current_context=self.user_context
	def restore_user_context(self):
		""" restore user active backend before testsuite runs """
		if self.user_context == 'shadow' and self.current_context != 'shadow':
			process.execute([ 'mod', 'config', '-B', 'openldap'])
		if self.user_context == 'openldap' and self.current_context != 'openldap':
			process.execute([ 'mod', 'config', '-b', 'openldap'])
		test_message("Restored initial backend to %s." % self.user_context)
	def add_scenario(self,scenario):
		""" add a scenario to the testsuite and set a number for it """
		scenario.set_number(len(self.list_scenario)+1)
		self.list_scenario.append(scenario)
	def run(self):
		""" run selected scenarii """
		if self.selected_scenario != []:
			# clean the system from previus run
			self.clean_system()
			for scenario in self.selected_scenario:
				# save the state of the testsuite (number of current scenario)
				# in order to be abble to restart from here if the TS stopped.
				self.save_state(scenario.counter)
				scenario.Run()
			# reset selection
			self.selected_scenario = []
	def get_scenarii(self):
		""" display the list of scenarii in the TS """
		# display stats
		self.get_stats()
		logging.notice('''List of scenarii in %s TS: (%s=no trace;%s=not '''
			'''completely tested;%s=completety tested)''' % (self.name,
			stylize(ST_BAD,'*'), stylize(ST_NAME,'*'), stylize(ST_OK,'*')))
		for scenario in self.list_scenario:
			try:
				nbr_cmd_in_dir = len(os.listdir('%s/%s' %
					(self.directory_scenarii, scenario.hash)))
			except OSError:
				nbr_cmd_in_dir = 0
			nbr_cmd = len(scenario.cmds)
			if nbr_cmd_in_dir < nbr_cmd: color=ST_NAME
			if nbr_cmd_in_dir == 0: color=ST_BAD
			if nbr_cmd_in_dir == nbr_cmd: color=ST_OK
			logging.notice('%s: %s %s' % (stylize(color, '%3d' % scenario.counter),
				scenario.descr,
				'[%s]' % stylize(ST_LINK,scenario.context) if self.name=='CLI' \
				else ''))
			if Testsuite.verbose:
				for cmd in scenario.cmds:
					logging.notice("--> cmd %2d: %s" % (cmd,
						self.cmd_display_func(scenario.cmds[cmd])))
	def get_stats(self):
		""" display some statistique of the TS (number of scenario, number
		of commands) """
		num_cmd=0
		for scenario in self.list_scenario:
			num_cmd+=len(scenario.cmds)
		logging.notice("The %s testsuite has %s scenarii (%s commands)." % (self.name,
			stylize(ST_OK,len(self.list_scenario)),stylize(ST_OK,num_cmd)))
	def select(self,scenario_number=None, all=False, mode=None):
		""" select some scenarii to be executed """
		if all:
			# select all scenarii
			self.selected_scenario = self.list_scenario
		elif scenario_number != None and mode == None:
			try:
				# select only one scenario
				self.selected_scenario.append(self.list_scenario[scenario_number])
			except IndexError, e:
				test_message("No scenario selected")
		elif scenario_number != None and mode == 'start':
			# start selection from a scenario to the end of the list
			for scenario in self.list_scenario[scenario_number-1:]:
				self.selected_scenario.append(scenario)
			if self.selected_scenario == []:
				test_message("No scenario selected")
	def clean_scenarii_directory(self,scenario_number=None):
		""" clean the scenarii directory (remove old scenario directory) """
		""" if scenario_number is provided, the scenario directory will be
		deleted"""
		number=0
		list_hash=[]
		for scenario in self.list_scenario:
			list_hash.append(scenario.hash)
		for dir in os.listdir(self.directory_scenarii):
			if scenario_number != None:
				# delete only the directory of scenario_number
				try:
					if self.list_scenario[scenario_number-1].hash == dir:
						shutil.rmtree('%s/%s' % (self.directory_scenarii,dir))
						number+=1
				except IndexError, e:
					# if the scenario_number is not valid
					test_message("Scenario number '%s' is not valid." %
						scenario_number)
					break
			else:
				# deleted all scenario directory that don't have hash in the
				# scenario_list
				if dir not in list_hash:
					shutil.rmtree('%s/%s' % (self.directory_scenarii,dir))
					number+=1
		logging.notice('''Scenarii directory has been cleaned (%s folders '''
			'''were deleted).''' % number)
	def save_state(self,num, state_type='scenarii'):
		""" save the state of the TS (record the number of the current
		scenario)"""
		open(self.state_file[state_type],'w').write('%d' % num)
	def get_state(self,state_type='scenarii'):
		""" get state of the TS """
		if os.path.exists(self.state_file[state_type]):
			 return int(open(self.state_file[state_type]).read())
		else:
			return None
	def clean_state_file(self):
		""" clear state of the TS """
		for state_type in self.state_file:
			if state_type == 'owner':
				continue
			try:
				os.unlink(self.state_file[state_type])
			except (IOError, OSError), e:
					if e.errno != 2:
						raise e
		test_message('State file deleted, start from beginning.')
	def cmdfmt(self, cmd, prefix=''):
		'''convert a sequence to a colorized string.'''
		return '%s%s' % (prefix, stylize(ST_NAME, self.cmd_display_func(cmd)))
	def cmdfmt_big(self, cmd, prefix=''):
		'''convert a sequence to a colorized string.'''
		return '%s%s' % (prefix, stylize(ST_LOG, self.cmd_display_func(cmd)))
curses.setupterm()
clear = curses.tigetstr('clear')
def clean_path_name(command):
	# return a multo-OS friendly path for a given command.
	return ('_'.join(command)).replace(
		'../', '').replace('./', '').replace('//','_').replace(
		'/','_').replace('>','_').replace('&', '_').replace(
		'`', '_').replace('\\','_').replace("'",'_').replace(
		'|','_').replace('^','_').replace('%', '_').replace(
		'(', '_').replace(')', '_').replace ('*', '_').replace(
		' ', '_').replace('__', '_')
def clear_term():
	sys.stdout.write(clear)
	sys.stdout.flush()
def term_size():
	#print '(rows, cols, x pixels, y pixels) =',
	return struct.unpack("HHHH",
		fcntl.ioctl(
			sys.stdout.fileno(),
			termios.TIOCGWINSZ,
			struct.pack("HHHH", 0, 0, 0, 0)
			)
		)
def small_cmd_cli(cmd):
	return re.sub(r'((sudo|python|-OO) |\.\./interfaces/cli/|\.py\b)', r'', ' '.join(cmd))
def small_cmd_wmi(cmd):
	list_cmd = []
	for subcmd in cmd:
		if type(subcmd) == type({}):
			list_cmd.append(str(subcmd))
		else:
			list_cmd.append(subcmd)
	return small_cmd_cli(list_cmd)
def test_message(msg):
	#display a message to stderr.
	sys.stderr.write("%s>>> %s%s\n"
		% (colors[ST_LOG], msg, colors[ST_NO]))

def testsuite_parse_args():
	""" return basic options of a TS """
	from optparse import OptionParser
	parser = OptionParser()
	parser.add_option("-r", "--reload", action="store_true", dest="reload",
	help="reload testsuite. Start from beginning")
	parser.add_option("-e", "--execute", dest="execute", type="int",
		default=False, help="execute a specific scenario of the testsuite.")
	parser.add_option("-l", "--list", action="store_true", dest="list",
		default=False, help="list all scenarii of the testsuite.")
	parser.add_option("-a", "--all", action="store_true", dest="all",
		default=False, help="select all scenarii")
	parser.add_option("-s", "--start-from", dest="start_from", type="int",
		default=False, help="start from the scenario N.")
	parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
		default=False, help="display messages during command execution.")
	parser.add_option("-c", "--clean", action="store_true", dest="clean",
		default=False, help="clean scenarii directory.")
	parser.add_option("-d", "--delete-trace", dest="delete_trace", type="int",
		default=False, help="delete trace of a scenario")
	parser.add_option("--stats", action="store_true", dest="stats",
		default=False, help="display statistics of the testsuite.")
	return parser

