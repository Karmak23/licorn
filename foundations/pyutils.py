# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://dev.licorn.org/documentation/foundations

pyutils - Pure Python utilities functions, which are not present in python 2.4

Copyright (C) 2007 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2

"""

from licorn.foundations import exceptions

def next_free(used_list, start, end):
	""" Find a new ID (which is not used).
		Return the smallest unused identifier in [start_id,end_id] of used_id_list.
		Note: don't sort the list before ! This function does it.
	"""
	used_list.sort()

	if start in used_list:
		cur = start + 1
		while cur in used_list:
			cur += 1
		if cur <= end:
			return cur
	else:
		return start
		
	raise exceptions.NoAvaibleIdentifierError()
def list2set(in_list):
	""" Transform a list to a set (ie remove duplicates). """
	out_set = []
	for elem in in_list:
		if elem in out_set: continue
		out_set.append(e)
	return out_set
def keep_false(x, y):
	""" function used in reduce(), keepping only False values in lists. """

	if x is False: return x
	else:          return y
