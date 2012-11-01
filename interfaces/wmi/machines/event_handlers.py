# -*- coding: utf-8 -*-

from django.template.loader       import render_to_string
from django.utils.translation     import ugettext as _
from licorn.foundations.network   import find_first_local_ip_address
from licorn.foundations.constants import host_status, host_types
from licorn.interfaces.wmi.libs   import utils

from licorn.core                  import LMC

import wmi_data

def get_machine(event):
	if event._forwarded:
		return LMC.machines[event.sender]

	else:
		try:
			return event.kwargs['host']

		except KeyError:
			return LMC.machines[find_first_local_ip_address()]
def update_machine_instance(machine):
	return utils.format_RPC_JS('update_instance',
								'machines',
								machine.wid,
								render_to_string('machines/machine_row.html', {
									'machine': machine,
									'host_status' : host_status,
									'get_host_status_html' : wmi_data.get_host_status_html,
									'get_host_os_html'     : wmi_data.get_host_os_html,
									'get_host_type_html'   : wmi_data.get_host_type_html}),
								"setup_row"
								)

def host_online_handler(request, event, reinit=False):

	machine = get_machine(event)

	yield utils.notify(_(u'New machine "{0}" found online.').format(machine.mid))

	yield update_machine_instance(machine)

	yield utils.format_RPC_JS('update_total_items', 'machines',
					'/' + str(len(LMC.machines.select(host_status.ONLINE))))
def host_back_online_handler(request, event, reinit=False):

	machine = get_machine(event)

	yield utils.notify(_(u'Machine "{0}" is back online.').format(machine.hostname))

	yield update_machine_instance(machine)
def host_offline_handler(request, event, reinit=False):

	machine = get_machine(event)

	yield utils.notify(_(u'Machine "{0}" is now offline.').format(machine.hostname))

	yield update_machine_instance(machine)
def licorn_host_online_handler(request, event, reinit=False):

	machine = get_machine(event)

	yield utils.notify(_(u'New Licorn® machine {0} discovered.').format(machine.mid))

	yield update_machine_instance(machine)
def machine_hostname_changed_handler(request, event, reinit=False):

	machine = get_machine(event)

	yield utils.notify(_(u'Machine with address {0} is now known as {1}.').format(
												machine.mid, machine.hostname))

	yield utils.format_RPC_JS('reload_div', '#machine_hostname_{0}'.format(machine.wid),
		machine.hostname)

	yield update_machine_instance(machine)
def licorn_host_shutdown_handler(request, event, reinit=False):
	raise NotImplementedError('TODO.')
def software_upgrades_started_handler(request, event, reinit=False):

	machine = get_machine(event)

	yield utils.notify(_(u'Software upgrades started on machine {0}.').format(
															machine.hostname))

	yield update_machine_instance(machine)

	#yield utils.format_RPC_JS('reload_div', "#machines_{0} #machine_status".format(machine.wid),
	#	"<img src='/media/images/throbber.gif'>")

def software_upgrades_finished_handler(request, event, reinit=False):

	machine = get_machine(event)

	yield utils.notify(_(u'Software upgrades finished on machine {0}.').format(
															machine.hostname))

	yield update_machine_instance(machine)
def machine_changed_handler(request, event, reinit=False):

	machine = get_machine(event)

	yield update_machine_instance(machine)
