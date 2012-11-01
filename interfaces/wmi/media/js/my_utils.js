
function password_helpers(content) {
	// setup password helpers such as 'Password matching', 'Password strenght',
	// 'Password generator'

	// setup interface, add  the #check_pwds and #pwd_strenght spans
	pwd_strenght = $('<span></span>')
	pwd_check = $('<span></span>')

	generate_pwd = $('<span><img id="generate_pwds" src="/media/images/16x16/generate.png" alt="'+ gettext("Generate passwords") +'"/></span>')
	generate_pwd.clickover({
		title : gettext("Random password generator"),
		content : '',
	})
	$.get('/users/generate_pwd/', function(html) {
		generate_pwd.attr("data-content", html);
	})

	content.find("input:password:first").parent().append(generate_pwd).append(pwd_strenght)
	content.find("input:password:last").parent().append(pwd_check)

	var url_tim;
	content.find('input:password').keyup(function() {

		clearTimeout(url_tim)

		var one_password_empty = false;
		content.find('input:password').each(function() {
			if ($(this).val() == '') {
				one_password_empty = true;
			}
		});

		// while one of the two password field is empty do not do anything.
		if ( !one_password_empty ) {
				var first = true;
				var passwords_match = true;
				content.find('input:password').each(function() {
					if (first) {
						pwd = $(this).val();
					}
					else {
						if (pwd != $(this).val()) { passwords_match = false; }
					}
					first = false;
				});
				if ( passwords_match ) {
					// if passwords match, check password strenght and present it to the user
					pwd_check.html('<img src="/media/images/16x16/check_ok.png"/>');

					$.get("/users/check_pwd_strenght/"+pwd, function(html) {
						if (html != pwd) {
							pwd_strenght.html("<div class='check_pwd_recap' style='color:red;'>" + html +"</div>")
						}
						else {
							pwd_strenght.html("<div class='check_pwd_recap' style='color:green;'> Mot de passe sécurisé </div>" )
						}
						url_tim = setTimeout(function() {
							$.get($('input:password:last').data('instant-url')+$('input:password:last').val())
						}, 1000);
					});
				}
				else {
					// passwords not matching
					pwd_check.html('<img src="/media/images/16x16/check_bad.png"/>');
					pwd_strenght.html('')
				}
		}
		else {
			content.find('#check_pwds').html('')
			content.find('#pwd_strenght').html('')
		}
	});

	generate_pwd.click(function() {
		var pwd_generated = null;
		$.get('/users/generate_pwd/', function(html) {
			generate_pwd.attr("data-content", html);
		})
		$('#confirm_generated_password').click(function(event) {
			content.find('input:password').val($('#generated_password').val()).keyup();
		})

	});
}

var reA = /[^a-zA-Z]/g;
var reN = /[^0-9]/g;

function sort_alphanum(a, b) {
	var aA = a.replace(reA, "");
    var bA = b.replace(reA, "");
    if(aA === bA) {
        var aN = parseInt(a.toString().replace(reN, ""), 10);
        var bN = parseInt(b.toString().replace(reN, ""), 10);
        return aN === bN ? 0 : aN > bN ? 1 : -1;
    } else {
        return aA > bA ? 1 : -1;
    }
}


var tab_sort = { "alpha": true, "relation": false}

function setup_sort_items(elements, sort_items, alpha_search) {
	// sort elements in differents ways

	// initialize interface item
	$.each(sort_items, function(i, item) {
		// setup interface
		if (tab_sort[$(item).data('sort')]) {
			$(item).addClass('active')
		}
		else {
			$(item).removeClass('active')
		}
	})
	// on click, start sorting
	$(sort_items).click(function(e) {
		do_sort($(this).data('id'), $(this).data('sort'));
	})

	// function that make the sort
	function do_sort(div, sort_item) {

		tab = $('#'+div+' '+elements)
		tab.sort(function(a, b) {

			// we currently have two way to sort : alphanumeric and by relationship
			if (sort_item == 'alpha') {
				a = $(a).find('.'+alpha_search).text().toLowerCase()
				b = $(b).find('.'+alpha_search).text().toLowerCase()

				return sort_alphanum(a, b);
			}

			else if (sort_item == 'relation') {
				arel = $(a).attr('data-rel')
				brel = $(b).attr('data-rel')

				// sort on relationship, and, if equal sort alphanumeric way
				if (arel == brel) {
					a = $(a).find('.'+alpha_search).text().toLowerCase()
					b = $(b).find('.'+alpha_search).text().toLowerCase()

					return sort_alphanum(a, b);
				}
				else {
					// bigger relation in top
					if (arel > brel) {
						return -1
					}
					else {
						return 1
					}
				}
			}
		})

		// hide elements, re-append them in the good order and finally show them
		$('#'+div+' '+elements).hide()

		$.each(tab, function(i, item) {
			$('#'+div).append($(item))
		})

		$('#'+div+' '+elements).show()
	}

}

