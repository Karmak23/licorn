# -*- coding: utf-8 -*-
"""
Licorn Testsuites basics.
some small classes, objects and functions to avoid code duplicates.

Copyright (C) 2010 Olivier Cortès <oc@meta-it.fr>,
Copyright (C) 2010 Robin Lucbernet <rl@meta-it.fr>

Licensed under the terms of the GNU GPL version 2.

"""
import os, curses, re, sys, shutil, time, hashlib, tempfile, gzip

from subprocess import Popen, PIPE, STDOUT
from traceback  import print_exc
from threading  import Event
from Queue      import PriorityQueue, Empty

from licorn.foundations           import logging, options, exceptions, settings
from licorn.foundations           import process, fsapi, pyutils, hlstr
from licorn.foundations.styles    import *
from licorn.foundations.constants import verbose, priorities
from licorn.foundations.base      import EnumDict

from licorn.daemon.threads        import GenericQueueWorkerThread
from licorn.core                  import LMC

# set this if you want background thread debugging.
#options.SetVerbose(verbose.INFO)

sce_status = EnumDict('scenario_status')
sce_status.NOT_STARTED = 0x0
sce_status.RUNNING     = 0x1
sce_status.FAILED      = 0x2
sce_status.PASSED      = 0x3

rwi = LMC.connect()
configuration_get = rwi.configuration_get

# ===================================================================== CLASSES

