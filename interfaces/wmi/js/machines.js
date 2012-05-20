/*
* Licorn WMI users page javascript
*
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
* Licensed under the terms of the GNU GPL version 2
*/

var _LIST = new List('machines', 'login', "#machines_list_content", '.machine_select', '.machine_content');


$(document).ready(function() {
	$("#users_list_content").html('<center><img style="margin-top:30px;" src="/images/progress/ajax-loader.gif"/></center>');
	_LIST.load_list();

	not_yet_dialog = new dialog('Not yet developped', 'Not yet developped');

});






// Necessary methods for change_content function
function init_events_sub_content_new() {
	//TODO
	//make_machines_interaction();
}

function init_events_list_header() {
	// search event
	$('#search_box').keyup(function(event) {

		if (DEBUG || DEBUG_USER) { console.log('<> KEYUP EVENT : on search box => '+$('#search_box').val()); }

		search_in_list($('#search_box').val());
	});
}
function search_in_list(search_string) {
	for(i=0 ; i<_LIST.items.length ; i++) {

		login = _LIST.items[i].login
		uid = _LIST.items[i].uid
		gecos = _LIST.items[i].gecos



		if (login.toLowerCase().search(search_string.toLowerCase()) == -1 &&
			uid.search(search_string) == -1 &&
			gecos.toLowerCase().search(search_string.toLowerCase()) == -1 ) {
			$("#"+login).hide();
			_LIST.items[i].displayed = false;
			$("#"+login).removeClass('display').addClass('hidden');

			//console.log('hiding '+login);
		}
		else {
			$("#"+login).show();
			_LIST.items[i].displayed = true;
			$("#"+login).removeClass('hidden').addClass('display');

			//console.log('displaying '+login);
		}
	}
}


function create_items(xml) {
	item_number = 0;
	$('<div />').html(xml).find("machine").each(function() {
		// user information
		machine_name = $(this).find("hostname").text();
		machine_id = $(this).find("mid").text();
		machine_managed = $(this).find("managed").text();
		machine_ether = $(this).find("ether").text();
		machine_expiry = $(this).find("expiry").text();
		
		_LIST.items[item_number] = new item(machine_name, machine_id, machine_managed, machine_ether, machine_expiry);

		item_number += 1;


				});

}

function item(machine_name, machine_id, machine_managed, machine_ether, machine_expiry) {

	//console.log("adding user "+user_login);

	this.hostname = machine_name;
	this.mid = machine_id;
	this.managed = machine_managed;
	this.ether = machine_ether;
	this.expiry = machine_expiry;
	this.displayed = true;
	this.selected = false;
}

function generate_items_list(items) {
	list_html = '';
	privs_tab = [];

	// pas besoin d'afficher ce titre. uniquement pour les privilèges
	//list_html += '<div class="main_content_title">Groupes :</div>';

	list_html += '<div id="machine_list_content"><!-- start machines_list_content -->';


	if (items == null) { items = _LIST.items; }
	for (i=0;i<items.length;i++) {

			display = 'display'
			if (items[i].displayed == false) {
				display = 'hidden'
			}

			machine_hostname = items[i].hostname;
			machine_mid = items[i].mid;
			machine_managed = items[i].managed;
			machine_ether = items[i].ether;
			machine_expiry = items[i].expiry;
			machine_selected = items[i].selected;
			machine_clicked = items[i].clicked;
			machine_status = "??";

			machine_nav = '<div class="reapply_skel_group" name="'+machine_hostname+'">';
			machine_nav += '	<img src="/images/16x16/reapply-skel.png" title="Reapply skel of group '+machine_hostname+'" alt="Reapply skel of group '+machine_hostname+'"/>';
			machine_nav += '</div>';
			machine_nav += '<div class="delete_group" name="'+machine_hostname+'">';
			machine_nav += '	<img src="/images/16x16/supprimer.png" title="Delete user '+machine_hostname+'" alt="Delete user '+machine_hostname+'"/>';
			machine_nav += '</div>';


			checked = '';
			selected = '';
			if (machine_selected == true) {

				//console.log("checked")

				checked = 'checked';
			}
			if (machine_clicked == true) {
					selected = 'item_selected';
			}

			//console.log("user " + user_login + ' displayed : TRUE');

			list_html += '<div class="machine_row '+ selected + '" id='+ machine_hostname +'>';
			list_html += '	<div class="machines_list_item groups_list_select" name='+machine_hostname+'>';
			list_html += '		<input id="checkbox_'+machine_hostname+'" type="checkbox" '+checked+'/>';
			list_html += '	</div>';
			list_html += '	<div class="group_content" name='+machine_hostname+'>';
			list_html += '		<div class="machines_list_item machines_list_status">';
			list_html += '			'+machine_status;
			list_html += '		</div>';
			list_html += '		<div class="machines_list_item machines_list_hostname">';
			list_html += '			'+machine_hostname;
			list_html += '		</div>';
			list_html += '		<div class="machines_list_item machines_list_mid">';
			list_html += '			'+machine_mid;
			list_html += '		</div>';
			//list_html += '		<div class="machines_list_item machines_list_ether">';
			//list_html += '			'+machine_ether;
			//list_html += '		</div>';
			list_html += '		<div class="machines_list_item machines_list_expiry">';
			list_html += '			'+machine_expiry;
			list_html += '		</div>';
			list_html += '		<div class="machines_list_item machines_list_managed">';
			list_html += '			'+machine_managed;
			list_html += '		</div>';
			list_html += '	</div>';
			list_html += '	<div class="machines_list_item machines_list_nav">';
			list_html += '		<div class="item_menu">'+machine_nav+'</div>';
			list_html += '	</div>';
			list_html += '</div>';


		}


	list_html += '</div><!-- end privs_list_content -->';
	//console.log("returning " + list_html);
	return list_html;
}

function init_events() {
	console.log("init events");
}
function init_load() {
	//console.log("init_sort_users_list");

}


function sort_items_list(groups_list, sort, item_sort) {

	
}


