/*
* Licorn WMI users javascript
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
*/

//global var
var hover_timeout;

function init_machines_events(list_name, mid, hostname, identifier) {
	// id for machine is IP address => we need to replace '.' by '_' 
	me = $('#'+list_name+'_list').find('.row').filter("#"+mid.replace(/\./gi,"_"));
	
	// hide the navigation
	me.find('.item_menu').hide();
	
	
}
function generate_locked_img(hover, locked) {
	if (locked == 'true' || locked == 'True') {
		lock_title = strargs(gettext("Unlock user %1"), [login]);
		lock_class = "user_unlock_action";
		lock_img = "/media/images/24x24/locked.png";
		lock_alt = gettext("Unlock account ") +login + ".";
	}
	else {
		if (hover == 'in') {
			lock_title = strargs(gettext("Lock user %1"), [login]);
			lock_class = "locked_box user_lock_action";
			lock_img = '/media/images/24x24/locked_over.png';
			lock_alt = gettext("Lock account ") + login + ".";
		}
		else {
			lock_title = gettext("Lock account ") + login + ".";
			lock_class = "locked_box user_lock_action";
			lock_img = '/media/images/24x24/locked_box.png';
			lock_alt = gettext("Lock account ") + login + ".";
		}
	}
	
	return "<img src='"+lock_img+"' class='"+lock_class+"' alt='"+lock_alt+"' title='"+lock_title+"'/>"
}