function my_setup_table_search(searchbox) {
	// setup a timer in order to let the user type several letter
	// in the search field before making search happens
	var search_timeout;
	searchbox.keyup(function() {
	
		// clear the timer
		clearTimeout(search_timeout)
		search_timeout = setTimeout( function() {

			// get the value to search
			val = searchbox.val()

			// do not search through 'filtered' rows
			$('.filtered:not(.hidden)').addClass('hidden');

			if (val == '') {
				$('.not_filtered').css('display', '').removeClass('hidden')
				$('.filtered').removeClass('hidden')

			} else {
				$('.not_filtered:not(:contains('+val+'))').css('display', 'none').addClass('hidden')
				$('.not_filtered:contains('+val+')').css('display', '').removeClass('hidden')
			}
		}, 500);
	})
}

function setup_sortabletable(list_name) {
	st = new SortableTable(document.getElementById("model_"+list_name+"_table"),
			get_list_column())

	// setup default sort state
	$('#model_'+list_name+'_table').attr('data-sort-col', 2)
	$('.table_column_header').each(function(i, header) {
		$(header).attr('data-sort-col', i)
		$(header).attr('data-sort-way', 0)
		if (parseInt(i)==2) {
			$(header).addClass('ascending')
		}
	})
	$('.table_column_header').click(function() {
		console.log('click')
		// set new context
		_THIS       = $(this);
		current_way = _THIS.attr('data-sort-way');

		if (current_way == 1) {
			new_way = 0;

		} else {
			new_way = 1;
		}

		_THIS.attr('data-sort-way', new_way);
		$('#model_'+list_name+'_table').attr('data-sort-col', _THIS.data('sort-col'));

		animate = $('#model_'+list_name+'_table .licorn_row').length > max_items_animate;
		//console.log('SORTING, SHOULD WE ANIMATE ?', animate);

		if (animate) {
			// true, in order to fit table content
			loading_animation_func(gettext('Please wait while sorting list'), true);

			tim = setTimeout( function() {
				st.sort(_THIS.attr('data-sort-col'), new_way);
				remove_loading_animation();
			}, 500);

		} else {
			st.sort(_THIS.attr('data-sort-col'), new_way);
		}
	})
}

function setup_table_filter(div, items, filters) {
	/* setup table filters */

	$.each(items, function(i, item) {
		// setup interface
		if (filters[$(item).data('filter')]) {
			$(item).addClass('active')
		}
		else {
			$(item).removeClass('active')
		}
	})

	$(items).click(function() {
		// check the filter state
		if ($(this).hasClass('active')) {
			// the filter is currently activated, disable it
			$(this).removeClass('.active');
			filters[$(this).data('filter')] = false;
		}
		else {
			// set the filter as active
			$(this).addClass('.active')
			filters[$(this).data('filter')] = true;
		}
		do_filter();
		$('#list_search').keyup()
	})

	do_filter();

	function do_filter() {
		/* really do the filter, show/hide rows */
		$.each(filters, function(name, on_state) {
			filter_items = $('#'+div+' .filter_'+name+'')
			if (on_state) {
				filter_items.addClass('not_filtered').removeClass('filtered').css('display', '')
			}
			else {
				filter_items.removeClass('not_filtered').addClass('filtered').css('display', 'none');
			}
		})
	}
}

function setup_massive_actions(list_name) {
	if (list_name[list_name.length-1] == 's') {
		item_name = list_name.substring(0, list_name.length-1)
	}
	else {
		item_name = list_name
	}

	//console.log('setup_massive_actions', list_name, item_name);

	$('.massive_action').click(function() {
		// get selected items
		selected_rows = get_selected_rows($('#model_'+list_name+'_table tbody'), select_active_class);

		action_name = $(this).data('name')
		action_url = $(this).data('url')

		if (selected_rows.length == 0) {
			show_message_through_notification('{{ _("Please select at least one <strong><em>'+item_name+'</em></strong> to apply massive action <strong><em>'+action_name+'</em></strong> on") }}');
		}
		else {
			ids=[]
			$.each(get_selected_rows($('#model_'+list_name+'_table tbody'), select_active_class), function(i, item) {
				ids.push($(item).data('id'))
			})

			// get the massive selection template
			url = '/'+list_name+'/massive_select_template/'+action_name+'/'+ids.join(',')
			
			$.get(url, function(modal_html) {
				$("#modal").html(modal_html).modal()
				init_massive_select_events(action_name, action_url, ids);
			})
		}
	})
}

