#!/usr/bin/python
# poor man's last


import sys, utmp, time, random, glob
from datetime import datetime

from licorn.foundations        import logging, styles
from licorn.foundations.styles import *
from licorn.foundations.base   import EnumDict
from licorn.foundations.apt    import version_compare as filecmp

stylize = styles.stylize

# local imports
from base import DataSource, sha1

from UTMPCONST import *

utmp_types = EnumDict('utmp_types',
	from_dict={
		'EMPTY'        : 0,
		'RUN_LVL'      : 1,
		'BOOT_TIME'    : 2,
		'NEW_TIME'     : 3,
		'OLD_TIME'     : 4,
		'INIT_PROCESS' : 5,
		'LOGIN_PROCESS': 6,
		'USER_PROCESS' : 7,
		'DEAD_PROCESS' : 8,
		'ACCOUNTING'   : 9,
	})

class WtmpDataSource(DataSource):
	def __init__(self, *args, **kwargs):

		self.since = kwargs.pop('since', 0.0)
		self.last  = kwargs.pop('last', None)

		# On the remote side, only strings are stored.
		# using randint() for anonymization will not
		# help that much. In fact, we randomize
		# hostnames too, so using integers is probably
		# not safe enough.
		kwargs['anon_genfunc'] = sha1

		super(WtmpDataSource, self).__init__(self, *args, **kwargs)
	def __iter__(self):
		return self.iter()
	def iter(self):

		# get these things handy, we will use them a lot.
		anon         = self.anonmap
		since        = self.since
		last         = self.last

		# keep trace of open entries, to yield only complete ones (start + end)
		open_entries    = {}
		ignored_entries = {}

		# This will ``True`` when the 'last' is reached or if there is
		# no 'last'; When it's ``True``, the method starts to yield entries.
		should_yield = not last

		# We go from older to newer, to correctly close open entries.
		for wtmp_path in sorted(glob.glob(WTMP_FILE + '*'), cmp=filecmp, reverse=True):
			wtmp  = utmp.UtmpRecord(wtmp_path)
			entry = wtmp.getutent()

			while entry:
				if since and entry.ut_tv < since:
					assert ltrace(TRACE_MYLICORN, 'skipped older entry {0}'.format(
							str((entry[0], entry.ut_user, entry.ut_line,
								entry.ut_host, time.ctime(entry.ut_tv[0])))))
					continue

				if entry[0] in (BOOT_TIME, USER_PROCESS):
					if (entry.ut_user, entry.ut_line) in open_entries:
						logging.warning(_(u'{0}: skipping duplicate entry {1}; '
								u'WTMP file {2} is probably corrupt.').format(
								self.pretty_name,
								stylize(ST_COMMENT, (entry.ut_user, entry.ut_line)),
								stylize(ST_PATH, wtmp_path)))

					else:
						# Record an opened entry, that will be yielded
						# if a matching closing one is found.
						open_entries[entry.ut_pid, entry.ut_line] = [
											entry.ut_user,
											entry.ut_line,
											entry.ut_host,
											# entry.ut_session, is always '0'.
											str(datetime.fromtimestamp(entry.ut_tv[0]))
										]
				elif entry[0] == LOGIN_PROCESS:
					# keep login/getty in memory to avoid missing real orphans,
					# and still avoid to send useless entries.
					ignored_entries[entry.ut_pid, entry.ut_line] = entry.ut_line

				elif (entry[0] == RUN_LVL and entry.ut_user != 'runlevel') \
												or entry[0] == DEAD_PROCESS:
					# we are looking either for a "shutdown" entry matching an
					# earlier "reboot", or closing user session matching an
					# already opened one.

					try:
						# Now that we have the end time too, the
						# entry is complete and we can yield it.
						e = open_entries.pop(
											(entry.ut_pid, entry.ut_line)
										) + [ str(datetime.fromtimestamp(entry.ut_tv[0])) ]

					except KeyError:
						try:
							# Is this a login / getty process for which we
							# don't care? if yes, we already noted it to avoid
							# useless "orphan" warnings.
							ignored_entries.pop((entry.ut_pid, entry.ut_line))

						except KeyError:
							logging.warning2(_(u'{0}: skipped orphaned entry '
								u'{1} with no start; either it was opened '
								u'before WTMP file {2} was rotated, either the '
								u'file is corrupt.').format(
									self.pretty_name,
									stylize(ST_COMMENT, (entry.ut_user,
														entry.ut_line,
														str(datetime.fromtimestamp(
															entry.ut_tv[0])),
														entry.ut_host)),
									stylize(ST_PATH, wtmp_path)))

					else:
						# Compute the checksum of the entry; the SHA1 is
						# made on the non-anonymized data, to allow re-sync
						# between central and us without re-transmitting the
						# whole data.
						e.insert(0, sha1(str(e)))

						# Anonymise if needed, after checksum computation.
						if e[1] != 'reboot':
							# Anonymize usernames and hostnames
							e[1] = anon[e[1]]
							e[3] = anon[e[3]]

						if should_yield:
							yield e

						if last and e[0] == last:
							# we just reached the last known entry of
							# the central server. Next and subsequent
							# must be yielded.
							should_yield = True

							# reset 'last' locally, to be sure next loop
							# iteration will yield, by not altering
							# 'should_yield'. We could update 'last' with
							# the current value, but this would imply more
							# CPU hits. Disabling 'last' is lighter.
							last = None

				entry = wtmp.getutent()

			wtmp.endutent()

		if open_entries:
			# these entries don't have matching closing ones.
			# They could be still open sessions, or duplicates,
			# or corrupt entries, we can't know.
			logging.warning2(_(u'{0}: There are {1} still-open entries in '
				u'WTMP database. Not yielded, perhaps next time if they get '
				u'closed until then.').format(self.pretty_name,
								stylize(ST_COMMENT, len(open_entries))))

__all__ = ('utmp_types', 'WtmpDataSource', )
