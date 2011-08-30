/*
* Licorn WMI groups page javascript
*
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
* Licensed under the terms of the GNU GPL version 2
*/

function template_main_content_list(content_obj) {

}


$(document).ready(function() {

	// global vars :
	//console.log("LIST = "+ _LIST);

	//get the object representing the main_content
	/*obj_content = {
	 *  "lists" : [
	 * 		{ "name" : "groups",
	 * 			"title" : "Groupes",
	 * 		},
	 * 		{ "name" : "privs",
	 * 			"title" : "Privilèges",
	 * 		} ],
	 * 	"items" : [ groups_list ],
	 * 	"choice_item" : "is_priv"
	 * }
	 * */

	page = '/groups/get_main_content_JSON'

	_PAGE = new Page('groups');

	$.getJSON(page, function(obj_content){
		obj = obj_content.content
		$("#main_content").html("<!-- starting lists -->");
		$.each(obj.lists, function (k, list_obj) {
			var handler = setTimeout(function(){
				list = new Licorn_List(list_obj, k);
				$("#main_content").append(list.generate_html());
				list.initialize_events(list);
				list.sort_items_list('asc', list_obj.main_attr);
				_PAGE.lists.push(list);
				_PAGE.initialize_list(k);
				if (k == 0){
					// on load, we are always on the first list.
					_PAGE.current_list = list;
				}
			}, k * 250);
		});

		$("#main_content").append("<!-- end lists -->");
	});

	not_yet_dialog = new dialog(_("Not yet developped"), _("Not yet developped"));
});

// group specific functions
// group menu
$("#add_group_menu").click(function() {
	if (DEBUG || DEBUG_GROUP) { console.log('> CLICK EVENT : on #add_group_menu'); }
	page = '/groups/new';

	// do not let the user add a priv from the wmi
	if (_PAGE.current_list.name != 'groups') {
		alert(_("It is currently impossible to add systems group; please select the standard groups list first, to add a standard group account."));
	}
	else {
		change_content_of_sub_content_main(page);
		// in the case a group was selected, unselect him
		$('.item_selected').removeClass('item_selected');
		$('.bkg_selected').removeClass('bkg_selected');
	}
	if (DEBUG || DEBUG_GROUP) { console.log('< CLICK EVENT : on #add_group_menu'); }
});
$("#import_group_menu").click(function() {
	if (DEBUG || DEBUG_GROUP) { console.log('> CLICK EVENT : on #import_group_menu'); }
	not_yet_dialog.show();
	if (DEBUG || DEBUG_GROUP) { console.log('< CLICK EVENT : on #import_group_menu'); }
});


// Necessary methods for change_content function
function init_events_sub_content_new() {
	make_users_interaction();

	// click save button
	$('#save_group_button').click( function() {
		// get group information
		new_group_name = $('#new_group_name').attr('value').toString();
		new_group_desc = $('#new_group_desc').attr('value').toString();
		new_group_skel = $('#new_group_skel').attr('value').toString();
		new_group_perm = $('#new_group_perm').attr('checked').toString();

		if (DEBUG || DEBUG_GROUP) { console.log('> adding group(name='+new_group_name+',desc='+new_group_desc+',skel='+new_group_skel+',perm='+new_group_perm); }
		page='/groups/create/'+$.URLEncode(new_group_name)+'/'+$.URLEncode(new_group_desc)+'/'+$.URLEncode(new_group_skel)+'/'+new_group_perm;
		apply(page, 'create')

	});

	// click cancel button
	$('#cancel_button').click(function() {
		change_content_of_sub_content_main(null);
	});

}