class TestsuiteRunnerThread(GenericQueueWorkerThread):
	""" Will actually run the tests by poping them from the run queue. """
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
								'backends'])[0].split('\n') if 'U' in line
															and line != '' ]
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

		# link us to the scenario
		scenario.testsuite = self

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
					test_message(_(u"Keyboard Interrupt received; "
									u"cleaning scenario, please wait…"))
					sce.clean()
					raise

			self.passed.append(sce.counter)
			self.save_best_state()
	def run_threaded(self):

		# As contexts are shared with one only licorn, we cannot run more
		# than 1 parallel job for now. But this still allows to continue
		# to run jobs while the tester inspects job results, and this is
		# still important to save time on success jobs which don't wait.
		self.workers_scheduler = TestsuiteRunnerThread.setup(licornd=None,
									input_queue=self.to_run,
									peers_min=1, peers_max=1, daemon=True)

		""" Feed the queue with things to do. """
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
						u'waiting for any failed scenario…'))

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
									u'for further execution.'))
					# wait a short while, to avoid displaying next status
					# working on the end of the last failed scenario, which
					# is a false-positive.
					#time.sleep(1.0)
			except KeyboardInterrupt:
				#best state is already saved.

				test_message(_(u'Stopping the run queue worker '
								u'and cleaning, please wait…'))

				self.workers_scheduler.stop()
				self.display_status()
				#self.threads[0].join()
				raise

			except Empty:
				#print '>> empty'
				if self.to_run.qsize() == 0 and self.failed.qsize() == 0 \
											and not self.working.is_set():

					self.workers_scheduler.stop()
					self.save_best_state()
					logging.notice(_(u'no more jobs, ending testsuite.'))
					break

		self.workers_scheduler.stop()
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
		""" display some statistics of the TS (number of scenario, number
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
class ScenarioTest:
	counter   = 0
	def __init__(self, cmds, context='std', descr=None, clean_num=0):

		# This one will be filled directly by the TS, when the scenario
		# is added to it.
		self.testsuite  = None


		self.context    = context
		self.counter    = None
		self.sce_number = ScenarioTest.counter
		self.descr      = descr

		# the number of commands, starting from the end of the scenario,
		# that must be run to consider the scenario data has been cleaned
		# from the system.
		self.clean_num  = clean_num

		self.status     = sce_status.NOT_STARTED
		self.failed_cmd = -1

		# used from the outside to know the current sce status
		self.current_cmd = None

		# we have to give a unique number to commands in case they are repeated.
		# this is quite common, to test commands twice (the second call should
		# fail in that case).
		self.cmd_counter = 0

		self.name = '%s%s%s%s%s' % (
			stylize(ST_NAME, 'Scenario #'),
			stylize(ST_OK, ScenarioTest.counter+1),
			stylize(ST_NAME, ' (%s)' % descr) if descr else '',
			stylize(ST_NAME, ', context '),
			stylize(ST_OK, self.context))

		ScenarioTest.counter += 1

		self.cmds = {}

		for cmd in cmds:
			self.cmds[self.cmd_counter] = cmd
			self.cmd_counter += 1

		# used from the inside and the outside to display the current status.
		self.total_cmds = len(self.cmds)

		self.batch_run        = False
		self.full_interactive = False

		string_to_hash = "%s%s" % (self.context, str(cmds))
		self.hash      = hashlib.sha1(string_to_hash).hexdigest()
		self.base_path = 'data/scenarii/%s' % self.hash
	def set_number(self, num):
		self.counter = num
	def check_failed_command(self):
		""" Check failed command interactively.

			Uses:

			* self.failed_cmd (int)
			* self.current_output (str)
			* self.current_retcode (int)

		"""

		try:
			ref_output, ref_code, gz_file = self.load_output(self.failed_cmd)

		except exceptions.DoesntExistException:

			if self.interactive or self.full_interactive:
				logging.notice(_(u'no reference output for {sce_name}, '
					'cmd #{cmd_num}/{total_cmds}:'
					'\n\n{highlight_cmds}\n\n{run_output}').format(
						sce_name=self.name,
						cmd_num=stylize(ST_OK, self.failed_cmd+1),
						total_cmds=stylize(ST_OK, self.total_cmds),
						highlight_cmds=self.show_commands(highlight_num=self.failed_cmd),
						run_output=self.current_output))

			if self.batch_run or logging.ask_for_repair(
									_(u'is this output good to keep as '
									'reference for future runs?')):
				# Save the output AND the return code for future
				# references and comparisons
				self.SaveOutput(self.failed_cmd,
								self.current_output,
								self.current_retcode)
				return True
			else:
				return False
		else:
			# we must diff the failed command with its previous output.
			handle, tmpfilename = tempfile.mkstemp(
				prefix=hlstr.clean_path_name(self.cmds[self.failed_cmd]))

			if gz_file:
				handle2, tmpfilename2 = tempfile.mkstemp(
					prefix=hlstr.clean_path_name(self.cmds[self.failed_cmd]))
				open(tmpfilename2, 'w').write(ref_output)

			open(tmpfilename, 'w').write(self.current_output)

			diff_output = process.execute(['diff', '-u',
									tmpfilename2
										if gz_file
										else '%s/%s/out.txt' % (
											self.base_path, self.failed_cmd),
									tmpfilename])[0]

			if self.interactive or self.full_interactive:
				logging.warning(_(u'command #{cmd_num}/{total_cmds} failed '
					'(sce#{sce_num}, ctx {context}). '
					'Retcode {ret_code} (ref {ref_code}).'
					'\n\n{highlight_cmds}\n\n{diff_output}').format(
					cmd_num=stylize(ST_OK, self.failed_cmd+1),
					total_cmds=stylize(ST_OK, self.total_cmds),
					sce_num=stylize(ST_OK, self.sce_number+1),
					context=stylize(ST_OK, self.context),
					ret_code=stylize(ST_BAD, self.current_retcode),
					ref_code=stylize(ST_OK, ref_code),
					highlight_cmds=self.show_commands(
											highlight_num=self.failed_cmd),
					diff_output=diff_output))

			if self.batch_run or logging.ask_for_repair(
						_(u'Should I keep the new return code '
						'and trace as reference for future runs?')):
				self.SaveOutput(self.failed_cmd,
								self.current_output, self.current_retcode)
				return True
			else:
				return False
	def check_for_context(self):
		""" Check if the scenario's context is the same than the user. """

		changed = False

		if self.context == 'shadow' and str(self.testsuite.current_context) != 'shadow':
			execute([ 'mod', 'config', '-B', 'openldap'])

			if self.interactive:
				test_message(_(u"Backend changed to shadow"))

			self.testsuite.current_context = 'shadow'
			changed = True

		if self.context == 'openldap' and str(self.testsuite.current_context) != 'openldap':
			execute([ 'mod', 'config', '-b', 'openldap'])

			if self.interactive:
				test_message(_(u"Backend changed to OpenLDAP"))

			self.testsuite.current_context = 'openldap'
			changed = True

		if changed:
			time.sleep(4.0)
	def SaveOutput(self, cmdnum, output, code):
		try:
			os.makedirs('%s/%s' % (self.base_path, cmdnum))

		except (OSError, IOError), e:
			if e.errno != 17:
				raise e

		open('%s/%s/cmdline.txt' % (
				self.base_path, cmdnum), 'w').write(
				' '.join(self.cmds[cmdnum]))
		open('%s/%s/code.txt' % (self.base_path, cmdnum), 'w').write(str(code))

		filename_gz  = '%s/%s/out.txt.gz' % (self.base_path, cmdnum)
		filename_txt = '%s/%s/out.txt' % (self.base_path, cmdnum)
		# we have to try to delete the other logfile, bacause in some rare
		# cases (when output raises above 1024 or lower besides), the format
		# changes and testsuite loops comparing to a wrong output.
		if len(output) > 1024:
			try:
				os.unlink(filename_txt)
			except (OSError, IOError), e:
				if e.errno != 2:
					raise e
			file = gzip.GzipFile(filename=filename_gz, mode='wb', compresslevel=9)
		else:
			try:
				os.unlink(filename_gz)
			except (OSError, IOError), e:
				if e.errno != 2:
					raise e
			file = open(filename_txt, 'w')
		file.write(output)
		file.close()
	def show_commands(self, highlight_num):
		""" output all commands, to get an history of the current scenario,
			and higlight the current one. """

		data = ''

		for cmdcounter in self.cmds:
			if cmdcounter < highlight_num:
				data += '	%s\n' % self.testsuite.cmdfmt(self.cmds[cmdcounter],
					prefix='  ')

			elif cmdcounter == highlight_num:
				data += '	%s\n' % self.testsuite.cmdfmt_big(
										self.cmds[cmdcounter],
										prefix='> ')

			elif cmdcounter > highlight_num:
				data += '	%s%s\n' % (
					self.testsuite.cmdfmt(
						self.cmds[cmdcounter],
						prefix='  '),
						'\n	%s' % self.testsuite.cmdfmt(u'[…]', prefix='  ') \
							if len(self.cmds) > cmdcounter+1 \
							else '')
				break

		return data
	def load_output(self, cmdnum):
		try:
			if os.path.exists('%s/%s' % (self.base_path, cmdnum)):

				if os.path.exists('%s/%s/out.txt.gz' % (
										self.base_path, cmdnum)):

					ref_output = gzip.open('%s/%s/out.txt.gz' %
						(self.base_path, cmdnum), 'r').read()
					gz_file = True

				else:
					ref_output = open('%s/%s/out.txt' %
						(self.base_path, cmdnum)).read()
					gz_file = False

				ref_code = int(open('%s/%s/code.txt' % (
							self.base_path, cmdnum)).read())

				return ref_output, ref_code, gz_file

		except Exception, e:
			logging.warning(_(u'Exception {exc} while loading output of '
				'cmd {cmd}, sce {sce}. Traceback follows, '
				'raising DoesntExistException').format(
				exc=e, cmd=cmdnum, sce=self.name))
			print_exc()

		raise exceptions.DoesntExistException(
								'problem loading data of command %s' % cmdnum)
	def RunCommand(self, cmdnum):
		try:
			ref_output, ref_code, gz_file = self.load_output(cmdnum)

		except exceptions.DoesntExistException:
			output, self.current_retcode = execute(self.cmds[cmdnum],
											interactive=self.interactive)
			self.current_output = strip_moving_data(output)
			return False

		output, self.current_retcode = execute(self.cmds[cmdnum],
											interactive=self.interactive)
		self.current_output = strip_moving_data(output)

		if self.current_retcode == ref_code \
								and  self.current_output == ref_output:
			return True
		else:
			return False
	def Run(self, options=[], interactive=False):
		""" run each command of the scenario, in turn. """

		self.interactive = interactive

		if self.interactive:
			# display a blank line to separate from TS status display.
			if self.full_interactive:
				logging.notice(_(u'Start run %s. Please wait while commands '
					'are executed, this can take some time.')
						% stylize(ST_NAME, self.name))
			else:
				sys.stderr.write('\n')

		self.check_for_context()

		#print '>> entering with', sce_status[self.status], self.name

		if self.status == sce_status.NOT_STARTED:
			self.clean()
			start = 0

		elif self.status == sce_status.FAILED:

			if self.clean_num:
				# the scenario has been cleaned by necessity, we must restart.
				self.check_failed_command()
				self.status = sce_status.NOT_STARTED
				#print '>> not started', self.name
				return

			else:
				# the scenario has no clean command, its just integrity or
				# unit test, we can continue from the failed cmd. if it
				# succeeds, continue from next; if it fails, rerun until
				# success.
				if self.check_failed_command():
					start = self.failed_cmd + 1
				else:
					start = self.failed_cmd

		elif self.status == sce_status.PASSED:

			if self.interactive:
				logging.warning(_(u'Already passed scenario %s') % self.name)
			return

		self.status = sce_status.RUNNING

		for cmdnum in self.cmds:

			# just for the display, we need to start from 1, not 0
			self.current_cmd = cmdnum + 1

			if not self.RunCommand(cmdnum):
				self.status     = sce_status.FAILED
				self.failed_cmd = cmdnum

				if self.full_interactive:
					while not self.check_failed_command():
						if self.RunCommand(cmdnum):
							break

				elif self.batch_run:
					if verbose:
						logging.notice(_(u'Automatically saved new output for '
							'scenario #{sce} command #{cmd}/{total}').format(
								sce=self.counter, cmd=self.current_cmd,
								total=self.total_cmds))

					self.check_failed_command()
					self.failed_cmd = None
				else:
					self.current_cmd = None
					if self.interactive:
						logging.notice(_(u'Checking FAILED cmd {cmd}/{total} '
							'of scenario {sce}').format(
							sce=stylize(ST_NAME, self.name), cmd=cmdnum,
							total=self.total_cmds))
					self.clean()
					#print '>> failed', self.name
					return

		# no need to clean() now, clean commands are part of the scenario,
		# they have already been run if everything went fine.
		#self.clean()
		#print '>> passed end', self.name
		self.status = sce_status.PASSED
		if self.interactive:
			logging.notice(_(u'End run %s.') % stylize(ST_NAME, self.name))
	def clean(self):
		""" execute clean commands without bothering on their output. """
		for cmdnum in sorted(self.cmds.keys())[-self.clean_num:]:
			#print '>> clean', cmdnum, ' '.join(self.cmds[cmdnum])
			#  don't call RunCommand(), it would overwrite the self.current_*
			# of the last failed command, if any.
			execute(self.cmds[cmdnum], interactive=True)
		return True

