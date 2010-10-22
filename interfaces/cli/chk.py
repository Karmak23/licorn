#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
Licorn CLI - http://dev.licorn.org/documentation/cli

check - check and repair things on an Licorn System.

Copyright (C) 2005-2010 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

from licorn.foundations.constants import filters
from licorn.foundations.ltrace    import ltrace
from licorn.foundations           import logging, styles
from licorn.interfaces.cli import cli_main, cli_select

_app = {
	"name"     		: "licorn-check",
	"description"	: "Licorn Check Entries",
	"author"   		: "Olivier Cortès <olive@deep-ocean.net>"
	}

def chk_user(opts, args, users, **kwargs):
	""" Check one or more user account(s). """
	include_id_lists=[
		(opts.login, users.login_to_uid),
		(opts.uid, users.confirm_uid)
	]
	exclude_id_lists=[
		(opts.exclude, users.guess_identifier),
		(opts.exclude_login, users.login_to_uid),
		(opts.exclude_uid, users.confirm_uid)
	]
	if opts.all and (
		(
			# NOTE TO THE READER: don't event try to simplify these conditions,
			# or the order the tests: they just MATTER. Read the tests in pure
			# english to undestand them and why the order is important.
				opts.non_interactive and opts.force) or opts.batch \
			or (opts.non_interactive and logging.ask_for_repair(
				'Are you sure you want to check all users ?',
				auto_answer=opts.auto_answer) or not opts.non_interactive)
		):
			include_id_lists.extend([
				(users.Select(filters.STD), users.confirm_uid),
				(users.Select(filters.SYSUNRSTR), users.confirm_uid)
				])
	uids_to_chk = cli_select(users, 'user', args,
		include_id_lists=include_id_lists,
		exclude_id_lists=exclude_id_lists
		)

	assert ltrace('chk', '> chk_user(%s)' % uids_to_chk)

	if uids_to_chk != []:
		if opts.force or opts.batch or opts.non_interactive:
			users.CheckUsers(uids_to_chk, minimal=opts.minimal,
				auto_answer=opts.auto_answer, batch=opts.batch,
				listener=opts.listener)
		else:
			for uid in uids_to_chk:
				if logging.ask_for_repair('''Check user %s ?''' %
					styles.stylize(styles.ST_LOGIN, users.uid_to_login(uid)),
					auto_answer=opts.auto_answer):
					users.CheckUsers([uid], minimal=opts.minimal,
						auto_answer=opts.auto_answer, batch=opts.batch,
						listener=opts.listener)
	assert ltrace('chk', '< chk_user()')
def chk_group(opts, args, groups, **kwargs):
	""" Check one or more group(s). """
	include_id_lists=[
		(opts.name, groups.name_to_gid),
		(opts.gid, groups.confirm_gid)
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
				'Are you sure you want to check all users ?',
				auto_answer=opts.auto_answer) or not opts.non_interactive)
		):
			include_id_lists.extend([
				(groups.Select(filters.STD), groups.confirm_gid),
				(groups.Select(filters.SYSUNRSTR), groups.confirm_gid)
				])
	gids_to_chk = cli_select(groups, 'group', args,
		include_id_lists=include_id_lists,
		exclude_id_lists=exclude_id_lists,
		default_selection=filters.STD,
		all=opts.all)

	assert ltrace('chk', '> chk_group(%s)' % gids_to_chk)

	if gids_to_chk != []:
		if opts.force or opts.batch or opts.non_interactive:
			groups.CheckGroups(gids_to_check=gids_to_chk,
				minimal=opts.minimal, batch=opts.batch,
				auto_answer=opts.auto_answer, force=opts.force,
				listener=opts.listener)
		else:
			for gid in gids_to_chk:
				if logging.ask_for_repair('''Check group %s ?''' %
					styles.stylize(styles.ST_LOGIN, groups.gid_to_name(gid)),
					auto_answer=opts.auto_answer):
					groups.CheckGroups(gids_to_check=[gid],
						minimal=opts.minimal, batch=opts.batch,
						auto_answer=opts.auto_answer, force=opts.force,
						listener=opts.listener)
	assert ltrace('chk', '< chk_group()')
def chk_profile(opts, args, profiles, **kwargs):
	""" TODO: to be implemented. """
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
			raise NotImplementedError("Sorry, not yet.")
def chk_configuration(opts, args, configuration, **kwargs):
	""" TODO: to be implemented. """

	configuration.check(opts.minimal, batch=opts.batch,
		auto_answer=opts.auto_answer, listener=opts.listener)
def chk_main():
	import argparser as agp

	functions = {
		'usr':	         (agp.chk_user_parse_arguments, chk_user),
		'user':	         (agp.chk_user_parse_arguments, chk_user),
		'users':         (agp.chk_user_parse_arguments, chk_user),
		'grp':           (agp.chk_group_parse_arguments, chk_group),
		'group':         (agp.chk_group_parse_arguments, chk_group),
		'groups':        (agp.chk_group_parse_arguments, chk_group),
		'profile':       (agp.chk_profile_parse_arguments, chk_profile),
		'profiles':      (agp.chk_profile_parse_arguments, chk_profile),
		'conf':			 (agp.chk_configuration_parse_arguments, chk_configuration),
		'config':		 (agp.chk_configuration_parse_arguments, chk_configuration),
		'configuration': (agp.chk_configuration_parse_arguments, chk_configuration),
	}

	cli_main(functions, _app)

if __name__ == "__main__":
	chk_main()