function init_events_list_header(list) {
	// massive events
	$('#'+list.name+'_massive_delete').click(function() {
		if (DEBUG || DEBUG_GROUP) { console.log('> CLICK EVENT : on massive delete'); }
		groups_selected = _PAGE.current_list.get_selected_items();

		groups_selected_html = '<ul>'
		$.each(groups_selected, function(k, group) {
			groups_selected_html += '<li>'+group.name+'</li>';
		});
		groups_selected_html += '</ul>';
		if (DEBUG || DEBUG_GROUP) console.log('massive delete on ' + groups_selected_html);

		delete_dialog_title = _("Deletion confirmation");;

		if (groups_selected_html == '<ul></ul>') {
			delete_dialog_content = _("Please select at least one group to delete");
			delete_dialog = new dialog(delete_dialog_title, delete_dialog_content);
		}
		else {
			delete_dialog_content = _("Do you really want to remove groups:");
			delete_dialog_content += groups_selected_html;
			delete_dialog_content += "<input type='checkbox' id='massive_delete_make_backup'/> <label for='massive_delete_make_backup'>"+_("Disable backup")+"</label>";
			delete_dialog = new dialog(delete_dialog_title,delete_dialog_content,
				true, delete_dialog_action);
		}
		delete_dialog.show();
		if (DEBUG || DEBUG_GROUP) { console.log('< CLICK EVENT : on massive delete'); }
	});
	$('#'+list.name+'_massive_skel').click(function() {

		if (DEBUG || DEBUG_GROUP) { console.log('> CLICK EVENT : on massive delete'); }
		groups_selected = _PAGE.current_list.get_selected_items();

		groups_selected_html = '<ul>'
		$.each(groups_selected, function(k, group) {
			groups_selected_html += '<li>'+group.name+'</li>';
		});
		groups_selected_html += '</ul>';

		if (DEBUG || DEBUG_GROUP) { console.log('> CLICK EVENT : on massive skel'); }
		if (DEBUG || DEBUG_GROUP) console.log('massive skel on ' + groups_selected_html);

		skel_dialog_title = _("Reapply skel confirmation");;

		if (groups_selected_html == '<ul></ul>') {
			skel_dialog_content = _("Please select at least one group to reapply skel");
			skel_dialog = new dialog(skel_dialog_title,	skel_dialog_content);
		}
		else {
			skel_dialog_content = _("Do you really want to reappl skel of groups:");
			skel_dialog_content += groups_selected_html;
			skel_dialog = new dialog(skel_dialog_title,	skel_dialog_content,
				true, reapply_skel_dialog_action);
		}
		skel_dialog.show();
		if (DEBUG || DEBUG_GROUP) { console.log('< CLICK EVENT : on massive skel'); }
	});

	$('#'+list.name+'_massive_export').click(function() {
		not_yet_dialog.show();
	});

}


function perm_dialog_action() {
	if (DEBUG || DEBUG_GROUP) { console.log('> perm_dialog_action()'); }
	group_name = $('#making_group_permissive').attr('name');
	make_permissive = "true"
	link = "/groups/edit_permissive/" + $.URLEncode(group_name) + "/"+make_permissive;

	apply(link, 'instant_apply');
	if (DEBUG || DEBUG_GROUP) { console.log('< perm_dialog_action()'); }
}
function unperm_dialog_action() {
	if (DEBUG || DEBUG_GROUP) { console.log('> unperm_dialog_action()'); }
	group_name = $('#making_group_permissive').attr('name');
	make_permissive = "false"

	link = "/groups/edit_permissive/" + $.URLEncode(group_name) + "/"+make_permissive;
	apply(link, 'instant_apply');
	if (DEBUG || DEBUG_GROUP) { console.log('< unperm_dialog_action()'); }
}
function delete_dialog_action() {
	var groups = []
	$.each(_PAGE.current_list.get_selected_items(), function(k, group) {
		groups.push(group.name);
	});
	if (DEBUG || DEBUG_GROUP) { console.log('> delete_dialog_action : '+groups.join(',')); }
	// check if 'no_archive' checkbox is checked
	//	the result will be interpretated in the core (python code):
	//	in python, empty strings are False, others strings are True
	if ($("#massive_delete_make_backup").attr('checked')) {
		make_backup = 'True';
	}
	else {
		make_backup = '';
	}
	page_url = "/groups/massive_delete/" + $.URLEncode(groups.join(',')) + "/True/" + make_backup;
	apply(page_url, 'delete');
	if (DEBUG || DEBUG_GROUP) { console.log('< delete_dialog_action'); }
}
function reapply_skel_dialog_action() {
	var groups = []
	$.each(_PAGE.current_list.get_selected_items(), function(k, group) {
		groups.push(group.name);
	});

	if (DEBUG || DEBUG_GROUP) { console.log('> reapply_skel_dialog_action : '+groups.join(',')); }

	page_url = "/groups/massive_skel/" + $.URLEncode(groups.join(',')) + "/True"
	apply(page_url);
	if (DEBUG || DEBUG_GROUP) { console.log('< reapply_skel_dialog_action'); }
}