# =================================================================== FUNCTIONS

def log_and_exec(command, inverse_test=False, result_code=0, comment="",
	verb=verbose):
	"""Display a command, execute it, and exit if soemthing went wrong."""

	sys.stderr.write(("%s>>> " + _(u'running ') + "%s%s%s\n") % (
		colors[ST_LOG], colors[ST_PATH], ' '.join(command), colors[ST_NO]))

	output, retcode = execute(command)
	must_exit = False

	#
	# TODO: implement a precise test on a precise exit value.
	# for example, when you try to add a group with an invalid name,
	# licorn-add should exit (e.g.) 34. We must test on this precise
	# value and not on != 0, because if something wrong but *other* than
	# errno 34 happened, we won't know it if we don't check carefully the
	# program output.
	#

	if inverse_test:
		if retcode != result_code:
			must_exit = True
	else:
		if retcode != 0:
			must_exit = True

	if must_exit:
		if inverse_test:
			test = ("	%s→ it should have failed with reason: %s%s%s\n"
				% (colors[ST_PATH], colors[ST_BAD],
					comment, colors[ST_NO]))
		else:
			test = ""

		sys.stderr.write("	%s→ return code of command: %s%d%s (expected: %d)%s\n%s	→ log follows:\n"
			% (	colors[ST_LOG], colors[ST_BAD],
				retcode, colors[ST_LOG], result_code,
				colors[ST_NO], test) )
		sys.stderr.write(output)
		test_message(
			_(u'The last command failed to execute, '
				'or returned an unexpected result!'))
		raise SystemExit(retcode)

	if verb:
		sys.stderr.write(output)