function init_massive_select_events(action_name, action_url, ids) {
	
	$('#apply_massive_action').click(function() {
		// run the action
		if (action_name == 'export') {
			$.get(action_url + ids+ '/' + $('#id_export_type').val(), function(data) {
				file_name = data.file_name
				iframe = document.getElementById('download_iframe')
				iframe.src = "/system/download/"+file_name
			}, "json")
		}
		else if (action_name == 'delete') {
			if ($('#delete_no_archive').is(':checked')) {
				no_archive = "True";

			} else {
				no_archive = ""; // python : bool('') = False
			}

			$.get(action_url + ids+ '/' + no_archive)
		}
		else if (action_name == 'upgrade') {
			if ($('#software_upgrade').is(':checked')) {
				software_upgrades = "True";

			} else {
				software_upgrades = ""; // python : bool('') = False
			}
			$.get(action_url + ids+ '/' + software_upgrades)
		}
		else {
			$.get(action_url + ids);
		}

		// unselect all rows
		//$('.'+select_active_class).removeClass(select_active_class);

		//hide the modal
		$('#modal').modal('hide');
	});
}

function setup_hover(list_name) {
	// on row hover, always clean interface in case of previus preselection with keyboard
	$('#model_'+list_name+'_table tbody tr').hover(function(){
		//in
		
		// change the background color to preselect it
		$(this).css({'background-color': background_color_hover})

		$('.preselected_row').removeClass('preselected_row').css({"background-color":"none"})
		//$(this).addClass('preselected_row')

	}, function() {
		//out
		$(this).css({'background-color': "none"})
	})
}

function get_row_filter(row) {
	var found;
	$.each(filters, function(filter) {
		//console.log(filter);
		if ($(row).hasClass('filter_'+filter)) {
			//console.log('filter found ', filter);
			found = filter
		}

	})
	return found
}

function does_row_match_search(row) {
	search_val = $('#list_search').val()

	if (search_val == '') {
		return true;
	}
	else if ($(row).text().indexOf(search_val) != -1) {
		return true;
	}
	else {
		return false
	}
}

function update_number_items(list_name) {
	$('#model_'+list_name+'_count').html($('#model_'+list_name+'_table .licorn_row:visible').length)
}
function update_total_items(list_name, number) {
	console.log("update_total_items", number)
	$('#model_'+list_name+'_total').html(number)
}