function init_events(me) {
	if (DEBUG || DEBUG_GROUP) { console.log("> Groups.init_events()"); }

	// hide the navigation
	me.find('.item_menu').hide();
	/*
	 * groups perm events
	 */

	  my_group_perm = me.find('.groups_list_permissive');

	// hover events
	my_group_perm.hover(function() {
		group_name = $(this).attr('name');
		if (DEBUG || DEBUG_GROUP) console.log('> HOVER EVENT : on .groups_list_permissive of '+group_name);
		group = _PAGE.current_list.get_item(group_name);

		if (group.permissive == "True") {
			perm_title = strargs(_("Make group %1 not permissive.", [group_name]));
			perm_class = "group_unperm_action";
			perm_img = "/images/24x24/locked.png";
			perm_alt = strargs(_("Make group %1 not permissive.", [group_name]));
		}
		else {
			perm_title = strargs(_("Make group %1 permissive.", [group_name]));
			perm_class = "perm_box group_perm_action";
			perm_img = '/images/24x24/locked_over.png';
			perm_alt = strargs(_("Make group %1 permissive.", [group_name]));
		}

		group_perm_html = "<img src='"+perm_img+"' class='"+perm_class+"' alt='"+perm_alt+"' title='"+perm_title+"'/>";
		$(this).html(group_perm_html);

	}, function() {
		if (group.permissive == 'True') {
			perm_title = strargs(_("Make group %1 not permissive.", [group_name]));
			perm_class = "group_unperm_action";
			perm_img = "/images/24x24/locked.png";
			prem_alt = strargs(_("Make group %1 not permissive.", [group_name]));
		}
		else {
			perm_title = strargs(_("Make group %1 permissive.", [group_name]));
			perm_class = "perm_box group_perm_action";
			perm_img = '/images/24x24/locked_box.png';
			perm_alt = strargs(_("Make group %1 permissive.", [group_name]));
		}
		group_perm_html = "<img src='"+perm_img+"' class='"+perm_class+"' alt='"+perm_alt+"' title='"+perm_title+"'/>";
		$(this).html(group_perm_html);
		if (DEBUG || DEBUG_GROUP) console.log('< HOVER EVENT : on .groups_list_permissive of '+group_name);

	});

	// click event
	my_group_perm.click(function() {
		group_name = $(this).attr('name');
		if (DEBUG || DEBUG_GROUP) console.log('> CLICK EVENT : on .groups_list_permissive of '+group_name);
		group = _PAGE.current_list.get_item(group_name);
		$('.groups_list_permissive').attr('id','');
		$(this).attr('id','making_group_permissive');
		if (group.permissive == "True") {
			if (DEBUG || DEBUG_GROUP) console.log(group_name + " is permissive, present NOTpermissive dialog");
			// unlock
			unperm_dialog_title = _("Permissiveness confirmation");
			unperm_dialog_content = strargs(_("Do you really want to make the group %1 not permissive?"), [group_name])
			unperm_dialog = new dialog(unperm_dialog_title, unperm_dialog_content, true, unperm_dialog_action);
			unperm_dialog.show();
		}
		else {
			// lock
			if (DEBUG || DEBUG_GROUP) console.log(group_name + " is NOT permissive, present permissive dialog");
			perm_dialog_title = _("Permissiveness confirmation");
			perm_dialog_content = strargs(_("Do you really want to make the group %1 permissive?"), [group_name])
			perm_dialog = new dialog(perm_dialog_title, perm_dialog_content, true, perm_dialog_action);
			perm_dialog.show();
		}
		if (DEBUG || DEBUG_GROUP) console.log('< CLICK EVENT : on .groups_list_permissive of '+group_name);
	});

	// delete click
	me.find('.delete_group').click(function() {
			group_to_delete = $(this).attr('name');
			$(this).attr('id', 'deleting_group');
			if (DEBUG || DEBUG_GROUP) console.log('> CLICK EVENT : on .delete_group for group '+group_to_delete);
			delete_group_dialog_title = _("Removal confirmation");
			delete_group_dialog_content = "";
			delete_group_dialog = new dialog(delete_group_dialog_title,	delete_group_dialog_content,
				true, delete_group_dialog_action, true, '/groups/delete_message/'+group_to_delete);
			delete_group_dialog.show();
			if (DEBUG || DEBUG_GROUP) console.log('< CLICK EVENT : on .delete_user');
		});
	me.find('.reapply_skel_group').click(function() {
		group_to_reapply_skel = $(this).attr('name');
		$(this).attr('id', 'reapplying_skel_group');
		if (DEBUG || DEBUG_GROUP) console.log('> CLICK EVENT : on .reapply_skel_group of '+group_to_reapply_skel);
		reapply_skel_group_dialog_title = _("Reapply skel");
		reapply_skel_group_dialog_content = "";
		reapply_skel_group_dialog = new dialog(reapply_skel_group_dialog_title, reapply_skel_group_dialog_content,
			true, reapply_skel_group_dialog_action, true, '/groups/skel_message/'+group_to_reapply_skel);
		reapply_skel_group_dialog.show();
		if (DEBUG || DEBUG_GROUP) console.log('< CLICK EVENT : on .reapply_skel_group of '+group_to_reapply_skel);
	});
	function delete_group_dialog_action() {
		if (DEBUG || DEBUG_GROUP) { console.log('> delete_group_dialog_action()'); }
		group_name = $('#deleting_group').attr('name');
		$('#deleting_group').attr('id', '');
		// check if 'no_archive' checkbox is checked
		//	the result will be interpretated in the core (python code):
		//	in python, empty strings are False, others strings are True
		if ($("#delete_group_make_backup").attr('checked')) {
			make_backup = 'True';
		}
		else {
			make_backup = '';
		}
		link_page = "/groups/delete/" + $.URLEncode(group_name) + "/True/"+make_backup;
		apply(link_page, 'delete');
		if (DEBUG || DEBUG_GROUP) { console.log('< delete_group_dialog_action()'); }
	}
	function reapply_skel_group_dialog_action() {
		if (DEBUG || DEBUG_GROUP) { console.log('> reapply_skel_group_dialog_action()'); }
		group_name = $('#reapplying_skel_group').attr('name');
		$('#reapplying_skel_group').attr('id', '');
		skel = $("#skel_to_apply").attr('value').toString();
		link_page = "/groups/skel/" + $.URLEncode(group_name) + "/True/"+ $.URLEncode(skel);

		apply(link_page, 'instant_apply');
		if (DEBUG || DEBUG_GROUP) { console.log('< reapply_skel_group_dialog_action()'); }
	}

}



