# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

Copyright (C) 2005-2006 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006 Jérémy Milhau "Luka" <jeremilhau@gmail.com>
Licensed under the terms of the GNU GPL version 2

"""

import re, shutil

from licorn.foundations    import exceptions
from licorn.core           import configuration
from licorn.core.internals import readers

_sysConfig = configuration

class TimeConstraintsList:
	constraints_dict = None # (Dictionary)
	def __init__(self):
		self.constraints_dict = readers.timeconstraints_conf_dict(_sysConfig.mSquidGuard['CONF'])
	def __is_a_valid_timezone(self, timezone):
		""" Return True if the string 'timezone' has the format HH:MM-HH:MM and if the hours which it contains are correct (example: no 26:86-10:00)
		"""
		tz_re = re.compile("(([01]?[0-9]|2[0-3]):[0-5][0-9])-(([01]?[0-9]|2[0-3]):[0-5][0-9])")
		directive = tz_re.match(timezone)
		if directive is None:
			return False

		# Verify that start is less than end (lexical comparison)
		if str(timezone[0:4]) >= str(timezone[6:10]):
			return False

		return True
	def __is_a_valid_id(self, timespace, constraint_id):
		""" Returns True if it exists a constraint of 'timespace' which has the id 'constraint_id'
		"""
		return constraint_id in range(len(self.constraints_dict[timespace]["constraints"]))
	def __is_a_valid_weekdays(self, weekdays):
		""" Returns True if the string weekdays has no doubled letters and if the letters are correct
		"""
		# Are there the good letters ?
		good_letters = re.compile("^[smtwhfa]{1,7}$")
		if good_letters.match(weekdays) is None:
			return False

		# Are there doubled letters ?
		for l in weekdays:
			compt = 0
			for x in weekdays:
				if l == x:
					compt += 1
			if compt > 1:
				return False

		return True
	def __translate_days(self, days_string):
		""" Translate days letters (smtwhfa) in days words:
			m -> Monday
			t -> Tuesday
			w -> Wednesday
			h -> Thursday
			f -> Friday
			a -> Saturday
			s -> Sunday
		"""
		translate_dict = { }
		translate_dict['m'] = "Monday"
		translate_dict['t'] = "Tuesday"
		translate_dict['w'] = "Wednesday"
		translate_dict['h'] = "Thursday"
		translate_dict['f'] = "Friday"
		translate_dict['a'] = "Saturday"
		translate_dict['s'] = "Sunday"

		i = 0
		translated = ""
		for l in days_string:
			l = translate_dict[l]
			if i < len(days_string)-1:
				l += ", "
			translated += l
			i += 1
		return translated
	def ExportXML(self, timespace, doreturn=True):
		""" Display the constraints of a time space (XML output)
		"""
		# XML output
		data = "<time-constraints-list>" + "\n"
		for i in self.constraints_dict[timespace]["constraints"]:
			i['weekdays'] = self.__translate_days(i['weekdays'])
			data += "\t" + "<time-constraint>\n" \
			+ "\t\t" + "<weekdays>" + str(i['weekdays']) + "</weekdays>\n" \
			+ "\t\t" + "<starthours>" + str(i['starthours']) + "</starthours>\n" \
			+ "\t\t" + "<startminutes>" + str(i['startminutes']) + "</startminutes>\n" \
			+ "\t\t" + "<endhours>" + str(i['endhours']) + "</endhours>\n" \
			+ "\t\t" + "<endminutes>" + str(i['endminutes']) + "</endminutes>\n"
			data += "\t" + "</time-constraint>\n"
	
		data += "</time-constraints-list>"
	
		if doreturn:
			return data
		else:
			sys.stdout.write( data )
	def Export(self, timespace, doreturn=True):
		""" Display the constraints of a time space (Normal output)
		"""
		data = ""
		# Normal output
		identifier = 0
		for i in self.constraints_dict[timespace]["constraints"]:
			data += str(identifier) + "\t" \
				+ str(i['weekdays']) + "\t\t" \
				+ str(i['starthours']) + ":" \
				+ str(i['startminutes']) + "-" \
				+ str(i['endhours']) + ":" \
				+ str(i['endminutes']) + "\n"
			identifier += 1
					
		if doreturn:
			return data
		else:
			sys.stdout.write( data )
	def ModifyTimeConstraint(self, timespace, constraint_id, weekdays="", timezone=""):
		""" Modify the time spaces timeworkingday and timepause.
		Parameters:
			- constraint_id: constrainttomodify's id (it's an integer)
			- weekdays: string of day letters (smtwhfa)
			- timezone: a valid timezone HH:MM-HH:MM
		"""
		# Redondant tests but skip borring rollback...
		if not self.__is_a_valid_timezone(timezone):
			raise exceptions.BadArgumentError, "The time zone is not valid (format is HH:MM-HH:MM)"
		if not self.__is_a_valid_weekdays(weekdays):
			raise exceptions.BadArgumentError, "Invalid weekdays string"

		DeleteTimeConstraint(timespace, constraint_id)
		AddTimeConstraint(timespace, weekdays, timezone)
	def DeleteTimeConstraint(self, timespace, constraint_id):
		""" Delete a time constraint in a time space
		"""
		if not self.__is_a_valid_id(constraint_id):
			raise exceptions.BadArgumentError, "No constraint of "+str(self.name)+" has the id="+str(constraint_id)
		del(self.constraints_dict[timespace]["constraints"][constraint_id])
	def AddTimeConstraint(self, timespace, weekdays, timezone):
		""" Add a time constraint in the time spaces timeworkingday and timepause.
		Parameters:
			- timespace: timeworkingday or timepause
			- weekdays: string of day letters (smtwhfa)
			- timezone: a valid timezone HH:MM-HH:MM
		"""
		# Validity tests of parameters
		if not self.__is_a_valid_timezone(timezone):
			raise exceptions.BadArgumentError, "The time zone is not valid (format is HH:MM-HH:MM)"
		if not self.__is_a_valid_weekdays(weekdays):
			raise exceptions.BadArgumentError, "Invalid weekdays string"

		self.constraints_dict[timespace]["constraints"].append({
												'weekdays': str(weekdays),
												'starthours': timezone[0:2],
												'startminutes': timezone[2:4],
												'endhours': timezone[6:8],
												'endminutes': timezone[8:10]
												})
	def SetRedirection(self, timespace, url):
		""" Change the url redirection of the rule which is restricted by 'timespace'
		"""
		self.constraints_dict[timespace]["redirection"] = url
	def GetRedirection(self, timespace):
		""" Get the url redirection of the rule which is restricted by 'timespace'
		"""
		return self.constraints_dict[timespace]["redirection"]
