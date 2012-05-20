/*
* Licorn WMI groups page javascript
*
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
*/
var hover_timeout;
function init_groups_events(list_name, gid, name, identifier) {
	/* initialize user row events */
	me = $('#'+list_name+'_list').find('.row').filter("#"+gid+"");

	// hide the navigation
	me.find('.item_menu').hide();

	group_perm = me.find('.'+list_name+'_permissive');
	// hover events
	group_perm.hover(function() {
		$(this).html(generate_permissive_img('in', $(this).hasClass('is_permissive'), name));
	}, function() {
		$(this).html(generate_permissive_img('out', $(this).hasClass('is_permissive'), name));
	});

	// click event
	group_perm.click(function() {

		if ($(this).hasClass('is_permissive')) {
			perm_title = strargs(gettext("Make group “%1” not permissive"), [name]);
			perm_content = strargs(gettext("Are you sure you want to make group “%1” not permissive?"), [name]);
			perm = ""; //python bool : empty strings are false

		} else {
			perm_title = strargs(gettext("Make group “%1” permissive?"), [name]);
			perm_content = gettext('This will permit wider access to files and folders in the group shared directory, allowing any <strong>member of the group</strong> to modify or delete any document in the shared directory (whichever the current owner). <br /><br /> <strong>If the group members are already accustomed to work together on the same documents, making the group permissive is the right choice.</strong> You would usually use this feature on small working groups of people only, as it makes hard to track “who modified what”. <br /><br /> NOTE: The operation may be lengthy because the system will change permissions of all current files (duration is therefore depending on the volume of data, about 10 second for 1Gb).');
			perm = "True";
		}

		perm_dialog = new dialog(perm_title, perm_content, true, function() {
			page_url = "/groups/mod/" + gid + "/permissive/" + perm;
			$.get(page_url);
		});
		perm_dialog.show();
	});

	// delete click
	me.find('.groups_delete').click(function() {
		delete_title = gettext("Removal confirmation");

		$.get('/groups/message/delete/'+gid, function(html) {
			delete_content = html;
			delete_dialog = new dialog(delete_title, delete_content,
				true, function() {
					if ($("#delete_group_no_archive").attr('checked')) { no_archive = 'True'; }
					else { no_archive = ''; }

					page_url = "/groups/delete/" + gid + "/" + no_archive;
					clear_sub_content_with_id(gid)
					$.get(page_url)
				});
			delete_dialog.show();
		});

	});

	// skel click
	me.find('.groups_reapply_skel').click(function() {
		$.get('/groups/message/skel/'+gid, function(delete_content) {
			skel_dialog = new dialog(
				gettext("Skeleton reapplying confirmation"), delete_content,
				true, function() {
					page_url = "/groups/mod/" + gid + "/apply_skel/"

					$.get(page_url)
				});
			skel_dialog.show();
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
					url: "/groups/view/"+gid,
					success: function(html) {
						$('#sub_content').attr('value', gid);
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

			lock_sub_content(gid);
			select_row(list_name, gid);

			// display the edit view
			$.ajax({
				url: "/groups/edit/"+$(this).find('.'+list_name+'_'+ identifier).text(),
				success: function(html) {
					reload_div('#sub_content', html)
				}
			});
		}
	});


	// init nav on each rows
	me.hover(function() {
			if (!is_sub_content_locked()) {
				$(this).find(".item_menu").show();
			}
		}, function() {
			if (!is_sub_content_locked()) {
				$(this).find(".item_menu").hide();
			}
		}
	);
}

function generate_permissive_img(hover, perm, group_name) {
	// console.log('generate_permissive_img('+hover+','+perm+','+group_name)
	if (typeof(perm) == "boolean") {
		if (perm) { perm = "true" } else { perm = "false" } }

	if (perm == 'true') {
		if (hover == 'in') {
			lock_title = strargs(gettext("Make group %1 not permissive"), [group_name]);
			lock_img = '/media/images/24x24/locked_over.png';
			lock_alt = gettext("Make group ") + group_name + " not permissive.";
		}
		else {
			lock_title = strargs(gettext("Make group %1 not permissive"), [group_name]);
			lock_img = '/media/images/24x24/locked_box.png';
			lock_alt = gettext("Make group ") + group_name + " not permissive.";
		}
	}
	else {
		lock_title = strargs(gettext("Make group %1 permissive"), [group_name]);
		lock_class = "locked_box user_lock_action";
		lock_img = '/media/images/24x24/locked.png';
		lock_alt = gettext("Make group ") + group_name + " permissive.";
	}

	return "<img src='"+lock_img+"' alt='"+lock_alt+"' title='"+lock_title+"'/>"
}