function init_events_on_subcontent_change() {
	make_users_interaction();
	init_instant_apply();

	// init height of list
	nb_ligne = $('.sub_content_line').length - 1;
	nb_list = $('.sub_content_list').length;

	nb_items_total = 0;
	percentage = [];
	nb_items = [];
	cpt = 0;
	$('.sub_content_list').each(function() {
		nb_items_in_list = $(this).find('.click_item').length;
		if (nb_items_in_list > 50) { nb_items_in_list = 50; }
		if (nb_items_in_list < 10) { nb_items_in_list = 10; }
		nb_items[cpt] = nb_items_in_list;
		nb_items_total += nb_items_in_list;
		cpt += 1;
	});

	$.each(nb_items, function(k, v) {
		percentage[k] = v / nb_items_total;
	});

	height = $('#sub_content_main').height() - (nb_ligne * $('.sub_content_line').height()) - $('#sub_content_header').height() - 30;

	min_height = 40;
	cpt = 0;
	$('.sub_content_list').each(function() {
		_height = height*percentage[cpt]

		$(this).height(_height);
		cpt += 1;
	});
}

function make_users_interaction() {
	var nb_states = 4;
	var nb_states_priv = 2;
	var states = new Array();
	var states_priv = new Array();

	states[0] = "no_membership";
	states[1] = "guest";
	states[2] = "member";
	states[3] = "resp";
	states_priv[0] = "no_membership";
	states_priv[1] = "member";

	function get_next_state(state_name, is_priv) {
		if (is_priv) {
			for(i=0 ; i<states_priv.length ; i++) {
				if (states_priv[i] == state_name) {
					return i+1;
				}
			}
		}
		else {
			for(i=0 ; i<states.length ; i++) {
				if (states[i] == state_name) {
					return i+1;
				}
			}
		}
	}
	function get_current_state(state_name) {
		for(i=0 ; i<states.length ; i++) {
			if (states[i] == state_name) {
				return i;
			}
		}
	}

	function init_list() {
		// init the list

		width = $("#sub_content_main").width();
		current_width = 0;
		$('.click_item').each(function() {
			current_state = $(this).find('.item_hidden_input').attr('name');
			cs_id = get_current_state(current_state);
			$(this).find('.item_relation').html('<img src="/images/24x24/' + states[cs_id] + '.png"/>');
		});
	}

	init_list();

	// the click
	$('.click_item').click(function() {
		is_priv = false;

		if ($(this).hasClass('priv_item')) {
			is_priv = true;
		}

		current_state = $(this).find('.item_hidden_input').attr('name');
		if (is_priv) {
			nb = nb_states_priv;
			s = states_priv;
		}
		else {
			nb = nb_states;
			s = states;
		}
		if (get_next_state(current_state, is_priv) >= nb) {
			next_state = 0;
		}
		else {
			next_state = get_next_state(current_state, is_priv);
		}
		//change the name of the hidden input
		$(this).find('.item_hidden_input').attr('name',s[next_state])
		$(this).removeClass('cat_no_membership cat_guest cat_member cat_resp');
		$(this).addClass('cat_' + s[next_state]);

		$(this).find('.item_relation').html('<img src="/images/24x24/' + s[next_state] + '.png"/>');

	});
}




