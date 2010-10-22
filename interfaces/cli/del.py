#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

delete - delete sompething on the system, an unser account, a group, etc.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2006-2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.

"""

import sys, re, os

from licorn.foundations           import logging, exceptions, styles
from licorn.foundations.constants import filters

from licorn.interfaces.cli import cli_main, cli_select
from licorn.core.configuration import LicornConfiguration
configuration = LicornConfiguration()

_app = {
	"name"        : "licorn-delete",
	"description" : "Licorn Delete Entries",
	"author"      : "Olivier Cortès <olive@deep-ocean.net>, Régis Cobrun <reg53fr@yahoo.fr>"
	}

def desimport_groups(opts, args, groups, **kwargs):
	""" Delete the groups (and theyr members) present in a import file.	"""

	if opts.filename is None:
		raise exceptions.BadArgumentError, "You must specify a file name"

	delete_file = file(opts.filename, 'r')

	groups_to_del = []

	user_re = re.compile("^\"?\w*\"?;\"?\w*\"?;\"?(?P<group>\w*)\"?$", re.UNICODE)
	for ligne in delete_file:
		mo = user_re.match(ligne)
		if mo is not None:
			u = mo.groupdict()
			g = u['group']
			if g not in groups_to_del:
				groups_to_del.append(g)

	delete_file.close()

	# Deleting
	length_groups = len(groups_to_del)
	quantity = length_groups
	if quantity <= 0:
		quantity = 1
	delta = 100.0 / float(quantity) # increment for progress indicator
	progression = 0.0
	i = 0 # to print i/length

	for g in groups_to_del:
		try:
			i += 1
			sys.stdout.write("\rDeleting groups (" + str(i) + "/" + str(length_groups) + "). Progression: " + str(int(progression)) + "%")
			groups.DeleteGroup(profiles, g, True, True, users)
			progression += delta
			sys.stdout.flush()
		except exceptions.LicornException, e:
			logging.warning(str(e))
	profiles.WriteConf(configuration.profiles_config_file)
	print "\nFinished"
def del_user(opts, args, users, **kwargs):
	""" delete a user account. """
	include_id_lists=[
		(opts.login, users.login_to_uid),
		(opts.uid, users.confirm_uid)
	]
	exclude_id_lists=[
		(opts.exclude, users.guess_identifier),
		(opts.exclude_login, users.login_to_uid),
		(opts.exclude_uid, users.confirm_uid),
		([os.getuid()], users.confirm_uid)
	]
	if opts.all and (
		(
			# NOTE TO THE READER: don't event try to simplify these conditions,
			# or the order the tests: they just MATTER. Read the tests in pure
			# english to undestand them and why the order is important.
			opts.non_interactive and opts.force) or opts.batch \
			or (opts.non_interactive and logging.ask_for_repair(
				'Are you sure you want to delete all users ?',
				auto_answer=opts.auto_answer) or not opts.non_interactive)
		):
			include_id_lists.extend([
				(users.Select(filters.STD), users.confirm_uid),
				(users.Select(filters.SYSUNRSTR), users.confirm_uid)
				])
	uids_to_del = cli_select(users, 'user',	args=args,
			include_id_lists=include_id_lists,
			exclude_id_lists=exclude_id_lists)

	for uid in uids_to_del:
		if opts.non_interactive or opts.batch or opts.force or \
			logging.ask_for_repair('''Delete user %s ?''' % styles.stylize(
			styles.ST_LOGIN,users.uid_to_login(uid)),
			auto_answer=opts.auto_answer):
			users.DeleteUser(uid=uid, no_archive=opts.no_archive,
				listener=opts.listener)
			#logging.notice("Deleting user : %s" % users.uid_to_login(uid))

def del_user_from_groups(opts, args, users, groups):

	uids_to_del = cli_select(users, 'user',
			args,
			include_id_lists=[
				(opts.login, users.login_to_uid),
				(opts.uid, users.confirm_uid)
			])

	for g in opts.groups_to_del.split(','):
		if g != "":
			try:
				groups.DeleteUsersFromGroup(name=g, users_to_del=uids_to_del,
					batch=opts.batch, listener=opts.listener)
			except exceptions.DoesntExistsException, e:
				logging.warning(
					"Unable to remove user(s) %s from group %s (was: %s)."
					% (styles.stylize(styles.ST_LOGIN, opts.login),
					styles.stylize(styles.ST_NAME, g), str(e)))
			except exceptions.LicornException, e:
				raise exceptions.LicornRuntimeError(
					"Unable to remove user(s) %s from group %s (was: %s)."
					% (styles.stylize(styles.ST_LOGIN, opts.login),
					styles.stylize(styles.ST_NAME, g), str(e)))
def dispatch_del_user(opts, args, users, groups, **kwargs):
	if opts.login is None:
		if len(args) == 2:
			opts.login = args[1]
			args[1] = ''
			del_user(opts, args, users)
		elif len(args) == 3:
			opts.login = args[1]
			opts.groups_to_del = args[2]
			args[1] = ''
			args[2] = ''
			del_user_from_groups(opts, args, users, groups)
		else:
			del_user(opts, args, users)
	else:
		del_user(opts, args, users)
def del_group(opts, args, groups, **kwargs):
	""" delete an Licorn group. """
	selection = filters.NONE
	if opts.empty:
		selection = filters.EMPTY
	include_id_lists=[
		(opts.name, groups.name_to_gid),
		(opts.gid, groups.confirm_gid),
	]
	exclude_id_lists = [
		(opts.exclude, groups.guess_identifier),
		(opts.exclude_group, groups.name_to_gid),
		(opts.exclude_gid, groups.confirm_gid)
	]
	if opts.all and (
		(
			# NOTE TO THE READER: don't event try to simplify these conditions,
			# or the order the tests: they just MATTER. Read the tests in pure
			# english to undestand them and why the order is important.
			opts.non_interactive and opts.force) or opts.batch \
			or (opts.non_interactive and logging.ask_for_repair(
				'Are you sure you want to delete all groups ?',
				auto_answer=opts.auto_answer) or not opts.non_interactive)
		):
			include_id_lists.extend([
				(groups.Select(filters.STD), groups.confirm_gid),
				(groups.Select(filters.SYSUNRSTR), groups.confirm_gid)
				])
	gids_to_del = cli_select(groups, 'group',
				args,
				include_id_lists=include_id_lists,
				exclude_id_lists = exclude_id_lists,
				default_selection=selection
				)
	for gid in gids_to_del:
		if opts.non_interactive or opts.batch or opts.force or \
			logging.ask_for_repair('''Delete group %s ?''' % styles.stylize(
			styles.ST_LOGIN,groups.gid_to_name(gid)),
			auto_answer=opts.auto_answer):
			groups.DeleteGroup(gid=gid, del_users=opts.del_users,
				no_archive=opts.no_archive, listener=opts.listener)
			#logging.notice("Deleting group : %s" % groups.gid_to_name(gid))
def del_profile(opts, args, profiles, **kwargs):
	""" Delete a system wide User profile. """
	include_id_lists=[
		(opts.name, profiles.name_to_group),
		(opts.group, profiles.confirm_group)
	]
	exclude_id_lists=[
		(opts.exclude, profiles.guess_identifier)
	]
	if opts.all and (
		(
			# NOTE TO THE READER: don't event try to simplify these conditions,
			# or the order the tests: they just MATTER. Read the tests in pure
			# english to undestand them and why the order is important.
			opts.non_interactive and opts.force) or opts.batch \
			or (opts.non_interactive and logging.ask_for_repair(
				'Are you sure you want to delete all profiles ?',
				opts.auto_answer) \
			or not opts.non_interactive)
		):
			include_id_lists.extend([
					(profiles.Select(filters.ALL), profiles.guess_identifier)
				])

	profiles_to_del = cli_select(profiles, 'profile', args,
			include_id_lists=include_id_lists,
			exclude_id_lists=exclude_id_lists)

	for p in profiles_to_del:
		if opts.non_interactive or opts.batch or opts.force or \
			logging.ask_for_repair('''Delete profile %s ?''' % styles.stylize(
			styles.ST_LOGIN,profiles.group_to_name(p)),
			auto_answer=opts.auto_answer):
			profiles.DeleteProfile(group=p, del_users=opts.del_users,
				no_archive=opts.no_archive, listener=opts.listener)
			#logging.notice("Deleting profile : %s" % profiles.group_to_name(p))
def del_keyword(opts, args, keywords, **kwargs):
	""" delete a system wide User profile. """

	if opts.name is None and len(args) == 2:
		opts.name = args[1]

	keywords.DeleteKeyword(opts.name, opts.del_children, listener=opts.listener)
def del_privilege(opts, args, privileges, **kwargs):
	if opts.privileges_to_remove is None and len(args) == 2:
		opts.privileges_to_remove = args[1]
	include_priv_lists=[
		(opts.privileges_to_remove, privileges.confirm_privilege),
	]
	exclude_priv_lists=[
		(opts.exclude, privileges.confirm_privilege),
	]
	if opts.all and (
		(
			# NOTE TO THE READER: don't event try to simplify these conditions,
			# or the order the tests: they just MATTER. Read the tests in pure
			# english to undestand them and why the order is important.
			opts.non_interactive and opts.force) or opts.batch \
			or (opts.non_interactive and logging.ask_for_repair(
				'Are you sure you want to delete all users ?',
				auto_answer=opts.auto_answer) or not opts.non_interactive)
		):
			include_priv_lists.extend([
				(privileges.Select(filters.ALL), privileges.confirm_privilege),
				])
	privs_to_del = cli_select(privileges, 'privilege',args=args,
			include_id_lists=include_priv_lists,
			exclude_id_lists=exclude_priv_lists)

	for priv_name in privs_to_del:
		if priv_name is not None and (
		opts.non_interactive or opts.batch or opts.force or \
		logging.ask_for_repair('''Delete privilege %s ?''' %
			styles.stylize(styles.ST_LOGIN, priv_name),
			auto_answer=opts.auto_answer)):
			privileges.delete(
				[priv_name], listener=opts.listener)

def del_main():
	""" DELETE main function. """
	import argparser as agp

	functions = {
		'usr':	         (agp.del_user_parse_arguments, dispatch_del_user),
		'user':	         (agp.del_user_parse_arguments, dispatch_del_user),
		'users':         (agp.del_user_parse_arguments, dispatch_del_user),
		'grp':           (agp.del_group_parse_arguments, del_group),
		'group':         (agp.del_group_parse_arguments, del_group),
		'groups':        (agp.delimport_parse_arguments, desimport_groups),
		'profile':       (agp.del_profile_parse_arguments, del_profile),
		'profiles':      (agp.del_profile_parse_arguments, del_profile),
		'priv':			 (agp.del_privilege_parse_arguments, del_privilege),
		'privs':		 (agp.del_privilege_parse_arguments, del_privilege),
		'privilege':	 (agp.del_privilege_parse_arguments, del_privilege),
		'privileges':	 (agp.del_privilege_parse_arguments, del_privilege),
		'kw':            (agp.del_keyword_parse_arguments, del_keyword),
		'tag':           (agp.del_keyword_parse_arguments, del_keyword),
		'tags':          (agp.del_keyword_parse_arguments, del_keyword),
		'keyword':       (agp.del_keyword_parse_arguments, del_keyword),
		'keywords':      (agp.del_keyword_parse_arguments, del_keyword),
	}

	cli_main(functions, _app)

if __name__ == "__main__":
	del_main()
