# -*- coding: utf-8 -*-
"""
Licorn® WMI - users views

:copyright:
	* 2008-2011 Olivier Cortès <olive@deep-ocean.net>
	* 2010-2011 META IT - Olivier Cortès <oc@meta-it.fr>
	* 2011-2012 Robin Lucbernet <robinlucbernet@gmail.com>
	* 2012 Olivier Cortès <olive@licorn.org>
:license: GNU GPL version 2
"""

import os, time, base64, tempfile, crack, json, types

from threading import current_thread
from operator  import attrgetter

from django.shortcuts               import *
from django.template.loader         import render_to_string
from django.utils.encoding          import smart_str
from django.utils.translation       import ugettext as _
from django.core.servers.basehttp   import FileWrapper
from django.contrib.auth.decorators import login_required

from licorn.foundations           import exceptions, logging, settings
from licorn.foundations           import hlstr, pyutils
from licorn.foundations.base      import Enumeration, LicornConfigObject
from licorn.foundations.constants import filters, relation
from licorn.foundations.ltrace    import *
from licorn.foundations.ltraces   import *

from licorn.core                  import LMC

from collections import OrderedDict

# FIXME: OLD!! MOVE FUNCTIONS to new interfaces.wmi.libs.utils.
# WARNING: this import will fail if nobody has previously called `wmi.init()`.
# This should have been done in the WMIThread.run() method. Anyway, this must
# disappear soon!!
from licorn.interfaces.wmi.libs            import old_utils as w

from licorn.interfaces.wmi.app             import wmi_event_app
from licorn.interfaces.wmi.libs            import utils
from licorn.interfaces.wmi.libs.decorators import staff_only, check_users

from forms import UserForm, SkelInput, ImportForm, get_user_form_blocks

# NOTE: mod() is not protected by @staff_only because standard users
# need to be able to modify their personnal attributes (except groups).
@login_required
@check_users('mod')
def mod(request, uid, action, value, *args, **kwargs):
	""" Modify all properties of a user account. """

	assert ltrace_func(TRACE_DJANGO)

	user = LMC.users.by_uid(uid)

	def mod_groups(group_id, rel_id):
		# Typical request: /mod/user_id/groups/group_id/rel_id

		group = LMC.groups.by_gid(group_id)
		if user.is_standard:
			g_group = group.guest_group
			r_group = group.responsible_group

		if rel_id == relation.MEMBER:
			group.add_Users(users_to_add=[user.uidNumber], force=True)

		elif rel_id == relation.GUEST:
			g_group.add_Users(users_to_add=[user.uidNumber], force=True)

		elif rel_id == relation.RESPONSIBLE:
			r_group.add_Users(users_to_add=[user.uidNumber], force=True)

		else:
			# the user has to be deleted, but from standard group or from helpers ?
			if group.get_relationship(user.uidNumber) == relation.GUEST:
				g_group.del_Users(users_to_del=[user.uidNumber])

			elif group.get_relationship(user.uidNumber) == relation.RESPONSIBLE:
				r_group.del_Users(users_to_del=[user.uidNumber])

			elif group.get_relationship(user.uidNumber) == relation.MEMBER:
				group.del_Users(users_to_del=[user.uidNumber])

	if action == 'gecos':
		if value != user.gecos:
			user.gecos = value

	elif action == 'password':
		user.password = value

	elif action == 'shell':
		if value != user.loginShell:
			user.loginShell = value

	elif action == 'groups':
		mod_groups(*(int(x) for x in value.split('/')))

	elif action == 'skel':
		user.apply_skel(value)

	elif action == 'lock':
		user.locked = True

	elif action == 'unlock':
		user.locked = False

	# updating the web page is done in the event handler, via the push stream.
	return HttpResponse('MOD DONE.')

