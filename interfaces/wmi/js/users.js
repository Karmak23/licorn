/*
* Licorn WMI users page javascript
*
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
* Licensed under the terms of the GNU GPL version 2
*/

//var _LIST = new List('users', 'login', "#users_list_content", '.user_content');

$(document).ready(function() {
	$("#users_list_content").html('<center><img style="margin-top:30px;" src="/images/progress/ajax-loader.gif"/></center>');

	page = '/users/get_main_content_JSON'

	_PAGE = new Page('users');

	$.getJSON(page, function(obj_content){
		//console.log('on y est');
		obj = obj_content.content
		//console.log(obj);
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

// User specific functions
// user menu
$("#add_user_menu").click(function() {
	if (DEBUG || DEBUG_USER) { console.log('> CLICK EVENT : on #add_uder_menu'); }
	page = '/users/new';
	// do not let the user add a priv from the wmi
	if (_PAGE.current_list.name != 'users') {
		alert(_("It is currently impossible to add systems user; please select the standard users list first, to add a standard user account."));
	}
	else {
		change_content_of_sub_content_main(page);
		// in the case a user was selected, unselect him
		$('.item_selected').removeClass('item_selected');
		$('.bkg_selected').removeClass('bkg_selected');
	}
	if (DEBUG || DEBUG_USER) { console.log('< CLICK EVENT : on #add_uder_menu'); }
});

function generate_select_mass_import(id) {

	data = ' <select id="'+id+'">';
	data += '	<option>1</option>';
	data += '	<option>2</option>';
	data += '	<option>3</option>';
	data += '	<option>4</option>';
	data += '</select> <br />';

	return data
}

$("#import_user_menu").click(function() {
	//TODO
	not_yet_dialog.show();
	/*
	if (DEBUG || DEBUG_USER) { console.log('> CLICK EVENT : on #import_user_menu'); }

	import_user_dialog_content = ' <div id="mass_import_content">'
	import_user_dialog_content += 'Please choose a CSV file to import users from :'
	import_user_dialog_content += '<input type="file" id="mass_import_file">'
	import_user_dialog_content += '<br /><br />'
	import_user_dialog_content += 'Please select column order :<br />'
	import_user_dialog_content += '<ul>'
	import_user_dialog_content += '<li>firstname : '+ generate_select_mass_import('mass_import_firstname') + '</li>';
	import_user_dialog_content += '<li>lastname : '+ generate_select_mass_import('mass_import_lastname') + '</li>';
	import_user_dialog_content += '<li>group : '+ generate_select_mass_import('mass_import_group') + '</li>';
	import_user_dialog_content += '<ul>'
	import_user_dialog_content += '<br />'
	import_user_dialog_content += '</div id="mass_import_content">'

	import_user_dialog = new dialog('Massive user import',import_user_dialog_content,
		true, mass_import_action);
	import_user_dialog.show();

	if (DEBUG || DEBUG_USER) { console.log('< CLICK EVENT : on #import_user_menu'); }*/
});

function mass_import_action() {
	//TODO
	file_path = $('#mass_import_file').val();
	group_col = $('#mass_import_group').val();
	firstname_col = $('#mass_import_firstname').val();
	lastname_col = $('#mass_import_lastname').val();
	link = "/users/massive_import/"+$.URLEncode(file_path)+"/"+firstname_col+"/"+lastname_col+"/"+group_col
	$("#users_list_content").html('<center><img style="margin-top:30px;" src="/images/progress/ajax-loader.gif"/></center>');
	apply(link, 'import');
}

// Dialog functions
function delete_dialog_action() {
	var users = []
	$.each(_PAGE.current_list.get_selected_items(), function(k, user) {
		users.push(user.login);
	});
	if (DEBUG || DEBUG_USER) { console.log('> delete_dialog_action : '+users.join(',')); }

	// check if 'no_archive' checkbox is checked
	//	the result will be interpretated in the core (python code):
	//	in python, empty strings are False, others strings are True
	if ($("#massive_delete_make_backup").attr('checked')) {
		make_backup = 'True';
	}
	else {
		make_backup = '';
	}

	page_url = "/users/massive_delete/" + $.URLEncode(users.join(',')) + "/True/" + make_backup;
	apply(page_url, 'delete');
	if (DEBUG || DEBUG_USER) { console.log('< delete_dialog_action'); }
}

function reapply_skel_dialog_action() {
	var users = []
	$.each(_PAGE.current_list.get_selected_items(), function(k, user) {
		users.push(user.login);
	});

	if (DEBUG || DEBUG_USER) { console.log('> reapply_skel_dialog_action : '+users.join(',')); }

	page_url = "/users/massive_skel/" + $.URLEncode(users.join(',')) + "/True"
	apply(page_url);
	if (DEBUG || DEBUG_USER) { console.log('< reapply_skel_dialog_action'); }
}

function lock_dialog_action() {
	if (DEBUG || DEBUG_USER) { console.log('> lock_dialog_action()'); }
	user_login = $('#locking_user').attr('login');
	//TODO
	delete_from_remotessh = "False";
	page_url = "/users/lock/" + $.URLEncode(user_login) + "/True/" + delete_from_remotessh;
	apply(page_url, 'instant_apply');
	if (DEBUG || DEBUG_USER) { console.log('< lock_dialog_action()'); }
}

function unlock_dialog_action() {
	if (DEBUG || DEBUG_USER) { console.log('> unlock_dialog_action()'); }
	user_login = $('#locking_user').attr('login');
	page_url = "/users/unlock/" + $.URLEncode(user_login);
	apply(page_url, 'instant_apply');
	if (DEBUG || DEBUG_USER) { console.log('< lock_dialog_action()'); }
}

function delete_user_dialog_action() {
	if (DEBUG || DEBUG_USER) { console.log('> delete_user_dialog_action()'); }
	user_login = $('#deleting_user').attr('login');
	$('#deleting_user').attr('id', '');
	// check if 'no_archive' checkbox is checked
	//	the result will be interpretated in the core (python code):
	//	in python, empty strings are False, others strings are True
	if ($("#delete_user_make_backup").attr('checked')) {
		make_backup = 'True';
	}
	else {
		make_backup = '';
	}
	page_url = "/users/delete/" + $.URLEncode(user_login) + "/True/"+make_backup;
	apply(page_url, 'delete');
	if (DEBUG || DEBUG_USER) { console.log('< delete_user_dialog_action()'); }
}

function reapply_skel_user_dialog_action() {
	if (DEBUG || DEBUG_USER) { console.log('> reapply_skel_user_dialog_action()'); }
	user_login = $('#reapplying_skel_user').attr('login');
	$('#reapplying_skel_user').attr('id', '');
	skel = $("#skel_to_apply").attr('value').toString();
	page_url = "/users/skel/" + $.URLEncode(user_login) + "/True/"+ $.URLEncode(skel);
	apply(page_url);
	if (DEBUG || DEBUG_USER) { console.log('< reapply_skel_user_dialog_action()'); }
}

// Necessary method for List object
function init_events_list_header(list) {
	//console.log('init users header specific events');

	// massive operations
	$('#'+list.name+'_massive_delete').click(function() {
		if (DEBUG || DEBUG_USER) { console.log('> CLICK EVENT : on massive delete'); }
		users_selected = _PAGE.current_list.get_selected_items();

		//console.log(users_selected);

		users_selected_html = '<ul>'
		$.each(users_selected, function(k, user) {
			users_selected_html += '<li>'+user.login+'</li>';
		});
		users_selected_html += '</ul>';
		if (DEBUG || DEBUG_USER) console.log('massive delete on ' + users_selected_html);

		delete_dialog_title = _("Please confirm massive removal");

		if (users_selected_html == '<ul></ul>') {
			delete_dialog_content = _("Please select at least one user account.");
			delete_dialog = new dialog(delete_dialog_title, delete_dialog_content);
		}
		else {
			delete_dialog_content = _("Are you sure you want to remove these account(s):");
			delete_dialog_content += users_selected_html;
			delete_dialog_content += "<input type='checkbox' id='massive_delete_make_backup'/> <label for='massive_delete_make_backup'>" + _("Definitely remove their home directories without archiving them") + "</label>";
			delete_dialog = new dialog(delete_dialog_title,delete_dialog_content,
				true, delete_dialog_action);
		}
		delete_dialog.show();
		if (DEBUG || DEBUG_USER) { console.log('< CLICK EVENT : on massive delete'); }
	});
	$('#'+list.name+'_massive_skel').click(function() {

				if (DEBUG || DEBUG_USER) { console.log('> CLICK EVENT : on massive delete'); }
		users_selected = _PAGE.current_list.get_selected_items();

		users_selected_html = '<ul>'
		$.each(users_selected, function(k, user) {
			users_selected_html += '<li>'+user.login+'</li>';
		});
		users_selected_html += '</ul>';

		if (DEBUG || DEBUG_USER) { console.log('> CLICK EVENT : on massive skel'); }
		if (DEBUG || DEBUG_USER) console.log('massive skel on ' + users_selected_html);

		skel_dialog_title = _("Massive skeleton reapplying");

		if (users_selected_html == '<ul></ul>') {
			skel_dialog_content =  _("Please select at least one user account.");
			skel_dialog = new dialog(skel_dialog_title,	skel_dialog_content);
		}
		else {
			skel_dialog_content = _("Are you sure you want to reapply their skeleton to these user account(s):");
			skel_dialog_content += users_selected_html;
			skel_dialog = new dialog(skel_dialog_title,	skel_dialog_content,
				true, reapply_skel_dialog_action);
		}
		skel_dialog.show();
		if (DEBUG || DEBUG_USER) { console.log('< CLICK EVENT : on massive skel'); }
	});

	$('#'+list.name+'_massive_export').click(function() {
		not_yet_dialog.show();
	});
}

function refresh_item_row(json_input) {
	if (DEBUG || DEBUG_USER) console.log("refresh_item_row ");

	_LIST = _PAGE.current_list;

	user_div = $("#"+_LIST.main_attr+"_"+$(json_input).attr(_LIST.main_attr));
	user = json_input

	
	_user = _LIST.get_item(user.login);
	_user.locked = user.locked;
	/*_user.gecos = user.gecos == '' ? "<span class='no_data'>(" + _("no GECOS") + ")</span>" : user.gecos;
	_user.skel = user.skel;
	*/

	user_locked_html = generate_user_locked_html(user);

	user_div.find('.user_locked').html(user_locked_html);
	user_div.find('.user_gecos').html(user.gecos == '' ? "<span class='no_data'>(" + _("no GECOS") + ")</span>" : user.gecos);
	
	//user.locked = "False";
}
function generate_user_locked_html(user) {
	if (user.locked == "True") {
		//console.log('user locked');
		lock_title = "TOTO";
		lock_class = "user_unlock_action";
		lock_img = "/images/24x24/locked.png";
		lock_alt = _("Unlock account ") + user.login + ".";
	}
	else {
		//console.log('user not locked');
		lock_title = "TATA";
		lock_class = "locked_box user_lock_action";
		lock_img = '/images/24x24/locked_box.png';
		lock_alt = _("Lock account ") + user.login + ".";
	}

	return "<img src='"+lock_img+"' class='"+lock_class+"' alt='"+lock_alt+"' title='"+lock_title+"' login='"+user.login+"'/>";
}
function init_events(me) {

	if (DEBUG || DEBUG_USER) { console.log('> init_events('+me.find('.user_locked').attr('login')+')'); }

	// hide the navigation
	me.find('.item_menu').hide();

	/*
	 * user lock events
	 */
	 my_user_lock = me.find('.user_locked');

	// hover events
	my_user_lock.hover(function() {
		user_login = $(this).attr('login');
		if (DEBUG || DEBUG_USER) console.log('> HOVER EVENT : on .user_locked of '+user_login);
		user = _PAGE.current_list.get_item(user_login);
		
		if (user.locked == "True") {
			//console.log('user locked');
			lock_title = "TOTO";
			lock_class = "user_unlock_action";
			lock_img = "/images/24x24/locked.png";
			lock_alt = _("Unlock account ") + user.login + ".";
		}
		else {
			//console.log('user not locked');
			lock_title = "TATA";
			lock_class = "locked_box user_lock_action";
			lock_img = '/images/24x24/locked_over.png';
			lock_alt = _("Lock account ") + user.login + ".";
		}

		$(this).html("<img src='"+lock_img+"' class='"+lock_class+"' alt='"+lock_alt+"' title='"+lock_title+"' login='"+user.login+"'/>");

	}, function() {

		if (user.locked == "True") {
			//console.log('user locked');
			lock_title = "TOTO";
			lock_class = "user_unlock_action";
			lock_img = "/images/24x24/locked.png";
			lock_alt = _("Unlock account ") + user.login + ".";
		}
		else {
			//console.log('user not locked');
			lock_title = "TATA";
			lock_class = "locked_box user_lock_action";
			lock_img = '/images/24x24/locked_box.png';
			lock_alt = _("Lock account ") + user.login + ".";
		}

		$(this).html("<img src='"+lock_img+"' class='"+lock_class+"' alt='"+lock_alt+"' title='"+lock_title+"' login='"+user.login+"'/>");

		if (DEBUG || DEBUG_USER) console.log('< HOVER EVENT : on .user_locked of '+user_login);

	});

	// click event
	my_user_lock.click(function() {
		user_login = $(this).attr('login');
		if (DEBUG || DEBUG_USER) console.log('> CLICK EVENT : on .user_locked of '+user_login);
		user = _PAGE.current_list.get_item(user_login);
		$('.user_locked').attr('id','');
		$(this).attr('id','locking_user');
		if (user.locked == "True") {
			if (DEBUG || DEBUG_USER) console.log(user_login + " is locked, present unlock dialog");
			// unlock
			unlock_dialog_title = _("Unlock confirmation");
			unlock_dialog_content = strargs(_("Are you sure you want to unlock user account %1?"), [user_login]);
			unlock_dialog = new dialog(unlock_dialog_title, unlock_dialog_content, true, unlock_dialog_action);
			unlock_dialog.show();
		}
		else {
			// lock
			if (DEBUG || DEBUG_USER) console.log(user_login + " is NOT locked, present lock dialog");
			lock_dialog_title = _("Lock confirmation");
			lock_dialog_content = strargs(_("Are you sure you want to lock user account %1?"), [user_login]);
			lock_dialog = new dialog(lock_dialog_title,	lock_dialog_content,
				true, lock_dialog_action, true, '/users/lock_message/'+user_login);
			lock_dialog.show();
		}
		if (DEBUG || DEBUG_USER) console.log('< CLICK EVENT : on .user_locked of '+user_login);
	});

	/*
	 * User nav
	 */
	 // delete click
	me.find('.delete_user').click(function() {
		user_to_delete = $(this).attr('login');
		$(this).attr('id', 'deleting_user');
		if (DEBUG || DEBUG_USER) console.log('> CLICK EVENT : on .delete_user of '+user_to_delete);
		delete_user_dialog_title = _("Removal confirmation");
		delete_user_dialog_content = strargs(_("Are you sure you want to remove user account %1?"), [user_to_delete]);
		delete_user_dialog = new dialog(delete_user_dialog_title,	delete_user_dialog_content,
			true, delete_user_dialog_action, true, '/users/delete_message/'+user_to_delete);
		delete_user_dialog.show();
		if (DEBUG || DEBUG_USER) console.log('< CLICK EVENT : on .delete_user of '+user_to_delete);
	});

	me.find('.reapply_skel_user').click(function() {
		user_to_reapply_skel = $(this).attr('login');
		$(this).attr('id', 'reapplying_skel_user');
		if (DEBUG || DEBUG_USER) console.log('> CLICK EVENT : on .reapply_skel_user of '+user_to_reapply_skel);
		reapply_skel_user_dialog_title = _("Skeleton reapplying confirmation");
		reapply_skel_user_dialog_content = strargs(_("Are you sure you want to reapply skeleton to user account %1?"), [user_to_reapply_skel]);
		reapply_skel_user_dialog = new dialog(reapply_skel_user_dialog_title, reapply_skel_user_dialog_content,
			true, reapply_skel_user_dialog_action, true, '/users/skel_message/'+user_to_reapply_skel);
		reapply_skel_user_dialog.show();
		if (DEBUG || DEBUG_USER) console.log('< CLICK EVENT : on .reapply_skel_user of '+user_to_reapply_skel);
	});

	if (DEBUG || DEBUG_USER) { console.log('< init_events()'); }
}

// Necessary methods for change_content function
function init_events_sub_content_new() {
	make_groups_interaction();
	//make_privs_interaction();

	// click save button
	$('#save_user_button').click( function() {

		// get user information
		new_user_profile = $('#new_user_profile').attr('value').toString();

		//console.log('>>>>>>'+new_user_profile);

		new_user_gecos = $('#new_user_gecos').val();
		new_user_password = $('#new_user_password').val();
		new_user_confirm_password = $('#new_user_confirm_password').val();
		new_user_login = $('#new_user_login').val();
		new_user_shell = $('#new_user_shell').attr('value').toString();
		new_user_groups = get_items_selected('.click_item');

		if (DEBUG || DEBUG_USER) { console.log('> adding user(login='+new_user_login+',gecos='+new_user_gecos+',password='+new_user_password+',confirm_pwd='+new_user_confirm_password+',profile='+new_user_profile+',shell='+new_user_shell+',group='+new_user_groups+')'); }
		if (DEBUG || DEBUG_USER) console.log("new_user_groups = "+new_user_groups);
		if (DEBUG || DEBUG_USER) console.log("new_user_groups = "+$.URLEncode(new_user_groups));
		if (DEBUG || DEBUG_USER) console.log("new_user_shell = "+$.URLEncode(new_user_shell));
		if (DEBUG || DEBUG_USER) console.log("new_user_login = "+$.URLEncode(new_user_login));
		if (DEBUG || DEBUG_USER) console.log("new_user_gecos = "+new_user_gecos);
		if (DEBUG || DEBUG_USER) console.log("new_user_gecos = "+$.URLEncode(new_user_gecos));
		page='/users/create/'+new_user_password+'/'+new_user_confirm_password+'/'+$.URLEncode(new_user_shell)+'/'+new_user_profile+'/'+$.URLEncode(new_user_login)+'/'+$.URLEncode(new_user_gecos)+'/'+$.URLEncode(new_user_groups);

		//console.log('page=' + page);

		apply(page, 'create')
	});

	// click cancel button
	$('#cancel_button').click(function() {
		change_content_of_sub_content_main(null);
	});
}

function init_events_on_subcontent_change() {
	make_groups_interaction();
	//make_privs_interaction();
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
		if (nb_items_in_list > 15) { nb_items_in_list = 15; }
		if (nb_items_in_list < 2) { nb_items_in_list = 2; }
		nb_items[cpt] = nb_items_in_list;
		nb_items_total += nb_items_in_list;
		cpt += 1;
	});

	$.each(nb_items, function(k, v) {
		percentage[k] = v / nb_items_total;
	});

	height = $('#sub_content_main').height() - (nb_ligne * $('.sub_content_line').height()) - $('#sub_content_header').height() - 15;
	//height = height_temp / nb_list;

	min_height = 40;
	cpt = 0;
	$('.sub_content_list').each(function() {
		_height = height*percentage[cpt]
		//~ if (_height < min_height) {
			//~ _height = min_height;
			//~
		//~ }
		$(this).height(_height);
		cpt += 1;
	});


}

function make_groups_interaction() {
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

	//console.log("make groups interaction");

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
			$(this).removeClass('cat_no_membership cat_guest cat_member cat_resp');
			$(this).addClass('cat_' + current_state);

			//console.log('current_state = ' + current_state);
			//console.log('current_state2 = ' + this.width);

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
		//alert(get_next_state(current_state));

		//change the name of the hidden input
		$(this).find('.item_hidden_input').attr('name',s[next_state])
		$(this).removeClass('cat_no_membership cat_guest cat_member cat_resp');
		$(this).addClass('cat_' + s[next_state]);

		$(this).find('.item_relation').html('<img src="/images/24x24/' + s[next_state] + '.png"/>');
		//init_list();

		//console.log('current_state = ' + states[next_state]);
	});
}

