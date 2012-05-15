/*
* Licorn WMI users javascript
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
*/

//global var
var hover_timeout;

function init_users_events(list_name, uid, login, identifier) {
	/* initialize user row events */
	me = $('#'+list_name+'_list').find('.row').filter("#"+uid+"");

	// hide the navigation
	me.find('.item_menu').hide();

	my_user_lock = me.find('.'+list_name+'_locked');

	// hover events
	my_user_lock.hover(function() {
		$(this).html(generate_locked_img('in', $(this).hasClass('is_locked')));
	}, function() {
		$(this).html(generate_locked_img('out', $(this).hasClass('is_locked')));
	});

	// click event
	my_user_lock.click(function() {
		login = me.find('.'+list_name+'_login').text();

		if ($(this).hasClass('is_locked')) {

			unlock_dialog = new dialog(gettext("Unlock confirmation"),
				strargs(gettext("Do you really want to unlock user account “%1”?"), [login]),
				true, function() {
					page_url = "/users/mod/" + $.URLEncode(uid) + "/unlock/";
					$.get(page_url);
				});
			unlock_dialog.show();

		} else {
			$.get('/users/message/lock/'+uid, function(lock_dialog_content) {
				lock_dialog = new dialog(gettext("Lock confirmation"), lock_dialog_content,
					true, function() {
						page_url = "/users/mod/" + $.URLEncode(uid) + "/lock/";
						$.get(page_url)
					});
				lock_dialog.show();
			});
		}
	});

	// delete click
	me.find('.users_delete').click(function() {

		delete_user_dialog_title = gettext("Removal confirmation");

		$.get('/users/message/delete/'+uid, function(delete_user_dialog_content) {
			delete_user_dialog = new dialog(delete_user_dialog_title, delete_user_dialog_content,
				true, function() {
					if ($("#delete_user_no_archive").attr('checked')) { no_archive = 'True'; }
					else { no_archive = ''; }

					page_url = "/users/delete/" + $.URLEncode(uid) + "/" + no_archive;
					clear_sub_content_with_id(uid)
					$.get(page_url)
				});
			delete_user_dialog.show();
		});

	});

	// skel click
	me.find('.users_reapply_skel').click(function() {

		reapply_skel_user_dialog_title = gettext("Skeleton reapplying confirmation");

		reapply_skel_user_dialog_content = strargs(gettext("Are you sure you want to reapply skeleton to user account “%1”?"), [uid]);

		$.get('/users/message/skel/'+uid, function(html) {
			reapply_skel_user_dialog_content += html;
			reapply_skel_user_dialog = new dialog(reapply_skel_user_dialog_title, reapply_skel_user_dialog_content,
				true, function() {
					skel = $("#id_skel_to_apply").attr('value').toString();
					page_url = "/users/mod/" + $.URLEncode(uid) + "/skel/"+ $.URLEncode(skel);

					$.get(page_url)
				});
			reapply_skel_user_dialog.show();
		});

	});

	child = me.find("."+list_name+"_content");

	// hover event of item_content
	child.hover(function() {
		// if sub_content not locked
		if (! is_sub_content_locked()) {
			// erase old timeout in case of fast actions
			clearTimeout(hover_timeout);
			// display user view
			hover_timeout = setTimeout(function(){
				$.ajax({
					url: "/users/view/"+uid,
					success: function(html) {
						reload_div('#sub_content', html)
					}
				});
			}, list_hover_timeout_value);
		}
	}, function() {
		// when we leave the row, erase the timer
		clearTimeout(hover_timeout);
	});

	// deal with click event on item_content
	child.click(function() {
		// if sub_content already locked by this users, unlock it
		if (is_sub_content_locked() && $('#sub_content').attr('value') == $(this).parent().attr('id')) {
			unlock_sub_content();
			unselect_row();
			reload_div('#sub_content', "")
		}

		else {
			// clear hover timeout to avoid hover event before click event
			clearTimeout(hover_timeout);

			lock_sub_content(uid)
			select_row(list_name, uid);

			// display the edit view
			$.ajax({
				url: "/users/edit/"+$(this).find('.'+list_name+'_'+ identifier).text(),
				success: function(html) {
					reload_div('#sub_content', html)
				}
			});
		}
	});


	// init nav on each rows
	me.hover(function() {
			if (! is_sub_content_locked()) {
				$(this).find(".item_menu").show();
			}
		},
		function() {
			if (! is_sub_content_locked()) {
				$(this).find(".item_menu").hide();
			}
		});

}
function generate_locked_img(hover, locked) {

	if (locked) {
		lock_title = gettext("Unlock user account");
		lock_class = "user_unlock_action";
		lock_img = "/media/images/24x24/locked.png";
		lock_alt = lock_title;

	} else {
		if (hover == 'in') {
			lock_title = gettext("Lock user account");
			lock_class = "locked_box user_lock_action";
			lock_img = '/media/images/24x24/locked_over.png';
			lock_alt = lock_title;

		} else {
			lock_title = gettext("Lock user account");
			lock_class = "locked_box user_lock_action";
			lock_img = '/media/images/24x24/locked_box.png';
			lock_alt = lock_title;
		}
	}

	return "<img src='" + lock_img + "' class='" + lock_class + "' alt='" + lock_alt + "' title='" + lock_title + "'/>"
}