@staff_only
@check_users('delete')
def delete(request, uid, no_archive, *args, **kwargs):

	assert ltrace_func(TRACE_DJANGO)

	# remote:
	#LMC.rwi.generic_controller_method_call('users', 'del_User',
	#					user=int(uid), no_archive=bool(no_archive))

	# local:
	LMC.users.del_User(user=int(uid), no_archive=bool(no_archive))

	return HttpResponse('DONE.')

@staff_only
def massive(request, uids, action, *args, **kwargs):
	print "massive ", uids, action, value
	assert ltrace_func(TRACE_DJANGO)

	if action == 'delete':
		no_archive = bool(kwargs.get('value', False))
		for uid in uids.split(','):
			delete(request, uid=int(uid), no_archive=no_archive)

			# Get a chance for events to be forwarded,
			# force thread switch in the interpreter.
			time.sleep(0)
	if action == 'lock':
		for uid in uids.split(','):
			user = LMC.users.guess_one(uid)
			print "working on user {0}({1}) ; is locked : {2}".format(user.login, user.uid, user.is_locked)


			if user.is_locked:
				mod(request, uid=user.uid, action='unlock', value=True)
			else:
				mod(request, uid=user.uid, action='lock', value=True)
	if action == 'skel':
		for uid in uids.split(','):
			if uid != '':
				mod(request, uid=uid, action='skel', value=kwargs.get('skel'))
	if action == 'export':

		selected_uids = [int(u) for u in uids.split(',')]

		print "EXPORTING USERS IN ", kwargs.get('value')

		if kwargs.get('value').lower() == 'csv':
			export = LMC.users.ExportCSV(selected=selected_uids)
			extension = '.csv'

		else:
			export = LMC.users.to_XML(selected=[LMC.users.by_uid(u)
													for u in selected_uids])
			extension = '.xml'

		export_handler, export_filename = tempfile.mkstemp(suffix=extension,
															prefix='export_')

		for chunk in export:
			os.write(export_handler, chunk)
		os.close(export_handler)

		return HttpResponse(json.dumps({ "file_name" : export_filename, "preview": export}))

	if action == 'shell':
		# massively mod shell
		for uid in uids.split(','):
			mod(request, uid=uid, action='shell', value=kwargs.get('shell'))
	if action == 'groups':
		for uid in uids.split(','):
			mod(request, uid=uid, action='groups', value=kwargs.get('value'))
			# group is : group_id/rel_id

	if action == 'edit':
		return get_user_template(request, "massiv",
			[ groups.append(LMC.groups.guess_one(gid)) for gid in uids.split(',')])

	return HttpResponse('MASSIVE DONE.')

@staff_only
def create(request, **kwargs):

	assert ltrace_func(TRACE_DJANGO)

	if request.method == 'POST':

		try:
			profile     = LMC.profiles[
								int(w.my_unquote(request.POST['profile']))
							]
			shell       = request.POST['shell']
			gecos       = w.my_unquote(request.POST['gecos'])
			login       = w.my_unquote(request.POST['login'])

			# XXX: why not unquote the password too ?
			password    = request.POST['password']

			user, password = LMC.users.add_User(
						login=login if login != '' else None,
						gecos=gecos if gecos != '' else None,
						password=password,
						# we don't use `in_groups` to
						# avoid the #771 security issue.
					 	#in_groups=…,
						shell=LMC.configuration.users.default_shell
										if shell is None else shell,
						profile=profile)

			# We call 'mod()' to make the needed checks
			# and avoid URL/POST forgeries cf #771.
			for post_name, rel in (('member_groups', relation.MEMBER),
								('guest_groups', relation.GUEST),
								('resp_groups', relation.RESPONSIBLE)):
				for g in request.POST.getlist(post_name):
					if g != '':
						mod(request, uid=user.uid, action='groups',
									value='%s/%s' % (g, rel))

		except Exception, e:
			logging.exception(_(u'Unable to add user'))
			wmi_event_app.queue(request).put(utils.notify(_('Unable to add '
									'user: {0}.').format(e)))

	return HttpResponse('DONE.')