function generate_item_row(user) {
	if (DEBUG || DEBUG_USER) { console.log('generate_item_row('+user.login+')'); }
	user_html = '';

	user_profile = user.profile == '' ? "System" : user.profile;
	user_gecos = user.gecos == '' ? "<span class='no_data'>(" + _("no GECOS") + ")</span>" : user.gecos;
	if (user.is_system == 'True') {
		content_class = 'users_system_content';
	}
	else {
		content_class = 'users_content';
	}

	user_locked_html = generate_user_locked_html(user);
	console.log(user_locked_html);

	user_nav = '<div class="reapply_skel_user" login="'+user.login+'">';
	user_nav += '	<img src="/images/16x16/reapply-skel.png" title="'+strargs(_("Reapply skel of user %1"), [user.login])+'" alt="'+strargs(_("Reapply skel of user %1"), [user.login])+'"/>';
	user_nav += '</div>';
	user_nav += '<div class="delete_user" login="'+user.login+'">';
	user_nav += '	<img src="/images/16x16/supprimer.png" title="'+strargs(_("Delete user %1"), [user.login])+'" alt="'+strargs(_("Delete user %1"), [user.login])+'"/></a>';
	user_nav += '</div>';


	user_html += '<span class="users_row" id="login_' + user.login + '">';
	user_html += '	<span class="user_select" login="' + user.login + '">';
	user_html += '		<input type="checkbox" name="selected" class="user_checkbox" id="checkbox_' + user.login + '">';
	user_html += '	</span>';
	user_html += '	<span class="user_locked odd_even_typed " login="'+user.login+'"> ' + user_locked_html + ' </span>';
	user_html += '	<span title="'+strargs(_("Click to edit user %1"), [user.login])+'" class="'+content_class+'" login="' + user.login + '">';
	user_html += '		<span class="user_login odd_even_typed">' + user.login + '</span>';
	user_html += '		<span class="user_gecos odd_even_typed">' + user_gecos + '</span>';
	user_html += '		<span class="user_uid odd_even_typed">' + user.uidNumber + '</span>';
	user_html += '		<span class="user_profile odd_even_typed">';
	user_html += '			<span class="user_profile_content">' + user_profile + '</span>';
	user_html += '		</span>';
	user_html += '	</span>';
	user_html += '	<span class="user_nav odd_even_typed">';
	user_html += '		<span class="item_menu">' + user_nav + '</span>';
	user_html += '	</span>';
	user_html += '</span>';

	return user_html;
}