function bind_hotkeys(list_name) {
	/* Bind all hotkeys

		- J/K : preselect previus/following row
		- S : select/unselect a preselected row

		- N : add a new group

		- ENTER :
			- if modal is not visible : edit/mass edit selected row(s)

		if modal not visible and searchbox not focused :
			- SUPPR / DELETE : massive delete operation on selected row(s)
			- L : massive reapply skel to groups' members operation on selected row(s)
			- X : massive export operation on selected row(s)
			- p : massive toggle permissive operation on selected row(s)

		- ESCAPE : (in order)
			- if modal visible : hide the modal
			- if searchbox focused : unfocus it
			- if row(s) selected : unselect it

		NOTE : we are catching keyup and keypressed
	*/

	// cache selectors used
	var searchb = $('#list_search');
	var modal = $('#modal')

	$(document).keyup(function(e) {
		
		if (e.which == 8 || e.which == 46) {    // SUPPR => mass delete
			if (! searchb.is(':focus') && modal.is(':hidden')) {
				$('#massive_delete').click()
			}
		}

		if (e.which == 27) {    // ESC
			// on ESC, first hide modal is visible, secondly
			// remove search content, thirdly unselect row

			if (modal.is(':visible')) {
				modal.modal('hide')
			}
			else if (searchb.is(':focus')) {
				searchb.val('');
				searchb.keyup();
				searchb.blur();

				e.stopPropagation();
				e.preventDefault();

			}
			else {
				$('.'+select_active_class).removeClass(select_active_class)
			}


		}
		if (! searchb.is(':focus') && $('#modal').is(':hidden')) {

			if (e.which == 78) {    // n => new group
				//console.log('toototototototo');
				$.get('/'+list_name+'/new', function(html) {
					modal.html(html).modal()
				})
			}

		}
	});
	$(document).keypress(function(e) {

		/* Rows selection mecanism */
		if ( !searchb.is(':focus') && modal.is(':hidden')) {
			if (e.which == 106 || e.which == 107 || e.which == 115) {
				var preselected_row  = null;

				var next_row         = null
				var previus_row      = null
				var new_selected_row = null

				// find where to start
				if ($('.preselected_row').length == 0) {

					$.each($('tbody tr'), function() {
						if ($(this).css('background-color') == background_color_hover) {
							preselected_row = $(this);
						}
					});
				}
				else {
					preselected_row = $('.preselected_row')
				}
			}

			if (e.which == 107) {    // K = next
				if (preselected_row == null) {
					// no, preselected row, start from the top
					new_selected_row = $('table tbody tr:first');
				}
				else {
					// one row is already preselected, start from it
					next_row = preselected_row.next(':visible')
					if (next_row.length == 0) {
						next_row = preselected_row.nextUntil(':visible').last().next()
					}
					new_selected_row = next_row;					}
			}

			if (e.which == 106) {    // J = previus
				if (preselected_row == null) {
					// no, preselected row, start from the top
					new_selected_row = $('table tbody tr:first');
				}
				else {
					// one row is already preselected, start from it
					prev_row = preselected_row.prev(':visible')
					if (prev_row.length == 0) {
						prev_row = preselected_row.prevUntil(':visible').prev().last();
					}
					new_selected_row = prev_row;

				}

			}
			if (e.which == 106 || e.which == 107) {

				if (new_selected_row.length != 0) {
					if (preselected_row != null) {
						// unpreselect preselected_row
						preselected_row.css({'background-color': "none"})
					}
					$('.preselected_row').removeClass('preselected_row')

					new_selected_row.addClass('preselected_row').css({'background-color' : background_color_hover})

					// scroll the body to have the selected row at the middle of the screen
					// NOTE : in chrome, selecting body is ok, but in FF we need to select html...
					$('body,html').scrollTop(new_selected_row.position().top - $(window).height() / 2)
				}
			}

			if (e.which == 115) {    // s
				if (preselected_row.hasClass(select_active_class)) {
					preselected_row.removeClass(select_active_class)
				}
				else {
					// if a row is "preselected", select it
					$('.preselected_row').removeClass('preselected_row')
					preselected_row.addClass('preselected_row').addClass(select_active_class)
				}
			}
		}
		if (e.which == 13) {    // enter
			if (modal.is(':hidden')) {
				selected_rows = get_selected_rows($('#model_'+list_name+'_table tbody'), select_active_class);
				
				if (selected_rows.length == 1) {
					gid = $(selected_rows).data('id');
					$.get('/'+list_name+'/edit/'+gid, function(modal_html) {
						modal.html(modal_html).modal()
					})
				}
				else if (selected_rows.length > 1) {
					$('#massive_edit').click()
				}
			}
			else {
				$('#apply_massive_action').trigger('click')
			}
		}

		if (! searchb.is(':focus') && $('#modal').is(':hidden')) {
			if (e.which == 112) {    // p
				//console.log('list', list_name)
				if (list_name == 'groups') {
					$('#massive_permissive').click()
				}
				else if (list_name == 'users') {
					$('#massive_lock').click()
				}
			}
			if (e.which == 120) {    // x => mass export
				$('#massive_export').click()
			}
			if (e.which == 108) {    // l => mass skel
				$('#massive_skel').click()
			}
			if (e.which == 63 && e.shiftKey) {    // ? => help
				$.get('/'+list_name+'/hotkeys_help', function(html) {
					modal.html(html).modal();
				})
			}
			if (e.which == 117) {    // u => machines.upgrade
				$('#massive_upgrade').click()
			}
			if (e.which == 104) {    // h => machine.shutdown
				$('#massive_shutdown').click()
			}
		}

	});
}

function get_changed_col(new_row, old_row) {
	/* helper to determine which cell of a row has changed */

	new_tds = $(new_row).find('td');
	old_tds = $(old_row).find('td');

	if (old_tds.length == 0) {
		// returns null if new row (no old row found)
		return null;
	}

	for (i=0;i<new_tds.length;i++) {
		if ($(new_tds[i]).html() != $(old_tds[i]).html()) {
			return i
		}
	}
}