def execute(cmd, verbose=0, interactive=False):
	if verbose and interactive:
		logging.notice('running %s.' % ' '.join(cmd))
	p4 = Popen(cmd, shell=False,
		  stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
	output = p4.stdout.read()
	retcode = p4.wait()
	if verbose and interactive:
		sys.stderr.write(output)
	return output, retcode
def strip_moving_data(output):
	""" strip dates from warnings and traces, else outputs and references
	always compare false ."""
	return	re.sub(r', line \d+, ', r', line [LINE], ',
			re.sub(r'([gu])id=(\x1b\[\d\d;\d\dm)?\d+(\x1b\[0;0m)?', r'\1id=[ID]',
			re.sub(r'(\.\d\d\d\d\d\d\d\d-\d\d\d\d\d\d|'
			'\[\d\d\d\d/\d\d/\d\d\s\d\d:\d\d:\d\d\.\d\d\d\d\]\s)', r'[D/T] ',
			re.sub(r'(Autogenerated\spassword\sfor\suser\s.*:|'
				'Set\spassword\sfor\suser\s.*\sto)\s.*', r'\1 [Password]',
			re.sub(r'report: /home/archives/import_.*.html',
				'report: /home/archives/import_[profile]-[D/T].html',
			re.sub(r'<(Thread|function|bound method)[^>]+>',
				r'<\1 at [hex_address]>',
				output
			))))))
def clean_dir_contents(directory):
	""" Totally empty the contents of a given directory, the licorn way. """
	if verbose:
		test_message(_(u'Cleaning directory %s.') % directory)

	def delete_entry(entry):
		if verbose:
			logging.notice(_(u'Deleting %s.') % entry)

		if os.path.isdir(entry):
			shutil.rmtree(entry)
		else:
			os.unlink(entry)

	map(delete_entry, fsapi.minifind(directory, mindepth=1, maxdepth=2))

	if verbose:
		test_message(_(u'Cleaned directory %s.') % directory)
def make_backups(mode):
	"""Make backup of important system files before messing them up ;-) """

	# this is mandatory, else there could be some inconsistencies following
	# backend (de)activation, and backup comparison could fail (false-negative)
	# because of this.
	execute([ 'chk', 'config', '-avvb'])

	if mode == 'shadow':
		for file in system_files:
			if os.path.exists('/etc/%s' % file):
				execute([ 'cp', '-f', '/etc/%s' % file,
					'/tmp/%s.bak.%s' % (file.replace('/', '_'), bkp_ext)])

	elif mode == 'openldap':
		execute([ 'slapcat', '-l', '/tmp/backup.1.ldif' ])

	else:
		logging.error('backup mode not understood.')

	test_message(_(u'Backed up system files for context %s.') % mode)
def compare_delete_backups(mode):
	""" """
	test_message(_(u'Comparing backups of system files after tests '
		'for side-effects alterations.'))

	if mode == 'shadow':
		for file in system_files:
			if os.path.exists('/etc/%s' % file):
				log_and_exec([ '/usr/bin/diff', '/etc/%s' % file,
					'/tmp/%s.bak.%s' % (file.replace('/', '_'), bkp_ext)], False,
				comment="should not display any diff (system has been cleaned).",
				verb = True)
				execute([ 'rm', '/tmp/%s.bak.%s' % (file.replace('/', '_'), bkp_ext)])
	elif mode == 'openldap':
		execute([ 'slapcat', '-l', '/tmp/backup.2.ldif'])
		log_and_exec([ '/usr/bin/diff', '/tmp/backup.1.ldif', '/tmp/backup.2.ldif'],
			False,
			comment="should not display any diff (system has been cleaned).",
			verb = True)
		execute([ 'rm', '/tmp/backup.1.ldif', '/tmp/backup.2.ldif'])
	else:
		logging.error('backup mode not understood.')

	test_message(_(u'System config files backup comparison finished successfully.'))
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
	sys.stderr.write("%s>>> %s%s\n" % (colors[ST_LOG], msg, colors[ST_NO]))
def testsuite_parse_args():
	""" return basic options of a TS """
	from optparse import OptionParser
	parser = OptionParser()

	parser.add_option("-r", "--reload", action="store_true", dest="reload",
						help=_(u"reload testsuite. Start from beginning."))
	parser.add_option("-e", "--execute", dest="execute", type="int",
		default=False, help=_(u"execute a specific scenario of the testsuite."))
	parser.add_option("-l", "--list", action="store_true", dest="list",
		default=False, help=_(u"List all scenarii of the testsuite."))
	parser.add_option("-a", "--all", action="store_true", dest="all",
		default=False, help=_(u"Select all scenarii."))
	parser.add_option("-s", "--start-from", dest="start_from", type="int",
		default=False, help=_(u"Start from the scenario N."))
	parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
		default=False, help=_(u"Display messages during command execution."))
	parser.add_option("-c", "--clean", action="store_true", dest="clean",
		default=False, help=_(u"Clean scenarii directory."))
	parser.add_option("-d", "--delete-trace", dest="delete_trace", type="int",
		default=False, help=_(u"Delete traces of a given scenario."))
	parser.add_option("--stats", action="store_true", dest="stats",
		default=False, help=_(u"Display statistics of the testsuite."))
	parser.add_option("-i", "--interactive",
		dest="interactive", action="store_true", default=False,
		help=_(u"Run the testsuite in standard interactive mode (one scenario "
			u"at a time. Use this when you have modified a mega bunch of code, "
			u"and you know it will be better to check everything manually "
			u"before doing anything else, and the batch run is not what you "
			u"want because your code is still in alpha stage."))
	parser.add_option("-b", "--batch-run", "--build-initial-data",
		dest="batch_run", action="store_true", default=False,
		help=_(u"Don't halt the scenario on fail, just accept the result of "
			u"the failed command and continue. WARNING: this flag is meant to "
			u"be used only when you don't have any scenario data in your "
			u"repository, to build a new one from scratch. Use this flag only"
			u"on a clean source tree, else your TS results will not be "
			u"reliable."))
	return parser


# =================================================================== MAIN

system_files = ( 'passwd', 'shadow', 'group', 'gshadow', 'adduser.conf',
				'login.defs', 'licorn/main.conf', 'licorn/group',
				'licorn/profiles.xml')

bkp_ext = 'licorn'

state_files = {
	'context':  'data/.ctx_status',
	'scenarii':	'data/.sce_status',
	'owner':    'data/.owner'
	}

# see http://docs.python.org/library/os.html#os.environ for details.
# we must unset them, else all argparser-related methods fail if there are
# any terminal movements between 2 runs.
for var_name in ('COLS', 'COLUMNS', 'LINES'):
	try:
		del os.environ[var_name]

	except KeyError:
		pass

if __debug__:
	PYTHON = [ 'python' ]
	verbose = True
else:
	PYTHON = [ 'python', '-OO' ]
	verbose = False