function refresh_item_row(json_input) {
	if (DEBUG || DEBUG_GROUP) console.log("GROUP.refresh_item_row "+json_input.name);

	// TODO : we need to be sure that the edit view disapear when we change the current list
	_LIST = _PAGE.current_list;

	group_div = $("#name_"+json_input.name);
	group = json_input;

	if (group.permissive == "True") {
		perm_title = "Make group "+group.name+" NOT permissive.";
		perm_class = "group_unperm_action";
		perm_img = "/images/24x24/locked.png";
		perm_alt = "Make group "+group.name+" NOT permissive.";
	}
	else {
		perm_title = "Make group "+group.name+" permissive.";
		perm_class = "perm_box group_perm_action";
		perm_img = '/images/24x24/locked_box.png';
		perm_alt = "Make group "+group.name+" permissive.";
	}

	group_perm_html = "<img src='"+perm_img+"' class='"+perm_class+"' alt='"+perm_alt+"' title='"+perm_title+"'/>";

	group_desc_html = group.description == '' ? '<span class="no_data">(' + _("no description") + ')</span>' : group.description;
	group_is_priv_html = group.description;
	group_skel_html = group.groupSkel;

	group_div.find('.'+_LIST.name+'_list_permissive').html(group_perm_html);
	group_div.find('.'+_LIST.name+'_list_desc').html(group_desc_html);
	group_div.find('.'+_LIST.name+'_list_skel').html(group_skel_html);
	group_div.find('.'+_LIST.name+'_list_is_priv').html(group_is_priv_html);

}
function generate_item_row(group) {

			group_name = group.name;
			group_gid = group.gidNumber;
			group_desc = group.description == '' ? '<span class="no_data">(' + _("no description") + ')</span>' : group.description;
			group_skel = group.groupSkel;
			group_permissive = group.permissive;
			group_priv = group.is_priv;

			if (group_priv == 'True' || group.is_system == 'True') {
				list_name = 'privs';
			}
			else {
				list_name = 'groups';
			}

			group_nav = '<div class="reapply_skel_group" name="'+group_name+'">';
			group_nav += '	<img src="/images/16x16/reapply-skel.png" title="'+strargs(_("Reapply skel of group %1"), [group_name])+' alt="'+strargs(_("Reapply skel of group %1"), [group_name])+'"/>';
			group_nav += '</div>';
			group_nav += '<div class="delete_group" name="'+group_name+'">';
			group_nav += '	<img src="/images/16x16/supprimer.png" title="'+strargs(_("Delete group %1"), [group_name])+'" alt="'+strargs(_("Delete group %1"), [group_name])+'"/>';
			group_nav += '</div>';


			//console.log("group.permissive = "+group_permissive);
			if (group_permissive == "True") {
				perm_title = "Make group "+group_name+" NOT permissive.";
				perm_class = "group_unperm_action";
				perm_img = "/images/24x24/locked.png";
				perm_alt = "Make group "+group_name+" NOT permissive.";
			}
			else {
				perm_title = "Make group "+group_name+" permissive.";
				perm_class = "perm_box group_perm_action";
				perm_img = '/images/24x24/locked_box.png';
				perm_alt = "Make group "+group_name+" permissive.";
			}

			group_perm_html = "<img src='"+perm_img+"' class='"+perm_class+"' alt='"+perm_alt+"' title='"+perm_title+"'/>";


			group_priv_html = group.is_priv;


			list_html = '<div class="groups_row" id="name_'+ group_name +'">';
			list_html += '	<div class="groups_list_select" name='+group_name+'>';
			list_html += '		<input id="checkbox_'+group_name+'" type="checkbox" />';
			list_html += '	</div>';

			if (group.is_priv != 'True' && group.is_system != 'True') {
				list_html += '	<div class="'+list_name+'_list_permissive '+list_name+'_list_item odd_even_typed" name="'+group_name+'">';
				list_html += '		'+group_perm_html;
				list_html += '	</div>';
			}

			if (group.is_priv == 'True' || group.is_system == 'True') {
				list_html += '	<div class="'+list_name+'_list_priv '+list_name+'_list_item odd_even_typed" name="'+group_name+'">';
				list_html += '		'+group_priv_html;
				list_html += '	</div>';
			}

			list_html += '	<div class="'+list_name+'_content" name='+group_name+'>';
			list_html += '		<div class="'+list_name+'_list_item '+list_name+'_list_name odd_even_typed">';
			list_html += '			'+group_name;
			list_html += '		</div>';
			list_html += '		<div class="'+list_name+'_list_item '+list_name+'_list_desc odd_even_typed">';
			list_html += '			'+group_desc;
			list_html += '		</div>';
			list_html += '		<div class="'+list_name+'_list_item '+list_name+'_list_gid odd_even_typed">';
			list_html += '			'+group_gid;
			list_html += '		</div>';
			if (group.is_priv != 'True' && group.is_system != 'True') {
				list_html += '		<div class="'+list_name+'_list_item '+list_name+'_list_skel odd_even_typed">';
				list_html += '			'+group_skel;
				list_html += '		</div>';
			}
			list_html += '	</div>';
			list_html += '	<div class="'+list_name+'_list_item groups_list_nav odd_even_typed">';
			list_html += '		<div class="item_menu">'+group_nav+'</div>';
			list_html += '	</div>';
			list_html += '</div>';

	return list_html;
}
