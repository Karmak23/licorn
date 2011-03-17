# -*- coding: utf-8 -*-
"""
Licorn Testsuites basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Copyright (C) 2010 Robin Lucbernet <rl@meta-it.fr>

Licensed under the terms of the GNU GPL version 2.

"""
import os, curses, re, sys, shutil, time

from threading import Event
from Queue     import PriorityQueue, Empty

from licorn.foundations           import logging, options, process
from licorn.foundations.styles    import *
from licorn.foundations.constants import verbose
from licorn.foundations.base      import EnumDict
from licorn.daemon                import priorities
from licorn.daemon.threads        import GenericQueueWorkerThread

# set this if you want background thread debugging.
options.SetVerbose(verbose.INFO)

sce_status = EnumDict('scenario_status')
sce_status.NOT_STARTED = 0x0
sce_status.RUNNING     = 0x1
sce_status.FAILED      = 0x2
sce_status.PASSED      = 0x3

class TestsuiteRunnerThread(GenericQueueWorkerThread):
	""" Will run the tests. """
	pass

class Testsuite:
	verbose = False
	def __init__(self, name, directory_scenarii,
			clean_func, state_file, cmd_display_func):
		self.name               = name
		self.list_scenario      = []
		self.selected_scenario  = []
		self.directory_scenarii = directory_scenarii
		self.clean_system       = clean_func
		self.cmd_display_func   = cmd_display_func
		self.state_file         = state_file
		# save the current context to restaure it at the end of the testsuite
		backends = [ line for line in process.execute(['get', 'config',
					'backends'])[0].split('\n') if 'U' in line ]
		reduce(lambda x,y: x if y == '' else y, backends)
		self.user_context    = backends[0].split('(')[0]
		self.current_context = self.user_context

		self.to_run     = PriorityQueue()
		self.failed     = PriorityQueue()
		self.passed     = []
		self.best_state = 1
		self.working    = Event()

		# used to modify the best state behaviour when running one one test
		# or the whole TS.
		self.best_state_only_one = 0

		# used to build initial testsuite data
		self.batch_run   = False
		self.interactive = False
	def restore_user_context(self):
		""" Restore user active backend before testsuite runs. """

		if self.user_context == 'shadow' and self.current_context != 'shadow':
			process.execute([ 'mod', 'config', '-B', 'openldap'])

		if self.user_context == 'openldap' \
										and self.current_context != 'openldap':
			process.execute([ 'mod', 'config', '-b', 'openldap'])

		test_message(_(u'Restored initial backend to %s.') % self.user_context)
	def add_scenario(self,scenario):
		""" add a scenario to the testsuite and set a number for it """
		scenario.set_number(len(self.list_scenario) + 1)
		self.list_scenario.append(scenario)
	def run(self):
		""" Run selected scenarii. """

		self.total_sce = len(self.selected_scenario)

		# we will start display 'context setup' if this is the case.
		self.last_setup_display  = -1
		self.last_status_display = 0

		if self.interactive:
			self.run_interactive()
		else:
			self.run_threaded()
	def run_interactive(self):

		for sce in self.selected_scenario:

			sce.full_interactive = True

			while sce.status in (sce_status.FAILED, sce_status.NOT_STARTED):
				try:
					sce.Run(interactive=True)

				except KeyboardInterrupt:
					test_message(_(u"Keyboard Interrupt received; cleaning scenario, please wait…"))
					sce.clean()
					raise

			self.passed.append(sce.counter)
			self.save_best_state()
	def run_threaded(self):

		self.threads = []
		self.threads.append(
				TestsuiteRunnerThread(
					in_queue=self.to_run,
					peers_min=1,
					peers_max=1,
					licornd=self,
					high_bypass=False,
					daemon=False
				)
			)
		self.threads[0].start()

		if self.selected_scenario != []:
			# clean the system from previus run
			self.clean_system()

			for scenario in self.selected_scenario:
				# save the state of the testsuite (number of current scenario)
				# in order to be abble to restart from here if the TS stopped.
				self.to_run.put((scenario.counter, self.run_scenario,
															(scenario,), {}))
			# reset selection
			self.selected_scenario = []

		test_message(_(u'Started background tests, '
						'waiting for any failed scenario…'))

		# wait for the first job to be run, else counter displays '-1'.
		time.sleep(2.0)

		while True:
			try:
				self.display_status()
				#time.sleep(1.0)

				prio, sce = self.failed.get(True, 1.0)

				if not self.best_state_only_one \
									and sce.counter > self.best_state:
					# we delay the checks for failed jobs which are not
					# the next to check. This permits the user to check
					# scenario to the end, before checking a new one, at
					# the expense of a little more loop cycles.
					#print '>> downgrading sce %s %s' % (sce.counter, sce.name)
					self.failed.task_done()
					self.failed.put((sce.counter, sce))
					# if we got another job, our current failed one is still
					# not finished, wait a little.
					time.sleep(1.0)
					continue

				#print '>> run sce %s %s ' % (sce.counter, sce.name)
				self.display_status()
				sce.Run(interactive=True)
				self.failed.task_done()

				# if it failed again, reput it in the queue (until it doesn't
				# fail anymore).

				if sce.status in (sce_status.FAILED, sce_status.NOT_STARTED):

					self.to_run.put(
						(sce.counter, self.run_scenario, (sce,), {}))
					test_message(_(u'Re-put scenario in the run queue '
						'for further execution.'))
					# wait a short while, to avoid displaying next status
					# working on the end of the last failed scenario, which
					# is a false-positive.
					#time.sleep(1.0)
			except KeyboardInterrupt:
				#best state is already saved.

				test_message(_(u'Stopping the run queue worker '
					'and cleaning, please wait…'))

				self.threads[0].stop()
				self.display_status()
				self.threads[0].join()
				raise

			except Empty:
				#print '>> empty'
				if self.to_run.qsize() == 0 and self.failed.qsize() == 0 \
											and not self.working.is_set():

					self.threads[0].stop()
					self.save_best_state()
					logging.notice(_(u'no more jobs, ending testsuite.'))
					break

		self.threads[0].join()
	def save_best_state(self):
		""" find the highest number of a consecutive suite of non failed ones,
			and save it as the best state we could reach in the current session.
		"""
		old_best = self.best_state

		for elem in sorted(self.passed):
			if elem < self.best_state:
				self.passed.remove(elem)
			elif elem == self.best_state:
				self.passed.remove(elem)
				self.best_state = elem + 1
			elif self.best_state_only_one and elem == self.best_state + 1:
				self.passed.remove(elem)
				self.best_state = elem
			else:
				break

		if self.best_state != old_best:
			# note we got at least until there, save it.
			self.save_state(self.best_state)
			test_message(_(u'Saved best state #%s (not inclusive).') %
				self.best_state)
	def run_scenario(self, scenario):

		self.current_sce = scenario

		self.working.set()

		scenario.batch_run = self.batch_run
		scenario.Run()

		if scenario.status == sce_status.PASSED:
			#print '>> got one passed'
			self.passed.append(scenario.counter)
			self.save_best_state()

		elif scenario.status == sce_status.FAILED:
			#print '>> got one failed -> put(failed)'
			self.failed.put((scenario.counter, scenario))

		elif scenario.status == sce_status.NOT_STARTED:
			#print '>> got not started -> put(re_run)'
			# after a corrected fail, the scenario must be rerun.
			# with high priority, because we are probably waiting for it.
			self.to_run.put(
				(scenario.counter, self.run_scenario, (scenario,), {}))

		self.current_sce = None
		self.working.clear()
	def display_status(self):
		""" display the current status of the TS, in the following conditions:

			* if not working on anything, don't display any status (this
			  happens in some rare cases when jobs are migrated from one
			  queue to another (which is blocking, or while cleanings occur).
			* if no command is running, display the fact that the scenario
			  is setting up its context.
			  This can take time because we need to wait for the daemon to
			  restart. In this case, the status will be displayed only ONCE
			  for a given scenario.
			  It may not be displayed at all, if context is fast enough to
			  check and setup (or not set up at all when not needed).
			* while running scenario commands, always display the status.

		"""
		#clear_term()
		# "1" counts for the job currently under test: it is not yet done.

		if self.working.is_set():

			if time.time() - self.last_status_display < 1.0:
				# don't display the status more than once per second,
				# in any case.
				return

			self.last_status_display = time.time()

			if self.current_sce.current_cmd != None \
				or self.last_setup_display != self.current_sce.counter:

				ran_sce = self.total_sce - (
							(1 if self.working.is_set() else 0)
							+ self.to_run.qsize()
							+ self.failed.qsize())
				failed_sce = self.failed.qsize()
				logging.notice(_(u'TS global status: on #{current}, '
					'{ran}/{total} passed '
					'({percent_done:.2}%) {passed_content}- '
					'{failed} failed '
					'({percent_failed:.2}%) - '
					'best score until now: #{best}').format(
						current=stylize(ST_BUSY, '%s (%s)' % (
							self.current_sce.counter,
							'%s/%s %.1f%%' % (
								self.current_sce.current_cmd,
								self.current_sce.total_cmds,
								100.0
									* self.current_sce.current_cmd
									/ self.current_sce.total_cmds,
								)
								if self.current_sce.current_cmd
								else _(u'context setup')
							)
							if self.current_sce
							else '-'),
						ran=ran_sce,
						total=self.total_sce,
						percent_done=100.0*ran_sce/self.total_sce,
						failed=failed_sce,
						percent_failed=100.0*failed_sce/self.total_sce,
						best=self.best_state,
						passed_content=_(u'last: {passed}{passed_more} ').format(
							passed=','.join([ str(i)
								for i in sorted(self.passed)[:5] ]),
							passed_more=_(u'…')
								if len(self.passed) > 5 else '')
							if len(self.passed) > 0 else ''
					)
				)

			# always mark the context setup displayed if we reach here.
			# either we displayed it, or we jumped directly to a command
			# display, which implies the context setup is already done.
			#
			# taking in account the second reason avoids displaying
			# 'context setup' while the scenario is cleaning after a fail.
			self.last_setup_display = self.current_sce.counter
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
			logging.notice('%s: %s %s' % (
				stylize(color, '%3d' % scenario.counter),
				scenario.descr,
				'[%s]' % stylize(ST_LINK,scenario.context)
					if self.name=='CLI' else ''))
			if Testsuite.verbose:
				for cmd in scenario.cmds:
					logging.notice("--> cmd %2d: %s" % (cmd,
						self.cmd_display_func(scenario.cmds[cmd])))
	def get_stats(self):
		""" display some statistique of the TS (number of scenario, number
		of commands) """

		sce_ = len(self.list_scenario)
		cmd_ = sum(len(sce.cmds) for sce in self.list_scenario)

		logging.notice(_(u'The {0} testsuite holds {1} scenarii, counting {2} '
			'commands (avg of {3} cmds per scenario).').format(
			stylize(ST_NAME, self.name), stylize(ST_OK, sce_),
			stylize(ST_OK, cmd_), stylize(ST_UGID, '%.1f' % (cmd_*1.0/sce_))))
	def select(self, scenario_number=None, all=False, mode=None):
		""" select some scenarii to be executed """
		if all:
			# select all scenarii
			self.selected_scenario = self.list_scenario[:]
			self.best_state = 1
		elif scenario_number != None and mode == None:
			try:
				# select only one scenario
				self.selected_scenario.append(
						self.list_scenario[scenario_number])
				self.best_state = self.get_state() or 1
				self.best_state_only_one = scenario_number
			except IndexError, e:
				test_message(_(u"No scenario selected"))
		elif scenario_number != None and mode == 'start':
			# start selection from a scenario to the end of the list
			for scenario in self.list_scenario[scenario_number-1:]:
				self.selected_scenario.append(scenario)
				self.best_state = self.get_state() or 1

				if self.best_state < scenario_number:
					raise RuntimeError(_('Cannot select a higher scenario '
						'than the current best_state (%s)' % self.best_state))
			if self.selected_scenario == []:
				test_message(_(u"No scenario selected"))
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
					test_message(_(u"Scenario number '%s' is not valid.") %
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
		test_message(_(u'State file deleted, start from beginning.'))
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
	return re.sub(r'((sudo|python|-OO) |\.\./interfaces/cli/|\.py\b)',
					r'', ' '.join(cmd))
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
	help=_(u"reload testsuite. Start from beginning"))
	parser.add_option("-e", "--execute", dest="execute", type="int",
		default=False, help=_(u"execute a specific scenario of the testsuite."))
	parser.add_option("-l", "--list", action="store_true", dest="list",
		default=False, help=_(u"list all scenarii of the testsuite."))
	parser.add_option("-a", "--all", action="store_true", dest="all",
		default=False, help=_(u"select all scenarii"))
	parser.add_option("-s", "--start-from", dest="start_from", type="int",
		default=False, help=_(u"start from the scenario N."))
	parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
		default=False, help=_(u"display messages during command execution."))
	parser.add_option("-c", "--clean", action="store_true", dest="clean",
		default=False, help=_(u"clean scenarii directory."))
	parser.add_option("-d", "--delete-trace", dest="delete_trace", type="int",
		default=False, help=_(u"delete trace of a scenario"))
	parser.add_option("--stats", action="store_true", dest="stats",
		default=False, help=_(u"display statistics of the testsuite."))
	parser.add_option("-i", "--interactive",
		dest="interactive", action="store_true", default=False,
		help=_(u"run the testsuite in standard interactive mode (one scenario "
			"at a time. Use this when you have modified a mega bunch of code, "
			"and you know it will be better to check everything manually "
			"before doing anything else, and the batch run is not what you "
			"want because your code is still in alpha stage."))
	parser.add_option("-b", "--batch-run", "--build-initial-data",
		dest="batch_run", action="store_true", default=False,
		help=_(u"don't halt the scenario on fail, just accept the result of "
			"the failed command and continue. WARNING: this flag is meant to "
			"be used only when you don't have any scenario data in your "
			"repository, to build a new one from scratch. Use this flag only"
			"on a clean source tree, else your TS results will not be "
			"reliable."))
	return parser