# TODO:
@staff_only
def massive_import(uri, http_user, filename, firstname_col, lastname_col,
													group_col, **kwargs):
	assert ltrace_func(TRACE_DJANGO)

	pass

@staff_only
def user(request, uid=None, login=None, action='edit', *args, **kwargs):

	assert ltrace_func(TRACE_DJANGO)

	try:
		# remote:
		#user = utils.select('users', [ uid ])[0]

		# local:
		user = LMC.users.by_uid(uid)
	except:
		try:
			# remote:
			#user = utils.select('users', [ login ])[0]

			# local:
			user = LMC.users.by_login(login)

		except:
			user = None

	# inform the user that the UI will take time to build,
	# to avoid re-clicks and (perfectly justified) grants.
	ngroups = len(LMC.groups.keys())
	if ngroups > 50:
		# TODO: make the notification sticky and remove it just
		# before returning the rendered template result.
		utils.notification(request, _('Building user {0} form, please wait…').format(
			_('edit') if action == 'edit' else _('creation')), 3000 + 5 * ngroups, 'wait_for_rendering')

	return get_user_template(request, action, user)

@staff_only
def upload_file(request, *args, **kwargs):

	assert ltrace_func(TRACE_DJANGO)

	if request.method == 'POST':
		csv_file = request.FILES['file']

		csv_handler, csv_filename = tempfile.mkstemp()

		destination = open(csv_filename, 'wb+')
		t = ''
		for chunk in csv_file.chunks():
			destination.write(chunk)
			t += chunk
		destination.close()
		#lprint(destination)
		return HttpResponse(csv_filename)

@staff_only
def import_view(request, confirm='', *args, **kwargs):

	assert ltrace_func(TRACE_DJANGO)

	if request.method == 'POST':

		opts                = LicornConfigObject()
		opts.filename       = request.POST['csv_filepath']
		opts.profile        = request.POST['profile']
		opts.confirm_import = bool(confirm)
		opts.no_sync        = False
		opts.separator      = request.POST['separator']
		opts.lastname_col   = int(request.POST['lastname_col']) \
								if request.POST['lastname_col'] != '' else None
		opts.firstname_col  = int(request.POST['firstname_col']) \
								if request.POST['firstname_col'] != '' else None
		opts.gecos_col   = int(request.POST['gecos_col']) \
								if request.POST['gecos_col'] != '' else None
		opts.profile_col   = int(request.POST['profile_col']) \
								if request.POST['profile_col'] != '' else None
		opts.group_col      = int(request.POST['group_col']) \
								if request.POST['group_col'] != '' else None
		opts.login_col      = int(request.POST['login_col']) \
								if request.POST['login_col'] != '' else None
		opts.password_col   = int(request.POST['password_col']) \
								if request.POST['password_col'] != '' else None

		# Execute the import in background in order to return instantly
		# remote:
		#LMC.rwi.import_users(opts=opts, background=True)

		# local:
		from licorn.daemon.main import daemon
		daemon.rwi.import_users(opts=opts, background=True)

		return HttpResponse('DONE.')

	else:
		form = ImportForm()

		if request.is_ajax():
			return render(request, '/users/import.html', {'form': form})

		else:
			return render(request, '/users/import_template.html', {'form': form})

@staff_only
def main(request, sort="login", order="asc", select=None, **kwargs):
	""" render the user main page """
	assert ltrace_func(TRACE_DJANGO)

	users = LMC.users.select(filters.STANDARD)

	if request.user.is_superuser:
		for u in LMC.users.select(filters.SYSTEM):
				users.append(u)

	return render(request, 'users/index.html', {
			'request' : request,
			'users' : pyutils.alphanum_sort(users, key='login')
		})



# ================================================================ Helper Views
#
# They are not protected because they are not security-sensitive, and
# could possibly help other processes / programs outside of Licorn®.

