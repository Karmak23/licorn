# -*- coding: utf-8 -*-

from licorn.core import LMC

# warning: this import will fail if nobody has previously called wmi.init()
# (this should have been done in the WMIThread.run() method.
from licorn.interfaces.wmi import utils as w

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

def reboot(uri, http_user, sure=False, **kwargs):

	data = ''

	if sure:
		(rettype, retdata) = w.run(['sudo', 'shutdown', '-r', 'now'], None,
		data, _('''Can't reboot the system.'''))

		if rettype == w.HTTP_TYPE_REDIRECT :
			return (w.HTTP_TYPE_TEXT, w.minipage(w.lbox(_('Rebooting…'))))
		else:
			return rettype, w.minipage(w.lbox(retdata))
	else:
		return (w.HTTP_TYPE_TEXT, w.minipage(w.lbox('''
		<div style="line-height: 1.5em; padding-bottom:20px">%s</div>
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
		_('Sure you want to reboot the %s server?') % LMC.configuration.app_name,
		_('YES'),
		_('NO')))))
def halt(uri, http_user, sure=False, **kwargs):

	data = ''

	if sure:
		(rettype, retdata) = w.run(['sudo', 'shutdown', '-p', 'now'], None,
		data, _('''Can't shutdown the system.'''))

		if rettype == w.HTTP_TYPE_REDIRECT :
			return (w.HTTP_TYPE_TEXT, w.minipage(w.lbox(_('Shutting down…'))))
		else:
			return rettype, w.minipage(w.lbox(retdata))

	else:
		return (w.HTTP_TYPE_TEXT, w.minipage(w.lbox('''
		<div  style="line-height: 1.5em; padding-bottom:20px">%s</div>
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
		_('Sure you want to shutdown the %s server?') % LMC.configuration.app_name,
		_('YES'),
		_('NO')))))
