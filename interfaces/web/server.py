# -*- coding: utf-8 -*-

import os, time, re

from subprocess            import Popen, PIPE
from licorn.core           import users, configuration
from licorn.foundations    import logging
from licorn.interfaces.web import utils as w

#remove this after testing
reload(w)

def ctxtnav():
	return '''
	<div id="ctxtnav" class="nav">
        <h2>Context Navigation</h2>
		<ul>
		<li><a href="/server/reboot" title="%s" class="lightwindow">
		<div class="ctxt-icon" id="icon-reboot">%s</div></a></li>
		<li><a href="/server/halt" title="%s" class="lightwindow">
		<div class="ctxt-icon" id="icon-shutdown">%s</div></a></li>
		</ul>
        <hr />
	</div>
	''' % (
		_('Restart server.'),
		_('Restart server'),
		_('Shutdown server.'),
		_('Shutdown server'))

def reboot(uri, http_user, sure = False):
	if sure:
		return w.minipage(w.lbox('''<div class="vspacer"></div>%s''' % \
			_('Rebooting…')))
	else:
		return w.minipage(w.lbox('''%s
		<div class="vspacer"></div>
		<table class="lbox-table">
			<tr>
				<td>
					<form name="reboot_form" id="reboot_form"
						action="/server/reboot/sure" method="get">
						<a href="/server/reboot/sure"
							params="lightwindow_form=reboot_form,'''
							'''lightwindow_width=320,lightwindow_height=140"
							class="lightwindow_action" rel="submitForm">
							<button>%s</button>
						</a>
					</form>
				</td>
				<td>
					<a href="#" class="lightwindow_action" rel="deactivate">
						<button>%s</button></a>
				</td>
			</tr>
		</table>
		''' % (
		_('Sure you want to reboot the %s server?') % configuration.app_name,
		_('YES'),
		_('NO'))))
def halt(uri, http_user, sure = False):
	if sure:
		return w.minipage(w.lbox('''<div class="vspacer"></div>%s''' % \
			_('Shutting down…')))
	else:
		return w.minipage(w.lbox('''%s<div class="vspacer"></div>
		<table class="lbox-table">
			<tr>
				<td>
					<form name="shutdown_form" id="shutdown_form"
						action="/server/halt/sure" method="get">
						<a href="/server/halt/sure"
							params="lightwindow_form=shutdown_form,'''
							'''lightwindow_width=320,lightwindow_height=140"
							class="lightwindow_action" rel="submitForm">
							<button>%s</button>
						</a>
					</form>
				</td>
				<td>
					<a href="#" class="lightwindow_action" rel="deactivate">
					<button>%s</button></a>
				</td>
			</tr>
		</table>''' % (
		_('Sure you want to shutdown the %s server?') % configuration.app_name,
		_('YES'),
		_('NO'))))