def check_pwd_strenght(request, pwd, *args, **kwargs):

	assert ltrace_func(TRACE_DJANGO)

	try:
		crack.FascistCheck(pwd)

	except ValueError, e:
		return HttpResponse(e)

	else:
		return HttpResponse(pwd)

def generate_pwd(request, *args, **kwargs):
	return HttpResponse(render_to_string('/users/parts/generate_password.html', {
		'password' : hlstr.generate_password(maxlen=10),
		}))

def massive_select_template(request, action_name, uids, *args, **kwargs):

	users = [ LMC.users.guess_one(u) for u in uids.split(',') ]

	if action_name == 'edit':
		return get_user_template(request, "massiv", users)

	if action_name in ('skel', ):
		_dict = {
			'users'  : [ u for u in users if u.is_standard ],
			'others' : [ u for u in users if not u.is_standard ]
		 }

	else:
		_dict = { 'users' : users, 'others': None }

	if action_name == 'delete':
		_dict.update({
				'archive_dir' : settings.home_archive_dir,
				'admin_group' : settings.defaults.admin_group
			})

	if _dict.get('others') and not _dict.get('users'):
		_dict['noop'] = True

	else:
		_dict['noop'] = False

	return HttpResponse(render_to_string('users/parts/massive_{0}.html'.format(
														action_name), _dict))

def get_user_template(request, mode, users):
	print "get_user_template", mode, users

	if type(users) != types.ListType:
		users = [ users ]

	_dict = {}


	groups_lists = [
		{
			'list_name'    : 'bstandard',
			'list_content' : ''.join([render_to_string('/users/parts/group_membership.html', {
				'users' : users,
				'group' : g
				}) for g in pyutils.alphanum_sort(LMC.groups.select(filters.STANDARD), key= 'name')])
		}
	]

	# if super user append the system users list
	if request.user.is_superuser:
		groups_lists.append(
			{
				'list_name'    : 'cprivileged',
				'list_content' : ''.join([render_to_string('/users/parts/group_membership.html', {
					'users' : users,
					'group' : g
					}) for g in pyutils.alphanum_sort(LMC.groups.select(filters.PRIVILEGED), key='name') if not g.is_helper])
			}
		)
		groups_lists.append(
			{
				'list_name'    : 'dsystem',
				'list_content' : ''.join([render_to_string('/users/parts/group_membership.html', {
					'users' : users,
					'group' : g
					}) for g in pyutils.alphanum_sort(LMC.groups.select(filters.SYSTEM), key='name') if not g.is_helper])
			}
		)

	# we need to sort the form_blocks dict to display headers in order
	sorted_blocks = OrderedDict({})
	form_blocks = get_user_form_blocks(request)
	for k in sorted(form_blocks.iterkeys()):
		sorted_blocks.update({ k: form_blocks[k]})


	print "BLOCKSSS", sorted_blocks

	_dict.update({
				'mode'    	  : mode,
				'form'        : UserForm(mode, users[0]),
				'groups_lists' : groups_lists,
				'form_blocks' : sorted_blocks
			})

	if mode == 'edit':
		_dict.update({"user" : users[0] })

	#print "rendering group.html", _dict

	if request.is_ajax():

		return render(request, 'users/user.html', _dict)

	else:
		# render the full page
		groups = LMC.groups.select(filters.STANDARD)

		if request.user.is_superuser:
			for g in LMC.groups.select(filters.SYSTEM):
				if not g.is_helper:
					groups.append(g)
		else:
			for g in LMC.groups.select(filters.PRIVILEGED):
				groups.append(g)

		return render(request, 'users/index.html', {
				'request' : request,
				'users' : pyutils.alphanum_sort(users, key= 'login'),
				'modal_html' : render(request, 'users/user.html', _dict) \
						if mode == 'new' else render_to_string('users/user.html', _dict)
			})


def hotkeys_help(request):
	return render(request, '/users/parts/hotkeys_help.html')
